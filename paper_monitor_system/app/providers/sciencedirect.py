from __future__ import annotations

from datetime import date, timedelta
from typing import Iterator, Sequence

import requests
from bs4 import BeautifulSoup

from ..config import (
    ELSEVIER_API_KEY,
    ELSEVIER_INSTTOKEN,
    ENABLE_CROSSREF_FALLBACK,
    ENABLE_SCIENCEDIRECT_API,
    ENABLE_SCIENCEDIRECT_PAGE,
    ENABLE_SCIENCEDIRECT_RSS,
    HTTP_TIMEOUT,
)
from ..journals import JournalSpec, display_issn
from ..utils import build_session, clean_doi, get_json, normalize_space
from . import crossref
from .base import ArticleRecord
from .enrichment import extract_doi, page_metadata, resolve_crossref
from .rss_source import fetch_rss

BASE_URL = "https://api.elsevier.com/content/search/sciencedirect"


def _query_for_spec(spec: JournalSpec, load_day: date) -> str:
    date_clause = f"Load-Date({load_day:%Y%m%d})"
    if spec.issns:
        issn_clause = " OR ".join(f"ISSN({display_issn(i)})" for i in spec.issns)
        return f"{date_clause} AND ({issn_clause})"
    safe_title = spec.journal.replace("}", "\\}").replace("{", "\\{")
    return f"{date_clause} AND Srctitle({{{safe_title}}})"


def _base_url(spec: JournalSpec) -> str:
    url = spec.primary_url.rstrip("/")
    for suffix in ("/articles-in-press", "/latest"):
        if suffix in url:
            return url.split(suffix)[0]
    return url


def _candidate_pages(spec: JournalSpec) -> list[str]:
    base = _base_url(spec)
    candidates = [spec.primary_url] if spec.primary_url else []
    if base:
        candidates.extend([f"{base}/articles-in-press", f"{base}/latest", base])
    out: list[str] = []
    for url in candidates:
        if url and url not in out:
            out.append(url)
    return out


def _api_discover(spec: JournalSpec, start: date, end: date) -> list[ArticleRecord]:
    """Optional ScienceDirect Search API discovery.

    Load-Date is used only to discover records. It is NOT used as online_date.
    Crossref/publisher metadata must provide published-online before publication.
    """
    if not ELSEVIER_API_KEY:
        raise RuntimeError("ELSEVIER_API_KEY is missing")
    session = build_session()
    headers = {"X-ELS-APIKey": ELSEVIER_API_KEY, "Accept": "application/json"}
    if ELSEVIER_INSTTOKEN:
        headers["X-ELS-Insttoken"] = ELSEVIER_INSTTOKEN

    records: list[ArticleRecord] = []
    seen: set[str] = set()
    day = start
    while day <= end:
        data = get_json(session, BASE_URL, params={
            "query": _query_for_spec(spec, day), "content": "journals", "start": 0, "count": 100,
        }, headers=headers)
        entries = ((data.get("search-results") or {}).get("entry") or [])
        for entry in entries:
            title = normalize_space(entry.get("dc:title") or "")
            doi = clean_doi(entry.get("prism:doi") or entry.get("dc:identifier"))
            if not title or not doi:
                continue
            try:
                cr = resolve_crossref(title, spec, doi)
            except requests.RequestException:
                cr = {}
            online = cr.get("online_date")
            if online and not (start <= online <= end):
                continue
            key = doi
            if key in seen:
                continue
            seen.add(key)
            records.append(ArticleRecord(
                provider="sciencedirect", publisher="Elsevier", title=title, journal=spec.journal,
                authors=cr.get("authors") or normalize_space(entry.get("dc:creator") or ""), doi=doi,
                external_id=normalize_space(entry.get("pii") or "") or doi,
                issn=normalize_space(entry.get("prism:issn") or "") or (display_issn(spec.issns[0]) if spec.issns else ""),
                content_type="Journal Article", url=cr.get("url") or f"https://doi.org/{doi}",
                online_date=online, online_date_raw=cr.get("online_raw") or "",
                date_precision=cr.get("precision") or "unknown",
                online_date_source=("ScienceDirect API discovery + Crossref published-online" if online else "ScienceDirect API discovery; awaiting published-online"),
                source_update_date=online, status="published" if online else "pending",
            ))
        day += timedelta(days=1)
    return records


def _page_records(spec: JournalSpec, start: date, end: date) -> list[ArticleRecord]:
    """Optional publisher-page path retained for networks where ScienceDirect pages are accessible."""
    session = build_session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    })
    last_error: Exception | None = None
    for page_url in _candidate_pages(spec):
        try:
            response = session.get(page_url, timeout=HTTP_TIMEOUT)
            response.raise_for_status()
        except requests.RequestException as exc:
            last_error = exc
            continue
        soup = BeautifulSoup(response.text, "html.parser")
        links: list[tuple[str, str]] = []
        for a in soup.find_all("a", href=True):
            href = normalize_space(a.get("href") or "")
            if "/science/article/pii/" not in href:
                continue
            full = requests.compat.urljoin(response.url, href)
            title = normalize_space(a.get_text(" ", strip=True))
            if title:
                links.append((full, title))
        found: list[ArticleRecord] = []
        seen: set[str] = set()
        for link, title in links[:160]:
            try:
                meta = page_metadata(link)
            except requests.RequestException:
                meta = {}
            doi = meta.get("doi") or extract_doi(link)
            try:
                cr = resolve_crossref(title, spec, doi)
            except requests.RequestException:
                cr = {}
            online = meta.get("online_date") or cr.get("online_date")
            if not online or not (start <= online <= end):
                continue
            key = doi or link
            if key in seen:
                continue
            seen.add(key)
            found.append(ArticleRecord(
                provider="sciencedirect", publisher="Elsevier", title=meta.get("title") or title,
                journal=spec.journal, authors=meta.get("authors") or cr.get("authors") or "",
                doi=doi or cr.get("doi"), external_id=link,
                issn=meta.get("issn") or cr.get("issn") or (display_issn(spec.issns[0]) if spec.issns else ""),
                content_type="Journal Article", url=link, online_date=online,
                online_date_raw=meta.get("online_raw") or cr.get("online_raw") or "",
                date_precision=meta.get("precision") or cr.get("precision") or "unknown",
                online_date_source=("ScienceDirect page Available online" if meta.get("online_date") else "ScienceDirect page + Crossref published-online"),
                source_update_date=online,
            ))
        if found:
            return found
    if last_error:
        raise last_error
    return []


def _direct_rss_records(spec: JournalSpec, start: date, end: date) -> list[ArticleRecord]:
    if not ENABLE_SCIENCEDIRECT_RSS or not spec.rss_url:
        return []
    return list(fetch_rss(
        "sciencedirect", "Elsevier", spec, spec.rss_url, start, end,
        "ScienceDirect direct RSS + publisher/Crossref online date", allow_pending=True,
    ))


def fetch(start: date, end: date, journals: Sequence[JournalSpec]) -> Iterator[ArticleRecord]:
    """LOCAL V2 Elsevier strategy: optional direct RSS + Crossref incremental.

    ScienceDirect API/page paths remain opt-in and disabled by default after the
    user's local connectivity test returned HTTP 401/403.
    """
    seen: set[str] = set()
    api_count = page_count = rss_count = 0

    for spec in journals:
        local_records: list[ArticleRecord] = []
        if ENABLE_SCIENCEDIRECT_API:
            try:
                local_records.extend(_api_discover(spec, start, end))
                api_count += 1
            except Exception as exc:
                status = getattr(getattr(exc, "response", None), "status_code", None)
                print(f"[sciencedirect] optional API warning: {spec.journal}: HTTP {status} {type(exc).__name__}")
        if ENABLE_SCIENCEDIRECT_PAGE:
            try:
                page_records = _page_records(spec, start, end)
                local_records.extend(page_records)
                if page_records:
                    page_count += 1
            except Exception as exc:
                status = getattr(getattr(exc, "response", None), "status_code", None)
                print(f"[sciencedirect] optional page warning: {spec.journal}: HTTP {status} {type(exc).__name__}")
        if spec.rss_url and ENABLE_SCIENCEDIRECT_RSS:
            try:
                rss_records = _direct_rss_records(spec, start, end)
                local_records.extend(rss_records)
                if rss_records:
                    rss_count += 1
            except Exception as exc:
                status = getattr(getattr(exc, "response", None), "status_code", None)
                print(f"[sciencedirect] direct RSS warning: {spec.journal}: HTTP {status} {type(exc).__name__}")

        for record in local_records:
            key = record.doi or record.external_id or record.title.lower()
            if key and key not in seen:
                seen.add(key)
                yield record

    crossref_count = 0
    if ENABLE_CROSSREF_FALLBACK:
        try:
            for record in crossref.incremental_discover("sciencedirect", "Elsevier", end, journals):
                key = record.doi or record.external_id or record.title.lower()
                if key and key not in seen:
                    seen.add(key)
                    crossref_count += 1
                    yield record
        except Exception as exc:
            print(f"[sciencedirect] Crossref incremental ERROR: {type(exc).__name__}: {exc}")
            raise

    print(
        f"[sciencedirect] sources: optional_api_journals={api_count}, optional_page_journals={page_count}, "
        f"direct_rss_journals={rss_count}, crossref_incremental_records={crossref_count}, total_unique={len(seen)}"
    )

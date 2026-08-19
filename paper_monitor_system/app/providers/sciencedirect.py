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
    HTTP_TIMEOUT,
)
from ..journals import JournalSpec, display_issn, match_journal
from ..utils import build_session, clean_doi, first_nonempty, get_json, join_authors, normalize_space
from . import crossref
from .base import ArticleRecord
from .enrichment import extract_doi, page_metadata, resolve_crossref
from .rss_source import fetch_rss

BASE_URL = "https://api.elsevier.com/content/search/sciencedirect"


def _date_range(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _scidir_link(entry: dict) -> str:
    links = entry.get("link") or []
    if isinstance(links, dict):
        links = [links]
    for link in links:
        if isinstance(link, dict) and link.get("@ref") == "scidir" and link.get("@href"):
            return str(link["@href"])
    doi = clean_doi(first_nonempty(entry.get("prism:doi"), entry.get("dc:identifier")))
    return f"https://doi.org/{doi}" if doi else ""


def _authors(entry: dict) -> str:
    authors = entry.get("authors") or {}
    if isinstance(authors, dict):
        authors = authors.get("author") or authors
    return join_authors(authors)


def _query_for_spec(spec: JournalSpec, load_day: date) -> str:
    date_clause = f"Load-Date({load_day:%Y%m%d})"
    if spec.issns:
        issn_clause = " OR ".join(f"ISSN({display_issn(i)})" for i in spec.issns)
        return f"{date_clause} AND ({issn_clause})"
    safe_title = spec.journal.replace("}", "\\}").replace("{", "\\{")
    return f"{date_clause} AND Srctitle({{{safe_title}}})"


def _api_one(spec: JournalSpec, start: date, end: date) -> list[ArticleRecord]:
    if not ELSEVIER_API_KEY:
        raise RuntimeError("ELSEVIER_API_KEY is missing")

    session = build_session()
    headers = {"X-ELS-APIKey": ELSEVIER_API_KEY, "Accept": "application/json"}
    if ELSEVIER_INSTTOKEN:
        headers["X-ELS-Insttoken"] = ELSEVIER_INSTTOKEN

    records: list[ArticleRecord] = []
    seen: set[str] = set()
    for load_day in _date_range(start, end):
        offset = 0
        while True:
            params = {
                "query": _query_for_spec(spec, load_day),
                "content": "journals",
                "start": offset,
                "count": 100,
            }
            data = get_json(session, BASE_URL, params=params, headers=headers)
            results = data.get("search-results", {})
            entries = results.get("entry") or []
            if isinstance(entries, dict):
                entries = [entries]

            for e in entries:
                title = normalize_space(e.get("dc:title"))
                if not title:
                    continue
                doi = clean_doi(first_nonempty(e.get("prism:doi"), e.get("dc:identifier")))
                pii = first_nonempty(e.get("pii"), e.get("eid"))
                journal = normalize_space(e.get("prism:publicationName"))
                issn = normalize_space(first_nonempty(e.get("prism:issn"), e.get("prism:eIssn")))
                matched = match_journal("sciencedirect", journal, issn, [spec])
                if matched is None and journal and journal.lower() != spec.journal.lower():
                    continue
                identity = doi or str(pii or "") or title.lower()
                if identity in seen:
                    continue
                seen.add(identity)
                records.append(ArticleRecord(
                    provider="sciencedirect",
                    publisher="Elsevier",
                    title=title,
                    journal=spec.journal,
                    authors=_authors(e) or normalize_space(e.get("dc:creator")),
                    doi=doi,
                    external_id=str(pii) if pii else None,
                    issn=issn or (display_issn(spec.issns[0]) if spec.issns else ""),
                    content_type="Journal Article",
                    url=_scidir_link(e),
                    online_date=load_day,
                    online_date_raw=load_day.isoformat(),
                    date_precision="day",
                    online_date_source="ScienceDirect API Load-Date",
                    source_update_date=load_day,
                ))

            total = int(results.get("opensearch:totalResults") or len(entries) or 0)
            items = int(results.get("opensearch:itemsPerPage") or len(entries) or 0)
            step = max(items, len(entries))
            if not entries or step <= 0 or offset + step >= total:
                break
            offset += step
    return records


def _base_url(spec: JournalSpec) -> str:
    u = spec.primary_url.rstrip("/")
    for suffix in ("/articles-in-press", "/latest"):
        if suffix in u:
            return u.split(suffix)[0]
    return u


def _candidate_pages(spec: JournalSpec) -> list[str]:
    base = _base_url(spec)
    candidates: list[str] = []
    if spec.primary_url:
        candidates.append(spec.primary_url)
    if base:
        candidates.extend([f"{base}/articles-in-press", f"{base}/latest", base])
    out: list[str] = []
    for url in candidates:
        if url and url not in out:
            out.append(url)
    return out


def _article_links(html: str, base_url: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = normalize_space(a.get("href", ""))
        if "/science/article/pii/" not in href:
            continue
        full = requests.compat.urljoin(base_url, href)
        if full in seen:
            continue
        title = normalize_space(a.get_text(" ", strip=True))
        if not title:
            continue
        seen.add(full)
        links.append((full, title))
    return links


def _page_records(spec: JournalSpec, start: date, end: date) -> list[ArticleRecord]:
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

        records: list[ArticleRecord] = []
        seen: set[str] = set()
        for link, title in _article_links(response.text, response.url)[:160]:
            meta: dict = {}
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
            raw = meta.get("online_raw") or cr.get("online_raw") or ""
            precision = meta.get("precision") or cr.get("precision") or "unknown"
            if not online or not (start <= online <= end):
                continue
            key = doi or link or title.lower()
            if key in seen:
                continue
            seen.add(key)
            source = (
                "ScienceDirect page Available online"
                if meta.get("online_date")
                else "ScienceDirect page + Crossref published-online"
            )
            records.append(ArticleRecord(
                provider="sciencedirect",
                publisher="Elsevier",
                title=meta.get("title") or title,
                journal=spec.journal,
                authors=meta.get("authors") or cr.get("authors") or "",
                doi=doi or cr.get("doi"),
                external_id=link,
                issn=meta.get("issn") or cr.get("issn") or (display_issn(spec.issns[0]) if spec.issns else ""),
                content_type="Journal Article",
                url=link,
                online_date=online,
                online_date_raw=raw,
                date_precision=precision,
                online_date_source=source,
                source_update_date=online,
            ))
        # A valid page with zero matching records is still useful; try other
        # candidate pages only if this page produced nothing.
        if records:
            return records
    if last_error:
        raise last_error
    return []


def _discover_rss_urls(spec: JournalSpec) -> list[str]:
    session = build_session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    })
    found: list[str] = []
    for page_url in _candidate_pages(spec):
        try:
            response = session.get(page_url, timeout=HTTP_TIMEOUT)
            response.raise_for_status()
        except requests.RequestException:
            continue
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup.find_all(["link", "a"], href=True):
            href = normalize_space(tag.get("href") or "")
            typ = normalize_space(tag.get("type") or "").lower()
            rel = " ".join(tag.get("rel") or []).lower() if isinstance(tag.get("rel"), list) else normalize_space(tag.get("rel") or "").lower()
            if "rss" in typ or "atom" in typ or "rss" in href.lower() or ("alternate" in rel and "xml" in typ):
                full = requests.compat.urljoin(response.url, href)
                if full and full not in found:
                    found.append(full)
        if found:
            break
    return found


def _rss_records(spec: JournalSpec, start: date, end: date) -> list[ArticleRecord]:
    urls: list[str] = []
    if spec.rss_url:
        urls.append(spec.rss_url)
    for url in _discover_rss_urls(spec):
        if url not in urls:
            urls.append(url)
    for url in urls:
        try:
            records = list(fetch_rss(
                "sciencedirect", "Elsevier", spec, url, start, end,
                "ScienceDirect RSS discovery + publisher/Crossref online date",
            ))
            if records:
                return records
        except Exception as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            suffix = f" HTTP {status}" if status else ""
            print(f"[sciencedirect] RSS warning: {spec.journal}:{suffix} {type(exc).__name__}")
    return []


def fetch(start: date, end: date, journals: Sequence[JournalSpec]) -> Iterator[ArticleRecord]:
    seen: set[str] = set()
    api_journals = page_journals = rss_journals = crossref_journals = 0
    api_disabled_for_run = not ENABLE_SCIENCEDIRECT_API or not ELSEVIER_API_KEY
    if ENABLE_SCIENCEDIRECT_API and not ELSEVIER_API_KEY:
        print("[sciencedirect] local API path enabled but ELSEVIER_API_KEY is missing; continuing with page/RSS/Crossref")

    for spec in journals:
        records: list[ArticleRecord] = []

        if not api_disabled_for_run:
            try:
                records = _api_one(spec, start, end)
                if records:
                    api_journals += 1
            except requests.HTTPError as exc:
                status = getattr(exc.response, "status_code", None)
                print(f"[sciencedirect] API warning: {spec.journal}: HTTP {status}")
                if status in {401, 403}:
                    print("[sciencedirect] API authorization appears unavailable on this network; disabling API for the remainder of this run")
                    api_disabled_for_run = True
            except Exception as exc:
                print(f"[sciencedirect] API warning: {spec.journal}: {type(exc).__name__}: {exc}")

        if not records:
            try:
                records = _page_records(spec, start, end)
                if records:
                    page_journals += 1
            except Exception as exc:
                status = getattr(getattr(exc, "response", None), "status_code", None)
                suffix = f" HTTP {status}" if status else ""
                print(f"[sciencedirect] page warning: {spec.journal}:{suffix} {type(exc).__name__}")

        if not records:
            records = _rss_records(spec, start, end)
            if records:
                rss_journals += 1

        if not records and ENABLE_CROSSREF_FALLBACK:
            try:
                records = list(crossref.fetch("sciencedirect", "Elsevier", start, end, [spec]))
                if records:
                    crossref_journals += 1
            except Exception as exc:
                print(f"[sciencedirect] Crossref warning: {spec.journal}: {type(exc).__name__}: {exc}")
                records = []

        for record in records:
            key = record.doi or record.external_id or record.title.lower()
            if not key or key in seen:
                continue
            seen.add(key)
            yield record

    print(
        f"[sciencedirect] sources: api_journals={api_journals}, page_journals={page_journals}, "
        f"rss_journals={rss_journals}, crossref_journals={crossref_journals}, records={len(seen)}"
    )

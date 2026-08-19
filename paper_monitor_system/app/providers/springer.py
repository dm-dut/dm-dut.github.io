from __future__ import annotations

from datetime import date
from typing import Iterator, Sequence

import requests
from bs4 import BeautifulSoup

from ..config import ENABLE_CROSSREF_FALLBACK, ENABLE_SPRINGER_API, HTTP_TIMEOUT, SPRINGER_API_KEY
from ..journals import JournalSpec, display_issn
from ..utils import build_session, clean_doi, first_nonempty, get_json, join_authors, normalize_space, parse_flexible_date
from . import crossref
from .base import ArticleRecord
from .enrichment import extract_doi, page_metadata, resolve_crossref

BASE_URL = "https://api.springernature.com/meta/v2/json"


def _online_url(spec: JournalSpec) -> str:
    url = spec.primary_url.rstrip("/")
    if "/journal/" in url:
        return url.split("/articles")[0].split("/online-first")[0] + "/online-first"
    return url


def _query_variants(spec: JournalSpec, start: date, end: date, issn: str | None) -> list[str]:
    base_space = f"onlinedatefrom:{start.isoformat()} onlinedateto:{end.isoformat()}"
    base_and = f"onlinedatefrom:{start.isoformat()} AND onlinedateto:{end.isoformat()}"
    out: list[str] = []
    if issn:
        di = display_issn(issn)
        out.extend([
            f"{base_space} issn:{di}",
            f"{base_and} AND issn:{di}",
        ])
    # Publication-title variant is intentionally last because some Springer
    # titles contain punctuation that may produce fewer hits than ISSN.
    out.append(f'{base_and} AND pub:"{spec.journal}"')
    return out


def _parse_records(spec: JournalSpec, rows: list[dict], start: date, end: date, seen: set[str]) -> list[ArticleRecord]:
    out: list[ArticleRecord] = []
    for row in rows:
        if normalize_space(row.get("publicationType")).lower() not in {"", "journal"}:
            continue
        raw = normalize_space(row.get("onlineDate"))
        online_date, precision = parse_flexible_date(raw)
        if not online_date or not (start <= online_date <= end):
            continue
        title = normalize_space(row.get("title"))
        doi = clean_doi(first_nonempty(row.get("doi"), row.get("identifier")))
        key = doi or normalize_space(row.get("identifier")) or title.lower()
        if not title or key in seen:
            continue
        seen.add(key)

        urls = row.get("url") or []
        if isinstance(urls, dict):
            urls = [urls]
        url = ""
        for item in urls:
            if isinstance(item, dict) and item.get("value"):
                url = item["value"]
                break

        out.append(ArticleRecord(
            provider="springer",
            publisher="Springer Nature",
            title=title,
            journal=spec.journal,
            authors=join_authors(row.get("creators") or []),
            doi=doi,
            external_id=normalize_space(row.get("identifier")) or doi,
            issn=display_issn(spec.issns[0]) if spec.issns else "",
            content_type="Journal Article",
            url=url,
            online_date=online_date,
            online_date_raw=raw,
            date_precision=precision,
            online_date_source="Springer Meta API onlineDate",
            source_update_date=online_date,
        ))
    return out


def _api(spec: JournalSpec, start: date, end: date) -> list[ArticleRecord]:
    if not SPRINGER_API_KEY:
        raise RuntimeError("SPRINGER_API_KEY missing")

    session = build_session()
    last_error: Exception | None = None
    # Prefer eISSN, then print ISSN. Each query syntax is tried independently
    # because Springer has historically been inconsistent about which complex
    # query forms return 404 vs an empty result.
    issns = list(reversed(spec.issns)) or [None]
    for issn in issns:
        for query in _query_variants(spec, start, end, issn):
            collected: list[ArticleRecord] = []
            seen: set[str] = set()
            start_index = 1
            try:
                while True:
                    data = get_json(session, BASE_URL, params={
                        "api_key": SPRINGER_API_KEY,
                        "q": query,
                        "s": start_index,
                        "p": 20,
                    })
                    rows = data.get("records") or []
                    collected.extend(_parse_records(spec, rows, start, end, seen))
                    if len(rows) < 20:
                        break
                    start_index += len(rows)
                # A successful 200 response, even with zero rows, proves this
                # query form is valid. Return and let the page fallback decide
                # whether zero records really means no new article.
                return collected
            except requests.RequestException as exc:
                last_error = exc
                status = getattr(getattr(exc, "response", None), "status_code", None)
                print(f"[springer] API query warning: {spec.journal}: HTTP {status}; trying alternate query")
                continue

    if last_error:
        raise last_error
    raise RuntimeError("Springer Meta API unavailable for journal")


def _page(spec: JournalSpec, start: date, end: date) -> list[ArticleRecord]:
    url = _online_url(spec)
    if not url:
        return []
    session = build_session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"})
    response = session.get(url, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    found: list[ArticleRecord] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if "/article/10." not in href:
            continue
        link = requests.compat.urljoin(response.url, href)
        title = normalize_space(a.get_text(" ", strip=True))
        if not title or link in seen:
            continue
        seen.add(link)
        meta: dict = {}
        try:
            meta = page_metadata(link)
        except requests.RequestException:
            pass
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
        found.append(ArticleRecord(
            provider="springer",
            publisher="Springer Nature",
            title=meta.get("title") or title,
            journal=spec.journal,
            authors=meta.get("authors") or cr.get("authors") or "",
            doi=doi or cr.get("doi"),
            external_id=link,
            issn=display_issn(spec.issns[0]) if spec.issns else "",
            content_type="Journal Article",
            url=link,
            online_date=online,
            online_date_raw=raw,
            date_precision=precision,
            online_date_source="Springer Online First page",
            source_update_date=online,
        ))
    return found


def fetch(start: date, end: date, journals: Sequence[JournalSpec]) -> Iterator[ArticleRecord]:
    seen: set[str] = set()
    api_journals = page_journals = crossref_journals = 0

    for spec in journals:
        records: list[ArticleRecord] = []
        if ENABLE_SPRINGER_API:
            try:
                records = _api(spec, start, end)
                api_journals += 1
            except Exception as exc:
                print(f"[springer] API warning: {spec.journal}: {type(exc).__name__}")

        if not records:
            try:
                records = _page(spec, start, end)
                if records:
                    page_journals += 1
            except Exception as exc:
                print(f"[springer] page warning: {spec.journal}: {type(exc).__name__}")

        if not records and ENABLE_CROSSREF_FALLBACK:
            try:
                records = list(crossref.fetch("springer", "Springer Nature", start, end, [spec]))
                if records:
                    crossref_journals += 1
            except Exception as exc:
                print(f"[springer] Crossref warning: {spec.journal}: {type(exc).__name__}: {exc}")
                records = []

        for record in records:
            key = record.doi or record.external_id or record.title.lower()
            if not key or key in seen:
                continue
            seen.add(key)
            yield record

    print(
        f"[springer] sources: api_journals={api_journals}, online_first_journals={page_journals}, "
        f"crossref_journals={crossref_journals}, records={len(seen)}"
    )

from __future__ import annotations

from datetime import date
from typing import Iterator, Sequence

import requests
from bs4 import BeautifulSoup

from ..config import (
    ENABLE_CROSSREF_FALLBACK,
    ENABLE_SPRINGER_API,
    ENABLE_SPRINGER_BATCH_API,
    HTTP_TIMEOUT,
    SPRINGER_API_KEY,
    SPRINGER_BATCH_MAX_PAGES,
    SPRINGER_BATCH_PAGE_SIZE,
)
from ..journals import JournalSpec, display_issn, match_journal
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
        out.extend([f"{base_space} issn:{di}", f"{base_and} AND issn:{di}"])
    out.append(f'{base_and} AND pub:"{spec.journal}"')
    return out


def _batch_query_variants(start: date, end: date) -> list[str]:
    return [
        f"onlinedatefrom:{start.isoformat()} onlinedateto:{end.isoformat()}",
        f"onlinedatefrom:{start.isoformat()} AND onlinedateto:{end.isoformat()}",
    ]


def _record_from_row(spec: JournalSpec, row: dict, start: date, end: date) -> ArticleRecord | None:
    if normalize_space(row.get("publicationType")).lower() not in {"", "journal"}:
        return None
    raw = normalize_space(row.get("onlineDate"))
    online_date, precision = parse_flexible_date(raw)
    if not online_date or not (start <= online_date <= end):
        return None
    title = normalize_space(row.get("title"))
    if not title:
        return None
    doi = clean_doi(first_nonempty(row.get("doi"), row.get("identifier")))
    urls = row.get("url") or []
    if isinstance(urls, dict):
        urls = [urls]
    url = ""
    for item in urls:
        if isinstance(item, dict) and item.get("value"):
            url = item["value"]
            break
    return ArticleRecord(
        provider="springer", publisher="Springer Nature", title=title, journal=spec.journal,
        authors=join_authors(row.get("creators") or []), doi=doi,
        external_id=normalize_space(row.get("identifier")) or doi,
        issn=normalize_space(row.get("issn") or "") or (display_issn(spec.issns[0]) if spec.issns else ""),
        content_type="Journal Article", url=url, online_date=online_date, online_date_raw=raw,
        date_precision=precision, online_date_source="Springer Meta API onlineDate", source_update_date=online_date,
    )


def _batch_api(start: date, end: date, journals: Sequence[JournalSpec]) -> list[ArticleRecord]:
    """Try one date-window Meta API stream and filter the returned records locally."""
    if not SPRINGER_API_KEY:
        raise RuntimeError("SPRINGER_API_KEY missing")
    session = build_session()
    last_error: Exception | None = None
    page_size = max(1, min(SPRINGER_BATCH_PAGE_SIZE, 100))

    for query in _batch_query_variants(start, end):
        try:
            records: list[ArticleRecord] = []
            seen: set[str] = set()
            start_index = 1
            for page_no in range(SPRINGER_BATCH_MAX_PAGES):
                data = get_json(session, BASE_URL, params={
                    "api_key": SPRINGER_API_KEY, "q": query, "s": start_index, "p": page_size,
                })
                rows = data.get("records") or []
                for row in rows:
                    spec = match_journal(
                        "springer",
                        normalize_space(row.get("publicationName") or row.get("publicationTitle") or ""),
                        normalize_space(row.get("issn") or ""),
                        journals,
                    )
                    if spec is None:
                        continue
                    record = _record_from_row(spec, row, start, end)
                    if record is None:
                        continue
                    key = record.doi or record.external_id or record.title.lower()
                    if key and key not in seen:
                        seen.add(key)
                        records.append(record)
                if len(rows) < page_size:
                    break
                start_index += len(rows)
            else:
                raise RuntimeError(f"Springer batch query exceeded {SPRINGER_BATCH_MAX_PAGES} pages")
            print(f"[springer] batch Meta API success: raw_pages={page_no + 1}, whitelist_records={len(records)}")
            return records
        except requests.RequestException as exc:
            last_error = exc
            status = getattr(getattr(exc, "response", None), "status_code", None)
            print(f"[springer] batch API query warning: HTTP {status}; trying alternate batch syntax")
        except Exception as exc:
            last_error = exc
            print(f"[springer] batch API warning: {type(exc).__name__}: {exc}")
            break

    if last_error:
        raise last_error
    raise RuntimeError("Springer batch Meta API unavailable")


def _api(spec: JournalSpec, start: date, end: date) -> list[ArticleRecord]:
    if not SPRINGER_API_KEY:
        raise RuntimeError("SPRINGER_API_KEY missing")
    session = build_session()
    last_error: Exception | None = None
    for issn in list(reversed(spec.issns)) or [None]:
        for query in _query_variants(spec, start, end, issn):
            collected: list[ArticleRecord] = []
            seen: set[str] = set()
            start_index = 1
            try:
                while True:
                    data = get_json(session, BASE_URL, params={
                        "api_key": SPRINGER_API_KEY, "q": query, "s": start_index, "p": 20,
                    })
                    rows = data.get("records") or []
                    for row in rows:
                        record = _record_from_row(spec, row, start, end)
                        if record:
                            key = record.doi or record.external_id or record.title.lower()
                            if key not in seen:
                                seen.add(key)
                                collected.append(record)
                    if len(rows) < 20:
                        break
                    start_index += len(rows)
                return collected
            except requests.RequestException as exc:
                last_error = exc
                status = getattr(getattr(exc, "response", None), "status_code", None)
                print(f"[springer] per-journal API query warning: {spec.journal}: HTTP {status}; trying alternate query")
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
        found.append(ArticleRecord(
            provider="springer", publisher="Springer Nature", title=meta.get("title") or title,
            journal=spec.journal, authors=meta.get("authors") or cr.get("authors") or "",
            doi=doi or cr.get("doi"), external_id=link,
            issn=meta.get("issn") or cr.get("issn") or (display_issn(spec.issns[0]) if spec.issns else ""),
            content_type="Journal Article", url=link, online_date=online,
            online_date_raw=meta.get("online_raw") or cr.get("online_raw") or "",
            date_precision=meta.get("precision") or cr.get("precision") or "unknown",
            online_date_source="Springer Online First page", source_update_date=online,
        ))
    return found


def fetch(start: date, end: date, journals: Sequence[JournalSpec]) -> Iterator[ArticleRecord]:
    seen: set[str] = set()

    if ENABLE_SPRINGER_API and ENABLE_SPRINGER_BATCH_API:
        try:
            batch = _batch_api(start, end, journals)
            for record in batch:
                key = record.doi or record.external_id or record.title.lower()
                if key and key not in seen:
                    seen.add(key)
                    yield record
            print(f"[springer] sources: batch_meta_api=1, records={len(seen)}")
            return
        except Exception as exc:
            print(f"[springer] batch Meta API unavailable ({type(exc).__name__}); falling back to per-journal chain")

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
            if key and key not in seen:
                seen.add(key)
                yield record

    print(
        f"[springer] sources: per_journal_api={api_journals}, online_first={page_journals}, "
        f"crossref={crossref_journals}, records={len(seen)}"
    )

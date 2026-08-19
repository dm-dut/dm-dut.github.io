from __future__ import annotations

from datetime import date
from time import perf_counter
from typing import Iterator, Sequence

import requests

from ..config import (
    ENABLE_CROSSREF_FALLBACK,
    ENABLE_SPRINGER_API,
    ENABLE_SPRINGER_BATCH_API,
    SPRINGER_API_KEY,
    SPRINGER_BATCH_MAX_PAGES,
    SPRINGER_BATCH_PAGE_SIZE,
)
from ..journals import JournalSpec, display_issn, match_journal
from ..utils import build_session, clean_doi, first_nonempty, get_json, join_authors, normalize_space, parse_flexible_date
from . import crossref
from .base import ArticleRecord

BASE_URL = "https://api.springernature.com/meta/v2/json"
SPRINGER_CROSSREF_PREFIX = "10.1007"


def _batch_query(start: date, end: date) -> str:
    # Springer Nature documents onlinedatefrom/onlinedateto as Meta API query constraints.
    # Space-separated constraints are used because the user's Basic Meta API key is known
    # to work, while explicit Boolean AND variants previously produced 403 responses.
    return f"onlinedatefrom:{start.isoformat()} onlinedateto:{end.isoformat()}"


def _batch_query_variants(start: date, end: date) -> list[str]:
    # Backward-compatible helper retained for self-tests/documentation.
    return [_batch_query(start, end)]


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


def _batch_api(start: date, end: date, journals: Sequence[JournalSpec]) -> tuple[list[ArticleRecord], bool]:
    """Run the Basic Meta API as one date-window batch and filter locally.

    The official Springer Nature client uses p=20 and caps Basic-plan pagination at
    start position 100. V3.1 follows that conservative behavior. If the API reaches
    that cap with full pages, `truncated=True` is returned so a single Crossref
    prefix-level batch can supplement the result. No per-journal Springer API loop
    is used.
    """
    if not SPRINGER_API_KEY:
        raise RuntimeError("SPRINGER_API_KEY missing")

    session = build_session()
    page_size = max(1, min(int(SPRINGER_BATCH_PAGE_SIZE), 20))
    max_pages = max(1, min(int(SPRINGER_BATCH_MAX_PAGES), 5))
    query = _batch_query(start, end)
    records: list[ArticleRecord] = []
    seen: set[str] = set()
    start_index = 1
    raw_total = 0
    t0 = perf_counter()
    last_full_page = False

    for page_no in range(1, max_pages + 1):
        data = get_json(session, BASE_URL, params={
            "api_key": SPRINGER_API_KEY,
            "q": query,
            "s": start_index,
            "p": page_size,
        })
        rows = data.get("records") or []
        raw_total += len(rows)
        print(
            f"[springer] Meta batch progress: page={page_no}/{max_pages}, "
            f"raw={raw_total}, whitelist={len(records)}"
        )
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
        last_full_page = len(rows) >= page_size
        if len(rows) < page_size:
            print(
                f"[springer] Meta batch success: pages={page_no}, raw={raw_total}, "
                f"whitelist_records={len(records)}, elapsed={perf_counter()-t0:.1f}s"
            )
            return records, False
        start_index += page_size
        if start_index > 100:
            break

    truncated = last_full_page
    print(
        f"[springer] Meta batch reached Basic-plan pagination cap: raw={raw_total}, "
        f"whitelist_records={len(records)}, truncated={'yes' if truncated else 'no'}, "
        f"elapsed={perf_counter()-t0:.1f}s"
    )
    return records, truncated


def fetch(start: date, end: date, journals: Sequence[JournalSpec]) -> Iterator[ArticleRecord]:
    t0 = perf_counter()
    seen: set[str] = set()
    api_ok = False
    truncated = False

    if ENABLE_SPRINGER_API and ENABLE_SPRINGER_BATCH_API:
        try:
            batch, truncated = _batch_api(start, end, journals)
            api_ok = True
            for record in batch:
                key = record.doi or record.external_id or record.title.lower()
                if key and key not in seen:
                    seen.add(key)
                    yield record
        except requests.RequestException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            print(f"[springer] Meta batch unavailable: HTTP {status}; using one Crossref prefix batch fallback")
        except Exception as exc:
            print(f"[springer] Meta batch unavailable: {type(exc).__name__}: {exc}; using Crossref prefix batch fallback")

    # Crucial V3.1 behavior: never fall back to 25 per-journal Springer API requests.
    # Crossref is queried once by Springer DOI prefix when the Meta API failed or hit
    # the Basic-plan result cap. Official Springer onlineDate remains higher priority
    # in the DB, so the supplement cannot overwrite it with a weaker date source.
    if ENABLE_CROSSREF_FALLBACK and (not api_ok or truncated):
        try:
            supplement = crossref.prefix_batch_discover(
                "springer", "Springer Nature", start, end, journals,
                prefix=SPRINGER_CROSSREF_PREFIX,
            )
            added = 0
            for record in supplement:
                key = record.doi or record.external_id or record.title.lower()
                if key and key not in seen:
                    seen.add(key)
                    added += 1
                    yield record
            print(f"[springer] Crossref prefix supplement added={added}")
        except Exception as exc:
            if not api_ok:
                raise RuntimeError(f"Springer Meta API and Crossref prefix fallback both failed: {exc}") from exc
            print(f"[springer] Crossref prefix supplement warning: {type(exc).__name__}: {exc}")

    if not api_ok and not ENABLE_CROSSREF_FALLBACK:
        raise RuntimeError("Springer Meta API failed and Crossref fallback is disabled")

    print(
        f"[springer] sources: meta_batch={'ok' if api_ok else 'failed'}, "
        f"crossref_prefix={'used' if (not api_ok or truncated) and ENABLE_CROSSREF_FALLBACK else 'not-needed'}, "
        f"records={len(seen)}, elapsed={perf_counter()-t0:.1f}s"
    )

from __future__ import annotations

from datetime import date, timedelta
from typing import Iterator, Sequence

import requests

from ..config import CROSSREF_MAILTO, CROSSREF_DISCOVERY_DAYS
from ..journals import JournalSpec, display_issn, normalize_issn
from ..utils import build_session, clean_doi, get_json, normalize_space
from .base import ArticleRecord

BASE_URL = "https://api.crossref.org"


def _date_parts(item: dict) -> tuple[date | None, str, str]:
    block = item.get("published-online") or {}
    parts_list = block.get("date-parts") or []
    if not parts_list or not parts_list[0]:
        return None, "unknown", ""
    parts = parts_list[0]
    try:
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 1
        day = int(parts[2]) if len(parts) > 2 else 1
        precision = "day" if len(parts) > 2 else ("month" if len(parts) > 1 else "year")
        raw = f"{year:04d}" if precision == "year" else (
            f"{year:04d}-{month:02d}" if precision == "month" else f"{year:04d}-{month:02d}-{day:02d}"
        )
        return date(year, month, day), precision, raw
    except (TypeError, ValueError, IndexError):
        return None, "unknown", ""


def _authors(item: dict) -> str:
    out: list[str] = []
    for author in item.get("author") or []:
        if not isinstance(author, dict):
            continue
        given = normalize_space(str(author.get("given") or ""))
        family = normalize_space(str(author.get("family") or ""))
        name = normalize_space(f"{given} {family}")
        if name:
            out.append(name)
    return "; ".join(out)


def _first_text(value) -> str:
    if isinstance(value, list):
        return normalize_space(str(value[0])) if value else ""
    return normalize_space(str(value or ""))


def _status_label(exc: Exception) -> str:
    status = getattr(getattr(exc, "response", None), "status_code", None)
    return f"HTTP {status}" if status else type(exc).__name__


def _request_items(session, issn: str, filters: list[str]) -> list[dict]:
    """Query Crossref's global /works endpoint.

    Previous builds used /journals/{issn}/works. Some valid journal ISSNs returned
    404 from that journal-scoped endpoint even though the same ISSN is queryable
    through the global /works endpoint. Crossref documents `issn` as a Works
    filter, so the global endpoint is both simpler and more tolerant.
    """
    normalized = normalize_issn(issn)
    if len(normalized) != 8:
        return []

    url = f"{BASE_URL}/works"
    all_filters = [f"issn:{display_issn(normalized)}", *filters]
    params = {
        "filter": ",".join(all_filters),
        "rows": 200,
        "cursor": "*",
    }
    if CROSSREF_MAILTO:
        params["mailto"] = CROSSREF_MAILTO

    items: list[dict] = []
    cursor = "*"
    for _ in range(20):  # ample for a short date window on a single journal
        params["cursor"] = cursor
        data = get_json(session, url, params=params)
        message = data.get("message") or {}
        batch = message.get("items") or []
        items.extend(item for item in batch if isinstance(item, dict))
        next_cursor = message.get("next-cursor")
        if not batch or not next_cursor or next_cursor == cursor or len(batch) < int(params["rows"]):
            break
        cursor = next_cursor
    return items


def _to_record(
    provider: str,
    publisher: str,
    spec: JournalSpec,
    item: dict,
    start: date,
    end: date,
) -> ArticleRecord | None:
    online_date, precision, raw_date = _date_parts(item)
    # Never substitute print/issued dates: this monitor is explicitly online-date based.
    if online_date is None or online_date < start or online_date > end:
        return None

    title = _first_text(item.get("title"))
    if not title:
        return None

    doi = clean_doi(item.get("DOI"))
    url = normalize_space(str(item.get("URL") or ""))
    if not url and doi:
        url = f"https://doi.org/{doi}"
    alt = item.get("alternative-id") or []
    external_id = normalize_space(str(alt[0])) if isinstance(alt, list) and alt else None
    issns = "; ".join(str(value) for value in (item.get("ISSN") or []) if value)

    return ArticleRecord(
        provider=provider,
        publisher=publisher,
        title=title,
        journal=spec.journal,
        authors=_authors(item),
        doi=doi,
        external_id=external_id,
        issn=issns or (display_issn(spec.issns[0]) if spec.issns else ""),
        content_type="Journal Article",
        url=url,
        online_date=online_date,
        online_date_raw=raw_date,
        date_precision=precision,
        online_date_source="Crossref published-online fallback",
        source_update_date=online_date,
    )


def _records_for_issn(
    session,
    provider: str,
    publisher: str,
    spec: JournalSpec,
    issn: str,
    start: date,
    end: date,
) -> list[ArticleRecord]:
    direct_filters = [
        "type:journal-article",
        f"from-online-pub-date:{start.isoformat()}",
        f"until-online-pub-date:{end.isoformat()}",
    ]
    items = _request_items(session, issn, direct_filters)
    records = [record for item in items if (record := _to_record(provider, publisher, spec, item, start, end))]
    if records:
        return records

    # Conservative second pass: inspect recently indexed metadata, but still
    # require an actual published-online value within the requested window.
    discovery_start = start - timedelta(days=CROSSREF_DISCOVERY_DAYS)
    indexed_filters = [
        "type:journal-article",
        f"from-index-date:{discovery_start.isoformat()}",
        f"until-index-date:{(end + timedelta(days=1)).isoformat()}",
    ]
    items = _request_items(session, issn, indexed_filters)
    return [record for item in items if (record := _to_record(provider, publisher, spec, item, start, end))]


def fetch(
    provider: str,
    publisher: str,
    start: date,
    end: date,
    journals: Sequence[JournalSpec],
) -> Iterator[ArticleRecord]:
    """Crossref fallback with per-journal/per-ISSN fault isolation."""
    session = build_session()
    seen: set[str] = set()
    attempts = 0
    successful_requests = 0

    for spec in journals:
        if not spec.issns:
            continue

        preferred = list(reversed(spec.issns))  # online/eISSN first
        spec_records: list[ArticleRecord] = []
        for issn in preferred:
            attempts += 1
            try:
                spec_records = _records_for_issn(session, provider, publisher, spec, issn, start, end)
                successful_requests += 1
            except requests.RequestException as exc:
                print(
                    f"[{provider}] Crossref warning: {spec.journal} "
                    f"({display_issn(issn)}) failed ({_status_label(exc)}); trying alternate/next journal"
                )
                continue
            if spec_records:
                break

        for record in spec_records:
            key = record.doi or record.external_id or record.title.lower()
            if not key or key in seen:
                continue
            seen.add(key)
            yield record

    # Do not let a single 404/timeout kill a whole publisher, but also do not
    # silently report success if Crossref itself failed for every attempted ISSN.
    if attempts and successful_requests == 0:
        raise RuntimeError(f"Crossref fallback failed for all {attempts} attempted ISSN queries")

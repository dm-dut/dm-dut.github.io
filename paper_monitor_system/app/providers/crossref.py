from __future__ import annotations

from datetime import date, timedelta
from typing import Iterator, Sequence

import requests

from ..config import CROSSREF_DISCOVERY_DAYS, CROSSREF_MAILTO, EXPORT_DAYS
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


def _request_items(session, issn: str, filters: list[str], *, rows: int = 500) -> list[dict]:
    """Query Crossref's global /works endpoint using an ISSN filter and cursor paging."""
    normalized = normalize_issn(issn)
    if len(normalized) != 8:
        return []
    url = f"{BASE_URL}/works"
    params = {
        "filter": ",".join([f"issn:{display_issn(normalized)}", *filters]),
        "rows": rows,
        "cursor": "*",
    }
    if CROSSREF_MAILTO:
        params["mailto"] = CROSSREF_MAILTO

    items: list[dict] = []
    cursor = "*"
    for _ in range(40):
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
    *,
    allow_pending: bool,
    max_online_date: date | None = None,
    min_online_date: date | None = None,
    source_label: str = "Crossref published-online fallback",
) -> ArticleRecord | None:
    title = _first_text(item.get("title"))
    if not title:
        return None
    doi = clean_doi(item.get("DOI"))
    if not doi and allow_pending:
        # Pending records need a stable key for future rechecks.
        return None

    online_date, precision, raw_date = _date_parts(item)
    if online_date is not None:
        if max_online_date and online_date > max_online_date:
            # Do not show future publication dates. Keep as pending so it can be checked again.
            online_date = None
            precision = "unknown"
            raw_date = ""
        elif min_online_date and online_date < min_online_date:
            return None
    elif not allow_pending:
        return None

    url = normalize_space(str(item.get("URL") or ""))
    if not url and doi:
        url = f"https://doi.org/{doi}"
    alt = item.get("alternative-id") or []
    external_id = normalize_space(str(alt[0])) if isinstance(alt, list) and alt else doi
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
        online_date_source=source_label if online_date else "Crossref index-date discovery; awaiting published-online",
        source_update_date=online_date,
        status="published" if online_date else "pending",
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
    return [
        record for item in items
        if (record := _to_record(
            provider, publisher, spec, item,
            allow_pending=False, min_online_date=start, max_online_date=end,
            source_label="Crossref published-online fallback",
        ))
    ]


def fetch(
    provider: str,
    publisher: str,
    start: date,
    end: date,
    journals: Sequence[JournalSpec],
) -> Iterator[ArticleRecord]:
    """Conservative online-date fallback for Springer/IEEE and optional use elsewhere."""
    session = build_session()
    seen: set[str] = set()
    attempts = successful_requests = 0

    for spec in journals:
        if not spec.issns:
            continue
        spec_records: list[ArticleRecord] = []
        for issn in reversed(spec.issns):
            attempts += 1
            try:
                spec_records = _records_for_issn(session, provider, publisher, spec, issn, start, end)
                successful_requests += 1
            except requests.RequestException as exc:
                print(f"[{provider}] Crossref warning: {spec.journal} ({display_issn(issn)}) failed ({_status_label(exc)})")
                continue
            if spec_records:
                break
        for record in spec_records:
            key = record.doi or record.external_id or record.title.lower()
            if key and key not in seen:
                seen.add(key)
                yield record

    if attempts and successful_requests == 0:
        raise RuntimeError(f"Crossref fallback failed for all {attempts} attempted ISSN queries")


def incremental_discover(
    provider: str,
    publisher: str,
    end: date,
    journals: Sequence[JournalSpec],
    *,
    discovery_days: int | None = None,
) -> Iterator[ArticleRecord]:
    """Discover new/changed journal metadata by Crossref index date.

    Items with a real `published-online` are immediately publishable. Items without
    it are retained as `pending` so later Crossref redeposits/reindexing can promote
    them without permanently losing the DOI.
    """
    days = CROSSREF_DISCOVERY_DAYS if discovery_days is None else discovery_days
    indexed_start = end - timedelta(days=max(days, 1))
    oldest_online = end - timedelta(days=max(EXPORT_DAYS, days))
    filters = [
        "type:journal-article",
        f"from-index-date:{indexed_start.isoformat()}",
        f"until-index-date:{(end + timedelta(days=1)).isoformat()}",
    ]
    session = build_session()
    seen: set[str] = set()
    journal_hits = pending_count = published_count = 0
    attempts = successful_requests = 0

    for spec in journals:
        if not spec.issns:
            continue
        spec_seen: set[str] = set()
        got_response = False
        # Prefer eISSN. If it returns zero, try print ISSN too; Crossref deposits vary.
        for issn in reversed(spec.issns):
            attempts += 1
            try:
                items = _request_items(session, issn, filters)
                got_response = True
                successful_requests += 1
            except requests.RequestException as exc:
                print(f"[{provider}] Crossref incremental warning: {spec.journal} ({display_issn(issn)}): {_status_label(exc)}")
                continue
            for item in items:
                record = _to_record(
                    provider, publisher, spec, item,
                    allow_pending=True,
                    min_online_date=oldest_online,
                    max_online_date=end,
                    source_label="Crossref index-date discovery + published-online",
                )
                if record is None:
                    continue
                key = record.doi or record.external_id or record.title.lower()
                if not key or key in spec_seen or key in seen:
                    continue
                spec_seen.add(key)
                seen.add(key)
                if record.online_date:
                    published_count += 1
                else:
                    pending_count += 1
                yield record
            if spec_seen:
                break
        if got_response and spec_seen:
            journal_hits += 1

    print(
        f"[{provider}] Crossref incremental: journals_with_records={journal_hits}, "
        f"published={published_count}, pending={pending_count}, unique={len(seen)}"
    )
    if attempts and successful_requests == 0:
        raise RuntimeError(f"Crossref incremental failed for all {attempts} attempted ISSN queries")


def by_doi(
    provider: str,
    publisher: str,
    spec: JournalSpec,
    doi: str,
    *,
    today: date | None = None,
) -> ArticleRecord | None:
    """Recheck one pending DOI and return its latest Crossref metadata."""
    doi = clean_doi(doi)
    if not doi:
        return None
    session = build_session()
    params = {"mailto": CROSSREF_MAILTO} if CROSSREF_MAILTO else None
    data = get_json(session, f"{BASE_URL}/works/{doi}", params=params)
    item = data.get("message") or {}
    return _to_record(
        provider, publisher, spec, item,
        allow_pending=True,
        min_online_date=None,
        max_online_date=today or date.today(),
        source_label="Crossref pending recheck + published-online",
    )

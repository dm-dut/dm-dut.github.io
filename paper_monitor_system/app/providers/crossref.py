from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from time import perf_counter
from typing import Iterator, Sequence

import requests

from ..config import (
    CROSSREF_BATCH_MAX_PAGES,
    CROSSREF_BATCH_ROWS,
    CROSSREF_DISCOVERY_DAYS,
    CROSSREF_MAILTO,
    ELSEVIER_CROSSREF_MEMBER_ID,
    EXPORT_DAYS,
)
from ..journals import JournalSpec, display_issn, match_journal, normalize_issn
from ..utils import build_session, clean_doi, get_json, normalize_space
from .base import ArticleRecord

BASE_URL = "https://api.crossref.org"
SELECT_FIELDS = "DOI,title,author,container-title,ISSN,published-online,URL"


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


def _container_title(item: dict) -> str:
    return _first_text(item.get("container-title"))


def _item_issns(item: dict) -> str:
    return "; ".join(str(value) for value in (item.get("ISSN") or []) if value)


def _status_label(exc: Exception) -> str:
    status = getattr(getattr(exc, "response", None), "status_code", None)
    return f"HTTP {status}" if status else type(exc).__name__


def _request_items(session, issn: str, filters: list[str], *, rows: int = 500) -> list[dict]:
    """Fallback ISSN query through the global /works endpoint."""
    normalized = normalize_issn(issn)
    if len(normalized) != 8:
        return []
    url = f"{BASE_URL}/works"
    params = {
        "filter": ",".join([f"issn:{display_issn(normalized)}", *filters]),
        "rows": rows,
        "cursor": "*",
        "select": SELECT_FIELDS,
    }
    if CROSSREF_MAILTO:
        params["mailto"] = CROSSREF_MAILTO

    items: list[dict] = []
    cursor = "*"
    for _ in range(20):
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
    pending_source_label: str = "Crossref discovery; awaiting published-online",
) -> ArticleRecord | None:
    title = _first_text(item.get("title"))
    if not title:
        return None
    doi = clean_doi(item.get("DOI"))
    if not doi and allow_pending:
        return None

    online_date, precision, raw_date = _date_parts(item)
    if online_date is not None:
        if max_online_date and online_date > max_online_date:
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
    issns = _item_issns(item)

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
        online_date_source=source_label if online_date else pending_source_label,
        source_update_date=online_date,
        status="published" if online_date else "pending",
    )


def _records_for_issn(session, provider: str, publisher: str, spec: JournalSpec, issn: str, start: date, end: date) -> list[ArticleRecord]:
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


def fetch(provider: str, publisher: str, start: date, end: date, journals: Sequence[JournalSpec]) -> Iterator[ArticleRecord]:
    """Conservative per-ISSN online-date fallback used only when a primary source fails."""
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


def _bounded_discovery_start(start: date, end: date, days: int | None = None) -> date:
    configured = max(1, CROSSREF_DISCOVERY_DAYS if days is None else days)
    cap = end - timedelta(days=configured - 1)
    return max(start, cap)


def _member_groups(journals: Sequence[JournalSpec], default_member_id: int) -> dict[tuple[int, str], list[JournalSpec]]:
    groups: dict[tuple[int, str], list[JournalSpec]] = defaultdict(list)
    for spec in journals:
        member = spec.crossref_member or default_member_id
        prefix = normalize_space(spec.crossref_prefix)
        groups[(member, prefix)].append(spec)
    return groups


def member_batch_discover(
    provider: str,
    publisher: str,
    start: date,
    end: date,
    journals: Sequence[JournalSpec],
    *,
    default_member_id: int = ELSEVIER_CROSSREF_MEMBER_ID,
) -> Iterator[ArticleRecord]:
    """Publisher/member-level Crossref discovery, then local whitelist filtering.

    This replaces 39–78 per-ISSN requests with one small set of cursor-paged
    publisher-level requests. `from-created-date` is intentionally used for the
    daily new-record monitor; pending DOI rechecks handle later online-date deposits.
    """
    actual_start = _bounded_discovery_start(start, end)
    groups = _member_groups(journals, default_member_id)
    session = build_session()
    global_seen: set[str] = set()
    total_pages = total_raw = total_matched = total_published = total_pending = 0
    t0 = perf_counter()

    for group_no, ((member_id, prefix), specs) in enumerate(groups.items(), start=1):
        filters = [
            "type:journal-article",
            f"from-created-date:{actual_start.isoformat()}",
            f"until-created-date:{end.isoformat()}",
        ]
        if prefix:
            filters.append(f"prefix:{prefix}")
        url = f"{BASE_URL}/members/{member_id}/works"
        params = {
            "filter": ",".join(filters),
            "rows": max(20, min(CROSSREF_BATCH_ROWS, 1000)),
            "cursor": "*",
            "select": SELECT_FIELDS,
        }
        if CROSSREF_MAILTO:
            params["mailto"] = CROSSREF_MAILTO

        print(
            f"[{provider}] Crossref batch group {group_no}/{len(groups)}: member={member_id}"
            + (f", prefix={prefix}" if prefix else "")
            + f", journals={len(specs)}, created={actual_start}..{end}"
        )
        cursor = "*"
        group_success = False
        for page_no in range(1, max(1, CROSSREF_BATCH_MAX_PAGES) + 1):
            params["cursor"] = cursor
            data = get_json(session, url, params=params)
            group_success = True
            total_pages += 1
            message = data.get("message") or {}
            batch = [item for item in (message.get("items") or []) if isinstance(item, dict)]
            total_raw += len(batch)
            if page_no == 1 or page_no % 5 == 0:
                print(f"[{provider}] Crossref batch progress: page={page_no}, raw_items_so_far={total_raw}")

            for item in batch:
                spec = match_journal(provider, _container_title(item), _item_issns(item), specs)
                if spec is None:
                    continue
                record = _to_record(
                    provider, publisher, spec, item,
                    allow_pending=True,
                    min_online_date=actual_start,
                    max_online_date=end,
                    source_label="Crossref Elsevier member batch + published-online",
                    pending_source_label="Crossref Elsevier member batch discovery; awaiting published-online",
                )
                if record is None:
                    continue
                key = record.doi or record.external_id or record.title.lower()
                if not key or key in global_seen:
                    continue
                global_seen.add(key)
                total_matched += 1
                if record.online_date:
                    total_published += 1
                else:
                    total_pending += 1
                yield record

            next_cursor = message.get("next-cursor")
            if not batch or not next_cursor or next_cursor == cursor or len(batch) < int(params["rows"]):
                break
            cursor = next_cursor
        else:
            raise RuntimeError(f"Crossref member batch exceeded {CROSSREF_BATCH_MAX_PAGES} pages for member {member_id}")
        if not group_success:
            raise RuntimeError(f"Crossref member batch returned no response for member {member_id}")

    elapsed = perf_counter() - t0
    print(
        f"[{provider}] Crossref member batch done: groups={len(groups)}, pages={total_pages}, raw={total_raw}, "
        f"whitelist={total_matched}, published={total_published}, pending={total_pending}, elapsed={elapsed:.1f}s"
    )



def prefix_batch_discover(
    provider: str,
    publisher: str,
    start: date,
    end: date,
    journals: Sequence[JournalSpec],
    *,
    prefix: str,
) -> Iterator[ArticleRecord]:
    """Crossref prefix-level batch discovery followed by local whitelist filtering.

    Used by Springer V3.1 as a fast single-route fallback when the Meta API is
    unavailable or its Basic-plan pagination cap is reached. It intentionally
    avoids 25 per-journal ISSN requests.
    """
    actual_start = _bounded_discovery_start(start, end)
    session = build_session()
    global_seen: set[str] = set()
    total_pages = total_raw = total_matched = total_published = total_pending = 0
    t0 = perf_counter()

    url = f"{BASE_URL}/prefixes/{prefix}/works"
    params = {
        "filter": ",".join([
            "type:journal-article",
            f"from-created-date:{actual_start.isoformat()}",
            f"until-created-date:{end.isoformat()}",
        ]),
        "rows": max(20, min(CROSSREF_BATCH_ROWS, 1000)),
        "cursor": "*",
        "select": SELECT_FIELDS,
    }
    if CROSSREF_MAILTO:
        params["mailto"] = CROSSREF_MAILTO

    print(
        f"[{provider}] Crossref prefix batch: prefix={prefix}, journals={len(journals)}, "
        f"created={actual_start}..{end}"
    )
    cursor = "*"
    for page_no in range(1, max(1, CROSSREF_BATCH_MAX_PAGES) + 1):
        params["cursor"] = cursor
        data = get_json(session, url, params=params)
        total_pages += 1
        message = data.get("message") or {}
        batch = [item for item in (message.get("items") or []) if isinstance(item, dict)]
        total_raw += len(batch)
        if page_no == 1 or page_no % 5 == 0:
            print(f"[{provider}] Crossref prefix progress: page={page_no}, raw_items_so_far={total_raw}")

        for item in batch:
            spec = match_journal(provider, _container_title(item), _item_issns(item), journals)
            if spec is None:
                continue
            record = _to_record(
                provider, publisher, spec, item,
                allow_pending=True,
                min_online_date=actual_start,
                max_online_date=end,
                source_label=f"Crossref {publisher} prefix batch + published-online",
                pending_source_label=f"Crossref {publisher} prefix batch discovery; awaiting published-online",
            )
            if record is None:
                continue
            key = record.doi or record.external_id or record.title.lower()
            if not key or key in global_seen:
                continue
            global_seen.add(key)
            total_matched += 1
            if record.online_date:
                total_published += 1
            else:
                total_pending += 1
            yield record

        next_cursor = message.get("next-cursor")
        if not batch or not next_cursor or next_cursor == cursor or len(batch) < int(params["rows"]):
            break
        cursor = next_cursor
    else:
        raise RuntimeError(f"Crossref prefix batch exceeded {CROSSREF_BATCH_MAX_PAGES} pages for prefix {prefix}")

    print(
        f"[{provider}] Crossref prefix batch done: pages={total_pages}, raw={total_raw}, "
        f"whitelist={total_matched}, published={total_published}, pending={total_pending}, "
        f"elapsed={perf_counter()-t0:.1f}s"
    )

def incremental_discover(provider: str, publisher: str, end: date, journals: Sequence[JournalSpec], *, discovery_days: int | None = None) -> Iterator[ArticleRecord]:
    """Slow per-ISSN emergency fallback retained for resilience only."""
    days = CROSSREF_DISCOVERY_DAYS if discovery_days is None else discovery_days
    indexed_start = end - timedelta(days=max(days, 1) - 1)
    oldest_online = end - timedelta(days=max(EXPORT_DAYS, days))
    filters = [
        "type:journal-article",
        f"from-created-date:{indexed_start.isoformat()}",
        f"until-created-date:{end.isoformat()}",
    ]
    session = build_session()
    seen: set[str] = set()
    attempts = successful_requests = 0
    for idx, spec in enumerate(journals, start=1):
        if not spec.issns:
            continue
        print(f"[{provider}] Crossref emergency ISSN fallback {idx}/{len(journals)}: {spec.journal}")
        spec_seen: set[str] = set()
        for issn in reversed(spec.issns):
            attempts += 1
            try:
                items = _request_items(session, issn, filters)
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
                    source_label="Crossref created-date fallback + published-online",
                    pending_source_label="Crossref created-date fallback discovery; awaiting published-online",
                )
                if record is None:
                    continue
                key = record.doi or record.external_id or record.title.lower()
                if not key or key in spec_seen or key in seen:
                    continue
                spec_seen.add(key)
                seen.add(key)
                yield record
            if spec_seen:
                break
    if attempts and successful_requests == 0:
        raise RuntimeError(f"Crossref incremental failed for all {attempts} attempted ISSN queries")


def by_doi(provider: str, publisher: str, spec: JournalSpec, doi: str, *, today: date | None = None) -> ArticleRecord | None:
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
        pending_source_label="Crossref pending recheck; awaiting published-online",
    )

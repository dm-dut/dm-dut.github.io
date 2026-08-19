from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from time import perf_counter
from difflib import SequenceMatcher
import re
from typing import Iterator, Sequence

import requests

from ..config import (
    CROSSREF_BATCH_MAX_PAGES,
    CROSSREF_BATCH_ROWS,
    CROSSREF_DISCOVERY_DAYS,
    CROSSREF_MAILTO,
    ELSEVIER_CROSSREF_MEMBER_ID,
    EXPORT_DAYS,
    ENABLE_ELSEVIER_GENERIC_PUBDATE_FALLBACK,
    IEEE_TITLE_MATCH_ROWS,
    IEEE_TITLE_MATCH_THRESHOLD,
)
from ..journals import JournalSpec, display_issn, match_journal, normalize_issn
from ..utils import build_session, clean_doi, get_json, normalize_space
from .base import ArticleRecord

BASE_URL = "https://api.crossref.org"
SELECT_FIELDS = "DOI,title,author,container-title,ISSN,published-online,published,issued,created,URL"


def _date_parts(item: dict) -> tuple[date | None, str, str]:
    return _date_from_block(item.get("published-online") or {})


def _date_from_block(block) -> tuple[date | None, str, str]:
    if not isinstance(block, dict):
        return None, "unknown", ""
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


def _generic_publication_date(item: dict) -> tuple[date | None, str, str]:
    # Crossref's generic `published` field is lower-confidence than
    # `published-online`, but is useful for publishers that do not deposit an
    # explicit online date. `issued` is the final fallback.
    for key in ("published", "issued"):
        value = _date_from_block(item.get(key) or {})
        if value[0] is not None:
            return value
    return None, "unknown", ""


def _created_date(item: dict) -> date | None:
    block = item.get("created") or {}
    raw = str(block.get("date-time") or "").strip() if isinstance(block, dict) else ""
    if raw:
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
        except Exception:
            pass
    return _date_from_block(block)[0]


def _normalize_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", normalize_space(value).lower()).strip()


def title_similarity(a: str, b: str) -> float:
    aa, bb = _normalize_title(a), _normalize_title(b)
    if not aa or not bb:
        return 0.0
    seq = SequenceMatcher(None, aa, bb).ratio()
    sa, sb = set(aa.split()), set(bb.split())
    jac = len(sa & sb) / max(1, len(sa | sb))
    return max(seq, 0.45 * seq + 0.55 * jac)


def metadata_from_item(item: dict) -> dict:
    online, precision, raw = _date_parts(item)
    pub_date, pub_precision, pub_raw = _generic_publication_date(item)
    return {
        "doi": clean_doi(item.get("DOI")),
        "title": _first_text(item.get("title")),
        "authors": _authors(item),
        "journal": _container_title(item),
        "issn": _item_issns(item),
        "online_date": online,
        "online_raw": raw,
        "precision": precision,
        "published_date": pub_date,
        "published_raw": pub_raw,
        "published_precision": pub_precision,
        "created_date": _created_date(item),
        "url": normalize_space(str(item.get("URL") or "")),
    }


def search_title_match(title: str, provider: str, specs: Sequence[JournalSpec], *, rows: int | None = None) -> tuple[dict, JournalSpec, float] | None:
    """Find a Crossref candidate by article title, but only accept results
    whose journal/ISSN maps to the configured whitelist.
    """
    title = normalize_space(title)
    if not title:
        return None
    session = build_session()
    params = {
        "query.title": title,
        "filter": "type:journal-article",
        "rows": max(1, min(rows or IEEE_TITLE_MATCH_ROWS, 10)),
        "select": SELECT_FIELDS,
    }
    if CROSSREF_MAILTO:
        params["mailto"] = CROSSREF_MAILTO
    data = get_json(session, f"{BASE_URL}/works", params=params)
    best = None
    best_score = 0.0
    for item in (data.get("message") or {}).get("items") or []:
        if not isinstance(item, dict):
            continue
        spec = match_journal(provider, _container_title(item), _item_issns(item), specs)
        if spec is None:
            continue
        score = title_similarity(title, _first_text(item.get("title")))
        if score > best_score:
            best = (item, spec, score)
            best_score = score
    if best and best_score >= IEEE_TITLE_MATCH_THRESHOLD:
        return best
    return None


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
    allow_generic_pubdate: bool = False,
    generic_source_label: str = "Crossref published-date fallback",
) -> ArticleRecord | None:
    title = _first_text(item.get("title"))
    if not title:
        return None
    doi = clean_doi(item.get("DOI"))
    if not doi and allow_pending:
        return None

    online_date, precision, raw_date = _date_parts(item)
    used_generic = False
    if online_date is None and allow_generic_pubdate:
        generic_date, generic_precision, generic_raw = _generic_publication_date(item)
        if generic_date is not None:
            online_date, precision, raw_date = generic_date, generic_precision, generic_raw
            used_generic = True

    if online_date is not None:
        if max_online_date and online_date > max_online_date:
            online_date = None
            precision = "unknown"
            raw_date = ""
            used_generic = False
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
        online_date_source=(generic_source_label if (online_date and used_generic) else (source_label if online_date else pending_source_label)),
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


def _member_groups(journals: Sequence[JournalSpec], default_member_id: int) -> dict[int, list[JournalSpec]]:
    """Group journals by Crossref member only.

    LOCAL V3.3 intentionally does not hard-filter Elsevier by DOI prefix.  The
    publisher/member route is broad enough for discovery; ISSN/title whitelist
    matching is the authoritative local filter.
    """
    groups: dict[int, list[JournalSpec]] = defaultdict(list)
    for spec in journals:
        member = spec.crossref_member or default_member_id
        groups[member].append(spec)
    return groups


def _member_batch_pass(
    session,
    provider: str,
    publisher: str,
    member_id: int,
    specs: Sequence[JournalSpec],
    start: date,
    end: date,
    *,
    pass_name: str,
    from_filter: str,
    until_filter: str,
    allow_pending: bool,
    global_seen: set[str],
    allow_generic_pubdate: bool = False,
) -> tuple[list[ArticleRecord], int, int]:
    """Run one cursor-paged Crossref member pass and locally whitelist results."""
    filters = [
        "type:journal-article",
        f"{from_filter}:{start.isoformat()}",
        f"{until_filter}:{end.isoformat()}",
    ]
    url = f"{BASE_URL}/members/{member_id}/works"
    params = {
        "filter": ",".join(filters),
        "rows": max(20, min(CROSSREF_BATCH_ROWS, 1000)),
        "cursor": "*",
        "select": SELECT_FIELDS,
    }
    if CROSSREF_MAILTO:
        params["mailto"] = CROSSREF_MAILTO

    records: list[ArticleRecord] = []
    raw_total = pages = 0
    cursor = "*"
    print(
        f"[{provider}] Crossref {pass_name} batch: member={member_id}, journals={len(specs)}, "
        f"window={start}..{end}, rows={params['rows']}"
    )
    for page_no in range(1, max(1, CROSSREF_BATCH_MAX_PAGES) + 1):
        params["cursor"] = cursor
        data = get_json(session, url, params=params)
        pages += 1
        message = data.get("message") or {}
        batch = [item for item in (message.get("items") or []) if isinstance(item, dict)]
        raw_total += len(batch)
        if page_no == 1 or page_no % 5 == 0:
            print(
                f"[{provider}] Crossref {pass_name} progress: page={page_no}, "
                f"raw={raw_total}, accepted={len(records)}"
            )

        for item in batch:
            spec = match_journal(provider, _container_title(item), _item_issns(item), specs)
            if spec is None:
                continue
            record = _to_record(
                provider, publisher, spec, item,
                allow_pending=allow_pending,
                min_online_date=start,
                max_online_date=end,
                source_label=f"Crossref {publisher} {pass_name} batch + published-online",
                pending_source_label=f"Crossref {publisher} {pass_name} batch discovery; awaiting published-online",
                allow_generic_pubdate=allow_generic_pubdate,
                generic_source_label=f"Crossref {publisher} published-date fallback",
            )
            if record is None:
                continue
            key = record.doi or record.external_id or record.title.lower()
            if not key or key in global_seen:
                continue
            global_seen.add(key)
            records.append(record)

        next_cursor = message.get("next-cursor")
        if not batch or not next_cursor or next_cursor == cursor or len(batch) < int(params["rows"]):
            break
        cursor = next_cursor
    else:
        raise RuntimeError(
            f"Crossref {pass_name} batch exceeded {CROSSREF_BATCH_MAX_PAGES} pages for member {member_id}"
        )

    print(
        f"[{provider}] Crossref {pass_name} done: pages={pages}, raw={raw_total}, "
        f"accepted={len(records)}"
    )
    return records, pages, raw_total


def member_dual_batch_discover(
    provider: str,
    publisher: str,
    start: date,
    end: date,
    journals: Sequence[JournalSpec],
    *,
    default_member_id: int = ELSEVIER_CROSSREF_MEMBER_ID,
) -> Iterator[ArticleRecord]:
    """Fast publisher-level discovery using two complementary two-day passes.

    Pass A filters directly on Crossref ``published-online``. Pass B uses the
    generic Crossref publication date as a clearly-labelled fallback for
    publishers that do not deposit ``published-online``. Both passes are only
    two calendar dates and are locally filtered to the journal whitelist.
    """
    actual_start = _bounded_discovery_start(start, end)
    groups = _member_groups(journals, default_member_id)
    session = build_session()
    global_seen: set[str] = set()
    total_pages = total_raw = 0
    online_count = publication_count = 0
    t0 = perf_counter()

    for group_no, (member_id, specs) in enumerate(groups.items(), start=1):
        print(f"[{provider}] Crossref member group {group_no}/{len(groups)}: member={member_id}, journals={len(specs)}")

        online_records, pages, raw = _member_batch_pass(
            session, provider, publisher, member_id, specs, actual_start, end,
            pass_name="online-date",
            from_filter="from-online-pub-date",
            until_filter="until-online-pub-date",
            allow_pending=False,
            global_seen=global_seen,
        )
        total_pages += pages
        total_raw += raw
        online_count += len(online_records)
        for record in online_records:
            yield record

        publication_records, pages, raw = _member_batch_pass(
            session, provider, publisher, member_id, specs, actual_start, end,
            pass_name="publication-date",
            from_filter="from-pub-date",
            until_filter="until-pub-date",
            allow_pending=False,
            global_seen=global_seen,
            allow_generic_pubdate=ENABLE_ELSEVIER_GENERIC_PUBDATE_FALLBACK,
        )
        total_pages += pages
        total_raw += raw
        publication_count += len(publication_records)
        for record in publication_records:
            yield record

    print(
        f"[{provider}] Crossref dual batch done: groups={len(groups)}, pages={total_pages}, raw={total_raw}, "
        f"online_pass={online_count}, publication_fallback_new={publication_count}, pending=0, "
        f"unique={len(global_seen)}, elapsed={perf_counter()-t0:.1f}s"
    )


def member_batch_discover(
    provider: str,
    publisher: str,
    start: date,
    end: date,
    journals: Sequence[JournalSpec],
    *,
    default_member_id: int = ELSEVIER_CROSSREF_MEMBER_ID,
) -> Iterator[ArticleRecord]:
    """Backward-compatible alias for the V3.3 dual member batch."""
    yield from member_dual_batch_discover(
        provider, publisher, start, end, journals, default_member_id=default_member_id
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

    Used by Springer V3.3 as a fast single-route fallback when the Meta API is
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

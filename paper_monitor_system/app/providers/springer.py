from __future__ import annotations

from datetime import date, timedelta
from time import perf_counter
from typing import Iterator, Sequence

from ..config import SPRINGER_API_KEY, SPRINGER_BATCH_MAX_PAGES_PER_DAY, SPRINGER_BATCH_PAGE_SIZE
from ..journals import JournalSpec, match_journal
from ..utils import build_session, clean_doi, first_nonempty, get_json, join_authors, normalize_space, parse_publisher_day
from .base import ArticleRecord

BASE_URL = "https://api.springernature.com/meta/v2/json"


def _day_query(day: date) -> str:
    return f"onlinedatefrom:{day.isoformat()} onlinedateto:{day.isoformat()}"


def _record_from_row(spec: JournalSpec, row: dict, day: date, source_rank: int = 9999) -> ArticleRecord | None:
    if normalize_space(row.get("publicationType")).lower() not in {"", "journal"}:
        return None
    online_date = parse_publisher_day(normalize_space(row.get("onlineDate")))
    if online_date != day:
        return None
    title = normalize_space(row.get("title"))
    if not title:
        return None
    doi = clean_doi(first_nonempty(row.get("doi"), row.get("identifier")))
    external_id = normalize_space(row.get("identifier")) or doi or f"{spec.journal}:{title}:{day.isoformat()}"
    urls = row.get("url") or []
    if isinstance(urls, dict):
        urls = [urls]
    url = ""
    for item in urls:
        if isinstance(item, dict) and item.get("value"):
            url = normalize_space(item["value"])
            if url:
                break
    return ArticleRecord(
        provider="springer", publisher="Springer Nature", title=title, journal=spec.journal,
        authors=join_authors(row.get("creators") or []), external_id=external_id, url=url,
        display_date=online_date.isoformat(), sort_date=online_date,
        date_kind="online", date_precision="day", date_source="Springer Meta API onlineDate",
        source_rank=source_rank, doi=doi, issn=normalize_space(row.get("issn") or ""),
    )


def fetch(start: date, end: date, journals: Sequence[JournalSpec], known_ids: set[str] | None = None) -> Iterator[ArticleRecord]:
    if not SPRINGER_API_KEY:
        raise RuntimeError("SPRINGER_API_KEY missing in paper_monitor_system/.env")
    known = set(known_ids or set())
    session = build_session(); t0 = perf_counter(); accepted_total = 0; seen: set[str] = set()
    day = start
    while day <= end:
        query = _day_query(day)
        page_size = max(1, min(int(SPRINGER_BATCH_PAGE_SIZE), 20))
        max_pages = max(1, int(SPRINGER_BATCH_MAX_PAGES_PER_DAY))
        start_index = 1; raw_total = accepted_day = 0
        print(f"[springer] onlineDate day={day}")
        for page_no in range(1, max_pages + 1):
            data = get_json(session, BASE_URL, params={
                "api_key": SPRINGER_API_KEY, "q": query, "s": start_index, "p": page_size,
            })
            rows = data.get("records") or []; raw_total += len(rows)
            for row_index, row in enumerate(rows, start=1):
                spec = match_journal(
                    "springer", normalize_space(row.get("publicationName") or row.get("publicationTitle") or ""),
                    normalize_space(row.get("issn") or ""), journals,
                )
                if spec is None:
                    continue
                rec = _record_from_row(spec, row, day, source_rank=(page_no - 1) * page_size + row_index)
                if rec is None or rec.external_id in seen or rec.external_id in known:
                    continue
                seen.add(rec.external_id); known.add(rec.external_id)
                accepted_day += 1; accepted_total += 1
                yield rec
            print(f"[springer] page={page_no}, raw={raw_total}, whitelist_new={accepted_day}")
            if len(rows) < page_size:
                break
            start_index += page_size
        else:
            print(f"[springer] WARNING: day {day} reached configured page cap")
        day += timedelta(days=1)
    print(f"[springer] done: new records={accepted_total}, elapsed={perf_counter()-t0:.1f}s")

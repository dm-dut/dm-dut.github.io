from __future__ import annotations

from datetime import date
from typing import Iterator, Sequence

from ..config import SPRINGER_API_KEY
from ..journals import JournalSpec, display_issn, match_journal
from ..utils import build_session, clean_doi, first_nonempty, get_json, join_authors, normalize_space, parse_flexible_date
from .base import ArticleRecord

BASE_URL = "https://api.springernature.com/meta/v2/json"


def _url(record: dict) -> str:
    urls = record.get("url") or []
    if isinstance(urls, dict):
        urls = [urls]
    for item in urls:
        if not isinstance(item, dict):
            continue
        value = item.get("value") or item.get("url") or item.get("$", "")
        if "link.springer.com" in str(value):
            return str(value)
    for item in urls:
        if isinstance(item, dict):
            value = item.get("value") or item.get("url") or item.get("$", "")
            if value:
                return str(value)
        elif isinstance(item, str):
            return item
    return ""


def _queries(spec: JournalSpec, start: date, end: date) -> list[str]:
    date_clause = f"onlinedatefrom:{start.isoformat()} onlinedateto:{end.isoformat()}"
    if spec.issns:
        return [f"{date_clause} issn:{display_issn(i)}" for i in spec.issns]
    # Publication-title fallback; ISSN is preferred because title constraints can
    # differ by API plan and title punctuation/renaming is less stable.
    safe = spec.journal.replace('"', '\\"')
    return [f'{date_clause} pub:"{safe}"']


def fetch(start: date, end: date, journals: Sequence[JournalSpec]) -> Iterator[ArticleRecord]:
    if not SPRINGER_API_KEY:
        raise RuntimeError("SPRINGER_API_KEY is missing")
    if not journals:
        return

    session = build_session()
    page_size = 100
    seen: set[str] = set()

    for spec in journals:
        for query in _queries(spec, start, end):
            s = 1
            while True:
                params = {"api_key": SPRINGER_API_KEY, "q": query, "s": s, "p": page_size}
                data = get_json(session, BASE_URL, params=params)
                records = data.get("records") or []
                if not records:
                    break

                for r in records:
                    content_type = normalize_space(r.get("contentType"))
                    if content_type and content_type.lower() != "article":
                        continue
                    title = normalize_space(r.get("title"))
                    if not title:
                        continue

                    raw_date = normalize_space(first_nonempty(r.get("onlineDate"), r.get("coverDate")))
                    online_date, precision = parse_flexible_date(raw_date)
                    creators = r.get("creators") or []
                    doi = clean_doi(first_nonempty(r.get("doi"), r.get("identifier")))
                    identifier = normalize_space(r.get("identifier"))
                    journal = normalize_space(first_nonempty(r.get("publicationName"), r.get("journalTitle")))
                    issn = normalize_space(first_nonempty(r.get("issn"), r.get("eIssn")))

                    matched = match_journal("springer", journal, issn, journals)
                    if matched is None and journal and journal.lower() != spec.journal.lower():
                        continue

                    identity = doi or identifier or title.lower()
                    if identity in seen:
                        continue
                    seen.add(identity)

                    yield ArticleRecord(
                        provider="springer",
                        publisher="Springer Nature",
                        title=title,
                        journal=journal or spec.journal,
                        authors=join_authors(creators),
                        doi=doi,
                        external_id=identifier or doi,
                        issn=issn or (display_issn(spec.issns[0]) if spec.issns else ""),
                        content_type=content_type or "Article",
                        url=_url(r),
                        online_date=online_date,
                        online_date_raw=raw_date,
                        date_precision=precision,
                        online_date_source="Springer onlineDate" if r.get("onlineDate") else "Springer coverDate fallback",
                        source_update_date=online_date or end,
                    )

                total = 0
                result = data.get("result") or []
                if result and isinstance(result, list):
                    try:
                        total = int(result[0].get("total", 0))
                    except Exception:
                        total = 0
                s += len(records)
                if len(records) < page_size or (total and s > total):
                    break

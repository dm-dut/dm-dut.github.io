from __future__ import annotations

from datetime import date
from typing import Iterator, Sequence

import requests

from ..config import SPRINGER_API_KEY, ENABLE_CROSSREF_FALLBACK
from ..journals import JournalSpec, display_issn, match_journal
from ..utils import build_session, clean_doi, first_nonempty, get_json, join_authors, normalize_space, parse_flexible_date
from . import crossref
from .base import ArticleRecord

BASE_URL = "https://api.springernature.com/meta/v2/json"


def _url(record: dict) -> str:
    urls = record.get("url") or []
    if isinstance(urls, dict):
        urls = [urls]
    for item in urls:
        if isinstance(item, dict):
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
    # These constraints are supported by Meta/v2 Basic Plan. type:Journal also
    # prevents book chapters/conference chapters from entering the database.
    date_clause = f"type:Journal onlinedatefrom:{start.isoformat()} onlinedateto:{end.isoformat()}"
    if spec.issns:
        return [f"{date_clause} issn:{display_issn(i)}" for i in spec.issns]
    safe = spec.journal.replace('"', '\\"')
    return [f'{date_clause} journal:"{safe}"']


def _fetch_primary(start: date, end: date, journals: Sequence[JournalSpec]) -> Iterator[ArticleRecord]:
    if not SPRINGER_API_KEY:
        raise RuntimeError("SPRINGER_API_KEY is missing")

    session = build_session()
    # 25 is conservative and well within the current Meta API pagination rules.
    page_size = 25
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
                    publication_type = normalize_space(r.get("publicationType"))
                    if publication_type and publication_type.lower() != "journal":
                        continue
                    title = normalize_space(r.get("title"))
                    if not title:
                        continue

                    # The monitor is intentionally based on onlineDate, not the
                    # later volume/issue publicationDate.
                    raw_date = normalize_space(r.get("onlineDate"))
                    online_date, precision = parse_flexible_date(raw_date)
                    if online_date is None:
                        continue

                    creators = r.get("creators") or []
                    doi = clean_doi(first_nonempty(r.get("doi"), r.get("identifier")))
                    identifier = normalize_space(r.get("identifier"))
                    journal = normalize_space(first_nonempty(r.get("publicationName"), r.get("journalTitle")))
                    issn = normalize_space(first_nonempty(r.get("issn"), r.get("eIssn")))

                    matched = match_journal("springer", journal, issn, [spec])
                    if matched is None and journal and journal.lower() not in {
                        spec.journal.lower(), *(a.lower() for a in spec.aliases)
                    }:
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
                        content_type=normalize_space(r.get("contentType")) or "Article",
                        url=_url(r),
                        online_date=online_date,
                        online_date_raw=raw_date,
                        date_precision=precision,
                        online_date_source="Springer onlineDate",
                        source_update_date=online_date,
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


def fetch(start: date, end: date, journals: Sequence[JournalSpec]) -> Iterator[ArticleRecord]:
    if not journals:
        return
    try:
        yield from _fetch_primary(start, end, journals)
    except (requests.RequestException, RuntimeError) as exc:
        if not ENABLE_CROSSREF_FALLBACK:
            raise
        status = getattr(getattr(exc, "response", None), "status_code", None)
        label = f"HTTP {status}" if status else type(exc).__name__
        print(f"[springer] primary Meta API unavailable ({label}); using Crossref fallback")
        yield from crossref.fetch("springer", "Springer Nature", start, end, journals)

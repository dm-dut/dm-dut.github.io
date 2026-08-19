from __future__ import annotations

from datetime import date
from typing import Iterator, Sequence

import requests

from ..config import SPRINGER_API_KEY, ENABLE_CROSSREF_FALLBACK
from ..journals import JournalSpec, display_issn
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


def _preferred_issns(spec: JournalSpec) -> list[str]:
    # journal_list.xlsx stores print ISSN first and eISSN second. For online-first
    # monitoring, try the electronic ISSN first, then the print ISSN if needed.
    return list(reversed(spec.issns)) if spec.issns else []


def _queries(spec: JournalSpec, start: date, end: date) -> list[str]:
    # IMPORTANT: Meta/v2 supports onlinedatefrom/onlinedateto and issn. It does
    # not document a generic `type:Journal` constraint; adding that constraint
    # caused HTTP 404 in the previous build. We filter publicationType=Journal
    # client-side instead.
    date_clause = f"onlinedatefrom:{start.isoformat()} onlinedateto:{end.isoformat()}"
    issns = _preferred_issns(spec)
    if issns:
        return [f"{date_clause} issn:{display_issn(i)}" for i in issns]
    # The supported publication-name constraint is `pub:`.
    safe = spec.journal.replace('"', '\\"')
    return [f'{date_clause} pub:"{safe}"']


def _fetch_query(session, query: str, spec: JournalSpec) -> list[ArticleRecord]:
    page_size = 25
    s = 1
    out: list[ArticleRecord] = []
    seen: set[str] = set()

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

            raw_date = normalize_space(r.get("onlineDate"))
            online_date, precision = parse_flexible_date(raw_date)
            if online_date is None:
                continue

            doi = clean_doi(first_nonempty(r.get("doi"), r.get("identifier")))
            identifier = normalize_space(r.get("identifier"))
            api_journal = normalize_space(first_nonempty(r.get("publicationName"), r.get("journalTitle")))
            # Several Meta/v2 records expose ISSNs under slightly different keys.
            api_issn = normalize_space(first_nonempty(
                r.get("issn"), r.get("eissn"), r.get("eIssn"),
                r.get("electronicIssn"), r.get("printIssn"),
            ))

            identity = doi or identifier or title.lower()
            if identity in seen:
                continue
            seen.add(identity)

            out.append(ArticleRecord(
                provider="springer",
                publisher="Springer Nature",
                title=title,
                # The query itself is scoped to this whitelist journal. Use the
                # canonical whitelist title so the web filters remain stable.
                journal=spec.journal,
                authors=join_authors(r.get("creators") or []),
                doi=doi,
                external_id=identifier or doi,
                issn=api_issn or (display_issn(spec.issns[0]) if spec.issns else ""),
                content_type=normalize_space(r.get("contentType")) or "Journal Article",
                url=_url(r),
                online_date=online_date,
                online_date_raw=raw_date,
                date_precision=precision,
                online_date_source="Springer Meta API onlineDate",
                source_update_date=online_date,
            ))

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

    return out


def _fetch_primary(start: date, end: date, journals: Sequence[JournalSpec]) -> Iterator[ArticleRecord]:
    if not SPRINGER_API_KEY:
        raise RuntimeError("SPRINGER_API_KEY is missing")

    session = build_session()
    global_seen: set[str] = set()

    for spec in journals:
        # Try eISSN first. If it returns records, the print ISSN query would be a
        # duplicate query for the same journal, so stop there. If zero, try the
        # alternate ISSN. This roughly halves normal API traffic.
        for query in _queries(spec, start, end):
            records = _fetch_query(session, query, spec)
            if records:
                for record in records:
                    key = record.doi or record.external_id or record.title.lower()
                    if key in global_seen:
                        continue
                    global_seen.add(key)
                    yield record
                break


def fetch(start: date, end: date, journals: Sequence[JournalSpec]) -> Iterator[ArticleRecord]:
    if not journals:
        return
    try:
        records = list(_fetch_primary(start, end, journals))
        print(f"[springer] Springer Meta API fetched={len(records)}")
        yield from records
    except (requests.RequestException, RuntimeError) as exc:
        if not ENABLE_CROSSREF_FALLBACK:
            raise
        status = getattr(getattr(exc, "response", None), "status_code", None)
        label = f"HTTP {status}" if status else type(exc).__name__
        print(f"[springer] primary Meta API unavailable ({label}); using Crossref fallback")
        records = list(crossref.fetch("springer", "Springer Nature", start, end, journals))
        print(f"[springer] Crossref fallback fetched={len(records)}")
        yield from records

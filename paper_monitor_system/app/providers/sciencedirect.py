from __future__ import annotations

from datetime import date, timedelta
from typing import Iterator, Sequence

import requests

from ..config import ELSEVIER_API_KEY, ELSEVIER_INSTTOKEN, ENABLE_CROSSREF_FALLBACK
from ..journals import JournalSpec, display_issn, match_journal
from ..utils import build_session, clean_doi, first_nonempty, get_json, join_authors, normalize_space
from . import crossref
from .base import ArticleRecord

# ScienceDirect Search API V2. The old /scidir endpoint now returns HTTP 410.
BASE_URL = "https://api.elsevier.com/content/search/sciencedirect"


def _date_range(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _scidir_link(entry: dict) -> str:
    links = entry.get("link") or []
    if isinstance(links, dict):
        links = [links]
    for link in links:
        if isinstance(link, dict) and link.get("@ref") == "scidir" and link.get("@href"):
            return str(link["@href"])
    doi = clean_doi(first_nonempty(entry.get("prism:doi"), entry.get("dc:identifier")))
    return f"https://doi.org/{doi}" if doi else ""


def _authors(entry: dict) -> str:
    authors = entry.get("authors") or {}
    if isinstance(authors, dict):
        authors = authors.get("author") or authors
    return join_authors(authors)


def _query_for_spec(spec: JournalSpec, load_day: date) -> str:
    # Exact-day Load-Date is deliberate: the STANDARD search result does not
    # expose the original load date, so querying day by day preserves the exact
    # ScienceDirect first-load date used by the user's monitor.
    date_clause = f"Load-Date({load_day:%Y%m%d})"
    if spec.issns:
        issn_clause = " OR ".join(f"ISSN({display_issn(i)})" for i in spec.issns)
        return f"{date_clause} AND ({issn_clause})"
    safe_title = spec.journal.replace("}", "\\}").replace("{", "\\{")
    return f"{date_clause} AND Srctitle({{{safe_title}}})"


def _fetch_primary(start: date, end: date, journals: Sequence[JournalSpec]) -> Iterator[ArticleRecord]:
    if not ELSEVIER_API_KEY:
        raise RuntimeError("ELSEVIER_API_KEY is missing")

    session = build_session()
    headers = {"X-ELS-APIKey": ELSEVIER_API_KEY, "Accept": "application/json"}
    if ELSEVIER_INSTTOKEN:
        headers["X-ELS-Insttoken"] = ELSEVIER_INSTTOKEN
    seen: set[str] = set()

    for load_day in _date_range(start, end):
        for spec in journals:
            offset = 0
            while True:
                params = {
                    "query": _query_for_spec(spec, load_day),
                    "content": "journals",
                    "start": offset,
                    "count": 100,
                }
                try:
                    data = get_json(session, BASE_URL, params=params, headers=headers)
                except requests.HTTPError as exc:
                    status = getattr(exc.response, "status_code", None)
                    # 401/403 are normally key/entitlement/IP-wide conditions; one
                    # more journal request will not fix them, so switch the provider
                    # to fallback immediately. Other HTTP errors are isolated to the
                    # current journal/day instead of aborting all 39 journals.
                    if status in {401, 403}:
                        raise
                    print(
                        f"[sciencedirect] API warning: {spec.journal} {load_day} "
                        f"failed (HTTP {status}); continuing with next journal"
                    )
                    break
                results = data.get("search-results", {})
                entries = results.get("entry") or []
                if isinstance(entries, dict):
                    entries = [entries]

                for e in entries:
                    title = normalize_space(e.get("dc:title"))
                    if not title:
                        continue
                    doi = clean_doi(first_nonempty(e.get("prism:doi"), e.get("dc:identifier")))
                    pii = first_nonempty(e.get("pii"), e.get("eid"))
                    journal = normalize_space(e.get("prism:publicationName"))
                    issn = normalize_space(first_nonempty(e.get("prism:issn"), e.get("prism:eIssn")))

                    matched = match_journal("sciencedirect", journal, issn, [spec])
                    if matched is None and journal and journal.lower() != spec.journal.lower():
                        continue

                    identity = doi or str(pii or "") or title.lower()
                    if identity in seen:
                        continue
                    seen.add(identity)

                    yield ArticleRecord(
                        provider="sciencedirect",
                        publisher="Elsevier",
                        title=title,
                        journal=journal or spec.journal,
                        authors=_authors(e) or normalize_space(e.get("dc:creator")),
                        doi=doi,
                        external_id=str(pii) if pii else None,
                        issn=issn or (display_issn(spec.issns[0]) if spec.issns else ""),
                        content_type="Journal Article",
                        url=_scidir_link(e),
                        online_date=load_day,
                        online_date_raw=load_day.isoformat(),
                        date_precision="day",
                        online_date_source="ScienceDirect API Load-Date",
                        source_update_date=load_day,
                    )

                total = int(results.get("opensearch:totalResults") or len(entries) or 0)
                items = int(results.get("opensearch:itemsPerPage") or len(entries) or 0)
                step = max(items, len(entries))
                if not entries or step <= 0 or offset + step >= total:
                    break
                offset += step


def fetch(start: date, end: date, journals: Sequence[JournalSpec]) -> Iterator[ArticleRecord]:
    if not journals:
        return
    try:
        records = list(_fetch_primary(start, end, journals))
        print(f"[sciencedirect] ScienceDirect API fetched={len(records)}")
        yield from records
    except (requests.RequestException, RuntimeError) as exc:
        if not ENABLE_CROSSREF_FALLBACK:
            raise
        status = getattr(getattr(exc, "response", None), "status_code", None)
        label = f"HTTP {status}" if status else type(exc).__name__
        print(f"[sciencedirect] primary API unavailable ({label}); using Crossref fallback")
        records = list(crossref.fetch("sciencedirect", "Elsevier", start, end, journals))
        print(f"[sciencedirect] Crossref fallback fetched={len(records)}")
        yield from records

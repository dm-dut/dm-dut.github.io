from __future__ import annotations

from datetime import date, timedelta
from typing import Iterator, Sequence

from app.config import ELSEVIER_API_KEY
from app.journals import JournalSpec, display_issn, match_journal
from app.utils import build_session, clean_doi, first_nonempty, get_json, join_authors, normalize_space
from .base import ArticleRecord

BASE_URL = "https://api.elsevier.com/content/search/scidir"


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
        if isinstance(link, dict) and link.get("@ref") in {"scidir", "scopus"} and link.get("@href"):
            return link["@href"]
    doi = clean_doi(entry.get("prism:doi"))
    return f"https://doi.org/{doi}" if doi else ""


def _authors(entry: dict) -> str:
    authors = entry.get("authors") or {}
    if isinstance(authors, dict):
        authors = authors.get("author") or authors
    return join_authors(authors)


def _query_for_spec(spec: JournalSpec, load_day: date) -> str:
    date_clause = f"Load-Date({load_day:%Y%m%d})"
    if spec.issns:
        issn_clause = " OR ".join(f"ISSN({display_issn(i)})" for i in spec.issns)
        return f"{date_clause} AND ({issn_clause})"
    # Fallback for a row without ISSN. Exact source-title match is less robust;
    # therefore ISSN/eISSN is strongly recommended in journal_list.xlsx.
    safe_title = spec.journal.replace("}", "\\}").replace("{", "\\{")
    return f"{date_clause} AND Srctitle({{{safe_title}}})"


def fetch(start: date, end: date, journals: Sequence[JournalSpec]) -> Iterator[ArticleRecord]:
    """Fetch only whitelisted journal records first loaded on ScienceDirect in [start, end]."""
    if not ELSEVIER_API_KEY:
        raise RuntimeError("ELSEVIER_API_KEY is missing")
    if not journals:
        return

    session = build_session()
    headers = {"X-ELS-APIKey": ELSEVIER_API_KEY, "Accept": "application/json"}
    seen: set[str] = set()

    for load_day in _date_range(start, end):
        for spec in journals:
            offset = 0
            while True:
                params = {
                    "query": _query_for_spec(spec, load_day),
                    "content": "journals",
                    "view": "STANDARD",
                    "start": offset,
                    "count": 100,
                    "httpAccept": "application/json",
                }
                data = get_json(session, BASE_URL, params=params, headers=headers)
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

                    # Defense-in-depth: verify returned metadata when possible.
                    matched = match_journal("sciencedirect", journal, issn, journals)
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
                        online_date_source="ScienceDirect Load-Date",
                        source_update_date=load_day,
                    )

                total = int(results.get("opensearch:totalResults") or len(entries) or 0)
                items = int(results.get("opensearch:itemsPerPage") or len(entries) or 0)
                if not entries or offset + max(items, len(entries)) >= total:
                    break
                offset += max(items, len(entries))

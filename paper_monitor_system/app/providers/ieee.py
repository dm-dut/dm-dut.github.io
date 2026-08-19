from __future__ import annotations

from datetime import date
from typing import Iterator, Sequence

import requests

from ..config import IEEE_API_KEY, IEEE_QUERYTEXT, ENABLE_CROSSREF_FALLBACK
from ..journals import JournalSpec, display_issn, match_journal
from ..utils import build_session, clean_doi, first_nonempty, get_json, join_authors, normalize_space, parse_flexible_date
from . import crossref
from .base import ArticleRecord

BASE_URL = "https://ieeexploreapi.ieee.org/api/v1/search/articles"


def _authors(article: dict) -> str:
    authors = article.get("authors") or {}
    if isinstance(authors, dict):
        return join_authors(authors.get("authors"))
    return join_authors(authors)


def _search_keys(spec: JournalSpec) -> list[tuple[str, str]]:
    if spec.issns:
        return [("issn", display_issn(i)) for i in spec.issns]
    return [("publication_title", spec.journal)]


def _fetch_one(start: date, end: date, content_type: str, spec: JournalSpec, field: str, value: str) -> Iterator[ArticleRecord]:
    session = build_session()
    start_record = 1
    page_size = 200

    while True:
        params = {
            "apikey": IEEE_API_KEY,
            "format": "json",
            "start_date": start.strftime("%Y%m%d"),
            "end_date": end.strftime("%Y%m%d"),
            "content_type": content_type,
            "max_records": page_size,
            "start_record": start_record,
            field: value,
        }
        if IEEE_QUERYTEXT:
            params["querytext"] = IEEE_QUERYTEXT

        data = get_json(session, BASE_URL, params=params)
        articles = data.get("articles") or []
        if not articles:
            break

        for a in articles:
            title = normalize_space(a.get("title"))
            if not title:
                continue

            insert_raw = normalize_space(a.get("insert_date"))
            insert_date, _ = parse_flexible_date(insert_raw)
            pub_raw = normalize_space(a.get("publication_date"))
            online_date, precision = parse_flexible_date(pub_raw, fallback=insert_date)
            date_source = "IEEE publication_date" if pub_raw and precision != "fallback" else "IEEE insert_date fallback"
            journal = normalize_space(a.get("publication_title"))
            issn = normalize_space(first_nonempty(a.get("issn"), a.get("eissn")))

            matched = match_journal("ieee", journal, issn, [spec])
            if matched is None and journal and journal.lower() != spec.journal.lower():
                continue

            yield ArticleRecord(
                provider="ieee",
                publisher="IEEE",
                title=title,
                journal=journal or spec.journal,
                authors=_authors(a),
                doi=clean_doi(a.get("doi")),
                external_id=str(first_nonempty(a.get("article_number"), a.get("publication_number"), "")) or None,
                issn=issn or (display_issn(spec.issns[0]) if spec.issns else ""),
                content_type=normalize_space(a.get("content_type")) or content_type,
                url=normalize_space(first_nonempty(a.get("html_url"), a.get("abstract_url"), a.get("pdf_url"))),
                online_date=online_date,
                online_date_raw=pub_raw or insert_raw,
                date_precision=precision,
                online_date_source=("IEEE Xplore API " + date_source.removeprefix("IEEE ")),
                source_update_date=insert_date or end,
            )

        total = int(data.get("total_records") or data.get("totalfound") or 0)
        start_record += len(articles)
        if len(articles) < page_size or (total and start_record > total):
            break


def _fetch_primary(start: date, end: date, journals: Sequence[JournalSpec]) -> Iterator[ArticleRecord]:
    if not IEEE_API_KEY:
        raise RuntimeError("IEEE_API_KEY is missing")

    seen: set[str] = set()
    for spec in journals:
        for field, value in _search_keys(spec):
            for content_type in ("Early Access", "Journals"):
                for record in _fetch_one(start, end, content_type, spec, field, value):
                    key = record.doi or record.external_id or record.title.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    yield record


def fetch(start: date, end: date, journals: Sequence[JournalSpec]) -> Iterator[ArticleRecord]:
    if not journals:
        return
    try:
        records = list(_fetch_primary(start, end, journals))
        print(f"[ieee] IEEE Xplore API fetched={len(records)}")
        yield from records
    except (requests.RequestException, RuntimeError) as exc:
        if not ENABLE_CROSSREF_FALLBACK:
            raise
        status = getattr(getattr(exc, "response", None), "status_code", None)
        label = f"HTTP {status}" if status else type(exc).__name__
        print(f"[ieee] primary IEEE API unavailable ({label}); using Crossref fallback")
        records = list(crossref.fetch("ieee", "IEEE", start, end, journals))
        print(f"[ieee] Crossref fallback fetched={len(records)}")
        yield from records

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
    return list(reversed(spec.issns)) if spec.issns else []


def _queries(spec: JournalSpec, start: date, end: date) -> list[str]:
    # Use explicit Boolean AND operators. The API supports onlinedatefrom,
    # onlinedateto and issn; publicationType is filtered client-side.
    date_clause = (
        f"onlinedatefrom:{start.isoformat()} AND "
        f"onlinedateto:{end.isoformat()}"
    )
    issns = _preferred_issns(spec)
    if issns:
        return [f"{date_clause} AND issn:{display_issn(issn)}" for issn in issns]
    safe = spec.journal.replace('"', '\\"')
    return [f'{date_clause} AND pub:"{safe}"']


def _status_label(exc: Exception) -> str:
    status = getattr(getattr(exc, "response", None), "status_code", None)
    return f"HTTP {status}" if status else type(exc).__name__


def _fetch_query(
    session,
    query: str,
    spec: JournalSpec,
    start: date,
    end: date,
) -> list[ArticleRecord]:
    # Keep page size conservative under the basic Meta API plan.
    page_size = 20
    s = 1
    out: list[ArticleRecord] = []
    seen: set[str] = set()

    while True:
        params = {"api_key": SPRINGER_API_KEY, "q": query, "s": s, "p": page_size}
        data = get_json(session, BASE_URL, params=params)
        records = data.get("records") or []
        if not records:
            break

        for record in records:
            publication_type = normalize_space(record.get("publicationType"))
            if publication_type and publication_type.lower() != "journal":
                continue

            title = normalize_space(record.get("title"))
            if not title:
                continue

            raw_date = normalize_space(record.get("onlineDate"))
            online_date, precision = parse_flexible_date(raw_date)
            if online_date is None or online_date < start or online_date > end:
                continue

            doi = clean_doi(first_nonempty(record.get("doi"), record.get("identifier")))
            identifier = normalize_space(record.get("identifier"))
            api_issn = normalize_space(first_nonempty(
                record.get("issn"), record.get("eissn"), record.get("eIssn"),
                record.get("electronicIssn"), record.get("printIssn"),
            ))

            identity = doi or identifier or title.lower()
            if identity in seen:
                continue
            seen.add(identity)

            out.append(ArticleRecord(
                provider="springer",
                publisher="Springer Nature",
                title=title,
                journal=spec.journal,
                authors=join_authors(record.get("creators") or []),
                doi=doi,
                external_id=identifier or doi,
                issn=api_issn or (display_issn(spec.issns[0]) if spec.issns else ""),
                content_type=normalize_space(record.get("contentType")) or "Journal Article",
                url=_url(record),
                online_date=online_date,
                online_date_raw=raw_date,
                date_precision=precision,
                online_date_source="Springer Meta API onlineDate",
                source_update_date=online_date,
            ))

        result = data.get("result") or []
        try:
            total = int(result[0].get("total", 0)) if result and isinstance(result, list) else 0
        except (TypeError, ValueError, AttributeError):
            total = 0

        s += len(records)
        if len(records) < page_size or (total and s > total):
            break

    return out


def fetch(start: date, end: date, journals: Sequence[JournalSpec]) -> Iterator[ArticleRecord]:
    if not journals:
        return

    # Missing key: fall back for all journals rather than failing the whole run.
    if not SPRINGER_API_KEY:
        if not ENABLE_CROSSREF_FALLBACK:
            raise RuntimeError("SPRINGER_API_KEY is missing")
        print("[springer] SPRINGER_API_KEY missing; using Crossref fallback for all journals")
        records = list(crossref.fetch("springer", "Springer Nature", start, end, journals))
        print(f"[springer] Crossref fallback fetched={len(records)}")
        yield from records
        return

    session = build_session()
    global_seen: set[str] = set()
    primary_count = 0
    fallback_specs: list[JournalSpec] = []

    for spec in journals:
        spec_records: list[ArticleRecord] = []
        any_successful_query = False
        errors: list[str] = []

        # Try eISSN first and then print ISSN. A failure on one journal/ISSN no
        # longer sends all 25 Springer journals to fallback.
        for query in _queries(spec, start, end):
            try:
                records = _fetch_query(session, query, spec, start, end)
                any_successful_query = True
            except requests.RequestException as exc:
                errors.append(_status_label(exc))
                print(
                    f"[springer] Meta API warning: {spec.journal} query failed "
                    f"({_status_label(exc)}); trying alternate ISSN"
                )
                continue

            if records:
                spec_records = records
                break

        if any_successful_query:
            for record in spec_records:
                key = record.doi or record.external_id or record.title.lower()
                if key in global_seen:
                    continue
                global_seen.add(key)
                primary_count += 1
                yield record
        else:
            fallback_specs.append(spec)
            detail = ", ".join(errors) or "no successful Meta API request"
            print(f"[springer] {spec.journal}: primary unavailable ({detail}); queued for Crossref fallback")

    print(f"[springer] Springer Meta API fetched={primary_count}")

    if fallback_specs:
        if not ENABLE_CROSSREF_FALLBACK:
            raise RuntimeError(f"Springer Meta API failed for {len(fallback_specs)} journal(s) and fallback is disabled")
        records = list(crossref.fetch("springer", "Springer Nature", start, end, fallback_specs))
        emitted = 0
        for record in records:
            key = record.doi or record.external_id or record.title.lower()
            if key in global_seen:
                continue
            global_seen.add(key)
            emitted += 1
            yield record
        print(f"[springer] Crossref fallback fetched={emitted} for {len(fallback_specs)} journal(s)")

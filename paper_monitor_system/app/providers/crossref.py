from __future__ import annotations

from datetime import date
from typing import Iterator, Sequence

from ..config import CROSSREF_MAILTO
from ..journals import JournalSpec, display_issn, match_journal
from ..utils import build_session, clean_doi, get_json, normalize_space
from .base import ArticleRecord

BASE_URL = "https://api.crossref.org/works"


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
    for a in item.get("author") or []:
        if not isinstance(a, dict):
            continue
        given = normalize_space(str(a.get("given") or ""))
        family = normalize_space(str(a.get("family") or ""))
        name = normalize_space(f"{given} {family}")
        if name:
            out.append(name)
    return "; ".join(out)


def _first_text(value) -> str:
    if isinstance(value, list):
        return normalize_space(str(value[0])) if value else ""
    return normalize_space(str(value or ""))


def _fetch_issn(
    provider: str,
    publisher: str,
    spec: JournalSpec,
    issn: str,
    start: date,
    end: date,
) -> Iterator[ArticleRecord]:
    session = build_session()
    filters = ",".join(
        [
            "type:journal-article",
            f"issn:{display_issn(issn)}",
            f"from-online-pub-date:{start.isoformat()}",
            f"until-online-pub-date:{end.isoformat()}",
        ]
    )
    params = {"filter": filters, "rows": 1000}
    if CROSSREF_MAILTO:
        params["mailto"] = CROSSREF_MAILTO

    data = get_json(session, BASE_URL, params=params)
    items = ((data.get("message") or {}).get("items") or [])
    for item in items:
        if not isinstance(item, dict):
            continue
        online_date, precision, raw_date = _date_parts(item)
        # The query is specifically filtered on published-online. If a record
        # still lacks that field, do not substitute print/issued dates.
        if online_date is None:
            continue

        title = _first_text(item.get("title"))
        journal = _first_text(item.get("container-title")) or spec.journal
        issns = "; ".join(str(x) for x in (item.get("ISSN") or []) if x)
        matched = match_journal(provider, journal, issns or display_issn(issn), [spec])
        if matched is None:
            continue

        doi = clean_doi(item.get("DOI"))
        url = normalize_space(str(item.get("URL") or ""))
        if not url and doi:
            url = f"https://doi.org/{doi}"
        alt = item.get("alternative-id") or []
        external_id = normalize_space(str(alt[0])) if isinstance(alt, list) and alt else None

        yield ArticleRecord(
            provider=provider,
            publisher=publisher,
            title=title,
            journal=journal,
            authors=_authors(item),
            doi=doi,
            external_id=external_id,
            issn=issns or display_issn(issn),
            content_type="Journal Article",
            url=url,
            online_date=online_date,
            online_date_raw=raw_date,
            date_precision=precision,
            online_date_source="Crossref published-online fallback",
            source_update_date=online_date,
        )


def fetch(
    provider: str,
    publisher: str,
    start: date,
    end: date,
    journals: Sequence[JournalSpec],
) -> Iterator[ArticleRecord]:
    """Crossref fallback using ISSN + published-online date.

    It intentionally keeps ``provider`` as sciencedirect/springer/ieee so the
    existing publisher tabs and whitelist continue to work.
    """
    seen: set[str] = set()
    for spec in journals:
        if not spec.issns:
            # All current whitelist rows have an ISSN/eISSN. A title-only
            # Crossref fallback is deliberately avoided to prevent false hits.
            continue
        for issn in spec.issns:
            for record in _fetch_issn(provider, publisher, spec, issn, start, end):
                key = record.doi or record.external_id or record.title.lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                yield record

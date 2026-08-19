from __future__ import annotations

from datetime import date
from time import perf_counter
from typing import Iterator, Sequence

import requests

from ..config import ENABLE_IEEE_CROSSREF_SUPPLEMENT, HTTP_TIMEOUT, IEEE_SAVED_SEARCH_RSS_URL
from ..journals import JournalSpec, display_issn, match_journal
from ..utils import build_session, normalize_space, parse_flexible_date
from . import crossref
from .base import ArticleRecord
from .enrichment import extract_doi, page_metadata, resolve_crossref
from .rss_source import parse_feed


def _normalize_saved_search_url(url: str) -> str:
    """Preserve the user's IEEE Saved Search URL apart from surrounding whitespace."""
    return normalize_space(url)


def _combined_rss_urls(journals: Sequence[JournalSpec]) -> list[str]:
    urls: list[str] = []
    if IEEE_SAVED_SEARCH_RSS_URL:
        urls.append(_normalize_saved_search_url(IEEE_SAVED_SEARCH_RSS_URL))
    for spec in journals:
        if spec.rss_url:
            normalized = _normalize_saved_search_url(spec.rss_url)
            if normalized and normalized not in urls:
                urls.append(normalized)
    return urls


def _spec_from_text(text: str, journals: Sequence[JournalSpec]) -> JournalSpec | None:
    low = normalize_space(text).lower()
    if not low:
        return None
    candidates: list[tuple[int, JournalSpec, str]] = []
    for spec in journals:
        for name in (spec.journal, *spec.aliases):
            name_low = normalize_space(name).lower()
            if name_low:
                candidates.append((len(name_low), spec, name_low))
    for _, spec, name_low in sorted(candidates, reverse=True, key=lambda x: x[0]):
        if name_low in low:
            return spec
    return None


def _entry_to_record(entry: dict, journals: Sequence[JournalSpec], start: date, end: date) -> ArticleRecord | None:
    title = normalize_space(entry.get("title") or "")
    link = normalize_space(entry.get("link") or "")
    ident = normalize_space(entry.get("id") or "")
    summary = normalize_space(entry.get("summary") or "")
    publication = normalize_space(entry.get("publication") or "")
    rss_raw = normalize_space(entry.get("published") or "")
    rss_date, rss_precision = parse_flexible_date(rss_raw) if rss_raw else (None, "unknown")
    if not title:
        return None

    text_blob = " ".join([title, publication, summary, ident])
    spec = match_journal("ieee", publication, "", journals) if publication else None
    if spec is None:
        spec = _spec_from_text(text_blob, journals)
    doi = extract_doi(" ".join([link, summary, ident]))

    # Crossref is enrichment/validation, not a publication gate.
    cr: dict = {}
    if doi:
        try:
            cr = resolve_crossref(title, spec or journals[0], doi)
        except requests.RequestException:
            cr = {}
    elif spec:
        try:
            cr = resolve_crossref(title, spec, None)
        except requests.RequestException:
            cr = {}

    if spec is None and cr:
        spec = match_journal("ieee", cr.get("journal"), cr.get("issn"), journals)

    # Only open the IEEE article page when journal identity is still unknown or
    # when it may provide a stronger publisher date.  A page failure does not
    # discard an otherwise valid Saved Search RSS record.
    page: dict = {}
    need_page = spec is None or (not cr.get("online_date") and bool(link))
    if need_page and link:
        try:
            page = page_metadata(link)
        except requests.RequestException:
            page = {}
        doi = page.get("doi") or doi
        if spec is None:
            spec = match_journal("ieee", page.get("journal"), page.get("issn"), journals)

    if spec is None:
        return None

    if not cr and doi:
        try:
            cr = resolve_crossref(title, spec, doi)
        except requests.RequestException:
            cr = {}

    # If publisher/Crossref supplied a journal identity, it must map to the
    # whitelist.  Otherwise an exact journal name found in the Saved Search RSS
    # is sufficient; this allows RSS to remain the primary IEEE source.
    authoritative_journal = page.get("journal") or cr.get("journal")
    authoritative_issn = page.get("issn") or cr.get("issn")
    if authoritative_journal or authoritative_issn:
        confirmed = match_journal("ieee", authoritative_journal or spec.journal, authoritative_issn, journals)
        if confirmed is None:
            return None
        spec = confirmed

    doi = page.get("doi") or doi or cr.get("doi")
    online = page.get("online_date") or cr.get("online_date")
    raw = page.get("online_raw") or cr.get("online_raw") or ""
    precision = page.get("precision") or cr.get("precision") or "unknown"
    source = ""

    if online:
        if not (start <= online <= end):
            return None
        source = (
            "IEEE Saved Search RSS + IEEE page publication date"
            if page.get("online_date")
            else "IEEE Saved Search RSS + Crossref published-online"
        )
    elif rss_date and start <= rss_date <= end:
        # V3.2 fallback: IEEE's own Saved Search RSS timestamp is accepted as a
        # clearly-labelled fallback date.  It can later be replaced by a higher
        # priority publisher/Crossref published-online date.
        online = rss_date
        raw = rss_raw
        precision = rss_precision
        source = "IEEE Saved Search RSS pubDate fallback"
    else:
        # Keep a DOI-bearing discovery as pending for later DOI-only recheck.
        if not doi:
            return None
        source = "IEEE Saved Search RSS discovery; awaiting published-online"

    return ArticleRecord(
        provider="ieee",
        publisher="IEEE",
        title=page.get("title") or title,
        journal=spec.journal,
        authors=page.get("authors") or cr.get("authors") or "",
        doi=doi,
        external_id=ident or link,
        issn=page.get("issn") or cr.get("issn") or (display_issn(spec.issns[0]) if spec.issns else ""),
        content_type="Journal Article",
        url=page.get("url") or link or cr.get("url") or "",
        online_date=online,
        online_date_raw=raw,
        date_precision=precision,
        online_date_source=source,
        source_update_date=online,
        status="published" if online else "pending",
    )


def _fetch_combined_rss(url: str, journals: Sequence[JournalSpec], start: date, end: date) -> list[ArticleRecord]:
    session = build_session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    response = session.get(url, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    entries = parse_feed(response.content)
    if not entries:
        content_type = response.headers.get("content-type", "") if hasattr(response, "headers") else ""
        raise RuntimeError(f"IEEE Saved Search RSS returned no RSS/Atom entries (content-type={content_type!r})")

    records: list[ArticleRecord] = []
    seen: set[str] = set()
    for idx, entry in enumerate(entries, start=1):
        title = normalize_space(entry.get("title") or "")
        print(f"[ieee] RSS entry {idx}/{len(entries)}: {title[:90]}")
        record = _entry_to_record(entry, journals, start, end)
        if record is None:
            continue
        key = record.doi or record.external_id or record.title.lower()
        if not key or key in seen:
            continue
        seen.add(key)
        records.append(record)
    rss_fallback = sum(1 for r in records if r.online_date_source == "IEEE Saved Search RSS pubDate fallback")
    pending = sum(1 for r in records if r.online_date is None)
    print(
        f"[ieee] combined Saved Search RSS entries={len(entries)}, accepted_whitelist_records={len(records)}, "
        f"rss_date_fallback={rss_fallback}, pending={pending}"
    )
    if len(entries) == 10 and "rowsPerPage=10" in url:
        print("[ieee] NOTE: feed returned the configured 10-item page limit; daily local scheduling is recommended.")
    return records


def fetch(start: date, end: date, journals: Sequence[JournalSpec]) -> Iterator[ArticleRecord]:
    t0 = perf_counter()
    rss_urls = _combined_rss_urls(journals)
    seen: set[str] = set()
    rss_records: list[ArticleRecord] = []
    successful_feeds = 0

    for url in rss_urls:
        try:
            rss_records.extend(_fetch_combined_rss(url, journals, start, end))
            successful_feeds += 1
        except Exception as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            suffix = f" HTTP {status}" if status else ""
            print(f"[ieee] Saved Search RSS warning:{suffix} {type(exc).__name__}: {exc}")

    if rss_urls and successful_feeds == 0:
        raise RuntimeError("All configured IEEE Saved Search RSS feeds failed")

    for record in rss_records:
        key = record.doi or record.external_id or record.title.lower()
        if key in seen:
            continue
        seen.add(key)
        yield record

    # Disabled by default in V3 because the combined RSS is the discovery source;
    # per-journal Crossref supplementation would add up to dozens of extra requests.
    if ENABLE_IEEE_CROSSREF_SUPPLEMENT:
        journals_seen = {r.journal for r in rss_records}
        missing = [spec for spec in journals if spec.journal not in journals_seen]
        if missing:
            try:
                for record in crossref.fetch("ieee", "IEEE", start, end, missing):
                    key = record.doi or record.external_id or record.title.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    yield record
            except Exception as exc:
                print(f"[ieee] optional Crossref supplement warning: {type(exc).__name__}: {exc}")

    elapsed = perf_counter() - t0
    print(
        f"[ieee] sources: combined_saved_search_rss={len(rss_urls)} feed(s), rss_records={len(rss_records)}, "
        f"total_unique_records={len(seen)}, elapsed={elapsed:.1f}s"
    )
    if not rss_urls:
        raise RuntimeError("No IEEE Saved Search RSS URL is configured")

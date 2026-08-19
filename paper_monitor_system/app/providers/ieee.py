from __future__ import annotations

from datetime import date
from time import perf_counter
from typing import Iterator, Sequence

import requests

from ..config import (
    ENABLE_IEEE_CROSSREF_SUPPLEMENT,
    ENABLE_IEEE_PAGE_ENRICHMENT,
    HTTP_TIMEOUT,
    IEEE_SAVED_SEARCH_RSS_URL,
    IEEE_TITLE_MATCH_THRESHOLD,
)
from ..journals import JournalSpec, display_issn, match_journal
from ..utils import build_session, normalize_space, parse_flexible_date
from . import crossref
from .base import ArticleRecord
from .enrichment import crossref_by_doi, extract_doi, page_metadata
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


def _crossref_candidate(title: str, doi: str | None, journals: Sequence[JournalSpec]) -> tuple[dict, JournalSpec | None, str, float]:
    """Resolve one RSS item against Crossref.

    DOI lookup is preferred when the feed exposes a DOI.  Otherwise a title
    query is run and only results whose container-title/ISSN maps to the 15
    journal whitelist are eligible.  This is what makes the combined IEEE RSS
    usable even when the RSS itself contains no journal field.
    """
    if doi:
        try:
            item = crossref_by_doi(doi) or {}
        except requests.RequestException:
            item = {}
        if item:
            spec = match_journal("ieee", crossref._container_title(item), crossref._item_issns(item), journals)
            if spec is not None:
                score = crossref.title_similarity(title, crossref._first_text(item.get("title")))
                # A DOI extracted from IEEE's own RSS/link is strong evidence;
                # keep a modest title guard to avoid malformed identifiers.
                if score >= 0.70:
                    return item, spec, "doi", score

    try:
        matched = crossref.search_title_match(title, "ieee", journals)
    except requests.RequestException:
        matched = None
    if matched:
        item, spec, score = matched
        return item, spec, "title-search", score
    return {}, None, "none", 0.0


def _entry_to_record(
    entry: dict,
    journals: Sequence[JournalSpec],
    start: date,
    end: date,
    *,
    diagnostic_prefix: str = "",
) -> ArticleRecord | None:
    title = normalize_space(entry.get("title") or "")
    link = normalize_space(entry.get("link") or "")
    ident = normalize_space(entry.get("id") or "")
    summary = normalize_space(entry.get("summary") or "")
    publication = normalize_space(entry.get("publication") or "")
    rss_raw = normalize_space(entry.get("published") or "")
    rss_date, rss_precision = parse_flexible_date(rss_raw) if rss_raw else (None, "unknown")
    if not title:
        if diagnostic_prefix:
            print(f"{diagnostic_prefix} rejected: empty-title")
        return None

    text_blob = " ".join([publication, summary, ident])
    spec = match_journal("ieee", publication, "", journals) if publication else None
    if spec is None:
        spec = _spec_from_text(text_blob, journals)

    doi = extract_doi(" ".join([normalize_space(entry.get("doi") or ""), link, summary, ident]))
    cr_item, cr_spec, cr_method, cr_score = _crossref_candidate(title, doi, journals)
    if cr_spec is not None:
        spec = cr_spec
    cr = crossref.metadata_from_item(cr_item) if cr_item else {}
    doi = doi or cr.get("doi")

    # Optional publisher-page enrichment is deliberately off by default.  It
    # is only a last resort because IEEE page requests were much slower than
    # the RSS + Crossref route in local testing.
    page: dict = {}
    if ENABLE_IEEE_PAGE_ENRICHMENT and link and (spec is None or not cr.get("online_date")):
        try:
            page = page_metadata(link)
        except requests.RequestException:
            page = {}
        doi = page.get("doi") or doi
        page_spec = match_journal("ieee", page.get("journal"), page.get("issn"), journals)
        if page_spec is not None:
            spec = page_spec

    if spec is None:
        if diagnostic_prefix:
            print(
                f"{diagnostic_prefix} rejected: no-whitelist-match "
                f"(crossref_method={cr_method}, score={cr_score:.3f})"
            )
        return None

    # If Crossref/page supplied an authoritative journal identity, it must map
    # back to the whitelist.  This filters Virtual Journals/Compendia while
    # still allowing their underlying Transactions article to pass.
    authoritative_journal = page.get("journal") or cr.get("journal")
    authoritative_issn = page.get("issn") or cr.get("issn")
    if authoritative_journal or authoritative_issn:
        confirmed = match_journal("ieee", authoritative_journal or spec.journal, authoritative_issn, journals)
        if confirmed is None:
            if diagnostic_prefix:
                print(f"{diagnostic_prefix} rejected: authoritative-journal-not-whitelisted")
            return None
        spec = confirmed

    online = page.get("online_date") or cr.get("online_date")
    raw = page.get("online_raw") or cr.get("online_raw") or ""
    precision = page.get("precision") or cr.get("precision") or "unknown"

    if online:
        if not (start <= online <= end):
            if diagnostic_prefix:
                print(f"{diagnostic_prefix} rejected: online-date-outside-window ({online})")
            return None
        source = (
            "IEEE Saved Search RSS + IEEE page publication date"
            if page.get("online_date")
            else "IEEE Saved Search RSS + Crossref published-online"
        )
        date_method = "publisher/crossref"
    elif rss_date and start <= rss_date <= end:
        # The Saved Search feed itself is the verified IEEE discovery source.
        # Its pubDate is accepted as an explicitly labelled lower-priority
        # fallback and can later be upgraded by Crossref/publisher metadata.
        online = rss_date
        raw = rss_raw
        precision = rss_precision
        source = "IEEE Saved Search RSS pubDate fallback"
        date_method = "rss-fallback"
    else:
        # If the article is confidently mapped to the whitelist and has a DOI,
        # keep it pending for later DOI-only recheck.  Do not discard it.
        if not doi:
            if diagnostic_prefix:
                print(f"{diagnostic_prefix} rejected: no-date-and-no-doi")
            return None
        source = "IEEE Saved Search RSS discovery; awaiting published-online"
        date_method = "pending"

    if diagnostic_prefix:
        print(
            f"{diagnostic_prefix} accepted: {spec.journal}; match={cr_method} "
            f"score={cr_score:.3f}; date={date_method}"
        )

    return ArticleRecord(
        provider="ieee",
        publisher="IEEE",
        title=page.get("title") or cr.get("title") or title,
        journal=spec.journal,
        authors=page.get("authors") or cr.get("authors") or "",
        doi=doi,
        external_id=ident or link,
        issn=page.get("issn") or cr.get("issn") or (display_issn(spec.issns[0]) if spec.issns else ""),
        content_type="Journal Article",
        url=page.get("url") or cr.get("url") or link or (f"https://doi.org/{doi}" if doi else ""),
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
    rejected = 0
    for idx, entry in enumerate(entries, start=1):
        title = normalize_space(entry.get("title") or "")
        print(f"[ieee] RSS entry {idx}/{len(entries)}: {title[:90]}")
        record = _entry_to_record(
            entry, journals, start, end,
            diagnostic_prefix=f"[ieee] RSS resolve {idx}/{len(entries)}",
        )
        if record is None:
            rejected += 1
            continue
        key = record.doi or record.external_id or record.title.lower()
        if not key or key in seen:
            continue
        seen.add(key)
        records.append(record)

    rss_fallback = sum(1 for r in records if r.online_date_source == "IEEE Saved Search RSS pubDate fallback")
    crossref_dates = sum(1 for r in records if "Crossref published-online" in r.online_date_source)
    pending = sum(1 for r in records if r.online_date is None)
    print(
        f"[ieee] combined Saved Search RSS entries={len(entries)}, accepted_whitelist_records={len(records)}, "
        f"crossref_dates={crossref_dates}, rss_date_fallback={rss_fallback}, pending={pending}, rejected={rejected}"
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

    # Optional old per-journal supplement; disabled by default because the
    # combined RSS plus title resolution is now the primary discovery route.
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

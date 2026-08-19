from __future__ import annotations

from datetime import date
from typing import Iterator, Sequence

import requests

from ..config import ENABLE_CROSSREF_FALLBACK, HTTP_TIMEOUT, IEEE_SAVED_SEARCH_RSS_URL
from ..journals import JournalSpec, display_issn, match_journal
from ..utils import build_session, normalize_space
from . import crossref
from .base import ArticleRecord
from .enrichment import extract_doi, page_metadata, resolve_crossref
from .rss_source import parse_feed


def _normalize_saved_search_url(url: str) -> str:
    """Preserve the user's IEEE Saved Search RSS URL byte-for-byte apart from whitespace.

    Earlier hybrid builds rewrote rowsPerPage=10 to 100. That changes the saved-search
    URL and may trigger IEEE anti-bot/session checks. The local build deliberately does
    NOT alter rowsPerPage, queryText, rssFeedName, or any other parameter.
    """
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
    if not title:
        return None

    # RSS is a discovery channel. Publisher-page/Crossref metadata determines the
    # original journal and online date, which also filters Virtual Journals and
    # Compendia from the final 15-journal whitelist.
    spec = _spec_from_text(" ".join([title, summary, ident]), journals)
    doi = extract_doi(" ".join([link, summary, ident]))

    page: dict = {}
    if link:
        try:
            page = page_metadata(link)
        except requests.RequestException:
            page = {}
    doi = page.get("doi") or doi

    cr: dict = {}
    if doi or not spec:
        seed_spec = spec or journals[0]
        try:
            cr = resolve_crossref(title, seed_spec, doi)
        except requests.RequestException:
            cr = {}

    if spec is None:
        spec = match_journal("ieee", page.get("journal"), page.get("issn"), journals)
    if spec is None:
        spec = match_journal("ieee", cr.get("journal"), cr.get("issn"), journals)
    if spec is None:
        return None

    if not cr:
        try:
            cr = resolve_crossref(title, spec, doi)
        except requests.RequestException:
            cr = {}

    online = page.get("online_date") or cr.get("online_date")
    raw = page.get("online_raw") or cr.get("online_raw") or ""
    precision = page.get("precision") or cr.get("precision") or "unknown"
    # Never use the RSS pubDate as the article's online-publication date.
    if not online or online < start or online > end:
        return None

    source = (
        "IEEE Saved Search RSS + IEEE page publication date"
        if page.get("online_date")
        else "IEEE Saved Search RSS + Crossref published-online"
    )

    return ArticleRecord(
        provider="ieee",
        publisher="IEEE",
        title=page.get("title") or title,
        journal=spec.journal,
        authors=page.get("authors") or cr.get("authors") or "",
        doi=doi or cr.get("doi"),
        external_id=ident or link,
        issn=page.get("issn") or cr.get("issn") or (display_issn(spec.issns[0]) if spec.issns else ""),
        content_type="Journal Article",
        url=page.get("url") or link or cr.get("url") or "",
        online_date=online,
        online_date_raw=raw,
        date_precision=precision,
        online_date_source=source,
        source_update_date=online,
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
    for entry in entries:
        record = _entry_to_record(entry, journals, start, end)
        if record is None:
            continue
        key = record.doi or record.external_id or record.title.lower()
        if not key or key in seen:
            continue
        seen.add(key)
        records.append(record)
    print(f"[ieee] combined Saved Search RSS entries={len(entries)}, accepted_whitelist_records={len(records)}")
    return records


def fetch(start: date, end: date, journals: Sequence[JournalSpec]) -> Iterator[ArticleRecord]:
    rss_urls = _combined_rss_urls(journals)
    seen: set[str] = set()
    rss_records: list[ArticleRecord] = []

    for url in rss_urls:
        try:
            rss_records.extend(_fetch_combined_rss(url, journals, start, end))
        except Exception as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            suffix = f" HTTP {status}" if status else ""
            print(f"[ieee] Saved Search RSS warning:{suffix} {type(exc).__name__}: {exc}")

    for record in rss_records:
        key = record.doi or record.external_id or record.title.lower()
        if key in seen:
            continue
        seen.add(key)
        yield record

    if ENABLE_CROSSREF_FALLBACK:
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
                print(f"[ieee] Crossref supplement warning: {type(exc).__name__}: {exc}")

    print(
        f"[ieee] sources: combined_saved_search_rss={len(rss_urls)} feed(s), "
        f"rss_records={len(rss_records)}, total_unique_records={len(seen)}"
    )
    if not rss_urls:
        print("[ieee] WARNING: no Saved Search RSS URL is configured in journal_list.xlsx or IEEE_SAVED_SEARCH_RSS_URL")

from __future__ import annotations

from datetime import date
from typing import Iterator, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

from ..config import ENABLE_CROSSREF_FALLBACK, HTTP_TIMEOUT, IEEE_SAVED_SEARCH_RSS_URL
from ..journals import JournalSpec, display_issn, match_journal
from ..utils import build_session, normalize_space
from . import crossref
from .base import ArticleRecord
from .enrichment import extract_doi, page_metadata, resolve_crossref
from .rss_source import parse_feed


def _normalize_saved_search_url(url: str) -> str:
    """Keep the user's saved-search RSS but request a larger result window.

    IEEE may ignore rowsPerPage for RSS; changing it is harmless and helps when
    the endpoint honors normal search-result pagination.
    """
    url = normalize_space(url)
    if not url:
        return ""
    parts = urlsplit(url)
    params = dict(parse_qsl(parts.query, keep_blank_values=True))
    params["rssFeed"] = "true"
    params["sortType"] = "newest"
    try:
        rows = int(params.get("rowsPerPage", "10") or "10")
    except ValueError:
        rows = 10
    params["rowsPerPage"] = str(max(rows, 100))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(params, doseq=True), parts.fragment))


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
    # Longest title first prevents a short/old alias from stealing a match.
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

    # First try the RSS text itself. Then inspect the IEEE article page and
    # Crossref metadata. This is what allows one combined RSS to be mapped back
    # to the 15 target journals while excluding Virtual Journals/Compendia.
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
        # If the page is incomplete, DOI metadata usually gives the original
        # IEEE journal title/ISSN even when the RSS result came through a
        # Compendium/Virtual Journal presentation.
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

    # Once the journal is known, retry Crossref with the correct spec so its
    # title-search ISSN penalty is meaningful if DOI was missing.
    if not cr:
        try:
            cr = resolve_crossref(title, spec, doi)
        except requests.RequestException:
            cr = {}

    online = page.get("online_date") or cr.get("online_date")
    raw = page.get("online_raw") or cr.get("online_raw") or ""
    precision = page.get("precision") or cr.get("precision") or "unknown"
    # RSS pubDate is deliberately NOT accepted as an online-publication date.
    if not online or online < start or online > end:
        return None

    if page.get("online_date"):
        source = "IEEE Saved Search RSS + IEEE page publication date"
    else:
        source = "IEEE Saved Search RSS + Crossref published-online"

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

    # Crossref is a supplement, not a replacement for RSS discovery. It is run
    # only for journals that produced no accepted RSS record in this window.
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

from __future__ import annotations

import re
from datetime import date
from typing import Iterator, Sequence

import requests
from bs4 import BeautifulSoup

from ..config import ENABLE_CROSSREF_FALLBACK, HTTP_TIMEOUT
from ..journals import JournalSpec, display_issn
from ..utils import build_session, normalize_space, parse_flexible_date
from . import crossref
from .base import ArticleRecord
from .enrichment import extract_doi, page_metadata, resolve_crossref
from .rss_source import fetch_rss

DATE_RE = re.compile(r"Available online\s+([0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})", re.I)


def _base_url(spec: JournalSpec) -> str:
    u = spec.primary_url.rstrip("/")
    if "/articles-in-press" in u:
        return u.split("/articles-in-press")[0]
    if "/latest" in u:
        return u.split("/latest")[0]
    return u


def _candidate_pages(spec: JournalSpec) -> list[str]:
    base = _base_url(spec)
    out: list[str] = []
    candidates: list[str] = []
    if spec.primary_url and "/articles-in-press" in spec.primary_url:
        candidates.append(spec.primary_url)
    if base:
        candidates.extend([f"{base}/articles-in-press", f"{base}/latest"])
    candidates.extend([spec.primary_url, base])
    for url in candidates:
        if url and url not in out:
            out.append(url)
    return out


def _page_records(spec: JournalSpec, start: date, end: date) -> list[ArticleRecord]:
    session = build_session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    })
    last_error: Exception | None = None
    for page_url in _candidate_pages(spec):
        try:
            response = session.get(page_url, timeout=HTTP_TIMEOUT)
            response.raise_for_status()
        except requests.RequestException as exc:
            last_error = exc
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        links: list[tuple[str, str]] = []
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if "/science/article/pii/" not in href:
                continue
            full = requests.compat.urljoin(response.url, href)
            title = normalize_space(a.get_text(" ", strip=True))
            if title and (full, title) not in links:
                links.append((full, title))

        records: list[ArticleRecord] = []
        seen: set[str] = set()
        for link, title in links[:160]:
            container = soup.find("a", href=lambda x: x and link.split("sciencedirect.com")[-1] in x)
            text = normalize_space(container.parent.parent.get_text(" ", strip=True)) if container and container.parent else ""
            match = DATE_RE.search(text)
            online = None
            precision = "unknown"
            raw = ""
            if match:
                raw = match.group(1)
                online, precision = parse_flexible_date(raw)

            meta: dict = {}
            if not online:
                try:
                    meta = page_metadata(link)
                except requests.RequestException:
                    meta = {}
                online = meta.get("online_date")
                precision = meta.get("precision") or precision
                raw = meta.get("online_raw") or raw

            doi = meta.get("doi") or extract_doi(text)
            try:
                cr = resolve_crossref(title, spec, doi)
            except requests.RequestException:
                cr = {}
            online = online or cr.get("online_date")
            raw = raw or cr.get("online_raw") or ""
            precision = precision if precision != "unknown" else (cr.get("precision") or "unknown")
            if not online or online < start or online > end:
                continue

            key = doi or link
            if key in seen:
                continue
            seen.add(key)
            records.append(ArticleRecord(
                provider="sciencedirect",
                publisher="Elsevier",
                title=meta.get("title") or title,
                journal=spec.journal,
                authors=meta.get("authors") or cr.get("authors") or "",
                doi=doi or cr.get("doi"),
                external_id=link,
                issn=display_issn(spec.issns[0]) if spec.issns else "",
                content_type="Journal Article",
                url=link,
                online_date=online,
                online_date_raw=raw,
                date_precision=precision,
                online_date_source="ScienceDirect page Available online",
                source_update_date=online,
            ))
        if records:
            return records

    if last_error:
        raise last_error
    return []


def _discover_rss_urls(spec: JournalSpec) -> list[str]:
    """Read explicit RSS/Atom links from journal pages instead of guessing URLs."""
    out: list[str] = []
    if spec.rss_url:
        out.append(spec.rss_url)

    session = build_session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    })
    for page_url in _candidate_pages(spec):
        try:
            response = session.get(page_url, timeout=30)
            response.raise_for_status()
        except requests.RequestException:
            continue
        soup = BeautifulSoup(response.text, "html.parser")

        for tag in soup.find_all("link", href=True):
            typ = (tag.get("type") or "").lower()
            rel = " ".join(tag.get("rel") or []).lower()
            href = tag.get("href") or ""
            if "rss" in typ or "atom" in typ or ("alternate" in rel and ("rss" in href.lower() or "feed" in href.lower())):
                full = requests.compat.urljoin(response.url, href)
                if full.startswith("http") and full not in out:
                    out.append(full)

        for a in soup.find_all("a", href=True):
            href = a.get("href") or ""
            text = normalize_space(a.get_text(" ", strip=True)).lower()
            if "rss" in text or "rss" in href.lower():
                full = requests.compat.urljoin(response.url, href)
                if full.startswith("http") and full not in out:
                    out.append(full)
        if out:
            break
    return out


def fetch(start: date, end: date, journals: Sequence[JournalSpec]) -> Iterator[ArticleRecord]:
    seen: set[str] = set()
    page_ok = rss_ok = crossref_ok = 0

    for spec in journals:
        records: list[ArticleRecord] = []
        try:
            records = _page_records(spec, start, end)
            if records:
                page_ok += 1
        except requests.RequestException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            print(f"[sciencedirect] page warning: {spec.journal}: HTTP {status}")

        if not records:
            for rss_url in _discover_rss_urls(spec):
                try:
                    records = list(fetch_rss(
                        "sciencedirect", "Elsevier", spec, rss_url, start, end,
                        "ScienceDirect RSS + verified online date",
                    ))
                except Exception as exc:
                    print(f"[sciencedirect] RSS warning: {spec.journal}: {type(exc).__name__}")
                    continue
                if records:
                    rss_ok += 1
                    break

        if not records and ENABLE_CROSSREF_FALLBACK:
            try:
                records = list(crossref.fetch("sciencedirect", "Elsevier", start, end, [spec]))
                if records:
                    crossref_ok += 1
            except Exception as exc:
                print(f"[sciencedirect] Crossref warning: {spec.journal}: {type(exc).__name__}: {exc}")
                records = []

        for record in records:
            key = record.doi or record.external_id or record.title.lower()
            if not key or key in seen:
                continue
            seen.add(key)
            yield record

    print(
        f"[sciencedirect] sources: page_journals={page_ok}, rss_journals={rss_ok}, "
        f"crossref_journals={crossref_ok}, records={len(seen)}"
    )

from __future__ import annotations

from datetime import date
from typing import Iterator
from xml.etree import ElementTree as ET

import requests

from ..config import HTTP_TIMEOUT
from ..journals import JournalSpec, display_issn
from ..utils import build_session, normalize_space
from .base import ArticleRecord
from .enrichment import extract_doi, page_metadata, resolve_crossref


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _child_text(node, names):
    wanted = {x.lower() for x in names}
    for child in list(node):
        if _local(child.tag) in wanted:
            return normalize_space("".join(child.itertext()))
    return ""


def _entry_link(node):
    for child in list(node):
        if _local(child.tag) == "link":
            href = normalize_space(child.attrib.get("href") or "")
            if href:
                return href
            text = normalize_space("".join(child.itertext()))
            if text:
                return text
    return ""


def parse_feed(content: bytes):
    root = ET.fromstring(content)
    nodes = [n for n in root.iter() if _local(n.tag) in {"item", "entry"}]
    out = []
    for node in nodes:
        out.append({
            "title": _child_text(node, ["title"]),
            "link": _entry_link(node),
            "id": _child_text(node, ["guid", "id"]),
            "summary": _child_text(node, ["description", "summary", "content"]),
            "published": _child_text(node, ["pubDate", "published", "updated", "date"]),
        })
    return out


def fetch_rss(
    provider: str,
    publisher: str,
    spec: JournalSpec,
    url: str,
    start: date,
    end: date,
    source_label: str,
    *,
    allow_pending: bool = False,
) -> Iterator[ArticleRecord]:
    if not url:
        return
    session = build_session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*;q=0.8",
    })
    response = session.get(url, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    entries = parse_feed(response.content)
    if not entries:
        raise RuntimeError("RSS/Atom feed contains no item/entry records")

    seen = set()
    for entry in entries:
        title = normalize_space(entry.get("title") or "")
        link = normalize_space(entry.get("link") or "")
        summary = normalize_space(entry.get("summary") or "")
        ident = normalize_space(entry.get("id") or "")
        if not title:
            continue
        doi = extract_doi(" ".join([link, summary, ident]))
        page = {}
        if link:
            try:
                page = page_metadata(link)
            except requests.RequestException:
                page = {}
        doi = page.get("doi") or doi
        try:
            cr = resolve_crossref(title, spec, doi)
        except requests.RequestException:
            cr = {}
        doi = doi or cr.get("doi")
        online = page.get("online_date") or cr.get("online_date")
        raw = page.get("online_raw") or cr.get("online_raw") or ""
        precision = page.get("precision") or cr.get("precision") or "unknown"

        # Feed timestamps are discovery timestamps only; never promote them to online_date.
        if online and not (start <= online <= end):
            continue
        if not online and (not allow_pending or not doi):
            continue

        key = doi or ident or title.lower()
        if key in seen:
            continue
        seen.add(key)
        yield ArticleRecord(
            provider=provider,
            publisher=publisher,
            title=page.get("title") or title,
            journal=spec.journal,
            authors=page.get("authors") or cr.get("authors") or "",
            doi=doi,
            external_id=ident or link,
            issn=display_issn(spec.issns[0]) if spec.issns else "",
            content_type="Journal Article",
            url=page.get("url") or link or cr.get("url") or "",
            online_date=online,
            online_date_raw=raw,
            date_precision=precision,
            online_date_source=(source_label if online else f"{source_label}; awaiting published-online"),
            source_update_date=online,
            status="published" if online else "pending",
        )

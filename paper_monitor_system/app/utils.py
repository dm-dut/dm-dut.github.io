from __future__ import annotations

import hashlib
import re
import time
from datetime import date, datetime
from typing import Any, Iterable

import requests
from dateutil import parser as dtparser
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import HTTP_RETRY_BACKOFF, HTTP_RETRY_TOTAL, HTTP_TIMEOUT, REQUEST_PAUSE_SECONDS


def build_session() -> requests.Session:
    retry = Retry(
        total=max(0, HTTP_RETRY_TOTAL), connect=max(0, HTTP_RETRY_TOTAL), read=max(0, HTTP_RETRY_TOTAL),
        status=max(0, HTTP_RETRY_TOTAL), backoff_factor=max(0.0, HTTP_RETRY_BACKOFF),
        status_forcelist=(429, 500, 502, 503, 504), allowed_methods=frozenset(["GET"]),
        respect_retry_after_header=True,
    )
    s = requests.Session()
    s.headers.update({"User-Agent": "dm-dut-paper-monitor/6.0 (publisher-id-first monitoring)"})
    adapter = HTTPAdapter(max_retries=retry, pool_connections=4, pool_maxsize=4)
    s.mount("https://", adapter); s.mount("http://", adapter)
    return s


def get_json(session: requests.Session, url: str, *, params=None, headers=None) -> dict[str, Any]:
    r = session.get(url, params=params, headers=headers, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    if REQUEST_PAUSE_SECONDS > 0:
        time.sleep(REQUEST_PAUSE_SECONDS)
    return r.json()


def clean_doi(value: str | None) -> str | None:
    if not value:
        return None
    v = str(value).strip()
    v = re.sub(r"^https?://(dx\.)?doi\.org/", "", v, flags=re.I)
    v = re.sub(r"^doi:\s*", "", v, flags=re.I).strip().lower()
    return v or None


def first_nonempty(*values):
    for v in values:
        if v not in (None, "", [], {}):
            return v
    return None


def normalize_space(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def title_key(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalize_space(value).lower())


def identity_key(provider: str, doi: str | None, external_id: str | None, title: str) -> str:
    if external_id:
        raw = f"{provider}:id:{external_id.strip().lower()}"
    elif doi:
        raw = f"doi:{clean_doi(doi)}"
    else:
        raw = f"{provider}:title:{normalize_space(title).lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def parse_publisher_day(raw: str | None) -> date | None:
    if not raw:
        return None
    text = normalize_space(raw)
    for fmt in ("%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    try:
        dt = dtparser.parse(text, fuzzy=True, dayfirst=True)
    except Exception:
        return None
    if not re.search(r"\b(?:[1-9]|[12]\d|3[01])\b", text):
        return None
    return dt.date()


def parse_month_year(raw: str | None) -> tuple[str, str] | tuple[None, None]:
    if not raw:
        return None, None
    text = normalize_space(raw)
    months = (
        "January|February|March|April|May|June|July|August|September|October|November|December|"
        "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
    )
    m = re.search(rf"\b({months})\s+(20\d{{2}})\b", text, flags=re.I)
    if not m:
        return None, None
    for fmt in ("%B %Y", "%b %Y"):
        try:
            dt = datetime.strptime(f"{m.group(1)} {m.group(2)}", fmt)
            return dt.strftime("%Y-%m"), dt.strftime("%B %Y")
        except ValueError:
            pass
    return None, None


def join_authors(items: Any) -> str:
    if not items:
        return ""
    if isinstance(items, str):
        return normalize_space(items)
    names: list[str] = []
    if isinstance(items, dict):
        items = [items]
    if isinstance(items, Iterable):
        for item in items:
            if isinstance(item, str):
                name = normalize_space(item)
            elif isinstance(item, dict):
                name = normalize_space(str(first_nonempty(
                    item.get("full_name"), item.get("creator"), item.get("$"), item.get("name")
                ) or ""))
            else:
                name = ""
            if name and name not in names:
                names.append(name)
    return "; ".join(names)

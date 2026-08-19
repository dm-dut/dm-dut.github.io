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
        total=max(0, HTTP_RETRY_TOTAL),
        connect=max(0, HTTP_RETRY_TOTAL),
        read=max(0, HTTP_RETRY_TOTAL),
        status=max(0, HTTP_RETRY_TOTAL),
        backoff_factor=max(0.0, HTTP_RETRY_BACKOFF),
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        respect_retry_after_header=True,
    )
    s = requests.Session()
    s.headers.update({"User-Agent": "dm-dut-paper-monitor/3.0 (metadata monitoring)"})
    adapter = HTTPAdapter(max_retries=retry, pool_connections=8, pool_maxsize=8)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
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
    v = value.strip()
    v = re.sub(r"^https?://(dx\.)?doi\.org/", "", v, flags=re.I)
    v = re.sub(r"^doi:\s*", "", v, flags=re.I)
    v = v.strip().lower()
    return v or None


def first_nonempty(*values):
    for v in values:
        if v not in (None, "", [], {}):
            return v
    return None


def normalize_space(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()


def identity_key(provider: str, doi: str | None, external_id: str | None, title: str) -> str:
    if doi:
        raw = f"doi:{clean_doi(doi)}"
    elif external_id:
        raw = f"{provider}:{external_id.strip().lower()}"
    else:
        raw = f"{provider}:title:{normalize_space(title).lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def parse_flexible_date(raw: str | None, fallback: date | None = None) -> tuple[date | None, str]:
    if not raw:
        return (fallback, "fallback" if fallback else "unknown")
    text = normalize_space(raw)
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date(), "day"
        except ValueError:
            pass
    if re.fullmatch(r"\d{4}-\d{2}", text):
        y, m = map(int, text.split("-"))
        return date(y, m, 1), "month"
    m = re.search(r"(?:Q|Quarter\s*)([1-4])\D*(\d{4})", text, re.I)
    if not m:
        m = re.search(r"([1-4])(?:st|nd|rd|th)?\s+Quarter\D*(\d{4})", text, re.I)
    if m:
        q, y = int(m.group(1)), int(m.group(2))
        return date(y, 1 + (q - 1) * 3, 1), "quarter"
    if re.fullmatch(r"\d{4}", text):
        return date(int(text), 1, 1), "year"
    try:
        dt = dtparser.parse(text, fuzzy=True, default=datetime(1900, 1, 1))
        has_day = bool(re.search(r"\b([0-2]?\d|3[01])\b", text))
        if has_day:
            return dt.date(), "day"
        if re.search(r"[A-Za-z]{3,9}", text):
            return date(dt.year, dt.month, 1), "month"
        return dt.date(), "day"
    except Exception:
        return (fallback, "fallback" if fallback else "unknown")


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
                names.append(normalize_space(item))
            elif isinstance(item, dict):
                name = first_nonempty(item.get("full_name"), item.get("creator"), item.get("$"), item.get("name"))
                if name:
                    names.append(normalize_space(str(name)))
    return "; ".join(n for n in names if n)

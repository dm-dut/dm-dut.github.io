from __future__ import annotations

import hashlib
import re
import time
from datetime import date
from email.utils import parsedate_to_datetime
from typing import Any


def normalize_space(value: Any) -> str:
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def normalize_doi(value: Any) -> str:
    text = normalize_space(value).lower()
    text = re.sub(r'^https?://(?:dx\.)?doi\.org/', '', text)
    text = re.sub(r'^doi:\s*', '', text)
    return text.strip().rstrip('.,;')


def identity_key(doi: str, title: str, journal: str) -> str:
    doi = normalize_doi(doi)
    if doi:
        raw = f'doi:{doi}'
    else:
        raw = f"title:{normalize_space(title).lower()}|journal:{normalize_space(journal).lower()}"
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def date_parts(value: Any) -> date | None:
    if not isinstance(value, dict):
        return None
    parts = value.get('date-parts')
    if not parts or not isinstance(parts, list) or not parts[0]:
        return None
    row = parts[0]
    try:
        year = int(row[0])
        month = int(row[1]) if len(row) > 1 else 1
        day = int(row[2]) if len(row) > 2 else 1
        return date(year, month, day)
    except Exception:
        return None


def parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except Exception:
        return None


def first_text(value: Any) -> str:
    if isinstance(value, list):
        return normalize_space(value[0] if value else '')
    return normalize_space(value)


def authors_text(author_list: Any) -> str:
    if not isinstance(author_list, list):
        return ''
    names = []
    for author in author_list:
        if not isinstance(author, dict):
            continue
        literal = normalize_space(author.get('name'))
        if literal:
            names.append(literal)
            continue
        given = normalize_space(author.get('given'))
        family = normalize_space(author.get('family'))
        name = normalize_space(f'{given} {family}')
        if name:
            names.append(name)
    return ', '.join(names)


def polite_sleep(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)

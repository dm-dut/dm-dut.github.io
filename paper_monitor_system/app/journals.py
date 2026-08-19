from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Sequence

from openpyxl import load_workbook

from .config import CROSSREF_MEMBERS, JOURNAL_LIST_PATH, PROVIDER_LABELS, WHITELIST_REQUIRED
from .utils import normalize_space

_PROVIDER_ALIASES = {
    'elsevier':'sciencedirect','sciencedirect':'sciencedirect','science direct':'sciencedirect',
    'springer':'springer','springer nature':'springer','springernature':'springer',
    'ieee':'ieee','ieee xplore':'ieee',
}


@dataclass(frozen=True)
class JournalSpec:
    provider: str
    publisher: str
    journal: str
    issns: tuple[str, ...]
    aliases: tuple[str, ...]
    category: str
    crossref_member: int


def normalize_issn(value: str | None) -> str:
    return re.sub(r'[^0-9Xx]', '', str(value or '')).upper()


def _title_key(value: str | None) -> str:
    return re.sub(r'[^a-z0-9]+', '', normalize_space(value).lower())


def _truthy(value) -> bool:
    if isinstance(value, bool): return value
    if isinstance(value, (int,float)): return value != 0
    return str(value or '').strip().lower() in {'1','true','yes','y','on','enabled','是'}


def _header_key(value) -> str:
    return re.sub(r'[^a-z0-9]', '', str(value or '').lower())


def _split_aliases(value: str | None) -> tuple[str,...]:
    if not value: return ()
    return tuple(x for x in (normalize_space(v) for v in re.split(r'[;|\n]', str(value))) if x)


@lru_cache(maxsize=1)
def load_journal_list(path: str | Path | None = None) -> tuple[JournalSpec,...]:
    target = Path(path or JOURNAL_LIST_PATH)
    if not target.exists():
        if WHITELIST_REQUIRED: raise FileNotFoundError(target)
        return ()
    wb = load_workbook(target, read_only=True, data_only=True)
    ws = wb['Journals'] if 'Journals' in wb.sheetnames else wb[wb.sheetnames[0]]
    rows = ws.iter_rows(values_only=True)
    header = next(rows)
    col = {_header_key(v):i for i,v in enumerate(header)}
    def val(row,*names):
        for n in names:
            idx=col.get(_header_key(n))
            if idx is not None and idx < len(row) and row[idx] not in (None,''):
                return row[idx]
        return ''
    specs=[]
    for row in rows:
        if not _truthy(val(row,'Enabled','Active')): continue
        pub_raw=normalize_space(val(row,'Publisher','Provider','Source')).lower()
        provider=_PROVIDER_ALIASES.get(pub_raw,pub_raw)
        if provider not in PROVIDER_LABELS: raise ValueError(f'Unsupported publisher: {pub_raw}')
        journal=normalize_space(val(row,'Journal','Journal Title','Title'))
        issns=[]
        for raw in (val(row,'ISSN','Print ISSN'),val(row,'eISSN','Electronic ISSN','Online ISSN')):
            for part in re.split(r'[,;/|\n]', str(raw or '')):
                n=normalize_issn(part)
                if len(n)==8 and n not in issns: issns.append(n)
        member_raw=val(row,'Crossref Member','CrossrefMember','Member')
        try: member=int(float(member_raw)) if member_raw not in (None,'') else CROSSREF_MEMBERS[provider]
        except Exception: member=CROSSREF_MEMBERS[provider]
        specs.append(JournalSpec(provider,PROVIDER_LABELS[provider],journal,tuple(issns),_split_aliases(val(row,'Aliases','Alias')),normalize_space(val(row,'Category')),member))
    return tuple(specs)


def enabled_journals(provider: str) -> tuple[JournalSpec,...]:
    p=_PROVIDER_ALIASES.get(provider.lower(),provider.lower())
    return tuple(s for s in load_journal_list() if s.provider==p)


def extract_issns(value) -> set[str]:
    if isinstance(value,list):
        out=set()
        for v in value: out |= extract_issns(v)
        return out
    text=str(value or '')
    hits=re.findall(r'\b\d{4}-?\d{3}[\dXx]\b',text)
    return {normalize_issn(v) for v in hits if len(normalize_issn(v))==8}


def match_journal(provider: str, journal: str | None, issn, specs: Sequence[JournalSpec] | None=None) -> JournalSpec | None:
    candidates=tuple(specs) if specs is not None else enabled_journals(provider)
    rec_issns=extract_issns(issn)
    if rec_issns:
        for s in candidates:
            if rec_issns.intersection(s.issns): return s
    key=_title_key(journal)
    if key:
        for s in candidates:
            if key in {_title_key(x) for x in (s.journal,*s.aliases) if x}: return s
    return None

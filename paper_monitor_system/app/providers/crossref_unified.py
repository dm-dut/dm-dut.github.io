from __future__ import annotations

from datetime import date
from time import perf_counter
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..config import (
    CROSSREF_API, CROSSREF_MAILTO, CROSSREF_MAX_PAGES, CROSSREF_ROWS,
    HTTP_RETRY_BACKOFF, HTTP_RETRY_TOTAL, HTTP_TIMEOUT, REQUEST_PAUSE_SECONDS,
)
from ..journals import JournalSpec, match_journal
from ..utils import authors_text, date_parts, first_text, identity_key, normalize_doi, polite_sleep

SELECT_FIELDS = ','.join([
    'DOI','title','author','container-title','ISSN','published-online','published','issued',
    'published-print','created','indexed','URL','type','member','prefix','publisher'
])


def _session() -> requests.Session:
    retry = Retry(
        total=HTTP_RETRY_TOTAL,
        connect=HTTP_RETRY_TOTAL,
        read=HTTP_RETRY_TOTAL,
        status=HTTP_RETRY_TOTAL,
        backoff_factor=HTTP_RETRY_BACKOFF,
        status_forcelist=(429,500,502,503,504),
        allowed_methods=frozenset({'GET'}),
        respect_retry_after_header=True,
    )
    s=requests.Session()
    s.mount('https://',HTTPAdapter(max_retries=retry))
    s.headers.update({'User-Agent': f'PaperMonitorV4/1.0 ({CROSSREF_MAILTO or "local-user"})','Accept':'application/json'})
    return s


def _best_date(item: dict) -> tuple[date | None, str]:
    for field,label in (
        ('published-online','Crossref published-online'),
        ('published','Crossref published'),
        ('issued','Crossref issued'),
        ('published-print','Crossref published-print'),
    ):
        d=date_parts(item.get(field))
        if d: return d,label
    return None,''


def _record(item: dict, provider: str, spec: JournalSpec, discovered_via: str) -> dict | None:
    title=first_text(item.get('title'))
    if not title: return None
    d,date_source=_best_date(item)
    if not d: return None
    doi=normalize_doi(item.get('DOI'))
    journal=spec.journal
    url=f'https://doi.org/{doi}' if doi else first_text(item.get('URL'))
    issns=','.join(item.get('ISSN') or []) if isinstance(item.get('ISSN'),list) else str(item.get('ISSN') or '')
    return {
        'identity_key': identity_key(doi,title,journal),
        'provider': provider,
        'publisher': spec.publisher,
        'title': title,
        'journal': journal,
        'authors': authors_text(item.get('author')),
        'doi': doi or None,
        'issn': issns,
        'content_type': item.get('type') or 'journal-article',
        'url': url,
        'online_date': d,
        'date_source': date_source,
        'discovered_via': discovered_via,
    }


def _batch(provider: str, member: int, specs: tuple[JournalSpec,...], start: date, end: date, mode: str) -> tuple[list[dict],dict]:
    if mode=='pub':
        filter_value=f'type:journal-article,from-pub-date:{start.isoformat()},until-pub-date:{end.isoformat()}'
        label='pub-date'
    else:
        filter_value=f'type:journal-article,from-index-date:{start.isoformat()},until-index-date:{end.isoformat()}'
        label='index-date'
    url=f'{CROSSREF_API}/members/{member}/works'
    cursor='*'
    page=0
    raw=0
    matched=0
    records=[]
    seen=set()
    s=_session()
    t0=perf_counter()
    while page < CROSSREF_MAX_PAGES:
        page += 1
        params={'filter':filter_value,'rows':CROSSREF_ROWS,'cursor':cursor,'select':SELECT_FIELDS}
        if CROSSREF_MAILTO: params['mailto']=CROSSREF_MAILTO
        r=s.get(url,params=params,timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        message=r.json().get('message',{})
        items=message.get('items') or []
        raw += len(items)
        page_matched=0
        for item in items:
            spec=match_journal(provider,first_text(item.get('container-title')),item.get('ISSN'),specs)
            if not spec: continue
            rec=_record(item,provider,spec,f'Crossref {label}')
            if not rec: continue
            key=rec['doi'] or rec['identity_key']
            if key in seen: continue
            seen.add(key)
            records.append(rec)
            matched += 1
            page_matched += 1
        print(f'[{provider}] {label} page={page}, raw={len(items)}, whitelist={page_matched}, total_match={matched}')
        next_cursor=message.get('next-cursor')
        if not items or not next_cursor or len(items) < CROSSREF_ROWS: break
        cursor=next_cursor
        polite_sleep(REQUEST_PAUSE_SECONDS)
    return records, {'mode':label,'pages':page,'raw':raw,'matched':matched,'elapsed':perf_counter()-t0}


def fetch_provider(provider: str, journals: tuple[JournalSpec,...], start: date, end: date) -> tuple[list[dict],dict]:
    members={j.crossref_member for j in journals}
    if len(members)!=1:
        raise ValueError(f'{provider}: expected one Crossref member, got {sorted(members)}')
    member=next(iter(members))
    print(f'[{provider}] Crossref member={member}, journals={len(journals)}, window={start}..{end}')
    pub_records,pub_stats=_batch(provider,member,journals,start,end,'pub')
    index_records,index_stats=_batch(provider,member,journals,start,end,'index')
    merged={}
    # pub-date pass wins ties; index pass supplements late metadata.
    for rec in index_records:
        merged[rec['doi'] or rec['identity_key']]=rec
    for rec in pub_records:
        merged[rec['doi'] or rec['identity_key']]=rec
    stats={
        'member':member,
        'pub':pub_stats,
        'index':index_stats,
        'unique':len(merged),
        'requests':pub_stats['pages']+index_stats['pages'],
    }
    return list(merged.values()),stats

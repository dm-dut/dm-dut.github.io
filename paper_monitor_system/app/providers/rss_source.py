from __future__ import annotations
from datetime import date
from typing import Iterator
from xml.etree import ElementTree as ET
import requests
from ..config import HTTP_TIMEOUT
from ..journals import JournalSpec,display_issn
from ..utils import build_session,normalize_space
from .base import ArticleRecord
from .enrichment import extract_doi,page_metadata,resolve_crossref

def _local(tag:str)->str:
    return tag.rsplit('}',1)[-1].lower()

def _child_text(node,names):
    wanted={x.lower() for x in names}
    for c in list(node):
        if _local(c.tag) in wanted:
            return normalize_space(''.join(c.itertext()))
    return ''

def _entry_link(node):
    for c in list(node):
        if _local(c.tag)=='link':
            href=normalize_space(c.attrib.get('href') or '')
            if href:return href
            text=normalize_space(''.join(c.itertext()))
            if text:return text
    return ''

def parse_feed(content:bytes):
    root=ET.fromstring(content)
    nodes=[n for n in root.iter() if _local(n.tag) in {'item','entry'}]
    out=[]
    for n in nodes:
        out.append({
            'title':_child_text(n,['title']),
            'link':_entry_link(n),
            'id':_child_text(n,['guid','id']),
            'summary':_child_text(n,['description','summary','content']),
            'published':_child_text(n,['pubDate','published','updated','date']),
        })
    return out

def fetch_rss(provider:str,publisher:str,spec:JournalSpec,url:str,start:date,end:date,source_label:str)->Iterator[ArticleRecord]:
    if not url:return
    s=build_session();s.headers.update({'User-Agent':'Mozilla/5.0 paper-monitor/2.0'})
    r=s.get(url,timeout=HTTP_TIMEOUT);r.raise_for_status()
    entries=parse_feed(r.content)
    if not entries:raise RuntimeError('RSS/Atom feed contains no item/entry records')
    seen=set()
    for e in entries:
        title=normalize_space(e.get('title') or '');link=normalize_space(e.get('link') or '');summary=normalize_space(e.get('summary') or '');ident=normalize_space(e.get('id') or '')
        if not title:continue
        doi=extract_doi(' '.join([link,summary,ident]))
        page={}
        if link:
            try:page=page_metadata(link)
            except requests.RequestException:page={}
        doi=page.get('doi') or doi
        cr=resolve_crossref(title,spec,doi)
        online=page.get('online_date') or cr.get('online_date')
        raw=page.get('online_raw') or cr.get('online_raw') or ''
        precision=page.get('precision') or cr.get('precision') or 'unknown'
        # Feed timestamps are intentionally NOT treated as Online dates.
        if not online or online<start or online>end:continue
        key=doi or ident or title.lower()
        if key in seen:continue
        seen.add(key)
        yield ArticleRecord(provider=provider,publisher=publisher,title=page.get('title') or title,journal=spec.journal,
            authors=page.get('authors') or cr.get('authors') or '',doi=doi or cr.get('doi'),external_id=ident or link,
            issn=display_issn(spec.issns[0]) if spec.issns else '',content_type='Journal Article',url=page.get('url') or link or cr.get('url') or '',
            online_date=online,online_date_raw=raw,date_precision=precision,online_date_source=source_label,source_update_date=online)

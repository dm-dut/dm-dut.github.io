from __future__ import annotations
import json,re
from datetime import date
from difflib import SequenceMatcher
from bs4 import BeautifulSoup
from ..config import CROSSREF_MAILTO,HTTP_TIMEOUT
from ..journals import JournalSpec,extract_issns
from ..utils import build_session,clean_doi,normalize_space,parse_flexible_date
CROSSREF="https://api.crossref.org"
DOI_RE=re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+",re.I)
DATE_PATTERNS=[
    re.compile(r"Available online\s*[:]?\s*([0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})",re.I),
    re.compile(r"Date of Publication\s*[:]?\s*([A-Za-z]+\s+[0-9]{1,2},?\s+[0-9]{4}|[0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})",re.I),
    re.compile(r"Published(?: online)?\s*[:]?\s*([0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})",re.I),
]

def extract_doi(text):
    m=DOI_RE.search(str(text or "")); return clean_doi(m.group(0).rstrip(".,);]")) if m else None

def _cr_date(item):
    b=item.get("published-online") or {}; parts=(b.get("date-parts") or [[]])[0]
    if not parts:return None,"unknown",""
    try:
        y=int(parts[0]);m=int(parts[1]) if len(parts)>1 else 1;d=int(parts[2]) if len(parts)>2 else 1
        p="day" if len(parts)>2 else ("month" if len(parts)>1 else "year")
        raw=f"{y:04d}-{m:02d}-{d:02d}" if p=="day" else (f"{y:04d}-{m:02d}" if p=="month" else f"{y:04d}")
        return date(y,m,d),p,raw
    except Exception:return None,"unknown",""

def crossref_by_doi(doi):
    doi=clean_doi(doi)
    if not doi:return None
    s=build_session();params={"mailto":CROSSREF_MAILTO} if CROSSREF_MAILTO else None
    r=s.get(f"{CROSSREF}/works/{doi}",params=params,timeout=HTTP_TIMEOUT)
    if r.status_code!=200:return None
    return r.json().get("message") or {}

def crossref_by_title(title,spec):
    if not title:return None
    s=build_session();params={"query.title":title,"rows":5,"select":"DOI,title,author,container-title,ISSN,published-online,URL"}
    if CROSSREF_MAILTO:params["mailto"]=CROSSREF_MAILTO
    r=s.get(f"{CROSSREF}/works",params=params,timeout=HTTP_TIMEOUT)
    if r.status_code!=200:return None
    best=None;score=0.0
    for item in (r.json().get("message") or {}).get("items") or []:
        it=((item.get("title") or [""])[0] or "")
        sim=SequenceMatcher(None,normalize_space(title).lower(),normalize_space(it).lower()).ratio()
        item_issns=set()
        for x in item.get("ISSN") or []:item_issns|=extract_issns(x)
        if spec.issns and item_issns and not item_issns.intersection(spec.issns):sim-=0.25
        if sim>score:score=sim;best=item
    return best if score>=0.72 else None

def resolve_crossref(title,spec,doi=None):
    item=crossref_by_doi(doi) or crossref_by_title(title,spec)
    if not item:return {}
    online,precision,raw=_cr_date(item);authors=[]
    for a in item.get("author") or []:
        n=normalize_space(f"{a.get('given','')} {a.get('family','')}")
        if n:authors.append(n)
    container=(item.get("container-title") or [""])
    journal=normalize_space(container[0] if isinstance(container,list) and container else container)
    issns="; ".join(normalize_space(str(x)) for x in (item.get("ISSN") or []) if x)
    return {
        "doi":clean_doi(item.get("DOI")),
        "online_date":online,
        "online_raw":raw,
        "precision":precision,
        "authors":"; ".join(authors),
        "url":normalize_space(item.get("URL") or ""),
        "journal":journal,
        "issn":issns,
    }

def _jsonld_date(soup):
    for tag in soup.find_all("script",attrs={"type":"application/ld+json"}):
        try:data=json.loads(tag.string or tag.get_text() or "")
        except Exception:continue
        stack=data if isinstance(data,list) else [data]
        for obj in stack:
            if isinstance(obj,dict) and obj.get("datePublished"):
                return normalize_space(str(obj.get("datePublished")))
    return ""

def page_metadata(url):
    if not url:return {}
    s=build_session();s.headers.update({"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36","Accept-Language":"en-US,en;q=0.9"})
    r=s.get(url,timeout=HTTP_TIMEOUT);r.raise_for_status();soup=BeautifulSoup(r.text,"html.parser")
    def meta(*names):
        for name in names:
            tag=soup.find("meta",attrs={"name":name}) or soup.find("meta",attrs={"property":name})
            if tag and tag.get("content"):return normalize_space(tag.get("content"))
        return ""
    title=meta("citation_title","dc.title","og:title")
    doi=clean_doi(meta("citation_doi","dc.identifier")) or extract_doi(r.text)
    journal=meta("citation_journal_title","prism.publicationName")
    issn=meta("citation_issn","prism.issn")
    raw=meta("citation_online_date")
    if not raw:
        text=normalize_space(soup.get_text(" ",strip=True))
        for pat in DATE_PATTERNS:
            m=pat.search(text)
            if m:
                raw=m.group(1)
                break
    # JSON-LD datePublished is useful when the page exposes no dedicated
    # Online/Available-online label, but it is deliberately lower priority.
    if not raw:
        raw=_jsonld_date(soup)
    online,precision=parse_flexible_date(raw) if raw else (None,"unknown")
    authors=[normalize_space(x.get("content")) for x in soup.find_all("meta",attrs={"name":"citation_author"}) if x.get("content")]
    return {"title":title,"doi":doi,"journal":journal,"issn":issn,"online_date":online,"online_raw":raw,"precision":precision,"authors":"; ".join(authors),"url":r.url}

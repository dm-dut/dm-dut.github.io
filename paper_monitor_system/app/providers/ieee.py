from __future__ import annotations

import re
from datetime import date
from time import perf_counter
from typing import Iterator, Sequence

from ..config import BROWSER_JOURNAL_DELAY_MS, BROWSER_KNOWN_STREAK_STOP, BROWSER_MAX_RESULTS
from ..journals import JournalSpec
from ..utils import normalize_space
from .base import ArticleRecord
from .browser import BrowserRuntime

DOC_RE = re.compile(r"/document/(\d+)", re.I)

_SEARCH_JS = r'''els => {
  const bad = /^(pdf|abstract|full text|html|view|download|early access)$/i;
  const out = [];
  for (const a of els) {
    const href = a.href || '';
    const m = href.match(/\/document\/(\d+)/i);
    if (!m) continue;
    const card = a.closest('xpl-toc-item, article, li, .List-results-items, [class*="result-item"], [class*="List-results"]') || a.parentElement?.parentElement || a.parentElement;
    const anchors = card ? [...card.querySelectorAll('a[href*="/document/"]')] : [a];
    const titleChoices = anchors.map(x => (x.innerText || x.textContent || '').trim())
      .filter(x => x.length > 5 && !bad.test(x));
    const title = titleChoices.sort((x,y) => y.length-x.length)[0] || (a.innerText || a.textContent || '').trim();
    const authorNodes = card ? [...card.querySelectorAll('.authors-info, .authors, [class*="authors"], [class*="author"], a[href*="/author/"]')] : [];
    const authorTexts = authorNodes.map(x => (x.innerText || x.textContent || '').trim()).filter(Boolean);
    const authors = [...new Set(authorTexts)].sort((x,y)=>y.length-x.length)[0] || '';
    out.push({href, title, authors});
  }
  return out;
}'''


def _search_candidates(page, max_results: int = BROWSER_MAX_RESULTS) -> list[dict]:
    rows = page.eval_on_selector_all('a[href*="/document/"]', _SEARCH_JS)
    by_id: dict[str, dict] = {}; order: list[str] = []
    for row in rows:
        href = str(row.get("href") or "")
        m = DOC_RE.search(href)
        if not m:
            continue
        doc_id = m.group(1)
        title = normalize_space(row.get("title") or row.get("text") or "")
        authors = normalize_space(row.get("authors") or "")
        if doc_id not in by_id:
            order.append(doc_id)
            by_id[doc_id] = {
                "external_id": doc_id, "url": f"https://ieeexplore.ieee.org/document/{doc_id}/",
                "title": title, "authors": authors,
            }
        else:
            if len(title) > len(by_id[doc_id].get("title", "")):
                by_id[doc_id]["title"] = title
            if len(authors) > len(by_id[doc_id].get("authors", "")):
                by_id[doc_id]["authors"] = authors
    return [by_id[k] for k in order[:max_results]]


def fetch(start: date, end: date, journals: Sequence[JournalSpec], known_ids: set[str] | None = None) -> Iterator[ArticleRecord]:
    # start/end are deliberately ignored: IEEE is incremental by Document ID.
    known = set(known_ids or set())
    t0 = perf_counter(); accepted_total = 0
    with BrowserRuntime() as browser:
        page = browser.new_page()
        for idx, spec in enumerate(journals, start=1):
            jt0 = perf_counter()
            print(f"[ieee] early-access list {idx}/{len(journals)}: {spec.journal}")
            try:
                browser.goto(page, spec.search_url, label="IEEE Early Access")
                try:
                    page.wait_for_selector('a[href*="/document/"]', timeout=15000)
                except Exception:
                    pass
                candidates = _search_candidates(page)
            except Exception as exc:
                print(f"[ieee] warning: {spec.journal}: {type(exc).__name__}: {exc}")
                continue
            print(f"[ieee] candidates={len(candidates)}")
            known_streak = accepted_journal = 0
            for rank, c in enumerate(candidates, start=1):
                external_id = c["external_id"]
                if external_id in known:
                    known_streak += 1
                    if known_streak >= max(1, BROWSER_KNOWN_STREAK_STOP):
                        print(f"[ieee] stop: {known_streak} consecutive known Document IDs")
                        break
                    continue
                known_streak = 0
                if not c.get("title"):
                    print(f"[ieee] skip {external_id}: missing title on list page")
                    continue
                rec = ArticleRecord(
                    provider="ieee", publisher="IEEE", journal=spec.journal,
                    title=c["title"], authors=c.get("authors") or "", external_id=external_id,
                    url=c.get("url") or "", source_rank=rank,
                    issn=spec.issns[-1] if spec.issns else "",
                    date_source="IEEE Xplore Early Access list order",
                )
                accepted_journal += 1; accepted_total += 1; known.add(external_id)
                print(f"[ieee] new Document ID rank={rank}: {rec.title[:90]}")
                yield rec
            print(f"[ieee] journal done: new={accepted_journal}, elapsed={perf_counter()-jt0:.1f}s")
            if BROWSER_JOURNAL_DELAY_MS > 0:
                page.wait_for_timeout(BROWSER_JOURNAL_DELAY_MS)
        page.close()
    print(f"[ieee] done: new records={accepted_total}, elapsed={perf_counter()-t0:.1f}s")

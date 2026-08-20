from __future__ import annotations

import re
from datetime import date
from time import perf_counter
from typing import Iterator, Sequence

from ..config import BROWSER_JOURNAL_DELAY_MS, BROWSER_KNOWN_STREAK_STOP, BROWSER_MAX_RESULTS
from ..journals import JournalSpec
from ..utils import normalize_space, parse_month_year, parse_publisher_day
from .base import ArticleRecord
from .browser import BrowserRuntime

PII_RE = re.compile(r"/science/article/pii/([A-Za-z0-9]+)", re.I)
AVAILABLE_RE = re.compile(r"Available online\s+([0-3]?\d\s+[A-Za-z]+\s+\d{4})", re.I)

_SEARCH_JS = r'''els => {
  const bad = /^(view|download|pdf|abstract|full text|open access|show more|read more)$/i;
  const out = [];
  for (const a of els) {
    const href = a.href || '';
    const m = href.match(/\/science\/article\/pii\/([A-Za-z0-9]+)/i);
    if (!m) continue;
    const card = a.closest('[data-aa-name="srp-result-item"], article, li, .ResultItem, [class*="result-item"], [class*="ResultItem"]') || a.parentElement?.parentElement || a.parentElement;
    const anchors = card ? [...card.querySelectorAll('a[href*="/science/article/pii/"]')] : [a];
    const titleChoices = anchors.map(x => (x.innerText || x.textContent || '').trim())
      .filter(x => x.length > 5 && !bad.test(x));
    const title = titleChoices.sort((x,y) => y.length-x.length)[0] || (a.innerText || a.textContent || '').trim();
    const authorNodes = card ? [...card.querySelectorAll('.Authors, .authors, [class*="Authors"], [class*="authors"], [class*="Author"], [class*="author"], a[href*="/author/"]')] : [];
    const authorTexts = authorNodes.map(x => (x.innerText || x.textContent || '').trim()).filter(Boolean);
    const authors = [...new Set(authorTexts)].sort((x,y)=>y.length-x.length)[0] || '';
    out.push({href, title, authors, card_text: card ? (card.innerText || card.textContent || '') : ''});
  }
  return out;
}'''


def _date_from_card(text: str) -> tuple[str, date | None, str, str, str]:
    text = normalize_space(text)
    m = AVAILABLE_RE.search(text)
    if m:
        raw = normalize_space(m.group(1))
        d = parse_publisher_day(raw)
        if d:
            return raw, d, "online", "day", "ScienceDirect search Available online"
    _, display = parse_month_year(text)
    if display:
        # Publication month/year is for display only, never treated as an online sort date.
        return display, None, "publication", "month", "ScienceDirect search publication month"
    return "", None, "", "", ""


def _search_candidates(page, max_results: int = BROWSER_MAX_RESULTS) -> list[dict]:
    rows = page.eval_on_selector_all('a[href*="/science/article/pii/"]', _SEARCH_JS)
    by_id: dict[str, dict] = {}
    order: list[str] = []
    for row in rows:
        href = str(row.get("href") or "")
        m = PII_RE.search(href)
        if not m:
            continue
        pii = m.group(1).upper()
        title = normalize_space(row.get("title") or row.get("text") or "")
        authors = normalize_space(row.get("authors") or "")
        display_date, sort_date, kind, precision, source = _date_from_card(row.get("card_text") or "")
        candidate = {
            "external_id": pii,
            "url": href.split("?")[0],
            "title": title,
            "authors": authors,
            "display_date": display_date,
            "sort_date": sort_date,
            "date_kind": kind,
            "date_precision": precision,
            "date_source": source,
        }
        if pii not in by_id:
            order.append(pii)
            by_id[pii] = candidate
        else:
            prev = by_id[pii]
            if len(title) > len(prev.get("title", "")):
                prev["title"] = title
            if len(authors) > len(prev.get("authors", "")):
                prev["authors"] = authors
            if not prev.get("display_date") and display_date:
                prev.update({
                    "display_date": display_date, "sort_date": sort_date, "date_kind": kind,
                    "date_precision": precision, "date_source": source,
                })
    return [by_id[k] for k in order[:max_results]]


def fetch(start: date, end: date, journals: Sequence[JournalSpec], known_ids: set[str] | None = None) -> Iterator[ArticleRecord]:
    # start/end are deliberately ignored: ScienceDirect is incremental by PII.
    known = {x.upper() for x in (known_ids or set())}
    t0 = perf_counter(); accepted_total = 0
    with BrowserRuntime() as browser:
        page = browser.new_page()
        for idx, spec in enumerate(journals, start=1):
            jt0 = perf_counter()
            print(f"[sciencedirect] search {idx}/{len(journals)}: {spec.journal}")
            try:
                browser.goto(page, spec.search_url, label="ScienceDirect search")
                try:
                    page.wait_for_selector('a[href*="/science/article/pii/"]', timeout=15000)
                except Exception:
                    pass
                candidates = _search_candidates(page)
            except Exception as exc:
                print(f"[sciencedirect] warning: {spec.journal}: {type(exc).__name__}: {exc}")
                continue
            print(f"[sciencedirect] candidates={len(candidates)}")
            known_streak = accepted_journal = 0
            for rank, c in enumerate(candidates, start=1):
                external_id = c["external_id"].upper()
                if external_id in known:
                    known_streak += 1
                    if known_streak >= max(1, BROWSER_KNOWN_STREAK_STOP):
                        print(f"[sciencedirect] stop: {known_streak} consecutive known PII values")
                        break
                    continue
                known_streak = 0
                if not c.get("title"):
                    print(f"[sciencedirect] skip {external_id}: missing title on search card")
                    continue
                rec = ArticleRecord(
                    provider="sciencedirect", publisher="Elsevier", journal=spec.journal,
                    title=c["title"], authors=c.get("authors") or "", external_id=external_id,
                    url=c.get("url") or "", display_date=c.get("display_date") or "",
                    sort_date=c.get("sort_date"), date_kind=c.get("date_kind") or "",
                    date_precision=c.get("date_precision") or "", date_source=c.get("date_source") or "",
                    source_rank=rank, issn=spec.issns[0] if spec.issns else "",
                )
                accepted_journal += 1; accepted_total += 1; known.add(external_id)
                print(f"[sciencedirect] new PII rank={rank}: {rec.display_date or '-'} | {rec.title[:90]}")
                yield rec
            print(f"[sciencedirect] journal done: new={accepted_journal}, elapsed={perf_counter()-jt0:.1f}s")
            if BROWSER_JOURNAL_DELAY_MS > 0:
                page.wait_for_timeout(BROWSER_JOURNAL_DELAY_MS)
        page.close()
    print(f"[sciencedirect] done: new records={accepted_total}, elapsed={perf_counter()-t0:.1f}s")

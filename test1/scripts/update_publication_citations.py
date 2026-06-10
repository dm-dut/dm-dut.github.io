#!/usr/bin/env python3
"""Update Google Scholar citation counts for publication records using SerpAPI.

Inputs:
  data/publications.json

Outputs:
  data/publications.json, with these extra fields for non-Chinese publications:
    google_scholar_citations
    google_scholar_url
    citation_updated
    citation_match_score

Notes:
- Chinese-language publications are intentionally skipped and will not display citation counts.
- Matching is title-based against the author's Google Scholar profile articles.
- Requires SERPAPI_KEY in the environment. Optional: SCHOLAR_AUTHOR_ID.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError as exc:
    raise SystemExit("Please install requests first: pip install requests") from exc

ROOT = Path(__file__).resolve().parents[1]
PUBS_JSON = ROOT / "data" / "publications.json"
AUTHOR_ID = os.getenv("SCHOLAR_AUTHOR_ID", "vBSJplMAAAAJ")
SERPAPI_URL = "https://serpapi.com/search.json"
MATCH_THRESHOLD = float(os.getenv("SCHOLAR_MATCH_THRESHOLD", "0.86"))
MAX_ARTICLES = int(os.getenv("SCHOLAR_MAX_ARTICLES", "500"))


def normalize_title(s: str) -> str:
    s = str(s or "").lower()
    s = re.sub(r"[\u2010-\u2015]", "-", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def similarity(a: str, b: str) -> float:
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    # Reward containment for titles where Scholar truncates subtitles.
    shorter, longer = sorted([na, nb], key=len)
    contain_score = len(shorter) / len(longer) if shorter in longer and longer else 0.0
    return max(SequenceMatcher(None, na, nb).ratio(), contain_score)


def is_chinese_publication(pub: dict[str, Any]) -> bool:
    lang = str(pub.get("language", "")).strip().lower()
    if lang.startswith("zh") or "中文" in lang or "chinese" == lang:
        return True
    # Conservative fallback for older JSON generated before language was stored.
    indexes = [str(x).upper() for x in pub.get("indexes", [])]
    venue = str(pub.get("venue", ""))
    if "CSSCI" in indexes:
        return True
    chinese_venues = ["Chinese Journal of Management Science", "Systems Engineering", "Journal of Systems Engineering"]
    return any(v.lower() == venue.lower() for v in chinese_venues)


def fetch_author_articles(api_key: str) -> list[dict[str, Any]]:
    articles: list[dict[str, Any]] = []
    start = 0
    page_size = 100
    while len(articles) < MAX_ARTICLES:
        params = {
            "engine": "google_scholar_author",
            "author_id": AUTHOR_ID,
            "hl": "en",
            "api_key": api_key,
            "num": page_size,
            "start": start,
        }
        response = requests.get(SERPAPI_URL, params=params, timeout=60)
        response.raise_for_status()
        payload = response.json()
        page_articles = payload.get("articles", []) or []
        if not page_articles:
            break
        articles.extend(page_articles)
        if len(page_articles) < page_size:
            break
        start += page_size
    return articles[:MAX_ARTICLES]


def best_match(pub: dict[str, Any], articles: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, float]:
    title = pub.get("title", "")
    best = None
    best_score = 0.0
    for article in articles:
        score = similarity(title, article.get("title", ""))
        if score > best_score:
            best_score = score
            best = article
    return best, best_score


def citation_value(article: dict[str, Any]) -> str:
    cited_by = article.get("cited_by") or {}
    value = cited_by.get("value", "") if isinstance(cited_by, dict) else ""
    return "" if value in (None, "") else str(value)


def article_link(article: dict[str, Any]) -> str:
    cited_by = article.get("cited_by") or {}
    if isinstance(cited_by, dict) and cited_by.get("link"):
        return str(cited_by.get("link"))
    return str(article.get("link", "") or "")


def main() -> None:
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        print("SERPAPI_KEY is not set; publication citation counts were not updated.", file=sys.stderr)
        return
    if not PUBS_JSON.exists():
        raise SystemExit(f"Missing {PUBS_JSON}")

    pubs = json.loads(PUBS_JSON.read_text(encoding="utf-8"))
    articles = fetch_author_articles(api_key)
    today = str(date.today())
    updated = matched = skipped = 0

    for pub in pubs:
        if is_chinese_publication(pub):
            for key in ["google_scholar_citations", "google_scholar_url", "citation_updated", "citation_match_score"]:
                pub.pop(key, None)
            pub["show_citations"] = False
            skipped += 1
            continue

        pub["show_citations"] = True
        article, score = best_match(pub, articles)
        if article and score >= MATCH_THRESHOLD:
            pub["google_scholar_citations"] = citation_value(article)
            pub["google_scholar_url"] = article_link(article)
            pub["citation_updated"] = today
            pub["citation_match_score"] = round(score, 3)
            matched += 1
        else:
            # Keep fields explicit so the webpage can simply hide empty values.
            pub["google_scholar_citations"] = ""
            pub["google_scholar_url"] = ""
            pub["citation_updated"] = today
            pub["citation_match_score"] = round(score, 3) if article else ""
        updated += 1

    PUBS_JSON.write_text(json.dumps(pubs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Updated publication citations: matched={matched}, non_chinese={updated}, chinese_skipped={skipped}, articles_fetched={len(articles)}")


if __name__ == "__main__":
    main()

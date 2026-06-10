#!/usr/bin/env python3
"""Update Google Scholar citation counts for publication records using SerpAPI.

This script updates both homepage-level Scholar metrics and per-publication
citation counts when used together with update_scholar.py in the workflow.

Inputs:
  data/publications.json

Outputs:
  data/publications.json, with these extra fields:
    google_scholar_citations
    google_scholar_url
    google_scholar_cited_by_url
    citation_updated
    citation_match_score

Matching strategy:
- Fetch the author's Google Scholar article list through SerpAPI.
- Match each local publication against Scholar records using both English and
  Chinese titles when available: title, title_en, title_zh/title_cn.
- Chinese-language publications are no longer skipped; they can display Google
  Scholar citations and BibTeX when a Scholar record is matched.

Requires SERPAPI_KEY in the environment. Optional: SCHOLAR_AUTHOR_ID.
"""
from __future__ import annotations

import json
import os
import re
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
PUBS_JSON = ROOT / "data" / "publications.json"
AUTHOR_ID = os.getenv("SCHOLAR_AUTHOR_ID", "vBSJplMAAAAJ")
SERPAPI_URL = "https://serpapi.com/search.json"
MATCH_THRESHOLD = float(os.getenv("SCHOLAR_MATCH_THRESHOLD", "0.75"))
MAX_ARTICLES = int(os.getenv("SCHOLAR_MAX_ARTICLES", "500"))
PAGE_SIZE = 100


def normalize_title(text: str) -> str:
    text = str(text or "").lower()
    text = re.sub(r"[\u2010-\u2015]", "-", text)
    text = text.replace("&", " and ")
    # Keep CJK characters so Chinese titles can be matched.
    text = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def similarity(a: str, b: str) -> float:
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    shorter, longer = sorted([na, nb], key=len)
    contain_score = len(shorter) / len(longer) if shorter in longer and longer else 0.0
    return max(SequenceMatcher(None, na, nb).ratio(), contain_score)


def title_candidates(pub: dict[str, Any]) -> list[str]:
    keys = ["title", "title_en", "title_english", "title_zh", "title_cn", "title_chinese"]
    seen: set[str] = set()
    out: list[str] = []
    for key in keys:
        value = str(pub.get(key, "") or "").strip()
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def fetch_author_articles(api_key: str) -> list[dict[str, Any]]:
    articles: list[dict[str, Any]] = []
    start = 0
    while len(articles) < MAX_ARTICLES:
        params = {
            "engine": "google_scholar_author",
            "author_id": AUTHOR_ID,
            "hl": "en",
            "api_key": api_key,
            "num": PAGE_SIZE,
            "start": start,
        }
        response = requests.get(SERPAPI_URL, params=params, timeout=60)
        response.raise_for_status()
        payload = response.json()
        page_articles = payload.get("articles", []) or []
        if not page_articles:
            break
        articles.extend(page_articles)
        if len(page_articles) < PAGE_SIZE:
            break
        start += PAGE_SIZE
    return articles[:MAX_ARTICLES]


def best_match(pub: dict[str, Any], articles: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, float, str]:
    titles = title_candidates(pub)
    best = None
    best_score = 0.0
    best_local_title = ""
    for local_title in titles:
        for article in articles:
            score = similarity(local_title, article.get("title", ""))
            if score > best_score:
                best_score = score
                best = article
                best_local_title = local_title
    return best, best_score, best_local_title


def citation_value(article: dict[str, Any]) -> str:
    cited_by = article.get("cited_by") or {}
    if isinstance(cited_by, dict):
        value = cited_by.get("value", 0)
        return "0" if value in (None, "") else str(value)
    return "0"


def scholar_record_link(article: dict[str, Any]) -> str:
    return str(article.get("link", "") or "")


def cited_by_link(article: dict[str, Any]) -> str:
    cited_by = article.get("cited_by") or {}
    if isinstance(cited_by, dict) and cited_by.get("link"):
        return str(cited_by["link"])
    return ""


def main() -> None:
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        raise SystemExit("SERPAPI_KEY is not set. Add it in GitHub Settings → Secrets and variables → Actions.")
    if not PUBS_JSON.exists():
        raise SystemExit(f"Missing {PUBS_JSON}")

    publications = json.loads(PUBS_JSON.read_text(encoding="utf-8"))
    articles = fetch_author_articles(api_key)
    today = str(date.today())
    matched = unmatched = 0

    for pub in publications:
        article, score, matched_title = best_match(pub, articles)
        pub["citation_updated"] = today
        pub["citation_match_score"] = round(score, 3) if article else ""
        pub["citation_matched_title"] = matched_title

        if article and score >= MATCH_THRESHOLD:
            pub["google_scholar_citations"] = citation_value(article)
            pub["google_scholar_url"] = scholar_record_link(article)
            pub["google_scholar_cited_by_url"] = cited_by_link(article)
            matched += 1
        else:
            pub["google_scholar_citations"] = ""
            pub["google_scholar_url"] = ""
            pub["google_scholar_cited_by_url"] = ""
            unmatched += 1

    PUBS_JSON.write_text(json.dumps(publications, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        "Updated publication citations: "
        f"matched={matched}, unmatched={unmatched}, articles_fetched={len(articles)}, "
        f"threshold={MATCH_THRESHOLD}"
    )


if __name__ == "__main__":
    main()

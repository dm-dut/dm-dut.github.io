#!/usr/bin/env python3
"""Update Google Scholar citation counts for publication records using SerpAPI.

Inputs:
  data/publications.json

Outputs:
  data/publications.json, with these extra fields for English/non-Chinese records:
    google_scholar_citations
    google_scholar_url
    citation_updated
    citation_match_score
    show_citations

Rules:
- Chinese-language publications are skipped and will not display citation counts.
- DOI display is handled by assets/main.js from each record's doi field.
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

import requests

ROOT = Path(__file__).resolve().parents[1]
PUBS_JSON = ROOT / "data" / "publications.json"
AUTHOR_ID = os.getenv("SCHOLAR_AUTHOR_ID", "vBSJplMAAAAJ")
SERPAPI_URL = "https://serpapi.com/search.json"
MATCH_THRESHOLD = float(os.getenv("SCHOLAR_MATCH_THRESHOLD", "0.75"))
MAX_ARTICLES = int(os.getenv("SCHOLAR_MAX_ARTICLES", "500"))
PAGE_SIZE = 100

CHINESE_VENUES = {
    "chinese journal of management science",
    "systems engineering",
    "journal of systems engineering",
    "operations research and management science",
    "journal of industrial engineering and engineering management",
}


def normalize_title(text: str) -> str:
    text = str(text or "").lower()
    text = re.sub(r"[\u2010-\u2015]", "-", text)
    text = re.sub(r"&", " and ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
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


def is_chinese_publication(pub: dict[str, Any]) -> bool:
    lang = str(pub.get("language", "")).strip().lower()
    if lang in {"chinese", "cn", "zh", "zh-cn"} or lang.startswith("zh") or "中文" in lang:
        return True
    indexes = [str(x).upper() for x in pub.get("indexes", [])]
    if "CSSCI" in indexes:
        return True
    venue = str(pub.get("venue", "")).strip().lower()
    return venue in CHINESE_VENUES


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
    if isinstance(cited_by, dict):
        value = cited_by.get("value", "")
        return "" if value in (None, "") else str(value)
    return ""


def citation_link(article: dict[str, Any]) -> str:
    cited_by = article.get("cited_by") or {}
    if isinstance(cited_by, dict) and cited_by.get("link"):
        return str(cited_by["link"])
    return str(article.get("link", "") or "")


def main() -> None:
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        raise SystemExit("SERPAPI_KEY is not set. Add it in GitHub Settings → Secrets and variables → Actions.")
    if not PUBS_JSON.exists():
        raise SystemExit(f"Missing {PUBS_JSON}")

    publications = json.loads(PUBS_JSON.read_text(encoding="utf-8"))
    articles = fetch_author_articles(api_key)
    today = str(date.today())
    matched = skipped = unmatched = 0

    for pub in publications:
        if is_chinese_publication(pub):
            for key in ["google_scholar_citations", "google_scholar_url", "citation_updated", "citation_match_score"]:
                pub.pop(key, None)
            pub["show_citations"] = False
            skipped += 1
            continue

        pub["show_citations"] = True
        article, score = best_match(pub, articles)
        pub["citation_updated"] = today
        pub["citation_match_score"] = round(score, 3) if article else ""

        if article and score >= MATCH_THRESHOLD:
            pub["google_scholar_citations"] = citation_value(article)
            pub["google_scholar_url"] = citation_link(article)
            matched += 1
        else:
            pub["google_scholar_citations"] = ""
            pub["google_scholar_url"] = ""
            unmatched += 1

    PUBS_JSON.write_text(json.dumps(publications, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        "Updated publication citations: "
        f"matched={matched}, unmatched={unmatched}, chinese_skipped={skipped}, "
        f"articles_fetched={len(articles)}, threshold={MATCH_THRESHOLD}"
    )


if __name__ == "__main__":
    main()

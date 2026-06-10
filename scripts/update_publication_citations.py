#!/usr/bin/env python3
"""Update per-publication Google Scholar citation counts with SerpAPI.

This script is designed for the homepage workflow:
  data/publications.json -> match Google Scholar records -> write citation fields.

It uses the Google Scholar Author API first, which is efficient because it gets
records from the user's own Google Scholar profile. It also supports matching
against both English and Chinese titles.

Required environment variable:
  SERPAPI_KEY

Optional environment variables:
  SCHOLAR_AUTHOR_ID=vBSJplMAAAAJ
  SCHOLAR_MATCH_THRESHOLD=0.72
  SCHOLAR_MAX_ARTICLES=500
  SCHOLAR_TITLE_FALLBACK=0   # set to 1 to query by title for unmatched records
  SCHOLAR_TITLE_FALLBACK_LIMIT=25
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import requests

ROOT = Path(__file__).resolve().parents[1]
PUBS_JSON = ROOT / "data" / "publications.json"
SERPAPI_URL = "https://serpapi.com/search.json"
AUTHOR_ID = os.getenv("SCHOLAR_AUTHOR_ID", "vBSJplMAAAAJ")
API_KEY = os.getenv("SERPAPI_KEY")
MATCH_THRESHOLD = float(os.getenv("SCHOLAR_MATCH_THRESHOLD", "0.72"))
MAX_ARTICLES = int(os.getenv("SCHOLAR_MAX_ARTICLES", "500"))
PAGE_SIZE = 100
TITLE_FALLBACK = os.getenv("SCHOLAR_TITLE_FALLBACK", "0").strip().lower() in {"1", "true", "yes"}
TITLE_FALLBACK_LIMIT = int(os.getenv("SCHOLAR_TITLE_FALLBACK_LIMIT", "25"))

if not API_KEY:
    raise SystemExit(
        "SERPAPI_KEY is not set. Add it in GitHub Settings -> "
        "Secrets and variables -> Actions."
    )


def clean_value(value: Any) -> str:
    """Return a display-safe string while preserving numeric 0."""
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        if int(value) == value:
            return str(int(value))
        return str(value)
    text = str(value).strip()
    if not text or text.lower() in {"none", "null", "nan", "-", "—"}:
        return ""
    return text


def normalize_title(text: Any) -> str:
    text = str(text or "").lower()
    text = re.sub(r"[\u2010-\u2015]", "-", text)
    text = text.replace("&", " and ")
    # Keep CJK characters so Chinese titles can be matched.
    text = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def similarity(a: Any, b: Any) -> float:
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    shorter, longer = sorted([na, nb], key=len)
    contain_score = len(shorter) / len(longer) if shorter in longer and longer else 0.0
    return max(SequenceMatcher(None, na, nb).ratio(), contain_score)


def title_candidates(pub: dict[str, Any]) -> list[str]:
    keys = [
        "title",
        "title_en",
        "title_english",
        "english_title",
        "title_zh",
        "title_cn",
        "title_chinese",
        "chinese_title",
        "original_title",
    ]
    seen: set[str] = set()
    titles: list[str] = []
    for key in keys:
        value = clean_value(pub.get(key))
        if value and value not in seen:
            titles.append(value)
            seen.add(value)
    return titles


def extract_citation_count(article: dict[str, Any]) -> str:
    """Extract citation count from multiple SerpAPI response shapes.

    SerpAPI may return Author API records such as:
      cited_by: {"value": 35, "link": "..."}
    Search API records may instead return:
      inline_links: {"cited_by": {"total": 35, "link": "..."}}
    This function handles both and parses strings such as "Cited by 35".
    """
    candidates: list[Any] = []

    cited_by = article.get("cited_by")
    if isinstance(cited_by, dict):
        candidates.extend([
            cited_by.get("value"),
            cited_by.get("total"),
            cited_by.get("count"),
            cited_by.get("cites"),
        ])
    elif cited_by is not None:
        candidates.append(cited_by)

    inline_links = article.get("inline_links")
    if isinstance(inline_links, dict):
        inline_cited_by = inline_links.get("cited_by")
        if isinstance(inline_cited_by, dict):
            candidates.extend([
                inline_cited_by.get("total"),
                inline_cited_by.get("value"),
                inline_cited_by.get("count"),
            ])
        elif inline_cited_by is not None:
            candidates.append(inline_cited_by)

    for value in candidates:
        text = clean_value(value)
        if text == "0":
            return "0"
        if text:
            m = re.search(r"\d[\d,]*", text)
            if m:
                return m.group(0).replace(",", "")
            return text

    # If a Scholar record is matched but no citation block is present, treat it as 0.
    return "0"


def extract_record_link(article: dict[str, Any]) -> str:
    for key in ["link", "resource_link"]:
        link = clean_value(article.get(key))
        if link:
            return link
    return ""


def extract_cited_by_link(article: dict[str, Any]) -> str:
    cited_by = article.get("cited_by")
    if isinstance(cited_by, dict):
        for key in ["link", "serpapi_link"]:
            link = clean_value(cited_by.get(key))
            if link:
                return link

    inline_links = article.get("inline_links")
    if isinstance(inline_links, dict):
        inline_cited_by = inline_links.get("cited_by")
        if isinstance(inline_cited_by, dict):
            for key in ["link", "serpapi_link"]:
                link = clean_value(inline_cited_by.get(key))
                if link:
                    return link
    return ""


def fetch_author_articles() -> list[dict[str, Any]]:
    articles: list[dict[str, Any]] = []
    start = 0
    while len(articles) < MAX_ARTICLES:
        params = {
            "engine": "google_scholar_author",
            "author_id": AUTHOR_ID,
            "hl": "en",
            "api_key": API_KEY,
            "num": PAGE_SIZE,
            "start": start,
        }
        response = requests.get(SERPAPI_URL, params=params, timeout=60)
        response.raise_for_status()
        payload = response.json()
        page_articles = payload.get("articles") or []
        if not page_articles:
            break
        articles.extend(page_articles)
        print(f"Fetched {len(page_articles)} Scholar profile articles at start={start}.")
        if len(page_articles) < PAGE_SIZE:
            break
        start += PAGE_SIZE
        time.sleep(0.5)
    return articles[:MAX_ARTICLES]


def best_article_match(pub: dict[str, Any], articles: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, float, str]:
    best: dict[str, Any] | None = None
    best_score = 0.0
    best_local_title = ""
    for local_title in title_candidates(pub):
        for article in articles:
            score = similarity(local_title, article.get("title", ""))
            if score > best_score:
                best = article
                best_score = score
                best_local_title = local_title
    return best, best_score, best_local_title


def fetch_title_fallback(title: str) -> dict[str, Any] | None:
    """Optional fallback: query Google Scholar by title if author profile matching fails."""
    if not title:
        return None
    params = {
        "engine": "google_scholar",
        "q": f'"{title}"',
        "hl": "en",
        "api_key": API_KEY,
        "num": 10,
    }
    response = requests.get(SERPAPI_URL, params=params, timeout=60)
    response.raise_for_status()
    payload = response.json()
    organic = payload.get("organic_results") or []
    if not organic:
        return None
    best = None
    best_score = 0.0
    for result in organic:
        score = similarity(title, result.get("title", ""))
        if score > best_score:
            best = result
            best_score = score
    if best and best_score >= MATCH_THRESHOLD:
        best["_fallback_match_score"] = best_score
        return best
    return None


def google_scholar_search_url(title: str) -> str:
    return f"https://scholar.google.com/scholar?q={quote_plus(title)}" if title else ""


def update_publication(pub: dict[str, Any], article: dict[str, Any], score: float, matched_title: str, today: str) -> None:
    record_link = extract_record_link(article) or google_scholar_search_url(matched_title)
    cited_by_url = extract_cited_by_link(article)
    pub["google_scholar_citations"] = extract_citation_count(article)
    pub["google_scholar_url"] = record_link
    pub["google_scholar_link"] = record_link  # compatibility with older front-end code
    pub["google_scholar_cited_by_url"] = cited_by_url
    pub["citation_updated"] = today
    pub["citation_match_score"] = round(score, 3)
    pub["citation_matched_title"] = clean_value(article.get("title"))


def clear_publication(pub: dict[str, Any], today: str) -> None:
    # Keep a Scholar search link so the front end can still provide a path to Scholar,
    # but leave citations blank because no reliable count was found.
    titles = title_candidates(pub)
    title = titles[0] if titles else ""
    search = google_scholar_search_url(title)
    pub["google_scholar_citations"] = ""
    pub["google_scholar_url"] = search
    pub["google_scholar_link"] = search
    pub["google_scholar_cited_by_url"] = ""
    pub["citation_updated"] = today
    pub["citation_match_score"] = ""
    pub["citation_matched_title"] = ""


def main() -> None:
    if not PUBS_JSON.exists():
        raise SystemExit(f"Missing {PUBS_JSON}")

    publications = json.loads(PUBS_JSON.read_text(encoding="utf-8"))
    if not isinstance(publications, list):
        raise SystemExit("data/publications.json must be a JSON list.")

    articles = fetch_author_articles()
    today = str(date.today())
    matched = 0
    unmatched = 0
    fallback_used = 0

    for pub in publications:
        article, score, matched_title = best_article_match(pub, articles)

        if article and score >= MATCH_THRESHOLD:
            update_publication(pub, article, score, matched_title, today)
            matched += 1
            print(
                f"MATCH {matched:03d}: citations={pub['google_scholar_citations']} "
                f"score={score:.3f} :: {matched_title[:90]}"
            )
            continue

        used_fallback = False
        if TITLE_FALLBACK and fallback_used < TITLE_FALLBACK_LIMIT:
            for title in title_candidates(pub):
                fallback_article = fetch_title_fallback(title)
                fallback_used += 1
                time.sleep(0.5)
                if fallback_article:
                    fscore = float(fallback_article.get("_fallback_match_score", MATCH_THRESHOLD))
                    update_publication(pub, fallback_article, fscore, title, today)
                    matched += 1
                    used_fallback = True
                    print(
                        f"FALLBACK MATCH {matched:03d}: citations={pub['google_scholar_citations']} "
                        f"score={fscore:.3f} :: {title[:90]}"
                    )
                    break

        if not used_fallback:
            clear_publication(pub, today)
            unmatched += 1
            first_title = title_candidates(pub)[0] if title_candidates(pub) else "Untitled"
            print(f"NO MATCH: {first_title[:90]}")

    PUBS_JSON.write_text(json.dumps(publications, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        "Updated publication Google Scholar data: "
        f"matched={matched}, unmatched={unmatched}, author_articles={len(articles)}, "
        f"title_fallback_used={fallback_used}, threshold={MATCH_THRESHOLD}"
    )


if __name__ == "__main__":
    main()

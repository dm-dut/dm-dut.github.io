import os
import json
import time
import requests
from difflib import SequenceMatcher
from pathlib import Path

AUTHOR_ID = "vBSJplMAAAAJ"
PUBLICATION_FILE = Path("data/publications.json")
API_KEY = os.environ.get("SERPAPI_KEY")

if not API_KEY:
    raise RuntimeError("SERPAPI_KEY is not set. Please add it in GitHub Secrets.")


def normalize_text(text):
    if text is None:
        return ""
    text = str(text).lower()
    for ch in ["–", "—", ":", ",", ".", ";", "'", '"', "“", "”", "‘", "’", "(", ")", "[", "]"]:
        text = text.replace(ch, " ")
    return " ".join(text.split())


def similarity(a, b):
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()


def get_citation_count(article):
    cited_by = article.get("cited_by", {})
    value = cited_by.get("value", "")

    if value not in ["", None]:
        return value

    inline_links = article.get("inline_links", {})
    cited_by_inline = inline_links.get("cited_by", {})

    value = cited_by_inline.get("total", "")

    if value not in ["", None]:
        return value

    return ""


def get_scholar_link(article):
    if article.get("link"):
        return article.get("link")

    cited_by = article.get("cited_by", {})
    if cited_by.get("link"):
        return cited_by.get("link")

    inline_links = article.get("inline_links", {})
    cited_by_inline = inline_links.get("cited_by", {})

    if cited_by_inline.get("link"):
        return cited_by_inline.get("link")

    return ""


def collect_author_articles():
    all_articles = []
    start = 0

    while True:
        params = {
            "engine": "google_scholar_author",
            "author_id": AUTHOR_ID,
            "hl": "en",
            "num": 100,
            "start": start,
            "api_key": API_KEY,
        }

        response = requests.get(
            "https://serpapi.com/search",
            params=params,
            timeout=60,
        )
        response.raise_for_status()

        data = response.json()
        articles = data.get("articles", [])

        if not articles:
            break

        all_articles.extend(articles)

        print(f"Retrieved {len(articles)} articles from start={start}.")

        if len(articles) < 100:
            break

        start += 100
        time.sleep(1)

    return all_articles


def main():
    with PUBLICATION_FILE.open("r", encoding="utf-8") as f:
        publications = json.load(f)

    articles = collect_author_articles()

    print(f"Total Scholar articles retrieved: {len(articles)}")
    updated = 0

    for pub in publications:
        titles_to_match = []

        for key in [
            "title",
            "title_en",
            "english_title",
            "title_cn",
            "chinese_title",
            "original_title",
        ]:
            value = pub.get(key)
            if value:
                titles_to_match.append(value)

        if not titles_to_match:
            continue

        best_article = None
        best_score = 0

        for title in titles_to_match:
            for article in articles:
                score = similarity(title, article.get("title", ""))
                if score > best_score:
                    best_score = score
                    best_article = article

        if best_article and best_score >= 0.72:
            citation_count = get_citation_count(best_article)
            scholar_link = get_scholar_link(best_article)

            pub["google_scholar_citations"] = citation_count
            pub["google_scholar_link"] = scholar_link
            pub["citation_match_score"] = round(best_score, 3)
            pub["matched_scholar_title"] = best_article.get("title", "")

            updated += 1

            print(
                f"Matched: {titles_to_match[0][:80]} | "
                f"citations={citation_count} | score={best_score:.3f}"
            )

        else:
            pub["google_scholar_citations"] = ""
            pub["google_scholar_link"] = ""
            pub["citation_match_score"] = ""
            pub["matched_scholar_title"] = ""

            print(f"No match: {titles_to_match[0][:80]}")

    with PUBLICATION_FILE.open("w", encoding="utf-8") as f:
        json.dump(publications, f, ensure_ascii=False, indent=2)

    print(f"Updated citation information for {updated} publications.")


if __name__ == "__main__":
    main()
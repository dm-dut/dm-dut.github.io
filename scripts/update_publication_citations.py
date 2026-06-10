import os
import json
import requests
from difflib import SequenceMatcher

AUTHOR_ID = "vBSJplMAAAAJ"
API_KEY = os.environ["SERPAPI_KEY"]

PUBLICATION_FILE = "data/publications.json"


def normalize_text(text):
    if text is None:
        return ""
    return " ".join(
        str(text)
        .lower()
        .replace("–", "-")
        .replace("—", "-")
        .replace(":", "")
        .replace(",", "")
        .split()
    )


def similarity(a, b):
    return SequenceMatcher(
        None,
        normalize_text(a),
        normalize_text(b)
    ).ratio()


print("Loading publication database...")

with open(PUBLICATION_FILE, "r", encoding="utf-8") as f:
    publications = json.load(f)

print(f"Loaded {len(publications)} publications.")

print("Requesting Google Scholar author profile from SerpAPI...")

params = {
    "engine": "google_scholar_author",
    "author_id": AUTHOR_ID,
    "hl": "en",
    "num": 100,
    "api_key": API_KEY
}

response = requests.get(
    "https://serpapi.com/search",
    params=params,
    timeout=60
)

response.raise_for_status()

data = response.json()

articles = data.get("articles", [])

print(f"Retrieved {len(articles)} scholar articles.")

updated_count = 0

for pub in publications:

    language = str(pub.get("language", "")).lower()

    # 中文论文不显示引用
    if language in ["chinese", "cn", "zh"]:
        pub["google_scholar_citations"] = ""
        pub["google_scholar_link"] = ""
        continue

    title = pub.get("title", "")

    if not title:
        continue

    best_match = None
    best_score = 0

    for article in articles:

        scholar_title = article.get("title", "")

        score = similarity(title, scholar_title)

        if score > best_score:
            best_score = score
            best_match = article

    # 匹配阈值
    if best_match and best_score >= 0.75:

        cited_by = best_match.get("cited_by", {})

        pub["google_scholar_citations"] = cited_by.get(
            "value", ""
        )

        pub["google_scholar_link"] = best_match.get(
            "link", ""
        )

        updated_count += 1

        print(
            f"Matched: {title[:80]}"
            f" | citations = {pub['google_scholar_citations']}"
            f" | score = {best_score:.3f}"
        )

    else:

        pub["google_scholar_citations"] = ""
        pub["google_scholar_link"] = ""

        print(
            f"No match: {title[:80]}"
        )

print(f"Updated citation counts for {updated_count} papers.")

with open(PUBLICATION_FILE, "w", encoding="utf-8") as f:
    json.dump(
        publications,
        f,
        ensure_ascii=False,
        indent=2
    )

print("publications.json updated successfully.")
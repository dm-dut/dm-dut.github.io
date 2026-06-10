#!/usr/bin/env python3
"""
Update data/scholar_stats.json for the homepage.

Two modes are supported:
1. Stable/manual mode: edit data/scholar_stats.json directly. This script preserves existing values.
2. SerpAPI mode: set SERPAPI_KEY in GitHub Secrets, and optionally SCHOLAR_AUTHOR_ID.
   The script will update citations, h-index, i10-index, updated, and profile_url.

Google Scholar does not provide an official browser-side API, so the webpage reads
this JSON file instead of scraping Google Scholar directly.
"""
import json
import os
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

OUT = Path("data/scholar_stats.json")
DEFAULT_AUTHOR_ID = "vBSJplMAAAAJ"
PROFILE_URL = "https://scholar.google.com/citations?hl=zh-CN&user="

def load_existing():
    if OUT.exists():
        return json.loads(OUT.read_text(encoding="utf-8"))
    return {
        "citations": "—",
        "h_index": "—",
        "i10_index": "—",
        "updated": "",
        "profile_url": PROFILE_URL + os.getenv("SCHOLAR_AUTHOR_ID", DEFAULT_AUTHOR_ID),
    }

def save(data):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    data.pop("note", None)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Scholar stats written to {OUT}")

def update_with_serpapi(data):
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        return data, False

    author_id = os.getenv("SCHOLAR_AUTHOR_ID", DEFAULT_AUTHOR_ID)
    params = {
        "engine": "google_scholar_author",
        "author_id": author_id,
        "api_key": api_key,
        "hl": "en",
    }
    url = "https://serpapi.com/search.json?" + urlencode(params)
    with urlopen(url, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    cited_by = payload.get("cited_by", {})
    table = cited_by.get("table", [])
    metrics = {}
    for row in table:
        metric = str(row.get("citations", {}).get("all") or row.get("h_index", {}).get("all") or "")
        # SerpAPI table rows usually expose: {'citations': {'all': ...}}, {'h_index': {'all': ...}}, etc.
        if "citations" in row:
            metrics["citations"] = row.get("citations", {}).get("all", "—")
        if "h_index" in row:
            metrics["h_index"] = row.get("h_index", {}).get("all", "—")
        if "i10_index" in row:
            metrics["i10_index"] = row.get("i10_index", {}).get("all", "—")

    # Fallback for payload variants.
    if not metrics and isinstance(cited_by, dict):
        metrics["citations"] = cited_by.get("citations", {}).get("all", data.get("citations", "—")) if isinstance(cited_by.get("citations"), dict) else data.get("citations", "—")
        metrics["h_index"] = cited_by.get("h_index", {}).get("all", data.get("h_index", "—")) if isinstance(cited_by.get("h_index"), dict) else data.get("h_index", "—")
        metrics["i10_index"] = cited_by.get("i10_index", {}).get("all", data.get("i10_index", "—")) if isinstance(cited_by.get("i10_index"), dict) else data.get("i10_index", "—")

    data.update({
        "citations": str(metrics.get("citations", data.get("citations", "—"))),
        "h_index": str(metrics.get("h_index", data.get("h_index", "—"))),
        "i10_index": str(metrics.get("i10_index", data.get("i10_index", "—"))),
        "updated": str(date.today()),
        "profile_url": PROFILE_URL + author_id,
    })
    return data, True

def main():
    data = load_existing()
    try:
        data, changed = update_with_serpapi(data)
        if not changed:
            # Preserve manually maintained values; do not display explanatory notes on the webpage.
            data.setdefault("profile_url", PROFILE_URL + os.getenv("SCHOLAR_AUTHOR_ID", DEFAULT_AUTHOR_ID))
    except Exception as exc:
        print(f"SerpAPI update failed; preserving existing scholar_stats.json: {exc}", file=sys.stderr)
    save(data)

if __name__ == "__main__":
    main()

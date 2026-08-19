from __future__ import annotations

import argparse
from datetime import date

import requests

from .config import (
    BUILD_ID,
    CROSSREF_MAILTO,
    ELSEVIER_API_KEY,
    ELSEVIER_INSTTOKEN,
    HTTP_TIMEOUT,
    SPRINGER_API_KEY,
)
from .journals import enabled_journals
from .providers import ieee, sciencedirect, springer
from .providers.rss_source import parse_feed
from .utils import build_session


def _status(name: str, ok: bool, detail: str) -> tuple[str, bool]:
    print(f"[{name}] {'OK' if ok else 'FAIL'}: {detail}")
    return name, ok


def test_springer() -> tuple[str, bool]:
    if not SPRINGER_API_KEY:
        return _status("Springer Meta API", False, "SPRINGER_API_KEY is missing in paper_monitor_system/.env")
    session = build_session()
    try:
        r = session.get(
            springer.BASE_URL,
            params={"api_key": SPRINGER_API_KEY, "q": "keyword:test", "s": 1, "p": 1},
            timeout=HTTP_TIMEOUT,
        )
        return _status("Springer Meta API", r.status_code == 200, f"HTTP {r.status_code}")
    except requests.RequestException as exc:
        return _status("Springer Meta API", False, f"{type(exc).__name__}: {exc}")


def test_sciencedirect_api() -> tuple[str, bool]:
    if not ELSEVIER_API_KEY:
        return _status("ScienceDirect API", False, "ELSEVIER_API_KEY is missing; page/RSS/Crossref can still run")
    specs = enabled_journals("sciencedirect")
    spec = specs[0]
    headers = {"X-ELS-APIKey": ELSEVIER_API_KEY, "Accept": "application/json"}
    if ELSEVIER_INSTTOKEN:
        headers["X-ELS-Insttoken"] = ELSEVIER_INSTTOKEN
    params = {"query": sciencedirect._query_for_spec(spec, date.today()), "content": "journals", "start": 0, "count": 1}
    session = build_session()
    try:
        r = session.get(sciencedirect.BASE_URL, params=params, headers=headers, timeout=HTTP_TIMEOUT)
        return _status("ScienceDirect API", r.status_code == 200, f"HTTP {r.status_code} ({spec.journal})")
    except requests.RequestException as exc:
        return _status("ScienceDirect API", False, f"{type(exc).__name__}: {exc}")


def test_sciencedirect_page() -> tuple[str, bool]:
    spec = enabled_journals("sciencedirect")[0]
    url = sciencedirect._candidate_pages(spec)[0]
    s = build_session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    })
    try:
        r = s.get(url, timeout=HTTP_TIMEOUT)
        return _status("ScienceDirect page", r.status_code == 200, f"HTTP {r.status_code} ({url})")
    except requests.RequestException as exc:
        return _status("ScienceDirect page", False, f"{type(exc).__name__}: {exc}")


def test_sciencedirect_rss_discovery() -> tuple[str, bool]:
    spec = enabled_journals("sciencedirect")[0]
    try:
        urls = sciencedirect._discover_rss_urls(spec)
        if urls:
            return _status("ScienceDirect RSS discovery", True, f"found {len(urls)} feed(s); first={urls[0]}")
        return _status("ScienceDirect RSS discovery", False, "no RSS link discovered from accessible journal pages")
    except Exception as exc:
        return _status("ScienceDirect RSS discovery", False, f"{type(exc).__name__}: {exc}")


def test_ieee_saved_search_rss() -> tuple[str, bool]:
    specs = enabled_journals("ieee")
    urls = ieee._combined_rss_urls(specs)
    if not urls:
        return _status("IEEE Saved Search RSS", False, "no RSS URL configured")
    url = urls[0]
    s = build_session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    try:
        r = s.get(url, timeout=HTTP_TIMEOUT)
        if r.status_code != 200:
            return _status("IEEE Saved Search RSS", False, f"HTTP {r.status_code}; URL is preserved exactly as saved")
        try:
            entries = parse_feed(r.content)
        except Exception as exc:
            return _status("IEEE Saved Search RSS", False, f"HTTP 200 but feed parsing failed: {type(exc).__name__}")
        return _status("IEEE Saved Search RSS", bool(entries), f"HTTP 200; RSS/Atom entries={len(entries)}")
    except requests.RequestException as exc:
        return _status("IEEE Saved Search RSS", False, f"{type(exc).__name__}: {exc}")


def test_crossref() -> tuple[str, bool]:
    s = build_session()
    params = {"rows": 1}
    if CROSSREF_MAILTO:
        params["mailto"] = CROSSREF_MAILTO
    try:
        r = s.get("https://api.crossref.org/works", params=params, timeout=HTTP_TIMEOUT)
        return _status("Crossref", r.status_code == 200, f"HTTP {r.status_code}")
    except requests.RequestException as exc:
        return _status("Crossref", False, f"{type(exc).__name__}: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose publisher connectivity from this local computer")
    parser.add_argument("--strict", action="store_true", help="return non-zero unless all tested channels pass")
    args = parser.parse_args()

    print(f"Paper Monitor Build: {BUILD_ID}")
    print("Connection test runs from THIS computer/network; API keys are never printed.\n")
    results = [
        test_springer(),
        test_sciencedirect_api(),
        test_sciencedirect_page(),
        test_sciencedirect_rss_discovery(),
        test_ieee_saved_search_rss(),
        test_crossref(),
    ]
    passed = sum(1 for _, ok in results if ok)
    print(f"\nSummary: {passed}/{len(results)} checks passed.")
    print("A ScienceDirect API failure is not fatal when page/RSS works; publisher-specific fallbacks remain enabled.")
    if args.strict and passed != len(results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

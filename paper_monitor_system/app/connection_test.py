from __future__ import annotations

import argparse
from datetime import date, timedelta

import requests

from .config import BUILD_ID, CROSSREF_MAILTO, ELSEVIER_API_KEY, ELSEVIER_INSTTOKEN, HTTP_TIMEOUT, SPRINGER_API_KEY
from .journals import enabled_journals, display_issn
from .providers import ieee, sciencedirect, springer
from .providers.rss_source import parse_feed
from .utils import build_session


def _line(name: str, state: str, detail: str) -> None:
    print(f"[{name}] {state}: {detail}")


def test_springer() -> bool:
    if not SPRINGER_API_KEY:
        _line("Springer Meta API", "FAIL", "SPRINGER_API_KEY is missing in paper_monitor_system/.env")
        return False
    try:
        r = build_session().get(springer.BASE_URL, params={"api_key": SPRINGER_API_KEY, "q": "keyword:test", "s": 1, "p": 1}, timeout=HTTP_TIMEOUT)
        ok = r.status_code == 200
        _line("Springer Meta API", "OK" if ok else "FAIL", f"HTTP {r.status_code}")
        return ok
    except requests.RequestException as exc:
        _line("Springer Meta API", "FAIL", f"{type(exc).__name__}: {exc}")
        return False


def test_ieee_saved_search_rss() -> bool:
    urls = ieee._combined_rss_urls(enabled_journals("ieee"))
    if not urls:
        _line("IEEE Saved Search RSS", "FAIL", "no RSS URL configured")
        return False
    s = build_session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*;q=0.8",
    })
    try:
        r = s.get(urls[0], timeout=HTTP_TIMEOUT)
        if r.status_code != 200:
            _line("IEEE Saved Search RSS", "FAIL", f"HTTP {r.status_code}")
            return False
        entries = parse_feed(r.content)
        ok = bool(entries)
        extra = "; feed is at rowsPerPage=10 capacity" if len(entries) == 10 and "rowsPerPage=10" in urls[0] else ""
        _line("IEEE Saved Search RSS", "OK" if ok else "FAIL", f"HTTP 200; RSS/Atom entries={len(entries)}{extra}")
        return ok
    except Exception as exc:
        _line("IEEE Saved Search RSS", "FAIL", f"{type(exc).__name__}: {exc}")
        return False


def test_crossref() -> bool:
    params = {"rows": 1}
    if CROSSREF_MAILTO:
        params["mailto"] = CROSSREF_MAILTO
    try:
        r = build_session().get("https://api.crossref.org/works", params=params, timeout=HTTP_TIMEOUT)
        ok = r.status_code == 200
        _line("Crossref", "OK" if ok else "FAIL", f"HTTP {r.status_code}")
        return ok
    except requests.RequestException as exc:
        _line("Crossref", "FAIL", f"{type(exc).__name__}: {exc}")
        return False


def test_elsevier_crossref_incremental() -> bool:
    spec = enabled_journals("sciencedirect")[0]
    issn = list(reversed(spec.issns))[0]
    start = date.today() - timedelta(days=30)
    params = {
        "filter": ",".join([
            f"issn:{display_issn(issn)}", "type:journal-article", f"from-index-date:{start.isoformat()}"
        ]),
        "rows": 1,
    }
    if CROSSREF_MAILTO:
        params["mailto"] = CROSSREF_MAILTO
    try:
        r = build_session().get("https://api.crossref.org/works", params=params, timeout=HTTP_TIMEOUT)
        ok = r.status_code == 200
        _line("Elsevier Crossref incremental", "OK" if ok else "FAIL", f"HTTP {r.status_code} ({spec.journal})")
        return ok
    except requests.RequestException as exc:
        _line("Elsevier Crossref incremental", "FAIL", f"{type(exc).__name__}: {exc}")
        return False


def optional_sciencedirect_diagnostics() -> None:
    spec = enabled_journals("sciencedirect")[0]
    if ELSEVIER_API_KEY:
        headers = {"X-ELS-APIKey": ELSEVIER_API_KEY, "Accept": "application/json"}
        if ELSEVIER_INSTTOKEN:
            headers["X-ELS-Insttoken"] = ELSEVIER_INSTTOKEN
        try:
            r = build_session().get(sciencedirect.BASE_URL, params={"query": sciencedirect._query_for_spec(spec, date.today()), "content": "journals", "start": 0, "count": 1}, headers=headers, timeout=HTTP_TIMEOUT)
            _line("ScienceDirect API (optional)", "OK" if r.status_code == 200 else "WARN", f"HTTP {r.status_code}; LOCAL V2 does not require this channel")
        except requests.RequestException as exc:
            _line("ScienceDirect API (optional)", "WARN", f"{type(exc).__name__}; LOCAL V2 does not require this channel")
    else:
        _line("ScienceDirect API (optional)", "SKIP", "no API key; not required")

    try:
        url = sciencedirect._candidate_pages(spec)[0]
        r = build_session().get(url, timeout=HTTP_TIMEOUT)
        _line("ScienceDirect page (optional)", "OK" if r.status_code == 200 else "WARN", f"HTTP {r.status_code}; LOCAL V2 does not require this channel")
    except requests.RequestException as exc:
        _line("ScienceDirect page (optional)", "WARN", f"{type(exc).__name__}; LOCAL V2 does not require this channel")

    configured = [s for s in enabled_journals("sciencedirect") if s.rss_url]
    if configured:
        _line("ScienceDirect direct RSS", "INFO", f"{len(configured)} journal feed URL(s) configured; they will be merged with Crossref incremental discovery")
    else:
        _line("ScienceDirect direct RSS", "SKIP", "no stable direct RSS URLs configured; Crossref incremental remains active")


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose LOCAL V2 data-source connectivity")
    parser.add_argument("--strict", action="store_true", help="return non-zero unless all required channels pass")
    args = parser.parse_args()

    print(f"Paper Monitor Build: {BUILD_ID}")
    print("Required LOCAL V2 channels are tested first; ScienceDirect API/page are optional diagnostics.\n")
    required = [test_springer(), test_ieee_saved_search_rss(), test_crossref(), test_elsevier_crossref_incremental()]
    optional_sciencedirect_diagnostics()
    passed = sum(required)
    print(f"\nRequired summary: {passed}/{len(required)} checks passed.")
    if args.strict and passed != len(required):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

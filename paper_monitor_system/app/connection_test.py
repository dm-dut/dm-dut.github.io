from __future__ import annotations

import argparse
from datetime import date

from .config import BUILD_ID, SPRINGER_API_KEY
from .journals import enabled_journals
from .providers import ieee, sciencedirect, springer
from .providers.browser import BrowserRuntime
from .utils import build_session, get_json


def line(name: str, state: str, detail: str) -> None:
    print(f"[{name}] {state}: {detail}")


def test_springer() -> bool:
    if not SPRINGER_API_KEY:
        line("Springer Meta API", "FAIL", "SPRINGER_API_KEY missing in paper_monitor_system/.env")
        return False
    try:
        data = get_json(build_session(), springer.BASE_URL, params={
            "api_key": SPRINGER_API_KEY, "q": springer._day_query(date.today()), "s":1, "p":1,
        })
        line("Springer Meta API", "OK", f"records in first page={len(data.get('records') or [])}")
        return True
    except Exception as exc:
        line("Springer Meta API", "FAIL", f"{type(exc).__name__}: {exc}"); return False


def test_browser_sources() -> tuple[bool,bool]:
    sd_spec=enabled_journals("sciencedirect")[0]; ieee_spec=enabled_journals("ieee")[0]
    sd_ok=ieee_ok=False
    try:
        with BrowserRuntime() as br:
            page=br.new_page()
            try:
                br.goto(page, sd_spec.search_url, label="ScienceDirect search")
                c=sciencedirect._search_candidates(page); sd_ok=bool(c)
                line("ScienceDirect PII list", "OK" if sd_ok else "FAIL", f"PII candidates={len(c)}; {sd_spec.journal}")
            except Exception as exc:
                line("ScienceDirect PII list", "FAIL", f"{type(exc).__name__}: {exc}")
            try:
                br.goto(page, ieee_spec.search_url, label="IEEE Early Access")
                c=ieee._search_candidates(page); ieee_ok=bool(c)
                line("IEEE Early Access list", "OK" if ieee_ok else "FAIL", f"Document ID candidates={len(c)}; {ieee_spec.journal}")
            except Exception as exc:
                line("IEEE Early Access list", "FAIL", f"{type(exc).__name__}: {exc}")
            page.close()
    except Exception as exc:
        line("Browser engine", "FAIL", f"{type(exc).__name__}: {exc}")
    return sd_ok, ieee_ok


def main() -> None:
    parser=argparse.ArgumentParser(description="V6 source connectivity test"); parser.add_argument("--strict",action="store_true"); args=parser.parse_args()
    print(f"Paper Monitor Build: {BUILD_ID}")
    springer_ok=test_springer(); sd_ok,ieee_ok=test_browser_sources(); passed=sum([springer_ok,sd_ok,ieee_ok])
    print(f"\nRequired summary: {passed}/3 checks passed.")
    if args.strict and passed != 3: raise SystemExit(1)


if __name__ == "__main__": main()

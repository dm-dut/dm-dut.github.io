from __future__ import annotations

import re

from .config import BUILD_ID, DB_PATH, JOURNAL_LIST_PATH, SYSTEM_ROOT, WEB_JSON_PATH
from .db import init_db
from .journals import enabled_journals, load_journal_list
from .providers import crossref, ieee, springer


def main() -> None:
    specs = load_journal_list()
    counts = {p: len(enabled_journals(p)) for p in ("sciencedirect", "springer", "ieee")}
    assert specs and counts == {"sciencedirect": 39, "springer": 25, "ieee": 15}, counts
    assert JOURNAL_LIST_PATH.exists()
    assert springer.BASE_URL.endswith("/meta/v2/json")
    assert crossref.BASE_URL.rstrip("/") == "https://api.crossref.org"
    assert BUILD_ID.startswith("LOCAL-")

    bad = []
    for py in (SYSTEM_ROOT / "app").rglob("*.py"):
        if re.search(r"(?:from|import)\s+app(?:\.|\s|$)", py.read_text(encoding="utf-8")):
            bad.append(str(py))
    assert not bad, bad

    for spec in enabled_journals("sciencedirect"):
        assert spec.primary_url, f"Missing ScienceDirect primary URL: {spec.journal}"
        assert spec.mode == "sciencedirect_page", (spec.journal, spec.mode)
    for spec in enabled_journals("springer"):
        assert spec.primary_url, f"Missing Springer primary URL: {spec.journal}"
        assert spec.mode == "springer_api", (spec.journal, spec.mode)

    ieee_specs = enabled_journals("ieee")
    urls = ieee._combined_rss_urls(ieee_specs)
    assert len(urls) == 1, f"Expected one deduplicated combined IEEE Saved Search RSS, got {len(urls)}"
    assert "rssFeed=true" in urls[0]
    assert "IEEETrans15" in urls[0]
    assert "rowsPerPage=10" in urls[0], "LOCAL build must preserve the user's original Saved Search URL"

    init_db()
    WEB_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"build={BUILD_ID}")
    print(f"journal_list={JOURNAL_LIST_PATH} ({len(specs)} enabled)")
    print(f"providers={counts}")
    print("strategy=sciencedirect api(local)->page->rss->crossref; springer api->online-first->crossref; ieee exact combined-saved-search-rss->crossref")
    print(f"ieee_combined_rss=1 exact feed for {len(ieee_specs)} journals")
    print(f"database={DB_PATH}")
    print(f"web_json={WEB_JSON_PATH}")
    print("SELF-CHECK OK")


if __name__ == "__main__":
    main()

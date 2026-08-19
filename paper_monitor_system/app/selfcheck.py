from __future__ import annotations

import inspect
import re

from .config import BUILD_ID, DB_PATH, JOURNAL_LIST_PATH, SYSTEM_ROOT, WEB_JSON_PATH
from .db import init_db
from .journals import enabled_journals, load_journal_list
from .providers import crossref, ieee, sciencedirect, springer


def main() -> None:
    specs = load_journal_list()
    counts = {p: len(enabled_journals(p)) for p in ("sciencedirect", "springer", "ieee")}
    assert specs and counts == {"sciencedirect": 39, "springer": 25, "ieee": 15}, counts
    assert JOURNAL_LIST_PATH.exists()
    assert springer.BASE_URL.endswith("/meta/v2/json")
    assert crossref.BASE_URL.rstrip("/") == "https://api.crossref.org"
    assert BUILD_ID == "LOCAL-2026.08.19-V3.2"

    bad = []
    for py in (SYSTEM_ROOT / "app").rglob("*.py"):
        if re.search(r"(?:from|import)\s+app(?:\.|\s|$)", py.read_text(encoding="utf-8")):
            bad.append(str(py))
    assert not bad, bad

    elsevier = enabled_journals("sciencedirect")
    assert all(s.mode == "elsevier_member_dual_batch" for s in elsevier)
    assert all(s.crossref_member == 78 for s in elsevier), "All 39 Elsevier rows should use Crossref member 78 unless deliberately overridden"
    assert all(not s.crossref_prefix for s in elsevier), "V3.2 standard Elsevier rows should not hard-filter by DOI prefix"
    assert "member_dual_batch_discover" in inspect.getsource(sciencedirect.fetch)
    assert "from-online-pub-date" in inspect.getsource(crossref.member_dual_batch_discover)
    assert "from-update-date" in inspect.getsource(crossref.member_dual_batch_discover)
    assert "/journals/{" not in inspect.getsource(crossref)

    springer_specs = enabled_journals("springer")
    assert all(s.primary_url for s in springer_specs), "Missing Springer primary URL"
    assert all(s.mode == "springer_batch_api" for s in springer_specs)

    ieee_specs = enabled_journals("ieee")
    urls = ieee._combined_rss_urls(ieee_specs)
    assert len(urls) == 1, f"Expected one deduplicated IEEE Saved Search RSS, got {len(urls)}"
    assert "rssFeed=true" in urls[0] and "IEEETrans15" in urls[0]
    assert "rowsPerPage=10" in urls[0]

    init_db()
    WEB_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"build={BUILD_ID}")
    print(f"journal_list={JOURNAL_LIST_PATH} ({len(specs)} enabled)")
    print(f"providers={counts}")
    print("strategy=elsevier crossref-member-78 online/update dual batch + optional direct RSS; springer basic-safe batch-meta-api + crossref-prefix fallback; ieee combined-saved-search-rss with labelled RSS-date fallback")
    print("pending=DOI-only delayed recheck; no immediate same-run recheck")
    print(f"ieee_combined_rss=1 exact feed for {len(ieee_specs)} journals")
    print(f"database={DB_PATH}")
    print(f"web_json={WEB_JSON_PATH}")
    print("SELF-CHECK OK")


if __name__ == "__main__":
    main()

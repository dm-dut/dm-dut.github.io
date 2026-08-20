from __future__ import annotations

import re

from .config import BUILD_ID, DB_PATH, JOURNAL_LIST_PATH, SCHEMA_VERSION, SYSTEM_ROOT, WEB_JSON_PATH
from .db import init_db
from .journals import enabled_journals, load_journal_list


def main() -> None:
    specs = load_journal_list()
    counts = {p: len(enabled_journals(p)) for p in ("sciencedirect", "springer", "ieee")}
    assert len(specs) == 79 and counts == {"sciencedirect": 39, "springer": 25, "ieee": 15}, counts
    assert BUILD_ID == "LOCAL-2026.08.20-V6-ID-FIRST"
    assert SCHEMA_VERSION == "6-id-first"
    assert JOURNAL_LIST_PATH.exists()

    for spec in enabled_journals("sciencedirect"):
        assert spec.mode == "sciencedirect_id_first"
        assert spec.search_url.startswith("https://www.sciencedirect.com/search?docId=")
        assert "sortBy=date" in spec.search_url and "show=50" in spec.search_url and "qs=" not in spec.search_url
        assert spec.source_id_type == "PII"

    for spec in enabled_journals("springer"):
        assert spec.mode == "springer_meta_api"
        assert spec.online_date_field == "onlineDate"

    for spec in enabled_journals("ieee"):
        assert spec.mode == "ieee_early_access_id_first"
        assert spec.search_url.startswith("https://ieeexplore.ieee.org/xpl/tocresult.jsp?isnumber=")
        assert "sortType=newest" in spec.search_url
        assert "PublicationTitle" not in spec.search_url and "searchresult.jsp" not in spec.search_url
        assert spec.source_id_type == "IEEE Document ID"

    providers = SYSTEM_ROOT / "app" / "providers"
    for name in ("crossref.py", "rss_source.py", "enrichment.py"):
        assert not (providers / name).exists(), name

    bad = []
    for py in (SYSTEM_ROOT / "app").rglob("*.py"):
        if re.search(r"(?:from|import)\s+app(?:\.|\s|$)", py.read_text(encoding="utf-8")):
            bad.append(str(py))
    assert not bad, bad

    init_db()
    print(f"build={BUILD_ID}")
    print(f"journal_list={JOURNAL_LIST_PATH} ({len(specs)} enabled)")
    print(f"providers={counts}")
    print("strategy=Elsevier PII-first search page; Springer Meta API onlineDate; IEEE simple Early Access/TOC Document-ID-first")
    print("sorting=fetched_date desc -> journal asc -> true online date desc -> source_rank asc")
    print(f"database={DB_PATH}")
    print(f"web_json={WEB_JSON_PATH}")
    print("SELF-CHECK OK")


if __name__ == "__main__":
    main()

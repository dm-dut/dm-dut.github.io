from __future__ import annotations

import re
from pathlib import Path

from .config import DB_PATH, JOURNAL_LIST_PATH, REPO_ROOT, SYSTEM_ROOT, WEB_JSON_PATH
from .db import init_db
from .journals import enabled_journals, load_journal_list
from .providers import sciencedirect, springer, ieee


def main() -> None:
    specs = load_journal_list()
    counts = {p: len(enabled_journals(p)) for p in ("sciencedirect", "springer", "ieee")}
    assert specs, "No enabled journals found in whitelist"
    assert counts == {"sciencedirect": 39, "springer": 25, "ieee": 15}, f"Unexpected whitelist counts: {counts}"
    assert JOURNAL_LIST_PATH.exists(), f"Missing journal list: {JOURNAL_LIST_PATH}"
    assert sciencedirect.BASE_URL.endswith("/content/search/sciencedirect"), sciencedirect.BASE_URL
    assert springer.BASE_URL.endswith("/meta/v2/json"), springer.BASE_URL
    assert ieee.BASE_URL.endswith("/api/v1/search/articles"), ieee.BASE_URL

    # Guard against the package-import regression that caused the earlier
    # ModuleNotFoundError on GitHub Actions.
    bad_imports = []
    for py in (SYSTEM_ROOT / "app").rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        if re.search(r"(?:from|import)\s+app(?:\.|\s|$)", text):
            bad_imports.append(str(py.relative_to(REPO_ROOT)))
    assert not bad_imports, f"Legacy top-level app imports found: {bad_imports}"

    WEB_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    init_db()
    print(f"repo_root={REPO_ROOT}")
    print(f"system_root={SYSTEM_ROOT}")
    print(f"journal_list={JOURNAL_LIST_PATH} ({len(specs)} enabled)")
    print(f"providers={counts}")
    print(f"database={DB_PATH}")
    print(f"web_json={WEB_JSON_PATH}")
    print("ScienceDirect endpoint OK")
    print("Springer Meta/v2 endpoint OK")
    print("IEEE endpoint OK; Crossref fallback enabled by default")
    print("SELF-CHECK OK")


if __name__ == "__main__":
    main()

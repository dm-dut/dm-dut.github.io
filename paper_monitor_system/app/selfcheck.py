from __future__ import annotations

from .config import DB_PATH, JOURNAL_LIST_PATH, REPO_ROOT, SYSTEM_ROOT, WEB_JSON_PATH
from .db import init_db
from .journals import enabled_journals, load_journal_list


def main() -> None:
    specs = load_journal_list()
    counts = {p: len(enabled_journals(p)) for p in ("sciencedirect", "springer", "ieee")}
    assert specs, "No enabled journals found in whitelist"
    assert JOURNAL_LIST_PATH.exists(), f"Missing journal list: {JOURNAL_LIST_PATH}"
    WEB_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    init_db()
    print(f"repo_root={REPO_ROOT}")
    print(f"system_root={SYSTEM_ROOT}")
    print(f"journal_list={JOURNAL_LIST_PATH} ({len(specs)} enabled)")
    print(f"providers={counts}")
    print(f"database={DB_PATH}")
    print(f"web_json={WEB_JSON_PATH}")
    print("SELF-CHECK OK")


if __name__ == "__main__":
    main()

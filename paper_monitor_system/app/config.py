from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def env_bool(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///paper_monitor_system/data/papers.db")
ELSEVIER_API_KEY = os.getenv("ELSEVIER_API_KEY", "").strip()
SPRINGER_API_KEY = os.getenv("SPRINGER_API_KEY", "").strip()
IEEE_API_KEY = os.getenv("IEEE_API_KEY", "").strip()
IEEE_QUERYTEXT = os.getenv("IEEE_QUERYTEXT", "").strip()

OVERLAP_DAYS = int(os.getenv("OVERLAP_DAYS", "3"))
EXPORT_DAYS = int(os.getenv("EXPORT_DAYS", "365"))
EXPORT_LIMIT = int(os.getenv("EXPORT_LIMIT", "20000"))
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "45"))
REQUEST_PAUSE_SECONDS = float(os.getenv("REQUEST_PAUSE_SECONDS", "0.15"))

ENABLE_SCIENCEDIRECT = env_bool("ENABLE_SCIENCEDIRECT", True)
ENABLE_SPRINGER = env_bool("ENABLE_SPRINGER", True)
ENABLE_IEEE = env_bool("ENABLE_IEEE", True)

# Journal whitelist. Only Enabled=1 rows are collected/exported.
JOURNAL_LIST_PATH = Path(os.getenv("JOURNAL_LIST_PATH", str(ROOT / "journal_list.xlsx")))
WHITELIST_REQUIRED = env_bool("WHITELIST_REQUIRED", True)

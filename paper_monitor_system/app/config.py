from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

SYSTEM_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SYSTEM_ROOT.parent
load_dotenv(SYSTEM_ROOT / ".env")

BUILD_ID = "LOCAL-2026.08.20-V6.1.1-CHROME-FIX"
SCHEMA_VERSION = "6.1-id-first"


def env_bool(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    return default if raw is None else raw.strip().lower() in {"1", "true", "yes", "y", "on"}


SPRINGER_API_KEY = os.getenv("SPRINGER_API_KEY", "").strip()

ENABLE_SCIENCEDIRECT = env_bool("ENABLE_SCIENCEDIRECT", True)
ENABLE_SPRINGER = env_bool("ENABLE_SPRINGER", True)
ENABLE_IEEE = env_bool("ENABLE_IEEE", True)

OVERLAP_DAYS = int(os.getenv("OVERLAP_DAYS", "1"))
EXPORT_DAYS = int(os.getenv("EXPORT_DAYS", "365"))
EXPORT_LIMIT = int(os.getenv("EXPORT_LIMIT", "20000"))
WHITELIST_REQUIRED = env_bool("WHITELIST_REQUIRED", True)

SPRINGER_BATCH_PAGE_SIZE = int(os.getenv("SPRINGER_BATCH_PAGE_SIZE", "20"))
SPRINGER_BATCH_MAX_PAGES_PER_DAY = int(os.getenv("SPRINGER_BATCH_MAX_PAGES_PER_DAY", "5"))
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "25"))
HTTP_RETRY_TOTAL = int(os.getenv("HTTP_RETRY_TOTAL", "2"))
HTTP_RETRY_BACKOFF = float(os.getenv("HTTP_RETRY_BACKOFF", "0.40"))
REQUEST_PAUSE_SECONDS = float(os.getenv("REQUEST_PAUSE_SECONDS", "0.10"))

# V6 reads only list/search pages for ScienceDirect and IEEE.
BROWSER_CHANNEL = os.getenv("BROWSER_CHANNEL", "").strip()
BROWSER_EXECUTABLE_PATH = os.getenv("BROWSER_EXECUTABLE_PATH", "").strip()
BROWSER_HEADLESS = env_bool("BROWSER_HEADLESS", False)
BROWSER_NAV_TIMEOUT_MS = int(os.getenv("BROWSER_NAV_TIMEOUT_MS", "45000"))
BROWSER_WAIT_MS = int(os.getenv("BROWSER_WAIT_MS", "1200"))
BROWSER_JOURNAL_DELAY_MS = int(os.getenv("BROWSER_JOURNAL_DELAY_MS", "3000"))
BROWSER_RANDOM_DELAY_MIN_MS = int(os.getenv("BROWSER_RANDOM_DELAY_MIN_MS", "3000"))
BROWSER_RANDOM_DELAY_MAX_MS = int(os.getenv("BROWSER_RANDOM_DELAY_MAX_MS", "8000"))
BROWSER_MAX_RESULTS = int(os.getenv("BROWSER_MAX_RESULTS", "20"))
BROWSER_KNOWN_STREAK_STOP = int(os.getenv("BROWSER_KNOWN_STREAK_STOP", "5"))


def _resolve(name: str, default: Path) -> Path:
    raw = os.getenv(name, "").strip()
    p = Path(raw).expanduser() if raw else default
    return p.resolve() if p.is_absolute() else (REPO_ROOT / p).resolve()


JOURNAL_LIST_PATH = _resolve("JOURNAL_LIST_PATH", SYSTEM_ROOT / "journal_list.xlsx")
WEB_JSON_PATH = _resolve("WEB_JSON_PATH", REPO_ROOT / "paper-monitor" / "data" / "online_papers.json")
DB_PATH = _resolve("PAPER_MONITOR_DB_PATH", SYSTEM_ROOT / "data" / "papers.db")
BROWSER_PROFILE_DIR = _resolve("BROWSER_PROFILE_DIR", SYSTEM_ROOT / "browser_profile")
DATABASE_URL = os.getenv("DATABASE_URL", "").strip() or f"sqlite:///{DB_PATH.as_posix()}"

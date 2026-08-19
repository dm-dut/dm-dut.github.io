from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

SYSTEM_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SYSTEM_ROOT.parent
load_dotenv(SYSTEM_ROOT / ".env")

BUILD_ID = "LOCAL-2026.08.19-V3"


def env_bool(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    return default if raw is None else raw.strip().lower() in {"1", "true", "yes", "y", "on"}


ELSEVIER_API_KEY = os.getenv("ELSEVIER_API_KEY", "").strip()
ELSEVIER_INSTTOKEN = os.getenv("ELSEVIER_INSTTOKEN", "").strip()
SPRINGER_API_KEY = os.getenv("SPRINGER_API_KEY", "").strip()
IEEE_API_KEY = os.getenv("IEEE_API_KEY", "").strip()
CROSSREF_MAILTO = os.getenv("CROSSREF_MAILTO", "").strip()
IEEE_SAVED_SEARCH_RSS_URL = os.getenv("IEEE_SAVED_SEARCH_RSS_URL", "").strip()

# Provider switches. LOCAL V3 is intentionally optimized around the channels
# that were verified from the user's local network: Springer Meta API, IEEE
# Saved Search RSS, and Crossref. ScienceDirect API/page remain optional only.
ENABLE_SCIENCEDIRECT = env_bool("ENABLE_SCIENCEDIRECT", True)
ENABLE_SPRINGER = env_bool("ENABLE_SPRINGER", True)
ENABLE_IEEE = env_bool("ENABLE_IEEE", True)
ENABLE_SCIENCEDIRECT_API = env_bool("ENABLE_SCIENCEDIRECT_API", False)
ENABLE_SCIENCEDIRECT_PAGE = env_bool("ENABLE_SCIENCEDIRECT_PAGE", False)
ENABLE_SCIENCEDIRECT_RSS = env_bool("ENABLE_SCIENCEDIRECT_RSS", True)
ENABLE_SPRINGER_API = env_bool("ENABLE_SPRINGER_API", True)
ENABLE_SPRINGER_BATCH_API = env_bool("ENABLE_SPRINGER_BATCH_API", True)
ENABLE_IEEE_API = env_bool("ENABLE_IEEE_API", False)
ENABLE_IEEE_CROSSREF_SUPPLEMENT = env_bool("ENABLE_IEEE_CROSSREF_SUPPLEMENT", False)
ENABLE_CROSSREF_FALLBACK = env_bool("ENABLE_CROSSREF_FALLBACK", True)

# Daily incremental windows. OVERLAP_DAYS=1 means yesterday..today (two
# calendar dates, inclusive). The Crossref discovery cap is also two days.
CROSSREF_DISCOVERY_DAYS = int(os.getenv("CROSSREF_DISCOVERY_DAYS", "2"))
OVERLAP_DAYS = int(os.getenv("OVERLAP_DAYS", "1"))
PENDING_RECHECK_DAYS = int(os.getenv("PENDING_RECHECK_DAYS", "60"))
PENDING_RECHECK_MIN_HOURS = int(os.getenv("PENDING_RECHECK_MIN_HOURS", "20"))
PENDING_RECHECK_LIMIT = int(os.getenv("PENDING_RECHECK_LIMIT", "200"))
EXPORT_DAYS = int(os.getenv("EXPORT_DAYS", "365"))
EXPORT_LIMIT = int(os.getenv("EXPORT_LIMIT", "20000"))

# Network behavior: limited retries and shorter timeouts prevent one slow
# endpoint from making the daily run appear hung.
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "20"))
REQUEST_PAUSE_SECONDS = float(os.getenv("REQUEST_PAUSE_SECONDS", "0.10"))
HTTP_RETRY_TOTAL = int(os.getenv("HTTP_RETRY_TOTAL", "2"))
HTTP_RETRY_BACKOFF = float(os.getenv("HTTP_RETRY_BACKOFF", "0.40"))

WHITELIST_REQUIRED = env_bool("WHITELIST_REQUIRED", True)

# Crossref batch strategy for the 39 Elsevier journals.
ELSEVIER_CROSSREF_MEMBER_ID = int(os.getenv("ELSEVIER_CROSSREF_MEMBER_ID", "78"))
CROSSREF_BATCH_ROWS = int(os.getenv("CROSSREF_BATCH_ROWS", "500"))
CROSSREF_BATCH_MAX_PAGES = int(os.getenv("CROSSREF_BATCH_MAX_PAGES", "30"))

# Springer Meta API batch strategy.
SPRINGER_BATCH_PAGE_SIZE = int(os.getenv("SPRINGER_BATCH_PAGE_SIZE", "100"))
SPRINGER_BATCH_MAX_PAGES = int(os.getenv("SPRINGER_BATCH_MAX_PAGES", "100"))


def _resolve(name: str, default: Path) -> Path:
    raw = os.getenv(name, "").strip()
    p = Path(raw).expanduser() if raw else default
    return p.resolve() if p.is_absolute() else (REPO_ROOT / p).resolve()


JOURNAL_LIST_PATH = _resolve("JOURNAL_LIST_PATH", SYSTEM_ROOT / "journal_list.xlsx")
WEB_JSON_PATH = _resolve("WEB_JSON_PATH", REPO_ROOT / "paper-monitor" / "data" / "online_papers.json")
DB_PATH = _resolve("PAPER_MONITOR_DB_PATH", SYSTEM_ROOT / "data" / "papers.db")
DATABASE_URL = os.getenv("DATABASE_URL", "").strip() or f"sqlite:///{DB_PATH.as_posix()}"


def ieee_rss_secret_map() -> dict[str, str]:
    """Backward-compatible optional map for per-journal RSS URLs."""
    raw = os.getenv("IEEE_RSS_FEEDS_JSON", "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return (
            {str(k).strip(): str(v).strip() for k, v in data.items() if str(v).strip()}
            if isinstance(data, dict)
            else {}
        )
    except json.JSONDecodeError:
        print("[ieee] WARNING: IEEE_RSS_FEEDS_JSON is not valid JSON; ignoring it")
        return {}

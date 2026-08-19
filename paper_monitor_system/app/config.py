from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

SYSTEM_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SYSTEM_ROOT.parent
load_dotenv(SYSTEM_ROOT / ".env")

BUILD_ID = "LOCAL-2026.08.19-V1"


def env_bool(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    return default if raw is None else raw.strip().lower() in {"1", "true", "yes", "y", "on"}


ELSEVIER_API_KEY = os.getenv("ELSEVIER_API_KEY", "").strip()
ELSEVIER_INSTTOKEN = os.getenv("ELSEVIER_INSTTOKEN", "").strip()
SPRINGER_API_KEY = os.getenv("SPRINGER_API_KEY", "").strip()
IEEE_API_KEY = os.getenv("IEEE_API_KEY", "").strip()
CROSSREF_MAILTO = os.getenv("CROSSREF_MAILTO", "").strip()
IEEE_SAVED_SEARCH_RSS_URL = os.getenv("IEEE_SAVED_SEARCH_RSS_URL", "").strip()

# Local-PC defaults. ScienceDirect API is worth trying again on a local / campus
# network, while IEEE remains Saved-Search-RSS first because the user's API key
# has returned 403 even in IEEE's own interactive tools.
ENABLE_SCIENCEDIRECT_API = env_bool("ENABLE_SCIENCEDIRECT_API", True)
ENABLE_SPRINGER_API = env_bool("ENABLE_SPRINGER_API", True)
ENABLE_IEEE_API = env_bool("ENABLE_IEEE_API", False)
ENABLE_CROSSREF_FALLBACK = env_bool("ENABLE_CROSSREF_FALLBACK", True)

ENABLE_SCIENCEDIRECT = env_bool("ENABLE_SCIENCEDIRECT", True)
ENABLE_SPRINGER = env_bool("ENABLE_SPRINGER", True)
ENABLE_IEEE = env_bool("ENABLE_IEEE", True)
CROSSREF_DISCOVERY_DAYS = int(os.getenv("CROSSREF_DISCOVERY_DAYS", "30"))
OVERLAP_DAYS = int(os.getenv("OVERLAP_DAYS", "3"))
EXPORT_DAYS = int(os.getenv("EXPORT_DAYS", "365"))
EXPORT_LIMIT = int(os.getenv("EXPORT_LIMIT", "20000"))
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "45"))
REQUEST_PAUSE_SECONDS = float(os.getenv("REQUEST_PAUSE_SECONDS", "0.35"))
WHITELIST_REQUIRED = env_bool("WHITELIST_REQUIRED", True)


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

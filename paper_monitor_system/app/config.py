from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

SYSTEM_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SYSTEM_ROOT.parent
load_dotenv(SYSTEM_ROOT / ".env")


def env_bool(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


ELSEVIER_API_KEY = os.getenv("ELSEVIER_API_KEY", "").strip()
# Optional institutional token. This can be required when Elsevier resources are
# entitlement-restricted outside the institution network (e.g. GitHub runners).
ELSEVIER_INSTTOKEN = os.getenv("ELSEVIER_INSTTOKEN", "").strip()
SPRINGER_API_KEY = os.getenv("SPRINGER_API_KEY", "").strip()
IEEE_API_KEY = os.getenv("IEEE_API_KEY", "").strip()
IEEE_QUERYTEXT = os.getenv("IEEE_QUERYTEXT", "").strip()

CROSSREF_MAILTO = os.getenv("CROSSREF_MAILTO", "").strip()
ENABLE_CROSSREF_FALLBACK = env_bool("ENABLE_CROSSREF_FALLBACK", True)
CROSSREF_DISCOVERY_DAYS = int(os.getenv("CROSSREF_DISCOVERY_DAYS", "30"))

OVERLAP_DAYS = int(os.getenv("OVERLAP_DAYS", "3"))
EXPORT_DAYS = int(os.getenv("EXPORT_DAYS", "365"))
EXPORT_LIMIT = int(os.getenv("EXPORT_LIMIT", "20000"))
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "45"))
REQUEST_PAUSE_SECONDS = float(os.getenv("REQUEST_PAUSE_SECONDS", "0.60"))

ENABLE_SCIENCEDIRECT = env_bool("ENABLE_SCIENCEDIRECT", True)
ENABLE_SPRINGER = env_bool("ENABLE_SPRINGER", True)
ENABLE_IEEE = env_bool("ENABLE_IEEE", True)
WHITELIST_REQUIRED = env_bool("WHITELIST_REQUIRED", True)


def _resolve_path_env(name: str, default: Path) -> Path:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default.resolve()
    p = Path(raw).expanduser()
    return p.resolve() if p.is_absolute() else (REPO_ROOT / p).resolve()


JOURNAL_LIST_PATH = _resolve_path_env("JOURNAL_LIST_PATH", SYSTEM_ROOT / "journal_list.xlsx")
WEB_JSON_PATH = _resolve_path_env(
    "WEB_JSON_PATH", REPO_ROOT / "paper-monitor" / "data" / "online_papers.json"
)
DB_PATH = _resolve_path_env("PAPER_MONITOR_DB_PATH", SYSTEM_ROOT / "data" / "papers.db")
DATABASE_URL = os.getenv("DATABASE_URL", "").strip() or f"sqlite:///{DB_PATH.as_posix()}"

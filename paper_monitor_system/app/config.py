from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

SYSTEM_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SYSTEM_ROOT.parent
load_dotenv(SYSTEM_ROOT / '.env')

BUILD_ID = 'LOCAL-2026.08.19-V4-CROSSREF'
DB_SCHEMA_VERSION = 4

CROSSREF_MAILTO = os.getenv('CROSSREF_MAILTO', '').strip()
CROSSREF_API = os.getenv('CROSSREF_API', 'https://api.crossref.org').rstrip('/')
CROSSREF_ROWS = max(20, min(1000, int(os.getenv('CROSSREF_ROWS', '1000'))))
CROSSREF_MAX_PAGES = max(1, int(os.getenv('CROSSREF_MAX_PAGES', '30')))
CROSSREF_DISCOVERY_DAYS = max(1, int(os.getenv('CROSSREF_DISCOVERY_DAYS', '2')))
OVERLAP_DAYS = max(0, int(os.getenv('OVERLAP_DAYS', '1')))
HTTP_TIMEOUT = max(5, int(os.getenv('HTTP_TIMEOUT', '20')))
HTTP_RETRY_TOTAL = max(0, int(os.getenv('HTTP_RETRY_TOTAL', '2')))
HTTP_RETRY_BACKOFF = max(0.0, float(os.getenv('HTTP_RETRY_BACKOFF', '0.5')))
REQUEST_PAUSE_SECONDS = max(0.0, float(os.getenv('REQUEST_PAUSE_SECONDS', '0.05')))
EXPORT_DAYS = max(1, int(os.getenv('EXPORT_DAYS', '365')))
EXPORT_LIMIT = max(1, int(os.getenv('EXPORT_LIMIT', '20000')))
WHITELIST_REQUIRED = True

# Crossref member IDs verified against Crossref member/participation pages.
CROSSREF_MEMBERS = {
    'sciencedirect': 78,   # Elsevier BV
    'springer': 297,       # Springer Science and Business Media LLC
    'ieee': 263,           # Institute of Electrical and Electronics Engineers (IEEE)
}
PROVIDER_LABELS = {
    'sciencedirect': 'Elsevier',
    'springer': 'Springer Nature',
    'ieee': 'IEEE',
}


def _resolve(name: str, default: Path) -> Path:
    raw = os.getenv(name, '').strip()
    p = Path(raw).expanduser() if raw else default
    return p.resolve() if p.is_absolute() else (REPO_ROOT / p).resolve()


JOURNAL_LIST_PATH = _resolve('JOURNAL_LIST_PATH', SYSTEM_ROOT / 'journal_list.xlsx')
WEB_JSON_PATH = _resolve('WEB_JSON_PATH', REPO_ROOT / 'paper-monitor' / 'data' / 'online_papers.json')
DB_PATH = _resolve('PAPER_MONITOR_DB_PATH', SYSTEM_ROOT / 'data' / 'papers.db')
RESET_FLAG_PATH = SYSTEM_ROOT / 'data' / 'RESET_TO_V4.flag'
DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"

#!/usr/bin/env python3
"""
Update data/scholar_stats.json.

Recommended stable option:
- Manually edit scholar_stats.json when needed, or
- Replace this script with a SerpAPI request if you use SerpAPI.

Google Scholar has no official public API and may block automated scraping.
This placeholder keeps your GitHub Action structure clean without risking brittle scraping.
"""
import json
from datetime import date
from pathlib import Path

path = Path("data/scholar_stats.json")
if not path.exists():
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"citations":"—","h_index":"—","i10_index":"—","updated":str(date.today())}
else:
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("updated", str(date.today()))

path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print("Scholar stats preserved/updated:", path)

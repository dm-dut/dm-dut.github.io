import os
import sys
import json
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.database import init

CONFIG_DIR = os.path.join(ROOT, "config")
WEB_DIR = os.path.join(ROOT, "web")
DB_DIR = os.path.join(ROOT, "database")

os.makedirs(WEB_DIR, exist_ok=True)


def clean(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def write_json(filename, data):
    with open(
        os.path.join(WEB_DIR, filename),
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )


# 1. Generate journal_order.json from Excel row order.
journals = pd.read_excel(
    os.path.join(CONFIG_DIR, "journals.xlsx")
)

journal_order = {}

for idx, (_, row) in enumerate(
    journals.iterrows(),
    start=1,
):
    name = clean(row.get("Journal", ""))

    if name and name not in journal_order:
        journal_order[name] = idx

write_json("journal_order.json", journal_order)


# 2. Rebuild papers.json from the existing SQLite database.
# No Crossref requests are made.
conn = init(os.path.join(DB_DIR, "papers.db"))

rows = conn.execute(
    "SELECT * FROM papers"
).fetchall()

papers = []

for row in rows:
    if len(row) < 8:
        raise RuntimeError(
            "The papers table has fewer than 8 columns. "
            "Please check core/database.py."
        )

    papers.append({
        "doi": clean(row[0]),
        "title": clean(row[1]),
        "authors": clean(row[2]),
        "journal": clean(row[3]),
        "category": clean(row[4]),
        "publisher": clean(row[5]),
        "online_date": clean(row[6]),
        "fetched_date": clean(row[7]),
    })

write_json("papers.json", papers)

print(
    f"Rebuilt papers.json with {len(papers)} papers."
)
print(
    f"Generated journal_order.json with "
    f"{len(journal_order)} journals."
)

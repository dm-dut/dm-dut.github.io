import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

DB_FILE = ROOT / "database" / "papers.db"
OUTPUT_FILE = ROOT / "web" / "papers.json"

WEB_PAPER_LIMIT = 5000


def clean(value):
    return "" if value is None else str(value).strip()


conn = sqlite3.connect(DB_FILE)

rows = conn.execute(
    """
    SELECT
        doi,
        title,
        authors,
        journal,
        category,
        publisher,
        online_date,
        first_seen,
        volume,
        number,
        pages,
        article_number
    FROM papers
    ORDER BY
        first_seen DESC,
        rowid DESC
    LIMIT ?
    """,
    (WEB_PAPER_LIMIT,)
).fetchall()

conn.close()


papers = []

for row in rows:
    papers.append({
        "doi": clean(row[0]),
        "title": clean(row[1]),
        "authors": clean(row[2]),
        "journal": clean(row[3]),
        "category": clean(row[4]),
        "publisher": clean(row[5]),
        "online_date": clean(row[6]),
        "fetched_date": clean(row[7]),
        "volume": clean(row[8]),
        "number": clean(row[9]),
        "pages": clean(row[10]),
        "article_number": clean(row[11]),
    })


with open(
    OUTPUT_FILE,
    "w",
    encoding="utf-8"
) as f:
    json.dump(
        papers,
        f,
        ensure_ascii=False,
        indent=2
    )


print(
    f"Rebuilt papers.json: {len(papers)} papers"
)

print(
    f"Output: {OUTPUT_FILE}"
)
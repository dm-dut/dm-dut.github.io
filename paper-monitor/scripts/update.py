import os
import sys
import json
import datetime
import html

import pandas as pd
import yaml


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from collectors.crossref import fetch
from core.database import init, exists


CONFIG_DIR = os.path.join(ROOT, "config")
WEB_DIR = os.path.join(ROOT, "web")
DB_DIR = os.path.join(ROOT, "database")
LOG_DIR = os.path.join(ROOT, "logs")

for folder in (WEB_DIR, DB_DIR, LOG_DIR):
    os.makedirs(folder, exist_ok=True)


GMT8_TZ = datetime.timezone(datetime.timedelta(hours=8))


def clean(value):
    if pd.isna(value):
        return ""

    value = str(value)

    # Decode HTML entities:
    # &amp; -> &
    # &lt;  -> <
    # &gt;  -> >
    value = html.unescape(value)

    # Normalize spaces
    value = " ".join(value.split())

    return value.strip()


def gmt8_now():
    return datetime.datetime.now(GMT8_TZ)


def read_settings():
    settings = {
        "days": 3,
        "rows": 50,
    }

    path = os.path.join(CONFIG_DIR, "settings.yaml")

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
            settings.update(loaded)

    return settings


def read_journals():
    path = os.path.join(CONFIG_DIR, "journals.xlsx")
    return pd.read_excel(path)


def build_journal_order(journals):
    """
    Journal order is independent from papers.json.
    It follows the physical row order in config/journals.xlsx.
    """
    order = {}

    for idx, (_, row) in enumerate(journals.iterrows(), start=1):
        name = clean(row.get("Journal", ""))

        if name and name not in order:
            order[name] = idx

    return order


def write_journal_order(order):
    path = os.path.join(WEB_DIR, "journal_order.json")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            order,
            f,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )


def ensure_metadata_columns(conn):
    """
    Upgrade an existing papers table in place.

    Older databases contain 8 columns:
        doi, title, authors, journal, category, publisher,
        online_date, first_seen

    This function adds:
        volume, number, pages, article_number

    Existing data are preserved.
    """
    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(papers)").fetchall()
    }

    new_columns = (
        ("volume", "TEXT"),
        ("number", "TEXT"),
        ("pages", "TEXT"),
        ("article_number", "TEXT"),
    )

    changed = False

    for name, column_type in new_columns:
        if name not in columns:
            conn.execute(
                f'ALTER TABLE papers ADD COLUMN "{name}" {column_type}'
            )
            print(f"Database upgraded: added column '{name}'")
            changed = True

    if changed:
        conn.commit()


def read_all_db_rows(conn):
    """
    Read all stored papers using explicit column names.

    The database now contains:
        doi, title, authors, journal, category, publisher,
        online_date, first_seen, volume, number, pages

    Existing historical papers automatically have blank values for
    volume/number/pages/article_number until those metadata are backfilled.
    """
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
        """
    ).fetchall()

    result = []

    for row in rows:
        result.append({
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

    return result


def write_json(filename, data):
    path = os.path.join(WEB_DIR, filename)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )


settings = read_settings()
days = int(settings.get("days", 3))
rows = int(settings.get("rows", 50))

journals = read_journals()
journal_order = build_journal_order(journals)
write_journal_order(journal_order)

conn = init(os.path.join(DB_DIR, "papers.db"))

# Upgrade old database without deleting/rebuilding it.
ensure_metadata_columns(conn)

# Snapshot BEFORE this update.
previous_papers = read_all_db_rows(conn)
write_json("previous_papers.json", previous_papers)

first_run = len(previous_papers) == 0

print("=" * 72)
print("Paper Monitor v15.0")
print("Mode:", "INITIAL" if first_run else "INCREMENTAL")
print("Journals:", len(journals))
print("Days:", days)
print("Rows:", rows)
print("=" * 72)

today_gmt8 = gmt8_now().strftime("%Y-%m-%d")

new_papers = []
total_fetched = 0
successful = 0
failed = []

for i, (_, row) in enumerate(journals.iterrows(), start=1):
    journal_name = clean(row.get("Journal", ""))
    issn = clean(row.get("pISSN", ""))
    category = clean(row.get("Category", ""))
    publisher = clean(row.get("Publisher", ""))

    print(f"[{i}/{len(journals)}] {journal_name}")
    print(f"  ISSN: {issn}")

    if not issn:
        failed.append({
            "journal": journal_name,
            "issn": issn,
            "error": "Missing pISSN",
        })

        print("  Status: FAILED (missing pISSN)")
        continue

    try:
        fetched = fetch(
            issn,
            days=days,
            rows=rows,
        )

        total_fetched += len(fetched)
        new_count = 0

        for paper in fetched:
            doi = clean(paper.get("doi", ""))

            if not doi:
                continue

            if exists(conn, doi):
                continue

            title = clean(paper.get("title", ""))
            authors = clean(paper.get("authors", ""))
            online_date = clean(paper.get("online_date", ""))

            # Additional Crossref bibliographic metadata.
            #
            # Crossref normally calls these fields:
            #   volume
            #   issue
            #   page
            #
            # The Paper Monitor JSON uses:
            #   volume
            #   number
            #   pages
            #
            # The fallbacks below allow crossref.py to return either naming
            # convention.
            volume = clean(
                paper.get("volume", "")
            )

            number = clean(
                paper.get(
                    "number",
                    paper.get("issue", "")
                )
            )

            pages = clean(
                paper.get(
                    "pages",
                    paper.get("page", "")
                )
            )

            article_number = clean(
                paper.get(
                    "article_number",
                    paper.get("article-number", "")
                )
            )

            # Use the Excel journal name so journal_order.json
            # matches the stored/displayed journal consistently.
            stored_journal = journal_name

            conn.execute(
                """
                INSERT INTO papers (
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
                )
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    doi,
                    title,
                    authors,
                    stored_journal,
                    category,
                    publisher,
                    online_date,
                    today_gmt8,
                    volume,
                    number,
                    pages,
                    article_number,
                ),
            )

            new_item = {
                "doi": doi,
                "title": title,
                "authors": authors,
                "journal": stored_journal,
                "category": category,
                "publisher": publisher,
                "online_date": online_date,
                "fetched_date": today_gmt8,
                "volume": volume,
                "number": number,
                "pages": pages,
                "article_number": article_number,
            }

            new_papers.append(new_item)
            new_count += 1

        conn.commit()
        successful += 1

        print(f"  Fetched: {len(fetched)}")
        print(f"  New: {new_count}")
        print("  Status: OK")

    except Exception as exc:
        failed.append({
            "journal": journal_name,
            "issn": issn,
            "error": str(exc),
        })

        print(f"  Status: FAILED ({exc})")


# Export all stored papers after the update.
all_papers = read_all_db_rows(conn)

write_json("papers.json", all_papers)
write_json("new_papers.json", new_papers)

updated = gmt8_now().strftime("%Y-%m-%d %H:%M:%S")

with open(
    os.path.join(WEB_DIR, "update_time.json"),
    "w",
    encoding="utf-8",
) as f:
    json.dump(
        {
            "updated": updated,
            "timezone": "UTC+8",
            "count": len(new_papers),
        },
        f,
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    )


with open(
    os.path.join(LOG_DIR, "failed_journals.json"),
    "w",
    encoding="utf-8",
) as f:
    json.dump(
        failed,
        f,
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    )


print("=" * 72)
print("Update Finished")
print("Successful journals:", successful)
print("Failed journals:", len(failed))
print("Fetched papers:", total_fetched)
print("New papers:", len(new_papers))
print("Total stored papers:", len(all_papers))
print("Fetched date for new papers:", today_gmt8, "(GMT+8)")
print("Update time:", updated, "(UTC+8)")
print("=" * 72)

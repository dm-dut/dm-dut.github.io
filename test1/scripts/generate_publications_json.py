#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate data/publications.json from the publication Excel database.

Design choices
--------------
- Uses only Python standard library (zipfile + XML parser), so it does not require pandas/openpyxl.
- Outputs English records only.
- Excludes working papers (Type == 工作).
- Keeps formally published/accepted records: journal articles, conference papers, monographs/book chapters. If the database has a status field in the future, draft/rejected/under-review records will be excluded automatically.
- Creates DOI links as https://doi.org/{DOI}; if DOI is absent, link is blank.
"""

from __future__ import annotations

import argparse
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def clean(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


def col_to_idx(cell_ref: str) -> int:
    letters = "".join(re.findall(r"[A-Z]+", cell_ref))
    idx = 0
    for char in letters:
        idx = idx * 26 + ord(char) - 64
    return idx - 1


def read_first_sheet(path: Path, max_cols: int = 30) -> list[list[object]]:
    with zipfile.ZipFile(path) as zf:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root.findall("a:si", NS):
                shared.append("".join(t.text or "" for t in si.findall(".//a:t", NS)))

        root = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
        rows: list[list[object]] = []
        for row in root.findall("a:sheetData/a:row", NS):
            values = {}
            for cell in row.findall("a:c", NS):
                col = col_to_idx(cell.attrib["r"])
                cell_type = cell.attrib.get("t")
                v = cell.find("a:v", NS)
                value = None
                if v is not None:
                    raw = v.text or ""
                    if cell_type == "s":
                        value = shared[int(raw)]
                    else:
                        try:
                            number = float(raw)
                            value = int(number) if number.is_integer() else number
                        except Exception:
                            value = raw
                elif cell_type == "inlineStr":
                    value = "".join(t.text or "" for t in cell.findall(".//a:t", NS))
                values[col] = value
            if values:
                width = max(max_cols, max(values.keys()) + 1)
                rows.append([values.get(i) for i in range(width)])
        return rows


def invert_name(name: str) -> str:
    name = clean(name)
    if not name:
        return ""
    if "," in name:
        family, given = [p.strip() for p in name.split(",", 1)]
        if given:
            return f"{given} {family}"
    return name


def author_key(name: str) -> str:
    return re.sub(r"\s+", " ", invert_name(name).lower()).strip()


def parse_authors(author_string: str, corresponding_string: str) -> list[str]:
    corresponding = {author_key(x) for x in clean(corresponding_string).split(";") if clean(x)}
    authors: list[str] = []
    for author in clean(author_string).split(";"):
        formatted = invert_name(author)
        if not formatted:
            continue
        if author_key(author) in corresponding:
            formatted += "*"
        authors.append(formatted)
    return authors


def normalize_doi(value: str) -> str:
    doi = clean(value)
    if not doi or doi.lower() in {"none", "nan", "#name?"}:
        return ""
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi, flags=re.I).strip()
    return doi


def is_yes(value) -> bool:
    return clean(value) in {"是", "yes", "Yes", "YES", "1", "true", "True"}



def is_formally_published_or_accepted(row: dict) -> bool:
    """Return True for published/accepted records.

    The current database does not include a status column, so all non-working
    monograph/book-chapter/journal/conference records are treated as formal records.
    If a future database adds Status/Publication_Status/状态, this function excludes
    under-review, submitted, rejected, draft, and working-paper records.
    """
    status = clean(row.get("Status") or row.get("Publication_Status") or row.get("状态"))
    if not status:
        return True
    bad = {"under review", "submitted", "rejected", "draft", "working", "工作", "投稿", "在投", "拒稿", "草稿"}
    good = {"published", "accepted", "正式接收", "已发表", "online", "in press"}
    s = status.lower()
    if any(x in s for x in bad):
        return False
    return True if any(x in s for x in good) else True

def build_indexes(row: dict) -> tuple[list[str], list[str]]:
    indexes: list[str] = []
    for field in ["SCI", "SSCI", "EI", "CSSCI", "ISTP"]:
        if is_yes(row.get(field)):
            indexes.append(field)

    fms = clean(row.get("FMS"))
    if fms:
        indexes.append(f"FMS {fms}")

    abs_value = clean(row.get("ABS "))
    if abs_value:
        indexes.append(f"ABS {abs_value}")

    impact_factor = clean(row.get("IF"))
    if impact_factor and impact_factor.lower() not in {"nan", "#name?"}:
        indexes.append(f"IF={impact_factor}")

    labels: list[str] = []
    if is_yes(row.get("ESI_Highly_Cited")):
        labels.append("ESI Highly Cited Paper")
    if is_yes(row.get("ESI_Hot")):
        labels.append("ESI Hot Paper")
    return indexes, labels


def publication_record(row: dict, index: int) -> dict:
    type_map = {
        "期刊": "Journal Article",
        "会议": "Conference Paper",
        "专著": "Monograph",
        "章节": "Book Chapter",
    }
    doi = normalize_doi(row.get("DOI"))
    indexes, labels = build_indexes(row)

    year = clean(row.get("Year"))
    try:
        year_value = int(float(year)) if year else None
    except Exception:
        year_value = year or None

    return {
        "id": f"pub-{index:03d}",
        "type": type_map.get(clean(row.get("Type")), clean(row.get("Type")) or "Other"),
        "year": year_value,
        "authors": parse_authors(row.get("Author_English"), row.get("Corresponding_Author")),
        "title": clean(row.get("Title_English")).replace("\n", " "),
        "venue": clean(row.get("Source_English")),
        "volume": clean(row.get("Volume")),
        "issue": clean(row.get("Number")),
        "pages": clean(row.get("Page")),
        "doi": doi,
        "link": f"https://doi.org/{doi}" if doi else "",
        "indexes": indexes,
        "labels": labels,
        "note": clean(row.get("Note_English")),
        "isbn": clean(row.get("ISBN")),
        "conference_date": clean(row.get("Conference_Date")),
        "conference_address": clean(row.get("Conference_Address")),
        "address": clean(row.get("Address")),
        "corresponding_author_note": "* corresponding author" if clean(row.get("Corresponding_Author")) else "",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="publication_database.xlsx", help="Path to publication Excel database")
    parser.add_argument("--output", default="data/publications.json", help="Output JSON path")
    args = parser.parse_args()

    rows = read_first_sheet(Path(args.input), max_cols=30)
    if not rows:
        raise SystemExit("No rows found in the Excel file.")

    headers = [clean(h) for h in rows[0]]
    records = []
    for raw_row in rows[1:]:
        row = dict(zip(headers, raw_row))
        if clean(row.get("Language")) != "英文":
            continue
        if clean(row.get("Type")) == "工作":
            continue
        if clean(row.get("Type")) not in {"期刊", "会议", "专著", "章节"}:
            continue
        if not is_formally_published_or_accepted(row):
            continue
        records.append(publication_record(row, len(records) + 1))

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generated {len(records)} publication records: {out}")


if __name__ == "__main__":
    main()

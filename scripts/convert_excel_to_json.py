#!/usr/bin/env python3
"""
Convert homepage Excel files to JSON used by the website.

Usage:
  python scripts/convert_excel_to_json.py --excel homepage_content.xlsx --out data
  python scripts/convert_excel_to_json.py --excel homepage_content.xlsx --publications-xlsx publications.xlsx --out data

Notes:
- Awards are exported record by record; year ranges or repeated titles are not merged.
- profile / links / scholar settings are intentionally NOT maintained in Excel.
- Publications are read from your existing publication Excel and normalized to data/publications.json.
"""
import argparse, json, re
from pathlib import Path
import pandas as pd

SHEETS = {
    "News": ["date","category","content","link","link_text","links_json","show_on_home"],
    "Awards": ["year","title","organization"],
    "Grants": ["no","role","title","funder","grant_no","amount","period"],
    "Services": ["category","role","organization","item","period"],
    "Group": ["category","name","note","link"],
    "Projects": ["category","title","role","organization","grant_no","amount","period","note"],
}

PUB_ALIASES = {
    "year": ["year", "Year"],
    "type": ["type", "Type", "category", "Category", "Publication_Type", "pub_type"],
    "authors": ["authors", "Authors", "Authors_EN", "author_en", "English Authors"],
    "title": ["title", "Title", "Title_EN", "Article_Title", "Paper_Title", "English Title"],
    "venue": ["venue", "Venue", "Journal", "Journal_EN", "Conference", "Publisher", "Source title"],
    "volume": ["volume", "Volume"],
    "issue": ["issue", "Issue"],
    "pages": ["pages", "Pages", "Page"],
    "doi": ["doi", "DOI"],
    "link": ["link", "Link", "URL", "url"],
    "indexes": ["indexes", "Index", "Indices", "SCI_SSCI_EI", "indexed_by"],
    "labels": ["labels", "Labels", "ABS_FMS_IF", "notes_index"],
    "note": ["note", "Note", "Notes", "Status"],
}

def clean_value(x):
    if pd.isna(x):
        return ""
    if hasattr(x, "strftime"):
        return x.strftime("%Y-%m-%d")
    s = str(x).strip()
    if s.endswith(".0") and re.fullmatch(r"\d+\.0", s):
        s = s[:-2]
    return s

def records_from_sheet(xlsx, sheet, columns):
    try:
        df = pd.read_excel(xlsx, sheet_name=sheet, dtype=object)
    except ValueError:
        return []
    df = df.dropna(how="all")
    out = []
    for _, row in df.iterrows():
        rec = {c: clean_value(row.get(c, "")) for c in columns}
        if sheet == "News":
            raw_links = rec.pop("links_json", "")
            links = []
            if raw_links:
                try:
                    parsed = json.loads(raw_links)
                    if isinstance(parsed, list):
                        links = [clean_value(x) for x in parsed if clean_value(x)]
                except Exception:
                    links = [x.strip() for x in str(raw_links).split(";") if x.strip()]
            if not links and rec.get("link"):
                links = [rec.get("link")]
            if links:
                rec["links"] = links
                rec["link"] = links[0]
            if not rec.get("link_text"):
                rec["link_text"] = "↗" if links else ""
        if any(rec.values()):
            out.append(rec)
    return out

def pick(row, aliases):
    for name in aliases:
        if name in row and clean_value(row[name]):
            return clean_value(row[name])
    return ""

def normalize_publications(pub_xlsx):
    # Read all sheets and concatenate, allowing your current Excel to keep separate sheets
    xls = pd.ExcelFile(pub_xlsx)
    all_records = []
    for sheet in xls.sheet_names:
        df = pd.read_excel(pub_xlsx, sheet_name=sheet, dtype=object).dropna(how="all")
        if df.empty:
            continue
        for _, row in df.iterrows():
            r = row.to_dict()
            rec = {field: pick(r, aliases) for field, aliases in PUB_ALIASES.items()}
            # If sheet names are Journal / Conference / Working Papers etc., use them as type when no type column exists.
            if not rec["type"]:
                rec["type"] = sheet
            if rec["title"] or rec["authors"] or rec["venue"]:
                all_records.append(rec)
    def sort_key(p):
        try:
            y = int(float(p.get("year") or 0))
        except Exception:
            y = 0
        return -y
    all_records.sort(key=sort_key)
    return all_records

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--excel", required=True, help="Homepage content Excel, e.g., homepage_content.xlsx")
    ap.add_argument("--publications-xlsx", default="", help="Optional existing publication Excel")
    ap.add_argument("--out", default="data", help="Output JSON folder")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    for sheet, cols in SHEETS.items():
        records = records_from_sheet(args.excel, sheet, cols)
        # projects are optional; skip empty file if no records
        if records or sheet != "Projects":
            (out / f"{sheet.lower()}.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.publications_xlsx:
        pubs = normalize_publications(args.publications_xlsx)
        (out / "publications.json").write_text(json.dumps(pubs, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote {len(pubs)} publication records.")
    print(f"JSON files written to {out}")

if __name__ == "__main__":
    main()

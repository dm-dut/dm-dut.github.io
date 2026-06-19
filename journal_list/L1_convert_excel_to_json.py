import pandas as pd
from pathlib import Path

# 当前 Python 文件所在目录：根目录/journal_list
SCRIPT_DIR = Path(__file__).resolve().parent

# 根目录
ROOT_DIR = SCRIPT_DIR.parent

# Excel 文件目录：根目录/journal_list
EXCEL_DIR = ROOT_DIR / "journal_list"

# JSON 输出目录：根目录/data
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def excel_to_json(excel_path, json_path):
    df = pd.read_excel(excel_path).fillna("")
    df.to_json(json_path, orient="records", force_ascii=False, indent=2)


# AJG
excel_to_json(
    EXCEL_DIR / "AJG2024.xlsx",
    DATA_DIR / "ajg.json"
)

# CCF
excel_to_json(
    EXCEL_DIR / "CCF2026.xlsx",
    DATA_DIR / "ccf.json"
)

# FMS
excel_to_json(
    EXCEL_DIR / "FMS2025.xlsx",
    DATA_DIR / "fms.json"
)

print("JSON 文件已生成")
print(f"输出目录：{DATA_DIR}")

# file_path = "JCR2026-web.xlsx"
# jcr_df = pd.read_excel(file_path)
#
# def clean(x):
#     return str(x).strip() if pd.notna(x) else ""
#
# def split_cat(cat):
#     if not cat:
#         return []
#     return [c.strip() for c in str(cat).replace(";", ",").split(",") if c.strip()]
#
# data = []
#
# for _, r in jcr_df.iterrows():
#
#     data.append({
#         "journal": clean(r.get("Journal name")),
#         "issn": clean(r.get("ISSN")),
#         "eissn": clean(r.get("eISSN")),
#         "categories": split_cat(r.get("Category")),
#         "jif": clean(r.get("2025 JIF")),
#         "jif5": clean(r.get("5-year JIF")),
#         "quartile": clean(r.get("JIF quartile"))
#     })
#
# jcr_df.to_json("data/jcr.json", orient="records", force_ascii=False)
#
# print("JCR JSON生成完成")

# -*- coding: utf-8 -*-
"""
从 JCR2026-web.xlsx 的 Category_Quartiles sheet 生成拆分后的 JCR JSON 文件。

输出结构：
data/jcr/categories.json
data/jcr/index.json
data/jcr/category/*.json

说明：
1. categories.json：只存 JCR 分类名称、对应文件名和条目数量，用于网页生成下拉框。
2. category/*.json：每个分类一个 JSON 文件，用于按分类浏览。
3. index.json：轻量期刊索引，用于 Journal name / ISSN / eISSN 全局检索。
"""

import json
import re
from pathlib import Path

import pandas as pd


EXCEL_FILE = "JCR2026-web.xlsx"
SHEET_NAME = "Category_Quartiles"

OUTPUT_DIR = Path("../data") / "jcr"
CATEGORY_DIR = OUTPUT_DIR / "category"

PRIORITY_CATEGORY = "OPERATIONS RESEARCH & MANAGEMENT SCIENCE"


COLUMN_ALIASES = {
    "journal": ["Journal name", "Journal Name", "journal name", "journal", "期刊名称"],
    "issn": ["ISSN", "issn"],
    "eissn": ["eISSN", "EISSN", "e-ISSN", "E-ISSN", "eissn"],
    "category": ["Category", "category", "JCR Category", "Web of Science Category", "分类"],
    "edition": ["Edition", "edition"],
    "jif": ["2025 JIF", "JIF", "Journal Impact Factor", "影响因子"],
    "jif5": ["5-year JIF", "5-Year JIF", "Five-year JIF", "5 Year JIF", "五年影响因子"],
    "quartile": ["JIF quartile", "JIF Quartile", "Quartile", "分区"],
    "rank": ["JIF rank", "JIF Rank", "Rank", "排名"],
}


def normalize_col_name(name):
    return re.sub(r"\s+", "", str(name).strip().lower())


def find_column(df, aliases, required=False):
    col_map = {normalize_col_name(c): c for c in df.columns}

    for alias in aliases:
        key = normalize_col_name(alias)
        if key in col_map:
            return col_map[key]

    if required:
        raise ValueError(f"未找到必要字段：{aliases}")

    return None


def clean(value):
    if pd.isna(value):
        return ""

    text = str(value).strip()

    if text.lower() in {"nan", "none"}:
        return ""

    return text


def clean_number(value):
    if pd.isna(value):
        return ""

    text = str(value).strip()

    if text == "" or text.lower() in {"nan", "none", "na", "n/a", "-", "—"}:
        return ""

    try:
        num = float(text)
        if num.is_integer():
            return int(num)
        return num
    except Exception:
        return text


def slugify(text):
    text = clean(text).lower()
    text = text.replace("&", "and")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "unknown"


def normalize_issn(value):
    return clean(value).lower().replace("-", "").replace(" ", "")


def normalize_title(value):
    return re.sub(r"\s+", " ", clean(value).lower())


def category_priority_key(category):
    is_priority = category.upper() == PRIORITY_CATEGORY
    return (0 if is_priority else 1, category.lower())


def build_record(row, cols):
    return {
        "Journal name": clean(row.get(cols["journal"], "")) if cols["journal"] else "",
        "ISSN": clean(row.get(cols["issn"], "")) if cols["issn"] else "",
        "eISSN": clean(row.get(cols["eissn"], "")) if cols["eissn"] else "",
        "Category": clean(row.get(cols["category"], "")) if cols["category"] else "",
        "Edition": clean(row.get(cols["edition"], "")) if cols["edition"] else "",
        "2025 JIF": clean_number(row.get(cols["jif"], "")) if cols["jif"] else "",
        "5-year JIF": clean_number(row.get(cols["jif5"], "")) if cols["jif5"] else "",
        "JIF quartile": clean(row.get(cols["quartile"], "")) if cols["quartile"] else "",
        "JIF rank": clean(row.get(cols["rank"], "")) if cols["rank"] else "",
    }


def get_journal_key(record):
    """
    同一期刊可能因为多个 Category 重复出现。
    优先用 ISSN，其次 eISSN，最后用期刊名。
    """
    issn = normalize_issn(record.get("ISSN", ""))
    eissn = normalize_issn(record.get("eISSN", ""))
    title = normalize_title(record.get("Journal name", ""))

    if issn:
        return f"issn:{issn}"

    if eissn:
        return f"eissn:{eissn}"

    return f"title:{title}"


def main():
    excel_path = Path(EXCEL_FILE)

    if not excel_path.exists():
        raise FileNotFoundError(f"未找到文件：{excel_path.resolve()}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CATEGORY_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_excel(excel_path, sheet_name=SHEET_NAME)
    df.columns = [str(c).strip() for c in df.columns]

    cols = {
        key: find_column(df, aliases, required=(key in {"journal", "category"}))
        for key, aliases in COLUMN_ALIASES.items()
    }

    records = []

    for _, row in df.iterrows():
        rec = build_record(row, cols)

        # 删除完全无效行
        if not rec["Journal name"] and not rec["ISSN"] and not rec["eISSN"]:
            continue

        if not rec["Category"]:
            rec["Category"] = "Unclassified"

        records.append(rec)

    # =========================================================
    # 1. 按 Category 拆分
    # =========================================================

    category_groups = {}

    for rec in records:
        category = rec["Category"] or "Unclassified"
        category_groups.setdefault(category, []).append(rec)

    categories = sorted(category_groups.keys(), key=category_priority_key)

    categories_meta = []
    used_files = set()

    for category in categories:
        base = slugify(category)
        filename = f"{base}.json"

        # 防止极少数情况下 slug 重名
        if filename in used_files:
            i = 2
            while f"{base}_{i}.json" in used_files:
                i += 1
            filename = f"{base}_{i}.json"

        used_files.add(filename)

        data = category_groups[category]

        with open(CATEGORY_DIR / filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        categories_meta.append({
            "Category": category,
            "file": f"category/{filename}",
            "count": len(data)
        })

    with open(OUTPUT_DIR / "categories.json", "w", encoding="utf-8") as f:
        json.dump(categories_meta, f, ensure_ascii=False, indent=2)

    # =========================================================
    # 2. 生成轻量检索索引 index.json
    # =========================================================

    index_map = {}

    for rec in records:
        key = get_journal_key(rec)

        if not key or key in {"title:", "issn:", "eissn:"}:
            continue

        if key not in index_map:
            index_map[key] = {
                "Journal name": rec["Journal name"],
                "ISSN": rec["ISSN"],
                "eISSN": rec["eISSN"],
                "2025 JIF": rec["2025 JIF"],
                "5-year JIF": rec["5-year JIF"],
                "categories": []
            }

        cat_info = {
            "Category": rec["Category"],
            "Edition": rec["Edition"],
            "JIF quartile": rec["JIF quartile"],
            "JIF rank": rec["JIF rank"]
        }

        if cat_info not in index_map[key]["categories"]:
            index_map[key]["categories"].append(cat_info)

    index_data = list(index_map.values())

    with open(OUTPUT_DIR / "index.json", "w", encoding="utf-8") as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)

    print("JCR JSON 拆分完成：")
    print(f"- 原始记录数：{len(records)}")
    print(f"- 分类数量：{len(categories_meta)}")
    print(f"- 索引期刊数：{len(index_data)}")
    print(f"- 输出目录：{OUTPUT_DIR.resolve()}")
    print()
    print("生成文件：")
    print(f"- {OUTPUT_DIR / 'categories.json'}")
    print(f"- {OUTPUT_DIR / 'index.json'}")
    print(f"- {CATEGORY_DIR}/*.json")


if __name__ == "__main__":
    main()
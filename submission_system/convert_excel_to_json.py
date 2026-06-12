#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Convert journal_submission_systems.xlsx to journal_submission_systems.json.

Usage:
    python convert_excel_to_json.py --excel journal_submission_systems.xlsx --out journal_submission_systems.json

Required columns:
    分类, 系统类型, 期刊/平台名称, 英文名称, 缩写, 出版社/平台, 链接, 原始标题, 备注
"""
import argparse
import json
from datetime import date
from pathlib import Path

try:
    from openpyxl import load_workbook
except ImportError as exc:
    raise SystemExit("请先安装 openpyxl：pip install openpyxl") from exc

COL_MAP = {
    "分类": "category",
    "系统类型": "system_type",
    "期刊/平台名称": "name_cn",
    "英文名称": "name_en",
    "缩写": "abbr",
    "出版社/平台": "platform",
    "链接": "url",
    "原始标题": "original_title",
    "备注": "notes",
}

def cell_text(value):
    if value is None:
        return ""
    return str(value).strip()

def convert(excel_path: Path, out_path: Path):
    wb = load_workbook(excel_path, data_only=True)
    ws = wb["SubmissionLinks"] if "SubmissionLinks" in wb.sheetnames else wb.active
    headers = [cell_text(c.value) for c in ws[1]]
    missing = [c for c in COL_MAP if c not in headers]
    if missing:
        raise SystemExit(f"Excel 缺少必要列：{', '.join(missing)}")
    idx = {h: headers.index(h) for h in headers if h}
    links = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not any(row):
            continue
        item = {eng: cell_text(row[idx[cn]]) for cn, eng in COL_MAP.items()}
        if not item["url"]:
            continue
        item["id"] = len(links) + 1
        item["updated_date"] = date.today().isoformat()
        links.append(item)
    data = {"generated_at": date.today().isoformat(), "count": len(links), "links": links}
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已生成 {out_path}，共 {len(links)} 条。")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--excel", required=True, help="输入 Excel 文件路径")
    parser.add_argument("--out", default="journal_submission_systems.json", help="输出 JSON 文件路径")
    args = parser.parse_args()
    convert(Path(args.excel), Path(args.out))

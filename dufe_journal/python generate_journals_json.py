# -*- coding: utf-8 -*-
"""
从“东北财经大学学术期刊目录_2025修订.xlsx”的“全部目录”sheet
自动生成 journals_cn.json 和 journals_en.json。

输出目录：
data/journals_cn.json
data/journals_en.json
"""

import json
from pathlib import Path

import pandas as pd


EXCEL_FILE = "东北财经大学学术期刊目录_2025修订.xlsx"
SHEET_NAME = "全部目录"

OUTPUT_DIR = Path("data")
OUTPUT_CN = OUTPUT_DIR / "journals_cn.json"
OUTPUT_EN = OUTPUT_DIR / "journals_en.json"


def clean_value(value):
    """清洗单元格内容，空值返回空字符串。"""
    if pd.isna(value):
        return ""

    text = str(value).strip()

    # 处理 Excel 中可能出现的 1.0、174.0 这类编号
    if text.endswith(".0"):
        try:
            number = float(text)
            if number.is_integer():
                return str(int(number))
        except ValueError:
            pass

    return text


def clean_number(value):
    """用于 serial 等数字字段，能转成整数则转整数，否则返回清洗后的字符串。"""
    if pd.isna(value):
        return ""

    try:
        number = float(value)
        if number.is_integer():
            return int(number)
        return number
    except Exception:
        return clean_value(value)


def clean_if(value):
    """清洗影响因子字段，数字尽量保留为数字，空值返回空字符串。"""
    if pd.isna(value):
        return ""

    text = str(value).strip()

    if text == "" or text in {"-", "—", "NA", "N/A", "nan"}:
        return ""

    try:
        number = float(text)
        return number
    except ValueError:
        return text


def normalize_language(value):
    """
    规范化语种字段。
    返回：
    cn = 中文期刊
    en = 外文/英文期刊
    unknown = 无法识别
    """
    text = clean_value(value).lower()

    if text in {"中文", "中文期刊", "中国", "cn", "chinese"}:
        return "cn"

    if text in {"外文", "外文期刊", "英文", "英文期刊", "en", "english", "foreign"}:
        return "en"

    # 兼容包含式写法
    if "中文" in text or "chinese" in text:
        return "cn"

    if "外文" in text or "英文" in text or "english" in text or "foreign" in text:
        return "en"

    return "unknown"


def build_record(row, language):
    """
    将 Excel 的一行转换为 JSON 记录。
    language: cn 或 en
    """
    record = {
        "serial": clean_number(row.get("总序号", "")),
        "rank": clean_value(row.get("级别", "")),
        "title": clean_value(row.get("期刊名称", "")),
        "publisher": clean_value(row.get("主办单位", "")),
        "issn": clean_value(row.get("ISSN", "")),
        "eissn": clean_value(row.get("eISSN", "")),
    }

    impact_factor = clean_if(row.get("影响因子", ""))

    # 英文期刊保留 IF；中文期刊如果 Excel 中确实有 IF，也一并保留
    if impact_factor != "":
        record["IF"] = impact_factor

    # 删除完全为空的可选字段，但保留 serial/rank/title/publisher/issn/eissn 这些基础字段
    # 如果你希望空字段也全部保留，可以删除下面这段
    for key in list(record.keys()):
        if key not in {"serial", "rank", "title", "publisher", "issn", "eissn"} and record[key] == "":
            del record[key]

    return record


def main():
    excel_path = Path(EXCEL_FILE)

    if not excel_path.exists():
        raise FileNotFoundError(f"未找到 Excel 文件：{excel_path.resolve()}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_excel(excel_path, sheet_name=SHEET_NAME)

    # 清理列名中的空格
    df.columns = [str(col).strip() for col in df.columns]

    required_columns = ["语种", "总序号", "级别", "期刊名称"]
    missing = [col for col in required_columns if col not in df.columns]

    if missing:
        raise ValueError(f"Excel 中缺少必要字段：{missing}")

    journals_cn = []
    journals_en = []

    for _, row in df.iterrows():
        lang = normalize_language(row.get("语种", ""))

        title = clean_value(row.get("期刊名称", ""))
        if not title:
            continue

        if lang == "cn":
            journals_cn.append(build_record(row, "cn"))
        elif lang == "en":
            journals_en.append(build_record(row, "en"))

    with open(OUTPUT_CN, "w", encoding="utf-8") as f:
        json.dump(journals_cn, f, ensure_ascii=False, indent=2)

    with open(OUTPUT_EN, "w", encoding="utf-8") as f:
        json.dump(journals_en, f, ensure_ascii=False, indent=2)

    print("JSON 文件生成完成：")
    print(f"- {OUTPUT_CN}：{len(journals_cn)} 条")
    print(f"- {OUTPUT_EN}：{len(journals_en)} 条")


if __name__ == "__main__":
    main()
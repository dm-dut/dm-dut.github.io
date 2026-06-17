import pandas as pd
import numpy as np
from difflib import get_close_matches

# =========================
# 文件名
# =========================
ajg_file = "AJG2024.xlsx"
ccf_file = "CCF2026.xlsx"
fms_file = "FMS2025.xlsx"
if_file = "JCR2026.xlsx"

# =========================
# 清洗 IF
# =========================
def clean_if_value(x):
    if pd.isna(x):
        return np.nan

    x = str(x).strip().lower()

    if x in ["n/a", "na", "nan", "none", ""]:
        return np.nan

    if x.startswith("<"):
        try:
            return float(x.replace("<", "").strip())
        except:
            return np.nan

    try:
        return float(x)
    except:
        return np.nan


# =========================
# 标准化名称
# =========================
def normalize_name(name):
    if pd.isna(name):
        return ""
    return (
        str(name)
        .lower()
        .replace("&", "and")
        .replace("-", " ")
        .replace(":", " ")
        .replace(",", " ")
        .replace(".", " ")
        .replace("/", " ")
        .replace("(", " ")
        .replace(")", " ")
        .strip()
    )


# =========================
# 读取 JCR
# =========================
if_df = pd.read_excel(if_file)

if_df["JIF 2025"] = if_df["JIF 2025"].apply(clean_if_value)
if_df["normalized_name"] = if_df["Journal Name"].apply(normalize_name)

if_dict = dict(zip(
    if_df["normalized_name"],
    if_df["JIF 2025"]
))

if_name_list = list(if_dict.keys())


# =========================
# 匹配 IF
# =========================
def find_if(journal_name):
    norm_name = normalize_name(journal_name)

    if norm_name in if_dict:
        return if_dict[norm_name]

    match = get_close_matches(norm_name, if_name_list, n=1, cutoff=0.90)
    if match:
        return if_dict[match[0]]

    return np.nan


# =========================
# ⭐ 核心更新：先清空再填充
# =========================
def update_if_column(df, journal_col, if_col_name="影响因子"):

    # 如果列不存在就创建
    if if_col_name not in df.columns:
        df[if_col_name] = np.nan

    # ⭐ 关键：每次运行先清空
    df[if_col_name] = np.nan

    # 防止 dtype 冲突
    df[if_col_name] = df[if_col_name].astype("object")

    for idx, row in df.iterrows():
        matched_if = find_if(row[journal_col])

        matched_if = clean_if_value(matched_if)

        df.at[idx, if_col_name] = matched_if

    return df


# =========================
# AJG
# =========================
ajg_df = pd.read_excel(ajg_file)

ajg_df = update_if_column(
    ajg_df,
    journal_col="Journal Title",
    if_col_name="影响因子"
)

ajg_df.to_excel("AJG2024.xlsx", index=False)
print("已生成: AJG2024.xlsx")


# =========================
# CCF
# =========================
ccf_df = pd.read_excel(ccf_file)

ccf_df = update_if_column(
    ccf_df,
    journal_col="全称",
    if_col_name="影响因子"
)

ccf_df.to_excel("CCF2026.xlsx", index=False)
print("已生成: CCF2026.xlsx")


# =========================
# FMS
# =========================
fms_df = pd.read_excel(fms_file)

fms_df = update_if_column(
    fms_df,
    journal_col="期刊名称",
    if_col_name="影响因子"
)

fms_df.to_excel("FMS2025.xlsx", index=False)
print("已生成: FMS2025.xlsx")


# =========================
# 统计
# =========================
print("\n更新完成：")
print("AJG:", ajg_df["影响因子"].notna().sum(), "/", len(ajg_df))
print("CCF:", ccf_df["影响因子"].notna().sum(), "/", len(ccf_df))
print("FMS:", fms_df["影响因子"].notna().sum(), "/", len(fms_df))
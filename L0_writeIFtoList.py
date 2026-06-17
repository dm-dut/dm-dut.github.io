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
# 影响因子清洗函数（核心修复）
# =========================
def clean_if_value(x):
    if pd.isna(x):
        return np.nan

    x = str(x).strip().lower()

    # 空值类
    if x in ["n/a", "na", "nan", "none", ""]:
        return np.nan

    # 处理 <0.1 这种
    if x.startswith("<"):
        try:
            return float(x.replace("<", "").strip())
        except:
            return np.nan

    # 正常数值
    try:
        return float(x)
    except:
        return np.nan


# =========================
# 读取影响因子文件
# =========================
if_df = pd.read_excel(if_file)

# 清洗 IF 列
if_df["JIF 2024"] = if_df["JIF 2024"].apply(clean_if_value)


# =========================
# 标准化期刊名称
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
# 构建 IF 字典
# =========================
if_df["normalized_name"] = if_df["Journal Name"].apply(normalize_name)

if_dict = dict(zip(
    if_df["normalized_name"],
    if_df["JIF 2024"]
))

if_name_list = list(if_dict.keys())


# =========================
# 匹配影响因子
# =========================
def find_if(journal_name):
    norm_name = normalize_name(journal_name)

    # 1. 精确匹配
    if norm_name in if_dict:
        return if_dict[norm_name]

    # 2. 模糊匹配
    match = get_close_matches(norm_name, if_name_list, n=1, cutoff=0.90)
    if match:
        return if_dict[match[0]]

    return np.nan


# =========================
# 更新函数（已彻底修复dtype问题）
# =========================
def update_if_column(df, journal_col, if_col_name="影响因子"):

    # 强制 object，避免 float64 写入冲突
    if if_col_name not in df.columns:
        df[if_col_name] = np.nan

    df[if_col_name] = df[if_col_name].astype("object")

    for idx, row in df.iterrows():
        current_if = row[if_col_name]

        if pd.isna(current_if) or str(current_if).strip() == "":
            matched_if = find_if(row[journal_col])

            # 二次清洗（保证安全）
            matched_if = clean_if_value(matched_if)

            df.at[idx, if_col_name] = matched_if

    return df


# =========================
# 处理 AJG
# =========================
ajg_df = pd.read_excel(ajg_file)

ajg_df = update_if_column(
    df=ajg_df,
    journal_col="Journal Title",
    if_col_name="影响因子"
)

ajg_output = "AJG2024.xlsx"
ajg_df.to_excel(ajg_output, index=False)

print(f"已生成: {ajg_output}")


# =========================
# 处理 CCF
# =========================
ccf_df = pd.read_excel(ccf_file)

ccf_df = update_if_column(
    df=ccf_df,
    journal_col="全称",
    if_col_name="影响因子"
)

ccf_output = "CCF2026.xlsx"
ccf_df.to_excel(ccf_output, index=False)

print(f"已生成: {ccf_output}")


# =========================
# 处理 FMS
# =========================
fms_df = pd.read_excel(fms_file)

fms_df = update_if_column(
    df=fms_df,
    journal_col="期刊名称",
    if_col_name="影响因子"
)

fms_output = "FMS2025.xlsx"
fms_df.to_excel(fms_output, index=False)

print(f"已生成: {fms_output}")


# =========================
# 统计结果
# =========================
print("\n更新完成：")

print(f"AJG 已填充影响因子数量: {ajg_df['影响因子'].notna().sum()} / {len(ajg_df)}")
print(f"CCF 已填充影响因子数量: {ccf_df['影响因子'].notna().sum()} / {len(ccf_df)}")
print(f"FMS 已填充影响因子数量: {fms_df['影响因子'].notna().sum()} / {len(fms_df)}")
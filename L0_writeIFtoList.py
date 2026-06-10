import pandas as pd
from difflib import get_close_matches

# =========================
# 文件名
# =========================
ajg_file = "AJG2024.xlsx"
ccf_file = "CCF2026.xlsx"
fms_file = "FMS2025.xlsx"
if_file = "2025IF.xlsx"

# =========================
# 读取影响因子文件
# =========================
if_df = pd.read_excel(if_file)

# 标准化期刊名称，方便匹配
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

# 构建影响因子字典
if_df["normalized_name"] = if_df["Journal Name"].apply(normalize_name)
if_dict = dict(zip(if_df["normalized_name"], if_df["JIF 2024"]))

# 所有影响因子文件中的标准化名称列表
if_name_list = list(if_dict.keys())

# =========================
# 匹配影响因子函数
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

    # 3. 未匹配返回空值
    return None

# =========================
# 更新指定列中的影响因子
# =========================
def update_if_column(df, journal_col, if_col_name="影响因子"):
    # 如果原表中不存在“影响因子”列，则自动创建
    if if_col_name not in df.columns:
        df[if_col_name] = None

    # 仅填充空值，不覆盖已有值
    for idx, row in df.iterrows():
        current_if = row[if_col_name]

        if pd.isna(current_if) or str(current_if).strip() == "":
            matched_if = find_if(row[journal_col])
            df.at[idx, if_col_name] = matched_if

    return df

# =========================
# 处理 AJG 文件
# =========================
ajg_df = pd.read_excel(ajg_file)

# 请确保这里的列名和你表中的影响因子列名一致
ajg_df = update_if_column(
    df=ajg_df,
    journal_col="Journal Title",
    if_col_name="影响因子"
)

ajg_output = "AJG2024.xlsx"
ajg_df.to_excel(ajg_output, index=False)

print(f"已生成: {ajg_output}")

# =========================
# 处理 CCF 文件
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
# 处理 FMS 文件
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
# 输出统计信息
# =========================
print("\n更新完成。")
print(f"AJG 已填充影响因子数量: {ajg_df['影响因子'].notna().sum()} / {len(ajg_df)}")
print(f"CCF 已填充影响因子数量: {ccf_df['影响因子'].notna().sum()} / {len(ccf_df)}")
print(f"FMS 已填充影响因子数量: {fms_df['影响因子'].notna().sum()} / {len(fms_df)}")


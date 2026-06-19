import pandas as pd
import os

os.makedirs("data", exist_ok=True)

# AJG
ajg_df = pd.read_excel("AJG2024.xlsx").fillna("")
ajg_df.to_json("data/ajg.json", orient="records", force_ascii=False)

# CCF
ccf_df = pd.read_excel("CCF2026.xlsx").fillna("")
ccf_df.to_json("data/ccf.json", orient="records", force_ascii=False)

# FMS
fms_df = pd.read_excel("FMS2025.xlsx").fillna("")
fms_df.to_json("data/fms.json", orient="records", force_ascii=False)

print("JSON 文件已生成")

file_path = "JCR2026-web.xlsx"
jcr_df = pd.read_excel(file_path)

def clean(x):
    return str(x).strip() if pd.notna(x) else ""

def split_cat(cat):
    if not cat:
        return []
    return [c.strip() for c in str(cat).replace(";", ",").split(",") if c.strip()]

data = []

for _, r in jcr_df.iterrows():

    data.append({
        "journal": clean(r.get("Journal name")),
        "issn": clean(r.get("ISSN")),
        "eissn": clean(r.get("eISSN")),
        "categories": split_cat(r.get("Category")),
        "jif": clean(r.get("2025 JIF")),
        "jif5": clean(r.get("5-year JIF")),
        "quartile": clean(r.get("JIF quartile"))
    })

jcr_df.to_json("data/jcr.json", orient="records", force_ascii=False)

print("JCR JSON生成完成")
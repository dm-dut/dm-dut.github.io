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
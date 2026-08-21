import os
import json
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(ROOT, "config")
WEB_DIR = os.path.join(ROOT, "web")

os.makedirs(WEB_DIR, exist_ok=True)


def clean(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


journals = pd.read_excel(
    os.path.join(CONFIG_DIR, "journals.xlsx")
)

journal_order = {}

for idx, (_, row) in enumerate(
    journals.iterrows(),
    start=1,
):
    name = clean(row.get("Journal", ""))

    if name and name not in journal_order:
        journal_order[name] = idx

output = os.path.join(
    WEB_DIR,
    "journal_order.json",
)

with open(output, "w", encoding="utf-8") as f:
    json.dump(
        journal_order,
        f,
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    )

print(
    f"Generated {output} "
    f"with {len(journal_order)} journals."
)

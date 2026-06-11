import json
from pathlib import Path
from openpyxl import load_workbook

INPUT = Path("journal_list.xlsx")
OUTPUT = Path("journals.json")

wb = load_workbook(INPUT, data_only=True)
ws = wb["Journals"]
headers = [str(c.value).strip() if c.value is not None else "" for c in ws[1]]
idx = {h: i for i, h in enumerate(headers)}
required = ["Category", "Order", "Journal", "URL"]
for h in required:
    if h not in idx:
        raise ValueError(f"Missing required column: {h}")

rows = []
for row in ws.iter_rows(min_row=2, values_only=True):
    category = row[idx["Category"]]
    journal = row[idx["Journal"]]
    url = row[idx["URL"]]
    if not category or not journal or not url:
        continue
    order_val = row[idx.get("Order", -1)] if "Order" in idx else None
    try:
        order = int(order_val)
    except Exception:
        order = 999999
    extra_raw = row[idx.get("Extra Links (label|url; ...)", -1)] if "Extra Links (label|url; ...)" in idx else ""
    extra_links = []
    if extra_raw:
        for part in str(extra_raw).split(";"):
            part = part.strip()
            if not part:
                continue
            if "|" in part:
                label, href = part.split("|", 1)
            else:
                label, href = "Link", part
            label, href = label.strip(), href.strip()
            if href:
                extra_links.append({"label": label or "Link", "url": href})
    rows.append({
        "category": str(category).strip(),
        "order": order,
        "journal": str(journal).strip(),
        "url": str(url).strip(),
        "extra_links": extra_links,
    })

rows.sort(key=lambda x: (x["order"], x["journal"].lower()))
categories = []
for item in rows:
    if item["category"] not in categories:
        categories.append(item["category"])

OUTPUT.write_text(json.dumps({"categories": categories, "journals": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Generated {OUTPUT} with {len(rows)} journals in {len(categories)} categories.")

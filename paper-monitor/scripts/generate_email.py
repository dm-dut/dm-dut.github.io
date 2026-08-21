"""
Generate HTML email digest for new papers.

Input:
    web/new_papers.json
    web/journal_order.json
    web/update_time.json

Output:
    web/daily_papers_email.html

Only NEW papers are included.
If there are no NEW papers, no email body is generated.
"""

import json
from pathlib import Path
from collections import defaultdict


ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"


def load_json(path, default):
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


papers = load_json(WEB / "new_papers.json", [])

if not papers:
    print("No new papers. Email generation skipped.")
    raise SystemExit(0)

journal_order = load_json(WEB / "journal_order.json", {})
update_time = load_json(WEB / "update_time.json", {})

groups = defaultdict(list)

for p in papers:
    groups[p.get("journal", "Unknown Journal")].append(p)


def order_value(journal):
    return journal_order.get(journal, 999999)


journals = sorted(groups.keys(), key=order_value)

rows = []

for journal in journals:
    rows.append(f"""
    <h2 style="font-size:18px;color:#102a43;margin-top:25px;">
        {journal} ({len(groups[journal])})
    </h2>
    """)

    for p in groups[journal]:
        title = p.get("title", "")
        doi = p.get("doi", "")
        link = f"https://doi.org/{doi}" if doi else "#"

        rows.append(f"""
        <table width="100%" cellpadding="8"
        style="border-collapse:collapse;margin-bottom:15px;
        border-bottom:1px solid #d9e2ec;">
        <tr>
        <td>
        <a href="{link}"
        style="font-size:16px;font-weight:bold;
        color:#102a43;text-decoration:none;">
        {title}
        </a>

        <br><br>

        <b>Authors:</b><br>
        {p.get("authors","")}

        <br><br>

        <b>Online:</b>
        {p.get("online_date","")}

        <br>

        <b>DOI:</b>
        <a href="{link}">{doi}</a>

        </td>
        </tr>
        </table>
        """)


date_text = update_time.get("updated", "")
count = len(papers)

html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;
color:#243b53;">

<h1 style="color:#102a43;">
Paper Monitor Daily Update
</h1>

<p>
Date: {date_text} (GMT+8)
</p>

<p>
<b>{count}</b> new papers found.
</p>

{''.join(rows)}

<hr>

<p style="font-size:12px;color:#627d98;">
Copyright © 2026 Zhen Zhang, Dalian University of Technology
</p>

</body>
</html>
"""

with open(WEB / "daily_papers_email.html", "w", encoding="utf-8") as f:
    f.write(html)

print(f"Generated email: {WEB / 'daily_papers_email.html'}")

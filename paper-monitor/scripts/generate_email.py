"""
Generate styled HTML email digest for Paper Monitor.

Features:
- Blue academic style
- Journal grouping
- New paper statistics
- DOI hyperlinks
- Mobile-friendly HTML
- GMT+8 update display
"""

import json
from pathlib import Path
from collections import defaultdict, Counter

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"


def load_json(path, default):
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


papers = load_json(WEB / "new_papers.json", [])

if not papers:
    print("No new papers. Skip email generation.")
    raise SystemExit(0)

journal_order = load_json(WEB / "journal_order.json", {})
update_time = load_json(WEB / "update_time.json", {})

groups = defaultdict(list)

for paper in papers:
    groups[paper.get("journal", "Unknown Journal")].append(paper)


def journal_rank(name):
    return journal_order.get(name, 999999)


journals = sorted(groups.keys(), key=journal_rank)

summary = Counter(
    p.get("journal", "Unknown Journal")
    for p in papers
)

summary_rows = "".join(
    f"""
    <tr>
      <td style="padding:6px 12px;color:#334e68;">{j}</td>
      <td style="padding:6px 12px;color:#102a43;font-weight:bold;">{summary[j]}</td>
    </tr>
    """
    for j in journals
)

paper_blocks = []

for journal in journals:

    paper_blocks.append(
        f"""
        <h2 style="
        color:#1f4e85;
        font-size:18px;
        margin-top:28px;
        border-left:4px solid #1f4e85;
        padding-left:10px;">
        {journal} ({len(groups[journal])})
        </h2>
        """
    )

    for p in groups[journal]:
        doi = p.get("doi", "")
        doi_url = f"https://doi.org/{doi}" if doi else "#"

        paper_blocks.append(
            f"""
            <table width="100%" cellpadding="0" cellspacing="0"
            style="background:#fff;border:1px solid #d9e2ec;margin-bottom:15px;">
            <tr>
            <td style="padding:16px;">

            <a href="{doi_url}"
            style="color:#102a43;font-size:16px;font-weight:bold;text-decoration:none;">
            {p.get("title","")}
            </a>

            <br><br>

            <span style="color:#334e68;font-size:14px;">
            <b>Authors:</b><br>
            {p.get("authors","")}
            </span>

            <br><br>

            <span style="color:#627d98;font-size:13px;">
            Online: {p.get("online_date","")}<br>
            Fetched (GMT+8): {p.get("fetched_date","")}
            </span>

            <br><br>

            <a href="{doi_url}"
            style="background:#2f6fad;color:white;padding:5px 12px;
            border-radius:4px;text-decoration:none;font-size:13px;">
            DOI
            </a>

            </td>
            </tr>
            </table>
            """
        )


updated = update_time.get("updated", "")

html = f"""
<!DOCTYPE html>
<html>
<body style="margin:0;padding:20px;background:#f7fafc;
font-family:Arial,Helvetica,sans-serif;">

<table width="700" align="center"
style="background:white;padding:25px;border-collapse:collapse;">
<tr>
<td>

<h1 style="color:#1f4e85;font-size:26px;">
Paper Monitor
</h1>

<p style="color:#627d98;font-size:15px;">
Daily New Papers Digest
</p>

<hr style="border:none;border-top:1px solid #d9e2ec;">

<p style="color:#334e68;">
Update time:
<b>{updated} (GMT+8)</b>
</p>

<div style="background:#f0f6fc;padding:15px;color:#102a43;">
<b style="font-size:20px;">{len(papers)}</b>
new papers found.
</div>

<h3 style="color:#1f4e85;">Journal Summary</h3>

<table>
{summary_rows}
</table>

{''.join(paper_blocks)}

<hr style="border:none;border-top:1px solid #d9e2ec;">

<p style="font-size:12px;color:#829ab1;">
Copyright © 2026 Zhen Zhang, Dalian University of Technology
</p>

</td>
</tr>
</table>

</body>
</html>
"""

output = WEB / "daily_papers_email.html"

with open(output, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Generated: {output}")

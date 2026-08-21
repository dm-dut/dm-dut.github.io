"""
Generate mobile-friendly HTML email digest for Paper Monitor.

Version:
v15.0 Email Mobile Optimization

Features:
- Responsive email layout
- Larger fonts for mobile reading
- Blue academic style
- Journal grouping
- DOI hyperlinks
- GMT+8 update display
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
    print("No new papers. Skip email generation.")
    raise SystemExit(0)


journal_order = load_json(WEB / "journal_order.json", {})
update_time = load_json(WEB / "update_time.json", {})


def journal_rank(name):
    return journal_order.get(name, 999999)


groups = defaultdict(list)

for paper in papers:
    groups[paper.get("journal", "Unknown Journal")].append(paper)


journals = sorted(groups.keys(), key=journal_rank)


paper_blocks = []

for journal in journals:

    paper_blocks.append(
        f"""
        <h2 style="
        color:#1f4e85;
        font-size:14px;
        line-height:1.5;
        margin-top:30px;
        border-left:5px solid #1f4e85;
        padding-left:12px;">
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
            style="
            background:#ffffff;
            border:1px solid #d9e2ec;
            margin-bottom:12px;">

            <tr>
            <td style="padding:14px;">

            <a href="{doi_url}"
            style="
            color:#102a43;
            font-size:14px;
            line-height:1.5;
            font-weight:600;
            text-decoration:none;">
            {p.get("title","")}
            </a>

            <div style="height:8px;"></div>

            <div style="
            color:#334e68;
            font-size:13.5px;
            line-height:1.6;">
            <b>Authors:</b><br>
            {p.get("authors","")}
            </div>

            <br>

            <div style="
            color:#627d98;
            font-size:13.5px;
            line-height:1.6;">
            Online: {p.get("online_date","")}
            <br>
            Fetched (GMT+8): {p.get("fetched_date","")}
            </div>

            <br>

            <a href="{doi_url}"
            style="
            display:inline-block;
            background:#2f6fad;
            color:#ffffff;
            padding:7px 16px;
            border-radius:5px;
            font-size:13.5px;
            text-decoration:none;">
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

<head>

<meta name="viewport"
content="width=device-width, initial-scale=1.0">

<style>

@media only screen and (max-width:600px) {{

    h1 {{
        font-size:28px !important;
    }}

    h2 {{
        font-size:20px !important;
    }}

}}


@media only screen and (max-width:600px) {{

    h1 {{
        font-size:20px !important;
        margin-bottom:4px !important;
    }}

    h2 {{
        font-size:15px !important;
        margin-top:18px !important;
        margin-bottom:10px !important;
        border-left-width:3px !important;
        padding-left:8px !important;
    }}

    a {{
        font-size:15px !important;
        line-height:1.4 !important;
    }}

    body {{
        padding:8px !important;
    }}

    table td {{
        padding:10px !important;
    }}

}}

</style>

</head>


<body style="
margin:0;
padding:10px;
background:#f7fafc;
font-family:Arial,Helvetica,sans-serif;">


<table width="100%"
style="
max-width:700px;
margin:auto;
background:#ffffff;
border-collapse:collapse;">

<tr>

<td style="padding:15px;">


<h1 style="
color:#1f4e85;
font-size:24px;
margin:0;">
Paper Monitor
</h1>


<p style="
color:#627d98;
font-size:14px;">
Daily New Papers Digest
</p>


<hr style="
border:none;
border-top:1px solid #d9e2ec;">



<p style="
color:#334e68;
font-size:14px;">
Update time:
<b>{updated} (GMT+8)</b>
</p>



<div style="
background:#f0f6fc;
padding:16px;
color:#102a43;
font-size:14px;">

<b style="font-size:18px;">
{len(papers)}
</b>

new papers found.

</div>



{''.join(paper_blocks)}



<hr style="
border:none;
border-top:1px solid #d9e2ec;
margin-top:30px;">



<p style="
font-size:13px;
color:#829ab1;">

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
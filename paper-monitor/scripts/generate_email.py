"""
Generate Paper Monitor email digest v15.8 clean.

Features:
- Responsive PC/mobile layout
- Keeps title hyperlink
- Removes DOI display
- Removes online/fetched dates
- Keeps authors
- Keeps new paper summary
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


paper_html = []

for journal in journals:

    paper_html.append(
        f"""
        <h2 class="journal">
        {journal}
        </h2>
        """
    )

    for p in groups[journal]:

        doi = p.get("doi", "")
        title_link = f"https://doi.org/{doi}" if doi else "#"

        paper_html.append(
            f"""
            <div class="paper">

                <a class="title"
                   href="{title_link}">
                   {p.get("title", "")}
                </a>

                <div class="authors">
                    <b>Authors:</b><br>
                    {p.get("authors", "")}
                </div>

            </div>
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

body {{
    margin:0;
    padding:15px;
    background:#f7fafc;
    font-family:Arial, Helvetica, sans-serif;
}}

.container {{
    max-width:780px;
    margin:auto;
    background:white;
    padding:25px;
}}

.header {{
    color:#1f4e85;
    font-size:22px;
    font-weight:bold;
}}

.subtitle {{
    color:#627d98;
    font-size:14px;
}}

.info {{
    color:#334e68;
    font-size:14px;
    margin-top:15px;
}}

.summary {{
    background:#f0f6fc;
    padding:12px;
    margin:15px 0;
    color:#102a43;
    font-size:15px;
}}

.journal {{
    color:#1f4e85;
    font-size:15px;
    margin-top:24px;
    margin-bottom:12px;
    border-left:4px solid #1f4e85;
    padding-left:10px;
}}

.paper {{
    border:1px solid #d9e2ec;
    padding:16px;
    margin-bottom:12px;
}}

.title {{
    color:#102a43;
    font-size:15px;
    line-height:1.45;
    font-weight:700;
    text-decoration:none;
}}

.authors {{
    margin-top:10px;
    color:#334e68;
    font-size:14px;
    line-height:1.5;
}}


.footer {{
    margin-top:30px;
    border-top:1px solid #d9e2ec;
    padding-top:10px;
    color:#829ab1;
    font-size:12px;
}}


@media only screen and (max-width:600px) {{

    body {{
        padding:8px;
    }}

    .container {{
        padding:12px;
    }}

    .header {{
        font-size:15px;
    }}

    .subtitle {{
        font-size:11px;
    }}

    .info {{
        font-size:12px;
    }}

    .summary {{
        font-size:13px;
        padding:10px;
    }}

    .journal {{
        font-size:14px;
        margin-top:14px;
        margin-bottom:8px;
        border-left-width:2px;
        padding-left:7px;
    }}

    .paper {{
        padding:8px;
        margin-bottom:6px;
    }}

    .title {{
        font-size:14px;
        line-height:1.35;
    }}

    .authors {{
        font-size:12px;
        line-height:1.4;
    }}

}}


@media only screen and (max-width:600px) {{

    body {{
        padding:5px !important;
    }}

    .container {{
        padding:8px !important;
    }}

    .header {{
        font-size:16px !important;
        line-height:1.75 !important;
    }}

    .subtitle {{
        font-size:11px !important;
        margin:3px 0 !important;
        line-height:1.75 !important;
    }}

    .info {{
        font-size:12px !important;
        margin-top:8px !important;
        line-height:1.75 !important;
    }}

    .summary {{
        font-size:13px !important;
        padding:8px !important;
        margin:10px 0 !important;
        line-height:1.75 !important;
    }}

    .journal {{
        font-size:11.5px !important;
        margin-top:16px !important;
        margin-bottom:10px !important;
        padding-left:6px !important;
        line-height:1.75 !important;
    }}

    .paper {{
        padding:8px !important;
        margin-bottom:10px !important;
    }}

    .title {{
        font-size:11px !important;
        line-height:1.75 !important;
    }}

    .authors {{
        font-size:10.5px !important;
        line-height:1.75 !important;
        margin-top:6px !important;
    }}
}}

</style>

</head>


<body>

<div class="container">


<div class="header">
Paper Monitor
</div>


<div class="subtitle">
Daily New Papers Digest
</div>


<div class="info">
Update time:
<b>{updated} (GMT+8)</b>
</div>


<div class="summary">
<b>{len(papers)}</b>
new papers found.
</div>


{''.join(paper_html)}


<div class="footer">
Copyright © 2026 Zhen Zhang, Dalian University of Technology
</div>


</div>

</body>

</html>
"""


output = WEB / "daily_papers_email.html"

with open(output, "w", encoding="utf-8") as f:
    f.write(html)


print(f"Generated: {output}")
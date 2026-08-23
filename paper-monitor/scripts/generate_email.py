"""
Generate Paper Monitor email digest.

Features:
- Responsive PC/mobile layout
- Keeps title hyperlink
- Removes DOI display
- Removes online/fetched dates
- Keeps authors
- Keeps new paper summary
- Displays volume / issue / pages / article number as plain non-clickable text
- Archives generated HTML by date/time
- Keeps multiple runs on the same day
- Deletes email HTML archives older than 30 days
"""

import json
import re
import datetime
from pathlib import Path
from collections import defaultdict


ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"

GMT8 = datetime.timezone(datetime.timedelta(hours=8))


def load_json(path, default):
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_run_datetime(update_time):
    updated = str(update_time.get("updated", "")).strip()

    try:
        dt = datetime.datetime.strptime(
            updated,
            "%Y-%m-%d %H:%M:%S"
        )
        return dt.replace(tzinfo=GMT8)

    except (ValueError, TypeError):
        return datetime.datetime.now(GMT8)


def get_unique_email_path(run_dt):
    base_name = (
        "daily_papers_email_"
        + run_dt.strftime("%Y-%m-%d_%H%M%S")
    )

    output = WEB / f"{base_name}.html"

    if not output.exists():
        return output, run_dt.strftime("%H%M%S")

    index = 2

    while True:
        output = WEB / f"{base_name}_{index:02d}.html"

        if not output.exists():
            run_id = (
                run_dt.strftime("%H%M%S")
                + f"-{index:02d}"
            )
            return output, run_id

        index += 1


def cleanup_old_email_files(reference_dt, keep_days=30):
    cutoff_date = (
        reference_dt.date()
        - datetime.timedelta(days=keep_days)
    )

    pattern = re.compile(
        r"^daily_papers_email_"
        r"(\d{4}-\d{2}-\d{2})"
        r"(?:_\d{6})?"
        r"(?:_\d{2})?"
        r"\.html$"
    )

    for file in WEB.glob("daily_papers_email_*.html"):
        match = pattern.match(file.name)

        if not match:
            continue

        try:
            file_date = datetime.datetime.strptime(
                match.group(1),
                "%Y-%m-%d"
            ).date()
        except ValueError:
            continue

        if file_date < cutoff_date:
            try:
                file.unlink()
                print(f"Deleted old email archive: {file.name}")
            except OSError as exc:
                print(
                    f"Failed to delete old email archive "
                    f"{file.name}: {exc}"
                )


def publication_info(paper):
    """
    Publication metadata display rules:

    1. Show volume and issue when available.
    2. Prefer page range when pages are available.
    3. Otherwise show the article number.
    4. If there is no volume but an article number exists,
       prefix the metadata with "In Press".
    """
    parts = []

    volume = str(paper.get("volume", "") or "").strip()
    number = str(paper.get("number", "") or "").strip()
    pages = str(paper.get("pages", "") or "").strip()
    article_number = str(
        paper.get("article_number", "") or ""
    ).strip()

    # If Crossref has not assigned a volume yet, treat the paper as
    # an in-press / early-access item whenever page/article metadata exists.
    # Some publishers place an article ID in the Crossref "page" field,
    # so the rule must not depend only on article_number.
    if not volume and (pages or article_number):
        parts.append("In Press")

    if volume:
        parts.append(f"Vol. {volume}")

    if number:
        parts.append(f"No. {number}")

    if pages:
        parts.append(f"Pages {pages}")
    elif article_number:
        parts.append(f"Article No. {article_number}")

    return " | ".join(parts)


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

        doi = str(p.get("doi", "") or "").strip()
        title_link = f"https://doi.org/{doi}" if doi else "#"
        pub_info = publication_info(p)

        publication_block = (
            f"""
                <div class="authors publication-info">
                    {pub_info}
                </div>
            """
            if pub_info
            else ""
        )

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

                {publication_block}

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
    margin-top:15px;
    margin-bottom:10px !important;
}}

.subtitle {{
    color:#627d98;
    font-size:14px;
    margin-top:15px;
    margin-bottom:10px !important;
}}

.info {{
    color:#334e68;
    font-size:14px;
    margin-top:15px;
    margin-bottom:10px !important;
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

.publication-info,
.publication-info a,
.publication-info a[x-apple-data-detectors] {{
    color:#334e68 !important;
    text-decoration:none !important;
    pointer-events:none !important;
    cursor:default !important;
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
        line-height:1.75 !important;
    }}

    .subtitle {{
        font-size:11px;
        line-height:1.75 !important;
    }}

    .info {{
        font-size:12px;
        line-height:1.75 !important;
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


run_dt = get_run_datetime(update_time)
output, run_id = get_unique_email_path(run_dt)

with open(output, "w", encoding="utf-8") as f:
    f.write(html)


paper_count = len(papers)

subject = (
    f"[Paper Monitor] "
    f"{run_dt.strftime('%Y-%m-%d %H:%M')} · "
    f"{paper_count} New Paper"
    f"{'' if paper_count == 1 else 's'} "
    f"· #{run_id}"
)


latest_email_info = {
    "html_file": output.name,
    "subject": subject,
    "run_id": run_id,
    "run_time": run_dt.strftime("%Y-%m-%d %H:%M:%S"),
    "timezone": "GMT+8",
    "paper_count": paper_count
}


latest_email_file = WEB / "latest_email.json"

with open(latest_email_file, "w", encoding="utf-8") as f:
    json.dump(
        latest_email_info,
        f,
        ensure_ascii=False,
        indent=2
    )


cleanup_old_email_files(
    reference_dt=run_dt,
    keep_days=30
)


print(f"Generated: {output}")
print(f"Run ID: {run_id}")
print(f"Subject: {subject}")
print(f"Metadata: {latest_email_file}")
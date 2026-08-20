
import requests
from datetime import datetime, timedelta


def format_partial(parts):
    if len(parts) == 3:
        return f"{parts[0]}-{parts[1]:02d}-{parts[2]:02d}"
    if len(parts) == 2:
        return f"{parts[0]}-{parts[1]:02d}"
    if len(parts) == 1:
        return str(parts[0])
    return None


def get_date(item):
    # Prefer complete publication dates.
    partial = None

    for field in [
        "published-online",
        "published-print",
        "issued",
        "published"
    ]:
        if field in item:
            try:
                parts = item[field]["date-parts"][0]
                value = format_partial(parts)

                if value and len(parts) == 3:
                    return value

                if value:
                    partial = value

            except Exception:
                pass

    # If only year-month is available, use Crossref created date
    # to obtain a complete date.
    created = item.get("created", {})
    if created.get("date-time"):
        return created["date-time"][:10]

    if partial:
        return partial

    return "N/A"


def get_authors(authors):
    result = []

    for a in authors:
        given = a.get("given", "")
        family = a.get("family", "")

        name = (given + " " + family).strip()

        if name:
            result.append(name)

    return ", ".join(result)


def fetch(issn, days=3, rows=50):

    if not issn:
        return []

    start = (
        datetime.utcnow() -
        timedelta(days=days)
    ).strftime("%Y-%m-%d")

    url = f"https://api.crossref.org/journals/{issn}/works"

    params = {
        "rows": rows,
        "sort": "created",
        "order": "desc",
        "filter": f"from-created-date:{start}"
    }

    response = requests.get(
        url,
        params=params,
        timeout=30
    )

    response.raise_for_status()

    papers = []

    for item in response.json().get("message", {}).get("items", []):

        papers.append({
            "doi": item.get("DOI", ""),
            "title": item.get("title", [""])[0],
            "journal": item.get("container-title", [""])[0],
            "authors": get_authors(item.get("author", [])),
            "online_date": get_date(item)
        })

    return papers

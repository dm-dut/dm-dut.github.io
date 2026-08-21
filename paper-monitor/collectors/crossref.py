import os
import time
import random
import datetime
from email.utils import parsedate_to_datetime

import requests


CROSSREF_URL = "https://api.crossref.org/journals/{issn}/works"

# Reuse the same TCP connection for all journals.
_SESSION = requests.Session()

# Keep requests comfortably below a few requests per second.
_MIN_INTERVAL_SECONDS = 0.6
_last_request_time = 0.0

# Retry policy: first request + 3 retries.
_RETRY_DELAYS = (2, 5, 10)

# Retry these server / rate-limit responses.
_RETRY_STATUS = {429, 500, 502, 503, 504}


def _clean(value):
    import html

    def _clean(value):
        if value is None:
            return ""

        value = str(value)

        value = html.unescape(value)

        value = " ".join(value.split())

        return value.strip()


def _build_headers(mailto=None):
    """
    Crossref recommends identifying API clients.

    You can set your email without changing code:

        Windows:
        set CROSSREF_MAILTO=your_email@example.com

        PowerShell:
        $env:CROSSREF_MAILTO="your_email@example.com"

        GitHub Actions:
        env:
          CROSSREF_MAILTO: ${{ secrets.CROSSREF_MAILTO }}

    The collector also works if no email is supplied.
    """
    email = (
        _clean(mailto)
        or _clean(os.getenv("CROSSREF_MAILTO"))
    )

    if email:
        user_agent = f"PaperMonitor/14.6 (mailto:{email})"
    else:
        user_agent = "PaperMonitor/14.6"

    return {
        "User-Agent": user_agent,
        "Accept": "application/json",
    }


def _wait_for_rate_limit():
    """
    Enforce a minimum delay between consecutive Crossref requests,
    even when fetch() is called repeatedly by update.py.
    """
    global _last_request_time

    now = time.monotonic()
    elapsed = now - _last_request_time
    wait = _MIN_INTERVAL_SECONDS - elapsed

    if wait > 0:
        time.sleep(wait)

    _last_request_time = time.monotonic()


def _retry_after_seconds(response):
    """
    Respect Retry-After when Crossref provides it.
    Supports both integer seconds and HTTP-date formats.
    """
    value = response.headers.get("Retry-After")

    if not value:
        return None

    value = value.strip()

    if value.isdigit():
        return max(1, int(value))

    try:
        retry_at = parsedate_to_datetime(value)

        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(
                tzinfo=datetime.timezone.utc
            )

        now = datetime.datetime.now(
            datetime.timezone.utc
        )

        seconds = int(
            (retry_at - now).total_seconds()
        )

        return max(1, seconds)

    except Exception:
        return None


def _request_json(url, params, headers, timeout=45):
    """
    Robust Crossref GET with:
    - connection reuse
    - rate limiting
    - retries
    - exponential backoff
    - Retry-After support
    - random jitter
    """
    total_attempts = 1 + len(_RETRY_DELAYS)

    for attempt in range(total_attempts):

        _wait_for_rate_limit()

        try:
            response = _SESSION.get(
                url,
                params=params,
                headers=headers,
                timeout=timeout,
            )

            if response.status_code in _RETRY_STATUS:
                if attempt >= total_attempts - 1:
                    response.raise_for_status()

                retry_after = _retry_after_seconds(
                    response
                )

                base_wait = _RETRY_DELAYS[
                    min(attempt, len(_RETRY_DELAYS) - 1)
                ]

                wait = (
                    retry_after
                    if retry_after is not None
                    else base_wait
                )

                wait += random.uniform(0.2, 0.8)

                print(
                    f"  Crossref HTTP "
                    f"{response.status_code}; "
                    f"retrying in {wait:.1f}s..."
                )

                time.sleep(wait)
                continue

            response.raise_for_status()
            return response.json()

        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.ChunkedEncodingError,
        ) as exc:

            if attempt >= total_attempts - 1:
                raise

            wait = _RETRY_DELAYS[
                min(attempt, len(_RETRY_DELAYS) - 1)
            ] + random.uniform(0.2, 0.8)

            print(
                "  Crossref connection error "
                f"({type(exc).__name__}); "
                f"retrying in {wait:.1f}s..."
            )

            time.sleep(wait)

    raise RuntimeError(
        "Crossref request failed after retries."
    )


def _authors(item):
    result = []

    for author in item.get("author", []) or []:
        given = _clean(author.get("given"))
        family = _clean(author.get("family"))

        name = " ".join(
            x for x in (given, family) if x
        ).strip()

        if name:
            result.append(name)

    return "; ".join(result)


def _date_parts(item, field):
    block = item.get(field) or {}
    parts = block.get("date-parts") or []

    if not parts or not parts[0]:
        return None

    values = parts[0]

    try:
        return [int(x) for x in values]
    except Exception:
        return None


def _format_date(parts):
    if not parts:
        return ""

    year = parts[0]

    if len(parts) >= 3:
        return f"{year:04d}-{parts[1]:02d}-{parts[2]:02d}"

    if len(parts) >= 2:
        return f"{year:04d}-{parts[1]:02d}"

    return f"{year:04d}"


def _created_date(item):
    created = item.get("created") or {}
    value = _clean(created.get("date-time"))

    if not value:
        return ""

    # Crossref date-time is normally ISO 8601.
    # The first 10 characters are YYYY-MM-DD.
    if len(value) >= 10:
        return value[:10]

    return ""


def _online_date(item):
    """
    Publication-date preference:
    published-online
    -> published-print
    -> issued
    -> published

    If the selected publication date has only year/month but
    Crossref's created date has a complete day, use created date
    as the practical YYYY-MM-DD display date.
    """
    for field in (
        "published-online",
        "published-print",
        "issued",
        "published",
    ):
        parts = _date_parts(item, field)

        if not parts:
            continue

        formatted = _format_date(parts)

        if len(parts) < 3:
            created = _created_date(item)

            if created:
                return created

        return formatted

    return _created_date(item)


def fetch(
    issn,
    days=3,
    rows=50,
    mailto=None,
    timeout=45,
):
    """
    Fetch recent Crossref records for one journal ISSN.

    Parameters
    ----------
    issn : str
        Journal pISSN used in the project.
    days : int
        Crossref metadata-created lookback window.
    rows : int
        Maximum records returned for this journal.
    mailto : str | None
        Optional Crossref contact email.
        If omitted, CROSSREF_MAILTO environment variable is used.
    timeout : int
        HTTP timeout in seconds.

    Returns
    -------
    list[dict]
        Each item contains:
        doi, title, authors, journal, online_date
    """
    issn = _clean(issn)

    if not issn:
        return []

    try:
        days = max(0, int(days))
    except Exception:
        days = 3

    try:
        rows = max(1, min(int(rows), 1000))
    except Exception:
        rows = 50

    start = (
        datetime.datetime.utcnow()
        - datetime.timedelta(days=days)
    ).strftime("%Y-%m-%d")

    params = {
        "rows": rows,
        "sort": "created",
        "order": "desc",
        "filter": f"from-created-date:{start}",
    }

    email = (
        _clean(mailto)
        or _clean(os.getenv("CROSSREF_MAILTO"))
    )

    # mailto parameter helps Crossref identify polite API users.
    if email:
        params["mailto"] = email

    url = CROSSREF_URL.format(issn=issn)

    payload = _request_json(
        url=url,
        params=params,
        headers=_build_headers(email),
        timeout=timeout,
    )

    items = (
        payload.get("message", {}).get("items", [])
        if isinstance(payload, dict)
        else []
    )

    result = []

    for item in items:

        doi = _clean(item.get("DOI"))

        title_list = item.get("title") or []
        title = (
            _clean(title_list[0])
            if title_list
            else ""
        )

        container = (
            item.get("container-title") or []
        )

        journal = (
            _clean(container[0])
            if container
            else ""
        )

        result.append({
            "doi": doi,
            "title": title,
            "authors": _authors(item),
            "journal": journal,
            "online_date": _online_date(item),
        })

    return result

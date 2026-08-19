from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import EXPORT_DAYS, EXPORT_LIMIT, WEB_JSON_PATH
from .db import Article, engine, init_db
from .journals import load_journal_list, match_journal


def display_date(article: Article) -> str:
    if article.date_precision == "day" and article.online_date:
        return article.online_date.isoformat()
    return article.online_date_raw or (article.online_date.isoformat() if article.online_date else "")


def source_label(source: str) -> str:
    text = source or ""
    low = text.lower()
    if "saved search rss" in low:
        return "IEEE Saved Search RSS"
    if "springer meta api" in low:
        return "Springer Meta API"
    if "springer online first" in low:
        return "Springer Online First"
    if "sciencedirect rss" in low:
        return "ScienceDirect RSS"
    if "sciencedirect page" in low or "available online" in low:
        return "ScienceDirect page"
    if "crossref" in low:
        return "Crossref"
    if "sciencedirect api" in low:
        return "ScienceDirect API"
    return text


def export_json() -> int:
    init_db()
    cutoff = date.today() - timedelta(days=EXPORT_DAYS)
    with Session(engine) as session:
        stmt = (
            select(Article)
            .where(
                Article.status == "published",
                Article.online_date.is_not(None),
                Article.online_date >= cutoff,
            )
            .order_by(Article.online_date.desc(), Article.first_seen_at.desc())
        )
        candidates = session.scalars(stmt).all()
        pending_count = session.scalar(select(func.count()).select_from(Article).where(Article.status == "pending")) or 0

    rows = [a for a in candidates if match_journal(a.provider, a.journal, a.issn) is not None][:EXPORT_LIMIT]
    specs = load_journal_list()
    journal_filters = [
        {"publisher": s.publisher, "journal": s.journal, "category": s.category}
        for s in sorted(specs, key=lambda x: (x.publisher.lower(), x.journal.lower()))
    ]
    publishers = sorted({s.publisher for s in specs})

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(rows),
        "monitoring": {
            "journal_count": len(specs),
            "publisher_count": len(publishers),
            "pending_count": int(pending_count),
        },
        "filters": {"publishers": publishers, "journals": journal_filters},
        "articles": [
            {
                "publisher": a.publisher,
                "provider": a.provider,
                "title": a.title,
                "journal": a.journal,
                "authors": a.authors,
                "doi": a.doi or "",
                "url": a.url,
                "online_date": a.online_date.isoformat() if a.online_date else "",
                "display_date": display_date(a),
                "date_precision": a.date_precision,
                "content_type": a.content_type,
                "source": source_label(a.online_date_source),
            }
            for a in rows
        ],
    }
    WEB_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    WEB_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(rows)

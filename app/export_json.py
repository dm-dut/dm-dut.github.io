from __future__ import annotations

import json
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import EXPORT_DAYS, EXPORT_LIMIT, ROOT
from .db import Article, engine, init_db
from .journals import match_journal

OUTPUT = ROOT / "paper-monitor" / "data" / "online_papers.json"


def display_date(article: Article) -> str:
    if article.date_precision == "day" and article.online_date:
        return article.online_date.isoformat()
    return article.online_date_raw or (article.online_date.isoformat() if article.online_date else "")


def export_json() -> int:
    """Export only records that are still present in the current enabled whitelist.

    This means disabling/removing a journal hides its historical rows from the website
    without destructively deleting them from the database.
    """
    init_db()
    cutoff = date.today() - timedelta(days=EXPORT_DAYS)
    with Session(engine) as session:
        stmt = (
            select(Article)
            .where((Article.online_date == None) | (Article.online_date >= cutoff))  # noqa: E711
            .order_by(Article.online_date.desc().nullslast(), Article.first_seen_at.desc())
        )
        candidates = session.scalars(stmt).all()

    rows = [a for a in candidates if match_journal(a.provider, a.journal, a.issn) is not None][:EXPORT_LIMIT]

    payload = {
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "count": len(rows),
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
            }
            for a in rows
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(rows)


if __name__ == "__main__":
    print(f"exported={export_json()}")

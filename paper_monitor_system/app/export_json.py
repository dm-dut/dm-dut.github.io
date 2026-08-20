from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import EXPORT_DAYS, EXPORT_LIMIT, WEB_JSON_PATH
from .db import Article, engine, init_db
from .journals import load_journal_list, match_journal


def article_sort_key(a: Article):
    return (
        -a.fetched_date.toordinal(),
        (a.journal or "").casefold(),
        -(a.sort_date.toordinal() if a.sort_date else 0),
        int(a.source_rank or 9999),
        a.id or 0,
    )


def export_json() -> int:
    init_db()
    cutoff = date.today() - timedelta(days=max(1, EXPORT_DAYS))
    with Session(engine) as session:
        rows = session.scalars(select(Article).where(Article.fetched_date >= cutoff)).all()

    rows = [a for a in rows if match_journal(a.provider, a.journal, a.issn) is not None]
    rows = sorted(rows, key=article_sort_key)[:EXPORT_LIMIT]
    specs = load_journal_list()
    publishers = sorted({s.publisher for s in specs})
    journals = [
        {"publisher": s.publisher, "journal": s.journal, "category": s.category}
        for s in sorted(specs, key=lambda x: (x.publisher.lower(), x.journal.lower()))
    ]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(rows),
        "monitoring": {"journal_count": len(specs), "publisher_count": len(publishers)},
        "filters": {"publishers": publishers, "journals": journals},
        "sort": ["fetched_date desc", "journal asc", "online_sort_date desc", "source_rank asc"],
        "articles": [
            {
                "publisher": a.publisher,
                "provider": a.provider,
                "journal": a.journal,
                "authors": a.authors,
                "title": a.title,
                "fetched_date": a.fetched_date.isoformat(),
                "display_date": a.display_date or "",
                "online_sort_date": a.sort_date.isoformat() if a.sort_date else "",
                "date_kind": a.date_kind or "",
                "date_precision": a.date_precision or "",
                "source_rank": a.source_rank,
                "url": a.url,
                "source": a.date_source or "",
                "doi": a.doi or "",
            }
            for a in rows
        ],
    }
    WEB_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    WEB_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(rows)

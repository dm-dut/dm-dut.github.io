from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import EXPORT_DAYS, EXPORT_LIMIT, WEB_JSON_PATH
from .db import Article, engine, init_db
from .journals import load_journal_list


def export_json() -> int:
    init_db()
    cutoff=date.today()-timedelta(days=EXPORT_DAYS)
    with Session(engine) as session:
        rows=session.scalars(
            select(Article).where(Article.online_date>=cutoff).order_by(Article.online_date.desc(),Article.first_seen_at.desc())
        ).all()[:EXPORT_LIMIT]
    specs=load_journal_list()
    publishers=sorted({s.publisher for s in specs})
    payload={
        'generated_at':datetime.now(timezone.utc).isoformat(),
        'count':len(rows),
        'monitoring':{'journal_count':len(specs),'publisher_count':len(publishers),'pending_count':0,'source':'Crossref'},
        'filters':{
            'publishers':publishers,
            'journals':[{'publisher':s.publisher,'journal':s.journal,'category':s.category} for s in sorted(specs,key=lambda x:(x.publisher,x.journal))],
        },
        'articles':[
            {
                'publisher':a.publisher,'provider':a.provider,'title':a.title,'journal':a.journal,'authors':a.authors,
                'doi':a.doi or '','url':a.url,'online_date':a.online_date.isoformat(),'display_date':a.online_date.isoformat(),
                'date_precision':'day','content_type':a.content_type,'source':a.date_source,
            } for a in rows
        ],
    }
    WEB_JSON_PATH.parent.mkdir(parents=True,exist_ok=True)
    WEB_JSON_PATH.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    return len(rows)

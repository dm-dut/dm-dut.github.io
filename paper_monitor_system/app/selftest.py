from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from .db import Article, Base, source_priority, upsert_article
from .journals import JournalSpec
from .providers import crossref, springer


def main() -> None:
    spec = JournalSpec(
        provider="springer",
        publisher="Springer Nature",
        journal="Annals of Operations Research",
        issns=("02545330", "15729338"),
    )
    queries = springer._queries(spec, date(2026, 8, 12), date(2026, 8, 19))
    assert queries[0].startswith("onlinedatefrom:2026-08-12 onlinedateto:2026-08-19 issn:")
    assert "type:Journal" not in " ".join(queries)
    assert "1572-9338" in queries[0], "eISSN should be tried first for online-first monitoring"

    sample = {"published-online": {"date-parts": [[2026, 8, 19]]}}
    d, precision, raw = crossref._date_parts(sample)
    assert d == date(2026, 8, 19) and precision == "day" and raw == "2026-08-19"

    assert source_priority("Springer Meta API onlineDate") > source_priority("Crossref published-online fallback")
    assert source_priority("ScienceDirect API Load-Date") > source_priority("Crossref published-online fallback")
    assert source_priority("IEEE Xplore API publication_date") > source_priority("Crossref published-online fallback")

    # Verify a later Crossref fallback cannot downgrade an authoritative date.
    mem = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(mem)
    primary = {
        "identity_key": "k1", "provider": "springer", "publisher": "Springer Nature",
        "title": "Test paper", "journal": "Annals of Operations Research", "authors": "A",
        "doi": "10.1000/test", "external_id": None, "issn": "0254-5330",
        "content_type": "Article", "url": "", "online_date": date(2026, 8, 19),
        "online_date_raw": "2026-08-19", "date_precision": "day",
        "online_date_source": "Springer Meta API onlineDate", "source_update_date": date(2026, 8, 19),
    }
    fallback = dict(primary)
    fallback.update({
        "online_date": date(2026, 8, 18),
        "online_date_raw": "2026-08-18",
        "online_date_source": "Crossref published-online fallback",
    })
    with Session(mem) as session:
        upsert_article(session, primary)
        session.commit()
        upsert_article(session, fallback)
        session.commit()
        row = session.scalar(select(Article).where(Article.doi == "10.1000/test"))
        assert row.online_date == date(2026, 8, 19)
        assert row.online_date_source == "Springer Meta API onlineDate"

    print("SELF-TEST OK")


if __name__ == "__main__":
    main()

from __future__ import annotations

from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from .config import REPO_ROOT
from .db import Article, Base, source_priority, upsert_article
from .journals import JournalSpec, enabled_journals
from .providers import crossref, ieee, sciencedirect, springer


def test_modes_and_ieee_feed():
    assert len(enabled_journals("sciencedirect")) == 39
    assert all(s.mode == "elsevier_incremental" for s in enabled_journals("sciencedirect"))
    assert all(s.mode == "springer_batch_api" for s in enabled_journals("springer"))
    urls = ieee._combined_rss_urls(enabled_journals("ieee"))
    assert len(urls) == 1
    params = parse_qs(urlsplit(urls[0]).query)
    assert params.get("rssFeed") == ["true"]
    assert params.get("rowsPerPage") == ["10"]


def test_crossref_incremental_pending_parser():
    spec = JournalSpec("sciencedirect", "Elsevier", "Applied Soft Computing", ("15684946", "18729681"))
    pending_item = {
        "DOI": "10.1016/j.asoc.2026.1", "title": ["Pending paper"], "ISSN": ["1872-9681"],
        "author": [{"given": "A", "family": "B"}], "URL": "https://doi.org/10.1016/j.asoc.2026.1",
    }
    rec = crossref._to_record("sciencedirect", "Elsevier", spec, pending_item, allow_pending=True, max_online_date=date(2026,8,19))
    assert rec is not None and rec.status == "pending" and rec.online_date is None

    published_item = dict(pending_item)
    published_item["published-online"] = {"date-parts": [[2026, 8, 19]]}
    rec2 = crossref._to_record("sciencedirect", "Elsevier", spec, published_item, allow_pending=True, max_online_date=date(2026,8,19))
    assert rec2 is not None and rec2.status == "published" and rec2.online_date == date(2026,8,19)


def test_pending_promotes_without_downgrade():
    memory = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(memory)
    pending = {
        "identity_key":"x", "provider":"sciencedirect", "publisher":"Elsevier", "title":"T", "journal":"J",
        "authors":"A", "doi":"10.1/x", "external_id":None, "issn":"", "content_type":"Article", "url":"",
        "online_date":None, "online_date_raw":"", "date_precision":"unknown",
        "online_date_source":"Crossref index-date discovery; awaiting published-online", "source_update_date":None, "status":"pending",
    }
    published = dict(pending)
    published.update(online_date=date(2026,8,19), online_date_raw="2026-08-19", date_precision="day",
                     online_date_source="Crossref pending recheck + published-online", source_update_date=date(2026,8,19), status="published")
    lower_pending = dict(pending)
    with Session(memory) as session:
        upsert_article(session, pending); session.commit()
        row = session.scalar(select(Article).where(Article.doi == "10.1/x"))
        assert row.status == "pending" and row.online_date is None
        upsert_article(session, published); session.commit()
        row = session.scalar(select(Article).where(Article.doi == "10.1/x"))
        assert row.status == "published" and row.online_date == date(2026,8,19)
        upsert_article(session, lower_pending); session.commit()
        row = session.scalar(select(Article).where(Article.doi == "10.1/x"))
        assert row.status == "published" and row.online_date == date(2026,8,19)


def test_springer_batch_parser_and_query():
    journals = enabled_journals("springer")
    spec = next(s for s in journals if s.journal == "Annals of Operations Research")
    variants = springer._batch_query_variants(date(2026,8,18), date(2026,8,19))
    assert any("onlinedatefrom:2026-08-18" in q and "onlinedateto:2026-08-19" in q for q in variants)
    row = {
        "publicationType":"Journal", "publicationName":"Annals of Operations Research", "issn":"1572-9338",
        "title":"AOR paper", "onlineDate":"2026-08-19", "doi":"10.1007/test", "creators":[{"creator":"A"}],
        "identifier":"doi:10.1007/test", "url":[{"value":"https://link.springer.com/article/10.1007/test"}],
    }
    rec = springer._record_from_row(spec, row, date(2026,8,18), date(2026,8,19))
    assert rec is not None and rec.online_date == date(2026,8,19)


def test_sciencedirect_crossref_is_primary_default_logic():
    import inspect
    text = inspect.getsource(sciencedirect.fetch)
    assert "incremental_discover" in text
    assert "spec.rss_url" in text
    assert "/journals/{" not in inspect.getsource(crossref._request_items)


def test_priority():
    assert source_priority("Springer Meta API onlineDate") > source_priority("Crossref published-online fallback")
    assert source_priority("ScienceDirect page Available online") > source_priority("Crossref published-online fallback")


def test_local_workflow_and_scripts():
    text = (REPO_ROOT / ".github/workflows/update-paper-monitor.yml").read_text(encoding="utf-8")
    assert "schedule:" not in text
    assert "git pull --rebase" not in text
    for name in ("setup_local.bat", "test_connections.bat", "update_papers.bat", "fetch_only.bat"):
        assert (REPO_ROOT / name).exists(), name


def main():
    test_modes_and_ieee_feed()
    test_crossref_incremental_pending_parser()
    test_pending_promotes_without_downgrade()
    test_springer_batch_parser_and_query()
    test_sciencedirect_crossref_is_primary_default_logic()
    test_priority()
    test_local_workflow_and_scripts()
    print("SELF-TEST OK")


if __name__ == "__main__":
    main()

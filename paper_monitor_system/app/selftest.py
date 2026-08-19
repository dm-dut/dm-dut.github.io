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
    elsevier = enabled_journals("sciencedirect")
    assert len(elsevier) == 39
    assert all(s.mode == "elsevier_member_batch" for s in elsevier)
    assert all(s.crossref_member == 78 and s.crossref_prefix == "10.1016" for s in elsevier)
    assert all(s.mode == "springer_batch_api" for s in enabled_journals("springer"))
    urls = ieee._combined_rss_urls(enabled_journals("ieee"))
    assert len(urls) == 1
    params = parse_qs(urlsplit(urls[0]).query)
    assert params.get("rssFeed") == ["true"]
    assert params.get("rowsPerPage") == ["10"]


def test_crossref_pending_parser():
    spec = JournalSpec(
        "sciencedirect", "Elsevier", "Applied Soft Computing", ("15684946", "18729681"),
        crossref_member=78, crossref_prefix="10.1016", crossref_group="Elsevier-78",
    )
    pending_item = {
        "DOI": "10.1016/j.asoc.2026.1", "title": ["Pending paper"], "ISSN": ["1872-9681"],
        "container-title": ["Applied Soft Computing"],
        "author": [{"given": "A", "family": "B"}], "URL": "https://doi.org/10.1016/j.asoc.2026.1",
    }
    rec = crossref._to_record(
        "sciencedirect", "Elsevier", spec, pending_item, allow_pending=True,
        max_online_date=date(2026, 8, 19), pending_source_label="batch pending",
    )
    assert rec is not None and rec.status == "pending" and rec.online_date is None
    published_item = dict(pending_item)
    published_item["published-online"] = {"date-parts": [[2026, 8, 19]]}
    rec2 = crossref._to_record(
        "sciencedirect", "Elsevier", spec, published_item, allow_pending=True,
        max_online_date=date(2026, 8, 19), source_label="Crossref member batch + published-online",
    )
    assert rec2 is not None and rec2.status == "published" and rec2.online_date == date(2026, 8, 19)


def test_crossref_member_batch_mock():
    journals = enabled_journals("sciencedirect")
    target = journals[0]
    captured = {}
    old_json, old_session = crossref.get_json, crossref.build_session
    try:
        def fake_json(session, url, *, params=None, headers=None):
            captured["url"] = url
            captured["params"] = dict(params or {})
            return {"message": {"items": [
                {
                    "DOI": "10.1016/j.asoc.2026.123",
                    "title": ["Target batch paper"],
                    "container-title": [target.journal],
                    "ISSN": ["1872-9681"],
                    "published-online": {"date-parts": [[2026, 8, 19]]},
                    "URL": "https://doi.org/10.1016/j.asoc.2026.123",
                },
                {
                    "DOI": "10.1016/j.not-monitored.1",
                    "title": ["Not monitored"],
                    "container-title": ["Some Other Journal"],
                    "ISSN": ["0000-0000"],
                },
            ], "next-cursor": None}}
        crossref.get_json = fake_json
        crossref.build_session = lambda: object()
        records = list(crossref.member_batch_discover(
            "sciencedirect", "Elsevier", date(2026, 8, 18), date(2026, 8, 19), journals
        ))
    finally:
        crossref.get_json, crossref.build_session = old_json, old_session
    assert len(records) == 1 and records[0].journal == target.journal
    assert "/members/78/works" in captured["url"]
    filt = captured["params"]["filter"]
    assert "from-created-date:2026-08-18" in filt and "until-created-date:2026-08-19" in filt
    assert "prefix:10.1016" in filt
    assert captured["params"].get("select") == crossref.SELECT_FIELDS


def test_pending_promotes_without_downgrade():
    memory = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(memory)
    pending = {
        "identity_key": "x", "provider": "sciencedirect", "publisher": "Elsevier", "title": "T", "journal": "J",
        "authors": "A", "doi": "10.1/x", "external_id": None, "issn": "", "content_type": "Article", "url": "",
        "online_date": None, "online_date_raw": "", "date_precision": "unknown",
        "online_date_source": "Crossref member batch discovery; awaiting published-online", "source_update_date": None, "status": "pending",
    }
    published = dict(pending)
    published.update(
        online_date=date(2026, 8, 19), online_date_raw="2026-08-19", date_precision="day",
        online_date_source="Crossref pending recheck + published-online", source_update_date=date(2026, 8, 19), status="published",
    )
    with Session(memory) as session:
        upsert_article(session, pending); session.commit()
        row = session.scalar(select(Article).where(Article.doi == "10.1/x"))
        assert row.status == "pending" and row.online_date is None
        upsert_article(session, published); session.commit()
        row = session.scalar(select(Article).where(Article.doi == "10.1/x"))
        assert row.status == "published" and row.online_date == date(2026, 8, 19)
        upsert_article(session, pending); session.commit()
        row = session.scalar(select(Article).where(Article.doi == "10.1/x"))
        assert row.status == "published" and row.online_date == date(2026, 8, 19)


def test_springer_batch_parser_and_query():
    journals = enabled_journals("springer")
    spec = next(s for s in journals if s.journal == "Annals of Operations Research")
    variants = springer._batch_query_variants(date(2026, 8, 18), date(2026, 8, 19))
    assert any("onlinedatefrom:2026-08-18" in q and "onlinedateto:2026-08-19" in q for q in variants)
    row = {
        "publicationType": "Journal", "publicationName": "Annals of Operations Research", "issn": "1572-9338",
        "title": "AOR paper", "onlineDate": "2026-08-19", "doi": "10.1007/test", "creators": [{"creator": "A"}],
        "identifier": "doi:10.1007/test", "url": [{"value": "https://link.springer.com/article/10.1007/test"}],
    }
    rec = springer._record_from_row(spec, row, date(2026, 8, 18), date(2026, 8, 19))
    assert rec is not None and rec.online_date == date(2026, 8, 19)



def test_springer_batch_mock():
    journals = enabled_journals("springer")
    target = next(s for s in journals if s.journal == "Annals of Operations Research")
    captured = {}
    old_json, old_session, old_key = springer.get_json, springer.build_session, springer.SPRINGER_API_KEY
    try:
        def fake_json(session, url, *, params=None, headers=None):
            captured["url"] = url
            captured["params"] = dict(params or {})
            return {"records": [
                {
                    "publicationType": "Journal",
                    "publicationName": target.journal,
                    "issn": "1572-9338",
                    "title": "Batch AOR paper",
                    "onlineDate": "2026-08-19",
                    "doi": "10.1007/batch-test",
                    "creators": [{"creator": "Author A"}],
                    "identifier": "doi:10.1007/batch-test",
                    "url": [{"value": "https://link.springer.com/article/10.1007/batch-test"}],
                },
                {
                    "publicationType": "Journal",
                    "publicationName": "Unmonitored Springer Journal",
                    "issn": "0000-0000",
                    "title": "Ignore me",
                    "onlineDate": "2026-08-19",
                },
            ]}
        springer.get_json = fake_json
        springer.build_session = lambda: object()
        springer.SPRINGER_API_KEY = "test-key"
        records = springer._batch_api(date(2026, 8, 18), date(2026, 8, 19), journals)
    finally:
        springer.get_json, springer.build_session, springer.SPRINGER_API_KEY = old_json, old_session, old_key
    assert len(records) == 1 and records[0].journal == target.journal
    assert captured["url"].endswith("/meta/v2/json")
    assert int(captured["params"]["p"]) >= 20


def test_ieee_crossref_first_mock():
    journals = enabled_journals("ieee")
    target = next(s for s in journals if s.journal == "IEEE Transactions on Cybernetics")
    old_resolve, old_page = ieee.resolve_crossref, ieee.page_metadata
    page_called = {"value": False}
    try:
        def fake_resolve(title, spec, doi=None):
            return {
                "doi": "10.1109/tcyb.2026.123",
                "online_date": date(2026, 8, 19),
                "online_raw": "2026-08-19",
                "precision": "day",
                "authors": "A. Author",
                "url": "https://doi.org/10.1109/tcyb.2026.123",
                "journal": target.journal,
                "issn": "2168-2275",
            }
        def fake_page(url):
            page_called["value"] = True
            raise AssertionError("publisher page should not be needed when Crossref is complete")
        ieee.resolve_crossref = fake_resolve
        ieee.page_metadata = fake_page
        rec = ieee._entry_to_record({
            "title": "A new cybernetics paper",
            "link": "https://ieeexplore.ieee.org/document/123456",
            "id": "doi:10.1109/TCYB.2026.123",
            "summary": target.journal,
        }, journals, date(2026, 8, 18), date(2026, 8, 19))
    finally:
        ieee.resolve_crossref, ieee.page_metadata = old_resolve, old_page
    assert rec is not None and rec.journal == target.journal and rec.online_date == date(2026, 8, 19)
    assert not page_called["value"]

def test_priority():
    assert source_priority("Springer Meta API onlineDate") > source_priority("Crossref member batch + published-online")
    assert source_priority("ScienceDirect page Available online") > source_priority("Crossref member batch + published-online")


def test_local_workflow_and_scripts():
    text = (REPO_ROOT / ".github/workflows/update-paper-monitor.yml").read_text(encoding="utf-8")
    assert "schedule:" not in text
    assert "git pull --rebase" not in text
    for name in ("setup_local.bat", "test_connections.bat", "update_papers.bat", "fetch_only.bat", "update_papers.ps1"):
        assert (REPO_ROOT / name).exists(), name
    bat = (REPO_ROOT / "update_papers.bat").read_text(encoding="utf-8", errors="ignore").lower()
    assert "pause" not in bat, "scheduled update_papers.bat must not pause"


def main():
    test_modes_and_ieee_feed()
    test_crossref_pending_parser()
    test_crossref_member_batch_mock()
    test_pending_promotes_without_downgrade()
    test_springer_batch_parser_and_query()
    test_springer_batch_mock()
    test_ieee_crossref_first_mock()
    test_priority()
    test_local_workflow_and_scripts()
    print("SELF-TEST OK")


if __name__ == "__main__":
    main()

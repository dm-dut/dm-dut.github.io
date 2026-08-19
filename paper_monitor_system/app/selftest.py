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
    assert all(s.mode == "elsevier_member_dual_batch" for s in elsevier)
    assert all(s.crossref_member == 78 and not s.crossref_prefix for s in elsevier)
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
    captured_filters = []
    old_json, old_session = crossref.get_json, crossref.build_session
    try:
        def fake_json(session, url, *, params=None, headers=None):
            filt = (params or {}).get("filter", "")
            captured_filters.append(filt)
            if "from-online-pub-date" in filt:
                items = [
                    {
                        "DOI": "10.1016/j.asoc.2026.123",
                        "title": ["Target online paper"],
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
                ]
            else:
                items = [
                    {
                        "DOI": "10.1016/j.asoc.2026.123",
                        "title": ["Target online paper"],
                        "container-title": [target.journal],
                        "ISSN": ["1872-9681"],
                        "published-online": {"date-parts": [[2026, 8, 19]]},
                        "URL": "https://doi.org/10.1016/j.asoc.2026.123",
                    },
                    {
                        "DOI": "10.1016/j.asoc.2026.pending",
                        "title": ["Target pending paper"],
                        "container-title": [target.journal],
                        "ISSN": ["1872-9681"],
                        "URL": "https://doi.org/10.1016/j.asoc.2026.pending",
                    },
                ]
            return {"message": {"items": items, "next-cursor": None}}
        crossref.get_json = fake_json
        crossref.build_session = lambda: object()
        records = list(crossref.member_dual_batch_discover(
            "sciencedirect", "Elsevier", date(2026, 8, 18), date(2026, 8, 19), journals
        ))
    finally:
        crossref.get_json, crossref.build_session = old_json, old_session
    assert len(records) == 2
    assert sum(r.online_date is not None for r in records) == 1
    assert sum(r.online_date is None for r in records) == 1
    assert any("from-online-pub-date:2026-08-18" in f and "until-online-pub-date:2026-08-19" in f for f in captured_filters)
    assert any("from-update-date:2026-08-18" in f and "until-update-date:2026-08-19" in f for f in captured_filters)
    assert all("prefix:" not in f for f in captured_filters)


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
        records, truncated = springer._batch_api(date(2026, 8, 18), date(2026, 8, 19), journals)
    finally:
        springer.get_json, springer.build_session, springer.SPRINGER_API_KEY = old_json, old_session, old_key
    assert len(records) == 1 and records[0].journal == target.journal and truncated is False
    assert captured["url"].endswith("/meta/v2/json")
    assert int(captured["params"]["p"]) == 20
    assert " AND " not in captured["params"]["q"]


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

def test_ieee_rss_date_fallback_mock():
    journals = enabled_journals("ieee")
    target = next(s for s in journals if s.journal == "IEEE Transactions on Cybernetics")
    old_resolve, old_page = ieee.resolve_crossref, ieee.page_metadata
    try:
        def fake_resolve(title, spec, doi=None):
            return {
                "doi": "10.1109/tcyb.2026.rss",
                "online_date": None,
                "online_raw": "",
                "precision": "unknown",
                "authors": "A. Author",
                "url": "https://doi.org/10.1109/tcyb.2026.rss",
                "journal": target.journal,
                "issn": "2168-2275",
            }
        ieee.resolve_crossref = fake_resolve
        ieee.page_metadata = lambda url: {}
        rec = ieee._entry_to_record({
            "title": "RSS fallback cybernetics paper",
            "link": "https://ieeexplore.ieee.org/document/123457",
            "id": "doi:10.1109/TCYB.2026.RSS",
            "summary": target.journal,
            "published": "Wed, 19 Aug 2026 08:00:00 GMT",
        }, journals, date(2026, 8, 18), date(2026, 8, 19))
    finally:
        ieee.resolve_crossref, ieee.page_metadata = old_resolve, old_page
    assert rec is not None
    assert rec.journal == target.journal
    assert rec.online_date == date(2026, 8, 19)
    assert rec.online_date_source == "IEEE Saved Search RSS pubDate fallback"


def test_ieee_rss_date_can_be_upgraded_by_crossref():
    memory = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(memory)
    rss = {
        "identity_key": "ieee-rss", "provider": "ieee", "publisher": "IEEE", "title": "RSS paper",
        "journal": "IEEE Transactions on Cybernetics", "authors": "A", "doi": "10.1109/test.rss",
        "external_id": None, "issn": "2168-2275", "content_type": "Journal Article", "url": "",
        "online_date": date(2026, 8, 19), "online_date_raw": "Wed, 19 Aug 2026 08:00:00 GMT",
        "date_precision": "day", "online_date_source": "IEEE Saved Search RSS pubDate fallback",
        "source_update_date": date(2026, 8, 19), "status": "published",
    }
    crossref_record = dict(rss)
    crossref_record.update(
        online_date=date(2026, 8, 18), online_date_raw="2026-08-18",
        online_date_source="IEEE Saved Search RSS + Crossref published-online",
        source_update_date=date(2026, 8, 18),
    )
    with Session(memory) as session:
        upsert_article(session, rss); session.commit()
        upsert_article(session, crossref_record); session.commit()
        row = session.scalar(select(Article).where(Article.doi == "10.1109/test.rss"))
        assert row.online_date == date(2026, 8, 18)
        assert "Crossref published-online" in row.online_date_source


def test_springer_prefix_batch_mock():
    journals = enabled_journals("springer")
    target = next(s for s in journals if s.journal == "Annals of Operations Research")
    captured = {}
    old_json, old_session = crossref.get_json, crossref.build_session
    try:
        def fake_json(session, url, *, params=None, headers=None):
            captured["url"] = url
            captured["params"] = dict(params or {})
            return {"message": {"items": [{
                "DOI": "10.1007/s10479-026-test",
                "title": ["Springer prefix batch paper"],
                "container-title": [target.journal],
                "ISSN": ["1572-9338"],
                "published-online": {"date-parts": [[2026, 8, 19]]},
                "URL": "https://doi.org/10.1007/s10479-026-test",
            }], "next-cursor": None}}
        crossref.get_json = fake_json
        crossref.build_session = lambda: object()
        records = list(crossref.prefix_batch_discover(
            "springer", "Springer Nature", date(2026, 8, 18), date(2026, 8, 19), journals, prefix="10.1007"
        ))
    finally:
        crossref.get_json, crossref.build_session = old_json, old_session
    assert len(records) == 1 and records[0].journal == target.journal
    assert "/prefixes/10.1007/works" in captured["url"]
    assert "from-created-date:2026-08-18" in captured["params"]["filter"]


def test_priority():
    assert source_priority("Springer Meta API onlineDate") > source_priority("Crossref member batch + published-online")
    assert source_priority("ScienceDirect page Available online") > source_priority("Crossref member batch + published-online")
    assert source_priority("Crossref pending recheck + published-online") > source_priority("IEEE Saved Search RSS pubDate fallback")


def test_local_workflow_and_scripts():
    text = (REPO_ROOT / ".github/workflows/update-paper-monitor.yml").read_text(encoding="utf-8")
    assert "schedule:" not in text
    assert "git pull --rebase" not in text
    for name in ("setup_local.bat", "test_connections.bat", "update_papers.bat", "update_papers_scheduled.bat", "fetch_only.bat", "update_papers.ps1"):
        assert (REPO_ROOT / name).exists(), name
    interactive = (REPO_ROOT / "update_papers.bat").read_text(encoding="utf-8", errors="ignore").lower()
    scheduled = (REPO_ROOT / "update_papers_scheduled.bat").read_text(encoding="utf-8", errors="ignore").lower()
    ps1 = (REPO_ROOT / "update_papers.ps1").read_text(encoding="utf-8", errors="ignore")
    assert "pause" in interactive, "interactive updater should stay open after manual runs"
    assert "pause" not in scheduled, "scheduled updater must never pause"
    assert "tee-object" not in ps1.lower(), "PowerShell native stderr must not be piped through Tee-Object"
    assert "run_logged" in ps1, "PowerShell wrapper should delegate logging to Python"
    springer_src = (REPO_ROOT / "paper_monitor_system/app/providers/springer.py").read_text(encoding="utf-8")
    assert "per-journal API query warning" not in springer_src
    assert "fallback progress" not in springer_src


def main():
    test_modes_and_ieee_feed()
    test_crossref_pending_parser()
    test_crossref_member_batch_mock()
    test_pending_promotes_without_downgrade()
    test_springer_batch_parser_and_query()
    test_springer_batch_mock()
    test_ieee_crossref_first_mock()
    test_ieee_rss_date_fallback_mock()
    test_ieee_rss_date_can_be_upgraded_by_crossref()
    test_springer_prefix_batch_mock()
    test_priority()
    test_local_workflow_and_scripts()
    print("SELF-TEST OK")


if __name__ == "__main__":
    main()

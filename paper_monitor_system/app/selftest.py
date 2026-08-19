from __future__ import annotations

from datetime import date
from urllib.parse import parse_qs, urlsplit

import requests
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from .config import REPO_ROOT
from .db import Article, Base, source_priority, upsert_article
from .journals import JournalSpec, enabled_journals
from .providers import crossref, ieee, sciencedirect, springer


class FakeResponse:
    def __init__(self, content=b"", text="", status=200, url="https://example.test", headers=None):
        self.content = content
        self.text = text or content.decode("utf-8", "ignore")
        self.status_code = status
        self.url = url
        self.headers = headers or {"content-type": "application/rss+xml"}

    def raise_for_status(self):
        if self.status_code >= 400:
            response = requests.Response()
            response.status_code = self.status_code
            raise requests.HTTPError(response=response)

    def json(self):
        return {}


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.headers = {}

    def get(self, *args, **kwargs):
        return self.response


def test_sciencedirect_candidates_and_rss_discovery():
    spec = JournalSpec(
        "sciencedirect", "Elsevier", "Applied Soft Computing", ("15684946", "18729681"),
        mode="sciencedirect_page", primary_url="https://www.sciencedirect.com/journal/applied-soft-computing/articles-in-press",
    )
    pages = sciencedirect._candidate_pages(spec)
    assert pages[0].endswith("/articles-in-press")
    assert any(x.endswith("/latest") for x in pages)

    html = '''<html><head><link rel="alternate" type="application/rss+xml" href="https://rss.example/feed" /></head></html>'''
    old = sciencedirect.build_session
    sciencedirect.build_session = lambda: FakeSession(FakeResponse(text=html))
    try:
        urls = sciencedirect._discover_rss_urls(spec)
    finally:
        sciencedirect.build_session = old
    assert urls == ["https://rss.example/feed"]


def test_ieee_combined_rss_deduplicates_and_preserves_url():
    specs = enabled_journals("ieee")
    urls = ieee._combined_rss_urls(specs)
    assert len(urls) == 1
    params = parse_qs(urlsplit(urls[0]).query)
    assert params.get("rssFeed") == ["true"]
    assert params.get("rowsPerPage") == ["10"]
    assert "rssFeedName=IEEETrans15" in urls[0]


def test_ieee_entry_whitelist_and_virtual_journal_rejection():
    specs = enabled_journals("ieee")
    tcyb = next(x for x in specs if x.journal == "IEEE Transactions on Cybernetics")
    entry = {
        "title": "A New Cybernetics Paper",
        "link": "https://ieeexplore.ieee.org/document/123",
        "id": "123",
        "summary": "IEEE Biometrics Compendium",
        "published": "Wed, 19 Aug 2026 09:00:00 GMT",
    }
    old_page, old_cr = ieee.page_metadata, ieee.resolve_crossref
    ieee.page_metadata = lambda url: {
        "title": "A New Cybernetics Paper",
        "doi": "10.1109/TCYB.2026.1",
        "journal": "IEEE Transactions on Cybernetics",
        "issn": "2168-2275",
        "online_date": date(2026, 8, 19),
        "online_raw": "2026-08-19",
        "precision": "day",
        "authors": "A; B",
        "url": url,
    }
    ieee.resolve_crossref = lambda *args, **kwargs: {}
    try:
        record = ieee._entry_to_record(entry, specs, date(2026, 8, 18), date(2026, 8, 19))
    finally:
        ieee.page_metadata, ieee.resolve_crossref = old_page, old_cr
    assert record is not None and record.journal == tcyb.journal

    # A real Virtual Journal item with no underlying whitelist metadata is rejected.
    old_page, old_cr = ieee.page_metadata, ieee.resolve_crossref
    ieee.page_metadata = lambda url: {"journal": "IEEE RFIC Virtual Journal", "issn": "", "online_date": date(2026, 8, 19), "online_raw": "2026-08-19", "precision": "day"}
    ieee.resolve_crossref = lambda *args, **kwargs: {"journal": "IEEE RFIC Virtual Journal", "issn": ""}
    try:
        rejected = ieee._entry_to_record({**entry, "title": "RFIC digest item", "summary": "IEEE RFIC Virtual Journal"}, specs, date(2026, 8, 18), date(2026, 8, 19))
    finally:
        ieee.page_metadata, ieee.resolve_crossref = old_page, old_cr
    assert rejected is None


def test_springer_query_variants_and_parser():
    spec = JournalSpec("springer", "Springer Nature", "Annals of Operations Research", ("02545330", "15729338"))
    variants = springer._query_variants(spec, date(2026, 8, 18), date(2026, 8, 19), "15729338")
    assert any("onlinedatefrom:2026-08-18 onlinedateto:2026-08-19" in q for q in variants)
    assert any(" AND " in q for q in variants)
    rows = [{
        "publicationType": "Journal", "title": "AOR paper", "onlineDate": "2026-08-19",
        "doi": "10.1007/test", "creators": [{"creator": "A"}], "identifier": "doi:10.1007/test",
        "url": [{"value": "https://link.springer.com/article/10.1007/test"}],
    }]
    parsed = springer._parse_records(spec, rows, date(2026, 8, 18), date(2026, 8, 19), set())
    assert len(parsed) == 1 and parsed[0].online_date == date(2026, 8, 19)


def test_crossref_global_works_endpoint():
    assert crossref.BASE_URL == "https://api.crossref.org"
    import inspect
    text = inspect.getsource(crossref._request_items)
    assert 'f"{BASE_URL}/works"' in text
    assert 'url = f"{BASE_URL}/works"' in text


def test_priority_and_upsert():
    assert source_priority("Springer Meta API onlineDate") > source_priority("Crossref published-online fallback")
    assert source_priority("ScienceDirect page Available online") > source_priority("Crossref published-online fallback")
    assert source_priority("IEEE Saved Search RSS + IEEE page publication date") > source_priority("Crossref published-online fallback")

    memory = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(memory)
    base = {
        "identity_key": "x", "provider": "springer", "publisher": "Springer Nature", "title": "T", "journal": "J",
        "authors": "A", "doi": "10.1/x", "external_id": None, "issn": "", "content_type": "Article", "url": "",
        "online_date": date(2026, 8, 19), "online_date_raw": "2026-08-19", "date_precision": "day",
        "online_date_source": "Springer Meta API onlineDate", "source_update_date": date(2026, 8, 19),
    }
    lower = dict(base)
    lower.update(online_date=date(2026, 8, 18), online_date_raw="2026-08-18", online_date_source="Crossref published-online fallback")
    with Session(memory) as session:
        upsert_article(session, base); session.commit()
        upsert_article(session, lower); session.commit()
        row = session.scalar(select(Article).where(Article.doi == "10.1/x"))
        assert row.online_date == date(2026, 8, 19)


def test_local_mode_workflow_and_scripts():
    text = (REPO_ROOT / ".github/workflows/update-paper-monitor.yml").read_text(encoding="utf-8")
    assert "schedule:" not in text
    assert "Publisher fetching is disabled on GitHub-hosted runners" in text
    assert "git pull --rebase" not in text
    assert (REPO_ROOT / "setup_local.bat").exists()
    assert (REPO_ROOT / "test_connections.bat").exists()
    assert (REPO_ROOT / "update_papers.bat").exists()
    assert (REPO_ROOT / "paper_monitor_system/app/local_update.py").exists()
    assert (REPO_ROOT / "paper_monitor_system/app/connection_test.py").exists()


def main():
    test_sciencedirect_candidates_and_rss_discovery()
    test_ieee_combined_rss_deduplicates_and_preserves_url()
    test_ieee_entry_whitelist_and_virtual_journal_rejection()
    test_springer_query_variants_and_parser()
    test_crossref_global_works_endpoint()
    test_priority_and_upsert()
    test_local_mode_workflow_and_scripts()
    print("SELF-TEST OK")


if __name__ == "__main__":
    main()

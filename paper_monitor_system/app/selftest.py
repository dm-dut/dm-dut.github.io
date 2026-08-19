from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

import requests
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from .config import REPO_ROOT
from .db import Article, Base, source_priority, upsert_article
from .journals import JournalSpec
from .providers import crossref, springer
from .providers.base import ArticleRecord


def _sample_record(provider: str, publisher: str, journal: str, doi: str, source: str) -> ArticleRecord:
    return ArticleRecord(
        provider=provider,
        publisher=publisher,
        title=f"Sample {doi}",
        journal=journal,
        authors="A. Author",
        doi=doi,
        issn="0254-5330",
        content_type="Journal Article",
        url=f"https://doi.org/{doi}",
        online_date=date(2026, 8, 19),
        online_date_raw="2026-08-19",
        date_precision="day",
        online_date_source=source,
        source_update_date=date(2026, 8, 19),
    )


def test_springer_query_and_pagination() -> None:
    spec = JournalSpec(
        provider="springer",
        publisher="Springer Nature",
        journal="Annals of Operations Research",
        issns=("02545330", "15729338"),
    )
    queries = springer._queries(spec, date(2026, 8, 12), date(2026, 8, 19))
    assert queries[0].startswith(
        "onlinedatefrom:2026-08-12 AND onlinedateto:2026-08-19 AND issn:"
    )
    assert "1572-9338" in queries[0], "eISSN should be tried first"
    assert "type:Journal" not in " ".join(queries)

    captured: list[dict] = []
    original = springer.get_json

    def fake_get_json(session, url, *, params=None, headers=None):
        captured.append(dict(params or {}))
        return {"result": [{"total": "0"}], "records": []}

    springer.get_json = fake_get_json
    try:
        result = springer._fetch_query(None, queries[0], spec, date(2026, 8, 12), date(2026, 8, 19))
    finally:
        springer.get_json = original
    assert result == []
    assert captured and captured[0]["p"] == 20
    assert captured[0]["q"] == queries[0]


def test_crossref_global_works_filter() -> None:
    captured: list[tuple[str, dict]] = []
    original = crossref.get_json

    def fake_get_json(session, url, *, params=None, headers=None):
        captured.append((url, dict(params or {})))
        return {"message": {"items": [], "next-cursor": None}}

    crossref.get_json = fake_get_json
    try:
        rows = crossref._request_items(
            None,
            "1872-9681",
            [
                "type:journal-article",
                "from-online-pub-date:2026-08-16",
                "until-online-pub-date:2026-08-19",
            ],
        )
    finally:
        crossref.get_json = original

    assert rows == []
    assert captured
    url, params = captured[0]
    assert url == "https://api.crossref.org/works"
    assert "issn:1872-9681" in params["filter"]
    assert "from-online-pub-date:2026-08-16" in params["filter"]
    assert "/journals/" not in url


def test_crossref_one_issn_failure_does_not_abort() -> None:
    spec = JournalSpec(
        provider="sciencedirect",
        publisher="Elsevier",
        journal="Applied Soft Computing",
        issns=("15684946", "18729681"),
    )
    original = crossref._records_for_issn
    calls: list[str] = []

    def fake_records(session, provider, publisher, spec_arg, issn, start, end):
        calls.append(issn)
        if len(calls) == 1:
            response = requests.Response()
            response.status_code = 404
            exc = requests.HTTPError("not found", response=response)
            raise exc
        return [_sample_record("sciencedirect", "Elsevier", spec_arg.journal, "10.1000/crossref-test", "Crossref published-online fallback")]

    crossref._records_for_issn = fake_records
    try:
        rows = list(crossref.fetch("sciencedirect", "Elsevier", date(2026, 8, 16), date(2026, 8, 19), [spec]))
    finally:
        crossref._records_for_issn = original

    assert len(rows) == 1
    assert len(calls) == 2, "alternate ISSN should be tried after a request failure"


def test_springer_per_journal_fallback_isolation() -> None:
    failing = JournalSpec(
        provider="springer",
        publisher="Springer Nature",
        journal="Annals of Operations Research",
        issns=("02545330", "15729338"),
    )
    working = JournalSpec(
        provider="springer",
        publisher="Springer Nature",
        journal="Group Decision and Negotiation",
        issns=("09262644", "15729907"),
    )

    original_key = springer.SPRINGER_API_KEY
    original_fetch_query = springer._fetch_query
    original_fallback = springer.crossref.fetch
    springer.SPRINGER_API_KEY = "self-test-key"

    def fake_fetch_query(session, query, spec, start, end):
        if spec.journal == failing.journal:
            response = requests.Response()
            response.status_code = 404
            raise requests.HTTPError("not found", response=response)
        return [_sample_record("springer", "Springer Nature", spec.journal, "10.1000/primary", "Springer Meta API onlineDate")]

    def fake_fallback(provider, publisher, start, end, journals):
        assert [j.journal for j in journals] == [failing.journal]
        yield _sample_record("springer", "Springer Nature", failing.journal, "10.1000/fallback", "Crossref published-online fallback")

    springer._fetch_query = fake_fetch_query
    springer.crossref.fetch = fake_fallback
    try:
        rows = list(springer.fetch(date(2026, 8, 16), date(2026, 8, 19), [failing, working]))
    finally:
        springer.SPRINGER_API_KEY = original_key
        springer._fetch_query = original_fetch_query
        springer.crossref.fetch = original_fallback

    dois = {row.doi for row in rows}
    assert dois == {"10.1000/primary", "10.1000/fallback"}


def test_authoritative_date_protection_and_doi_upsert() -> None:
    sample = {"published-online": {"date-parts": [[2026, 8, 19]]}}
    d, precision, raw = crossref._date_parts(sample)
    assert d == date(2026, 8, 19) and precision == "day" and raw == "2026-08-19"

    assert source_priority("Springer Meta API onlineDate") > source_priority("Crossref published-online fallback")
    assert source_priority("ScienceDirect API Load-Date") > source_priority("Crossref published-online fallback")
    assert source_priority("IEEE Xplore API publication_date") > source_priority("Crossref published-online fallback")

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
        assert session.scalar(select(Article).where(Article.doi == "10.1000/test")).id == row.id


def test_workflow_has_no_binary_rebase() -> None:
    workflow = REPO_ROOT / ".github" / "workflows" / "update-paper-monitor.yml"
    text = workflow.read_text(encoding="utf-8")
    assert "git pull --rebase" not in text
    assert "git reset --hard" in text
    assert "concurrency:" in text
    assert "paper_monitor_system/data/papers.db" in text
    assert "paper-monitor/data/online_papers.json" in text


def main() -> None:
    test_springer_query_and_pagination()
    test_crossref_global_works_filter()
    test_crossref_one_issn_failure_does_not_abort()
    test_springer_per_journal_fallback_isolation()
    test_authoritative_date_protection_and_doi_upsert()
    test_workflow_has_no_binary_rebase()
    print("SELF-TEST OK")


if __name__ == "__main__":
    main()

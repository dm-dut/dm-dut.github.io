from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from .config import BUILD_ID, REPO_ROOT
from .db import Article, Base, upsert_article
from .journals import enabled_journals
from .providers import ieee, sciencedirect, springer
from .utils import identity_key, parse_month_year, parse_publisher_day


class FakeSearchPage:
    def __init__(self, rows): self.rows = rows
    def eval_on_selector_all(self, selector, script): return list(self.rows)


def record_dict(provider="ieee", external_id="123"):
    return {
        "identity_key": identity_key(provider, None, external_id, "Test Paper"),
        "provider": provider,
        "publisher": "IEEE" if provider == "ieee" else "Elsevier",
        "journal": "IEEE Transactions on Cybernetics" if provider == "ieee" else "Applied Soft Computing",
        "title": "Test Paper", "authors": "Alice; Bob", "external_id": external_id,
        "url": "https://example.org", "display_date": "", "sort_date": None,
        "date_kind": "", "date_precision": "", "date_source": "", "source_rank": 1,
        "doi": None, "issn": "",
    }


def test_sciencedirect_list_parser():
    page = FakeSearchPage([
        {"href":"https://www.sciencedirect.com/science/article/pii/S1568494626012345", "title":"Paper A", "authors":"Alice; Bob", "card_text":"Available online 19 August 2026"},
        {"href":"https://www.sciencedirect.com/science/article/pii/S1568494626012346", "title":"Paper B", "authors":"Carol", "card_text":"Volume 203, January 2027, 116999"},
    ])
    rows = sciencedirect._search_candidates(page)
    assert len(rows) == 2
    assert rows[0]["external_id"] == "S1568494626012345"
    assert rows[0]["sort_date"] == date(2026,8,19) and rows[0]["date_kind"] == "online"
    assert rows[1]["display_date"] == "January 2027" and rows[1]["sort_date"] is None


def test_ieee_list_parser_no_date():
    page = FakeSearchPage([
        {"href":"https://ieeexplore.ieee.org/document/12345678/", "title":"IEEE Paper", "authors":"A Author; B Author"},
        {"href":"https://ieeexplore.ieee.org/document/12345678/", "title":"IEEE Paper", "authors":"A Author; B Author"},
    ])
    rows = ieee._search_candidates(page)
    assert len(rows) == 1 and rows[0]["external_id"] == "12345678"
    assert "date" not in rows[0]


def test_date_helpers():
    assert parse_publisher_day("19 August 2026") == date(2026,8,19)
    assert parse_publisher_day("January 2027") is None
    assert parse_month_year("Volume 203, January 2027") == ("2027-01", "January 2027")


def test_springer_online_date():
    spec = enabled_journals("springer")[0]
    row = {
        "publicationType":"Journal", "publicationName":spec.journal,
        "onlineDate":"2026-08-19", "publicationDate":"2027-01-01",
        "title":"Springer paper", "identifier":"doi:10.1007/test",
        "creators":[{"creator":"Alice"}], "issn":spec.issns[0] if spec.issns else "",
    }
    rec = springer._record_from_row(spec, row, date(2026,8,19), 3)
    assert rec and rec.sort_date == date(2026,8,19) and rec.display_date == "2026-08-19"


def test_db_accepts_date_less_ieee_and_preserves_fetched_date():
    eng = create_engine("sqlite:///:memory:", future=True); Base.metadata.create_all(eng)
    with Session(eng) as session:
        row, created = upsert_article(session, record_dict()); session.commit()
        assert created and row.sort_date is None and row.fetched_date == date.today()
        original = row.fetched_date
        changed = record_dict(); changed["title"] = "Test Paper Updated"; changed["source_rank"] = 2
        _, created2 = upsert_article(session, changed); session.commit()
        assert not created2
        saved = session.scalar(select(Article).where(Article.external_id == "123"))
        assert saved and saved.fetched_date == original and saved.title == "Test Paper Updated"


def test_configuration():
    assert BUILD_ID == "LOCAL-2026.08.20-V6-ID-FIRST"
    sd = enabled_journals("sciencedirect"); ieee_specs = enabled_journals("ieee")
    assert len(sd)==39 and len(enabled_journals("springer"))==25 and len(ieee_specs)==15
    assert all("docId=" in x.search_url and "show=50" in x.search_url for x in sd)
    assert all("tocresult.jsp?isnumber=" in x.search_url and "sortType=newest" in x.search_url for x in ieee_specs)
    assert all("PublicationTitle" not in x.search_url for x in ieee_specs)
    assert (REPO_ROOT / "START_HERE.txt").exists()
    interactive=(REPO_ROOT/"update_papers.bat").read_text(encoding="utf-8",errors="ignore").lower()
    scheduled=(REPO_ROOT/"update_papers_scheduled.bat").read_text(encoding="utf-8",errors="ignore").lower()
    assert "pause" in interactive and "pause" not in scheduled
    assert "git pull --rebase" not in (REPO_ROOT/"paper_monitor_system/app/local_update.py").read_text(encoding="utf-8")


def main():
    test_sciencedirect_list_parser(); test_ieee_list_parser_no_date(); test_date_helpers()
    test_springer_online_date(); test_db_accepts_date_less_ieee_and_preserves_fetched_date(); test_configuration()
    print("SELF-TEST OK")


if __name__ == "__main__": main()

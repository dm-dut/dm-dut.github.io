from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date

from ..utils import clean_doi, identity_key, normalize_space


@dataclass
class ArticleRecord:
    provider: str
    publisher: str
    title: str
    journal: str
    authors: str
    external_id: str
    url: str = ""
    display_date: str = ""
    sort_date: date | None = None
    date_kind: str = ""
    date_precision: str = ""
    source_rank: int = 9999
    doi: str | None = None
    issn: str = ""
    date_source: str = ""

    def to_db_dict(self) -> dict:
        self.title = normalize_space(self.title)
        self.journal = normalize_space(self.journal)
        self.authors = normalize_space(self.authors)
        self.external_id = normalize_space(self.external_id)
        self.display_date = normalize_space(self.display_date)
        self.doi = clean_doi(self.doi)
        data = asdict(self)
        data["identity_key"] = identity_key(self.provider, self.doi, self.external_id, self.title)
        return data

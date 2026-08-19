from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date

from ..utils import clean_doi, identity_key, normalize_space


@dataclass
class ArticleRecord:
    provider: str
    publisher: str
    title: str
    journal: str = ""
    authors: str = ""
    doi: str | None = None
    external_id: str | None = None
    issn: str = ""
    content_type: str = "Article"
    url: str = ""
    online_date: date | None = None
    online_date_raw: str = ""
    date_precision: str = "unknown"
    online_date_source: str = ""
    source_update_date: date | None = None

    def to_db_dict(self) -> dict:
        self.title = normalize_space(self.title)
        self.journal = normalize_space(self.journal)
        self.authors = normalize_space(self.authors)
        self.doi = clean_doi(self.doi)
        data = asdict(self)
        data["identity_key"] = identity_key(self.provider, self.doi, self.external_id, self.title)
        return data

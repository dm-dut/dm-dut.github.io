from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import Date, DateTime, Integer, String, Text, UniqueConstraint, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .config import DATABASE_URL, ROOT


class Base(DeclarativeBase):
    pass


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (UniqueConstraint("identity_key", name="uq_articles_identity_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    identity_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    publisher: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    journal: Mapped[str] = mapped_column(Text, default="")
    authors: Mapped[str] = mapped_column(Text, default="")
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    issn: Mapped[str] = mapped_column(String(80), default="")
    content_type: Mapped[str] = mapped_column(String(80), default="")
    url: Mapped[str] = mapped_column(Text, default="")

    # Normalized sortable date plus raw source date.
    online_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    online_date_raw: Mapped[str] = mapped_column(String(120), default="")
    date_precision: Mapped[str] = mapped_column(String(20), default="unknown")
    online_date_source: Mapped[str] = mapped_column(String(80), default="")

    # Date used to discover the record in a delta query (load/insert/query window).
    source_update_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)

    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SyncState(Base):
    __tablename__ = "sync_state"

    provider: Mapped[str] = mapped_column(String(40), primary_key=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_window_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str] = mapped_column(Text, default="")


def _normalized_db_url() -> str:
    if DATABASE_URL.startswith("sqlite:///data/"):
        db_path = ROOT / DATABASE_URL.removeprefix("sqlite:///")
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_path}"
    return DATABASE_URL


engine = create_engine(_normalized_db_url(), future=True)


def init_db() -> None:
    Base.metadata.create_all(engine)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_sync_state(session: Session, provider: str) -> SyncState | None:
    return session.get(SyncState, provider)


def save_sync_success(session: Session, provider: str, window_end: date, count: int) -> None:
    state = session.get(SyncState, provider)
    if state is None:
        state = SyncState(provider=provider)
        session.add(state)
    state.last_success_at = utcnow()
    state.last_window_end = window_end
    state.last_count = count
    state.last_error = ""


def save_sync_error(session: Session, provider: str, error: str) -> None:
    state = session.get(SyncState, provider)
    if state is None:
        state = SyncState(provider=provider)
        session.add(state)
    state.last_error = error[:4000]


def upsert_article(session: Session, record: dict) -> tuple[Article, bool]:
    """Insert or update one article without duplicating repeat/manual/scheduled fetches.

    The normal identity key is DOI-first, then provider external ID, then title.
    The extra DOI/external-ID lookups below make the upsert resilient when a
    publisher first exposes an item without a DOI and supplies the DOI later.
    """
    existing = session.scalar(select(Article).where(Article.identity_key == record["identity_key"]))

    doi = record.get("doi")
    if existing is None and doi:
        existing = session.scalar(select(Article).where(Article.doi == doi))

    external_id = record.get("external_id")
    if existing is None and external_id:
        existing = session.scalar(
            select(Article).where(
                Article.provider == record["provider"],
                Article.external_id == external_id,
            )
        )

    # Last-resort fallback only when the source supplies neither DOI nor ID.
    if existing is None and not doi and not external_id and record.get("title"):
        existing = session.scalar(
            select(Article).where(
                Article.provider == record["provider"],
                Article.title == record["title"],
            )
        )

    now = utcnow()
    created = existing is None
    if existing is None:
        existing = Article(
            identity_key=record["identity_key"],
            provider=record["provider"],
            publisher=record["publisher"],
            title=record["title"],
            first_seen_at=now,
            last_seen_at=now,
        )
        session.add(existing)
    elif existing.identity_key != record["identity_key"]:
        # Promote an external-ID/title identity to DOI identity when DOI arrives.
        collision = session.scalar(
            select(Article).where(
                Article.identity_key == record["identity_key"],
                Article.id != existing.id,
            )
        )
        if collision is None:
            existing.identity_key = record["identity_key"]

    for field in (
        "provider", "publisher", "title", "journal", "authors", "doi", "external_id",
        "issn", "content_type", "url", "online_date", "online_date_raw",
        "date_precision", "online_date_source", "source_update_date",
    ):
        value = record.get(field)
        if value not in (None, "") or field in {"online_date", "source_update_date"}:
            setattr(existing, field, value)
    existing.last_seen_at = now
    return existing, created

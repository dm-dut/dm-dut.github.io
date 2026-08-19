from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import Date, DateTime, Integer, String, Text, UniqueConstraint, create_engine, inspect, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .config import DATABASE_URL


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
    online_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    online_date_raw: Mapped[str] = mapped_column(String(120), default="")
    date_precision: Mapped[str] = mapped_column(String(20), default="unknown")
    online_date_source: Mapped[str] = mapped_column(String(120), default="")
    source_update_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="published", server_default="published", nullable=False, index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SyncState(Base):
    __tablename__ = "sync_state"
    provider: Mapped[str] = mapped_column(String(40), primary_key=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_window_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str] = mapped_column(Text, default="")


def _prepare_sqlite_dir(url: str) -> None:
    if not url.startswith("sqlite:///"):
        return
    raw = url.removeprefix("sqlite:///")
    if raw == ":memory:":
        return
    Path(raw).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


_prepare_sqlite_dir(DATABASE_URL)
engine = create_engine(DATABASE_URL, future=True)


def _migrate_sqlite() -> None:
    """Add monitor columns to an existing SQLite database without replacing it."""
    if engine.dialect.name != "sqlite":
        return
    inspector = inspect(engine)
    if "articles" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("articles")}
    with engine.begin() as conn:
        if "status" not in columns:
            conn.execute(text("ALTER TABLE articles ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'published'"))
        if "last_checked_at" not in columns:
            conn.execute(text("ALTER TABLE articles ADD COLUMN last_checked_at DATETIME"))
        conn.execute(text("UPDATE articles SET status='published' WHERE online_date IS NOT NULL AND (status IS NULL OR status='')"))
        conn.execute(text("UPDATE articles SET status='pending' WHERE online_date IS NULL AND (status IS NULL OR status='')"))


def init_db() -> None:
    Base.metadata.create_all(engine)
    _migrate_sqlite()


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


def source_priority(source: str | None) -> int:
    text_value = (source or "").lower()
    if "springer meta api" in text_value:
        return 60
    if "available online" in text_value or "publisher page" in text_value or "ieee page publication date" in text_value:
        return 55
    if "crossref" in text_value and "published-online" in text_value:
        return 50
    if "sciencedirect api" in text_value or "ieee xplore api" in text_value:
        return 40
    if "saved search rss" in text_value and "pubdate fallback" in text_value:
        return 35
    if "saved search rss" in text_value and "crossref" not in text_value:
        return 35
    if "sciencedirect rss" in text_value and "crossref" not in text_value:
        return 35
    if "crossref" in text_value or "fallback" in text_value:
        return 20
    return 20 if text_value else 0


def upsert_article(session: Session, record: dict) -> tuple[Article, bool]:
    """DOI-first upsert. Pending records may later be promoted to published."""
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

    if existing is None and not doi and not external_id and record.get("title"):
        existing = session.scalar(
            select(Article).where(
                Article.provider == record["provider"],
                Article.title == record["title"],
            )
        )

    now = utcnow()
    created = existing is None
    incoming_has_date = record.get("online_date") is not None
    incoming_status = "published" if incoming_has_date else "pending"

    if existing is None:
        existing = Article(
            identity_key=record["identity_key"],
            provider=record["provider"],
            publisher=record["publisher"],
            title=record["title"],
            status=incoming_status,
            first_seen_at=now,
            last_seen_at=now,
            last_checked_at=now,
        )
        session.add(existing)
    elif existing.identity_key != record["identity_key"]:
        collision = session.scalar(
            select(Article).where(
                Article.identity_key == record["identity_key"],
                Article.id != existing.id,
            )
        )
        if collision is None:
            existing.identity_key = record["identity_key"]

    incoming_priority = source_priority(record.get("online_date_source"))
    existing_priority = source_priority(existing.online_date_source) if not created else 0
    protect_authoritative_date = (
        not created
        and existing.online_date is not None
        and (not incoming_has_date or existing_priority > incoming_priority)
    )
    date_fields = {"online_date", "online_date_raw", "date_precision", "online_date_source", "source_update_date"}

    for field in (
        "provider", "publisher", "title", "journal", "authors", "doi", "external_id",
        "issn", "content_type", "url", "online_date", "online_date_raw",
        "date_precision", "online_date_source", "source_update_date",
    ):
        if protect_authoritative_date and field in date_fields:
            continue
        value = record.get(field)
        # A pending recheck must not blank fields already known on a published row.
        if value not in (None, ""):
            setattr(existing, field, value)
        elif created and field in {"online_date", "source_update_date"}:
            setattr(existing, field, value)

    # Status quality is monotone: an incoming pending observation must NEVER
    # demote a row that is already published.  Likewise a missing/lower-quality
    # date cannot erase a previously known date.
    if existing.online_date is not None or (not created and existing.status == "published"):
        existing.status = "published"
    else:
        existing.status = "pending"

    existing.last_seen_at = now
    existing.last_checked_at = now
    return existing, created

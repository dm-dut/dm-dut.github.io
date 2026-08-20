from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Integer, String, Text, UniqueConstraint, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .config import DATABASE_URL, DB_PATH, SCHEMA_VERSION, WEB_JSON_PATH


class Base(DeclarativeBase):
    pass


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (UniqueConstraint("identity_key", name="uq_articles_identity_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    identity_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    publisher: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    journal: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    authors: Mapped[str] = mapped_column(Text, default="")

    fetched_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    display_date: Mapped[str] = mapped_column(String(80), default="")
    sort_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    date_kind: Mapped[str] = mapped_column(String(40), default="")
    date_precision: Mapped[str] = mapped_column(String(20), default="")
    date_source: Mapped[str] = mapped_column(String(120), default="")

    external_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_rank: Mapped[int] = mapped_column(Integer, default=9999)
    url: Mapped[str] = mapped_column(Text, default="")
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    issn: Mapped[str] = mapped_column(String(80), default="")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SyncState(Base):
    __tablename__ = "sync_state"
    provider: Mapped[str] = mapped_column(String(40), primary_key=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_window_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str] = mapped_column(Text, default="")


class SchemaMeta(Base):
    __tablename__ = "schema_meta"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _prepare_dir() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    WEB_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)


def _existing_schema_version() -> str | None:
    if not DB_PATH.exists() or DB_PATH.stat().st_size == 0:
        return None
    try:
        with sqlite3.connect(DB_PATH) as conn:
            if not conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_meta'").fetchone():
                return None
            row = conn.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()
            return str(row[0]) if row else None
    except Exception:
        return None


def reset_legacy_database_if_needed() -> bool:
    _prepare_dir()
    if not DB_PATH.exists():
        return False
    version = _existing_schema_version()
    if version == SCHEMA_VERSION:
        return False
    try:
        DB_PATH.unlink()
    except FileNotFoundError:
        pass
    try:
        WEB_JSON_PATH.unlink()
    except FileNotFoundError:
        pass
    print(f"[database] removed pre-V6 database/json (schema={version or 'legacy/unknown'})")
    return True


reset_legacy_database_if_needed()
engine = create_engine(DATABASE_URL, future=True)


def init_db() -> None:
    _prepare_dir()
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        meta = session.get(SchemaMeta, "schema_version")
        if meta is None:
            session.add(SchemaMeta(key="schema_version", value=SCHEMA_VERSION))
        else:
            meta.value = SCHEMA_VERSION
        session.commit()


def get_sync_state(session: Session, provider: str) -> SyncState | None:
    return session.get(SyncState, provider)


def save_sync_success(session: Session, provider: str, window_end: date, count: int) -> None:
    state = session.get(SyncState, provider)
    if state is None:
        state = SyncState(provider=provider); session.add(state)
    state.last_success_at = utcnow(); state.last_window_end = window_end; state.last_count = count; state.last_error = ""


def save_sync_error(session: Session, provider: str, error: str) -> None:
    state = session.get(SyncState, provider)
    if state is None:
        state = SyncState(provider=provider); session.add(state)
    state.last_error = error[:4000]


def known_external_ids(session: Session, provider: str) -> set[str]:
    return set(session.scalars(select(Article.external_id).where(Article.provider == provider)).all())


def upsert_article(session: Session, record: dict) -> tuple[Article, bool]:
    existing = session.scalar(select(Article).where(Article.identity_key == record["identity_key"]))
    if existing is None and record.get("external_id"):
        existing = session.scalar(select(Article).where(
            Article.provider == record["provider"], Article.external_id == record["external_id"]
        ))
    if existing is None and record.get("doi"):
        existing = session.scalar(select(Article).where(Article.doi == record["doi"]))

    now = utcnow(); created = existing is None
    if existing is None:
        existing = Article(
            identity_key=record["identity_key"], provider=record["provider"], publisher=record["publisher"],
            journal=record["journal"], title=record["title"], authors=record.get("authors") or "",
            fetched_date=date.today(), display_date=record.get("display_date") or "", sort_date=record.get("sort_date"),
            date_kind=record.get("date_kind") or "", date_precision=record.get("date_precision") or "",
            date_source=record.get("date_source") or "", external_id=record["external_id"],
            source_rank=int(record.get("source_rank") or 9999), url=record.get("url") or "",
            doi=record.get("doi"), issn=record.get("issn") or "", first_seen_at=now, last_seen_at=now,
        )
        session.add(existing)
    else:
        # fetched_date never changes after first insertion.
        for field in ("publisher", "journal", "title", "authors", "url", "doi", "issn", "display_date",
                      "date_kind", "date_precision", "date_source"):
            value = record.get(field)
            if value not in (None, ""):
                setattr(existing, field, value)
        if record.get("sort_date") is not None:
            existing.sort_date = record["sort_date"]
        if record.get("source_rank") not in (None, ""):
            existing.source_rank = int(record["source_rank"])
        existing.last_seen_at = now
    return existing, created

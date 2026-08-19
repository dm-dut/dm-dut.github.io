from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import Date, DateTime, Integer, String, Text, UniqueConstraint, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .config import DATABASE_URL, DB_PATH, RESET_FLAG_PATH, WEB_JSON_PATH


class Base(DeclarativeBase):
    pass


class Article(Base):
    __tablename__ = 'articles'
    __table_args__ = (UniqueConstraint('identity_key', name='uq_articles_identity_key'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    identity_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    publisher: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    journal: Mapped[str] = mapped_column(Text, nullable=False, default='')
    authors: Mapped[str] = mapped_column(Text, nullable=False, default='')
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True, index=True)
    issn: Mapped[str] = mapped_column(String(120), nullable=False, default='')
    content_type: Mapped[str] = mapped_column(String(80), nullable=False, default='journal-article')
    url: Mapped[str] = mapped_column(Text, nullable=False, default='')
    online_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    date_source: Mapped[str] = mapped_column(String(80), nullable=False, default='Crossref')
    discovered_via: Mapped[str] = mapped_column(String(80), nullable=False, default='Crossref')
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SyncState(Base):
    __tablename__ = 'sync_state'
    provider: Mapped[str] = mapped_column(String(40), primary_key=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_window_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_count: Mapped[int] = mapped_column(Integer, default=0)


Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
engine = create_engine(DATABASE_URL, future=True)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def reset_database_if_requested() -> bool:
    """V4 intentionally starts with a fresh database once, per user request."""
    if not RESET_FLAG_PATH.exists():
        return False
    engine.dispose()
    if DB_PATH.exists():
        DB_PATH.unlink()
    if WEB_JSON_PATH.exists():
        WEB_JSON_PATH.unlink()
    RESET_FLAG_PATH.unlink(missing_ok=True)
    print('[database] V4 reset completed: previous papers.db and online_papers.json removed')
    return True


def init_db() -> None:
    Base.metadata.create_all(engine)


def save_sync_success(session: Session, provider: str, window_end: date, count: int) -> None:
    state = session.get(SyncState, provider)
    if state is None:
        state = SyncState(provider=provider)
        session.add(state)
    state.last_success_at = utcnow()
    state.last_window_end = window_end
    state.last_count = count


def upsert_article(session: Session, record: dict) -> tuple[Article, bool]:
    existing = None
    if record.get('doi'):
        existing = session.scalar(select(Article).where(Article.doi == record['doi']))
    if existing is None:
        existing = session.scalar(select(Article).where(Article.identity_key == record['identity_key']))
    now = utcnow()
    created = existing is None
    if existing is None:
        existing = Article(
            identity_key=record['identity_key'],
            provider=record['provider'],
            publisher=record['publisher'],
            title=record['title'],
            journal=record['journal'],
            authors=record.get('authors', ''),
            doi=record.get('doi') or None,
            issn=record.get('issn', ''),
            content_type=record.get('content_type', 'journal-article'),
            url=record.get('url', ''),
            online_date=record['online_date'],
            date_source=record.get('date_source', 'Crossref'),
            discovered_via=record.get('discovered_via', 'Crossref'),
            first_seen_at=now,
            last_seen_at=now,
        )
        session.add(existing)
        return existing, True

    # Never blank known values. Prefer explicit published-online over generic dates.
    for field in ('provider','publisher','title','journal','authors','doi','issn','content_type','url','discovered_via'):
        value = record.get(field)
        if value not in (None, ''):
            setattr(existing, field, value)
    incoming_source = record.get('date_source', '')
    priority = {'Crossref published-online': 3, 'Crossref published': 2, 'Crossref issued': 1, 'Crossref published-print': 1}
    if priority.get(incoming_source, 0) >= priority.get(existing.date_source, 0):
        existing.online_date = record['online_date']
        existing.date_source = incoming_source or existing.date_source
    existing.last_seen_at = now
    return existing, False

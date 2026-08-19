from __future__ import annotations

import argparse
from datetime import date, timedelta
from time import perf_counter

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .config import (
    BUILD_ID,
    CROSSREF_DISCOVERY_DAYS,
    CROSSREF_MAILTO,
    ENABLE_IEEE,
    ENABLE_SCIENCEDIRECT,
    ENABLE_SCIENCEDIRECT_API,
    ENABLE_SCIENCEDIRECT_PAGE,
    ENABLE_SCIENCEDIRECT_RSS,
    ENABLE_SPRINGER,
    ENABLE_SPRINGER_API,
    ENABLE_SPRINGER_BATCH_API,
    OVERLAP_DAYS,
    PENDING_RECHECK_DAYS,
    PENDING_RECHECK_LIMIT,
    PENDING_RECHECK_MIN_HOURS,
)
from .db import Article, engine, get_sync_state, init_db, save_sync_error, save_sync_success, upsert_article, utcnow
from .export_json import export_json
from .journals import enabled_journals, match_journal
from .providers import crossref, ieee, sciencedirect, springer

PROVIDERS = {
    "sciencedirect": (ENABLE_SCIENCEDIRECT, sciencedirect.fetch),
    "springer": (ENABLE_SPRINGER, springer.fetch),
    "ieee": (ENABLE_IEEE, ieee.fetch),
}


def default_window(session: Session, provider: str, initial_days: int) -> tuple[date, date]:
    today = date.today()
    state = get_sync_state(session, provider)
    if state and state.last_window_end:
        start = state.last_window_end - timedelta(days=max(0, OVERLAP_DAYS))
    else:
        start = today - timedelta(days=max(0, initial_days))
    # LOCAL V3 intentionally caps routine discovery at the configured two-day
    # window even if the computer was offline longer.
    cap = today - timedelta(days=max(1, CROSSREF_DISCOVERY_DAYS) - 1)
    return max(start, cap), today


def sync_provider(provider: str, fetcher, journals, start: date, end: date) -> tuple[int, int, int, int]:
    if start > end:
        raise ValueError(f"start date {start} is after end date {end}")
    total = created = published = pending = 0
    with Session(engine) as session:
        try:
            for record in fetcher(start, end, journals):
                total += 1
                published += int(record.online_date is not None)
                pending += int(record.online_date is None)
                _, was_created = upsert_article(session, record.to_db_dict())
                created += int(was_created)
                if total % 250 == 0:
                    session.commit()
            save_sync_success(session, provider, end, total)
            session.commit()
        except Exception as exc:
            try:
                session.commit()
            except Exception:
                session.rollback()
            save_sync_error(session, provider, repr(exc))
            session.commit()
            raise
    return total, created, published, pending


def recheck_pending(limit: int | None = None) -> tuple[int, int, int]:
    """Recheck pending DOIs at most about once per day, not immediately after discovery."""
    now = utcnow()
    recent_cutoff = now - timedelta(days=max(PENDING_RECHECK_DAYS, 1))
    recheck_before = now - timedelta(hours=max(PENDING_RECHECK_MIN_HOURS, 1))
    limit = PENDING_RECHECK_LIMIT if limit is None else limit
    checked = promoted = failed = 0
    with Session(engine) as session:
        stmt = (
            select(Article)
            .where(
                Article.status == "pending",
                Article.doi.is_not(None),
                Article.first_seen_at >= recent_cutoff,
                or_(Article.last_checked_at.is_(None), Article.last_checked_at <= recheck_before),
            )
            .order_by(Article.last_checked_at.asc().nullsfirst(), Article.first_seen_at.asc())
            .limit(max(1, limit))
        )
        rows = list(session.scalars(stmt))
        if rows:
            print(f"[pending] eligible={len(rows)} (min_age_since_check={PENDING_RECHECK_MIN_HOURS}h, limit={limit})")
        for article in rows:
            spec = match_journal(article.provider, article.journal, article.issn)
            if spec is None or not article.doi:
                continue
            checked += 1
            try:
                record = crossref.by_doi(article.provider, article.publisher, spec, article.doi, today=date.today())
                if record is None:
                    article.last_checked_at = utcnow()
                    continue
                upsert_article(session, record.to_db_dict())
                if record.online_date is not None:
                    promoted += 1
            except Exception as exc:
                failed += 1
                if failed <= 5:
                    print(f"[pending] recheck warning: {article.doi}: {type(exc).__name__}")
            if checked % 50 == 0:
                print(f"[pending] progress={checked}/{len(rows)}, promoted={promoted}, failed={failed}")
                session.commit()
        session.commit()
    return checked, promoted, failed


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch recent online papers from the journal whitelist")
    parser.add_argument("--provider", choices=["all", *PROVIDERS.keys()], default="all")
    parser.add_argument("--start", help="YYYY-MM-DD; overrides sync state")
    parser.add_argument("--end", help="YYYY-MM-DD; default today")
    parser.add_argument("--initial-days", type=int, default=1, help="first-run lookback; 1 means yesterday..today")
    parser.add_argument("--skip-pending-recheck", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    run_t0 = perf_counter()
    print(f"Paper Monitor Build: {BUILD_ID}")
    print("Execution mode: LOCAL_PC")
    print(
        f"Elsevier: Crossref member dual batch (online-date + update-date, max {CROSSREF_DISCOVERY_DAYS} days) + direct RSS(optional); "
        f"ScienceDirect API={'ON' if ENABLE_SCIENCEDIRECT_API else 'OFF'}, page={'ON' if ENABLE_SCIENCEDIRECT_PAGE else 'OFF'}, RSS={'ON' if ENABLE_SCIENCEDIRECT_RSS else 'OFF'}"
    )
    print(
        f"Springer: batch Meta API={'ON' if (ENABLE_SPRINGER_API and ENABLE_SPRINGER_BATCH_API) else 'OFF'} "
        "-> Crossref prefix batch fallback (no per-journal Springer API loop)"
    )
    print("IEEE: Combined Saved Search RSS primary -> Crossref/page enrichment -> RSS pubDate fallback when needed")
    print(f"Crossref polite-pool mailto: {'configured' if CROSSREF_MAILTO else 'NOT configured (recommended)'}")

    init_db()
    selected = PROVIDERS.items() if args.provider == "all" else [(args.provider, PROVIDERS[args.provider])]
    errors: list[tuple[str, Exception]] = []

    for provider, (enabled, fetcher) in selected:
        if not enabled:
            print(f"[{provider}] disabled")
            continue
        journals = enabled_journals(provider)
        if not journals:
            print(f"[{provider}] skipped: no Enabled=1 journals")
            continue
        with Session(engine) as session:
            start, end = default_window(session, provider, args.initial_days)
        if args.start:
            start = date.fromisoformat(args.start)
        if args.end:
            end = date.fromisoformat(args.end)

        print(f"[{provider}] journals={len(journals)}")
        print(f"[{provider}] window={start}..{end}")
        t0 = perf_counter()
        try:
            total, created, published, pending = sync_provider(provider, fetcher, journals, start, end)
            print(
                f"[{provider}] fetched={total}, new={created}, updated={total-created}, "
                f"published={published}, pending={pending}, elapsed={perf_counter()-t0:.1f}s"
            )
        except Exception as exc:
            errors.append((provider, exc))
            print(f"[{provider}] ERROR after fallback: {type(exc).__name__}: {exc}; elapsed={perf_counter()-t0:.1f}s")

    if not args.skip_pending_recheck:
        t0 = perf_counter()
        checked, promoted, failed = recheck_pending()
        print(f"[pending] checked={checked}, promoted={promoted}, failed={failed}, elapsed={perf_counter()-t0:.1f}s")

    exported = export_json()
    print(f"[export] {exported} whitelisted published records exported")
    print(f"[total] elapsed={perf_counter()-run_t0:.1f}s")

    if errors:
        print("WARNING: Provider failures: " + ", ".join(name for name, _ in errors))
        if args.strict:
            raise SystemExit(2)


if __name__ == "__main__":
    main()

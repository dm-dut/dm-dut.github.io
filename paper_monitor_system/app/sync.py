from __future__ import annotations

import argparse
from datetime import date, timedelta

from sqlalchemy.orm import Session

from .config import ENABLE_IEEE, ENABLE_SCIENCEDIRECT, ENABLE_SPRINGER, OVERLAP_DAYS, WEB_JSON_PATH
from .db import engine, get_sync_state, init_db, save_sync_error, save_sync_success, upsert_article
from .export_json import export_json
from .journals import describe_journals, enabled_journals
from .providers import ieee, sciencedirect, springer

PROVIDERS = {
    "sciencedirect": (ENABLE_SCIENCEDIRECT, sciencedirect.fetch),
    "springer": (ENABLE_SPRINGER, springer.fetch),
    "ieee": (ENABLE_IEEE, ieee.fetch),
}


def default_window(session: Session, provider: str, initial_days: int) -> tuple[date, date]:
    today = date.today()
    state = get_sync_state(session, provider)
    if state and state.last_window_end:
        start = state.last_window_end - timedelta(days=OVERLAP_DAYS)
    else:
        start = today - timedelta(days=initial_days)
    return start, today


def sync_provider(provider: str, fetcher, journals, start: date, end: date) -> tuple[int, int]:
    if start > end:
        raise ValueError(f"start date {start} is after end date {end}")
    total = created = 0
    with Session(engine) as session:
        try:
            for record in fetcher(start, end, journals):
                total += 1
                _, was_created = upsert_article(session, record.to_db_dict())
                created += int(was_created)
                if total % 250 == 0:
                    session.commit()
            save_sync_success(session, provider, end, total)
            session.commit()
        except Exception as exc:
            session.rollback()
            save_sync_error(session, provider, repr(exc))
            session.commit()
            raise
    return total, created


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch recent online papers from the journal whitelist")
    parser.add_argument("--provider", choices=["all", *PROVIDERS.keys()], default="all")
    parser.add_argument("--start", help="YYYY-MM-DD; overrides sync state")
    parser.add_argument("--end", help="YYYY-MM-DD; default today")
    parser.add_argument("--initial-days", type=int, default=7, help="first-run lookback")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero if a provider and its fallback both fail; default keeps other providers/web feed running",
    )
    args = parser.parse_args()

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
        try:
            total, created = sync_provider(provider, fetcher, journals, start, end)
            print(f"[{provider}] fetched={total}, new={created}, updated={total-created}")
        except Exception as exc:
            errors.append((provider, exc))
            print(f"[{provider}] ERROR after fallback: {type(exc).__name__}: {exc}")

    count = export_json()
    print(f"[export] {count} whitelisted records -> {WEB_JSON_PATH}")

    if errors:
        names = ", ".join(name for name, _ in errors)
        message = f"Provider failures after fallback: {names}. Existing data was preserved and the feed was exported."
        if args.strict:
            raise SystemExit(message)
        print(f"WARNING: {message}")


if __name__ == "__main__":
    main()

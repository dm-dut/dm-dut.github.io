from __future__ import annotations

import argparse
from datetime import date, timedelta
from time import perf_counter

from sqlalchemy.orm import Session

from .config import BUILD_ID, ENABLE_IEEE, ENABLE_SCIENCEDIRECT, ENABLE_SPRINGER, OVERLAP_DAYS
from .db import engine, get_sync_state, init_db, known_external_ids, save_sync_error, save_sync_success, upsert_article
from .export_json import export_json
from .journals import enabled_journals
from .providers import ieee, sciencedirect, springer

PROVIDERS = {
    "sciencedirect": (ENABLE_SCIENCEDIRECT, sciencedirect.fetch),
    "springer": (ENABLE_SPRINGER, springer.fetch),
    "ieee": (ENABLE_IEEE, ieee.fetch),
}


def default_window(session: Session, provider: str, initial_days: int) -> tuple[date, date]:
    today = date.today()
    # Only Springer uses this window. For ID-first browser providers the values are ignored.
    state = get_sync_state(session, provider)
    if state and state.last_window_end:
        start = state.last_window_end - timedelta(days=max(0, OVERLAP_DAYS))
    else:
        start = today - timedelta(days=max(1, initial_days) - 1)
    return start, today


def sync_provider(provider: str, fetcher, journals, start: date, end: date) -> tuple[int, int, int]:
    with Session(engine) as session:
        known = known_external_ids(session, provider)
    total = created = updated = 0
    with Session(engine) as session:
        try:
            for record in fetcher(start, end, journals, known_ids=known):
                total += 1
                _, was_created = upsert_article(session, record.to_db_dict())
                created += int(was_created); updated += int(not was_created)
                if total % 100 == 0:
                    session.commit()
            save_sync_success(session, provider, end, total); session.commit()
        except Exception as exc:
            session.rollback(); save_sync_error(session, provider, repr(exc)); session.commit(); raise
    return total, created, updated


def run(provider_arg: str, initial_days: int) -> None:
    init_db()
    print(f"Paper Monitor Build: {BUILD_ID}")
    print("Discovery policy:")
    print("  Elsevier -> ScienceDirect sorted list + PII; no article-detail request")
    print("  Springer -> Springer Nature Meta API onlineDate")
    print("  IEEE -> simple Xplore Early Access/TOC list + Document ID; no date/article-detail request")
    print("Sorting: fetched_date DESC -> journal ASC -> true online date DESC -> source_rank ASC")

    selected = list(PROVIDERS) if provider_arg == "all" else [provider_arg]
    grand_t0 = perf_counter(); failures: list[str] = []
    for provider in selected:
        enabled, fetcher = PROVIDERS[provider]
        if not enabled:
            print(f"[{provider}] disabled"); continue
        journals = enabled_journals(provider)
        with Session(engine) as session:
            start, end = default_window(session, provider, initial_days)
        print(f"[{provider}] journals={len(journals)}")
        if provider == "springer":
            print(f"[{provider}] onlineDate window={start}..{end}")
        else:
            print(f"[{provider}] mode=ID-first newest-list incremental")
        t0 = perf_counter()
        try:
            total, new, updated = sync_provider(provider, fetcher, journals, start, end)
            print(f"[{provider}] fetched={total}, new={new}, updated={updated}, elapsed={perf_counter()-t0:.1f}s")
        except Exception as exc:
            failures.append(provider); print(f"[{provider}] ERROR: {type(exc).__name__}: {exc}")

    exported = export_json()
    print(f"[export] {exported} records exported")
    print(f"[total] elapsed={perf_counter()-grand_t0:.1f}s")
    if failures:
        raise RuntimeError("Provider failures: " + ", ".join(failures))


def main() -> None:
    parser = argparse.ArgumentParser(description="V6 ID-first paper monitor")
    parser.add_argument("--provider", choices=["all", "sciencedirect", "springer", "ieee"], default="all")
    parser.add_argument("--initial-days", type=int, default=7, help="Springer first-run window only")
    args = parser.parse_args(); run(args.provider, args.initial_days)


if __name__ == "__main__":
    main()

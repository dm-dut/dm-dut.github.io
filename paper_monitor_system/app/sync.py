from __future__ import annotations

import argparse
from datetime import date, timedelta
from time import perf_counter

from sqlalchemy.orm import Session

from .config import BUILD_ID, CROSSREF_DISCOVERY_DAYS, CROSSREF_MAILTO, CROSSREF_MEMBERS
from .db import engine, init_db, reset_database_if_requested, save_sync_success, upsert_article
from .export_json import export_json
from .journals import enabled_journals
from .providers import fetch_provider

PROVIDERS=('sciencedirect','springer','ieee')


def main() -> None:
    parser=argparse.ArgumentParser(description='Crossref-only paper monitor V4')
    parser.add_argument('--provider',choices=['all',*PROVIDERS],default='all')
    parser.add_argument('--start',help='YYYY-MM-DD')
    parser.add_argument('--end',help='YYYY-MM-DD')
    parser.add_argument('--initial-days',type=int,default=2)
    args=parser.parse_args()

    run_t0=perf_counter()
    print(f'Paper Monitor Build: {BUILD_ID}')
    print('Execution mode: LOCAL_PC / CROSSREF_ONLY')
    print(f'Crossref members: Elsevier={CROSSREF_MEMBERS["sciencedirect"]}, Springer={CROSSREF_MEMBERS["springer"]}, IEEE={CROSSREF_MEMBERS["ieee"]}')
    print(f'Crossref polite-pool mailto: {"configured" if CROSSREF_MAILTO else "NOT configured (recommended)"}')
    print('Discovery: per member pub-date batch + index-date batch; local ISSN/title whitelist')

    reset_database_if_requested()
    init_db()
    end=date.fromisoformat(args.end) if args.end else date.today()
    lookback=max(1,min(CROSSREF_DISCOVERY_DAYS,args.initial_days or CROSSREF_DISCOVERY_DAYS))
    start=date.fromisoformat(args.start) if args.start else end-timedelta(days=lookback-1)

    selected=PROVIDERS if args.provider=='all' else (args.provider,)
    total_requests=0
    for provider in selected:
        journals=enabled_journals(provider)
        print(f'[{provider}] journals={len(journals)}')
        t0=perf_counter()
        records,stats=fetch_provider(provider,journals,start,end)
        total_requests += stats['requests']
        created=0
        with Session(engine) as session:
            for rec in records:
                _,is_new=upsert_article(session,rec)
                created += int(is_new)
            save_sync_success(session,provider,end,len(records))
            session.commit()
        print(
            f'[{provider}] member={stats["member"]}, requests={stats["requests"]}, '
            f'pub_raw={stats["pub"]["raw"]}, pub_match={stats["pub"]["matched"]}, '
            f'index_raw={stats["index"]["raw"]}, index_match={stats["index"]["matched"]}, '
            f'unique={stats["unique"]}, new={created}, updated={len(records)-created}, elapsed={perf_counter()-t0:.1f}s'
        )

    exported=export_json()
    print(f'[export] {exported} whitelisted records exported')
    print(f'[total] Crossref requests={total_requests}, elapsed={perf_counter()-run_t0:.1f}s')


if __name__=='__main__':
    main()

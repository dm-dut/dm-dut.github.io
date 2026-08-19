# Paper Monitor — LOCAL_FINAL_V3.2

Build: `LOCAL-2026.08.19-V3.2`

This package runs all publisher collection on the local computer. GitHub Pages remains only the display layer at `https://dm-dut.github.io/paper-monitor/`.

## Data-source strategy

### Elsevier / ScienceDirect

The normal daily path no longer depends on the ScienceDirect API or HTML pages, because local tests returned API 401 and page 403. V3.2 uses two fast Crossref publisher-level passes against Elsevier BV member `78` for the two-day window: one `published-online` pass and one `update-date` pass. Results are then filtered locally against the 39-journal ISSN/title whitelist. No hard DOI-prefix filter is applied. Optional stable direct RSS URLs can still be added in `journal_list.xlsx`. Records discovered through the update pass without a usable online date are stored as `pending` and rechecked later by DOI only.

### Springer Nature

Springer remains batch-first because the local Meta API connectivity test returned HTTP 200. The collector runs one date-window Meta API batch, filters locally against the 25-journal whitelist, and never performs the previous 25-journal retry loop. If the Meta batch is unavailable or reaches the Basic-plan pagination cap, one Crossref `10.1007` prefix batch is used as a supplement/fallback. Springer Meta API `onlineDate` remains the strongest date source.

### IEEE

One combined `IEEETrans15` Saved Search RSS covers all 15 journals. The feed is requested once. Crossref and, only when useful, the IEEE article page enrich journal/DOI/date metadata. V3.2 no longer requires Crossref `published-online` before showing a valid RSS record: when neither Crossref nor the IEEE page has a date, the feed's own `pubDate` can be used as a clearly labelled fallback (`IEEE Saved Search RSS pubDate fallback`). A later Crossref/publisher date has higher priority and can replace that fallback. The 15-journal whitelist still filters Virtual Journals and Compendia.

## First-time setup

Copy/overwrite this package into the local `dm-dut.github.io` repository root. Keep your existing `paper_monitor_system/data/papers.db` and `paper-monitor/data/online_papers.json`. Then run `setup_local.bat`, edit `paper_monitor_system/.env`, and configure at least:

```text
SPRINGER_API_KEY=...
CROSSREF_MAILTO=your-email@example.com
```

Recommended V3.2 settings:

```text
OVERLAP_DAYS=1
CROSSREF_DISCOVERY_DAYS=2
PENDING_RECHECK_DAYS=60
PENDING_RECHECK_MIN_HOURS=20
PENDING_RECHECK_LIMIT=200
HTTP_TIMEOUT=20
HTTP_RETRY_TOTAL=2
REQUEST_PAUSE_SECONDS=0.10
CROSSREF_BATCH_ROWS=1000
CROSSREF_BATCH_MAX_PAGES=30
ELSEVIER_CROSSREF_MEMBER_ID=78
ENABLE_ELSEVIER_EMERGENCY_ISSN_FALLBACK=false
SPRINGER_BATCH_PAGE_SIZE=20
SPRINGER_BATCH_MAX_PAGES=5
```

## Connection test

Run `test_connections.bat`. Required checks are Springer Meta API, IEEE Saved Search RSS, Crossref, Elsevier Crossref online-date batch, and Elsevier Crossref update-date batch. ScienceDirect API is only an optional diagnostic.

## Daily use

Run `update_papers.bat` manually. The interactive window now **always pauses at the end**, whether the update succeeds or fails, so a double-click will not appear to flash and disappear. For Windows Task Scheduler use `update_papers_scheduled.bat`; it never pauses. The updater performs `git pull --ff-only` before touching SQLite, runs self-check/self-test, collects all three publishers, rechecks eligible pending DOIs, exports JSON, commits only `papers.db` and `online_papers.json`, then pushes to the current branch.

Every run writes a log under `paper_monitor_system/logs/update_YYYYMMDD_HHMMSS.log`.

To fetch without Git push, run `fetch_only.bat`. To view locally, run `view_local.bat` and open `http://localhost:8000/paper-monitor/`.

## Expected V3.2 logs

```text
[sciencedirect] Crossref online-date batch: member=78, journals=39, window=...
[sciencedirect] Crossref online-date done: pages=..., raw=..., accepted=...
[sciencedirect] Crossref update-date batch: member=78, journals=39, window=...
[sciencedirect] Crossref update-date done: pages=..., raw=..., accepted=...
[sciencedirect] Crossref dual batch done: ...
[springer] Meta batch progress: ...
[ieee] RSS entry 1/10: ...
[ieee] combined Saved Search RSS entries=10, accepted_whitelist_records=..., rss_date_fallback=..., pending=...
[total] elapsed=...s
```

## Safety

Never commit `paper_monitor_system/.env`. This ZIP deliberately excludes generated `papers.db` and `online_papers.json`, so existing history is not wiped. GitHub Actions does not perform publisher fetching. The package also excludes the root homepage `index.html`, `assets/`, `images/`, `scripts/`, and root `data/` directory.

# Paper Monitor — LOCAL_FINAL_V3.1

Build: `LOCAL-2026.08.19-V3.1`

This version runs publisher collection on the local Windows computer. GitHub Pages remains only the display layer at:

`https://dm-dut.github.io/paper-monitor/`

## 1. Final data-source strategy

### Elsevier / ScienceDirect — optimized

Normal daily collection does **not** depend on ScienceDirect API or ScienceDirect HTML pages, because the local connectivity test returned API 401 and page 403.

Default path:

1. Optional stable direct RSS, when a feed URL is explicitly configured in `journal_list.xlsx`.
2. Fast Crossref publisher/member batch:
   - Crossref member: `78` (Elsevier BV)
   - DOI prefix: `10.1016`
   - created-date window: yesterday..today by default
   - response fields reduced with `select`
3. Local filtering against the 39-journal ISSN/title whitelist.
4. Records without `published-online` become `pending` and are rechecked later by DOI only.

This replaces the previous 39–78 per-ISSN Crossref calls with one/few cursor-paged batch requests in normal operation.

### Springer Nature — V3.1 simplified

1. One Springer Meta API date-window batch using the Basic-plan-safe page size `p=20`.
2. Local filtering against the 25-journal whitelist.
3. No 25-journal Springer API fallback loop is used.
4. If the Meta batch fails, or reaches the Basic-plan pagination cap, one Crossref prefix batch (`10.1007`) is used as a supplement/fallback.

`onlineDate` from the Springer Meta API remains the preferred date source.

### IEEE

1. One combined `IEEETrans15` Saved Search RSS for all 15 journals.
2. Crossref DOI/title resolution is attempted first.
3. IEEE article page is opened only when Crossref is insufficient.
4. The 15-journal whitelist removes Virtual Journal / Compendium noise.
5. RSS `pubDate` is discovery time only and is never used as the publication online date.

The original Saved Search URL is preserved, including `rowsPerPage=10`. Daily scheduling is recommended because the feed may contain at most 10 visible entries.

## 2. First-time setup

Place/overwrite this package in the local `dm-dut.github.io` repository root. Do **not** delete your existing:

- `paper_monitor_system/data/papers.db`
- `paper-monitor/data/online_papers.json`

Then double-click:

`setup_local.bat`

Edit:

`paper_monitor_system/.env`

At minimum configure:

```text
SPRINGER_API_KEY=...
CROSSREF_MAILTO=your-email@example.com
```

Recommended V3 defaults:

```text
OVERLAP_DAYS=1
CROSSREF_DISCOVERY_DAYS=2
PENDING_RECHECK_DAYS=60
PENDING_RECHECK_MIN_HOURS=20
PENDING_RECHECK_LIMIT=200
HTTP_TIMEOUT=20
HTTP_RETRY_TOTAL=2
REQUEST_PAUSE_SECONDS=0.10
SPRINGER_BATCH_PAGE_SIZE=20
SPRINGER_BATCH_MAX_PAGES=5
CROSSREF_BATCH_ROWS=500
ELSEVIER_CROSSREF_MEMBER_ID=78
```

`CROSSREF_MAILTO` is strongly recommended so Crossref can identify the client in its polite pool.

## 3. Test connections

Run:

`test_connections.bat`

Required V3 checks:

- Springer Meta API
- IEEE Saved Search RSS
- Crossref
- Elsevier Crossref member batch

ScienceDirect API is only an optional diagnostic and is not required for successful daily updates.

## 4. Fetch without Git push

Run:

`fetch_only.bat`

This updates local SQLite/JSON only.

## 5. Normal daily update

Run:

`update_papers.bat`

The sequence is:

1. Confirm Git worktree is clean.
2. `git pull --ff-only` before touching SQLite.
3. Run self-check and self-test.
4. Collect Elsevier / Springer / IEEE.
5. Recheck eligible pending DOI records.
6. Update `papers.db`.
7. Export `paper-monitor/data/online_papers.json`.
8. Commit only the DB and JSON data files.
9. Push to the current Git branch.
10. GitHub Pages displays the new JSON.

Each scheduled run writes a log to:

`paper_monitor_system/logs/update_YYYYMMDD_HHMMSS.log`

The logs directory is ignored by Git.

## 6. Windows Task Scheduler

Recommended frequency: once every day.

Create a task whose program is the full path to:

`update_papers_scheduled.bat`

Set **Start in** to the `dm-dut.github.io` repository root. Useful options:

- Run whether user is logged on or not, if desired.
- Run task as soon as possible after a scheduled start is missed.
- Wake the computer to run this task, if appropriate.

`update_papers.bat` is the interactive launcher and pauses only when an error occurs. For Task Scheduler use `update_papers_scheduled.bat`, which never pauses.

## 7. View locally

Run:

`view_local.bat`

It starts a local web server and opens:

`http://localhost:8000/paper-monitor/`

## 8. Runtime expectations

V3 adds progress and elapsed-time logs. The Elsevier phase should normally be much faster than the old 39-journal serial Crossref loop because normal operation uses one publisher-level batch group.

Typical logs include:

```text
[sciencedirect] Crossref batch group 1/1: member=78, prefix=10.1016, journals=39, created=... .. ...
[sciencedirect] Crossref batch progress: page=1, raw_items_so_far=...
[sciencedirect] Crossref member batch done: pages=..., raw=..., whitelist=..., elapsed=...s
[springer] batch progress: ...
[ieee] RSS entry 1/10: ...
[total] elapsed=...s
```

Actual duration depends on the number of new Crossref/Springer records and network latency.

## 9. Important safety notes

- Never commit `paper_monitor_system/.env`.
- The ZIP deliberately does not contain an empty `papers.db` or `online_papers.json`, so it will not wipe existing history.
- GitHub Actions does not perform publisher fetching in this version.
- The package does not contain the root homepage `index.html`, `assets/`, `images/`, `scripts/`, or root `data/` directory.


## 10. V3.1 Windows launcher fix

V3 used a PowerShell `2>&1 | Tee-Object` pipeline. On Windows PowerShell 5.1, normal native-program stderr (for example Git's `From github.com...`) could be wrapped as `NativeCommandError` when `$ErrorActionPreference=Stop`. V3.1 removes that pipeline. A Python streaming logger now writes the console and log file while preserving the real process exit code.

- Double-click `update_papers.bat` for interactive use. It stays open only if an error occurs.
- Use `update_papers_scheduled.bat` in Windows Task Scheduler. It never waits for keyboard input.
- Logs remain under `paper_monitor_system/logs/`.

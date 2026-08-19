# Paper Monitor LOCAL_FINAL_V2

Build: **LOCAL-2026.08.19-V2**

This version runs collection on the local computer. GitHub Pages is only the public display layer.

## Data-source strategy

### Elsevier / ScienceDirect (39 journals)

The user's real local connectivity test returned:

- ScienceDirect API: HTTP 401
- ScienceDirect journal page: HTTP 403
- Crossref: HTTP 200

Therefore LOCAL V2 no longer depends on the ScienceDirect API or page scraper. The normal path is:

1. **Direct RSS**, only when a stable RSS URL is explicitly entered in `journal_list.xlsx` column `RSS URL`.
2. **Crossref index-date incremental discovery**, always enabled when Crossref fallback is enabled.
3. If Crossref discovers a DOI but does not yet have `published-online`, the record is stored as **pending** rather than discarded.
4. Pending DOIs are rechecked on later runs; when `published-online` appears, the row is promoted to **published**.

ScienceDirect API and page paths remain optional switches for future networks, but are OFF by default in `.env.example`.

### Springer Nature (25 journals)

1. Try one **date-window Springer Meta API** query and filter returned records locally to the 25-journal whitelist.
2. If the batch query is rejected or exceeds the safety limit, fall back to the previous per-journal Meta API chain.
3. Then try Online First page and Crossref as fallbacks.
4. `onlineDate` from the Springer Meta API remains the preferred date.

### IEEE (15 journals)

The user's local test returned **HTTP 200** for the existing `IEEETrans15` combined Saved Search RSS.

1. Fetch the one combined RSS URL once.
2. Resolve each item to the 15-journal whitelist, filtering Virtual Journals/Compendia.
3. Use publisher/Crossref metadata for the true online date.
4. RSS timestamps are discovery timestamps only.
5. If a DOI is discovered before a true online date is available, it may be stored as pending and rechecked later.

The supplied feed currently has `rowsPerPage=10`. LOCAL V2 preserves the URL exactly. If the feed returns exactly 10 items, the program prints a capacity warning. **Daily local scheduling is recommended** to reduce the chance that more than 10 new IEEE items appear between runs.

## Pending mechanism

LOCAL V2 automatically upgrades an existing SQLite database. No manual database reset is needed.

New columns:

- `status`: `pending` or `published`
- `last_checked_at`

Existing `first_seen_at` is the discovery timestamp.

Pending rows remain in `paper_monitor_system/data/papers.db`, but **are not exported** to the public `online_papers.json` until a real online date is available.

## Install / upgrade

This ZIP is an overlay for the existing local clone of `dm-dut.github.io`.

Do **not** delete your existing:

- `paper_monitor_system/data/papers.db`
- `paper-monitor/data/online_papers.json`

The ZIP contains only `.gitkeep` in those folders, so historical data is preserved.

Upgrade steps:

1. Extract the ZIP into the local `dm-dut.github.io` root and overwrite the paper-monitor program files.
2. Commit/push the V2 program changes once.
3. If you already have `paper_monitor_system/.env`, keep it. Recommended V2 switches are:

```text
ENABLE_SCIENCEDIRECT_API=false
ENABLE_SCIENCEDIRECT_PAGE=false
ENABLE_SCIENCEDIRECT_RSS=true
ENABLE_SPRINGER_API=true
ENABLE_SPRINGER_BATCH_API=true
ENABLE_IEEE_API=false
ENABLE_CROSSREF_FALLBACK=true
CROSSREF_DISCOVERY_DAYS=30
PENDING_RECHECK_DAYS=60
```

4. Run `test_connections.bat`.
5. Run `fetch_only.bat` once for a no-Git test.
6. If the result is good, use `update_papers.bat` for normal updates.

## Connection test in V2

`test_connections.bat` now treats these as the **required** local channels:

- Springer Meta API
- IEEE Saved Search RSS
- Crossref
- Elsevier Crossref incremental query

ScienceDirect API/page are printed only as **optional diagnostics**. Their 401/403 responses no longer make the main connection test look failed.

## Normal update

Double-click:

`update_papers.bat`

Order:

1. verify clean Git tree;
2. `git pull --ff-only` before touching SQLite;
3. self-check + self-test;
4. fetch providers;
5. recheck recent pending DOI records;
6. export published rows to `paper-monitor/data/online_papers.json`;
7. commit only `papers.db` and `online_papers.json`;
8. push.

The updater never runs `git pull --rebase` after modifying SQLite.

## Automatic scheduling

Because the IEEE Saved Search feed currently exposes a 10-item page, **daily** scheduling is preferable to every two days. In Windows Task Scheduler, run `update_papers.bat` once per day at a time when the computer is normally on and connected.

If you prefer every two days, the program will still work, but the IEEE feed may have a higher overflow risk if more than 10 matching items appear between runs.

## journal_list.xlsx

79 enabled journals:

- Elsevier: 39
- Springer Nature: 25
- IEEE: 15

Key fields:

`Enabled | Publisher | Journal | ISSN | eISSN | Aliases | Category | Mode | Primary URL | RSS URL | Fallback | Notes`

Modes in V2:

- Elsevier: `elsevier_incremental`
- Springer: `springer_batch_api`
- IEEE: `ieee_saved_search_rss`

For Elsevier, `RSS URL` may remain blank. If you later obtain a stable direct ScienceDirect RSS URL for a journal, paste it into that journal's `RSS URL` cell; the crawler will merge it with Crossref incremental discovery automatically.

## Security

Store keys only in:

`paper_monitor_system/.env`

The file is excluded by `.gitignore`. Do not put keys in the workbook, Python source, web files, or GitHub Pages.

## GitHub Actions

`.github/workflows/update-paper-monitor.yml` remains an informational manual workflow only. There is no scheduled publisher collection on GitHub-hosted runners.

# Paper Monitor LOCAL V4 — Crossref only

V4 deliberately removes the publisher-specific collection paths. Runtime collection uses only the Crossref REST API.

## Architecture

- Elsevier: Crossref member 78
- Springer Nature: Crossref member 297
- IEEE: Crossref member 263
- Each publisher runs two 2-day batch discovery passes:
  1. `from-pub-date` / `until-pub-date`
  2. `from-index-date` / `until-index-date`
- Results are filtered locally against the 79-journal whitelist, first by ISSN and then exact normalized journal title/alias.
- Publication-date priority is: `published-online` → `published` → `issued` → `published-print`.
- DOI links are used for the public page.

## Database reset

Per the requested V4 migration, `paper_monitor_system/data/RESET_TO_V4.flag` is included. On the first V4 sync it deletes the previous `papers.db` and `paper-monitor/data/online_papers.json`, then removes the flag and creates a clean V4 database. Do not re-copy that flag after you have started using V4 unless you intentionally want another reset.

## First run

1. Copy V4 files over the repository.
2. Commit the V4 program files first so the Git working tree is clean.
3. Run `setup_local.bat`.
4. Edit `paper_monitor_system/.env` and set `CROSSREF_MAILTO`.
5. Run `test_connections.bat`.
6. Run `fetch_only.bat` to test without Git push, or `update_papers.bat` for the normal update/push workflow.

## Daily automation

Use `update_papers_scheduled.bat` in Windows Task Scheduler. The manual `update_papers.bat` pauses at the end; the scheduled version does not.

## GitHub

GitHub Pages remains the public display layer. Collection runs locally. The updater commits only:

- `paper_monitor_system/data/papers.db`
- `paper-monitor/data/online_papers.json`

The root personal-homepage files are not part of this package.

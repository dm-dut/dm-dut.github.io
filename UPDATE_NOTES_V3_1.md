# LOCAL V3.1 update notes

- Removed Springer 25-journal per-journal API fallback and its repeated 404/403 loops.
- Springer Meta batch now uses Basic-plan-safe `p=20`, one space-separated online-date query, and at most start positions through 100.
- If Springer Meta batch fails or is capped, one Crossref prefix `10.1007` batch supplements/falls back, followed by local 25-journal whitelist filtering.
- Replaced PowerShell native stderr/Tee-Object logging with `paper_monitor_system.app.run_logged`.
- `update_papers.bat` pauses on error for interactive diagnosis.
- Added `update_papers_scheduled.bat` with no pause for Task Scheduler.

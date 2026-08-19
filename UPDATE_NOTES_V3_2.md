# LOCAL V3.2 update notes

- Elsevier now uses two Crossref member-78 batch passes for the two-day window: `published-online` and `update-date`.
- Removed the standard Elsevier hard DOI-prefix filter; final acceptance is based on the 39-journal ISSN/title whitelist.
- Default Crossref batch size increased to 1000 rows to reduce cursor round trips.
- Slow Elsevier per-ISSN emergency fallback is disabled by default (`ENABLE_ELSEVIER_EMERGENCY_ISSN_FALLBACK=false`).
- IEEE Saved Search RSS is now a true primary source: RSS `pubDate` can be used as a clearly labelled fallback when Crossref/IEEE page dates are unavailable.
- Crossref/publisher `published-online` dates have higher DB priority than the IEEE RSS fallback and can replace it later.
- Springer retains the V3.1 batch-only design; no 25-journal Springer API retry loop is restored.
- `update_papers.bat` now always pauses at the end for manual double-click use; `update_papers_scheduled.bat` remains non-interactive for Task Scheduler.

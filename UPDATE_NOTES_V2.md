# LOCAL_FINAL_V2 update notes

Build: `LOCAL-2026.08.19-V2`

Main changes from LOCAL_FINAL V1:

- Elsevier no longer requires ScienceDirect API/page access.
- Elsevier now always uses Crossref `from-index-date` incremental discovery, plus optional direct RSS configured per journal.
- Added SQLite `pending` records for DOI metadata that lacks `published-online`; pending items are automatically rechecked and never shown publicly until promoted.
- Existing V1 SQLite databases are migrated in place by adding `status` and `last_checked_at` columns.
- Springer first tries one date-window Meta API query and locally filters to the 25-journal whitelist; the per-journal API/Page/Crossref chain remains the fallback.
- IEEE continues to use the one `IEEETrans15` Saved Search RSS; items without a confirmed online date may be retained pending.
- The connection test now evaluates the required V2 channels (Springer, IEEE RSS, Crossref, Elsevier Crossref incremental) and reports ScienceDirect API/page only as optional diagnostics.
- `journal_list.xlsx` modes/fallback descriptions were updated to reflect the new runtime behavior.

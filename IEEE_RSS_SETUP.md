# IEEE Combined Saved Search RSS

LOCAL_FINAL_V3 keeps the single combined `IEEETrans15` Saved Search RSS already stored in `journal_list.xlsx` for all 15 IEEE journals.

Important behavior:

- The feed URL is requested exactly as saved; `rowsPerPage=10` is not rewritten.
- The program fetches the duplicated workbook URL only once.
- RSS timestamps are discovery timestamps, not `online_date`.
- V3 attempts Crossref metadata first and opens the IEEE article page only when needed.
- Virtual Journals / Compendia are discarded through the 15-journal whitelist.
- If an RSS-discovered DOI has no reliable online date yet, it is stored as `pending` and rechecked later by DOI.

Because the current feed exposes 10 items, schedule `update_papers.bat` daily to reduce the risk of the newest-results page overflowing between runs.

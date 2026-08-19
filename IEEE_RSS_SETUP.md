# IEEE Combined Saved Search RSS

LOCAL_FINAL_V3.2 keeps the single combined `IEEETrans15` Saved Search RSS stored in `journal_list.xlsx` for all 15 IEEE journals.

Important behavior:

- The feed URL is requested exactly as saved; `rowsPerPage=10` is not rewritten.
- The duplicated workbook URL is deduplicated, so the feed is fetched only once per run.
- The parser also reads common RSS/Atom/DC/PRISM publication fields when present, improving mapping back to the 15-journal whitelist.
- Crossref and, only when useful, the IEEE article page enrich the RSS item.
- If neither Crossref nor the IEEE page exposes a usable publication date, the IEEE Saved Search RSS `pubDate` may be used as a clearly labelled fallback date.
- A later Crossref/publisher `published-online` date has higher database priority and can replace the RSS fallback.
- Virtual Journals / Compendia are still filtered through DOI/journal/ISSN whitelist validation where metadata is available.
- DOI-bearing items without any usable date remain `pending` and are rechecked later by DOI only.

Because the current feed exposes 10 items, schedule `update_papers_scheduled.bat` daily to reduce the risk of the newest-results page overflowing between runs.

# IEEE RSS setup — LOCAL_FINAL_V2

The existing combined Saved Search feed **IEEETrans15** is already embedded in `paper_monitor_system/journal_list.xlsx` for all 15 IEEE rows. The program deduplicates the URL and requests it once.

Your local connectivity test returned HTTP 200 with 10 RSS/Atom entries, so the RSS path is enabled as the primary IEEE discovery source.

Important:

- The feed URL is preserved exactly, including `rowsPerPage=10`.
- RSS `pubDate` is not treated as the article's online-publication date.
- The 15-journal whitelist filters Virtual Journals and Compendia.
- If a feed item resolves to a whitelist DOI but its true online date is not yet available, it is retained as `pending` for later recheck.
- When the feed returns exactly 10 entries, LOCAL V2 prints a warning that the configured page limit has been reached. Daily updates are recommended.

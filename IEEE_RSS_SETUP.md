# IEEETrans15 Saved Search RSS

The combined Saved Search RSS supplied by the user is already embedded in `paper_monitor_system/journal_list.xlsx` for all 15 IEEE journals.

The LOCAL_FINAL crawler:

1. Deduplicates the identical URL and requests it once.
2. Preserves the URL as supplied; it does not rewrite `rowsPerPage`.
3. Treats RSS as a discovery channel only.
4. Resolves the underlying original IEEE journal from RSS text, the IEEE article page, and/or Crossref.
5. Applies the 15-journal whitelist, excluding unrelated Virtual Journals/Compendia.
6. Does not use RSS `pubDate` as the online-publication date.

To replace the Saved Search later, update the `RSS URL` cells for the 15 IEEE rows in `journal_list.xlsx`, or set `IEEE_SAVED_SEARCH_RSS_URL` in the private local `.env` as an override.

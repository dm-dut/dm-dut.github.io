# IEEE Saved Search RSS — one feed for all 15 journals

This build already contains the combined `IEEETrans15` Saved Search RSS URL supplied for the 15 monitored IEEE journals. You do **not** need to create 15 RSS feeds.

## Recommended IEEE Xplore setup

1. Sign in to your IEEE personal account.
2. Open **My Settings / Saved Searches**.
3. Keep the saved search named `IEEETrans15` (or an equivalent name) that contains the 15 target publication titles.
4. Keep the result sort order as **Newest**.
5. If IEEE Xplore later allows the saved search itself to retain an **Early Access** result filter, enable it. It is not mandatory for this program because the crawler verifies the article's actual online/publication date before insertion.
6. If you regenerate the RSS URL, replace the `RSS URL` value in the 15 IEEE rows of `paper_monitor_system/journal_list.xlsx`. All 15 rows may contain the same URL; the crawler deduplicates it and requests the feed only once.

## Why the feed can contain Virtual Journals / Compendia

IEEE search results sometimes surface items through collections such as `IEEE Biometrics Compendium`, `IEEE RFIC Virtual Journal`, or `IEEE RFID Virtual Journal`. The crawler does **not** trust the feed publication label alone. It resolves the underlying IEEE article page and/or DOI metadata, then accepts the item only when the original journal title or ISSN matches one of the 15 whitelist journals.

Therefore a Virtual Journal result is discarded unless its underlying article actually belongs to one of the monitored journals.

## Date policy

The RSS `pubDate` is treated as discovery time only. It is never used blindly as the displayed Online date. The monitor prefers:

1. IEEE article-page publication/online date;
2. Crossref `published-online` when the IEEE page does not expose a usable date.

An item without a verifiable online date inside the requested window is not inserted.

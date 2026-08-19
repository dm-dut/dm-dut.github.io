# V4 changes

- Replaced ScienceDirect API/page/RSS, Springer Meta API, IEEE API/RSS, and multi-source fallback logic with one Crossref-only collector.
- Uses Crossref member routes: Elsevier 78, Springer 297, IEEE 263.
- Uses 2-day `pub-date` and `index-date` batches; no 30-day scan and no 79-journal network loop.
- Local whitelist matching remains ISSN-first, title/alias-second.
- Removed pending state and cross-source date precedence complexity.
- Fresh V4 database is intentionally created on first run.

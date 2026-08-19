# Hybrid Paper Monitor — implementation notes

## Source order

- Elsevier / ScienceDirect: Articles in Press → Latest / journal page → page-discovered RSS → Crossref.
- Springer Nature: Meta API → Online First page → Crossref.
- IEEE: one combined `IEEETrans15` Saved Search RSS → IEEE page/Crossref date verification → Crossref supplement.

## IEEE combined feed

The same Saved Search RSS URL is intentionally stored in all 15 IEEE rows of `paper_monitor_system/journal_list.xlsx`. The program normalizes and deduplicates those values, then requests exactly one combined feed.

The crawler maps each RSS entry back to the whitelist using, in order:

1. target journal names/aliases visible in the feed;
2. IEEE page `citation_journal_title` / `citation_issn` metadata;
3. Crossref container title / ISSN.

This removes unrelated Virtual Journal / Compendium items while retaining an underlying article when its original journal is one of the 15 monitored titles.

RSS `pubDate` is not used as the paper's online publication date.

## Safety

The package contains no root homepage `index.html` and no empty generated SQLite/JSON data file. Existing `paper_monitor_system/data/papers.db` and `paper-monitor/data/online_papers.json` should remain in the repository.

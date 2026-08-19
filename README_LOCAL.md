# Paper Monitor — LOCAL_FINAL_V3.3

Build: `LOCAL-2026.08.19-V3.3`

This package is designed to run the collector on the local Windows PC. GitHub Pages remains the public display layer; GitHub Actions does not fetch publisher data.

## Daily data-source strategy

### Elsevier / ScienceDirect (39 journals)

The default path does **not** require the ScienceDirect API or HTML pages because the user's local tests returned API 401 and page 403.

V3.3 uses two Crossref publisher/member-level batches for Elsevier BV member `78`, limited to yesterday..today:

1. `from-online-pub-date` / `until-online-pub-date` — highest-confidence explicit online date.
2. `from-pub-date` / `until-pub-date` — generic Crossref publication date used only as a clearly labelled fallback when `published-online` is missing.

Both batches are filtered locally against the 39-journal ISSN/title whitelist. V3.3 removes the very large `update-date` scan that produced many irrelevant pending rows in the previous version. Stable direct RSS URLs can still be added in `journal_list.xlsx` as supplements.

### Springer Nature (25 journals)

Springer Meta API date-window batch is primary. Records are filtered locally to the 25-journal whitelist. If the batch API route fails, one Crossref `10.1007` prefix batch is used. There is no 25-journal loop of alternate Springer API queries.

### IEEE (15 journals)

The single combined `IEEETrans15` Saved Search RSS is fetched once.

V3.3 no longer requires the RSS itself to expose the journal name. Each RSS entry is resolved in this order:

1. DOI found in RSS/link → Crossref DOI lookup → whitelist journal/ISSN confirmation.
2. If DOI is missing or unusable → Crossref `query.title` search → title-similarity test → whitelist journal/ISSN confirmation.
3. IEEE article-page enrichment is optional and disabled by default because it is slower.

A Virtual Journal/Compendium result is rejected unless the underlying Crossref record maps to one of the 15 monitored IEEE journals.

Date priority for IEEE:

1. IEEE publisher-page date (only when optional page enrichment is enabled)
2. Crossref `published-online`
3. IEEE Saved Search RSS `pubDate` as a clearly labelled fallback
4. otherwise keep a DOI-bearing discovery as `pending`

## Data-quality protection

V3.3 treats metadata quality as monotone:

- an existing `published` record is never downgraded to `pending`;
- a missing date never erases a known date;
- a higher-priority publisher/Crossref online date can replace a lower-priority RSS fallback date;
- pending DOI rechecks are DOI-only and delayed by the configured interval.

## Recommended `.env`

```text
SPRINGER_API_KEY=YOUR_KEY
CROSSREF_MAILTO=your_email@example.com

ENABLE_SCIENCEDIRECT=true
ENABLE_SCIENCEDIRECT_API=false
ENABLE_SCIENCEDIRECT_PAGE=false
ENABLE_SCIENCEDIRECT_RSS=true
ENABLE_ELSEVIER_GENERIC_PUBDATE_FALLBACK=true

ENABLE_SPRINGER=true
ENABLE_SPRINGER_API=true
ENABLE_SPRINGER_BATCH_API=true

ENABLE_IEEE=true
ENABLE_IEEE_API=false
ENABLE_IEEE_PAGE_ENRICHMENT=false
ENABLE_IEEE_CROSSREF_SUPPLEMENT=false
IEEE_TITLE_MATCH_THRESHOLD=0.86
IEEE_TITLE_MATCH_ROWS=5

ENABLE_CROSSREF_FALLBACK=true
CROSSREF_DISCOVERY_DAYS=2
OVERLAP_DAYS=1
CROSSREF_BATCH_ROWS=1000
CROSSREF_BATCH_MAX_PAGES=30
ELSEVIER_CROSSREF_MEMBER_ID=78

PENDING_RECHECK_DAYS=60
PENDING_RECHECK_MIN_HOURS=20
PENDING_RECHECK_LIMIT=200

HTTP_TIMEOUT=20
HTTP_RETRY_TOTAL=2
HTTP_RETRY_BACKOFF=0.40
REQUEST_PAUSE_SECONDS=0.10
EXPORT_DAYS=365
```

If `paper_monitor_system/.env` already exists, `setup_local.bat` will not overwrite it.

## First run after upgrading

1. Preserve the existing files:
   - `paper_monitor_system/data/papers.db`
   - `paper-monitor/data/online_papers.json`
2. Overlay the V3.3 package files onto the local repository.
3. Run `test_connections.bat`.
4. Run `fetch_only.bat` first if you want a collection test without Git push.
5. Run `update_papers.bat` for a full manual update and push.

## Manual and scheduled update

Manual update:

```text
update_papers.bat
```

This window pauses at the end so errors do not disappear.

Windows Task Scheduler should run:

```text
update_papers_scheduled.bat
```

The scheduled version has no `pause`.

## Expected V3.3 logs

Elsevier should look like:

```text
[sciencedirect] Crossref online-date batch: ...
[sciencedirect] Crossref online-date done: ...
[sciencedirect] Crossref publication-date batch: ...
[sciencedirect] Crossref publication-date done: ...
[sciencedirect] Crossref dual batch done: ... online_pass=..., publication_fallback_new=...
```

IEEE should now show a per-item resolution result, for example:

```text
[ieee] RSS entry 1/10: ...
[ieee] RSS resolve 1/10 accepted: IEEE Transactions on ...; match=title-search score=0.97; date=rss-fallback
```

or a concrete rejection reason:

```text
[ieee] RSS resolve 2/10 rejected: no-whitelist-match (crossref_method=none, score=0.000)
```

## Local browser preview

Run `view_local.bat`, then open:

```text
http://localhost:8000/paper-monitor/
```

## GitHub Pages

After `update_papers.bat` successfully pushes the two data files, the public page remains:

```text
https://dm-dut.github.io/paper-monitor/
```

# Paper Monitor — FINAL CHECKED 2

This build is intended to be merged into the **root of the existing `dm-dut.github.io` repository**.
It contains **no root `index.html`** and does not contain or replace the homepage `assets/`, `images/`, `scripts/`, root `data/`, `homepage_content.xlsx`, or `publication_database.xlsx`.

After upload:

- Existing homepage: `https://dm-dut.github.io/`
- Paper monitor: `https://dm-dut.github.io/paper-monitor/`

## What this build fixes

### 1. Springer Nature Meta API

- Uses `https://api.springernature.com/meta/v2/json`.
- Builds queries with explicit Boolean operators, e.g.
  `onlinedatefrom:2026-08-16 AND onlinedateto:2026-08-19 AND issn:1572-9338`.
- Uses `p=20` pagination.
- Filters `publicationType=Journal` in Python.
- Tries eISSN first and print ISSN second.
- A 404/other request failure for one Springer journal no longer forces all 25 journals to Crossref. Only journals for which **all** Meta API queries fail are sent to fallback.

### 2. Crossref fallback

The previous journal-scoped route `/journals/{issn}/works` could return 404 for a valid ISSN. This build uses the global Works endpoint:

`https://api.crossref.org/works`

with filters such as:

`issn:1872-9681,type:journal-article,from-online-pub-date:...,until-online-pub-date:...`

A failure for one ISSN is isolated: the alternate ISSN and subsequent journals are still tried. If every Crossref ISSN request fails, the provider is marked as failed so its sync window is not advanced.

The fallback still **requires a real Crossref `published-online` date**. Print/issued dates are not substituted.

### 3. ScienceDirect

- Keeps the current ScienceDirect Search API endpoint.
- Removes the explicit `view=STANDARD` parameter so Elsevier can return the best view allowed by the API key/entitlement.
- HTTP 401/403 is treated as a provider-wide entitlement/authentication condition and switches to Crossref quickly.
- Other journal-specific HTTP errors are isolated and do not terminate all 39 Elsevier journals.
- Optional `ELSEVIER_INSTTOKEN` remains supported.

### 4. IEEE

- IEEE Xplore API remains the primary source.
- Because the current IEEE key also returns 403 in IEEE's official testing interface, 401/403 switches to Crossref fallback.
- Non-authentication HTTP errors on an individual IEEE query are isolated.

### 5. Partial-results safety

If a provider succeeds for some journals and fails later, already fetched/upserted articles are preserved in SQLite. The provider's `last_window_end` is **not** advanced on a failed run, so the next run retries the same time window.

### 6. GitHub binary merge/rebase conflict fixed

The workflow no longer runs `git pull --rebase` on `papers.db` / `online_papers.json`.
It now:

1. saves the generated database and JSON to a temporary directory;
2. fetches and hard-resets to the newest remote branch;
3. restores **only** the two generated paper-monitor data files;
4. commits and pushes them;
5. retries up to three times if the remote branch changes during publishing.

`concurrency: paper-monitor-update` is retained so scheduled/manual refresh runs do not overlap.

## Important upload rule

If your repository already contains:

- `paper_monitor_system/data/papers.db`
- `paper-monitor/data/online_papers.json`

**keep those existing data files.** This ZIP intentionally does not contain empty replacements. Upload/overwrite the code and workflow files, not your existing database/feed.

## Required GitHub Repository Secrets

Under **Settings → Secrets and variables → Actions → Repository secrets**:

- `ELSEVIER_API_KEY`
- `SPRINGER_API_KEY`
- `IEEE_API_KEY`

Optional:

- `ELSEVIER_INSTTOKEN`

Optional Repository variable:

- `CROSSREF_MAILTO`

Do not put API keys in `paper-monitor/config.js` or any public file.

## “立即更新” button

`paper-monitor/config.js` contains no secret.

- If a secure `refreshEndpoint` is configured, the page can trigger the workflow through the included Cloudflare Worker and poll until the feed changes.
- If it is blank, the button opens the repository's `Update paper monitor` Actions page instead of showing the old configuration error.

Worker code is under:

`paper_monitor_system/trigger/cloudflare-worker/`

## Tests performed before packaging

This build was checked with:

- Python `compileall`;
- package/whitelist self-check;
- offline self-tests for Springer Boolean query construction and p=20 pagination;
- offline test confirming Crossref uses `/works + filter=issn:...`;
- simulated Crossref 404 on the first ISSN, confirming alternate ISSN continues;
- simulated per-journal Springer 404, confirming only that journal falls back;
- SQLite DOI upsert and authoritative-date protection tests;
- simulated late-provider failure, confirming partial rows are preserved and sync state does not advance;
- JSON export integration test;
- JavaScript syntax checks and a mocked browser runtime test for publisher/journal filtering, search, and Update Now fallback;
- Cloudflare Worker JavaScript syntax check;
- workflow YAML parse;
- explicit check that no `git pull --rebase` remains;
- ZIP extraction and second-pass package tests.

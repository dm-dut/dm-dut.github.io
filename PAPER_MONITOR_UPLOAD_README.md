# Paper Monitor — checked build for `dm-dut.github.io`

This package is designed to be merged into the **root of the existing `dm-dut.github.io` repository**. It intentionally contains **no root `index.html`**, and it does not contain your homepage `assets/`, `images/`, `data/`, `scripts/`, or homepage Excel files.

After upload:

- Existing homepage: `https://dm-dut.github.io/`
- Paper monitor: `https://dm-dut.github.io/paper-monitor/`

## Repository additions

```text
paper-monitor/                      # public monitoring page
paper_monitor_system/               # Python crawler + SQLite database
.github/workflows/update-paper-monitor.yml
PAPER_MONITOR_UPLOAD_README.md
```

## Required GitHub Repository Secrets

Create these under **Settings → Secrets and variables → Actions → Repository secrets**:

- `ELSEVIER_API_KEY`
- `SPRINGER_API_KEY`
- `IEEE_API_KEY`

Optional:

- `ELSEVIER_INSTTOKEN` — only if Elsevier grants an institutional token for server/off-campus API access.

Optional Repository variable:

- `CROSSREF_MAILTO` — your email address for Crossref polite-pool identification.

No API key is stored in the public website files.

## Data-source behavior

### Springer Nature
The primary source is Springer Nature **Meta API v2**. The query uses only documented `onlinedatefrom`, `onlinedateto`, and `issn`/`pub` constraints. `publicationType` is filtered to Journal in Python. The unsupported `type:Journal` query that caused the previous HTTP 404 has been removed.

### Elsevier / ScienceDirect
The program first tries the ScienceDirect Search API. HTTP 401 from GitHub-hosted runners can indicate entitlement/IP restrictions rather than a bad key. When the primary API is unavailable, the program uses the Crossref fallback without inventing print dates. An optional `ELSEVIER_INSTTOKEN` is supported.

### IEEE
The program first tries the IEEE Xplore Metadata API. If IEEE returns 403, it uses Crossref as the fallback.

### Crossref fallback
The fallback first queries by journal ISSN + `published-online` date. If this returns nothing, it makes a conservative second pass through recently indexed Crossref records and still requires an actual `published-online` date in the requested window. Print/issued dates are never substituted as online dates.

## “立即更新” button

A static GitHub Pages site cannot safely contain a GitHub token. Therefore:

1. If `paper-monitor/config.js` has a secure `refreshEndpoint`, the button triggers GitHub Actions through the included Cloudflare Worker and then polls for new data.
2. If `refreshEndpoint` is blank, the button **does not show the previous configuration error**. It opens the repository's `Update paper monitor` GitHub Actions page, where the signed-in repository owner can click **Run workflow**.

For true one-click updating from the website, deploy the included Worker:

```text
paper_monitor_system/trigger/cloudflare-worker/
```

Then set the Worker URL in `paper-monitor/config.js`.

## First run

Go to:

**Actions → Update paper monitor → Run workflow**

The workflow runs package checks and offline self-tests before accessing publisher APIs.

## Journal whitelist

`paper_monitor_system/journal_list.xlsx` contains the enabled journals and ISSN/eISSN information. You may edit it later; the self-check no longer hard-codes 39/25/15 counts, so changing the whitelist will not break the workflow.

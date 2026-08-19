# Paper Monitor — dm-dut.github.io integration

This package is prepared for an **existing `dm-dut.github.io` GitHub Pages repository**.
It does **not** contain or replace the repository's root `index.html` homepage.

After merging these files into the repository root, the monitoring page is available at:

```text
https://dm-dut.github.io/paper-monitor/
```

## 1. Target repository layout

```text
dm-dut.github.io/
├── index.html                         # your existing homepage — keep unchanged
├── ...                                # your existing homepage files
├── paper-monitor/                     # new public monitoring page
│   ├── index.html
│   ├── app.js
│   ├── config.js
│   ├── style.css
│   └── data/
│       └── online_papers.json
├── app/                               # Python collector
│   ├── sync.py
│   ├── db.py
│   ├── export_json.py
│   ├── journals.py
│   └── providers/
├── data/
│   └── papers.db                      # created/updated by the workflow
├── journal_list.xlsx                  # 79 enabled journals with ISSN/eISSN
├── paper-monitor-requirements.txt
├── trigger/
│   └── cloudflare-worker/             # optional secure manual-refresh trigger
└── .github/
    └── workflows/
        └── update-online-papers.yml
```

## 2. Important path changes in this version

The old standalone project used `web/`. This integration version uses `paper-monitor/` everywhere:

- JSON output: `paper-monitor/data/online_papers.json`
- Browser data URL: `./data/online_papers.json`
- Browser config: `paper-monitor/config.js`
- GitHub Actions commit path: `paper-monitor/data/online_papers.json`

Therefore the GitHub Pages route naturally becomes `/paper-monitor/`.

## 3. GitHub repository secrets

In the `dm-dut.github.io` repository, add these Actions secrets:

```text
ELSEVIER_API_KEY
SPRINGER_API_KEY
IEEE_API_KEY
```

Path:

```text
Settings → Secrets and variables → Actions → New repository secret
```

The browser never receives these API keys.

## 4. Test the update workflow

Open:

```text
Actions → Update online papers → Run workflow
```

The workflow runs:

```bash
python -m app.sync --provider all --initial-days 7
```

and updates the same persistent files used by scheduled/manual runs:

```text
data/papers.db
paper-monitor/data/online_papers.json
```

The program deliberately re-fetches an overlap window and performs DOI / provider-ID / title-based upserts, so scheduled and manually triggered updates do not blindly append duplicates.

## 5. Automatic update schedule

The workflow currently contains:

```yaml
schedule:
  - cron: "17 2 */2 * *"
```

This runs approximately every other day. GitHub cron uses UTC.

## 6. Journal whitelist

`journal_list.xlsx` is already populated with the 79 journals you supplied.

Main columns:

```text
Enabled | Publisher | Journal | ISSN | eISSN | Aliases | Category | Notes
```

All 79 journals are currently `Enabled = 1`.

The collector prefers ISSN/eISSN matching and falls back to normalized journal title/aliases. Disabling a row stops new collection and hides its records from the JSON export without deleting historical rows from SQLite.

## 7. Open the page

Once the files are pushed to the `dm-dut.github.io` repository and GitHub Pages is already enabled for that repository, open:

```text
https://dm-dut.github.io/paper-monitor/
```

No additional Pages site is needed because `paper-monitor/` is simply a subdirectory of the existing user Pages site.

## 8. “立即更新” button

The page includes an optional manual refresh button. Because GitHub Pages is static, the button cannot safely contain a GitHub PAT.

The safe flow is:

```text
paper-monitor page
   ↓
Cloudflare Worker /refresh
   ↓
GitHub workflow_dispatch
   ↓
update-online-papers.yml
   ↓
data/papers.db + paper-monitor/data/online_papers.json
```

Until that endpoint is configured, the scheduled GitHub Actions updates still work normally.

After deploying the included Worker, edit:

```text
paper-monitor/config.js
```

and set:

```js
window.PAPER_TRACKER_CONFIG = {
  refreshEndpoint: "https://YOUR-WORKER.workers.dev/refresh",
  refreshPollIntervalMs: 5000,
  refreshTimeoutMs: 10 * 60 * 1000,
};
```

Do **not** put publisher API keys, a GitHub PAT, or the refresh password in this public JS file.

## 9. Cloudflare Worker variables

The sample worker is in:

```text
trigger/cloudflare-worker/
```

Configure its repository information for the existing GitHub Pages repository, for example:

```text
GITHUB_OWNER=dm-dut
GITHUB_REPO=dm-dut.github.io
GITHUB_WORKFLOW=update-online-papers.yml
GITHUB_REF=main
ALLOWED_ORIGINS=https://dm-dut.github.io
```

Store these as Worker secrets rather than public variables where appropriate:

```text
GITHUB_PAT
REFRESH_PASSWORD
```

## 10. Local preview

From the repository root:

```bash
python -m http.server 8000
```

Then open:

```text
http://localhost:8000/paper-monitor/
```

To test collection locally, create `.env` locally from `.env.paper-monitor.example`, add the three API keys, then run:

```bash
pip install -r paper-monitor-requirements.txt
python -m app.sync --provider all --initial-days 7
```

## 11. Files that should not overwrite your existing homepage

This package deliberately has **no root `index.html`**. Keep your existing homepage files unchanged. Merge only the new/updated monitor files into the repository.

## 12. Merge-safety notes

To reduce the chance of overwriting files from your existing homepage, this package intentionally uses:

```text
PAPER_MONITOR_README.md
paper-monitor-requirements.txt
.env.paper-monitor.example
paper-monitor.gitignore.example
```

It does not include a root `README.md`, root `index.html`, or replacement `.gitignore`. If you want the ignore rules, merge the lines from `paper-monitor.gitignore.example` into your existing `.gitignore`.

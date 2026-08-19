# Online Papers Tracker

A small automated pipeline for collecting newly-online journal papers from ScienceDirect, Springer Nature and IEEE Xplore, storing normalized metadata in a database, and exporting a static JSON feed for a website.

## 1. Architecture

```text
ScienceDirect API ─┐
Springer API ──────┼─> provider adapters -> normalize -> DOI/external-id upsert
IEEE Xplore API ───┘                         |
                                              v
                                       SQLite / PostgreSQL
                                              |
                                              v
                                     online_papers.json
                                              |
                                              v
                                      static HTML + JS
```

The API keys are used only by the scheduled Python job. They are never sent to the browser.

## 2. Minimal fields stored

- publisher/provider
- title
- journal
- authors
- DOI / source identifier
- ISSN when available
- online/publication date + raw date + precision
- source update/discovery date
- article URL
- content type
- first/last seen timestamps

No abstract or full text is stored.

## 3. Date strategy

Different APIs expose different date concepts, so two dates are kept separately:

- `online_date`: the date used to display/sort the paper feed.
- `source_update_date`: the date used to discover delta updates.

Current mapping:

- **Springer Nature:** `onlineDate` is used directly.
- **ScienceDirect:** exact `Load-Date` (first loaded onto ScienceDirect) is used as the operational online date. `prism:coverDate` is deliberately not used for the feed because cover/issue dates can differ from first online appearance.
- **IEEE:** insertion date is used to discover deltas; `publication_date` is used for display when parseable. If it is unavailable, `insert_date` is used as a fallback and the row records that fact.

IEEE is queried for both `Early Access` and `Journals`; DOI-first upsert prevents duplicates as an Early Access item later becomes a normal journal record.

## 4. Local setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in the three API keys in `.env`, then run:

```bash
python -m app.sync --provider all --initial-days 7
```

For a controlled test window:

```bash
python -m app.sync --provider springer --start 2026-08-15 --end 2026-08-19
python -m app.sync --provider sciencedirect --start 2026-08-18 --end 2026-08-19
python -m app.sync --provider ieee --start 2026-08-18 --end 2026-08-19
```

Serve the demo page locally:

```bash
python -m http.server 8000 -d paper-monitor
```

Then open `http://localhost:8000`.

## 5. GitHub Actions

Add repository secrets:

- `ELSEVIER_API_KEY`
- `SPRINGER_API_KEY`
- `IEEE_API_KEY`

The included workflow runs every other day and commits:

- `data/papers.db`
- `paper-monitor/data/online_papers.json`

If your existing site is GitHub Pages, copy the `paper-monitor/data/online_papers.json` output and the filtering/rendering logic from `paper-monitor/app.js` into the site.

### About `*/2` cron

`17 2 */2 * *` means every second day-of-month, which is normally sufficient for this use case but is not a mathematically exact 48-hour timer across month boundaries. If exact 48-hour execution is important, use a server/systemd timer or run GitHub Actions daily and add an elapsed-time guard.

## 6. First-run and incremental logic

On the first run the program looks back 7 days by default. Afterward it remembers the last successful window in `sync_state` and deliberately re-fetches an overlap of 3 days. That overlap is important because publisher indexes can be updated late.

Every fetched record is upserted instead of blindly inserted. Identity priority is:

1. normalized DOI;
2. provider-specific external ID;
3. provider + normalized title hash (last-resort fallback).

## 7. Scaling beyond SQLite

SQLite is a good fit for a personal/static paper feed. If you later collect very large volumes, set `DATABASE_URL` to PostgreSQL and add a PostgreSQL driver to `requirements.txt`. The SQLAlchemy model and fetch logic can remain the same.

For an all-publisher/all-journal feed, API quotas and result volume can become the real bottleneck. In that case add an ISSN/journal whitelist or subject filter before increasing infrastructure size.

## 8. Recommended production refinements

- add an ISSN whitelist if only selected journals matter;
- record per-provider request counts and 429 errors;
- add a daily/weekly health summary from `sync_state`;
- move SQLite to PostgreSQL when repository/database size becomes large;
- keep the static JSON export limited to the most recent 6–12 months even if the database retains full history.

## 9. Journal whitelist (`journal_list.xlsx`)

Only rows with `Enabled = 1` are fetched, stored/updated, and exported to the website.
Recommended columns are:

- `Enabled`: `1` or `0`
- `Publisher`: `Elsevier`, `Springer Nature`, or `IEEE`
- `Journal`: canonical journal title
- `ISSN`, `eISSN`: strongly recommended; API-side filtering and matching prefer ISSN
- `Aliases`: optional alternative titles separated by semicolons
- `Category`: optional future website category
- `Notes`: optional notes

Disabling a journal does **not** delete its historical database rows. It simply stops future collection and hides those rows from the exported web feed.

## 10. “立即更新” button on a static website

GitHub Pages only serves static files, so the browser must not contain a GitHub PAT or any publisher API key. The included implementation uses this flow:

```text
Browser “立即更新”
        |
        v
Cloudflare Worker (password protected; secrets stay server-side)
        |
        v
GitHub REST API -> workflow_dispatch
        |
        v
same update-online-papers.yml
        |
        v
same data/papers.db -> DOI/external-id/title upsert
        |
        v
web/data/online_papers.json
        |
        v
browser polls generated_at and refreshes automatically
```

### Why the next scheduled run will not duplicate manually refreshed data

Both manual and scheduled updates execute the **same workflow**, open the **same committed SQLite database**, and call the same `upsert_article()` function. The database has a unique `identity_key`, whose priority is normalized DOI, source external ID, then a provider/title fallback. In addition, the next run re-fetches a small overlap window; existing rows are updated rather than appended.

The workflow also contains a `concurrency` group so a scheduled run and a button-triggered run are not allowed to update `papers.db` simultaneously.

### Configure the trigger

1. Deploy `trigger/cloudflare-worker/worker.js` as a Cloudflare Worker.
2. Set Worker variables from `wrangler.toml.example`.
3. Store two Worker secrets (never in the website repository):
   - `GITHUB_PAT`: fine-grained GitHub PAT with **Actions: write** for this repository.
   - `REFRESH_PASSWORD`: a password you will type when clicking the update button.
4. Set `ALLOWED_ORIGINS` to the exact origin of your website, for example `https://YOURNAME.github.io` or your custom domain.
5. Put the deployed Worker URL into `paper-monitor/config.js`:

```js
window.PAPER_TRACKER_CONFIG = {
  refreshEndpoint: "https://YOUR-WORKER.workers.dev/refresh",
  refreshPollIntervalMs: 5000,
  refreshTimeoutMs: 10 * 60 * 1000,
};
```

Now clicking **立即更新** asks for the password, securely triggers the GitHub Action, and waits until `online_papers.json` has a new `generated_at` value. The page then reloads the new articles without requiring you to press the browser refresh button.

### Security note

Do not call the GitHub workflow-dispatch REST endpoint directly from `paper-monitor/app.js`, because doing so would require a GitHub credential in public browser code. The trigger Worker exists specifically to keep that credential server-side.

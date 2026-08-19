# Paper Monitor — FINAL_FIX3

This package is designed to be merged into the **root of the existing `dm-dut.github.io` repository**.
It does **not** contain a root `index.html`, `assets/`, `images/`, or the existing homepage data files.

After upload, the monitor page remains:

`https://dm-dut.github.io/paper-monitor/`

## What was fixed in FINAL_FIX3

1. ScienceDirect uses the current Search API V2 endpoint:
   `https://api.elsevier.com/content/search/sciencedirect`
   instead of the retired `/scidir` endpoint that returned HTTP 410.
2. ScienceDirect keeps exact-day `Load-Date(YYYYMMDD)` queries so the stored date is the first-load date on ScienceDirect, rather than the later cover date.
3. Springer continues to use Meta API v2 and `onlineDate`; the query is restricted to `type:Journal` and page size is conservative.
4. If Springer or IEEE returns 401/403, or any provider has a network/API failure, the provider automatically falls back to Crossref using:
   - journal ISSN/eISSN;
   - `type:journal-article`;
   - `from-online-pub-date` / `until-online-pub-date`.
5. Crossref fallback does not replace online dates with print dates. Records without `published-online` are skipped.
6. A provider failure no longer destroys the entire workflow. Other providers and existing database rows are preserved. Add `--strict` manually if you want failures to produce a non-zero exit code.
7. All package imports and paths are validated by `python -m paper_monitor_system.app.selfcheck` before the crawl starts.
8. The workflow prints only whether each GitHub Secret is present and its length. It never prints the secret itself.

## GitHub Repository Secrets

Create/update these under:

`Settings → Secrets and variables → Actions → Repository secrets`

- `ELSEVIER_API_KEY`
- `SPRINGER_API_KEY`
- `IEEE_API_KEY`

Only paste the key value, not `NAME=value`.

Optional repository variable (not a secret):

- `CROSSREF_MAILTO` — your contact email for Crossref polite-pool identification.

## First run

Run:

`Actions → Update paper monitor → Run workflow`

The expected behavior is:

- ScienceDirect: direct Elsevier API if available; Crossref only if direct API fails.
- Springer Nature: direct Meta/v2 if available; Crossref only if direct API fails.
- IEEE: direct IEEE Metadata API if available; Crossref automatically if IEEE continues to return 403.

The scheduled and manual workflow use the same SQLite database, so DOI/external-ID/title upsert logic prevents duplicate rows.

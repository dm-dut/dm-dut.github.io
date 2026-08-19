# Paper Monitor LOCAL_FINAL

Build: **LOCAL-2026.08.19-V1**

This version intentionally runs publisher collection on the local computer, not on GitHub-hosted Actions. GitHub Pages remains the public display layer.

## Final data-source strategy

- **Springer Nature:** Springer Meta API → Online First page → Crossref.
- **ScienceDirect / Elsevier:** local ScienceDirect API when authorized → Articles in Press / Latest / journal page → RSS when exposed → Crossref.
- **IEEE:** the existing combined **IEEETrans15 Saved Search RSS** → IEEE article page / Crossref validation → 15-journal whitelist.
- RSS timestamps are discovery timestamps only. They are **not** used as the final online-publication date.

The exact IEEE Saved Search URL supplied by the user is preserved. This build does **not** rewrite `rowsPerPage=10` to `100`.

## Before installing

The ZIP is an overlay for the existing `dm-dut.github.io` repository. It does not contain or overwrite the root homepage `index.html`, `assets/`, `images/`, `scripts/`, or existing homepage data.

Keep the existing files if they are already present:

- `paper_monitor_system/data/papers.db`
- `paper-monitor/data/online_papers.json`

The package deliberately ships only `.gitkeep` files in those data folders so historical paper data is not erased.

## First-time setup on Windows

1. Extract the ZIP into the root of the local clone of `dm-dut.github.io`.
2. Commit/push the LOCAL_FINAL code changes once (do not add `.env` or `.venv`). This also replaces the old scheduled GitHub workflow with the local-mode informational workflow.
3. Double-click `setup_local.bat`.
4. Open `paper_monitor_system/.env` and fill at least:
   - `SPRINGER_API_KEY=...`
   - `ELSEVIER_API_KEY=...` (recommended; if unauthorized, page/RSS/Crossref continues)
   - `CROSSREF_MAILTO=your_email`
5. Do **not** put keys in `journal_list.xlsx` or public web files.
6. Double-click `test_connections.bat`.

The setup creates `paper_monitor_system/.venv`, installs requirements, creates `.env` from `.env.example`, and runs offline self-checks.

## Connection test

`test_connections.bat` reports separately:

- Springer Meta API status
- ScienceDirect API status
- ScienceDirect page status
- ScienceDirect RSS discovery status
- IEEE Saved Search RSS status and parsed item count
- Crossref status

The test runs from the current local network. A ScienceDirect API failure is not fatal if another ScienceDirect channel works.

## Normal update

Double-click:

`update_papers.bat`

It performs this order:

1. Refuses to run if the Git working tree has uncommitted changes.
2. `git pull --ff-only` **before** touching SQLite.
3. Runs package self-checks.
4. Fetches all three publishers.
5. Updates `paper_monitor_system/data/papers.db`.
6. Exports `paper-monitor/data/online_papers.json`.
7. Commits **only** the DB and JSON.
8. Pushes the current branch to GitHub.

It never performs `git pull --rebase` after generating SQLite data.

For fetching without Git operations, use `fetch_only.bat`.

## Automatic update every two days

Use Windows **Task Scheduler** and create a task that runs `update_papers.bat` from the repository root at your preferred time every 2 days. Choose a time when the computer is normally powered on and connected to the preferred network (for example, the campus network if it improves publisher access).

If Windows missed a scheduled run while the computer was off, enable the Task Scheduler option to run the task as soon as possible after a scheduled start is missed.

## GitHub Actions

`.github/workflows/update-paper-monitor.yml` is replaced with a manual informational workflow only. There is no scheduled publisher collection on GitHub-hosted runners in this build.

This is deliberate: prior GitHub-hosted runs produced ScienceDirect HTTP 403 and IEEE Saved Search RSS HTTP 418. Local network access is tested instead.

## journal_list.xlsx

The `Journals` sheet contains 79 monitored journals:

- Elsevier: 39
- Springer Nature: 25
- IEEE: 15

Configuration columns include:

`Enabled | Publisher | Journal | ISSN | eISSN | Aliases | Category | Mode | Primary URL | RSS URL | Fallback | Notes`

The 15 IEEE rows intentionally share the same `IEEETrans15` RSS URL. The program deduplicates identical URLs and requests the combined feed once.

## Website update button

The public page remains available under `/paper-monitor/`. In LOCAL mode, clicking `立即更新` no longer opens GitHub Actions. It tells the maintainer to run `update_papers.bat` locally and refresh the page after the push completes.

## Important IEEE note

Because the supplied IEEE Saved Search URL currently has `rowsPerPage=10`, only the feed behavior itself determines how many items IEEE actually returns. This build preserves that Saved Search URL exactly to avoid changing a URL that may be tied to IEEE's saved-search/session handling. Run `test_connections.bat` first and inspect the reported RSS/Atom entry count.

If the local RSS still returns HTTP 418 while it opens normally in the browser, do not edit the Python code immediately. That would indicate IEEE is applying browser/session checks locally too; the next fallback to investigate would be an IEEE saved-search email alert or a controlled browser-session method.

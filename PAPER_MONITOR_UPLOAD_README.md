# Paper Monitor — Hybrid Sources Final Build

This package is intended to merge into the root of the existing `dm-dut.github.io` repository. It does **not** contain a root `index.html`, `assets/`, `images/`, or other homepage files.

## Final source strategy

- **Springer Nature:** Springer Meta API (`onlineDate`) → Springer Online First page → Crossref fallback.
- **Elsevier / ScienceDirect:** Articles in Press page → Latest / journal landing page → auto-discovered ScienceDirect RSS → Crossref fallback. The ScienceDirect Search API is disabled by default because the current key returns HTTP 401.
- **IEEE:** one combined Saved Search RSS (`IEEETrans15`) for all 15 monitored journals → IEEE article-page / Crossref date verification → Crossref supplement. The IEEE Metadata API is disabled by default because the current key returns HTTP 403.

RSS timestamps are discovery signals, not publication dates.

## Upload

Merge these into the repository root:

- `paper-monitor/`
- `paper_monitor_system/`
- `.github/workflows/update-paper-monitor.yml`
- `IEEE_RSS_SETUP.md`

If the repository already contains:

- `paper_monitor_system/data/papers.db`
- `paper-monitor/data/online_papers.json`

keep those two generated data files. This package includes `.gitkeep` placeholders only and will not overwrite existing history with an empty database/feed.

## GitHub configuration

Required Repository Secret:

- `SPRINGER_API_KEY`

Optional Repository Variable:

- `CROSSREF_MAILTO` = your email address

The combined IEEE Saved Search RSS URL is already stored in `paper_monitor_system/journal_list.xlsx`; no extra IEEE RSS secret is required.

## journal_list.xlsx

The `Journals` sheet contains 79 journals and these operational fields:

- `Mode`
- `Primary URL`
- `RSS URL`
- `Fallback`

All 15 IEEE rows intentionally share the same Saved Search RSS URL. The Python code deduplicates it before requesting the feed.

## Update button

If `paper-monitor/config.js` has no secure `refreshEndpoint`, **立即更新** opens the authenticated GitHub Actions workflow page. The included Cloudflare Worker can later be deployed for true one-click updating without exposing a GitHub token.

## First test

Create a **new** run:

`Actions → Update paper monitor → Run workflow → main`

Do not use “Re-run” on an old execution when testing newly uploaded code.

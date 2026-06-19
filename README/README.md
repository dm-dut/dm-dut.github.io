# Zhen Zhang Homepage Package

This package uses a stable homepage template plus JSON data files.

## Main workflow

```bash
# 1) Convert homepage content Excel to JSON
python scripts/convert_excel_to_json.py --input homepage_content.xlsx --output data

# 2) Convert publication Excel database to JSON
python scripts/generate_publications_json.py --input publication_database.xlsx --output data/publications.json

# 3) Commit and push to GitHub Pages
```

## Data maintenance

- Stable profile, links, and Google Scholar profile URL are stored in `assets/site.config.js`.
- News, grants, awards, services, group members, and publications are stored in `data/*.json`.
- Publications are generated from `publication_database.xlsx`.
- Working papers are intentionally excluded from `data/publications.json`.
- DOI links are generated automatically as `https://doi.org/{DOI}`. Records without DOI keep an empty link.

## Publications tab

The Publications tab reads `data/publications.json` and supports:

- displaying all records;
- filtering by year;
- filtering by publication category;
- keyword search across title, venue, author, index labels, and conference information.

The current generator outputs English records only and keeps formally published/accepted records: journal articles, conference papers, monographs, and book chapters.

## News links

News text is displayed as plain text. When a link is available, only a small action label such as `DOI`, `Conference`, or `More` is linked.


## v5 notes

- Home keeps the full biography from the original homepage.
- News links are rendered as small links only; talk items do not use DOI links by default.
- Awards with year ranges are split into individual yearly records in `data/awards.json`.
- Special-session service entries use full conference names plus abbreviations.
- Publications are generated from `publication_database.xlsx` by `scripts/generate_publications_json.py`; working papers and non-English records are excluded. DOI links are generated as `https://doi.org/{DOI}`.
- Scholar metrics are read from `data/scholar_stats.json`; when opened locally and fetch is blocked, the page shows a profile link and a refresh hint.


## v6 notes
- Publications are generated from `publication_database.xlsx` with `python scripts/generate_publications_json.py`.
- Working papers are excluded. Chinese-language published records are included using English display fields.
- The portrait is referenced as `images/zz.jpg`; put your photo there.
- Switching tabs resets filters/searches to their initial state.
- Google Scholar metrics are read from `data/scholar_stats.json`; edit it manually or use an API/script updater.


## Google Scholar metrics

The homepage reads Google Scholar metrics from `data/scholar_stats.json`. You can maintain this file manually, or set a GitHub Actions secret named `SERPAPI_KEY` to let `scripts/update_scholar.py` update the JSON automatically via SerpAPI. The optional secret `SCHOLAR_AUTHOR_ID` defaults to `vBSJplMAAAAJ`.

## Google Scholar and Publication Citation Updates (v10)

This version supports automatic Google Scholar updates through SerpAPI.

### What is updated automatically

When `SERPAPI_KEY` is configured in GitHub repository secrets, the weekly GitHub Action will:

1. update `data/scholar_stats.json` for homepage-level indicators: citations, h-index, and i10-index;
2. regenerate `data/publications.json` from `publication_database.xlsx`;
3. query the Google Scholar author profile and add per-publication citation counts for non-Chinese publications;
4. keep Chinese publications citation-free on the webpage, as requested.

### DOI display

The DOI is stored in each publication record as `doi`. The webpage displays it as:

```text
DOI: 10.xxxx/xxxxx
```

and links it to `https://doi.org/<doi>`.

### Required GitHub Secret

Add this repository secret:

```text
SERPAPI_KEY
```

Optional repository variable:

```text
SCHOLAR_AUTHOR_ID=vBSJplMAAAAJ
```

If `SCHOLAR_AUTHOR_ID` is not set, the scripts use `vBSJplMAAAAJ` by default.

### Manual run

In GitHub, go to:

```text
Actions → Update homepage data → Run workflow
```

This immediately refreshes the Scholar statistics and publication citation counts.


## v11 notes

- Google Scholar links use `https://scholar.google.com/citations?user=vBSJplMAAAAJ` without `hl=zh-CN`.
- The homepage displays Citations, h-index and i10-index; the update date appears only in the small Scholar footer.
- `scripts/update_publication_citations.py` requires `SERPAPI_KEY` from GitHub Secrets and skips Chinese-language publications.
- DOI is displayed in each publication entry when the `doi` field is available.


## Multiple links in one News record

In the `News` sheet of `homepage_content.xlsx`, put multiple URLs in the `link` column separated by semicolons:

```text
https://example.com/page1; https://example.com/page2
```

After running `python scripts/convert_excel_to_json.py --excel homepage_content.xlsx --out data`, the website will display them after the news text as `↗1` and `↗2`.


## News: multiple links in one Excel cell

In the `News` sheet, the `link` column supports multiple URLs separated by English or Chinese semicolons. For example:

```text
https://example.com/page1; https://example.com/page2
```

After running:

```bash
python scripts/convert_excel_to_json.py --excel homepage_content.xlsx --out data
```

the generated `data/news.json` will contain both fields:

```json
{
  "link": "https://example.com/page1",
  "links": [
    "https://example.com/page1",
    "https://example.com/page2"
  ]
}
```

`link` is kept as the first URL for backward compatibility, while `links` is the canonical multi-link field used by the current webpage.

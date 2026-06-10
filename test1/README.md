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

# Excel → JSON driven personal homepage

This package follows your preferred design:

- The visual style is based on the earlier `homepage_tabs_integrated.html`.
- Only the **Home** tab displays profile/personal information.
- Other tabs directly display their own content.
- `profile`, `links`, and `scholar` settings are stable and stored in `assets/site.config.js`, not in Excel.
- Dynamic/maintainable content is maintained in `homepage_content.xlsx` and converted to JSON.
- Publications are loaded from `data/publications.json` and support filtering by year, type/category, and keyword.

## Files

```text
index.html
assets/
  style.css
  main.js
  site.config.js
data/
  news.json
  awards.json
  grants.json
  services.json
  group.json
  publications.json
  scholar_stats.json
scripts/
  convert_excel_to_json.py
  update_scholar.py
.github/workflows/update-site.yml
homepage_content.xlsx
```

## How to update non-publication content

Edit `homepage_content.xlsx`, then run:

```bash
python scripts/convert_excel_to_json.py --excel homepage_content.xlsx --out data
```

## How to update publications

Put your existing publication Excel in the repository as `publications.xlsx`, then run:

```bash
python scripts/convert_excel_to_json.py --excel homepage_content.xlsx --publications-xlsx publications.xlsx --out data
```

The converter tries to recognize common English field names such as:

```text
Year, Type, Authors, Authors_EN, Title, Title_EN, Journal, Venue, Volume, Issue, Pages, DOI, Link, Indexes, Labels, Note
```

The webpage displays all publication records by default, and supports filters for year and publication type.

## Scholar stats

`data/scholar_stats.json` is read automatically by the homepage.

Because Google Scholar does not provide an official public frontend API and automated scraping may be unstable, the package keeps this file as a safe JSON source. You can update it manually, use SerpAPI, or adapt `scripts/update_scholar.py` later.


## Layout note
This version uses the top tab-switching layout inspired by `homepage_tabs_integrated.html`; there is no left sidebar. Only Home shows the profile block; other tabs show their own content directly.

# Homepage architecture

## Maintenance principle

```text
Excel / publication Excel
        ↓
scripts/convert_excel_to_json.py
        ↓
data/*.json
        ↓
index.html + assets/main.js render tabs
```

## What is maintained where

### Stored directly in `assets/site.config.js`

These are relatively stable and do not need Excel:

- profile
- email/address
- external links
- Google Scholar JSON path/profile URL
- research keywords

### Maintained in `homepage_content.xlsx`

These are easier to update as table data:

- News
- Awards
- Grants
- Services
- Group
- optional Projects

### Maintained in your existing publication Excel

Publications can be kept in your own Excel format. The converter maps common field names to:

```json
{
  "year": "2026",
  "type": "Journal",
  "authors": "...",
  "title": "...",
  "venue": "...",
  "volume": "",
  "issue": "",
  "pages": "",
  "doi": "",
  "link": "",
  "indexes": "SCI; EI",
  "labels": "ABS 4; FMS A; IF=6.0",
  "note": "in press"
}
```

## Page layout

- Left sidebar navigation
- Home tab: personal header, biography, keywords, Google Scholar stats, latest news
- Publications tab: publication list with filters
- Other tabs: full direct content without repeated personal header

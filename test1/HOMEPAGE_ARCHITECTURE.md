# Homepage Architecture

```text
homepage_tabs_excel_json_v4/
├── index.html
├── homepage_content.xlsx
├── publication_database.xlsx
├── assets/
│   ├── style.css
│   ├── main.js
│   └── site.config.js
├── data/
│   ├── news.json
│   ├── awards.json
│   ├── grants.json
│   ├── services.json
│   ├── group.json
│   ├── scholar_stats.json
│   └── publications.json
└── scripts/
    ├── convert_excel_to_json.py
    ├── generate_publications_json.py
    └── update_scholar.py
```

## Design principles

1. `index.html` defines the page skeleton and tab structure.
2. `assets/style.css` controls the visual style.
3. `assets/main.js` renders all dynamic sections from JSON.
4. `assets/site.config.js` stores stable profile, links, portrait, and Scholar configuration.
5. `homepage_content.xlsx` is for manually maintained non-publication content.
6. `publication_database.xlsx` is the publication database.
7. `scripts/generate_publications_json.py` converts publication Excel into `data/publications.json`.

## Publication JSON schema

Each publication record contains:

```json
{
  "id": "pub-001",
  "type": "Journal Article",
  "year": 2026,
  "authors": ["Zhen Zhang", "Wenyu Yu*"],
  "title": "...",
  "venue": "...",
  "volume": "...",
  "issue": "...",
  "pages": "...",
  "doi": "10.xxxx/xxxx",
  "link": "https://doi.org/10.xxxx/xxxx",
  "indexes": ["SCI", "EI", "ABS 4", "FMS A", "IF=6.0"],
  "labels": ["ESI Highly Cited Paper"],
  "note": "",
  "isbn": "",
  "conference_date": "",
  "conference_address": "",
  "address": "",
  "corresponding_author_note": "* corresponding author"
}
```


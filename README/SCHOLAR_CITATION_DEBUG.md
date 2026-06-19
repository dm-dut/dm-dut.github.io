# Google Scholar citation display checklist

After replacing the files and running **Actions → Update homepage data → Run workflow**, check these files in GitHub:

1. `data/publications.json`

   Each matched publication should contain fields like:

   ```json
   "google_scholar_citations": "35",
   "google_scholar_link": "https://...",
   "citation_source": "author_profile"
   ```

   If `google_scholar_citations` is empty, the webpage can only show the Google Scholar link, not the count.

2. `data/publication_citation_debug.json`

   This file records the matching result for every publication:

   - `matched_author_profile`: matched from your Scholar author profile.
   - `matched_title_search`: matched by title fallback search.
   - `not_matched`: no reliable Scholar record was found.

3. Browser cache

   `index.html` now loads:

   ```html
   assets/main.js?v=27
   assets/style.css?v=27
   ```

   This avoids using an older cached JavaScript file.

## Expected display

- With citation count: `GS Citations: 35`
- With zero citations: `GS Citations: 0`
- Without a reliable count but with Scholar search link: `Google Scholar`

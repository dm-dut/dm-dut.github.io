
# Paper Monitor v13.7.2

Only update collector.

Fix:
- Online date now prefers complete publication date.
- If Crossref only provides YYYY-MM, created.date-time is used to supplement YYYY-MM-DD.
- Frontend remains unchanged.

Replace:
collectors/crossref.py

Then run:
python scripts/update.py

If old papers still show old dates, rebuild database once:
delete database/papers.db
and run update again.

Journal List Web Package

Files:
- index.html: the webpage.
- journal_list.xlsx: editable journal database.
- journals.json: data used by the webpage.
- convert_journal_excel_to_json.py: converts Excel to JSON.
- update_journals.bat: double-click to regenerate journals.json after editing Excel.
- update_and_preview.bat: regenerate JSON and open the webpage.
- watch_excel_auto_update_json.py / .bat: optional watcher; keeps JSON updated when Excel changes.

Usage:
1. Edit journal_list.xlsx.
2. Run update_journals.bat.
3. Upload index.html and journals.json to the same folder, or open index.html locally.

Notes:
- The webpage displays journal names only; clicking a journal name opens the URL field.
- Auxiliary links are stored in Excel under Extra Links using Label|URL; Label2|URL2.

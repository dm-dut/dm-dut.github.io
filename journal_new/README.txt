Journal List Web Package

Files
- index.html: journal list webpage.
- journals.json: data loaded by the webpage.
- journal_list.xlsx: source Excel file.
- convert_journal_excel_to_json.py: converts Excel to JSON.
- update_journals.bat: double-click to regenerate journals.json after editing Excel.
- update_and_preview.bat: regenerate JSON and preview locally.
- watch_excel_auto_update_json.py / .bat: optional watcher for automatic JSON updates.

Usage
1. Edit journal_list.xlsx.
2. Run update_journals.bat to update journals.json.
3. Open index.html or upload all files to the same website folder.

Display rules
- Journal names open the main website link.
- Extra links are shown only when they are different from the main website link, avoiding duplicate Website buttons.
- English journals use a compact 3–4 column layout; Chinese journals use a compact 5-column layout on wide screens.

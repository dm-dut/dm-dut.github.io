Journal List Website Package

Files:
- index.html: main webpage.
- journal_list.xlsx: source data.
- journals.json: webpage data generated from Excel.
- convert_journal_excel_to_json.py: convert Excel to JSON.
- update_journals.bat: regenerate journals.json after editing Excel.
- update_and_preview.bat: regenerate JSON and open the webpage.
- watch_excel_auto_update_json.bat: keep watching Excel and regenerate JSON automatically when the file is saved.

How to update:
1. Edit journal_list.xlsx.
2. Double-click update_journals.bat, or run watch_excel_auto_update_json.bat while editing.
3. Refresh index.html in the browser.

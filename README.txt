Journal List package

Files:
- index.html: journal list webpage
- journals.json: data loaded by the webpage
- journal_list.xlsx: editable data source
- convert_journal_excel_to_json.py: converts Excel to JSON
- update_journals.bat: double-click to update journals.json after editing Excel
- update_and_preview.bat: update JSON and open the webpage
- watch_excel_auto_update_json.bat: keep running to update JSON automatically when Excel changes

Excel format:
Category | Order | Journal | URL | Extra Links (label|url; ...) | Note

For multiple auxiliary links, separate them with semicolons, for example:
CNKI|https://example.com; Wanfang|https://example.com

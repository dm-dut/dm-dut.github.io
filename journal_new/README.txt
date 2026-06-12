Journal List Web Package

Files:
- index.html: journal list page
- journal_list.xlsx: editable journal data
- journals.json: generated data file used by index.html
- convert_journal_excel_to_json.py: convert Excel to JSON
- update_journals.bat: update journals.json after editing Excel
- update_and_preview.bat: update JSON and open the page
- watch_excel_auto_update_json.py / .bat: automatically watch Excel changes and update JSON

Usage:
1. Edit journal_list.xlsx.
2. Run update_journals.bat.
3. Upload index.html and journals.json to your website, or keep all files in the same folder for local use.

Display rules:
- English categories use a three-column layout on wide screens.
- 中文期刊 uses a four-column layout on wide screens.
- Click the journal name to open the main link.
- Supplemental links are shown only when distinct additional links exist, such as CNKI/Wanfang or publisher portals.

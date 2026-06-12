Journal list web package

Files:
- index.html: journal directory webpage
- journal_list.xlsx: source Excel file
- convert_journal_excel_to_json.py: converts Excel to journals.json
- journals.json: data file read by the webpage
- update_journals.bat: regenerate journals.json from journal_list.xlsx
- update_and_preview.bat: regenerate JSON and open the webpage
- watch_excel_auto_update_json.py / .bat: optional watcher

Excel columns:
Category | Order | Journal | URL | Extra Links | Note

Extra Links format:
CNKI|https://...; Wanfang|https://...

The converter also accepts common aliases such as Journal Name, Main Link, Website, Extra Link, Chinese headers, etc.
The webpage uses a clean blue style. Journal names are no longer deliberately bolded; Chinese journal names use the same normal/semi-normal weight as English entries.

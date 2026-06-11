@echo off
python convert_journal_excel_to_json.py --excel journal_list.xlsx --out journals.json
start index.html
pause

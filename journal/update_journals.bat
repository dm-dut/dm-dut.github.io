@echo off
python convert_journal_excel_to_json.py journal_list.xlsx journals.json
pause

git add journals.json
git commit -m "Update journal list data"
git push

pause
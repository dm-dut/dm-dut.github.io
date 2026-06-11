import os, time, subprocess, sys
EXCEL = 'journal_list.xlsx'
SCRIPT = 'convert_journal_excel_to_json.py'
last = None
print('Watching journal_list.xlsx. Press Ctrl+C to stop.')
while True:
    try:
        m = os.path.getmtime(EXCEL)
        if last is None:
            last = m
        elif m != last:
            last = m
            print('Excel updated. Regenerating journals.json ...')
            subprocess.run([sys.executable, SCRIPT], check=False)
            print('Done.')
    except FileNotFoundError:
        print('journal_list.xlsx not found.')
    time.sleep(2)

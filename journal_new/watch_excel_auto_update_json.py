# -*- coding: utf-8 -*-
import os, time, subprocess
EXCEL = 'journal_list.xlsx'
last = None
print('Watching journal_list.xlsx. Press Ctrl+C to stop.')
while True:
    try:
        m = os.path.getmtime(EXCEL)
        if last is None:
            last = m
        elif m != last:
            last = m
            print('Excel changed. Updating journals.json...')
            subprocess.run(['python','convert_journal_excel_to_json.py','--excel',EXCEL,'--out','journals.json'], check=False)
    except FileNotFoundError:
        print('journal_list.xlsx not found.')
    time.sleep(2)

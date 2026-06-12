# -*- coding: utf-8 -*-
import os
import time
import subprocess
from pathlib import Path

excel = Path('journal_list.xlsx')
script = Path('convert_journal_excel_to_json.py')
last = None
print('Watching journal_list.xlsx. Press Ctrl+C to stop.')
while True:
    try:
        mtime = excel.stat().st_mtime
        if last is None:
            last = mtime
        elif mtime != last:
            last = mtime
            subprocess.run(['python', str(script), '--excel', str(excel), '--out', 'journals.json'], check=False)
            print('journals.json updated.')
    except FileNotFoundError:
        print('journal_list.xlsx not found.')
    time.sleep(2)

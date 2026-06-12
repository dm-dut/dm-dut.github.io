#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, time, subprocess, sys
excel = 'journal_list.xlsx'
last = None
print('Watching journal_list.xlsx. Press Ctrl+C to stop.')
while True:
    try:
        m = os.path.getmtime(excel)
        if last is None:
            last = m
        elif m != last:
            last = m
            subprocess.run([sys.executable, 'convert_journal_excel_to_json.py', excel, 'journals.json'], check=False)
            print('journals.json updated.')
    except FileNotFoundError:
        pass
    time.sleep(2)

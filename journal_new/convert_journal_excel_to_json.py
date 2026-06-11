# -*- coding: utf-8 -*-
"""Convert journal_list.xlsx to journals.json.
Usage:
    python convert_journal_excel_to_json.py
    python convert_journal_excel_to_json.py --excel journal_list.xlsx --out journals.json
"""
import argparse, json, re
from pathlib import Path
from openpyxl import load_workbook


def split_extra_links(text):
    links = []
    if not text:
        return links
    parts = [p.strip() for p in str(text).split(';') if p.strip()]
    for p in parts:
        if '|' in p:
            label, url = p.split('|', 1)
        else:
            label, url = 'Link', p
        label, url = label.strip(), url.strip()
        if url:
            links.append({'label': label or 'Link', 'url': url})
    return links


def cell_value(row, header_map, name):
    idx = header_map.get(name.lower())
    if idx is None:
        return None
    return row[idx]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--excel', default='journal_list.xlsx')
    parser.add_argument('--out', default='journals.json')
    args = parser.parse_args()

    wb = load_workbook(args.excel, data_only=True)
    ws = wb['Journals'] if 'Journals' in wb.sheetnames else wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise SystemExit('No data found in Excel.')
    headers = [str(h).strip() if h is not None else '' for h in rows[0]]
    hmap = {h.lower(): i for i, h in enumerate(headers)}
    required = ['category', 'journal', 'url']
    missing = [r for r in required if r not in hmap]
    if missing:
        raise SystemExit('Missing columns: ' + ', '.join(missing))

    journals = []
    categories = []
    for row in rows[1:]:
        if not any(row):
            continue
        category = (cell_value(row, hmap, 'Category') or '').strip() if isinstance(cell_value(row, hmap, 'Category'), str) else cell_value(row, hmap, 'Category')
        journal = (cell_value(row, hmap, 'Journal') or '').strip() if isinstance(cell_value(row, hmap, 'Journal'), str) else cell_value(row, hmap, 'Journal')
        url = (cell_value(row, hmap, 'URL') or '').strip() if isinstance(cell_value(row, hmap, 'URL'), str) else cell_value(row, hmap, 'URL')
        if not category or not journal:
            continue
        if category not in categories:
            categories.append(category)
        order = cell_value(row, hmap, 'Order')
        try:
            order = int(order) if order is not None and str(order).strip() != '' else len([x for x in journals if x['category']==category]) + 1
        except Exception:
            order = len([x for x in journals if x['category']==category]) + 1
        extra_text = cell_value(row, hmap, 'Extra Links (label|url; ...)')
        note = cell_value(row, hmap, 'Note') or ''
        journals.append({
            'category': str(category).strip(),
            'order': order,
            'journal': str(journal).strip(),
            'url': str(url).strip() if url else '',
            'extra_links': split_extra_links(extra_text),
            'note': str(note).strip() if note else ''
        })

    journals.sort(key=lambda x: (categories.index(x['category']) if x['category'] in categories else 999, x['order']))
    Path(args.out).write_text(json.dumps({'categories': categories, 'journals': journals}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Updated {args.out}: {len(journals)} journals, {len(categories)} categories.')

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convert journal_list.xlsx to journals.json.

Excel columns:
Category | Order | Journal | URL | Extra Links (label|url; label|url) | Note

Example extra links:
CNKI|https://example.com; Wanfang|https://example.com
"""
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

NS = {'x':'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}

GENERIC_EXTRA_URLS = {
    'https://ieeexplore.ieee.org',
    'https://www.nature.com',
    'https://journals.vilniustech.lt',
    'https://www.sciengine.com',
}

def normalize_url(url):
    return str(url or '').strip().rstrip('/')

def is_generic_extra_url(url):
    return normalize_url(url) in GENERIC_EXTRA_URLS



def resolve_target_path(target):
    target = str(target or '').strip()
    if target.startswith('/'):
        return target.lstrip('/')
    if target.startswith('xl/'):
        return target
    return 'xl/' + target.lstrip('/')

def load_shared_strings(z):
    try:
        root = ET.fromstring(z.read('xl/sharedStrings.xml'))
    except KeyError:
        return []
    strings = []
    for si in root.findall('x:si', NS):
        texts = []
        # Plain string or rich text runs
        t = si.find('x:t', NS)
        if t is not None and t.text is not None:
            texts.append(t.text)
        for rt in si.findall('.//x:t', NS):
            if rt is not t and rt.text is not None:
                texts.append(rt.text)
        strings.append(''.join(texts))
    return strings

def cell_value(c, shared_strings):
    t = c.attrib.get('t')
    if t == 'inlineStr':
        inline = c.find('x:is/x:t', NS)
        return '' if inline is None or inline.text is None else inline.text
    v = c.find('x:v', NS)
    if v is None or v.text is None:
        return ''
    raw = v.text
    if t == 's':
        try:
            return shared_strings[int(raw)]
        except Exception:
            return raw
    return raw

def col_to_index(cell_ref):
    letters = re.match(r'([A-Z]+)', cell_ref).group(1)
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1

def read_xlsx_first_sheet(path):
    with zipfile.ZipFile(path) as z:
        wb = ET.fromstring(z.read('xl/workbook.xml'))
        sheets = wb.findall('x:sheets/x:sheet', NS)
        first = sheets[0]
        rel_id = first.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
        rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        target = None
        for rel in rels:
            if rel.attrib.get('Id') == rel_id:
                target = rel.attrib['Target']
                break
        if target is None:
            raise RuntimeError('Cannot locate the first worksheet.')
        target = resolve_target_path(target)
        shared_strings = load_shared_strings(z)
        root = ET.fromstring(z.read(target))
        rows = []
        for row in root.findall('x:sheetData/x:row', NS):
            cells = {}
            max_col = -1
            for c in row.findall('x:c', NS):
                ref = c.attrib.get('r','A1')
                idx = col_to_index(ref)
                max_col = max(max_col, idx)
                cells[idx] = cell_value(c, shared_strings)
            rows.append([cells.get(i,'') for i in range(max_col+1)])
        return rows

def parse_extra_links(s):
    result = []
    if not s:
        return result
    for part in str(s).split(';'):
        part = part.strip()
        if not part:
            continue
        if '|' in part:
            label, url = part.split('|', 1)
            label, url = label.strip(), url.strip()
        else:
            label, url = 'Link', part
        if url and not is_generic_extra_url(url):
            result.append({'label': label or 'Link', 'url': url})
    return result

def main():
    excel_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('journal_list.xlsx')
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path('journals.json')
    rows = read_xlsx_first_sheet(excel_path)
    if not rows:
        raise RuntimeError('No rows found.')
    journals, categories = [], []
    for r in rows[1:]:
        r = r + [''] * (6 - len(r))
        category, order, journal, url, extra, note = [x.strip() if isinstance(x,str) else x for x in r[:6]]
        if not category or not journal:
            continue
        if category not in categories:
            categories.append(category)
        try:
            order_val = int(float(order)) if str(order).strip() else len([j for j in journals if j['category'] == category]) + 1
        except Exception:
            order_val = len([j for j in journals if j['category'] == category]) + 1
        journals.append({
            'category': category,
            'order': order_val,
            'journal_old': journal,
            'url': url,
            'extra_links': parse_extra_links(extra),
            'note': note or ''
        })
    payload = {'categories': categories, 'journals': journals}
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Updated {out_path} with {len(journals)} journals in {len(categories)} categories.')

if __name__ == '__main__':
    main()

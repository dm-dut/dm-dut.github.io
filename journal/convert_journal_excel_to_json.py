#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convert journal_list.xlsx to journals.json.

Accepted Excel headers include:
Category / 类别
Order / 序号
Journal / Journal Name / 期刊名
URL / Main Link / Website / 主链接
Extra Links / Extra Link / 辅助链接
Note / 备注

JSON schema used by index.html:
{
  "categories": [...],
  "journals": [
    {"category": "...", "order": 1, "journal": "...", "url": "...",
     "extra_links": [{"label":"CNKI", "url":"..."}], "note":"..."}
  ]
}
"""
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

NS = {'x':'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}

ALIASES = {
    'category': {'category','类别','分类'},
    'order': {'order','序号','sort','排序'},
    'journal': {'journal','journal name','期刊名','期刊名称','name'},
    'url': {'url','main link','website','主链接','网址','link'},
    'extra': {'extra links','extra link','辅助链接','additional links','extras'},
    'note': {'note','备注','notes'}
}

GENERIC_EXTRA_URLS = {
    'https://ieeexplore.ieee.org',
    'https://www.nature.com',
    'https://journals.vilniustech.lt',
    'https://www.sciengine.com',
}

def clean_url(url):
    return str(url or '').strip().rstrip('/')

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
        strings.append(''.join((t.text or '') for t in si.findall('.//x:t', NS)))
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
    m = re.match(r'([A-Z]+)', cell_ref or 'A1')
    letters = m.group(1) if m else 'A'
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1

def read_xlsx_first_sheet(path):
    with zipfile.ZipFile(path) as z:
        wb = ET.fromstring(z.read('xl/workbook.xml'))
        first = wb.find('x:sheets/x:sheet', NS)
        rel_id = first.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
        rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        target = next((rel.attrib['Target'] for rel in rels if rel.attrib.get('Id') == rel_id), None)
        if target is None:
            raise RuntimeError('Cannot locate the first worksheet.')
        root = ET.fromstring(z.read(resolve_target_path(target)))
        shared_strings = load_shared_strings(z)
        rows = []
        for row in root.findall('x:sheetData/x:row', NS):
            cells = {}
            for c in row.findall('x:c', NS):
                idx = col_to_index(c.attrib.get('r', 'A1'))
                cells[idx] = cell_value(c, shared_strings)
            if cells:
                max_col = max(cells)
                # Read up to the last non-empty cell in the row, but later select only recognized columns.
                rows.append([cells.get(i, '') for i in range(max_col + 1)])
        return rows

def norm_header(v):
    return re.sub(r'\s+', ' ', str(v or '').strip().lower())

def build_colmap(header):
    normalized = [norm_header(h) for h in header]
    colmap = {}
    for key, aliases in ALIASES.items():
        for i, h in enumerate(normalized):
            if h in aliases:
                colmap[key] = i
                break
    required = ['category', 'journal', 'url']
    missing = [k for k in required if k not in colmap]
    if missing:
        raise RuntimeError('Missing required columns: ' + ', '.join(missing) + '. Please use headers such as Category, Journal, URL.')
    return colmap

def get(row, colmap, key):
    idx = colmap.get(key)
    return '' if idx is None or idx >= len(row) else str(row[idx] or '').strip()

def parse_extra_links(s, main_url=''):
    result = []
    seen = {clean_url(main_url)}
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
            label, url = 'Link', part.strip()
        nurl = clean_url(url)
        if not url or nurl in seen or nurl in GENERIC_EXTRA_URLS:
            continue
        seen.add(nurl)
        result.append({'label': label or 'Link', 'url': url})
    return result

def clean_note(note):
    note = str(note or '').strip()
    if re.fullmatch(r'\d+(\.0)?', note):
        return ''
    return note

def main():
    excel_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('journal_list.xlsx')
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path('journals.json')
    rows = read_xlsx_first_sheet(excel_path)
    if len(rows) < 2:
        raise RuntimeError('No data rows found.')
    colmap = build_colmap(rows[0])
    journals, categories = [], []
    category_counter = {}
    for row in rows[1:]:
        category = get(row, colmap, 'category')
        journal = get(row, colmap, 'journal')
        url = get(row, colmap, 'url')
        if not category or not journal:
            continue
        if category not in categories:
            categories.append(category)
            category_counter[category] = 0
        category_counter[category] += 1
        order_raw = get(row, colmap, 'order')
        try:
            order_val = int(float(order_raw)) if order_raw else category_counter[category]
        except Exception:
            order_val = category_counter[category]
        journals.append({
            'category': category,
            'order': order_val,
            'journal': journal,
            'url': url,
            'extra_links': parse_extra_links(get(row, colmap, 'extra'), url),
            'note': clean_note(get(row, colmap, 'note'))
        })
    out_path.write_text(json.dumps({'categories': categories, 'journals': journals}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Updated {out_path} with {len(journals)} journals in {len(categories)} categories.')

if __name__ == '__main__':
    main()

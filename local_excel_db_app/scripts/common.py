import argparse
import json
import os
import re
import sqlite3
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', required=True, help='SQLite database path')
    parser.add_argument('--out', required=True, help='Output directory')
    return parser.parse_args()


def read_tables(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    meta = conn.execute('SELECT table_name, sheet_name, columns FROM "_meta_tables" ORDER BY rowid').fetchall()
    result = []
    for row in meta:
        table_name = row['table_name']
        columns = row['columns'].split('|') if row['columns'] else []
        records = [dict(r) for r in conn.execute(f'SELECT * FROM "{table_name}" ORDER BY COALESCE(_order_index, id) ASC, id ASC').fetchall()]
        for record in records:
            record.pop('id', None)
            record.pop('_order_index', None)
        result.append({
            'table_name': table_name,
            'sheet_name': row['sheet_name'],
            'columns': columns,
            'records': records,
        })
    conn.close()
    return result


def ensure_out(out_dir):
    Path(out_dir).mkdir(parents=True, exist_ok=True)


def tex_escape(value):
    value = '' if value is None else str(value)
    replacements = {
        '\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#',
        '_': r'\_', '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}', '^': r'\textasciicircum{}',
    }
    return ''.join(replacements.get(ch, ch) for ch in value)


def safe_filename(name):
    name = re.sub(r'[^0-9A-Za-z_\-\u4e00-\u9fff]+', '_', str(name).strip())
    return name or 'sheet'

import os
from common import parse_args, read_tables, ensure_out, tex_escape, safe_filename

args = parse_args()
ensure_out(args.out)
tables = read_tables(args.db)

for table in tables:
    sheet = table['sheet_name']
    records = table['records']
    columns = table['columns']
    path = os.path.join(args.out, f'{safe_filename(sheet)}.tex')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('% Auto-generated from local SQLite database\n')
        f.write('% You may include this file in LaTeX using \\input{filename.tex}\n\n')
        f.write(f'\\subsection*{{{tex_escape(sheet)}}}\n')
        if not records:
            f.write('No records.\n')
            continue
        for i, record in enumerate(records, start=1):
            f.write(f'\\paragraph{{{i}.}}\n')
            for col in columns:
                value = record.get(col, '')
                if value != '':
                    f.write(f'\\textbf{{{tex_escape(col)}}}: {tex_escape(value)}\\\\\n')
            f.write('\n')

combined_path = os.path.join(args.out, 'all_sections.tex')
with open(combined_path, 'w', encoding='utf-8') as f:
    f.write('% Auto-generated combined TeX file\n\n')
    for table in tables:
        sheet = table['sheet_name']
        f.write(f'% ===== {sheet} =====\n')
        f.write(f'\\input{{{safe_filename(sheet)}.tex}}\n\n')

print(f'TeX generated: {combined_path}')

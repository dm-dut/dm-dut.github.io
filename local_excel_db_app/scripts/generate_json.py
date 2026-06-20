import json
import os
from common import parse_args, read_tables, ensure_out, safe_filename

args = parse_args()
ensure_out(args.out)
tables = read_tables(args.db)

all_data = {}
for table in tables:
    sheet = table['sheet_name']
    records = table['records']
    all_data[sheet] = records
    path = os.path.join(args.out, f'{safe_filename(sheet)}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

combined_path = os.path.join(args.out, 'all_data.json')
with open(combined_path, 'w', encoding='utf-8') as f:
    json.dump(all_data, f, ensure_ascii=False, indent=2)

print(f'JSON generated: {combined_path}')

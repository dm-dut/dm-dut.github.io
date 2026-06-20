import subprocess
import sys
from common import parse_args

args = parse_args()
for script in ['generate_json.py', 'generate_tex.py']:
    subprocess.run([sys.executable, __import__('os').path.join(__import__('os').path.dirname(__file__), script), '--db', args.db, '--out', args.out], check=True)
print('JSON and TeX generated successfully.')

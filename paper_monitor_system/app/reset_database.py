from __future__ import annotations
from .config import DB_PATH,WEB_JSON_PATH,RESET_FLAG_PATH


def main():
    for p in (DB_PATH,WEB_JSON_PATH):
        if p.exists():
            p.unlink(); print(f'deleted: {p}')
    RESET_FLAG_PATH.unlink(missing_ok=True)
    print('Database reset complete. The next sync will create a fresh V4 database.')

if __name__=='__main__': main()

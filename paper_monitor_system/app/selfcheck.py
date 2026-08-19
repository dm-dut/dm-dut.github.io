from __future__ import annotations
from collections import Counter
from .config import BUILD_ID, CROSSREF_MEMBERS, DB_PATH, JOURNAL_LIST_PATH, WEB_JSON_PATH
from .journals import load_journal_list


def main():
    specs=load_journal_list()
    counts=Counter(s.provider for s in specs)
    expected={'sciencedirect':39,'springer':25,'ieee':15}
    if len(specs)!=79 or dict(counts)!=expected:
        raise SystemExit(f'Whitelist mismatch: total={len(specs)}, providers={dict(counts)}')
    for provider,member in CROSSREF_MEMBERS.items():
        bad=[s.journal for s in specs if s.provider==provider and s.crossref_member!=member]
        if bad: raise SystemExit(f'{provider} member mismatch: {bad[:5]}')
    print(f'build={BUILD_ID}')
    print(f'journal_list={JOURNAL_LIST_PATH} ({len(specs)} enabled)')
    print(f'providers={expected}')
    print(f'crossref_members={CROSSREF_MEMBERS}')
    print('strategy=CROSSREF_ONLY: member-level pub-date + index-date batches; local whitelist')
    print(f'database={DB_PATH}')
    print(f'web_json={WEB_JSON_PATH}')
    print('SELF-CHECK OK')

if __name__=='__main__': main()

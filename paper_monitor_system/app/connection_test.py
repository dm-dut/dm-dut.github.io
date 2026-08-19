from __future__ import annotations
from datetime import date,timedelta
import requests
from .config import CROSSREF_API,CROSSREF_MAILTO,CROSSREF_MEMBERS,HTTP_TIMEOUT


def main():
    today=date.today(); start=today-timedelta(days=1)
    ok=True
    for provider,member in CROSSREF_MEMBERS.items():
        params={'filter':f'type:journal-article,from-pub-date:{start},until-pub-date:{today}','rows':0}
        if CROSSREF_MAILTO: params['mailto']=CROSSREF_MAILTO
        try:
            r=requests.get(f'{CROSSREF_API}/members/{member}/works',params=params,timeout=HTTP_TIMEOUT)
            if r.status_code==200:
                total=(r.json().get('message') or {}).get('total-results','?')
                print(f'[Crossref {provider}] OK: HTTP 200; member={member}; total-results={total}')
            else:
                ok=False; print(f'[Crossref {provider}] FAIL: HTTP {r.status_code}; member={member}')
        except Exception as e:
            ok=False; print(f'[Crossref {provider}] FAIL: {type(e).__name__}: {e}')
    print(f'[Crossref mailto] {"configured" if CROSSREF_MAILTO else "NOT configured (recommended)"}')
    if not ok: raise SystemExit(2)

if __name__=='__main__': main()

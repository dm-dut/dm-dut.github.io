from __future__ import annotations
from datetime import date
from unittest.mock import Mock, patch

from .journals import JournalSpec, match_journal
from .providers.crossref_unified import _best_date, _record, fetch_provider

CASES = [
    ('sciencedirect','Elsevier',78,'Applied Soft Computing',('15684946','18729681'),'10.1016/j.asoc.2026.123456'),
    ('springer','Springer Nature',297,'Annals of Operations Research',('02545330','15729338'),'10.1007/s10479-026-00001-1'),
    ('ieee','IEEE',263,'IEEE Transactions on Cybernetics',('21682267','21682275'),'10.1109/TCYB.2026.1234567'),
]


def _response(items):
    r=Mock(); r.raise_for_status.return_value=None
    r.json.return_value={'message':{'items':items}}
    return r


def main():
    for provider,publisher,member,journal,issns,doi in CASES:
        spec=JournalSpec(provider,publisher,journal,issns,(),'',member)
        item={
            'DOI':doi,'title':[f'{publisher} V4 test article'],'author':[{'given':'A','family':'Author'}],
            'container-title':[journal],'ISSN':[f'{issns[0][:4]}-{issns[0][4:]}'],'type':'journal-article',
            'published-online':{'date-parts':[[2026,8,19]]},'published':{'date-parts':[[2026,9,1]]},
        }
        assert _best_date(item)==(date(2026,8,19),'Crossref published-online')
        assert match_journal(provider,'Wrong title',[issns[-1]],(spec,))==spec
        rec=_record(item,provider,spec,'Crossref pub-date')
        assert rec and rec['online_date']==date(2026,8,19) and rec['publisher']==publisher
        fake_session=Mock()
        fake_session.get.side_effect=[_response([item]),_response([item])]
        with patch('paper_monitor_system.app.providers.crossref_unified._session',return_value=fake_session):
            records,stats=fetch_provider(provider,(spec,),date(2026,8,18),date(2026,8,19))
        assert len(records)==1 and stats['requests']==2 and stats['unique']==1 and stats['member']==member
        print(f'{provider} member={member} unified batch PASS')
    print('Crossref date priority PASS')
    print('Crossref ISSN whitelist PASS')
    print('Crossref pub/index merge PASS')
    print('SELF-TEST OK')

if __name__=='__main__': main()

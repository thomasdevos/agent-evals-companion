"""Offline error-analysis work queue. Authored records, never live measurements."""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
import json
from chapter23 import diagnose
from chapter07.replay import digest, load, save

FAMILIES = ('loop','arguments','premature','context','instructions','escalation','confirmation','unknown')
NOTES = (
    'The same read was attempted repeatedly without a changed observation.',
    'The proposed amount was a Boolean, rejected before the effect boundary.',
    'The run ended before collecting the required identity response.',
    'The saved request was rejected for exceeding the context allowance.',
    'A later turn omitted the earlier requirement to verify identity.',
    'The agent requested escalation although the supplied policy allowed resolution.',
    'The final message said refunded while the retained ledger was empty.',
    'The collector did not retain the tool response; the cause remains unresolved.')

def require(ok, message):
    if not ok: raise ValueError(message)

def schedule(): return [f'trace-{i:03d}' for i in range(100)]

def records():
    # A published finite census, not a sample of production traffic.
    result=[]
    for i, identity in enumerate(schedule()):
        f=i % len(FAMILIES)
        result.append(dict(id=identity, incident=f'incident-{i:03d}',
            note=NOTES[f], label=FAMILIES[f], consequence='financial' if f in (1,6) else 'service',
            evidence='unavailable' if f==7 else 'retained',
            review='authored-label', cost_usd=None))
    return result

def validate(rows):
    require(type(rows) is list, 'records must be a list')
    seen=set()
    for r in rows:
        require(type(r) is dict and set(r)==set(records()[0]), 'record fields')
        require(type(r['id']) is str and r['id'] in schedule(), 'foreign or malformed identity')
        require(r['id'] not in seen, 'duplicate scheduled record'); seen.add(r['id'])
        require(type(r['incident']) is str and r['incident']==r['id'].replace('trace','incident'), 'incident binding')
        require(type(r['note']) is str and bool(r['note'].strip()), 'free-form note required')
        require(type(r['label']) is str and r['label'] in FAMILIES, 'taxonomy label')
        require(r['consequence'] in ('financial','service') and type(r['consequence']) is str, 'consequence')
        require(r['review']=='authored-label' and type(r['review']) is str, 'no human approval claim')
        require(r['cost_usd'] is None, 'unknown cost remains null')
        require(r['evidence'] in ('retained','unavailable'), 'evidence status')
        require((r['label']=='unknown')==(r['evidence']=='unavailable'), 'unsupported cause')
    require(seen==set(schedule()), 'missing scheduled record')
    # This packet admits only the published authored corpus. A new corpus needs a new contract.
    require(digest(sorted(rows,key=lambda r:r['id']))==digest(records()), 'changed authored evidence')
    return rows

def analyse(rows):
    validate(rows)
    grouped=defaultdict(list)
    for r in rows: grouped[r['label']].append(r['id'])
    counts=Counter(r['label'] for r in rows)
    triage=sorted([dict(label=f,count=counts[f],consequence='financial' if f in ('arguments','confirmation') else 'service', ids=sorted(grouped[f])) for f in FAMILIES], key=lambda r:(r['consequence']!='financial',-r['count'],r['label']))
    return dict(scheduled=100, available=sum(r['evidence']=='retained' for r in rows),
                taxonomy=triage, population_rate=None, claim='authored corpus only')

def regressions(report):
    diagnose.verify(report)
    b=report['body']
    bad=b['state']['unsafe']; good=b['state']['idempotent']
    # Expectations are literal business requirements, not copied grader outputs.
    return [dict(id='refund-once',owner='payments engineer',
        before=bad['evidence']['after']['refunds']==[['A100',4200]],
        after=good['evidence']['after']['refunds']==[['A100',4200]],
        monitoring='duplicate financial effects per business operation'),
        dict(id='current-policy',owner='retrieval engineer',
        before=b['retrieval'][0]['metrics']['hits']==2,
        after=b['retrieval'][1]['metrics']['hits']==2,
        monitoring='obsolete returned policy identities'),
        dict(id='reject-extra-refund',owner='evaluation engineer',
        before=diagnose.state_score(bad,'weak-presence')=='FAIL',
        after=diagnose.state_score(bad,'pinned')=='FAIL',
        monitoring='false acceptance on the retained extra-refund canary')]

def capture():
    report=diagnose.capture()
    body=dict(schema='diagnosis23-v1', rows=records(), summary=analyse(records()),
        comparison=report, cases=regressions(report), approval='pending-human-review',
        closure='open', provider_requests=0, model_cost_usd=None)
    return dict(body=body,sha256=digest(body))

def verify(packet):
    try:
        require(type(packet) is dict and set(packet)=={'body','sha256'}, 'packet fields')
        b=packet['body']; require(type(b) is dict, 'body')
        require(set(b)=={'schema','rows','summary','comparison','cases','approval','closure','provider_requests','model_cost_usd'}, 'body fields')
        require(packet['sha256']==digest(b), 'digest')
        require(b['schema']=='diagnosis23-v1', 'schema')
        require(digest(b['summary'])==digest(analyse(b['rows'])), 'taxonomy/count contradiction')
        require(digest(b['cases'])==digest(regressions(b['comparison'])), 'repair contradiction')
        require(b['approval']=='pending-human-review' and b['closure']=='open', 'human authority required')
        require(type(b['provider_requests']) is int and b['provider_requests']==0 and b['model_cost_usd'] is None, 'accounting')
    except (KeyError,TypeError,IndexError) as e: raise ValueError('malformed packet') from e
    return packet

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['observe','failure','repair']);a=p.parse_args()
    r=capture()
    if a.mode=='failure':
        r['body']['summary']['taxonomy'][0]['count']+=1
        r['sha256']=digest(r['body'])
        save(Path('chapter23/output/failure.json'),r)
        try: verify(r)
        except ValueError as e: print('Rejected resealed contradiction:',e); return 1
        raise RuntimeError('contradiction accepted')
    verify(r);save(Path('chapter23/output')/(a.mode+'.json'),r)
    print(json.dumps(r['body']['summary'] if a.mode=='observe' else r['body']['cases'],indent=2))
    return 0
if __name__=='__main__':raise SystemExit(main())

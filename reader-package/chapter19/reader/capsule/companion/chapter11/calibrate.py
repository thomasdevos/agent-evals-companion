"""Authored synthetic calibration arithmetic and challenges. No model calls."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from chapter10 import judge as j

VERSION = 'calibration-v1'

def config():
    b=j.binding(j.packet()); b.pop('packet_sha256')
    return dict(version=VERSION, judge=b, implementation=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())

def wrapper(score=3, status='rated', text=None):
    p=j.packet()
    if text is not None: p['candidates']['A']=text
    return j.evaluate(p, lambda _:json.dumps(j.value(status, score if status=='rated' else None, refs=None if status=='rated' else [])))

def corpus(prefix='dev'):
    # Authored reference labels, NOT independently collected human judgements.
    pairs=[('accept',5),('accept',5),('accept',3),('accept',3),('accept',1),('reject',5),('reject',3),('reject',1)]
    schedule=[dict(id=f'{prefix}-{i}',family=f'{prefix}-family-{i}',slice='routine' if i<5 else 'discrepancy',label=label) for i,(label,_) in enumerate(pairs)]
    results=[]
    for s,(_,score) in zip(schedule,pairs):
        p=j.packet()
        # Distinct authored audit incident, not a renamed development packet.
        if prefix=='audit':
            p['evidence']['request']='Explain the recorded partial refund for damaged item B200 and how to dispute it.'
            p['evidence']['observed.refunds']=[['B200',1900]]
            p['evidence']['policy']='Explain the recorded partial refund; refer disputes to support without promising a correction.'
            p['candidates']['A']='A partial refund of 1900 pence is recorded for damaged item B200. Contact support to dispute this amount.'
        p['evidence']['request']+=' Authored scenario slot '+str(s['id'].split('-')[-1])+'.'
        result=j.evaluate(p,lambda _,score=score:json.dumps(j.value(score=score)))
        s['family']='full-refund-seed' if prefix!='audit' else 'damaged-item-partial-refund-seed'
        results.append(dict(id=s['id'],judge=result))
    return schedule,results

def validate_schedule(schedule):
    if type(schedule) is not list or not schedule: raise ValueError('EMPTY_OR_SCHEDULE')
    ids=set()
    for s in schedule:
        if type(s) is not dict or set(s)!={'id','family','slice','label'} or any(type(v) is not str or not v.strip() for v in s.values()): raise ValueError('SCHEDULE')
        if s['label'] not in ('accept','reject','unknown'): raise ValueError('LABEL')
        if s['id'] in ids: raise ValueError('DUPLICATE')
        ids.add(s['id'])
    return ids

def report(schedule,results,threshold):
    ids=validate_schedule(schedule)
    if type(threshold) is not int or threshold not in (1,3,5): raise ValueError('THRESHOLD')
    if type(results) is not list: raise ValueError('RESULTS')
    found={}
    for r in results:
        if type(r) is not dict or set(r)!={'id','judge'} or type(r['id']) is not str or r['id'] not in ids or r['id'] in found: raise ValueError('IDENTITY')
        j.validate_wrapper(r['judge'])
        if r['judge']['packet'] is not None and r['judge']['packet']['mode']!='pointwise': raise ValueError('MODE')
        found[r['id']]=r['judge']
    c=dict(TP=0,FP=0,TN=0,FN=0,unknown=0,refused=0,error=0,missing=0,label_unknown=0,rated=0,accepted=0)
    rows=[]
    for s in schedule:
        r=found.get(s['id']); status='missing' if r is None else r['status']
        decision='abstain'
        if status=='rated':
            c['rated']+=1
            decision='accept' if r['result']['score']>=threshold else 'reject'
            c['accepted']+=int(decision=='accept')
        else: c[status]+=1
        if s['label']=='unknown': c['label_unknown']+=1
        elif decision!='abstain':
            cell={('accept','accept'):'TP',('accept','reject'):'FN',('reject','accept'):'FP',('reject','reject'):'TN'}[(s['label'],decision)]
            c[cell]+=1
        rows.append(dict(id=s['id'],label=s['label'],status=status,decision=decision))
    n=len(schedule); comparable=sum(c[k] for k in ('TP','FP','TN','FN'))
    negatives=sum(s['label']=='reject' for s in schedule); positives=sum(s['label']=='accept' for s in schedule)
    rate=lambda a,b:dict(numerator=a,denominator=b,value=a/b if b else None)
    out=dict(version=VERSION,measurement='authored-synthetic',threshold=threshold,scheduled=n,counts=c,rows=rows,
        agreement=rate(c['TP']+c['TN'],comparable),false_accept=rate(c['FP'],negatives),false_reject=rate(c['FN'],positives),
        coverage=rate(c['rated'],n),accepted_scheduled=rate(c['accepted'],n))
    return out

def costs(schedule,results,fa=8,fr=1,abstain=2):
    if any(type(x) is not int or x<0 for x in (fa,fr,abstain)): raise ValueError('COST')
    if any(s['label']=='unknown' for s in schedule): raise ValueError('UNRESOLVED_LABEL')
    choices=[]
    for t in (1,3,5):
        r=report(schedule,results,t); c=r['counts']
        choices.append(dict(threshold=t,cost=fa*c['FP']+fr*c['FN']+abstain*(r['scheduled']-c['rated']),counts=c))
    return dict(costs=dict(false_accept=fa,false_reject=fr,abstain=abstain),choices=choices,selected=min(choices,key=lambda r:(r['cost'],-r['threshold']))['threshold'],tie_policy='higher threshold')

class Split:
    """Process demonstration, not access control or proof of private data."""
    def __init__(self):
        self.exposed=set(); self.frozen=None; self.opened=False
    def tune(self,schedule):
        validate_schedule(schedule)
        if self.frozen is not None: raise ValueError('FROZEN')
        self.exposed.update(s['family'] for s in schedule)
    def freeze(self,threshold):
        if type(threshold) is not int or threshold not in (1,3,5) or self.frozen is not None: raise ValueError('FREEZE')
        self.frozen=dict(config=config(),threshold=threshold)
    def audit(self,schedule,results):
        validate_schedule(schedule)
        if self.frozen is None or self.frozen['config']!=config(): raise ValueError('NOT_FROZEN')
        if self.opened or self.exposed & {s['family'] for s in schedule}: raise ValueError('EXPOSED_AUDIT')
        self.opened=True
        return report(schedule,results,self.frozen['threshold'])

def challenges():
    binding=config()
    short='Refund recorded for A100. The amount is 4199 pence. Contact support if this differs from your receipt.'
    long=short+' To repeat: '+short
    texts={'old':short,'new':long}
    orders=[['old','new'],['new','old']]
    pair=[]; point=[]
    for order in orders:
        p=j.packet(dict(zip(('A','B'),(texts[x] for x in order))))
        unsafe=j.evaluate(p,lambda _:json.dumps(j.value(score=None,winner='A',refs=['response.A','response.B','policy','observed.refunds'])))
        repaired=j.evaluate(p)
        pair.append(dict(order=order,unsafe=j.canonical_winner(unsafe,order),repaired=j.canonical_winner(repaired,order),packet_sha256=j.digest(p)))
        point.append({identity:j.evaluate(dict(j.packet(),candidates={'A':texts[identity]}))['result']['score'] for identity in order})
    if config()!=binding: raise ValueError('CHALLENGE_VERSION')
    return dict(id='order-verbosity-v1',config=binding,meaning='authored repetition; explanation propositions unchanged',texts=texts,pairwise=pair,pointwise=point,unsafe_order_sensitive=pair[0]['unsafe']!=pair[1]['unsafe'],repaired_order_sensitive=pair[0]['repaired']!=pair[1]['repaired'],pointwise_invariant=point[0]==point[1])

def financial():
    from chapter08.fixtures import fixture
    from chapter08.graders import project,aggregate,KEYS
    t,row=fixture([['A100',4199]]); record=project(t,row,'d','a','e')
    attached=j.attach(record,wrapper(5)); slot={k:record[k] for k in KEYS+('family','variant_group')}
    return aggregate([slot],[attached])

def demo(leak=False):
    s,r=corpus(); choice=costs(s,r); flow=Split(); flow.tune(s); flow.freeze(choice['selected'])
    if leak:
        try: flow.audit(s,r)
        except ValueError as e:
            print(json.dumps(dict(failure=str(e),reason='same families used for tuning and claimed audit'))); return 1
        raise RuntimeError('leak escaped')
    a,b=corpus('audit'); audit=flow.audit(a,b)
    # Explicit nonrated and missing results preserve scheduled denominators.
    extra=deepcopy(a[:4]); extra=[dict(x,id='status-'+str(i)) for i,x in enumerate(extra)]
    extra_results=[dict(id=extra[0]['id'],judge=wrapper(status='unknown')),dict(id=extra[1]['id'],judge=wrapper(status='refused')),dict(id=extra[2]['id'],judge=j.evaluate(j.packet(),lambda _: 'bad json'))]
    skew=[dict(id=str(i),family=str(i),slice='routine' if i<9 else 'discrepancy',label='accept' if i<9 else 'reject') for i in range(10)]
    sr=[dict(id=x['id'],judge=wrapper(5)) for x in skew]
    slices={name:report([x for x in skew if x['slice']==name],[x for x in sr if x['id'] in {y['id'] for y in skew if y['slice']==name}],5) for name in ('routine','discrepancy')}
    out=dict(measurement='authored synthetic; no human or model measurement',configuration=config(),development=choice,audit=audit,nonrated=report(extra,extra_results,5),always_pass=report(skew,sr,5),slices=slices,challenges=challenges(),financial=financial())
    dest=Path(__file__).parent/'output'; dest.mkdir(exist_ok=True); (dest/'report.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')
    print(json.dumps(out,indent=2,allow_nan=False)); return 0

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['leak','repair']);a=p.parse_args();raise SystemExit(demo(a.command=='leak'))

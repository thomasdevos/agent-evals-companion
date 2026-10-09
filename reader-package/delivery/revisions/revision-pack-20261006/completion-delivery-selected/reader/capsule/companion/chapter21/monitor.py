"""Synthetic finite-population monitoring, never a live population claim."""
import argparse
from copy import deepcopy
import json
import math
from pathlib import Path
import random
from chapter03.dataset_lab import load_rows, validate_rows
from chapter04.label_lab import read, validate as validate_split
from chapter08.graders import aggregate
from chapter19.delivery import inputs

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'chapter19-v1'

def fixture():
    population=[]
    for i in range(100):
        population.append(dict(identity=['synthetic-window-1',f'incident-{i:03}', 'attempt-1'],
            stratum='alert' if i<20 else 'routine', failed=i<20,
            outcome=False if i<20 else True, signal=1 if i<20 else 0))
    rng=random.Random(19)
    selected=population[:20]+rng.sample(population[20:],8)
    schedule=[dict(identity=x['identity'],probability=1.0 if x['stratum']=='alert' else .1,
                   stratum=x['stratum']) for x in selected]
    return population,schedule,deepcopy(selected)

def identity(x):
    if type(x) is not list or len(x)!=3 or any(type(v) is not str or not v or '|' in v for v in x):
        raise ValueError('identity must have three nonempty string components')
    return tuple(x)

def analyse(schedule, observations, population_size):
    if type(population_size) is not int or population_size<=0: raise ValueError('population size')
    if type(schedule) is not list or type(observations) is not list: raise ValueError('lists required')
    slots={}
    for s in schedule:
        if type(s) is not dict or set(s)!={'identity','probability','stratum'}: raise ValueError('schedule shape')
        k=identity(s['identity']); p=s['probability']
        if k in slots: raise ValueError('duplicate schedule')
        if s['stratum'] not in ('alert','routine'): raise ValueError('stratum')
        if p is not None:
            if type(p) not in (int,float) or not 0<p<=1 or not math.isfinite(p):
                raise ValueError('probability')
            if not math.isfinite(1 / p):
                raise ValueError('probability weight not representable as finite float')
        slots[k]=s
    if len(slots)>population_size: raise ValueError('schedule exceeds population')
    found={}
    for r in observations:
        if type(r) is not dict or set(r)!={'identity','stratum','failed','outcome','signal'}: raise ValueError('observation shape')
        k=identity(r['identity'])
        if k not in slots or k in found or r['stratum']!=slots[k]['stratum']: raise ValueError('foreign/duplicate identity')
        if type(r['failed']) is not bool or (r['outcome'] is not None and type(r['outcome']) is not bool): raise ValueError('outcome type')
        if type(r['signal']) is not int or r['signal'] not in (0,1): raise ValueError('signal')
        found[k]=r
    complete=len(found)==len(slots) and bool(slots)
    known=complete and all(s['probability'] is not None for s in slots.values())
    failures=sum(r['failed'] for r in found.values())
    matured=[r for r in found.values() if r['outcome'] is not None]
    estimate=None
    if known:
        total=sum(found[k]['failed']/s['probability'] for k,s in slots.items())
        if not math.isfinite(total):
            raise ValueError('weighted total not representable as finite float')
        estimate=total/population_size
    return dict(schema=VERSION,population_size=population_size,scheduled=len(slots),observed=len(found),
        missing=len(slots)-len(found),failures=failures,
        selected_failure_fraction=failures/len(found) if found else None,
        ht_failure_estimate=estimate,
        outcome_observed=len(matured),outcome_pending=len(slots)-len(matured),
        selected_matured_success=sum(r['outcome'] for r in matured)/len(matured) if matured else None,
        population_business_success=None, live_population_rate=None,
        action='INVESTIGATE',may_refund=False,may_deploy=False)

def promote(row, approval):
    validate_rows([row])
    split=read(ROOT/'chapter04/split-manifest.json'); validate_split(split)
    source={r['case_id']:r for r in load_rows(ROOT/'chapter03/repaired.jsonl')}
    if row!=source.get(row['case_id']): raise ValueError('changed source')
    expected=dict(case_id=row['case_id'],decision='approved',authority='authored-review-fixture',
                  purpose='public-regression',answer_exposed=True)
    if json.dumps(approval,sort_keys=True)!=json.dumps(expected,sort_keys=True): raise ValueError('review required')
    case=next(c for c in split['cases'] if c['case_id']==row['case_id'])
    return dict(row=deepcopy(row),incident_group=case['incident_group'],
        exposure=deepcopy(split['exposure'])+[dict(group=case['incident_group'],epoch=3,use='comparison-inspection')],
        role='development-regression',fresh_comparison_eligible=False,review=deepcopy(approval))

def run(mode):
    population,schedule,observations=fixture()
    if mode=='unknown': schedule[0]['probability']=None; observations[0]['outcome']=None; observations.pop()
    result=analyse(schedule,observations,len(population))
    result['finite_population_truth_diagnostic']=sum(r['failed'] for r in population)/len(population)
    if mode=='failure': result['incorrect_population_claim']=result['selected_failure_fraction']
    inherited_schedule,records=inputs('task-failure')
    result['scorecard']=aggregate(inherited_schedule,records)
    row=load_rows(ROOT/'chapter03/repaired.jsonl')[0]
    approval=dict(case_id=row['case_id'],decision='approved',authority='authored-review-fixture',purpose='public-regression',answer_exposed=True)
    promoted=promote(row,approval)
    result['regression']=promoted
    result['monitoring_spec']=dict(signal='authored binary alert, reference-free',threshold=1,
        window='synthetic-window-1',owner='evaluation investigator',business_outcome='separate delayed field',
        comparison='no causal inference',action='INVESTIGATE')
    result['sampling_manifest']=dict(design='alert census plus SRS without replacement of 8 of 80 routine units',seed=19,population_size=100,schedule=schedule)
    result['feedback_queue']=[dict(identity=r['identity'],reason='alert',review='pending') for r in observations if r['signal']]
    out=ROOT/'chapter21/output';out.mkdir(exist_ok=True)
    for name,value in [('population',population),(mode+'-observations',observations),(mode,result)]:
        (out/(name+'.json')).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['failure','repair','unknown']);args=p.parse_args()
    try:
        r=run(args.mode)
        print(json.dumps(r,sort_keys=True,allow_nan=False))
    except (ValueError, OverflowError) as exc:
        p.error(str(exc))
    return 1 if args.mode=='failure' else 0
if __name__=='__main__': raise SystemExit(main())

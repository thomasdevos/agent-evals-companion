"""Paired cluster analysis of authored outcomes using the cumulative scorecard."""
import argparse
from collections import defaultdict
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import random
from chapter08.graders import aggregate, project, KEYS
from chapter08.fixtures import fixture
from chapter12.repeated import analyse as repeated


def number(x, name, lo, hi, integer=False):
    if type(x) not in ((int,) if integer else (int, float)) or not math.isfinite(x) or not lo <= x <= hi:
        raise ValueError('invalid '+name)


def bootstrap(values, seed=17, reps=2000, confidence=.95):
    number(seed,'seed',0,2**32-1,True); number(reps,'reps',100,10000,True)
    number(confidence,'confidence',.5,.999)
    if type(values) is not list or not values:
        raise ValueError('nonempty values required')
    for v in values: number(v,'difference',-1,1)
    rng=random.Random(seed); n=len(values)
    draws=sorted(sum(rng.choices(values,k=n))/n for _ in range(reps))
    def q(p):
        pos=(reps-1)*p; i=int(pos); j=min(i+1,reps-1)
        return draws[i]+(draws[j]-draws[i])*(pos-i)
    return [q((1-confidence)/2),q((1+confidence)/2)]


def card():
    return dict(schema='chapter12-plan-v1',versions=['old','new'],repeats=3,
        meaningful=.1,seed=17,reps=2000,confidence=.95,min_clusters=8,
        estimand='equal incident means of equal case means of paired scheduled attempts',
        max_analyses=1,scope='authored synthetic; descriptive only',
        cluster_basis='declared incident lineage, not family taxonomy')


def validate_plan(p):
    if type(p) is not dict or set(p)!=set(card()): raise ValueError('plan fields')
    for k in ('schema','estimand','scope','cluster_basis'):
        if p[k]!=card()[k]: raise ValueError('unsupported plan '+k)
    if p['versions']!=['old','new']: raise ValueError('versions')
    for k,lo,hi in [('repeats',1,100),('seed',0,2**32-1),('reps',100,10000),('min_clusters',2,1000),('max_analyses',1,1)]:
        number(p[k],k,lo,hi,True)
    number(p['meaningful'],'meaningful',0,1); number(p['confidence'],'confidence',.5,.999)


class Experiment:
    """One local freeze/open/analyse cycle; not an access-control or secrecy service."""
    def __init__(self): self.phase='planning'; self.exposed=set(); self._plan_bytes=None
    @property
    def plan(self):
        # Each access decodes an independent copy, including nested values.
        return json.loads(self._plan_bytes) if self._plan_bytes is not None else None
    @property
    def digest(self):
        return hashlib.sha256(self._plan_bytes).hexdigest() if self._plan_bytes is not None else None
    def expose(self, groups):
        if self.phase!='planning': raise ValueError('exposure registration closed')
        self.exposed.update(groups)
    def freeze(self,p):
        if self.phase!='planning': raise ValueError('already frozen')
        snapshot=deepcopy(p); validate_plan(snapshot)
        self._plan_bytes=json.dumps(snapshot,sort_keys=True,allow_nan=False).encode()
        self.phase='frozen'
    def analyse(self,schedule,records):
        if self.phase!='frozen': raise ValueError('single analysis budget exhausted or not frozen')
        self.phase='spent'  # even failed opening consumes this local attempt
        plan_bytes=self._plan_bytes
        snapshot=json.loads(plan_bytes); validate_plan(snapshot)
        if self.exposed & {s['incident'] for s in schedule}: raise ValueError('EXPOSED_INCIDENT')
        result=analyse(schedule,records,snapshot)
        result['plan_sha256']=hashlib.sha256(plan_bytes).hexdigest()
        return result


def analyse(schedule,records,p):
    validate_plan(p)
    if type(schedule) is not list or type(records) is not list: raise ValueError('lists required')
    pairs=defaultdict(dict); groups={}; case_meta={}
    for s in schedule:
        if type(s) is not dict or type(s.get('incident')) is not str or not s['incident']: raise ValueError('incident required')
        if s.get('agent_revision') not in p['versions']: raise ValueError('foreign version')
        key=(s['dataset_revision'],s['task_id'],s['trial_id'])
        if s['agent_revision'] in pairs[key]: raise ValueError('duplicate scheduled pair')
        pairs[key][s['agent_revision']]=s
        case=(s['dataset_revision'],s['task_id'])
        meta=(s['incident'],s['family'],s['variant_group'])
        if case in case_meta and case_meta[case]!=meta: raise ValueError('case lineage mismatch')
        case_meta[case]=meta; groups[case]=s['incident']
    if any(set(v)!=set(p['versions']) for v in pairs.values()): raise ValueError('unpaired schedule')
    base=repeated(schedule,records,p['repeats'],p['repeats'])['scorecard']
    statuses={tuple(r['slot'][k] for k in KEYS):r['result_status'] for r in base['records']}
    differences=defaultdict(list); incomplete=0
    for key,slots in sorted(pairs.items()):
        ss=[statuses[tuple(slots[v][k] for k in KEYS)] for v in p['versions']]
        if any(s not in ('PASS','FAIL') for s in ss): incomplete+=1
        differences[key[:2]].append(int(ss[1]=='PASS')-int(ss[0]=='PASS'))
    case_d={k:sum(v)/len(v) for k,v in differences.items()}
    incident=defaultdict(list)
    for k,v in case_d.items(): incident[groups[k]].append(v)
    cluster={k:sum(v)/len(v) for k,v in sorted(incident.items())}
    values=list(cluster.values()); n=len(values)
    effect=sum(values)/n if n else None
    degenerate=bool(values) and len(set(values))==1
    eligible=n>=p['min_clusters'] and not incomplete and not degenerate
    interval=bootstrap(values,p['seed'],p['reps'],p['confidence']) if eligible else None
    reason='INCOMPLETE_PAIRS' if incomplete else 'EMPTY' if not n else 'FEW_CLUSTERS' if n<p['min_clusters'] else 'DEGENERATE' if degenerate else 'SYNTHETIC_ONLY'
    return dict(schema='comparison-v2',scorecard=base,plan=deepcopy(p),
        scheduled_pairs=len(pairs),incomplete_pairs=incomplete,declared_clusters=n,
        empirical_independent_clusters=0,authored_taxonomy_families=base['authored_families'],
        case_differences=[dict(dataset_revision=k[0],task_id=k[1],difference=v) for k,v in case_d.items()],cluster_differences=cluster,
        scheduled_completion_difference=effect,scored_effect=None if incomplete else effect,
        illustrative_percentile_interval=interval,decision='DESCRIPTIVE_INCONCLUSIVE',reason=reason,
        interval_exceeds_meaningful=bool(interval and interval[0]>p['meaningful']),
        sensitivity=dict(leave_one_cluster_out=[sum(values[:i]+values[i+1:])/(n-1) for i in range(n)] if n>1 else [],
            trial_weighted_difference=sum(sum(v) for v in differences.values())/len(pairs) if pairs else None))


def corpus(small=False):
    # Distinct IDs below are synthetic hypothetical incidents, never real independence evidence.
    patterns=[(False,True)]*3+[(True,False)] if small else [(False,True)]*6+[(True,False)]*2+[(True,True)]*4
    schedule=[]; records=[]
    for i,(old,new) in enumerate(patterns):
        for variant in range(10 if small else 2):
            for attempt in range(1,4):
                for version,success in [('old',old),('new',new)]:
                    trial,row=fixture(None if success else [['A100',4199]])
                    row['case_id']=f'incident-{i}-case-{variant}'
                    row['variant_group']=f'incident-{i}'
                    trial['trial_id']=row['case_id']+':'+str(attempt)
                    rec=project(trial,row,'authored-paired-v1',version,trial['trial_id'])
                    rec['diagnostics']['communication']=dict(review_status='reviewed',rating=5,provenance='author-synthetic')
                    slot={k:rec[k] for k in (*KEYS,'family','variant_group')}
                    slot.update(attempt=attempt,incident=f'incident-{i}')
                    schedule.append(slot); records.append(rec)
    return schedule,records


def workflow(mode,p):
    e=Experiment(); e.expose({'development-incident'}); e.freeze(p)
    s,r=corpus(mode in ('failure','repair'))
    report=e.analyse(s,r)
    if mode=='failure':
        # Real defective calculation: paired retries are incorrectly resampled as independent units.
        flat=[case['difference'] for case in report['case_differences']]*p['repeats']
        interval=bootstrap(flat,p['seed'],p['reps'],p['confidence'])
        report['unsafe']=dict(assumed_independent=len(flat),interval=interval,
            recommendation='IMPROVED' if interval[0]>p['meaningful'] else 'INCONCLUSIVE')
        report['detected']='PSEUDOREPLICATION'
    return report


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('mode',choices=['run','failure','repair'])
    parser.add_argument('--seed',type=int,default=17); parser.add_argument('--reps',type=int,default=2000)
    parser.add_argument('--confidence',type=float,default=.95)
    a=parser.parse_args(); p=card(); p.update(seed=a.seed,reps=a.reps,confidence=a.confidence)
    try: report=workflow(a.mode,p)
    except (ValueError,KeyError,TypeError) as exc: parser.error(str(exc))
    out=Path('chapter13/output'); out.mkdir(parents=True,exist_ok=True)
    (out/(a.mode+'.json')).write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(report,allow_nan=False))
    return 1 if a.mode=='failure' else 0

if __name__=='__main__': raise SystemExit(main())

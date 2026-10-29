"""Offline programme accounting. All prices and labour are hypothetical."""
import argparse
import json
import math
from pathlib import Path
from chapter03.dataset_lab import load_rows
from chapter05.harness import execute
from chapter08.graders import project, aggregate, KEYS
from chapter12.repeated import cost_summary, budget
from chapter13.compare import workflow, card
from chapter19.delivery import inputs

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'chapter20-programme-v1'
ROLES = {'dataset':'curate', 'grader':'validate', 'harness':'operate', 'decision':'hold-or-review'}

def number(v):
    try:
        valid = type(v) in (int,float) and math.isfinite(v) and v >= 0
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError('finite nonnegative in-range numeric amount required')
    return v

def handover(rows):
    if type(rows) is not list or len(rows)!=len(ROLES): raise ValueError('ownership obligations')
    seen=set()
    for r in rows:
        if type(r) is not dict or set(r)!={'role','owner','right','days','authored'}: raise ValueError('ownership shape')
        role=r['role']
        if type(role) is not str or role not in ROLES or role in seen: raise ValueError('duplicate or foreign role')
        seen.add(role)
        if type(r['owner']) is not str or not r['owner'].strip(): raise ValueError('owner identity')
        if type(r['right']) is not str or r['right']!=ROLES[role]: raise ValueError('decision right mismatch')
        if type(r['days']) is not int or not 1<=r['days']<=90: raise ValueError('review cadence')
        if r['authored'] is not True: raise ValueError('authored identity only')
    return rows

def owners():
    return [dict(role=k,owner='fixture-'+k,right=v,days=7 if k=='harness' else 30,authored=True) for k,v in ROLES.items()]

def account(schedule, records, costs):
    score=aggregate(schedule,records)
    slots={tuple(s[k] for k in KEYS) for s in schedule}
    seen=set(); total=0; unknown=0
    for row in costs:
        if type(row) is not dict or set(row)!=set(KEYS)|{'request_cents','labelling_cents','investigation_cents','infrastructure_cents','live_model_cost'}: raise ValueError('cost shape')
        ident=tuple(row[k] for k in KEYS)
        if any(type(x) is not str or not x for x in ident) or ident not in slots or ident in seen: raise ValueError('cost identity')
        seen.add(ident)
        for k in ('request_cents','labelling_cents','investigation_cents','infrastructure_cents'):
            if row[k] is None: unknown+=1
            else: total=number(total + number(row[k]))
        if row['live_model_cost'] is not None: number(row['live_model_cost'])
    complete=seen==slots and unknown==0
    return dict(scorecard=score,known_scenario_subtotal_cents=total,scenario_total_cents=total if complete else None,
        scenario_cost_per_successful_trial_cents=number(total/score['passed']) if complete and score['passed'] else None,
        scenario_cost_per_scheduled_task_cents=number(total/score['scheduled_tasks']) if complete and score['scheduled_tasks'] else None,
        missing_cost_rows=len(slots-seen),unknown_components=unknown,live_model_cost=None,
        basis='Hypothetical cents: requests 2 each, labelling 10 per task, investigation 100 per unsuccessful trial, infrastructure 1 per trial')

def suite(rows, selected):
    if type(selected) is not list or any(type(x) is not str for x in selected) or len(set(selected))!=len(selected): raise ValueError('suite identities')
    by={r['case_id']:r for r in rows}
    if not set(selected)<=set(by): raise ValueError('foreign case')
    obligations={(r['family'],r['severity']) for r in rows}
    kept={(by[x]['family'],by[x]['severity']) for x in selected}
    # Preserve every high-severity case, not merely its family representative.
    mandatory={r['case_id'] for r in rows if r['severity']=='high'}
    lost=sorted(set(by)-set(selected))
    return dict(full_cases=len(rows),selected_cases=len(selected),lost_cases=lost,lost_count=len(lost),
        obligations=[list(x) for x in sorted(obligations)],missing_obligations=[list(x) for x in sorted(obligations-kept)],
        missing_mandatory=sorted(mandatory-set(selected)),eligible=kept==obligations and mandatory<=set(selected),
        equivalent_full_coverage=False,retirement='NONE; saturation alone is insufficient',
        full_review='before release and weekly',frequent_review='each local change')

def run(mode):
    rows=load_rows(ROOT/'chapter03/repaired.jsonl')
    results={}
    for label,retry in [('direct',False),('bounded-retry',True)]:
        trials=[]; records=[]; schedule=[]; costs=[]
        for row in rows:
            t=execute(row,'fixture',retry,'transient'); trials.append(t)
            r=project(t,row,'chapter03-repaired',label,'chapter24:'+row['case_id']); records.append(r)
            s={k:r[k] for k in (*KEYS,'family','variant_group')}; schedule.append(s)
            costs.append(dict(**{k:r[k] for k in KEYS},request_cents=t['ledger']['request_attempts']*2,
                labelling_cents=10,investigation_cents=0 if r['result_status']=='PASS' else 100,
                infrastructure_cents=1,live_model_cost=None))
        ledger=cost_summary(trials)
        results[label]=dict(trials=trials,schedule=schedule,records=records,cost_rows=costs,
            account=account(schedule,records,costs),ledger=ledger,
            budget=budget(trials[0]['ledger']),request_cap=8,action_cap=6,
            timing_basis='observed local fixture execution; not provider latency')
    chosen=[]; covered=set()
    for row in rows:
        obligation=(row['family'],row['severity'])
        if row['severity']=='high' or obligation not in covered: chosen.append(row['case_id']); covered.add(obligation)
    health=suite(rows,chosen)
    fs,fr=inputs('task-failure')
    comparison=workflow('repair',card())
    return dict(schema=VERSION,mode=mode,baselines=results,suite_health=health,selected=chosen,
        ownership=handover(owners()),financial_scorecard=aggregate(fs,fr),comparison=comparison,
        naive_claim='direct has fewer requests so is cheaper' if mode=='failure' else None,
        decision='REJECT_REQUEST_ONLY_CLAIM' if mode=='failure' else 'ADOPT_REDUCED_LOCAL_REGRESSION_ONLY',
        architecture_promotion='DEFER: financial failure and inconclusive comparison remain',
        may_deploy=False,may_refund=False,live_prices=None,live_usage=None)

def main():
    p=argparse.ArgumentParser(); p.add_argument('mode',choices=['failure','repair']); a=p.parse_args()
    try:
        report=run(a.mode)
        serialized=json.dumps(report,indent=2,allow_nan=False)+'\n'
    except (ValueError, OverflowError) as exc:
        import sys
        print('accounting error: '+str(exc), file=sys.stderr)
        return 2
    out=ROOT/'chapter24/output'; out.mkdir(exist_ok=True)
    (out/(a.mode+'.json')).write_text(serialized)
    print(json.dumps({k:v for k,v in report.items() if k not in ('baselines','financial_scorecard','comparison')}))
    return 1 if a.mode=='failure' else 0
if __name__=='__main__': raise SystemExit(main())

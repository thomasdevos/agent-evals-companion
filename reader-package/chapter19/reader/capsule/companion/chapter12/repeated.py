"""Repeated deterministic executions and explicitly synthetic analysis exercises."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
from chapter03.dataset_lab import load_rows
from chapter05.harness import execute
from chapter08.graders import aggregate, project, identity


def positive(value, name):
    if type(value) is not int or not 1 <= value <= 100:
        raise ValueError(name + ': exact integer in 1..100 required')


def fraction(a, b):
    return dict(numerator=a, denominator=b, value=a/b if b else None)


def subset_events(n, c, k):
    positive(n, 'n'); positive(k, 'k')
    if type(c) is not int or not 0 <= c <= n or k > n:
        raise ValueError('invalid successes or k')
    return dict(at_least_one=1-math.comb(n-c,k)/math.comb(n,k),
                all_attempts=math.comb(c,k)/math.comb(n,k))


def analyse(schedule, records, repeats=3, k=3):
    positive(repeats, 'repeats'); positive(k, 'k')
    if k > repeats or type(schedule) is not list or type(records) is not list:
        raise ValueError('invalid schedule or k')
    groups = {}
    seen = set()
    for s in schedule:
        if type(s) is not dict:
            raise ValueError('slot object required')
        key = identity(s)
        for name in ('family','variant_group'):
            if type(s.get(name)) is not str or not s[name]:
                raise ValueError('group strings required')
        if key in seen:
            raise ValueError('duplicate schedule')
        seen.add(key)
        positive(s.get('attempt'), 'attempt')
        if s['attempt'] > repeats or s['trial_id'] != s['task_id']+':'+str(s['attempt']):
            raise ValueError('trial identity/attempt mismatch')
        g = groups.setdefault((key[0],key[1],key[3]), [])
        g.append(s)
    for slots in groups.values():
        if sorted(s['attempt'] for s in slots) != list(range(1,repeats+1)):
            raise ValueError('incomplete scheduled group')
        if len({(s['family'],s['variant_group']) for s in slots}) != 1:
            raise ValueError('task group mismatch')
    base = aggregate(schedule, records)
    statuses = {identity(r['slot']): r['result_status'] for r in base['records']}
    tasks=[]
    for key, slots in sorted(groups.items()):
        ss=[statuses[identity(s)] for s in sorted(slots,key=lambda x:x['attempt'])]
        c=ss.count('PASS'); eligible=sum(x in ('PASS','FAIL') for x in ss)
        complete=eligible==repeats
        tasks.append(dict(task_id=key[1], family=slots[0]['family'], statuses=ss,
            scheduled=repeats, eligible=eligible, success=fraction(c,repeats),
            measured_only=fraction(c,eligible), first_attempt=ss[0]=='PASS',
            at_least_one=any(x=='PASS' for x in ss), all_attempts=all(x=='PASS' for x in ss),
            complete_scored_group=complete,
            subset_estimates=subset_events(repeats,c,k) if complete else None))
    return dict(schema='chapter11-repeated-v1', scorecard=base, per_task=tasks, k=k,
        first_attempt=fraction(sum(t['first_attempt'] for t in tasks),len(tasks)),
        at_least_one=fraction(sum(t['at_least_one'] for t in tasks),len(tasks)),
        all_attempts=fraction(sum(t['all_attempts'] for t in tasks),len(tasks)),
        complete_scored_tasks=sum(t['complete_scored_group'] for t in tasks),
        interpretation='Observed scheduled events; subset estimates require iid stationary trials within task; no population inference')


def finite_quantity(value):
    try:
        valid = type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError('invalid or out-of-range ledger quantity')
    return value


def cost_summary(trials):
    ledgers=[t['ledger'] for t in trials]
    for l in ledgers:
        for key in ('request_attempts','provider_tool_calls','executor_action_attempts'):
            if type(l[key]) is not int or l[key] < 0:
                raise ValueError('invalid ledger count')
        for key in ('model_cost','elapsed_local_seconds'):
            v=l[key]
            if v is None and key=='model_cost':
                continue
            finite_quantity(v)
    elapsed = known = 0
    for l in ledgers:
        elapsed = finite_quantity(elapsed + l['elapsed_local_seconds'])
        if l['model_cost'] is not None:
            known = finite_quantity(known + l['model_cost'])
    unknown=sum(l['model_cost'] is None for l in ledgers)
    return dict(request_attempts=sum(l['request_attempts'] for l in ledgers),
        provider_tool_calls=sum(l['provider_tool_calls'] for l in ledgers),
        executor_action_attempts=sum(l['executor_action_attempts'] for l in ledgers),
        elapsed_local_seconds=elapsed,
        unknown_cost_trials=unknown, model_cost=None if unknown else known,
        known_cost_subtotal=known)


def budget(ledger, cents=120, request_price_cents=2, new_task_setup_cents=6):
    for v in (cents,request_price_cents,new_task_setup_cents):
        if type(v) is not int or v<0:
            raise ValueError('budget exact nonnegative integers required')
    requests=ledger['request_attempts']
    if type(requests) is not int or requests<=0 or request_price_cents==0:
        raise ValueError('positive request count and hypothetical price required')
    unit=requests*request_price_cents
    return dict(basis='Hypothetical cents per request, NOT provider token pricing or measured bill',
        fixed_budget_cents=cents, repeat_unit_cents=unit,new_task_unit_cents=unit+new_task_setup_cents,
        extra_repeats=cents//unit, new_independent_tasks=cents//(unit+new_task_setup_cents),
        repeat_unspent_cents=cents%unit,new_task_unspent_cents=cents%(unit+new_task_setup_cents))


def planning_variance(counts, between=0.04, within=0.16):
    """Hypothetical variance for independent tasks and stationary iid trials.

    Assumes common within-task variance and allocation fixed before outcomes.
    For fixed heterogeneous task variances W_i, the conditional within-component
    is sum(W_i / counts[i]) / T**2, not their scalar average times sum(1/r_i)/T**2.
    This helper does not estimate empirical variance or model adaptive allocation.
    """
    if type(counts) is not list or not counts:
        raise ValueError('nonempty repeat allocation required')
    for count in counts:
        positive(count, 'allocation')
    for value in (between,within):
        if type(value) not in (int,float) or not math.isfinite(value) or value<0:
            raise ValueError('finite nonnegative variance required')
    tasks=len(counts)
    return between/tasks+within*sum(1/count for count in counts)/(tasks*tasks)


def run(repeats=3):
    positive(repeats,'repeats')
    path=Path('chapter03/repaired.jsonl'); rows=load_rows(path)
    revision=hashlib.sha256(path.read_bytes()).hexdigest()
    schedule=[]; records=[]; trials=[]
    for row in rows:
        for attempt in range(1,repeats+1):
            trial=execute(row,mode='fixture')
            trial['trial_id']=row['case_id']+':'+str(attempt)
            record=project(trial,row,revision,'chapter05-direct-fixture',trial['trial_id'])
            schedule.append({**{x:record[x] for x in ('dataset_revision','task_id','trial_id','agent_revision','family','variant_group')},'attempt':attempt})
            records.append(record); trials.append(trial)
    return dict(scope='Actual bounded deterministic fixture executions, not stochastic model performance',
        schedule=schedule,trials=trials,analysis=analyse(schedule,records,repeats,repeats),
        ledger=cost_summary(trials),budget=budget(trials[0]['ledger']))


def exercise():
    # Generated statuses test the analysis only, never measured model performance.
    from chapter08.fixtures import fixture
    patterns=[['FAIL','PASS','PASS'],['PASS','PASS','PASS'],['FAIL','FAIL','FAIL']]
    schedule=[]; records=[]
    for i, pattern in enumerate(patterns):
        for j,status in enumerate(pattern,1):
            trial,row=fixture(None if status=='PASS' else [['A100',4199]])
            row['case_id']='exercise-'+str(i); trial['trial_id']=row['case_id']+':'+str(j)
            rec=project(trial,row,'synthetic-analysis-v1','authored-pattern',trial['trial_id'])
            rec['diagnostics']['communication']=dict(review_status='reviewed',rating=5,provenance='authored, not human')
            schedule.append({**{x:rec[x] for x in ('dataset_revision','task_id','trial_id','agent_revision','family','variant_group')},'attempt':j})
            records.append(rec)
    return schedule,records


def main():
    p=argparse.ArgumentParser(); p.add_argument('mode',choices=['run','failure','repair'])
    a=p.parse_args()
    if a.mode=='run':
        report=run()
    else:
        report=analyse(*exercise())
        report['scope']='Generated outcomes: tests of analysis, not measured model performance'
        if a.mode=='failure':
            report['mislabelled_first_attempt']=deepcopy(report['at_least_one'])
            report['detected']='BEST_OF_MANY_IS_NOT_FIRST_ATTEMPT'
    out=Path('chapter12/output'); out.mkdir(exist_ok=True,parents=True)
    (out/(a.mode+'.json')).write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(report,allow_nan=False))
    return 1 if a.mode=='failure' else 0

if __name__=='__main__':
    raise SystemExit(main())

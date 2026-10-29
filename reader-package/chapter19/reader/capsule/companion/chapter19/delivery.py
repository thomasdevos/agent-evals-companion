"""Offline delivery evidence consumer; no deployment or business action."""
import argparse
import hashlib
import json
from pathlib import Path
from copy import deepcopy
from chapter08.fixtures import fixture
from chapter08.graders import project, aggregate, KEYS
from chapter13.compare import workflow, card

VERSION = 'chapter18-delivery-v1'
SCENARIOS = ('pass', 'task-failure', 'grader-failure', 'outage', 'missing-job', 'missing-test', 'inconclusive')
ROOT = Path(__file__).resolve().parents[1]

def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False)

def digest(x):
    return hashlib.sha256(canonical(x).encode()).hexdigest()

def bindings():
    paths = ['chapter19/delivery.py', 'chapter19/ci.json', 'chapter08/graders.py', 'chapter08/fixtures.py', 'chapter02/task_lab.py', 'chapter02/cards/full.json', 'chapter13/compare.py', 'chapter12/repeated.py', 'chapter18/coding.py', 'chapter18/protected.py', 'first_eval.py']
    return {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}

def policy():
    # New values every call. No returned packet can mutate the trusted policy.
    return dict(schema=VERSION, candidate='scripted-support-v1', dataset='delivery-fixture-v1',
                grader='scorecard-v1', jobs=['code', 'support'],
                budget=dict(provider_calls=0, max_scheduled_trials=3),
                comparison_required=False, business_approval='REQUIRED_SEPARATELY')

def inputs(scenario):
    schedule, records = [], []
    for i in range(3):
        trial, row = fixture([['A100',4199]] if scenario == 'task-failure' and i == 1 else None)
        row['case_id'] = 'delivery-task-'+str(i)
        trial['trial_id'] = 'attempt-1'
        if i == 1 and scenario in ('outage', 'grader-failure'):
            trial.update(status='INFRA_ERROR' if scenario == 'outage' else 'GRADER_ERROR',
                         checks=None, checks_role='unavailable', scoring_eligible=False,
                         error='mock API unavailable' if scenario == 'outage' else 'mock grader unavailable')
        record = project(trial, row, policy()['dataset'], policy()['candidate'], 'fixture:'+str(i))
        schedule.append({k:record[k] for k in (*KEYS, 'family', 'variant_group')})
        if not (scenario == 'missing-test' and i == 1): records.append(record)
    return schedule, records

def code_check():
    from chapter18.coding import execute
    result = execute('repair')
    return result

def collect(scenario, code=None):
    if scenario not in SCENARIOS: raise ValueError('scenario')
    schedule, records = inputs(scenario)
    comparison = workflow('repair', card()) if scenario == 'inconclusive' else None
    jobs = ['code', 'support'] if scenario != 'missing-job' else ['support']
    return dict(schema=VERSION, scenario=scenario, policy=policy(), bindings=bindings(),
                schedule=schedule, records=records, scorecard=aggregate(schedule, records),
                jobs=jobs, code=code_check() if code is None else deepcopy(code), comparison=comparison,
                cost=dict(provider_calls=0, model_cost=None, basis='offline; live cost unmeasured'),
                human_approval=False)

def seal(body): return dict(body=body, sha256=digest(body))

def validate(packet):
    if type(packet) is not dict or set(packet) != {'body','sha256'}: raise ValueError('packet fields')
    body=packet['body']
    if type(body) is not dict or packet['sha256'] != digest(body): raise ValueError('digest')
    scenario=body.get('scenario')
    if type(scenario) is not str or scenario not in SCENARIOS: raise ValueError('scenario')
    # Replay this authored deterministic corpus. Typed canonical comparison rejects 0/1 booleans.
    expected=collect(scenario)
    # The repair control emits deterministic JSON without temporary paths.
    from chapter18.coding import validate_rows
    code=body.get('code')
    if type(code) is not dict or set(code) != set(expected['code']): raise ValueError('code shape')
    validate_rows(code['rows'])
    validate_rows(json.loads(code['process']['stdout']))
    if canonical(code) != canonical(expected['code']): raise ValueError('code contradiction')
    if canonical(body) != canonical(expected): raise ValueError('evidence mismatch')
    return body

def decide_body(body):
    score=body['scorecard']
    if body['jobs'] != policy()['jobs']: return 'FAIL', 'REQUIRED_JOB_MISSING'
    if body['code']['status'] != 'PASS': return 'FAIL', 'CODE_CHECK_FAILURE'
    if score['failed']: return 'FAIL', 'TASK_FAILURE'
    if score['status_counts'].get('GRADER_ERROR',0): return 'FAIL', 'GRADER_FAILURE'
    if score['errors'] or score['missing']: return 'DEFER', 'INCOMPLETE_EVIDENCE'
    if body['comparison'] is not None and body['comparison']['decision']=='DESCRIPTIVE_INCONCLUSIVE':
        return 'DEFER', 'COMPARISON_INCONCLUSIVE'
    return 'PASS', 'TECHNICAL_EVIDENCE_ONLY'

def decide(packet): return decide_body(validate(packet))

def runtime(packet):
    decision,reason=decide(packet)
    return dict(mode='READ_ONLY_REVIEW' if decision=='PASS' else 'HOLD', reason=reason,
                may_refund=False, may_deploy=False, business_approval='REQUIRED_SEPARATELY')

def validate_ci(config):
    if type(config) is not dict or set(config) != {'schema','required_jobs','entrypoint','fast','scheduled','live','hosted_execution'}:
        raise ValueError('CI fields')
    if config['schema'] != 'chapter18-local-ci-v2' or config['required_jobs'] != ['code','support']:
        raise ValueError('CI required jobs')
    if config['entrypoint'] != ['-m','chapter19.delivery','ci'] or config['hosted_execution'] != 'NOT_RUN':
        raise ValueError('CI entrypoint')
    if canonical(config['live']) != canonical(dict(enabled=False,authorisation=None,budget=None)):
        raise ValueError('live execution unsupported; no provider called')
    for name,jobs,slots in [('fast',['code','support'],3),('scheduled',['code','support','comparison'],6)]:
        lane=config[name]
        if type(lane) is not dict or set(lane) != {'enabled','trigger','jobs','provider_calls','max_scheduled_trials','scenario_matrix'}:
            raise ValueError('CI lane fields')
        if type(lane['enabled']) is not bool or (name=='fast' and not lane['enabled']): raise ValueError('CI enabled')
        if type(lane['trigger']) is not str or not lane['trigger']: raise ValueError('descriptive trigger')
        if lane['jobs'] != jobs: raise ValueError('CI lane required jobs')
        if type(lane['provider_calls']) is not int or lane['provider_calls'] != 0: raise ValueError('offline call budget')
        if type(lane['max_scheduled_trials']) is not int or lane['max_scheduled_trials'] < slots: raise ValueError('trial budget')
        if type(lane['scenario_matrix']) is not bool or lane['scenario_matrix'] is not False: raise ValueError('matrix is a separate demonstration')
    return deepcopy(config)

def run_ci(config, lane):
    config=validate_ci(config)
    if lane not in ('fast','scheduled'): raise ValueError('unsupported lane')
    selected=config[lane]
    result=dict(lane=lane,executed_jobs=[],scheduled_trials=0,provider_calls=0,model_cost=None,
                decision='DEFER',exit=2,may_deploy=False,may_refund=False,observations=[])
    if not selected['enabled']: return result
    # Dispatch is narrower than the seven-case teaching matrix. No network adapter exists.
    scenarios=['pass'] if lane=='fast' else ['pass','inconclusive']
    for scenario in scenarios:
        body=collect(scenario)
        decision,reason=decide_body(body)
        result['observations'].append(dict(scenario=scenario,decision=decision,reason=reason))
        result['scheduled_trials'] += len(body['schedule'])
        for job in body['jobs'] + (['comparison'] if body['comparison'] is not None else []):
            if job not in result['executed_jobs']: result['executed_jobs'].append(job)
    decisions=[r['decision'] for r in result['observations']]
    if result['executed_jobs'] != selected['jobs'] or result['scheduled_trials'] > selected['max_scheduled_trials']:
        result['decision']='FAIL'
    else: result['decision']='FAIL' if 'FAIL' in decisions else 'DEFER' if 'DEFER' in decisions else 'PASS'
    result['exit']={'PASS':0,'FAIL':1,'DEFER':2}[result['decision']]
    return result

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('mode',choices=['failure','repair','matrix','ci'])
    parser.add_argument('--lane', choices=['fast','scheduled'], default='fast')
    args=parser.parse_args(); out=ROOT/'chapter19/output'; out.mkdir(exist_ok=True)
    if args.mode=='ci':
        result=run_ci(json.loads((ROOT/'chapter19/ci.json').read_text()),args.lane)
        (out/('ci-'+args.lane+'.json')).write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result)); return result['exit']
    scenarios=('outage',) if args.mode=='failure' else SCENARIOS
    matrix=[]
    for scenario in scenarios:
        packet=seal(collect(scenario)); decision,reason=decide(packet)
        (out/(scenario+'.json')).write_text(json.dumps(packet,indent=2)+'\n')
        score=packet['body']['scorecard']
        row=dict(scenario=scenario,decision=decision,reason=reason,scheduled=score['scheduled_trials'],
                 passed=score['passed'],errors=score['errors'],missing=score['missing'],
                 runtime=runtime(packet))
        if args.mode=='failure': row['naive_success']=all(r['result_status']=='PASS' for r in packet['body']['records'] if r['scoring_eligible'])
        matrix.append(row)
    (out/(args.mode+'.json')).write_text(json.dumps(matrix,indent=2)+'\n'); print(json.dumps(matrix))
    return 1 if args.mode=='failure' else 0

if __name__=='__main__': raise SystemExit(main())

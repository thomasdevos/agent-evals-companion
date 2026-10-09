"""Application-owned offline trace lab. No OTEL SDK and no network path."""
import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import sys
import time
from unittest.mock import patch

# Use --companion for a fresh, disposable copy of the existing companion.
ROOT = Path(__file__).resolve().parents[4] / 'companion'
if '--companion' in sys.argv:
    i = sys.argv.index('--companion')
    ROOT = Path(sys.argv[i + 1]).resolve()
    del sys.argv[i:i + 2]
sys.path.insert(0, str(ROOT))
from chapter02.task_lab import validate_card, repaired_grade, run_trial
from chapter03.dataset_lab import load_rows
from chapter05 import harness
from chapter07.replay import digest, load, save


def require(ok, message):
    if not ok:
        raise ValueError(message)


def emit(mode='repair'):
    """Capture real local harness execution with an authored wire transport."""
    row = load_rows(ROOT / 'chapter03/repaired.jsonl')[0]
    spans = []
    original = harness.FixtureTransport
    class Capture(original):
        def __call__(self, payload, timeout):
            start = time.monotonic_ns()
            response = super().__call__(payload, timeout)
            # Fixed teaching corpus is approved in full; arbitrary free text is
            # never copied through this projection into telemetry.
            outputs = [x for x in payload['input']
                       if x.get('type') == 'function_call_output']
            observed = [{ 'call_id': x['call_id'],
                          'events': json.loads(x['output'])} for x in outputs]
            if mode == 'failure':
                observed = None
            n = len(spans) + 1
            spans.append(dict(span_id=f'm{n}', parent_id='turn', kind='model_call',
                session_id='session-lab', trace_id='trace-lab', trial_id=row['case_id']+':1',
                requested_model_id=payload['model'], served_model_id=response.get('model'),
                prompt_version='chapter05-source-bound', tool_name=None,
                argument_hash=None, latency_ns=time.monotonic_ns()-start,
                tokens=None, cost=None, error_status=None,
                observed_tool_results=observed, response=deepcopy(response)))
            return response
    with patch.object(harness, 'FixtureTransport', Capture):
        result = harness.execute(row, mode='fixture')
    base = dict(session_id='session-lab', trace_id='trace-lab', trial_id=result['trial_id'],
        requested_model_id=None, served_model_id=None, prompt_version=None,
        tool_name=None, argument_hash=None, latency_ns=None, tokens=None,
        cost=None, error_status=None, observed_tool_results=None, response=None)
    root = dict(base, span_id='root', parent_id=None, kind='trace')
    turn = dict(base, span_id='turn', parent_id='root', kind='agent_turn')
    # Tool spans are post-run projections of executor attempts, not timing claims.
    tools=[]
    for i,e in enumerate(result['trace']):
        if e['kind'] in ('refund','ask','read','change_order'):
            tools.append(dict(base, span_id=f't{i}', parent_id='turn', kind='tool_call',
                tool_name=e['kind'], argument_hash=digest(e)))
    return dict(schema='application-trace-v1', evidence_kind='authored offline transport',
        replayable=True, card=deepcopy(row['card']), evidence=result,
        spans=[root,turn]+spans+tools,
        source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
            for p in ['chapter02/task_lab.py','chapter02/task.schema.json',
                      'chapter03/dataset_lab.py','chapter05/harness.py','chapter07/replay.py']})


def display(bundle):
    """Ingestion projection for arbitrary input: retain only counts and enums."""
    # No raw values, IDs, hashes of low-entropy personal data or error strings.
    return dict(schema='trace-display-v1', replayable=False,
        span_count=len(bundle['spans']) if type(bundle.get('spans')) is list else None,
        evidence_kind='redacted display', outcome='unknown')


def validate(b):
    require(type(b) is dict and b.get('schema')=='application-trace-v1', 'trace schema')
    require(b.get('replayable') is True, 'redacted evidence is not replayable')
    require(b.get('evidence_kind')=='authored offline transport', 'evidence class')
    validate_card(b['card'])
    require(type(b['spans']) is list and bool(b['spans']), 'spans required')
    expected_keys=set(dict(span_id=0,parent_id=0,kind=0,session_id=0,trace_id=0,trial_id=0,
        requested_model_id=0,served_model_id=0,prompt_version=0,tool_name=0,argument_hash=0,
        latency_ns=0,tokens=0,cost=0,error_status=0,observed_tool_results=0,response=0))
    ids={}
    for s in b['spans']:
        require(type(s) is dict and set(s)==expected_keys, 'span shape')
        for k in ('span_id','session_id','trace_id','trial_id','kind'):
            require(type(s[k]) is str and bool(s[k]), 'span identity type')
        require(s['span_id'] not in ids, 'duplicate span')
        ids[s['span_id']]=s
        require(s['kind'] in ('trace','agent_turn','model_call','tool_call'), 'unknown span kind')
        require(s['parent_id'] is None or type(s['parent_id']) is str, 'parent type')
        for k in ('requested_model_id','served_model_id','prompt_version','tool_name','argument_hash','error_status'):
            require(s[k] is None or (type(s[k]) is str and bool(s[k])), k+' type')
        for k in ('latency_ns','tokens'):
            require(s[k] is None or (type(s[k]) is int and s[k]>=0), k+' type')
        if s['kind']=='model_call':
            require(type(s['latency_ns']) is int, 'model duration required')
        else:
            require(s['latency_ns'] is None, 'unmeasured duration must be null')
        require(s['cost'] is None or (type(s['cost']) in (int,float) and math.isfinite(s['cost']) and s['cost']>=0), 'cost type')
    require([s['span_id'] for s in b['spans'] if s['parent_id'] is None]==['root'], 'one root required')
    for s in b['spans']:
        seen=set(); node=s
        while node['parent_id'] is not None:
            require(node['span_id'] not in seen, 'parent cycle')
            seen.add(node['span_id'])
            require(node['parent_id'] in ids, 'missing parent')
            node=ids[node['parent_id']]
        require(s['trace_id']=='trace-lab' and s['session_id']=='session-lab' and
                s['trial_id']==b['evidence']['trial_id'], 'foreign identity')
    require(ids['root']['kind']=='trace' and ids.get('turn',{}).get('kind')=='agent_turn', 'root/turn kinds')
    require(ids['turn']['parent_id']=='root', 'turn parent')
    for s in b['spans']:
        if s['kind'] in ('model_call','tool_call'):
            require(s['parent_id']=='turn', 'operation parent')
    models=[s for s in b['spans'] if s['kind']=='model_call']
    require(bool(models), 'model observations required')
    for s in models:
        require(type(s['observed_tool_results']) is list, 'missing observed tool result')
        require(type(s['response']) is dict, 'response type')
    # Independently rerun recorded candidate actions in the unchanged local executor.
    # This validates evidence shape/semantics without trusting producer PASS flags.
    e=b['evidence']
    require(type(e) is dict and e.get('status') in ('PASS','FAIL'), 'unknown outcome')
    actions=[{k:v for k,v in x.items() if k!='known_order'}
             for x in e['trace'] if x['kind']!='user_reply']
    queue=iter(deepcopy(actions))
    replay=run_trial(b['card'], agent=lambda view: next(queue))
    for k in ('before','after','trace','terminal','checks','status'):
        require(digest(replay[k])==digest(e[k]), 'evidence mismatch: '+k)
    require(e['trial_id']==b['card']['id']+':1', 'task/trial mismatch')
    # Recreate exact wire observations using the real Chapter 5 adapter. The
    # authored transport is isolated, so no provider or external effect is possible.
    pristine=emit('repair')
    require(digest(b['card'])==digest(pristine['card']), 'unsupported task mapping')
    require(b['source_hashes']==pristine['source_hashes'], 'source changed')
    # Bind ALL retained evidence to the same bounded capture as the wire spans.
    # Canonical JSON distinguishes bool/int and rejects extra keys at any depth.
    # Only this measured local duration varies between authored executions.
    actual_e=deepcopy(e); expected_e=deepcopy(pristine['evidence'])
    elapsed=actual_e['ledger']['elapsed_local_seconds']
    require(type(elapsed) is float and math.isfinite(elapsed) and elapsed>=0,
            'elapsed_local_seconds type')
    # Sequential calls execute inside the enclosing harness measurement.
    # Compare integer nanoseconds with the ceiling of the recorded float's
    # exact value in nanoseconds. This permits less than one ns of unit-rounding,
    # not a percentage slack or equality with a fresh run's variable timings.
    numerator, denominator=elapsed.as_integer_ratio()
    enclosing_ns=(numerator*1_000_000_000+denominator-1)//denominator
    require(sum(s['latency_ns'] for s in models)<=enclosing_ns,
            'serial model durations exceed enclosing elapsed')
    actual_e['ledger'].pop('elapsed_local_seconds')
    expected_e['ledger'].pop('elapsed_local_seconds')
    require(digest(actual_e)==digest(expected_e), 'unsupported evidence capture')
    require(len(b['spans'])==len(pristine['spans']), 'span schedule mismatch')
    for actual, expected in zip(b['spans'],pristine['spans']):
        a=deepcopy(actual); x=deepcopy(expected)
        # Timing is measured per capture; all other lab fields are fixed.
        a.pop('latency_ns'); x.pop('latency_ns')
        require(digest(a)==digest(x), 'observation or span mismatch')
    return b


def convert(b):
    validate(b)
    e=b['evidence']
    checks=repaired_grade(e['before'],e['after'],e['trace'],e['terminal'],b['card'])
    return dict(schema='trace-task-evidence-v1', card=deepcopy(b['card']),
        evidence=deepcopy(e), checks=checks,
        status='PASS' if all(checks.values()) else 'FAIL',
        provenance=dict(source_trace_sha256=digest(b),
            operation='validated authored trace conversion',
            replay_bundle_compatible=False, provider_replayable=False,
            task_replayable=True, outcome_observed=True))


def main():
    p=argparse.ArgumentParser()
    p.add_argument('command',choices=['failure','repair','convert','display'])
    p.add_argument('--input',default='trace.json')
    p.add_argument('--output',default='trace.json')
    a=p.parse_args()
    try:
        if a.command in ('failure','repair'):
            value=emit(a.command); save(a.output,value)
            print(json.dumps({'written':a.output,'span_count':len(value['spans'])}))
        elif a.command=='display':
            value=display(load(a.input)); save(a.output,value); print(json.dumps(value))
        else:
            value=convert(load(a.input)); save(a.output,value)
            print(json.dumps({'status':value['status'],'task_replayable':True}))
    except (ValueError,KeyError,TypeError,StopIteration) as exc:
        print(json.dumps({'status':'UNASSESSABLE','reason':str(exc)})); return 2
    return 0

if __name__=='__main__':
    raise SystemExit(main())

"""Offline evidence replay, not agent invocation. Standard-library teaching checkpoint."""
import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import platform
import sqlite3
from unittest.mock import patch
from chapter02.task_lab import repaired_grade, CHECKS, validate_card
from chapter03.dataset_lab import load_rows
from chapter05.harness import run, execute, TOOLS

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ['first_eval.py', 'chapter02/task_lab.py', 'chapter02/task.schema.json',
           'chapter03/dataset_lab.py', 'chapter05/harness.py', 'chapter07/replay.py']
NORMALISATION = ['trials[*].ledger.elapsed_local_seconds']

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()

def filehash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def load(path):
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                raise ValueError('duplicate JSON key: '+k)
            result[k] = v
        return result
    try:
        value = json.loads(Path(path).read_text(), object_pairs_hook=pairs,
                           parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    except RecursionError as exc:
        raise ValueError('JSON nesting exceeds decoder limit') from exc
    # Bound later recursive copying, hashing and comparison as well as decoding.
    pending = [(value, 0)]
    while pending:
        item, depth = pending.pop()
        if depth > 128:
            raise ValueError('JSON nesting exceeds checkpoint limit (128)')
        if type(item) is dict:
            pending.extend((v, depth+1) for v in item.values())
        elif type(item) is list:
            pending.extend((v, depth+1) for v in item)
    return value

def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n')

def normalise(report):
    result = deepcopy(report)
    for trial in result['trials']:
        trial['ledger'].pop('elapsed_local_seconds')
    return result

def grader(revision):
    if revision not in ('state-v1', 'omit-ledger-demo'):
        raise ValueError('unknown grader revision')
    return dict(revision=revision, source_sha256=filehash(ROOT/'chapter02/task_lab.py'),
                wrapper_sha256=filehash(__file__))

def score(report, rows, revision):
    grader(revision)
    results = []
    for trial, row in zip(report['trials'], rows):
        checks = trial['checks']
        status = trial['status']
        if trial['scoring_eligible']:
            checks = repaired_grade(trial['before'], trial['after'], trial['trace'],
                                    trial['terminal'], row['card'])
            if revision == 'omit-ledger-demo':
                checks.pop('exact_refund_ledger')
            status = 'PASS' if all(checks.values()) else 'FAIL'
        results.append(dict(trial_id=trial['trial_id'], status=status, checks=checks,
                            scoring_eligible=trial['scoring_eligible'], checks_role=trial['checks_role']))
    return results

def seal(bundle):
    m = bundle['manifest']
    m['evidence_sha256'] = digest(bundle['evidence'])
    m['report_sha256'] = digest(bundle['report'])
    m.pop('report_id', None)
    m['report_id'] = digest(m)
    return bundle

def build():
    dataset = ROOT/'chapter03/repaired.jsonl'
    rows = load_rows(dataset)
    report = run(dataset, mode='script')
    def noop(view):
        return dict(kind='finish', status='completed', reason='full_refund',
                    text='Refund completed. Contact synthetic.person@example.invalid')
    with patch('chapter05.harness.scripted_agent', return_value=noop):
        report['trials'][0] = execute(rows[0], mode='script')
    report['counts']['PASS'] -= 1
    report['counts']['FAIL'] = 1
    manifest = dict(schema='chapter06-manifest-v1', evidence_kind='synthetic teaching fixture',
        model=dict(provider=None, id='scripted-with-first-noop', measured=False),
        configuration=dict(mode='script', retry=False, seed=None, temperature=None),
        prompt=dict(kind='no model prompt; scripted callback', source_sha256=filehash(__file__)),
        grader=grader('state-v1'), task_data_sha256=filehash(dataset),
        tools=dict(catalogue_sha256=digest(TOOLS), executor_sha256=filehash(ROOT/'chapter02/task_lab.py')),
        environment=dict(python=platform.python_version(), sqlite=sqlite3.sqlite_version,
                         system=platform.system(), machine=platform.machine()),
        budget=report['policy'], sources={p:filehash(ROOT/p) for p in SOURCES},
        normalisation=NORMALISATION, provenance=dict(operation='capture', parent_report_id=None))
    return seal(dict(manifest=manifest, evidence=dict(rows=rows, run=report),
                     report=score(report, rows, 'state-v1')))

def validate_manifest(m, run_):
    # A narrow checkpoint contract, not a general manifest framework.
    required = {'schema', 'evidence_kind', 'model', 'configuration', 'prompt', 'grader',
                'task_data_sha256', 'tools', 'environment', 'budget', 'sources',
                'normalisation', 'provenance', 'evidence_sha256', 'report_sha256', 'report_id'}
    if type(m) is not dict or set(m) != required:
        raise ValueError('manifest required fields')
    def exact(actual, expected, label):
        # JSON equality alone would equate False with 0 and True with 1.
        if type(actual) is not type(expected) or digest(actual) != digest(expected):
            raise ValueError(label+' mismatch')
    exact(m['model'], dict(provider=None, id='scripted-with-first-noop', measured=False), 'model')
    exact(m['configuration'], dict(mode='script', retry=False, seed=None, temperature=None), 'configuration')
    exact(m['prompt'], dict(kind='no model prompt; scripted callback', source_sha256=filehash(__file__)), 'prompt')
    exact(m['tools'], dict(catalogue_sha256=digest(TOOLS), executor_sha256=filehash(ROOT/'chapter02/task_lab.py')), 'tools')
    exact(m['sources'], {p:filehash(ROOT/p) for p in SOURCES}, 'source mismatch')
    exact(m['evidence_kind'], 'synthetic teaching fixture', 'evidence kind')
    exact(m['normalisation'], NORMALISATION, 'normalisation')
    policy = dict(max_requests_per_trial=8, max_actions_per_trial=6,
                  max_output_tokens_per_request=512, cooperative_seconds=30,
                  transport_attempts_per_request=1)
    exact(m['budget'], policy, 'budget')
    exact(run_['policy'], policy, 'run policy')
    if run_['mode'] != 'script' or run_['baseline'] != 'direct':
        raise ValueError('run configuration mismatch')
    env = m['environment']
    if type(env) is not dict or set(env) != {'python','sqlite','system','machine'} or any(type(v) is not str or not v for v in env.values()):
        raise ValueError('environment shape')
    def sha(value):
        return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)
    for key in ('task_data_sha256','evidence_sha256','report_sha256','report_id'):
        if not sha(m[key]): raise ValueError('manifest digest shape')
    g = m['grader']
    if type(g) is not dict or set(g) != {'revision','source_sha256','wrapper_sha256'} or type(g['revision']) is not str or not sha(g['source_sha256']) or not sha(g['wrapper_sha256']):
        raise ValueError('grader identity shape')
    provenance = m['provenance']
    if type(provenance) is not dict or set(provenance) != {'operation','parent_report_id'}:
        raise ValueError('provenance shape')
    operation, parent = provenance['operation'], provenance['parent_report_id']
    if not ((operation == 'capture' and parent is None and g['revision'] == 'state-v1') or
            (operation == 'regrade' and sha(parent) and parent != m['report_id'])):
        raise ValueError('provenance operation/parent mismatch')


def same_json(actual, expected):
    """Decoded JSON identity, without Python's bool/int/float equivalence."""
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return actual.keys() == expected.keys() and all(same_json(actual[k], v) for k, v in expected.items())
    if type(expected) is list:
        return len(actual) == len(expected) and all(same_json(a, b) for a, b in zip(actual, expected))
    return actual == expected


def validate_ledger(trial):
    ledger = trial['ledger']
    counters = ('agent_invocations', 'request_attempts', 'provider_tool_calls', 'executor_action_attempts')
    fields = set(counters) | {'provider_call_observation', 'usage', 'model_cost', 'cost_basis', 'elapsed_local_seconds'}
    if type(ledger) is not dict or set(ledger) != fields:
        raise ValueError('ledger required fields')
    if any(type(ledger[k]) is not int or ledger[k] < 0 for k in counters):
        raise ValueError('ledger counters must be nonnegative integers')
    def nonnegative_number(value):
        return type(value) in (int, float) and (type(value) is int or math.isfinite(value)) and value >= 0
    if not nonnegative_number(ledger['elapsed_local_seconds']):
        raise ValueError('elapsed time must be finite and nonnegative')
    if ledger['model_cost'] is not None and not nonnegative_number(ledger['model_cost']):
        raise ValueError('model cost must be unknown or finite and nonnegative')
    if ledger['provider_call_observation'] not in ('complete', 'partial_or_unknown'):
        raise ValueError('provider observation vocabulary')
    if type(ledger['cost_basis']) is not str or not ledger['cost_basis']:
        raise ValueError('cost basis must be a nonempty string')
    if type(ledger['usage']) is not list or any(v is not None and type(v) is not dict for v in ledger['usage']):
        raise ValueError('usage must be a list of records or unknown entries')
    trace = trial['trace']
    if type(trace) is not list or any(type(e) is not dict or type(e.get('kind')) is not str for e in trace):
        raise ValueError('trace event shape')
    attempts = sum(e['kind'] in ('ask', 'read', 'refund', 'change_order') for e in trace)
    if ledger['executor_action_attempts'] != attempts:
        raise ValueError('executor attempts disagree with retained trace')
    # No provider usage or cost is inferred from absent observations.


def verify(bundle, revision=None):
    if set(bundle) != {'manifest', 'evidence', 'report'}:
        raise ValueError('bundle shape')
    m = bundle['manifest']; e = bundle['evidence']; run_ = e['run']; rows = e['rows']
    validate_manifest(m, run_)
    if m['schema'] != 'chapter06-manifest-v1' or run_['schema'] != 'harness-run-v2':
        raise ValueError('unsupported schema')
    expected = deepcopy(m); identity = expected.pop('report_id')
    if digest(expected) != identity:
        raise ValueError('manifest identity mismatch')
    if digest(e) != m['evidence_sha256'] or digest(bundle['report']) != m['report_sha256']:
        raise ValueError('artifact digest mismatch')
    if m['normalisation'] != NORMALISATION:
        raise ValueError('normalisation mismatch')
    if m['sources'] != {p:filehash(ROOT/p) for p in SOURCES}:
        raise ValueError('source mismatch; restore checkpoint before replay')
    if m['configuration'] != dict(mode='script', retry=False, seed=None, temperature=None):
        raise ValueError('configuration mismatch')
    if m['budget'] != run_['policy'] or m['task_data_sha256'] != run_['dataset_sha256']:
        raise ValueError('run configuration mismatch')
    actual_rows = load_rows(ROOT/'chapter03/repaired.jsonl')
    if type(rows) is not list:
        raise ValueError('retained rows must be a list')
    for row in rows:
        validate_card(row['card'])
    if not same_json(rows, actual_rows) or m['task_data_sha256'] != filehash(ROOT/'chapter03/repaired.jsonl'):
        raise ValueError('task data mismatch')
    if any(type(run_[k]) is not int for k in ('scheduled_trials','reported_trials')) or len(rows) != len(run_['trials']) or len(rows) != run_['scheduled_trials'] or len(rows) != run_['reported_trials']:
        raise ValueError('incomplete schedule')
    counts = {}
    for row, t in zip(rows, run_['trials']):
        validate_ledger(t)
        if t['status'] not in ('PASS','FAIL','INVALID_TASK','AGENT_ERROR','INFRA_ERROR','GRADER_ERROR'):
            raise ValueError('unsupported original status')
        if t['trial_id'] != row['case_id']+':1':
            raise ValueError('trial identity mismatch')
        eligible = t['status'] in ('PASS', 'FAIL')
        role = 'unavailable' if t['checks'] is None else 'scoring' if eligible else 'diagnostic'
        if t['scoring_eligible'] is not eligible or t['checks_role'] != role:
            raise ValueError('scoring role mismatch')
        expected_counts = dict(passed=int(t['status']=='PASS'), failed=int(t['status']=='FAIL'), errors=int(not eligible))
        if any(type(t[k]) is not int or t[k] != value for k,value in expected_counts.items()):
            raise ValueError('original row counts mismatch')
        if eligible:
            original = repaired_grade(t['before'], t['after'], t['trace'], t['terminal'], row['card'])
            if digest(t['checks']) != digest(original) or t['status'] != ('PASS' if all(original.values()) else 'FAIL'):
                raise ValueError('original state-v1 checks/status mismatch')
        counts[t['status']] = counts.get(t['status'], 0)+1
    if type(run_['counts']) is not dict or any(type(v) is not int for v in run_['counts'].values()) or counts != run_['counts']:
        raise ValueError('counts mismatch')
    rev = revision or m['grader']['revision']
    if grader(rev) != m['grader']:
        raise ValueError('grader identity mismatch; use regrade to derive a new report')
    if type(bundle['report']) is not list:
        raise ValueError('derived report must be a list')
    for result in bundle['report']:
        checks = result['checks']
        if checks is not None and (type(checks) is not dict or any(type(v) is not bool for v in checks.values())):
            raise ValueError('derived checks must be booleans or unavailable')
    if not same_json(score(run_, rows, rev), bundle['report']):
        raise ValueError('stored score mismatch')
    return bundle

def replay(bundle, revision=None):
    verify(bundle, revision)
    return dict(report_id=bundle['manifest']['report_id'], operation='stored-evidence replay',
                normalised_evidence_sha256=digest(normalise(bundle['evidence']['run'])),
                report=bundle['report'])

def regrade(bundle, revision):
    verify(bundle)
    new = deepcopy(bundle)
    new['manifest']['grader'] = grader(revision)
    new['manifest']['provenance'] = dict(operation='regrade', parent_report_id=bundle['manifest']['report_id'])
    new['report'] = score(new['evidence']['run'], new['evidence']['rows'], revision)
    return seal(new)

def differences(a, b, path=''):
    if type(a) is dict and type(b) is dict:
        result = []
        for key in sorted(set(a)|set(b)):
            p = path+'/'+key.replace('~','~0').replace('/','~1')
            if key not in a or key not in b:
                result.append(dict(path=p, before=a.get(key), after=b.get(key),
                                   change='added' if key not in a else 'removed'))
            else:
                result.extend(differences(a[key], b[key], p))
        return result
    if type(a) != type(b) or a != b:
        return [dict(path=path, before=a, after=b, change='modified')]
    return []

def inspect(bundle):
    verify(bundle)
    t = bundle['evidence']['run']['trials'][0]
    # Allowlist projection. Free text is omitted, not rewritten in the authoritative bundle.
    return dict(schema='chapter06-display-v1', replayable=False,
        source_report_id=bundle['manifest']['report_id'], trial_id=t['trial_id'],
        grading_provenance=dict(original_revision='state-v1', derived_revision=bundle['manifest']['grader']['revision'], display_checks='original'),
        status=t['status'], before_refunds=None if t['before'] is None else t['before']['refunds'],
        after_refunds=None if t['after'] is None else t['after']['refunds'],
        events=[{k:v for k,v in event.items() if k in ('kind','order_id','amount_pence','known_order','status','reason')}
                for event in t['trace']], failed_checks=None if t['checks'] is None else [k for k,v in t['checks'].items() if not v],
        executor_action_attempts=t['ledger']['executor_action_attempts'],
        adapter_error=t['adapter_error'], checks_role=t['checks_role'],
        redaction='free text excluded; synthetic order IDs and amounts retained')

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['capture','replay','regrade','inspect','diff'])
    p.add_argument('input', nargs='?', default='chapter06-run.json')
    p.add_argument('--other'); p.add_argument('--grader', default=None); p.add_argument('--output')
    a = p.parse_args()
    try:
        if a.command == 'capture':
            value = build()
        else:
            bundle = load(a.input)
            if a.command == 'replay': value = replay(bundle, a.grader)
            elif a.command == 'regrade': value = regrade(bundle, a.grader or 'state-v1')
            elif a.command == 'inspect': value = inspect(bundle)
            else:
                verify(bundle); other = load(a.other); verify(other)
                value = differences(bundle['manifest'], other['manifest'])
        if a.output: save(a.output, value)
        print(json.dumps(value if a.command in ('inspect','diff') else
                         dict(operation=a.command, report_id=value.get('report_id', value.get('manifest',{}).get('report_id'))),
                         indent=2, sort_keys=True))
        return 0
    except (ValueError, KeyError, TypeError, OSError, IndexError) as exc:
        print(json.dumps(dict(error=str(exc), operation=a.command)))
        return 2

if __name__ == '__main__':
    raise SystemExit(main())

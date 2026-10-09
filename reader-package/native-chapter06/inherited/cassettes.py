"""Authored offline envelopes, never model recordings. Standard library only."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Protocol

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'vendor'))
from chapter02.task_lab import run_trial as executor_run_trial, scripted_agent
from chapter03.dataset_lab import load_rows
from chapter05.harness import TOOLS
from wire_guard import strict_json

MODEL = 'authored-support-v1'
VERSION = 'provider-cassette-import-v2'

def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False)

def digest(x):
    return hashlib.sha256(canonical(x).encode()).hexdigest()

def versions():
    paths = ['cassettes.py', 'vendor/chapter02/task_lab.py', 'vendor/first_eval.py',
             'vendor/chapter03/dataset_lab.py', 'vendor/chapter03/repaired.jsonl',
             'vendor/chapter05/harness.py', 'vendor/wire_guard.py']
    paths += ['vendor/chapter02/task.schema.json', 'call.schema.json']
    return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths}

class ContractError(ValueError):
    pass

class Provider(Protocol):
    name: str
    def request(self, view: dict) -> dict: ...
    def send(self, payload: dict) -> dict: ...
    def parse_tools(self, response: dict) -> list: ...
    def parse_final(self, response: dict): ...
    def usage(self, response: dict) -> dict: ...
    def served_id(self, response: dict) -> str: ...

class Base:
    def __init__(self, transport):
        self.transport = transport
    def send(self, payload):
        return self.transport(deepcopy(payload))
    def served_id(self, response):
        if response.get('model') != MODEL:
            raise ContractError('served_model_mismatch')
        return response['model']
    def usage(self, response):
        value = response.get('usage')
        if value is None:
            return dict(state='unknown', input_tokens=None, output_tokens=None)
        if (type(value) is not dict or set(value) != {'input_tokens', 'output_tokens'} or
            any(type(v) is not int or v < 0 for v in value.values())):
            return dict(state='invalid', input_tokens=None, output_tokens=None)
        return dict(state='known_authored', **value)
    def validate(self, response):
        self.served_id(response)
        tools, final = self.parse_tools(response), self.parse_final(response)
        if bool(tools) == (final is not None):
            raise ContractError('mixed_or_empty_output')
        ids = set()
        for cid, action in tools:
            if type(cid) is not str or not cid or cid in ids:
                raise ContractError('duplicate_or_missing_call_id')
            ids.add(cid)
            spec = next((t for t in TOOLS if t['name'] == action.get('kind')), None)
            if spec is None or set(action) != {'kind', *spec['parameters']['properties']}:
                raise ContractError('tool_schema')
            for key, rule in spec['parameters']['properties'].items():
                if type(action[key]) is not (int if rule['type'] == 'integer' else str):
                    raise ContractError('tool_type')
                if type(action[key]) is str:
                    action[key].encode('utf-8')
                    if not action[key].strip():
                        raise ContractError('tool_text')
            if action['kind'] == 'refund' and not 0 < action['amount_pence'] <= 2**63 - 1:
                raise ContractError('refund_range')
        if final is not None:
            if (type(final) is not dict or set(final) != {'status','reason','text'} or
                final['status'] not in ('completed','refused') or
                any(type(final[k]) is not str or not final[k] for k in ('reason','text'))):
                raise ContractError('final_schema')
            for value in final.values():
                value.encode('utf-8')
                if not value.strip():
                    raise ContractError('final_text')
        return tools, final

class Responses(Base):
    name = 'openai-responses-shaped'
    def request(self, view):
        return dict(model=MODEL, input=[dict(role='user', content=canonical(view))],
                    tools=deepcopy(TOOLS), max_output_tokens=512, store=False)
    def items(self, response):
        if response.get('status') != 'completed' or type(response.get('output')) is not list:
            raise ContractError('noncompleted_envelope')
        if any(type(i) is not dict or i.get('type') not in ('function_call','message') for i in response['output']):
            raise ContractError('unsupported_content')
        return response['output']
    def parse_tools(self, response):
        return [(i['call_id'], dict(kind=i['name'], **strict_json(i['arguments'])))
                for i in self.items(response) if i['type'] == 'function_call']
    def parse_final(self, response):
        messages = [i for i in self.items(response) if i['type'] == 'message']
        if not messages:
            return None
        parts = [c for m in messages for c in m['content']]
        if any(c.get('type') != 'output_text' for c in parts):
            raise ContractError('unsupported_content')
        return strict_json(''.join(c['text'] for c in parts))

class Messages(Base):
    name = 'anthropic-messages-shaped'
    def request(self, view):
        return dict(model=MODEL, max_tokens=512,
                    messages=[dict(role='user', content=canonical(view))],
                    tools=[dict(name=t['name'], description=t['description'],
                                input_schema=deepcopy(t['parameters'])) for t in TOOLS])
    def items(self, response):
        if (response.get('type') != 'message' or response.get('role') != 'assistant' or
            response.get('stop_reason') not in ('tool_use','end_turn') or
            type(response.get('content')) is not list):
            raise ContractError('noncompleted_envelope')
        items = response['content']
        if any(type(i) is not dict or i.get('type') not in ('tool_use','text') for i in items):
            raise ContractError('unsupported_content')
        if (response['stop_reason'] == 'tool_use') != any(i['type'] == 'tool_use' for i in items):
            raise ContractError('stop_reason_mismatch')
        return items
    def parse_tools(self, response):
        return [(i['id'], dict(kind=i['name'], **i['input']))
                for i in self.items(response) if i['type'] == 'tool_use']
    def parse_final(self, response):
        parts = [i['text'] for i in self.items(response) if i['type'] == 'text']
        return strict_json(''.join(parts)) if parts else None

class Authored:
    """Provider-shaped envelopes from the existing public corrected script."""
    def __init__(self, provider, fault=None):
        self.provider, self.fault, self.calls = provider, fault, 0
    def __call__(self, payload):
        self.calls += 1
        if self.fault == 'transport':
            raise OSError('authored transport failure')
        text = payload['input'][0]['content'] if self.provider == 'responses' else payload['messages'][0]['content']
        view = strict_json(text)
        action = scripted_agent('corrected')(view)
        kind = action.pop('kind')
        cid = 'authored-' + str(self.calls)
        if self.fault == 'malformed' and kind == 'refund':
            action['amount_pence'] = True
        usage = None if self.fault == 'unknown' else dict(input_tokens=10, output_tokens=5)
        if self.provider == 'responses':
            output = ([dict(type='message', role='assistant', content=[dict(type='output_text', text=canonical(action))])]
                      if kind == 'finish' else [dict(type='function_call', call_id=cid, name=kind, arguments=canonical(action))])
            return dict(id='authored-response-'+str(self.calls), model=MODEL, status='completed', output=output, usage=usage)
        content = ([dict(type='text', text=canonical(action))] if kind == 'finish' else
                   [dict(type='tool_use', id=cid, name=kind, input=action)])
        return dict(id='authored-message-'+str(self.calls), type='message', role='assistant', model=MODEL,
                    stop_reason='end_turn' if kind == 'finish' else 'tool_use', stop_sequence=None, content=content, usage=usage)

class Agent:
    def __init__(self, provider, identity, records):
        self.provider, self.identity, self.records = provider, identity, records
        self.queue, self.seen, self.attempt = [], set(), 0
        self.failure = None
    def __call__(self, view):
        if self.queue:
            return self.queue.pop(0)
        if self.attempt >= 8:
            raise ContractError('request_cap')
        self.attempt += 1
        visible = {k: deepcopy(view[k]) for k in ('request','policy','orders','trace')}
        payload = self.provider.request(visible)
        row = dict(schema=VERSION, identity=deepcopy(self.identity), attempt=self.attempt,
                   provider=self.provider.name, provenance='authored-fixture-not-model-output',
                   timestamp=datetime.now(timezone.utc).isoformat(), request=payload,
                   request_sha256=digest(payload), requested_model=MODEL, served_model=None,
                   response=None, tools=[], usage=dict(state='unknown', input_tokens=None, output_tokens=None),
                   error=None, model_cost=None, price_source=None)
        self.records.append(row)
        start = time.monotonic()
        try:
            response = self.provider.send(payload)
            row['response'] = deepcopy(response)
            row['served_model'] = response.get('model') if type(response) is dict else None
            row['usage'] = self.provider.usage(response)
            tools, final = self.provider.validate(response)
            row['tools'] = strict_json(canonical(tools))
            if any(cid in self.seen for cid, _ in tools):
                raise ContractError('reused_call_id')
            self.seen.update(cid for cid, _ in tools)
            if final is not None:
                return dict(kind='finish', **final)
            self.queue = [action for _, action in tools]
            return self.queue.pop(0)
        except OSError:
            row['error'] = 'transport_error'
            self.failure = dict(kind='transport_error', attempt=self.attempt)
            raise ContractError('transport_error') from None
        except (ValueError, TypeError, KeyError, AttributeError):
            row['error'] = 'contract_error'
            self.failure = dict(kind='contract_error', attempt=self.attempt)
            raise ContractError('contract_error') from None
        finally:
            row['elapsed_local_seconds'] = time.monotonic() - start

class Replay:
    def __init__(self, rows):
        snapshot = deepcopy(rows)
        validate_imported(snapshot)
        self.rows, self.position = snapshot, 0
    def __call__(self, request):
        if self.position >= len(self.rows):
            raise ContractError('exhausted')
        row = self.rows[self.position]
        if row['request'] != request or row['request_sha256'] != digest(request):
            raise ContractError('request_mismatch')
        self.position += 1
        if row['error'] == 'transport_error':
            raise OSError('recorded transport error')
        return deepcopy(row['response'])
    def finish(self):
        if self.position != len(self.rows):
            raise ContractError('unused_records')

ADAPTERS = {'responses': Responses, 'messages': Messages}

def run_trial(card, agent_name='corrected', agent=None):
    """Classify adapter failures without modifying the inherited executor."""
    result = executor_run_trial(card, agent_name, agent)
    failure = deepcopy(getattr(agent, 'failure', None))
    result['adapter_failure'] = failure
    if result['status'] == 'AGENT_ERROR' and failure and failure['kind'] == 'transport_error':
        result['status'] = 'INFRA_ERROR'
    return result

def summarise(schedule, trials):
    counts = {s: 0 for s in ('PASS','FAIL','AGENT_ERROR','INFRA_ERROR','GRADER_ERROR','INVALID_TASK')}
    for trial in trials:
        counts[trial['status']] += 1
    eligible = counts['PASS'] + counts['FAIL']
    return dict(scheduled=len(schedule), reported=len(trials), status_counts=counts,
                scoring_eligible=eligible, unassessable=len(trials)-eligible,
                scored_pass_rate=counts['PASS']/eligible if eligible else None,
                scheduled_success_rate=counts['PASS']/len(schedule) if schedule else None)

def run(provider='messages', fault=None):
    dataset = ROOT / 'vendor/chapter03/repaired.jsonl'
    bindings = versions()
    records, trials, schedule = [], [], []
    for case in load_rows(dataset):
        for index in range(1, 6):
            identity = dict(experiment_id='authored-support-five-v1', case_id=case['case_id'],
                            trial_id=case['case_id']+':'+str(index), trial_index=index,
                            companion_version=VERSION, versions=bindings)
            schedule.append(identity)
            local = []
            agent = Agent(ADAPTERS[provider](Authored(provider, fault)), identity, local)
            result = run_trial(case['card'], 'provider-neutral', agent)
            replay = Replay(local)
            repeated = run_trial(case['card'], 'provider-neutral', Agent(ADAPTERS[provider](replay), identity, []))
            replay.finish()
            if result != repeated:
                raise ContractError('replay_outcome_mismatch')
            trials.append(dict(identity=identity, status=result['status'], checks=result['checks'], after=result['after'],
                               error=result['error'], adapter_failure=result['adapter_failure']))
            records.extend(local)
    manifest = dict(schema=VERSION, provider=ADAPTERS[provider].name,
                    provenance='authored-fixture-not-model-output', schedule=schedule,
                    versions=bindings, captured_at=datetime.now(timezone.utc).isoformat(),
                    record_count=len(records), records_sha256=digest(records), trials=trials)
    manifest['summary'] = summarise(schedule, trials)
    return manifest, records

def validate_identity(identity):
    if (type(identity) is not dict or
        set(identity) != {'experiment_id','case_id','trial_id','trial_index','companion_version','versions'} or
        type(identity['trial_index']) is not int or not 1 <= identity['trial_index'] <= 5 or
        any(type(identity[k]) is not str or not identity[k] for k in
            ('experiment_id','case_id','trial_id','companion_version')) or
        type(identity['versions']) is not dict or
        any(type(k) is not str or type(v) is not str for k,v in identity['versions'].items())):
        raise ContractError('identity_type_or_range')

def validate_imported(rows):
    """Derive recorded projections without dispatching a single action."""
    try:
        bindings = versions()
        states = {}
        required = set(strict_json((ROOT / 'call.schema.json').read_text())['required'])
        for row in rows:
            if type(row) is not dict or set(row) != required:
                raise ContractError('record_fields')
            validate_identity(row['identity'])
            if (row['schema'] != VERSION or row['identity']['companion_version'] != VERSION or
                row['identity']['versions'] != bindings):
                raise ContractError('runtime_binding')
            key = canonical(row['identity'])
            seen, terminal = states.get(key, (set(), False))
            if terminal:
                raise ContractError('record_after_terminal')
            if row['model_cost'] is not None or row['price_source'] is not None:
                raise ContractError('offline_price_projection')
            if row['error'] not in (None, 'transport_error', 'contract_error'):
                raise ContractError('error_enum')
            adapter_cls = next((a for a in ADAPTERS.values() if a.name == row['provider']), None)
            if adapter_cls is None:
                raise ContractError('provider')
            adapter = adapter_cls(None)
            response = row['response']
            tools, final, error = [], None, None
            usage = dict(state='unknown', input_tokens=None, output_tokens=None)
            served = None
            if response is None:
                error = 'transport_error'
            else:
                if type(response) is not dict:
                    raise ContractError('response_type')
                served = response.get('model')
                usage = adapter.usage(response)
                try:
                    parsed, final = adapter.validate(deepcopy(response))
                    tools = strict_json(canonical(parsed))
                    if any(cid in seen for cid, _ in parsed):
                        raise ContractError('reused_call_id')
                    seen.update(cid for cid, _ in parsed)
                except (ValueError, TypeError, KeyError, AttributeError):
                    error = 'contract_error'
            # Canonical equality distinguishes True from 1, and 1.0 from 1.
            actual = [row['tools'], row['usage'], row['served_model'], row['error']]
            derived = [tools, usage, served, error]
            if canonical(actual) != canonical(derived):
                raise ContractError('semantic_projection')
            states[key] = (seen, error is not None or final is not None)
    except (TypeError, KeyError, AttributeError, StopIteration) as exc:
        raise ContractError('import_shape') from exc


def load(path, expected):
    """Validate the complete import before any caller can replay its actions."""
    try:
        if expected['schema'] != VERSION or expected['versions'] != versions():
            raise ContractError('manifest_runtime_binding')
        rows = _load_bound(path, expected)
        validate_imported(rows)
        return rows
    except (TypeError, KeyError, AttributeError, StopIteration) as exc:
        raise ContractError('import_shape') from exc


def _load_bound(path, expected):
    """Caller supplies trusted expected manifest, not identity from the loaded rows."""
    rows = [strict_json(line) for line in Path(path).read_text().splitlines()]
    if len(rows) != expected['record_count'] or digest(rows) != expected['records_sha256']:
        raise ContractError('content_binding')
    schedule = expected['schedule']
    for identity in schedule:
        validate_identity(identity)
    if len({canonical(identity) for identity in schedule}) != len(schedule):
        raise ContractError('duplicate_schedule_identity')
    pos, attempt = 0, 0
    for row in rows:
        validate_identity(row['identity'])
        if pos >= len(schedule):
            raise ContractError('extra_trial')
        if row['identity'] != schedule[pos]:
            if attempt == 0:
                raise ContractError('missing_trial')
            pos += 1
            attempt = 0
        if pos >= len(schedule) or row['identity'] != schedule[pos]:
            raise ContractError('foreign_or_reordered_identity')
        attempt += 1
        if (type(row['attempt']) is not int or row['attempt'] != attempt or attempt > 8 or
            row['schema'] != VERSION or row['provider'] != expected['provider'] or
            row['provenance'] != 'authored-fixture-not-model-output' or
            row['requested_model'] != MODEL or row['request'].get('model') != MODEL or
            row['request_sha256'] != digest(row['request'])):
            raise ContractError('record_contract')
        response = row['response']
        adapter = next(cls for cls in ADAPTERS.values() if cls.name == expected['provider'])(None)
        if response is not None:
            if row['served_model'] != response.get('model') or row['served_model'] != MODEL:
                raise ContractError('foreign_served_identity')
            if row['usage'] != adapter.usage(response):
                raise ContractError('usage_mismatch')
        elif row['error'] != 'transport_error' or row['usage']['state'] != 'unknown':
            raise ContractError('missing_response')
    if not rows or pos != len(schedule)-1:
        raise ContractError('missing_trial')
    return rows

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--provider', choices=ADAPTERS, default='messages')
    parser.add_argument('--fault', choices=['malformed','transport','unknown'])
    parser.add_argument('--output', default='run')
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    if args.live:
        print('BLOCKED: offline only; no request sent')
        return 2
    out = Path(args.output)
    out.mkdir(exist_ok=False)
    manifest, records = run(args.provider, args.fault)
    (out/'calls.jsonl').write_text(''.join(canonical(r)+'\n' for r in records))
    (out/'manifest.json').write_text(canonical(manifest)+'\n')
    load(out/'calls.jsonl', manifest)
    print(canonical(dict(provider=manifest['provider'], trials=len(manifest['trials']),
                         passed=sum(t['status']=='PASS' for t in manifest['trials']),
                         calls=len(records), unknown_usage=sum(r['usage']['state']=='unknown' for r in records),
                         model_cost=None, **manifest['summary'])))
    return 0 if all(t['status']=='PASS' for t in manifest['trials']) else 2

if __name__ == '__main__':
    raise SystemExit(main())

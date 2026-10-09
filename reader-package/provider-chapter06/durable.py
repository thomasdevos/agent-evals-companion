"""Single-trial offline durable integration; no resume and no network client."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import cassettes as c
import currency as money
import capture_store as storage

SCHEMA = 'currency-cassette-durable-v1'

class StorageFault(money.Stop):
    pass

def bindings():
    return {name: hashlib.sha256((c.ROOT/name).read_bytes()).hexdigest()
            for name in ('durable.py', 'currency.py', 'capture_store.py')}

def read(path):
    return c.strict_json(Path(path).read_text())

class DurableTransport(money.AdmittedTransport):
    def __init__(self, callback, budget, first, store, config):
        super().__init__(callback, budget, first)
        self.store, self.config = store, deepcopy(config)
        self.entry = None
        self.fatal = None
        self.before = None

    def fail(self, exc):
        # Restore the last pre-callback reservation, even if usage settled in RAM.
        if self.before is not None:
            self.budget.__dict__.clear()
            self.budget.__dict__.update(deepcopy(self.before))
        self.budget.blocked = True
        self.stop = 'storage_fault_unknown_completion'
        self.fatal = dict(type=type(exc).__name__, detail=str(exc))
        raise StorageFault(self.stop) from exc

    def __call__(self, payload):
        if self.fatal:
            raise StorageFault(self.stop)
        # AdmittedAgent reserves before creating the attempted-call row.
        if self.first is None:
            raise money.Stop('reservation_required')
        self.before = deepcopy(self.budget.__dict__)
        request = dict(payload=deepcopy(payload), attempt=self.first,
                       config=self.config, accounting=self.budget.report())
        try:
            self.entry = self.store.intent('full:1', request)
        except Exception as exc:
            self.fail(exc)
        return super().__call__(payload)

    def finish(self, row):
        if self.fatal:
            raise StorageFault(self.stop)
        try:
            self.store.finish(self.entry, dict(call=deepcopy(row),
                              accounting=self.budget.report(), stop=self.stop,
                              event=deepcopy(self.events[-1])))
        except Exception as exc:
            self.fail(exc)
        self.entry = None
        self.before = None

class DurableAgent(money.AdmittedAgent):
    def __call__(self, view):
        if self.admission.fatal:
            raise StorageFault(self.admission.stop)
        count = len(self.records)
        try:
            return super().__call__(view)
        finally:
            # Agent.finally has already completed the retained call. This runs
            # before its returned action can reach the SQLite executor.
            if len(self.records) > count and self.admission.entry is not None:
                self.admission.finish(self.records[-1])

def execute(directory, card, provider='messages', config=None, callback=None):
    effective = deepcopy(money.CONFIG if config is None else config)
    budget = money.configured(effective)
    first = budget.reserve()
    if provider not in c.ADAPTERS:
        raise money.PreflightStop('unsupported_provider')
    identity = dict(experiment_id='currency-offline-v1', case_id='full',
                    trial_id='full:1', trial_index=1,
                    companion_version=c.VERSION, versions=c.versions())
    # Existing directory is refused, including an interrupted previous capture.
    store = storage.CaptureStore(directory, SCHEMA, ['full:1'])
    contract = dict(schema=SCHEMA, identity=identity, provider=provider,
                    config=effective, card=deepcopy(card), bindings=bindings())
    storage.atomic_json(store.directory/'contract.json', contract)
    transport = DurableTransport(callback if callback is not None else c.Authored(provider),
                                 budget, first, store, effective)
    rows = []
    agent = DurableAgent(c.ADAPTERS[provider](transport), identity, rows, transport)
    result = c.run_trial(card, 'currency-admitted', agent)
    if transport.fatal:
        result.update(status='INFRA_ERROR', passed=0, failed=0, errors=1)
        # Disk may contain only intent. Do not publish a completion certificate.
        return dict(result=result, records=rows, stop=transport.stop,
                    accounting=budget.report(), storage_error=transport.fatal)
    c.validate_imported(rows)
    completed = dict(schema=SCHEMA, record_count=len(rows), records_sha256=c.digest(rows),
                     contract_sha256=c.digest(contract), result=result,
                     accounting=budget.report(), stop=transport.stop,
                     events=deepcopy(transport.events))
    try:
        storage.atomic_json(store.directory/'complete.json', completed)
    except Exception as exc:
        # All individual terminals are durable, but the run is not certified.
        budget.blocked = True
        return dict(result=result, records=rows, stop='completion_storage_fault',
                    accounting=budget.report(), storage_error=dict(type=type(exc).__name__,detail=str(exc)))
    return dict(result=result, records=rows, stop=transport.stop,
                accounting=budget.report(), storage_error=None)

def load(directory):
    """Adapter for the existing store, not its incompatible abstract-unit loader."""
    directory = Path(directory)
    manifest = read(directory/'manifest.json')
    expected = dict(schema=1, identity=SCHEMA, schedule=['full:1'],
                    provenance='synthetic', policy='full-private', replayable=True)
    if c.canonical(manifest) != c.canonical(expected):
        raise c.ContractError('durable_manifest')
    contract, complete = read(directory/'contract.json'), read(directory/'complete.json')
    if (contract['schema'] != SCHEMA or contract['bindings'] != bindings() or
        complete['schema'] != SCHEMA or complete['contract_sha256'] != c.digest(contract)):
        raise c.ContractError('durable_binding')
    c.validate_identity(contract['identity'])
    budget = money.configured(contract['config'])
    rows = []
    stop = None
    files = sorted(directory.glob('[0-9]*.json'))
    events = complete.get('events')
    event_fields = {'attempt', 'request_sha256', 'reserved_before_callback', 'stop'}
    if (type(events) is not list or len(events) != len(files) or
        any(type(event) is not dict or not event_fields <= event.keys() for event in events)):
        raise c.ContractError('event_binding')
    for number, file in enumerate(files, 1):
        entry = read(file)
        if (set(entry) != {'schema','identity','sequence','trial_id','state','request','request_sha256','result'} or
            type(entry['sequence']) is not int or entry['sequence'] != number or
            type(entry['schema']) is not int or entry['schema'] != 1 or
            file.name != f'{number:06d}.json' or entry['identity'] != SCHEMA or
            entry['trial_id'] != 'full:1' or entry['state'] != 'terminal' or
            entry['request_sha256'] != c.digest(entry['request'])):
            raise c.ContractError('unresolved_or_invalid_entry')
        request, terminal = entry['request'], entry['result']
        attempt = budget.reserve()
        row = terminal['call']
        expected_request = dict(payload=row['request'], attempt=attempt,
                                config=contract['config'], accounting=budget.report())
        if (c.canonical(request) != c.canonical(expected_request) or
            row['identity'] != contract['identity'] or type(row['attempt']) is not int or
            row['attempt'] != number or row['provider'] != c.ADAPTERS[contract['provider']].name or
            row['request_sha256'] != c.digest(row['request'])):
            raise c.ContractError('intent_call_binding')
        usage = row['response'].get('usage') if type(row['response']) is dict else None
        try:
            budget.settle(attempt, usage)
        except ValueError:
            stop = 'invalid_or_excess_usage'
        if stop is None and budget.blocked:
            stop = 'transport_error_unknown_exposure' if row['response'] is None else 'unknown_usage'
        if c.canonical(terminal['accounting']) != c.canonical(budget.report()) or terminal['stop'] != stop:
            raise c.ContractError('terminal_accounting')
        event = terminal.get('event')
        if (type(event) is not dict or not event_fields <= event.keys() or
            c.canonical(event) != c.canonical(events[number-1]) or
            type(event['attempt']) is not int or event['attempt'] != attempt or
            event['request_sha256'] != row['request_sha256'] or
            type(event['reserved_before_callback']) is not int or
            event['reserved_before_callback'] != request['accounting']['reserved_minor'] or
            event['stop'] != stop):
            raise c.ContractError('event_binding')
        rows.append(row)
    c.validate_imported(rows)
    if (not rows or type(complete['record_count']) is not int or
        len(complete['events']) != len(rows) or
        complete['record_count'] != len(rows) or complete['records_sha256'] != c.digest(rows) or
        c.canonical(complete['accounting']) != c.canonical(budget.report())):
        raise c.ContractError('completion_binding')
    # A later admission denial has no attempted-call row.
    if complete['stop'] == 'admission_denied':
        try:
            budget.reserve()
        except ValueError:
            pass
        else:
            raise c.ContractError('false_admission_denial')
    elif complete['stop'] != stop:
        raise c.ContractError('completion_stop')
    return contract, complete, rows

def export(directory, destination):
    contract, complete, rows = load(directory)
    out = Path(destination)
    out.mkdir(parents=True, exist_ok=False, mode=0o700)
    manifest = dict(schema=c.VERSION, versions=c.versions(),
                    provider=c.ADAPTERS[contract['provider']].name,
                    schedule=[contract['identity']], record_count=len(rows),
                    records_sha256=c.digest(rows))
    # The completion marker is last. Incomplete exports are not consumable.
    with (out/'calls.jsonl').open('x') as stream:
        stream.write(''.join(c.canonical(row)+'\n' for row in rows))
        stream.flush()
        storage.os.fsync(stream.fileno())
    storage.atomic_json(out/'manifest.json', manifest)
    storage.atomic_json(out/'policy.json', dict(contract=contract, complete=complete))
    c.load(out/'calls.jsonl', manifest)
    storage.atomic_json(out/'export-complete.json', dict(schema=SCHEMA,
                        calls_sha256=c.digest(rows), policy_sha256=c.digest(read(out/'policy.json'))))
    return len(rows)

def replay(directory):
    directory = Path(directory)
    seal = read(directory/'export-complete.json')
    policy = read(directory/'policy.json')
    rows = c.load(directory/'calls.jsonl', read(directory/'manifest.json'))
    if (seal['schema'] != SCHEMA or seal['calls_sha256'] != c.digest(rows) or
        seal['policy_sha256'] != c.digest(policy) or
        policy['contract']['bindings'] != bindings()):
        raise c.ContractError('export_binding')
    contract, complete = policy['contract'], policy['complete']
    callback = c.Replay(rows)
    run = money.execute(contract['card'], contract['provider'], contract['config'], callback)
    callback.finish()
    if (run['result'] != complete['result'] or
        run['budget_receipt']['accounting'] != complete['accounting'] or
        run['budget_receipt']['stop'] != complete['stop']):
        raise c.ContractError('policy_replay_mismatch')
    return run

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['capture','export','replay'])
    parser.add_argument('directory')
    parser.add_argument('--output')
    parser.add_argument('--provider', choices=c.ADAPTERS, default='messages')
    parser.add_argument('--unknown', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'capture':
            card = read(c.ROOT/'vendor/chapter02/cards/full.json')
            run = execute(args.directory, card, args.provider,
                          callback=c.Authored(args.provider, 'unknown' if args.unknown else None))
            print(c.canonical(dict(status=run['result']['status'], stop=run['stop'],
                                   accounting=run['accounting'], calls=len(run['records']))))
            return 0 if run['result']['status'] == 'PASS' and not run['storage_error'] else 2
        if args.command == 'export':
            if not args.output:
                raise ValueError('--output required')
            print(c.canonical(dict(exported_calls=export(args.directory,args.output))))
        else:
            run = replay(args.directory)
            print(c.canonical(dict(policy_replay='matched', status=run['result']['status'])))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(c.canonical(dict(refused=type(exc).__name__, detail=str(exc))))
        return 2

if __name__ == '__main__':
    raise SystemExit(main())

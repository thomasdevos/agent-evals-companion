"""Offline native reducer + durable store + hypothetical category admission."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from native import Conversation, SQLiteExecutor, usage, require, canonical, ContractError
from demo import envelope
import capture_store as storage

SCHEMA = 'native-durable-v1'
PROMPT = 'Synthetic task: refund A100, then inspect the ledger.'


class CategoryBudget(storage.MoneyBudget):
    """Fixed hypothetical GBP rates per 1000; reserve the highest input rate."""
    def __init__(self, ceiling=100):
        super().__init__(ceiling=ceiling, input_rate=4, output_rate=4)

    def cost(self, provider, raw):
        u = usage(provider, raw)
        c = u['categories']
        if provider == 'responses':
            # Cache-write overlap is not defined by this supported tariff.
            require('cached_tokens' in c and c.get('cache_write_tokens', 0) == 0,
                    'unknown_billing_split')
            inputs = c['input_total']
            numerator = (inputs - c['cached_tokens']) * 2 + c['cached_tokens']
        else:
            inputs = c['input_uncached'] + c['cache_creation'] + c['cache_read']
            ttl = c.get('cache_creation_by_ttl')
            require(ttl is not None or c['cache_creation'] == 0, 'unknown_cache_ttl')
            ttl = ttl or dict(ephemeral_5m_input_tokens=0, ephemeral_1h_input_tokens=0)
            numerator = (c['input_uncached'] * 2 + c['cache_read'] +
                         ttl['ephemeral_5m_input_tokens'] * 3 + ttl['ephemeral_1h_input_tokens'] * 4)
        require(inputs <= self.input_limit and c['output_total'] <= self.output_limit,
                'usage_exceeds_bounds')
        return (numerator + c['output_total'] * 4 + 999) // 1000

    def settle_native(self, attempt, provider, raw):
        require(attempt in self.held, 'reservation_required')
        self.settled[attempt] = self.cost(provider, raw)
        del self.held[attempt]

    def report(self):
        r = super().report()
        r['rates_minor_per_1000'] = dict(input_uncached=2, cache_read=1,
            cache_write_5m=3, cache_write_1h=4, output_total=4)
        r['reservation_rates_minor_per_1000'] = dict(input=4, output=4)
        r['model_cost_minor'] = None  # Never label a hypothetical tariff as a measured invoice.
        r['hypothetical_total_minor'] = None if self.held else sum(self.settled.values())
        return r


class Session:
    """Single writer; every failure latches closed. No restart or automatic retry."""
    def __init__(self, directory, provider, executor, ceiling=100, store_factory=storage.CaptureStore):
        self._conversation = Conversation(provider, PROMPT)
        self.provider, self.executor = provider, executor
        self.budget = CategoryBudget(ceiling)
        self.stopped = False
        self.turns = 0
        self.store = store_factory(directory, SCHEMA, ['trial:1'])
        self.contract = dict(schema=SCHEMA, provider=provider, prompt=PROMPT, ceiling=ceiling,
                             provenance='synthetic-envelopes-real-local-sqlite')
        storage.atomic_json(self.store.directory / 'contract.json', self.contract)

    def turn(self, callback):
        require(not self.stopped, 'session_stopped')
        before = None
        try:
            attempt = self.budget.reserve()
            before = deepcopy(self.budget.__dict__)
            request = self._conversation.request()
            entry = self.store.intent('trial:1', dict(kind='request', attempt=attempt,
                payload=request, accounting=self.budget.report()))
            response = deepcopy(callback(deepcopy(request)))
            calls = self._conversation.accept(response)
            # Validate category admission before any tool effect. Settlement waits for persistence.
            self.budget.cost(self.provider, response['usage'])
            self.store.finish(entry, dict(response=response))
            results = []
            for cid, call in calls:
                effect = self.store.intent('trial:1', dict(kind='effect', attempt=attempt,
                    response_id=response['id'], call_id=cid, action=call))
                output = self.executor(deepcopy(call))
                require(type(output) is dict and set(output) == {'is_error', 'output'}, 'executor_shape')
                require(type(output['is_error']) is bool and type(output['output']) is str
                        and bool(output['output']), 'executor_output')
                result = dict(call_id=cid, **deepcopy(output))
                self.store.finish(effect, result)
                results.append(result)
            # Persist the full result set and settled accounting before reducer continuation.
            self.budget.settle_native(attempt, self.provider, response['usage'])
            barrier = self.store.intent('trial:1', dict(kind='barrier', attempt=attempt,
                response_id=response['id']))
            self.store.finish(barrier, dict(results=results, accounting=self.budget.report()))
            if calls:
                self._conversation.complete(results)
            self.turns += 1
            return dict(request=request, response=response, results=deepcopy(results))
        except Exception:
            if before is not None:
                self.budget.__dict__.clear()
                self.budget.__dict__.update(before)
            self.budget.blocked = True
            self.stopped = True
            raise

    def finish(self):
        require(not self.stopped and self._conversation._closed, 'unfinished_session')
        try:
            storage.atomic_json(self.store.directory / 'complete.json', dict(schema=SCHEMA,
                contract_sha256=storage.sha(self.contract), turns=self.turns,
                accounting=self.budget.report(), entries_sha256=storage.sha(entries(self.store.directory))))
        except Exception:
            self.stopped = True
            self.budget.blocked = True
            raise
        self.stopped = True


def read(path):
    from wire_guard import strict_json
    return strict_json(Path(path).read_text())


def entries(directory):
    return [read(p) for p in sorted(Path(directory).glob('[0-9]*.json'))]


def validate(contract, complete, rows):
    """Reconstruct requests, tariffs and local results. Never trust duplicate hashes alone."""
    require(type(contract) is dict and set(contract) == {'schema','provider','prompt','ceiling','provenance'}, 'contract')
    require(contract['schema'] == SCHEMA and contract['prompt'] == PROMPT and
            contract['provenance'] == 'synthetic-envelopes-real-local-sqlite', 'contract')
    require(type(complete) is dict and set(complete) == {'schema','contract_sha256','turns','accounting','entries_sha256'}, 'completion')
    require(complete['schema'] == SCHEMA and complete['contract_sha256'] == storage.sha(contract)
            and complete['entries_sha256'] == storage.sha(rows), 'completion_binding')
    conv = Conversation(contract['provider'], contract['prompt'])
    budget = CategoryBudget(contract['ceiling'])
    for number, row in enumerate(rows, 1):
        require(type(row) is dict and set(row) == {'schema','identity','sequence','trial_id','state','request','request_sha256','result'}, 'entry_shape')
        require(type(row['sequence']) is int and row['sequence'] == number and
                type(row['schema']) is int and row['schema'] == 1 and row['identity'] == SCHEMA and
                row['trial_id'] == 'trial:1' and row['state'] == 'terminal' and
                row['request_sha256'] == storage.sha(row['request']), 'entry_binding')
    index, turns = 0, 0
    def take(expected):
        nonlocal index
        require(index < len(rows), 'missing_entry')
        row = rows[index]; index += 1
        require(canonical(row['request']) == canonical(expected), 'request_identity')
        return row['result']
    with tempfile.TemporaryDirectory(prefix='native-validation-') as d:
        executor = SQLiteExecutor(Path(d) / 'fixture.sqlite')
        while index < len(rows):
            attempt = budget.reserve()
            terminal = take(dict(kind='request', attempt=attempt, payload=conv.request(), accounting=budget.report()))
            require(type(terminal) is dict and set(terminal) == {'response'}, 'response_terminal')
            response = terminal['response']
            calls = conv.accept(response)
            budget.cost(contract['provider'], response['usage'])
            results = []
            for cid, call in calls:
                result = take(dict(kind='effect', attempt=attempt, response_id=response['id'], call_id=cid, action=call))
                expected = dict(call_id=cid, **executor(call))
                require(canonical(result) == canonical(expected), 'executor_result_identity')
                results.append(result)
            budget.settle_native(attempt, contract['provider'], response['usage'])
            barrier = take(dict(kind='barrier', attempt=attempt, response_id=response['id']))
            require(canonical(barrier) == canonical(dict(results=results, accounting=budget.report())), 'barrier_binding')
            if calls:
                conv.complete(results)
            turns += 1
    require(conv._closed and type(complete['turns']) is int and complete['turns'] == turns and
            canonical(complete['accounting']) == canonical(budget.report()), 'completion_accounting')
    return dict(turns=turns, entries=len(rows), accounting=budget.report())


def load(directory):
    d = Path(directory)
    expected = dict(schema=1, identity=SCHEMA, schedule=['trial:1'], provenance='synthetic', policy='full-private', replayable=True)
    require(canonical(read(d/'manifest.json')) == canonical(expected), 'manifest')
    rows = entries(d)
    require([p.name for p in sorted(d.glob('[0-9]*.json'))] == [f'{i:06d}.json' for i in range(1,len(rows)+1)], 'filenames')
    contract, complete = read(d/'contract.json'), read(d/'complete.json')
    validate(contract, complete, rows)
    return dict(contract=contract, complete=complete, entries=rows)


def export(directory, destination):
    bundle = load(directory)  # Refuse incomplete evidence before creating any export.
    out = Path(destination)
    out.mkdir(parents=True, exist_ok=False)
    storage.atomic_json(out/'bundle.json', bundle)
    storage.atomic_json(out/'export-complete.json', dict(schema=SCHEMA, sha256=storage.sha(bundle)))
    return len(bundle['entries'])


def replay(directory):
    d = Path(directory)
    bundle, seal = read(d/'bundle.json'), read(d/'export-complete.json')
    require(canonical(seal) == canonical(dict(schema=SCHEMA, sha256=storage.sha(bundle))), 'export_binding')
    require(type(bundle) is dict and set(bundle) == {'contract','complete','entries'}, 'bundle')
    return validate(bundle['contract'], bundle['complete'], bundle['entries'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['capture','export','replay'])
    p.add_argument('directory')
    p.add_argument('--provider', choices=['responses','messages'], default='messages')
    p.add_argument('--output')
    p.add_argument('--unknown', action='store_true')
    args = p.parse_args()
    session = None
    try:
        if args.command == 'capture':
            with tempfile.TemporaryDirectory(prefix='native-demo-') as d:
                executor = SQLiteExecutor(Path(d)/'fixture.sqlite')
                session = Session(args.directory, args.provider, executor)
                response = envelope(args.provider)
                if args.unknown:
                    response['usage'] = None
                session.turn(lambda request: response)
                session.turn(lambda request: envelope(args.provider, True))
                session.finish()
                print(canonical(dict(status='COMPLETE', executor_calls=executor.calls, **replay_capture(args.directory))))
        elif args.command == 'export':
            require(bool(args.output), 'output_required')
            print(canonical(dict(exported_entries=export(args.directory,args.output))))
        else:
            print(canonical(replay(args.directory)))
        return 0
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as exc:
        print(canonical(dict(status='BLOCKED', error=str(exc), accounting=session.budget.report() if session else None)))
        return 2


def replay_capture(directory):
    b = load(directory)
    return validate(b['contract'], b['complete'], b['entries'])


if __name__ == '__main__':
    raise SystemExit(main())

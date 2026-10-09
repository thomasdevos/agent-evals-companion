"""Offline capture storage and hypothetical currency admission. No network code."""
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from datetime import datetime
from copy import deepcopy

# Schema 1 has one supported synthetic policy: per-trial cumulative units.
# Historical schema-1 captures imply this same policy; no currency claim.
ABSTRACT_POLICY = {'attempt_cap': 8, 'ceiling_units': 8, 'units_per_attempt': 1}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def integer(value, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError('exact integer required')
    return value


def atomic_json(path, value):
    """Single-writer snapshot: fsync bytes, replace atomically, fsync directory."""
    path = Path(path)
    data = (canonical(value) + '\n').encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.capture-')
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


class MoneyBudget:
    """Integer minor units. Rates are hypothetical, not a provider invoice cap."""
    def __init__(self, ceiling=100, attempts=8, input_rate=1, output_rate=2,
                 input_limit=1000, output_limit=1000, currency='GBP'):
        for value in (ceiling, attempts, input_rate, output_rate, input_limit, output_limit):
            integer(value, 1)
        if currency != 'GBP':
            raise ValueError('this teaching configuration uses GBP minor units')
        self.ceiling, self.cap = ceiling, attempts
        self.input_rate, self.output_rate = input_rate, output_rate
        self.input_limit, self.output_limit = input_limit, output_limit
        self.currency = currency
        self.held = {}
        self.settled = {}
        self.unknown = set()
        self.blocked = False

    def price(self, inputs, outputs):
        integer(inputs); integer(outputs)
        # Rates are pence per 1000 tokens; round total upward once.
        return (inputs * self.input_rate + outputs * self.output_rate + 999) // 1000

    def reserve(self):
        reserve = self.price(self.input_limit, self.output_limit)
        if (self.blocked or len(self.held) + len(self.settled) >= self.cap or
                sum(self.held.values()) + sum(self.settled.values()) + reserve > self.ceiling):
            raise ValueError('currency_admission_denied')
        attempt = len(self.held) + len(self.settled) + 1
        self.held[attempt] = reserve
        return attempt

    def settle(self, attempt, usage):
        integer(attempt, 1)
        if attempt not in self.held or attempt in self.unknown:
            raise ValueError('unknown or already finalised attempt')
        if usage is None:
            self.unknown.add(attempt)
            self.blocked = True
            return
        try:
            if type(usage) is not dict or set(usage) != {'input_tokens', 'output_tokens'}:
                raise ValueError('unsupported billing categories')
            i, o = usage['input_tokens'], usage['output_tokens']
            integer(i); integer(o)
            if i > self.input_limit or o > self.output_limit:
                raise ValueError('usage exceeds reservation assumptions')
        except ValueError:
            self.unknown.add(attempt)
            self.blocked = True
            raise
        self.settled[attempt] = self.price(i, o)
        del self.held[attempt]

    def report(self):
        return dict(currency=self.currency, price_source='hypothetical-teaching-only',
                    rates_minor_per_1000={'input': self.input_rate, 'output': self.output_rate},
                    ceiling_minor=self.ceiling, reserved_minor=sum(self.held.values()),
                    known_cost_minor=sum(self.settled.values()),
                    model_cost_minor=None if self.held else sum(self.settled.values()),
                    unresolved_attempts=sorted(self.held), blocked=self.blocked,
                    guarantee='local admission only; no provider billing guarantee')


class MoneyTransport:
    """Offline transport decorator, caller must establish input/output bounds."""
    def __init__(self, transport, budget):
        self.transport, self.budget = transport, budget

    def __call__(self, payload, timeout):
        attempt = self.budget.reserve()
        try:
            reply = self.transport(payload, timeout)
        except Exception:
            self.budget.settle(attempt, None)
            raise
        self.budget.settle(attempt, reply.get('usage') if type(reply) is dict else None)
        return reply


class CaptureStore:
    """One private file per attempt, intent before send; no automatic resume."""
    def __init__(self, directory, identity, schedule):
        if type(identity) is not str or not identity:
            raise ValueError('identity required')
        if type(schedule) is not list or not schedule or any(type(x) is not str or not x for x in schedule) or len(set(schedule)) != len(schedule):
            raise ValueError('unique nonempty schedule required')
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=False, mode=0o700)
        self.manifest = dict(schema=1, identity=identity, schedule=schedule,
                             provenance='synthetic', policy='full-private', replayable=True)
        atomic_json(self.directory / 'manifest.json', self.manifest)
        self.sequence = 0

    def intent(self, trial_id, request):
        if trial_id not in self.manifest['schedule']:
            raise ValueError('foreign trial')
        self.sequence += 1
        entry = dict(schema=1, identity=self.manifest['identity'], sequence=self.sequence,
                     trial_id=trial_id, state='intent', request=deepcopy(request),
                     request_sha256=sha(request), result=None)
        atomic_json(self.directory / f'{self.sequence:06d}.json', entry)
        return entry

    def finish(self, entry, result):
        done = deepcopy(entry)
        done['state'] = 'terminal'
        done['result'] = deepcopy(result)
        atomic_json(self.directory / f"{entry['sequence']:06d}.json", done)


def load_capture(directory, identity, schedule):
    if type(identity) is not str or not identity:
        raise ValueError('identity required')
    directory = Path(directory)
    def reject_constant(value):
        raise ValueError('nonfinite JSON')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    def read(path):
        return json.loads(path.read_text(), parse_constant=reject_constant, object_pairs_hook=pairs)
    m = read(directory / 'manifest.json')
    expected = dict(schema=1, identity=identity, schedule=schedule, provenance='synthetic', policy='full-private', replayable=True)
    if type(m) is not dict or type(m.get('schema')) is not int or type(m.get('replayable')) is not bool or m != expected:
        raise ValueError('capture manifest mismatch')
    if type(schedule) is not list or not schedule or any(type(x) is not str or not x for x in schedule) or len(set(schedule)) != len(schedule):
        raise ValueError('invalid schedule')
    entries = []
    seen = set()
    attempts = {}
    trial_position = -1
    for number, file in enumerate(sorted(directory.glob('[0-9]*.json')), 1):
        e = read(file)
        if type(e) is not dict or set(e) != {'schema','identity','sequence','trial_id','state','request','request_sha256','result'}:
            raise ValueError('invalid entry shape')
        if type(e['schema']) is not int or e['schema'] != 1 or type(e['sequence']) is not int or e['sequence'] != number or file.name != f'{number:06d}.json':
            raise ValueError('invalid sequence')
        if e['identity'] != identity or e['trial_id'] not in schedule or e['state'] != 'terminal':
            raise ValueError('identity, schedule or unresolved intent')
        if type(e['request']) is not dict or sha(e['request']) != e['request_sha256']:
            raise ValueError('request digest mismatch')
        r = e['result']
        required = {'provenance','trial_id','attempt','request','request_sha256','requested_model','served_model','response','usage','error','timestamp','model_cost','reserved_units','elapsed_local_seconds'}
        if type(r) is not dict or set(r) != required or r['provenance'] != 'synthetic-not-recorded-model-data':
            raise ValueError('result schema mismatch')
        if type(r['timestamp']) is not str:
            raise ValueError('invalid timestamp')
        stamp = datetime.fromisoformat(r['timestamp'])
        if stamp.tzinfo is None:
            raise ValueError('timezone required')
        integer(r['reserved_units'], 1)
        if r['model_cost'] is not None or r['usage'] is not None:
            raise ValueError('synthetic schema expects unknown billing')
        if type(r) is not dict or r.get('request') != e['request'] or r.get('request_sha256') != e['request_sha256'] or r.get('trial_id') != e['trial_id']:
            raise ValueError('result evidence mismatch')
        if type(r.get('attempt')) is not int or r['attempt'] < 1:
            raise ValueError('invalid attempt')
        key = (e['trial_id'], r['attempt'])
        if key in seen:
            raise ValueError('duplicate attempt')
        seen.add(key)
        position = schedule.index(e['trial_id'])
        if position < trial_position or position > trial_position + 1:
            raise ValueError('trial schedule order mismatch')
        trial_position = position
        expected_attempt = attempts.get(e['trial_id'], 0) + 1
        if (r['attempt'] != expected_attempt or r['attempt'] > ABSTRACT_POLICY['attempt_cap'] or
                r['reserved_units'] != expected_attempt * ABSTRACT_POLICY['units_per_attempt'] or
                r['reserved_units'] > ABSTRACT_POLICY['ceiling_units']):
            raise ValueError('abstract budget policy mismatch')
        attempts[e['trial_id']] = expected_attempt
        elapsed = r.get('elapsed_local_seconds')
        if type(elapsed) not in (int,float) or not math.isfinite(elapsed) or elapsed < 0:
            raise ValueError('invalid elapsed time')
        if type(r.get('requested_model')) is not str or r['requested_model'] != identity or r.get('requested_model') != e['request'].get('model'):
            raise ValueError('requested identity mismatch')
        if r.get('error') is None:
            if type(r.get('response')) is not dict or r.get('served_model') != r['requested_model'] or r['response'].get('model') != r['served_model']:
                raise ValueError('served identity mismatch')
        elif type(r['error']) is not str:
            raise ValueError('invalid error')
        entries.append(r)
    if {e['trial_id'] for e in entries} != set(schedule):
        raise ValueError('missing scheduled rows')
    return entries


def publication_summary(directory, entries):
    """Allowlist metadata, drop all payloads, IDs and free text. Never replayable."""
    atomic_json(Path(directory), dict(schema=1, policy='redacted-nonreplayable', replayable=False,
                                    provenance='synthetic', attempt_count=len(entries),
                                    error_count=sum(e['error'] is not None for e in entries)))

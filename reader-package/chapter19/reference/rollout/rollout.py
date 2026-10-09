"""Synthetic local routing state machine. No deployment adapter exists."""
import copy
import hashlib
import json
from chapter19 import delivery
import drift

STAGES = ('hold', 'shadow', 'canary', 'staged', 'full')
SHARES = (0, 0, 5, 25, 100)
OWNER = 'Alex Morgan (synthetic release owner)'
BASE = 'scripted-support-v0'
CANDIDATE = 'scripted-support-v1'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def fields(value, keys):
    if type(value) is not dict or set(value) != set(keys.split()):
        raise ValueError('unexpected fields')


def integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('integer outside policy')


def initial():
    return dict(stage='hold', candidate_share=0, future_version=BASE,
                generation=0, last_day=19, committed_effects=['synthetic-refund-001'],
                stopped=False)


def validate_state(state):
    fields(state, 'stage candidate_share future_version generation last_day committed_effects stopped')
    if state['stage'] not in STAGES or type(state['stopped']) is not bool or (state['stopped'] and state['stage'] != 'hold'):
        raise ValueError('state stage or stop')
    # This sequence counter is nonnegative, not a bounded deployment allowance.
    # Every accepted counter must admit the successor needed by rollback.
    if type(state['generation']) is not int or state['generation'] < 0:
        raise ValueError('generation must be a nonnegative integer')
    integer(state['last_day'], 19, 79)
    integer(state['candidate_share'], 0, 100)
    if state['candidate_share'] != SHARES[STAGES.index(state['stage'])]:
        raise ValueError('share disagrees with stage')
    version = 'HALT' if state['stopped'] and state['last_day'] >= 60 else CANDIDATE if state['candidate_share'] else BASE
    if state['future_version'] != version:
        raise ValueError('version disagrees with route')
    if type(state['committed_effects']) is not list or any(type(x) is not str for x in state['committed_effects']):
        raise ValueError('effect history')


def evidence(day=20, scenario='pass', injected=False):
    """Call real existing producers. Envelope and epoch are authored lab metadata."""
    integer(day, 20, 79)
    return dict(schema='rollout-evidence-v1', synthetic=True, epoch=day,
                release=CANDIDATE, delivery=delivery.seal(delivery.collect(scenario)),
                sentinel=[r for r in drift.generate(20261006, injected) if r['day'] == day-3])


def check_evidence(packet, day):
    fields(packet, 'schema synthetic epoch release delivery sentinel')
    if packet['schema'] != 'rollout-evidence-v1' or packet['synthetic'] is not True:
        raise ValueError('synthetic schema')
    integer(packet['epoch'], 20, 79)
    if packet['epoch'] != day or packet['release'] != CANDIDATE:
        raise ValueError('stale or foreign evidence')
    verdict, reason = delivery.decide(packet['delivery'])
    rows = packet['sentinel']
    if type(rows) is not list or len(rows) != 200:
        raise ValueError('missing sentinel schedule')
    # Chapter 22 validates field values, not schedule or version identity. Add those here.
    window = day-3
    expected = {f'{window}:{i}' for i in range(200)}
    if any(type(r) is not dict for r in rows):
        raise ValueError('row object')
    for row in rows:
        fields(row, 'id day group refusal outcome outcome_due collected latency_ms cost_units agent_snapshot prompt tool evaluator collector')
        integer(row['outcome_due'], 0, 100)
    drift.validate(rows)
    if {r['id'] for r in rows} != expected:
        raise ValueError('foreign sentinel identity')
    for r in rows:
        if r['day'] != window or r['outcome_due'] != window+3 or any(r[k] != v for k, v in dict(agent_snapshot='lab-A', prompt='prompt-1', tool='tool-1', evaluator='eval-1', collector='collector-1').items()):
            raise ValueError('foreign sentinel version')
    if verdict != 'PASS':
        return verdict, reason
    if any(not r['collected'] or r['outcome'] is None or r['outcome_due'] > day for r in rows):
        return 'DEFER', 'COLLECTION_OR_MATURITY_GAP'
    # Operational stop threshold, not a calibrated inferential significance claim.
    for group, ceiling in [('routine', .15), ('complex', .25)]:
        selected = [r for r in rows if r['group'] == group]
        if not selected:
            return 'DEFER', 'EMPTY_SLICE'
        if sum(r['refusal'] for r in selected) / len(selected) > ceiling:
            return 'STOP', 'REFUSAL_CEILING:' + group
    return 'PASS', 'LOCAL_TECHNICAL_EVIDENCE'


def approval(state, packet, target, day, accepted=True):
    return dict(owner=OWNER, accepted=accepted, state_sha256=digest(state),
                evidence_sha256=digest(packet), target=target, epoch=day,
                scope='synthetic-routing-only')


def authorise(a, state, packet, target, day):
    fields(a, 'owner accepted state_sha256 evidence_sha256 target epoch scope')
    if type(a['accepted']) is not bool or not a['accepted']:
        raise ValueError('approval rejected')
    integer(a['epoch'], 20, 79)
    expected = approval(state, packet, target, day)
    if canonical(a) != canonical(expected):
        raise ValueError('approval binding or owner')


def advance(state, packet, a, day):
    """Return new state only after all checks; never mutate caller state."""
    validate_state(state)
    integer(day, 20, 79)
    if state['stopped'] or state['stage'] == 'full' or day <= state['last_day'] or day >= 60:
        raise ValueError('terminal or non-increasing observation window')
    target = STAGES[STAGES.index(state['stage']) + 1]
    verdict, reason = check_evidence(packet, day)
    if verdict != 'PASS':
        return copy.deepcopy(state), dict(decision=verdict, reason=reason, deployment_changes=0)
    authorise(a, state, packet, target, day)
    new = copy.deepcopy(state)
    new.update(stage=target, candidate_share=SHARES[STAGES.index(target)],
               future_version=CANDIDATE if target not in ('hold','shadow') else BASE,
               generation=state['generation']+1, last_day=day)
    return new, dict(decision='PROMOTE_LOCAL_ONLY', stage=target, deployment_changes=0)


def rollback(state, day, reason, owner):
    validate_state(state)
    integer(day, 20, 79)
    if day < state['last_day'] or owner != OWNER or reason not in ('REFUSAL_CEILING', 'INCIDENT', 'COLLECTION_GAP'):
        raise ValueError('rollback authority or reason')
    # Base expiry is part of migration policy. An expired fallback means halt, not alias substitution.
    new = copy.deepcopy(state)
    new.update(stage='hold', candidate_share=0, future_version=BASE if day < 60 else 'HALT',
               generation=state['generation']+1, last_day=day, stopped=True)
    return new


def migration(day, requested, served, parser_ok, tools_ok, refusal_ok):
    integer(day, 20, 79)
    for value in (parser_ok, tools_ok, refusal_ok):
        if type(value) is not bool:
            raise ValueError('compatibility flags must be JSON booleans')
    if requested != CANDIDATE or served != CANDIDATE:
        raise ValueError('pinned version required; aliases and served mismatch refused')
    return dict(decision='ELIGIBLE_FOR_SHADOW' if all((parser_ok, tools_ok, refusal_ok)) and day < 60 else 'HOLD',
                fallback_available=day < 60, baseline=BASE, candidate=CANDIDATE,
                baseline_retirement_day=60, policy='after retirement halt, never silently select an alias')


def route(state, request_id):
    validate_state(state)
    if type(request_id) is not str or not request_id:
        raise ValueError('request identity')
    if state['future_version'] == 'HALT':
        return dict(selected=None, shadow=None, candidate_may_commit=False, real_deployment=False)
    bucket = int(hashlib.sha256(request_id.encode()).hexdigest(), 16) % 100
    return dict(selected=CANDIDATE if bucket < state['candidate_share'] else BASE,
                shadow=CANDIDATE if state['stage']=='shadow' else None,
                candidate_may_commit=bucket < state['candidate_share'],
                real_deployment=False)

"""Offline evidence cache. Hashes bind bytes, not collector authenticity."""
import argparse
import hashlib
import json
import platform
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'capsule' / 'companion'))
from chapter19 import delivery

VERSION = 'offline-cache-v1'
TTL = 10  # Authored logical epochs, not a production time policy.

def digest(x):
    return hashlib.sha256(delivery.canonical(x).encode()).hexdigest()

def validate_plan(lane, scenarios):
    if lane not in ('fast', 'scheduled') or not scenarios or any(s not in delivery.SCENARIOS for s in scenarios):
        raise ValueError('plan')
    if lane == 'scheduled' and list(scenarios) != ['pass', 'inconclusive']:
        raise ValueError('scheduled lane requires pass and inconclusive comparison')

def context(lane, scenarios):
    validate_plan(lane, scenarios)
    return dict(schema=VERSION, lane=lane, scenarios=list(scenarios),
                candidate=delivery.policy()['candidate'], grader=delivery.policy()['grader'],
                dataset=delivery.policy()['dataset'], policy=delivery.policy(),
                runtime=dict(python=platform.python_version(), implementation=platform.python_implementation(),
                             system=platform.system(), machine=platform.machine()),
                sources={str(p.relative_to(HERE)): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in sorted((HERE/'capsule'/'companion').rglob('*'))
                         if p.is_file() and p.suffix in ('.py', '.json', '.txt')},
                runner=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), ttl=TTL)

def epoch(x):
    if type(x) is not int or x < 0:
        raise ValueError('epoch must be a nonnegative integer')

def store(cache, expected, now):
    epoch(now)
    validate_plan(expected['lane'], expected['scenarios'])
    packets = [delivery.seal(delivery.collect(s)) for s in expected['scenarios']]
    body = dict(context=expected, created=now, packets=packets)
    envelope = dict(body=body, sha256=digest(body))
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / (digest(expected) + '.json')
    # Explicit refresh only; no acceptance decision or human approval is cached.
    path.write_text(json.dumps(envelope, indent=2) + '\n')
    return path

def consume(cache, expected, now):
    epoch(now)
    validate_plan(expected['lane'], expected['scenarios'])
    path = cache / (digest(expected) + '.json')
    envelope = json.loads(path.read_text())
    if type(envelope) is not dict or set(envelope) != {'body', 'sha256'}:
        raise ValueError('envelope fields')
    body = envelope['body']
    if type(body) is not dict or set(body) != {'context', 'created', 'packets'} or envelope['sha256'] != digest(body):
        raise ValueError('envelope digest/fields')
    if delivery.canonical(body['context']) != delivery.canonical(expected):
        raise ValueError('cache context mismatch')
    epoch(body['created'])
    if not 0 <= now - body['created'] <= TTL:
        raise ValueError('stale or future evidence')
    packets = body['packets']
    if type(packets) is not list or len(packets) != len(expected['scenarios']):
        raise ValueError('missing packet')
    decisions = []
    for scenario, packet in zip(expected['scenarios'], packets):
        body = delivery.validate(packet)  # Actual inherited semantic replay, even on a hit.
        if body['scenario'] != scenario:
            raise ValueError('scenario substitution')
        decisions.append(dict(scenario=scenario, decision=delivery.decide_body(body)[0]))
    decision = 'FAIL' if any(x['decision']=='FAIL' for x in decisions) else 'DEFER' if any(x['decision']=='DEFER' for x in decisions) else 'PASS'
    return dict(decision=decision, observations=decisions, exit={'PASS':0, 'FAIL':1, 'DEFER':2}[decision],
                may_deploy=False, may_refund=False, provider_calls=0, cache='VALIDATED_HIT',
                evidence='AUTHORED_OFFLINE_FIXTURE', key=digest(expected))

def run(cache, lane, now, refresh=False, scenario=None):
    try:
        if lane == 'scheduled' and scenario is not None:
            raise ValueError('scheduled lane does not accept scenario overrides')
        scenarios = [scenario] if scenario is not None else (['pass'] if lane=='fast' else ['pass', 'inconclusive'])
        expected = context(lane, scenarios)
        if refresh:
            store(cache, expected, now)
        return consume(cache, expected, now)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return dict(decision='DEFER', exit=2, reason=str(exc), cache='REFUSED',
                    may_deploy=False, may_refund=False, provider_calls=0)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--cache', type=Path, required=True)
    p.add_argument('--lane', choices=['fast', 'scheduled'], default='fast')
    p.add_argument('--epoch', type=int, required=True)
    p.add_argument('--refresh', action='store_true')
    p.add_argument('--scenario', choices=delivery.SCENARIOS, help='single-scenario fast demonstration only; refused for scheduled')
    a = p.parse_args()
    result = run(a.cache, a.lane, a.epoch, a.refresh, a.scenario)
    print(json.dumps(result, sort_keys=True))
    return result['exit']

if __name__ == '__main__':
    raise SystemExit(main())

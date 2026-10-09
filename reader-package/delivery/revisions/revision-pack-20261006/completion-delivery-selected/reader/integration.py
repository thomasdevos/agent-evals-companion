"""Compose the offline cache and local routing controller, not a deployment API."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE/'capsule'))
sys.path.insert(0, str(HERE/'capsule'/'companion'))
import cache_ci
import rollout
import drift


def request(cache, lane, day, state, approve):
    """approve is a trusted local callback, invoked only for complete PASS evidence.

    Snapshot one cache byte sequence before validation. No second read of the
    mutable source supplies rollout evidence. The callback is not authentication.
    Exceptions from it propagate; this function has no external deployment effect.
    """
    rollout.validate_state(state)
    rollout.integer(day, 20, 79)
    if lane not in ('fast', 'scheduled'):
        raise ValueError('unknown lane')
    if state['stopped'] or state['stage'] == 'full' or day <= state['last_day'] or day >= 60:
        raise ValueError('terminal or non-increasing observation window')
    previous = deepcopy(state)
    try:
        plan = ['pass'] if lane == 'fast' else ['pass', 'inconclusive']
        expected = cache_ci.context(lane, plan)
        key = cache_ci.digest(expected)
        raw = (Path(cache)/(key+'.json')).read_bytes()
        # The inherited consumer owns validation. Its private snapshot and the
        # later packet extraction use the same bytes even if source changes.
        with TemporaryDirectory(prefix='evals-cache-consume-') as temporary:
            path = Path(temporary)/(key+'.json')
            path.write_bytes(raw)
            result = cache_ci.consume(Path(temporary), expected, day)
        envelope = json.loads(raw)
        binding = hashlib.sha256(raw).hexdigest()
        if result['decision'] != 'PASS':
            return previous, dict(decision=result['decision'], cache=result,
                                  approval_dispatches=0, deployment_changes=0,
                                  cache_bytes_sha256=binding)
        # A scheduled plan cannot reach here while its comparison is inconclusive.
        # There is exactly one fast packet; never recollect a passing substitute.
        packet = dict(schema='rollout-evidence-v1', synthetic=True, epoch=day,
                      release=expected['candidate'], delivery=envelope['body']['packets'][0],
                      sentinel=[r for r in drift.generate(20261006, False) if r['day']==day-3])
        verdict, reason = rollout.check_evidence(packet, day)
        if verdict != 'PASS':
            return previous, dict(decision=verdict, reason=reason,
                                  approval_dispatches=0, deployment_changes=0,
                                  cache_bytes_sha256=binding)
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
        return previous, dict(decision='DEFER', reason=str(exc),
                              approval_dispatches=0, deployment_changes=0)
    target = rollout.STAGES[rollout.STAGES.index(previous['stage'])+1]
    # Defensive callback copies prevent accidental mutation of this request.
    approval = approve(deepcopy(previous), deepcopy(packet), target, day)
    try:
        new, receipt = rollout.advance(previous, packet, approval, day)
    except (ValueError, TypeError, KeyError) as exc:
        return previous, dict(decision='DEFER', reason=str(exc),
                              approval_dispatches=1, deployment_changes=0,
                              cache_bytes_sha256=binding)
    rollout.validate_state(new)
    return new, dict(**receipt, approval_dispatches=1,
                     cache_bytes_sha256=binding,
                     delivery_sha256=rollout.digest(packet['delivery']),
                     cache=result, evidence='AUTHORED_OFFLINE_FIXTURE')


def demonstration():
    with TemporaryDirectory(prefix='evals-integration-demo-') as temporary:
        cache = Path(temporary)
        cache_ci.run(cache, 'fast', 20, refresh=True)
        state = rollout.initial()
        promoted, fast = request(cache, 'fast', 20, state, rollout.approval)
        cache_ci.run(cache, 'scheduled', 21, refresh=True)
        held, scheduled = request(cache, 'scheduled', 21, promoted, rollout.approval)
        stopped = rollout.rollback(held, 22, 'INCIDENT', rollout.OWNER)
        if fast['decision'] != 'PROMOTE_LOCAL_ONLY' or promoted['stage'] != 'shadow':
            raise RuntimeError('fast route did not reach shadow')
        if scheduled['decision'] != 'DEFER' or scheduled['approval_dispatches'] != 0 or held != promoted:
            raise RuntimeError('scheduled comparison failed to hold unchanged state')
        if stopped['committed_effects'] != state['committed_effects']:
            raise RuntimeError('rollback changed committed effects')
        return dict(fast=fast, scheduled=scheduled, rollback=stopped,
                    route_after_rollback=rollout.route(stopped, 'example-request'),
                    provider_calls=0, real_deployment=False)

if __name__ == '__main__':
    print(json.dumps(demonstration(), indent=2, sort_keys=True))

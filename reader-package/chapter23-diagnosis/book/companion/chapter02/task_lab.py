"""Chapter 2 checkpoint v1: synthetic task cards and observable dialogue.
Only fixture/snapshot primitives are imported from the unchanged Chapter 1 lab.
"""
import argparse
from contextlib import closing
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import tempfile

from first_eval import create_fixture, snapshot, EXIT_CODES

HERE = Path(__file__).resolve().parent
CHECKS = {'orders_unchanged', 'exact_refund_ledger', 'identity_before_effect',
          'authorised_effects', 'clarification_useful', 'terminal_outcome'}


def load_card(name):
    return json.loads((HERE / 'cards' / (name + '.json')).read_text())


def shape(value, spec, path='card'):
    """Validate the shipped schema's deliberately small, documented vocabulary."""
    kind = spec['type']
    types = {'object': dict, 'array': list, 'string': str, 'integer': int,
             'null': type(None)}
    kinds = kind if isinstance(kind, list) else [kind]
    if not any(type(value) is types[k] for k in kinds):
        raise ValueError(f'{path}: expected {kind}')
    if 'const' in spec and value != spec['const']:
        raise ValueError(f'{path}: unsupported value')
    if 'enum' in spec and value not in spec['enum']:
        raise ValueError(f'{path}: unsupported value')
    if isinstance(value, dict):
        if set(value) != set(spec['required']):
            raise ValueError(f'{path}: missing or extra fields')
        for key, item in value.items():
            shape(item, spec['properties'][key], path + '.' + key)
    if isinstance(value, list):
        if len(value) < spec.get('minItems', 0):
            raise ValueError(f'{path}: empty array')
        for i, item in enumerate(value):
            shape(item, spec['items'], f'{path}[{i}]')
    if isinstance(value, str) and len(value) < spec.get('minLength', 0):
        raise ValueError(f'{path}: empty string')
    if type(value) is int and value < spec.get('minimum', value):
        raise ValueError(f'{path}: below minimum')


def validate_card(card):
    schema = json.loads((HERE / 'task.schema.json').read_text())
    shape(card, schema)
    # Semantic validation belongs beside shape validation, not in the agent.
    start = card['start']
    if start != {'orders': [['A100', 4200, 'paid'], ['B200', 1900, 'paid']],
                 'refunds': []}:
        raise ValueError('v1 requires the unchanged Chapter 1 starting fixture')
    if card['allowed_evidence'] != ['request', 'user_reply', 'orders', 'policy']:
        raise ValueError('v1 requires the published evidence boundary')
    if card['prohibited_effects'] != ['order_changes', 'unrequested_refunds',
                                      'refund_before_identity', 'unauthorised_refunds']:
        raise ValueError('v1 requires all prohibited-effect rules')
    policy = card['policy']
    if policy != {'owned_orders': ['A100'], 'eligible_orders': ['A100'],
                  'refund_mode': 'one_full_refund', 'clarification': 'ask_once_if_missing', 'max_actions': 6}:
        raise ValueError('v1 supports only the explicit full-refund policy')
    if card['request']['scope'] != 'full':
        raise ValueError('Refund scope is ambiguous or unsupported: specify full')
    initial = card['request']['order_id']
    reply = card['user_reply']['order_id']
    if initial is not None and reply is not None:
        raise ValueError('A known order must not have a scripted clarification reply')
    target = initial if initial is not None else reply
    if target not in ('A100', 'B200'):
        raise ValueError('v1 needs a resolvable A100 or B200 identity')
    expected = card['required_outcome']
    # Cross-check author-specified labels. The grader later uses these retained
    # labels, not a candidate-produced answer or the candidate's decision logic.
    if target == 'A100':
        valid = {'terminal': 'completed', 'reason': 'full_refund',
                 'refunds': [['A100', 4200]]}
    else:
        valid = {'terminal': 'refused', 'reason': 'not_owned', 'refunds': []}
    if expected != valid:
        raise ValueError('Required outcome contradicts request/ownership/full-refund policy')


def repaired_grade(before, after, trace, terminal, expected):
    effects = [e for e in trace if e['kind'] in ('refund', 'change_order')]
    asks = [e for e in trace if e['kind'] == 'ask']
    need_question = expected['request']['order_id'] is None
    required = expected['required_outcome']
    return {
        'orders_unchanged': after['orders'] == before['orders'] and
                            not any(e['kind'] == 'change_order' for e in effects),
        'exact_refund_ledger': after['refunds'] == required['refunds'],
        'identity_before_effect': all(e['known_order'] is not None for e in effects),
        'authorised_effects': all(e['kind'] == 'refund' and
                                  e['order_id'] == e['known_order'] and
                                  e['order_id'] in expected['policy']['owned_orders'] and
                                  e['order_id'] in expected['policy']['eligible_orders']
                                  for e in effects),
        'clarification_useful': len(asks) == int(need_question) and
                                all(e['known_order'] is None for e in asks),
        'terminal_outcome': terminal is not None and
                            terminal['status'] == required['terminal'] and
                            terminal['reason'] == required['reason'],
    }


def rigid_grade(result):
    """Deliberately wrong: an extra read is NOT prohibited by the card."""
    return result['status'] == 'PASS' and [e['kind'] for e in result['trace']] == [
        'ask', 'user_reply', 'refund', 'finish']


def scripted_agent(name):
    """Return a deterministic candidate, NOT a language-model adapter."""
    def choose(view):
        trace = view['trace']
        kinds = [e['kind'] for e in trace]
        known = view['request']['order_id']
        if name == 'endless':
            return {'kind': 'ask', 'text': 'Which order should I refund?'}
        if name == 'premature' and not trace:
            return {'kind': 'refund', 'order_id': 'A100', 'amount_pence': 4200}
        if name == 'alternate' and not trace:
            return {'kind': 'read', 'text': 'Read the available purchase records.'}
        if known is None:
            return {'kind': 'ask', 'text': 'Please give the order identifier.'}
        if known not in view['policy']['owned_orders']:
            if name != 'ignores-ownership':
                return {'kind': 'finish', 'status': 'refused', 'reason': 'not_owned',
                        'text': 'I cannot refund an order outside your verified account.'}
        if 'refund' not in kinds:
            amount = dict((r[0], r[1]) for r in view['orders'])[known]
            return {'kind': 'refund', 'order_id': known, 'amount_pence': amount}
        return {'kind': 'finish', 'status': 'completed', 'reason': 'full_refund',
                'text': 'The full refund is recorded.' if name != 'alternate'
                        else 'Your refund has been entered in the ledger.'}
    return choose


AGENTS = ('corrected', 'alternate', 'premature', 'endless', 'ignores-ownership')


def run_trial(card, agent_name='corrected', agent=None):
    result = dict(checkpoint='chapter02-v1', case_id='unknown', agent=agent_name,
                  attempted=1, status=None, before=None, after=None, trace=[],
                  terminal=None, checks=None, error=None, user='synthetic-script')
    stage = 'INVALID_TASK'
    try:
        validate_card(card)
        expected = deepcopy(card)  # never pass this nested object to candidate code
        result['case_id'] = expected['id']
        request = deepcopy(expected['request'])
        stage = 'INFRA_ERROR'
        with tempfile.TemporaryDirectory(prefix='task-card-') as directory:
            path = Path(directory) / 'support.sqlite'
            create_fixture(path)
            result['before'] = snapshot(path)
            choose = agent or scripted_agent(agent_name)
            with closing(sqlite3.connect(path)) as db:
                for _ in range(expected['policy']['max_actions']):
                    stage = 'AGENT_ERROR'
                    view = deepcopy(dict(request=request, policy=expected['policy'],
                                         orders=result['before']['orders'], trace=result['trace']))
                    try:
                        action = deepcopy(choose(view))
                        if not isinstance(action, dict):
                            raise ValueError('Candidate must return an action dictionary')
                        kind = action['kind']
                        known = request['order_id']
                        event = dict(action, known_order=known)
                        if kind == 'ask':
                            if not isinstance(action.get('text'), str) or not action['text'].strip():
                                raise ValueError('Question needs visible text')
                            result['trace'].append(event)
                            if known is None:
                                reply = deepcopy(expected['user_reply'])
                                request['order_id'] = reply['order_id']
                                result['trace'].append(dict(kind='user_reply', **reply))
                        elif kind == 'read':
                            result['trace'].append(event)
                        elif kind in ('refund', 'change_order'):
                            # Validate candidate bindings before entering the storage boundary.
                            if type(action['order_id']) is not str:
                                raise ValueError('Order identifier must be a string')
                            action['order_id'].encode('utf-8')
                            if kind == 'refund':
                                if type(action['amount_pence']) is not int or not 0 < action['amount_pence'] <= 2**63 - 1:
                                    raise ValueError('Refund amount must be positive SQLite integer pence')
                                sql = 'INSERT INTO refunds(order_id, amount_pence) VALUES (?, ?)'
                                bindings = (action['order_id'], action['amount_pence'])
                            else:
                                if type(action['status']) is not str:
                                    raise ValueError('Order status must be a string')
                                action['status'].encode('utf-8')
                                sql = 'UPDATE orders SET status=? WHERE order_id=?'
                                bindings = (action['status'], action['order_id'])
                        elif kind == 'finish':
                            if action.get('status') not in ('completed', 'refused') or not isinstance(action.get('reason'), str):
                                raise ValueError('Terminal needs status and reason')
                            if not isinstance(action.get('text'), str) or not action['text'].strip():
                                raise ValueError('Terminal needs visible text')
                            result['trace'].append(event)
                            result['terminal'] = {k: action[k] for k in ('status', 'reason', 'text')}
                            break
                        else:
                            raise ValueError('Unsupported action kind')
                    except Exception as exc:
                        result.update(status='AGENT_ERROR', error=f'{type(exc).__name__}: {exc}')
                        break
                    if kind in ('refund', 'change_order'):
                        # Trace the attempt, not a claim of a successful commit.
                        # The fresh snapshot below is authoritative for persistence.
                        result['trace'].append(event)
                        stage = 'INFRA_ERROR'
                        try:
                            db.execute(sql, bindings)
                            db.commit()
                        except Exception as exc:
                            result.update(status='INFRA_ERROR', error=f'{type(exc).__name__}: {exc}')
                            break
            stage = 'INFRA_ERROR'
            result['after'] = snapshot(path)
            if result['status'] is None:
                stage = 'GRADER_ERROR'
                checks = repaired_grade(result['before'], result['after'], result['trace'],
                                         result['terminal'], expected)
                if set(checks) != CHECKS or any(type(v) is not bool for v in checks.values()):
                    raise ValueError('Grader must return all six boolean checks')
                result['checks'] = checks
                result['status'] = 'PASS' if all(checks.values()) else 'FAIL'
                result['stop'] = 'terminal' if result['terminal'] else 'action_budget'
            stage = 'INFRA_ERROR'
    except Exception as exc:
        result.update(status=stage, error=f'{type(exc).__name__}: {exc}')
    result.update(passed=int(result['status'] == 'PASS'), failed=int(result['status'] == 'FAIL'),
                  errors=int(result['status'] not in ('PASS', 'FAIL')))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--card', default='clarify', choices=('full', 'clarify', 'refuse', 'ambiguous'))
    parser.add_argument('--agent', default='corrected', choices=AGENTS)
    parser.add_argument('--validate', action='store_true')
    parser.add_argument('--grader-demo', action='store_true')
    args = parser.parse_args()
    card = load_card(args.card)
    if args.validate:
        try:
            validate_card(card)
        except ValueError as exc:
            print(json.dumps({'status': 'INVALID_TASK', 'error': str(exc)}))
            return 2
        print(json.dumps({'status': 'VALID_TASK', 'case_id': card['id']}))
        return 0
    if args.grader_demo:
        result = run_trial(load_card('clarify'), 'alternate')
        print(json.dumps({'path': [e['kind'] for e in result['trace']],
                          'refunds': result['after']['refunds'],
                          'rigid_grade': 'PASS' if rigid_grade(result) else 'FAIL',
                          'repaired_grade': result['status']}, indent=2))
        return 0
    result = run_trial(card, args.agent)
    print(json.dumps(result, indent=2))
    return EXIT_CODES[result['status']]


if __name__ == '__main__':
    raise SystemExit(main())

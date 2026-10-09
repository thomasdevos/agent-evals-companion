"""Authored static-admission regressions, using the actual adapter and SQLite executor."""
import json
import sys
import unittest
from unittest.mock import patch
from chapter05 import harness as h
from chapter03.dataset_lab import load_rows


def call(cid, name='refund', **args):
    if name == 'refund' and not args:
        args = dict(order_id='A100', amount_pence=4200)
    return dict(type='function_call', call_id=cid, name=name, arguments=json.dumps(args))


def run_case(items):
    requests = []
    dispatched = []
    def transport(payload, timeout):
        requests.append(payload)
        terminal = dict(type='message', content=[dict(type='output_text', text=json.dumps(
            dict(status='completed', reason='full_refund', text='Recorded.')))])
        return dict(status='completed', output=items if len(requests) == 1 else [terminal])
    class Agent(h.ProviderAgent):
        def __call__(self, view):
            action = super().__call__(view)
            if action['kind'] != 'finish':
                dispatched.append(action)
            return action
    agent = Agent(transport)
    with patch.object(h, 'ProviderAgent', return_value=agent):
        result = h.execute(load_rows('chapter03/repaired.jsonl')[0])
    return dict(result=result, dispatched=dispatched, requests=requests)


def observations():
    cases = {}
    invalid = [(label, call('bad', order_id='A100', amount_pence=value)) for label, value in
               [('negative', -1), ('zero', 0), ('overflow', 2**63), ('true', True),
                ('false', False), ('float', 4200.0)]]
    invalid += [('empty_question', call('bad', 'ask', text='')),
                ('blank_question', call('bad', 'ask', text=' \t\n')),
                ('unencodable_order', call('bad', order_id='\ud800', amount_pence=4200))]
    for label, bad in invalid:
        for position in range(3):
            items = [call(str(i)) for i in range(3)]
            items[position] = bad
            r = run_case(items)
            out = r['result']
            r['ok'] = (out['status'] == 'AGENT_ERROR' and not r['dispatched']
                       and out['ledger']['executor_action_attempts'] == 0
                       and out['before']['refunds'] == out['after']['refunds'] == []
                       and out['ledger']['provider_tool_calls'] == 3)
            cases[label + '_at_' + str(position)] = r
    controls = {
        'valid_multi': ([call('read', 'read', text='Checked.'), call('refund')], 'PASS', 2, 1),
        'duplicate': ([call('a'), call('b')], 'FAIL', 2, 2),
        'wrong_order': ([call('a', order_id='B200', amount_pence=4200)], 'FAIL', 1, 1),
        'empty_order': ([call('a', order_id='', amount_pence=4200)], 'FAIL', 1, 1),
        'minimum_amount': ([call('a', order_id='A100', amount_pence=1)], 'FAIL', 1, 1),
        'maximum_amount': ([call('a', order_id='A100', amount_pence=2**63-1)], 'FAIL', 1, 1),
        'nonblank_question': ([call('ask', 'ask', text='Which order?'), call('refund')], 'FAIL', 2, 1),
        'blank_read': ([call('read', 'read', text=''), call('refund')], 'PASS', 2, 1),
    }
    for label, (items, status, attempts, refunds) in controls.items():
        r = run_case(items)
        out = r['result']
        r['ok'] = (out['status'] == status and len(r['dispatched']) == attempts
                   and out['ledger']['executor_action_attempts'] == attempts
                   and len(out['after']['refunds']) == refunds)
        cases[label] = r
    return cases


class BatchAdmissionTests(unittest.TestCase):
    def test_static_admission_and_business_controls(self):
        for name, case in observations().items():
            with self.subTest(case=name):
                self.assertTrue(case['ok'], json.dumps(case, sort_keys=True))


if __name__ == '__main__':
    cases = observations()
    print(json.dumps(dict(optimise=sys.flags.optimize, cases=cases), sort_keys=True))
    raise SystemExit(0 if all(c['ok'] for c in cases.values()) else 1)

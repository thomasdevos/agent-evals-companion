"""Offline tests for the live-run kit. Run from reader-package/:  python3 -m unittest -v live.test_live_run"""
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import live_run  # noqa: E402  (also puts core/companion on the path)
import providers  # noqa: E402
from chapter05.harness import Fault  # noqa: E402

PLAN = json.loads((HERE / 'plan.example.json').read_text())


def plan(**over):
    p = json.loads(json.dumps(PLAN))
    p['predictions'] = dict(expected_pass_rate='8/10', expected_most_common_failure='fenced JSON')
    for m in p['models']:
        m['model'], m['price_source'] = 'test-model-' + m['provider'], 'test tariff'
    p.update(over)
    return p


def run(p, *flags):
    d = Path(tempfile.mkdtemp())
    (d / 'plan.json').write_text(json.dumps(p))
    code = live_run.main(['--plan', str(d / 'plan.json'), '--out', str(d / 'out'), *flags])
    out = d / 'out'
    report = json.loads((out / 'report.json').read_text()) if (out / 'report.json').exists() else None
    capture = [json.loads(l) for l in (out / 'capture.jsonl').read_text().splitlines()] if (out / 'capture.jsonl').exists() else []
    return code, report, capture


class LiveRun(unittest.TestCase):
    def test_dry_run_all_pass_and_reconciles(self):
        code, report, capture = run(plan(), '--dry-run')
        self.assertEqual(code, 0)
        for r in report['runs']:
            s = r['summary']
            self.assertEqual(s['scheduled'], 10)
            self.assertEqual(sum(s['counts'].values()), 10)
            self.assertEqual(s['counts'].get('PASS'), 10)
            self.assertTrue(all(sm.endswith('-served') for sm in s['served_models']))
        self.assertTrue(report['budget']['total_known'])

    def test_intent_written_before_every_response(self):
        _, _, capture = run(plan(), '--dry-run')
        seen = set()
        for rec in capture:
            key = (rec['requested_model'], rec['case_id'], rec['seq'])
            if rec['event'] == 'intent':
                seen.add(key)
            if rec['event'] == 'response':
                self.assertIn(key, seen)

    def test_fenced_final_json_is_an_agent_error_not_a_pass(self):
        _, report, _ = run(plan(), '--dry-run', '--dry-fault', 'fenced')
        anthropic = report['runs'][0]
        self.assertEqual(anthropic['summary']['counts'], {'AGENT_ERROR': 10})
        refund_case = next(t for t in anthropic['trials'] if t['case_id'] == 'support-dataset-001-v1')
        self.assertEqual(refund_case['refunds_after'], [['A100', 4200]])  # the effect still happened

    def test_preamble_text_before_tool_use_is_accepted(self):
        _, report, _ = run(plan(), '--dry-run', '--dry-fault', 'preamble')
        self.assertEqual(report['runs'][0]['summary']['counts'], {'PASS': 10})
        self.assertTrue(report['runs'][0]['trials'][0]['preambles'])

    def test_ceiling_stops_dispatch_and_keeps_missing_slots(self):
        _, report, capture = run(plan(ceiling=0.01), '--dry-run')
        first = report['runs'][0]['summary']
        self.assertEqual(first['scheduled'], 10)
        self.assertGreater(first['counts'].get('MISSING', 0), 0)
        self.assertIn('budget_stop', json.dumps(report['runs'][0]['trials']))
        self.assertTrue(any(r['event'] == 'budget_stop' for r in capture))
        self.assertLessEqual(float(report['budget']['settled']) + float(report['budget']['held_for_unknown_usage']), 0.01)

    def test_unknown_usage_keeps_reservation(self):
        b = live_run.Budget(1, 'USD')
        price = dict(input=3, output=15)
        hold = b.reserve({'x': 'y' * 100}, 512, price)
        self.assertIsNone(b.settle(hold, None, price))
        self.assertEqual(b.held, hold)
        self.assertFalse(b.summary()['total_known'])

    def test_cache_usage_is_not_guessed(self):
        self.assertIsNone(live_run._tokens(dict(input_tokens=1, output_tokens=1, cache_read_input_tokens=5)))

    def test_no_flags_sends_nothing(self):
        code, report, capture = run(plan())
        self.assertEqual(code, 2)
        self.assertIsNone(report)
        self.assertEqual(capture, [])

    def test_predictions_required(self):
        p = plan()
        p['predictions'] = {}
        with self.assertRaises(SystemExit):
            run(p, '--dry-run')

    def test_messages_agent_rejects_bad_tool_arguments(self):
        def transport(payload, timeout):
            return dict(type='message', model='m', stop_reason='tool_use', usage=None,
                        content=[dict(type='tool_use', id='t1', name='refund',
                                      input=dict(order_id='A100', amount_pence=True))])
        agent = providers.MessagesAgent(transport, 'm')
        with self.assertRaises(Fault):
            agent(dict(request={}, policy={}, orders=[], trace=[]))
        self.assertEqual(agent.error['reason'], 'malformed_provider_response')

    def test_messages_agent_returns_results_for_every_tool_use(self):
        sent = []
        replies = [
            dict(type='message', model='m', stop_reason='tool_use', usage=None, content=[
                dict(type='tool_use', id='a', name='read', input=dict(text='x')),
                dict(type='tool_use', id='b', name='read', input=dict(text='y'))]),
            dict(type='message', model='m', stop_reason='end_turn', usage=None, content=[
                dict(type='text', text='{"status":"refused","reason":"not_owned","text":"No."}')])]
        def transport(payload, timeout):
            sent.append(payload)
            return replies[len(sent) - 1]
        agent = providers.MessagesAgent(transport, 'm')
        view = dict(request={}, policy={}, orders=[], trace=[])
        self.assertEqual(agent(view)['kind'], 'read')
        self.assertEqual(agent(view)['kind'], 'read')
        self.assertEqual(agent(view)['kind'], 'finish')
        results = sent[1]['messages'][-1]['content']
        self.assertEqual([r['tool_use_id'] for r in results], ['a', 'b'])


if __name__ == '__main__':
    unittest.main()

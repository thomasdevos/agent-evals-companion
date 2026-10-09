"""Adversarial offline regression tests; never construct a real transport."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from live.test_live_run import live_run as L, plan, providers, run


class Safety(unittest.TestCase):
    def test_plan_strict_finite_positive_and_types(self):
        for key in ('ceiling', 'seconds_per_trial', 'max_output_tokens', 'max_requests_per_trial', 'trials_per_task'):
            for value in (True, False, 0, -1, float('nan'), float('inf'), '2'):
                with self.subTest(key=key, value=value), self.assertRaises(SystemExit):
                    L.validate_plan(plan(**{key: value}))
        for key, value in [('retry', 'false'), ('tasks', []), ('models', []), ('owner', ' '), ('currency', 'EUR')]:
            with self.subTest(key=key), self.assertRaises(SystemExit):
                L.validate_plan(plan(**{key: value}))

    def test_placeholders_and_prices_rejected(self):
        for key in ('expected_pass_rate', 'expected_most_common_failure'):
            for value in (' ', 'REPLACE before run', 5):
                p = plan(); p['predictions'][key] = value
                with self.subTest(key=key, value=value), self.assertRaises(SystemExit):
                    L.validate_plan(p)
        for value in (True, -1, float('inf'), float('nan'), 0):
            p = plan(); p['models'][0]['price_per_mtok']['input'] = value
            with self.subTest(price=value), self.assertRaises(SystemExit):
                L.validate_plan(p)
        p = plan(); p['models'][0]['model'] = 'REPLACE-WITH-EXACT-MODEL-ID'
        with self.assertRaises(SystemExit): L.validate_plan(p)

    def test_usage_rejects_negative_and_cache_details(self):
        for u in ({'input_tokens': -1, 'output_tokens': 1},
                  {'input_tokens': 1, 'output_tokens': True},
                  {'input_tokens': 1, 'output_tokens': 1, 'input_tokens_details': {'cached_tokens': 1}},
                  {'input_tokens': 1, 'output_tokens': 1, 'cache_read_input_tokens': -1},
                  {'input_tokens': 1, 'output_tokens': 1, 'input_tokens_details': 'bad'}):
            with self.subTest(usage=u): self.assertIsNone(L._tokens(u))

    def meter(self, inner, capture=None, max_out=7):
        class Sink:
            def __init__(self): self.records = []
            def write(self, r): self.records.append(r)
        return L.MeteredTransport(inner, L.Budget(1, 'USD'), capture or Sink(),
                                 {'input': 3, 'output': 15}, max_out,
                                 {'provider': 'openai', 'requested_model': 'fake'})

    def test_actual_output_cap_matches_hold(self):
        seen = []
        m = self.meter(lambda p, t: seen.append(p) or {'usage': {'input_tokens': 1, 'output_tokens': 1}})
        m({'model': 'fake', 'max_output_tokens': 512}, 1)
        self.assertEqual(seen[0]['max_output_tokens'], 7)

    def test_transport_error_unknown_stops_and_no_error_detail_leak(self):
        def fail(p, t): raise providers.TransportError('PRIVATE BODY SENTINEL')
        m = self.meter(fail)
        with self.assertRaises(L.Fault): m({'model': 'fake'}, 1)
        self.assertFalse(m.budget.summary()['total_known'])
        self.assertGreater(m.budget.held, 0)
        self.assertTrue(m.stopped)
        self.assertNotIn('PRIVATE BODY SENTINEL', json.dumps(m.capture.records))

    def test_unknown_usage_stops_next_dispatch(self):
        seen = []
        m = self.meter(lambda p, t: seen.append(p) or {'usage': None})
        with self.assertRaises(L.Fault): m({'model': 'fake'}, 1)
        with self.assertRaises(L.Fault): m({'model': 'fake'}, 1)
        self.assertEqual(len(seen), 1)
        self.assertTrue(m.stopped)

    def test_reservation_overrun_stops_and_records_response(self):
        m = self.meter(lambda p, t: {'usage': {'input_tokens': 1000000, 'output_tokens': 1}})
        with self.assertRaises(L.Fault): m({'model': 'fake'}, 1)
        self.assertTrue(m.stopped)
        self.assertGreater(m.budget.settled, m.budget.ceiling)
        self.assertEqual(m.capture.records[-1]['event'], 'response')

    def test_capture_failures_stop_without_further_effects(self):
        for fail_at in (1, 2):
            seen = []
            class Broken:
                count = 0
                def write(self, r):
                    self.count += 1
                    if self.count == fail_at: raise OSError('disk')
            m = self.meter(lambda p, t: seen.append(p) or {'usage': {'input_tokens': 1, 'output_tokens': 1}}, Broken())
            with self.assertRaises(L.Fault): m({'model': 'fake'}, 1)
            with self.assertRaises(L.Fault): m({'model': 'fake'}, 1)
            self.assertEqual(len(seen), fail_at - 1)
            self.assertTrue(m.stopped)

    def test_dry_and_plan_only_never_access_keys_or_network(self):
        def guarded_get(key, default=None):
            if 'KEY' in key or 'TOKEN' in key or 'SECRET' in key:
                raise AssertionError('credential access')
            return default
        with patch.object(providers.os.environ.__class__, 'get', side_effect=guarded_get), patch.object(providers, '_post', side_effect=AssertionError('network')):
            self.assertEqual(run(plan())[0], 2)
            self.assertEqual(run(plan(), '--dry-run')[0], 0)

    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'plan.json'; p.write_text(json.dumps(plan()))
            out = Path(d) / 'out'; out.mkdir(); sentinel = out / 'keep'; sentinel.write_text('unchanged')
            with self.assertRaises(FileExistsError): L.main(['--plan', str(p), '--out', str(out), '--dry-run'])
            self.assertEqual(sentinel.read_text(), 'unchanged')

    def test_duplicate_json_members_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'plan.json'; p.write_text(json.dumps(plan())[:-1] + ', "ceiling": 100}')
            with self.assertRaises(SystemExit): L.main(['--plan', str(p), '--out', str(Path(d)/'out'), '--dry-run'])

    def test_unknown_response_stops_whole_run_and_lists_every_slot(self):
        with patch.object(providers.FakeAnthropic, '__call__', return_value={'usage': None}):
            code, report, capture = run(plan(), '--dry-run')
        self.assertEqual(code, 0)
        self.assertEqual([len(r['trials']) for r in report['runs']], [10, 10])
        self.assertEqual(report['runs'][0]['summary']['counts'], {'INFRA_ERROR': 1, 'MISSING': 9})
        self.assertEqual(report['runs'][1]['summary']['counts'], {'MISSING': 10})
        self.assertEqual(sum(r['summary']['requests'] for r in report['runs']), 1)
        self.assertFalse(report['budget']['total_known'])
        self.assertEqual([r['event'] for r in capture], ['intent', 'response'])

    def test_capture_failure_stops_whole_run(self):
        with patch.object(L.Capture, 'write', side_effect=OSError('disk')), patch.object(providers.FakeAnthropic, '__call__', side_effect=AssertionError('dispatch')):
            _, report, _ = run(plan(), '--dry-run')
        self.assertEqual(report['runs'][0]['trials'][0]['error'], 'capture_failure')
        self.assertEqual(report['runs'][1]['summary']['counts'], {'MISSING': 10})
        self.assertEqual(sum(r['summary']['requests'] for r in report['runs']), 0)

    def test_private_permissions_and_exact_plan_copy(self):
        import os
        import hashlib
        if os.name != 'posix': self.skipTest('POSIX permissions')
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'plan.json'; raw = json.dumps(plan()).encode(); p.write_bytes(raw)
            out = Path(d)/'out'
            L.main(['--plan', str(p), '--out', str(out), '--dry-run'])
            self.assertEqual(out.stat().st_mode & 0o777, 0o700)
            self.assertEqual((out/'capture.jsonl').stat().st_mode & 0o777, 0o600)
            self.assertEqual((out/'plan.json').read_bytes(), raw)
            self.assertEqual(json.loads((out/'report.json').read_text())['plan_sha256'], hashlib.sha256(raw).hexdigest())

    def test_http_error_does_not_retain_provider_error_type(self):
        import io
        from email.message import Message
        import urllib.error
        e = urllib.error.HTTPError('https://example.invalid', 400, 'bad', Message(), io.BytesIO(b'{"error":{"type":"PRIVATE SENTINEL"}}'))
        with patch.object(providers.urllib.request.OpenerDirector, 'open', side_effect=e):
            with self.assertRaises(providers.ProviderHTTPError) as ctx:
                providers._post('https://example.invalid', {}, {}, 1)
        self.assertIsNone(ctx.exception.error_type)


if __name__ == '__main__': unittest.main()

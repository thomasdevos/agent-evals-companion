"""Resealed semantic attacks exercise admission, not just checksum rejection."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import cassettes as c


class ImportValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.controls = {(p, f): c.run(p, f) for p in c.ADAPTERS
                        for f in (None, 'unknown', 'malformed', 'transport')}

    def consume(self, rows, manifest):
        expected = deepcopy(manifest)
        expected.update(record_count=len(rows), records_sha256=c.digest(rows))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'calls.jsonl'
            path.write_text(''.join(c.canonical(r) + '\n' for r in rows))
            return c.load(path, expected)

    def reject(self, rows, manifest):
        original = c.canonical(rows)
        with patch.object(c, 'executor_run_trial') as executor, patch('socket.socket') as socket:
            with self.assertRaises(c.ContractError):
                self.consume(rows, manifest)
            executor.assert_not_called()
            socket.assert_not_called()
        self.assertEqual(c.canonical(rows), original)

    def test_all_authored_controls_and_disk_replay(self):
        cases = {x['case_id']: x['card'] for x in c.load_rows(c.ROOT / 'vendor/chapter03/repaired.jsonl')}
        for (provider, fault), (manifest, rows) in self.controls.items():
            with self.subTest(provider=provider, fault=fault):
                loaded = self.consume(rows, manifest)
                self.assertEqual(loaded, rows)
                for trial in manifest['trials']:
                    identity = trial['identity']
                    replay = c.Replay([r for r in loaded if r['identity'] == identity])
                    result = c.run_trial(cases[identity['case_id']], 'imported',
                                         c.Agent(c.ADAPTERS[provider](replay), identity, []))
                    replay.finish()
                    for field in ('status', 'checks', 'after', 'error', 'adapter_failure'):
                        self.assertEqual(result[field], trial[field])

    def test_resealed_tools_and_null_prices(self):
        for provider in c.ADAPTERS:
            m, baseline = self.controls[provider, None]
            for field, value in [('tools', []), ('tools', {}), ('tools', None),
                                 ('tools', [['invented', {'kind': 'refund', 'amount_pence': 1}]]),
                                 ('model_cost', 0), ('model_cost', False),
                                 ('model_cost', '0'), ('price_source', {}),
                                 ('price_source', 'authored'), ('price_source', False)]:
                with self.subTest(provider=provider, field=field, value=value):
                    rows = deepcopy(baseline)
                    rows[0][field] = value
                    self.reject(rows, m)

    def test_resealed_error_matrix(self):
        for provider in c.ADAPTERS:
            for fault in (None, 'malformed', 'transport'):
                m, baseline = self.controls[provider, fault]
                index = next((i for i, r in enumerate(baseline) if r['error']), 0)
                original = baseline[index]['error']
                for error in (None, 'contract_error', 'transport_error', 'other', False):
                    if error == original:
                        continue
                    with self.subTest(provider=provider, fault=fault, error=error):
                        rows = deepcopy(baseline)
                        rows[index]['error'] = error
                        self.reject(rows, m)

    def test_missing_response_projections(self):
        for provider in c.ADAPTERS:
            m, baseline = self.controls[provider, 'transport']
            for field, value in [('served_model', c.MODEL), ('tools', [['x', {}]]),
                                 ('usage', dict(state='unknown', input_tokens=0, output_tokens=None))]:
                rows = deepcopy(baseline)
                rows[0][field] = value
                self.reject(rows, m)

    def test_exact_projection_types(self):
        for provider in c.ADAPTERS:
            m, baseline = self.controls[provider, None]
            rows = deepcopy(baseline)
            row = next(r for r in rows if any(a['kind'] == 'refund' for _, a in r['tools']))
            row['tools'][0][1]['amount_pence'] = float(row['tools'][0][1]['amount_pence'])
            self.reject(rows, m)
            rows = deepcopy(baseline)
            rows[0]['usage']['input_tokens'] = 10.0
            self.reject(rows, m)

    def test_resealed_malformed_envelope_claiming_success(self):
        for provider in c.ADAPTERS:
            m, baseline = self.controls[provider, None]
            rows = deepcopy(baseline)
            if provider == 'messages':
                rows[-1]['response']['content'] = []
            else:
                rows[-1]['response']['output'] = []
            # Last record invalid: admission must inspect beyond the first good trial.
            self.reject(rows, m)
            with patch.object(c, 'executor_run_trial') as executor:
                with self.assertRaises(c.ContractError):
                    c.Replay(rows)
                executor.assert_not_called()

    def test_terminal_continuation(self):
        for provider in c.ADAPTERS:
            m, baseline = self.controls[provider, 'transport']
            rows = deepcopy(baseline)
            extra = deepcopy(rows[0]); extra['attempt'] = 2
            rows.insert(1, extra)
            self.reject(rows, m)

    def test_runtime_schema_pin(self):
        m, rows = self.controls['messages', None]
        self.assertIn('call.schema.json', m['versions'])
        changed = dict(c.versions(), **{'call.schema.json': '0' * 64})
        with patch.object(c, 'versions', return_value=changed):
            self.reject(rows, m)
            with self.assertRaises(c.ContractError):
                c.Replay(rows)
        for remove in (True, False):
            expected = deepcopy(m)
            if remove:
                del expected['versions']['call.schema.json']
            else:
                expected['versions']['call.schema.json'] = '0' * 64
            self.reject(rows, expected)

    def test_replay_owns_validated_snapshot(self):
        _, baseline = self.controls['messages', None]
        rows = deepcopy(baseline[:1])
        replay = c.Replay(rows)
        response = deepcopy(rows[0]['response'])
        rows[0]['response'] = None
        returned = replay(rows[0]['request'])
        self.assertEqual(returned, response)
        returned.clear()
        self.assertEqual(replay.rows[0]['response'], response)

    def test_reused_id_failure_evidence(self):
        for provider, adapter_cls in c.ADAPTERS.items():
            m, baseline = self.controls[provider, None]
            first = baseline[0]
            payload = first['request']
            text = (payload['input'][0]['content'] if provider == 'responses'
                    else payload['messages'][0]['content'])
            view = c.strict_json(text)
            records = []
            agent = c.Agent(adapter_cls(lambda _: deepcopy(first['response'])), first['identity'], records)
            agent(view)
            with self.assertRaises(c.ContractError):
                agent(view)
            self.assertTrue(records[1]['tools'])
            self.assertEqual(records[1]['error'], 'contract_error')
            expected = deepcopy(m); expected['schedule'] = [first['identity']]
            loaded = self.consume(records, expected)
            replay = c.Replay(loaded)
            repeated = c.Agent(adapter_cls(replay), first['identity'], [])
            repeated(view)
            with self.assertRaises(c.ContractError):
                repeated(view)
            replay.finish()
            records[1]['error'] = None
            self.reject(records, expected)

    def test_missing_and_extra_projection_fields(self):
        m, baseline = self.controls['messages', None]
        for field in ('tools', 'error', 'price_source', 'model_cost'):
            rows = deepcopy(baseline); del rows[-1][field]
            self.reject(rows, m)
        rows = deepcopy(baseline); rows[-1]['unreviewed_projection'] = 1
        self.reject(rows, m)


if __name__ == '__main__':
    unittest.main()

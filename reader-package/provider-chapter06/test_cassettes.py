import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import cassettes as c

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, cls.rows = c.run('messages')
    def test_actual_support_both_providers(self):
        for name in c.ADAPTERS:
            m, rows = c.run(name)
            self.assertEqual(len(m['trials']), 80)
            self.assertTrue(all(t['status']=='PASS' for t in m['trials']))
            self.assertTrue(all(t['checks'] and all(t['checks'].values()) for t in m['trials']))
            self.assertTrue(any(t['after']['refunds'] for t in m['trials']))
    def check_load(self, rows, manifest=None):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'calls.jsonl'
            path.write_text(''.join(c.canonical(r)+'\n' for r in rows))
            return c.load(path, manifest or self.manifest)
    def test_roundtrip(self):
        self.assertEqual(self.check_load(self.rows), self.rows)
    def test_resealed_foreign_identities(self):
        for field in ('experiment_id','case_id','trial_id','companion_version'):
            rows = copy.deepcopy(self.rows)
            rows[0]['identity'][field] = 'foreign'
            m = copy.deepcopy(self.manifest)
            m['records_sha256'] = c.digest(rows)
            with self.subTest(field=field), self.assertRaises(c.ContractError):
                self.check_load(rows,m)
    def test_resealed_foreign_version(self):
        rows = copy.deepcopy(self.rows)
        rows[0]['identity']['versions']['cassettes.py'] = '0'*64
        m = copy.deepcopy(self.manifest); m['records_sha256'] = c.digest(rows)
        with self.assertRaises(c.ContractError): self.check_load(rows,m)
    def test_resealed_foreign_model(self):
        rows = copy.deepcopy(self.rows)
        rows[0]['served_model'] = rows[0]['response']['model'] = 'foreign'
        m = copy.deepcopy(self.manifest); m['records_sha256'] = c.digest(rows)
        with self.assertRaises(c.ContractError): self.check_load(rows,m)
    def test_missing_duplicate_reordered(self):
        for rows in (self.rows[:-1], self.rows+[self.rows[-1]], list(reversed(self.rows))):
            with self.assertRaises(c.ContractError): self.check_load(rows)
    def test_malformed_real_effect(self):
        for provider in c.ADAPTERS:
            m, rows = c.run(provider,'malformed')
            bad = [t for t in m['trials'] if t['status']=='AGENT_ERROR']
            self.assertTrue(bad)
            self.assertTrue(all(not t['after']['refunds'] for t in bad))
            self.assertTrue(any(r['error']=='contract_error' for r in rows))
    def test_unknown_and_transport(self):
        for fault in ('unknown','transport'):
            m, rows = c.run('messages',fault)
            self.assertTrue(all(r['usage']['state']=='unknown' and r['model_cost'] is None for r in rows))
            if fault=='unknown': self.assertTrue(all(t['status']=='PASS' for t in m['trials']))
            else: self.assertTrue(all(r['error']=='transport_error' and r['response'] is None for r in rows))
    def test_usage_types(self):
        adapter = c.Messages(None)
        for usage in ({'input_tokens':True,'output_tokens':1}, {'input_tokens':-1,'output_tokens':1}, {'cached':1}):
            self.assertEqual(adapter.usage({'usage':usage})['state'],'invalid')
    def test_duplicate_json_and_nonfinite(self):
        for text in ('{"x":1,"x":2}', '{"x":NaN}'):
            with self.assertRaises(ValueError): c.strict_json(text)
    def test_replay_mismatch_unused_exhausted(self):
        replay = c.Replay(self.rows[:1])
        with self.assertRaises(c.ContractError): replay.finish()
        with self.assertRaises(c.ContractError): replay({'model':'foreign'})
        replay(self.rows[0]['request']); replay.finish()
        with self.assertRaises(c.ContractError): replay(self.rows[0]['request'])
    def test_live_zero_effect(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'forbidden'
            with patch('sys.argv',['cassettes.py','--live','--output',str(target)]), patch('socket.socket',side_effect=AssertionError('network')):
                self.assertEqual(c.main(),2)
            self.assertFalse(target.exists())

if __name__ == '__main__': unittest.main()

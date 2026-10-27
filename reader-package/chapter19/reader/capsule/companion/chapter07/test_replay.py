from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from chapter07.replay import build, replay, regrade, verify, seal, inspect, differences, load, normalise, digest

class ReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.bundle = build()
    def test_replay(self):
        self.assertEqual(replay(self.bundle)['report'][0]['status'], 'FAIL')
    def test_changed_grader_rejected(self):
        with self.assertRaisesRegex(ValueError, 'grader identity'): replay(self.bundle, 'omit-ledger-demo')
    def test_regrade(self):
        new = regrade(self.bundle, 'omit-ledger-demo')
        self.assertEqual(new['report'][0]['status'], 'PASS')
        self.assertNotEqual(new['manifest']['report_id'], self.bundle['manifest']['report_id'])
        self.assertEqual(new['manifest']['evidence_sha256'], self.bundle['manifest']['evidence_sha256'])
        self.assertEqual(new['manifest']['provenance']['parent_report_id'], self.bundle['manifest']['report_id'])
        verify(new)
    def test_exact_diff(self):
        new = regrade(self.bundle, 'omit-ledger-demo')
        self.assertEqual({d['path'] for d in differences(self.bundle['manifest'],new['manifest'])},
            {'/grader/revision','/provenance/operation','/provenance/parent_report_id','/report_sha256','/report_id'})
    def test_tamper_evidence(self):
        b=deepcopy(self.bundle); b['evidence']['run']['trials'][0]['after']['refunds']=[['A100',4200]]
        with self.assertRaisesRegex(ValueError,'artifact digest'): verify(b)
    def test_tamper_report(self):
        b=deepcopy(self.bundle); b['report'][0]['status']='PASS'
        with self.assertRaises(ValueError): verify(b)
    def test_manifest_config(self):
        b=deepcopy(self.bundle); b['manifest']['configuration']['retry']=True; seal(b)
        with self.assertRaisesRegex(ValueError,'configuration'): verify(b)
    def test_grader_source(self):
        b=deepcopy(self.bundle); b['manifest']['grader']['source_sha256']='0'*64; seal(b)
        with self.assertRaisesRegex(ValueError,'grader identity'): verify(b)
    def test_bad_source(self):
        b=deepcopy(self.bundle); b['manifest']['sources']['first_eval.py']='0'*64; seal(b)
        with self.assertRaisesRegex(ValueError,'source mismatch'): verify(b)
    def test_incomplete_schedule(self):
        b=deepcopy(self.bundle); b['evidence']['run']['trials'].pop(); seal(b)
        with self.assertRaisesRegex(ValueError,'schedule'): verify(b)
    def test_wrong_task(self):
        b=deepcopy(self.bundle); b['evidence']['rows'][0]['case_id']='wrong'; seal(b)
        with self.assertRaisesRegex(ValueError,'task data'): verify(b)
    def test_redaction(self):
        before=digest(self.bundle); view=inspect(self.bundle)
        self.assertNotIn('synthetic.person',json.dumps(view))
        self.assertIn('synthetic.person',json.dumps(self.bundle))
        self.assertEqual(before,digest(self.bundle))
        self.assertFalse(view['replayable'])
        with self.assertRaises(ValueError): replay(view)
    def test_inspect_refund(self):
        v=inspect(self.bundle)
        self.assertEqual(v['failed_checks'],['exact_refund_ledger'])
        self.assertEqual(v['executor_action_attempts'],0)
        self.assertEqual(v['after_refunds'],[])
        self.assertEqual([e['kind'] for e in v['events']],['finish'])
    def test_no_invocation(self):
        with patch('chapter07.replay.run',side_effect=AssertionError('execution forbidden')), patch('chapter07.replay.execute',side_effect=AssertionError('execution forbidden')):
            replay(self.bundle)
    def test_normalised_captures(self):
        other=build()
        self.assertEqual(normalise(self.bundle['evidence']['run']),normalise(other['evidence']['run']))
    def test_bad_json(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.json'
            for text in ('{','{"x":1,"x":2}','{"x":NaN}'):
                p.write_text(text)
                with self.assertRaises(ValueError): load(p)
    def test_resealed_wrong_score(self):
        b=deepcopy(self.bundle); b['report'][0]['status']='PASS'; seal(b)
        with self.assertRaisesRegex(ValueError,'stored score'): verify(b)
    def test_role_mismatch(self):
        b=deepcopy(self.bundle); b['evidence']['run']['trials'][0]['checks_role']='diagnostic'; seal(b)
        with self.assertRaisesRegex(ValueError,'scoring role'): verify(b)

if __name__=='__main__': unittest.main()

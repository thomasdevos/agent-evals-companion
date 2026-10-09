"""Independent-review regression cases: reseal to exercise semantics, not hashes."""
from collections import Counter
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from chapter07 import replay as r

class CorrectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.bundle = r.build()

    def reject(self, mutate):
        b = deepcopy(self.bundle)
        mutate(b)
        r.seal(b)
        with self.assertRaises(ValueError): r.verify(b)

    def test_original_checks_cli(self):
        b = deepcopy(self.bundle)
        b['evidence']['run']['trials'][0]['checks']['exact_refund_ledger'] = True
        self.cli_reject(b)

    def test_original_status_cli(self):
        b = deepcopy(self.bundle)
        t = b['evidence']['run']['trials'][0]
        t.update(status='PASS', passed=1, failed=0)
        b['evidence']['run']['counts'] = dict(Counter(t['status'] for t in b['evidence']['run']['trials']))
        self.cli_reject(b)

    def cli_reject(self, b):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'inconsistent.json'; r.save(p, r.seal(b))
            for command in ('inspect', 'replay'):
                result = subprocess.run([sys.executable, '-m', 'chapter07.replay', command, str(p)],
                    cwd=r.ROOT, capture_output=True, text=True,
                    env={**os.environ, 'PYTHONDONTWRITEBYTECODE':'1'})
                self.assertEqual(result.returncode, 2, result.stdout+result.stderr)
                self.assertIn('original', json.loads(result.stdout)['error'])

    def test_required_manifest_fields(self):
        for key in self.bundle['manifest']:
            if key in ('report_id','evidence_sha256','report_sha256'): continue
            with self.subTest(key=key):
                self.reject(lambda b: b['manifest'].pop(key))

    def test_manifest_exact_types(self):
        cases = [('model','measured',0), ('configuration','retry',0),
                 ('environment','python',3), ('environment','machine',None),
                 ('budget','transport_attempts_per_request',True)]
        for section,key,value in cases:
            with self.subTest(section=section,key=key):
                self.reject(lambda b: b['manifest'][section].__setitem__(key,value))

    def test_manifest_relationships(self):
        cases = [('model','id','other'), ('prompt','source_sha256','0'*64),
                 ('tools','catalogue_sha256','0'*64), ('tools','executor_sha256','0'*64),
                 ('provenance','operation','regrade'), ('provenance','parent_report_id','bad')]
        for section,key,value in cases:
            with self.subTest(section=section,key=key):
                self.reject(lambda b: b['manifest'][section].__setitem__(key,value))

    def test_effective_budget(self):
        def change(b):
            b['manifest']['budget']['max_actions_per_trial']=999
            b['evidence']['run']['policy']['max_actions_per_trial']=999
        self.reject(change)

    def test_run_mode_and_baseline(self):
        for key,value in [('mode','provider'),('baseline','bounded-retry')]:
            with self.subTest(key=key):
                self.reject(lambda b: b['evidence']['run'].__setitem__(key,value))

    def test_environment_is_not_current_host_requirement(self):
        b=deepcopy(self.bundle)
        b['manifest']['environment'] = dict(python='3.11.99', sqlite='3.99', system='OtherOS', machine='other')
        r.verify(r.seal(b))

    def test_unknown_status(self):
        def change(b):
            run=b['evidence']['run']; t=run['trials'][0]
            t.update(status='BANANA',scoring_eligible=False,checks_role='diagnostic',passed=0,failed=0,errors=1)
            run['counts']=dict(Counter(t['status'] for t in run['trials']))
            b['report']=r.score(run,b['evidence']['rows'],'state-v1')
        self.reject(change)

    def test_row_counts(self):
        self.reject(lambda b: b['evidence']['run']['trials'][0].__setitem__('passed',1))
        self.reject(lambda b: b['evidence']['run']['trials'][0].__setitem__('failed',True))

    def test_regrade_inspection_provenance(self):
        new=r.regrade(self.bundle,'omit-ledger-demo'); view=r.inspect(new)
        self.assertEqual(view['status'],'FAIL')
        self.assertEqual(view['grading_provenance']['original_revision'],'state-v1')
        self.assertEqual(view['grading_provenance']['derived_revision'],'omit-ledger-demo')
        self.assertEqual(view['grading_provenance']['display_checks'],'original')
        self.assertEqual(new['report'][0]['status'],'PASS')

    def test_real_errors_preserved(self):
        for fault in ('crash','action_budget'):
            b=deepcopy(self.bundle); run=b['evidence']['run']; row=b['evidence']['rows'][0]
            if fault=='crash': t=r.execute(row,mode='script',fault='crash')
            else:
                with patch('chapter05.harness.scripted_agent', return_value=lambda view:dict(kind='read',text='repeat')):
                    t=r.execute(row,mode='script')
            run['trials'][0]=t; run['counts']=dict(Counter(t['status'] for t in run['trials']))
            b['report']=r.score(run,b['evidence']['rows'],'state-v1');r.seal(b)
            new=r.regrade(b,'omit-ledger-demo'); r.replay(new)
            self.assertEqual(new['report'][0],b['report'][0])
            self.assertFalse(new['report'][0]['scoring_eligible'])
            self.assertEqual(t['checks_role'],'unavailable' if fault=='crash' else 'diagnostic')

    def test_all_replay_tripwires(self):
        from contextlib import ExitStack
        with ExitStack() as stack:
            for name in ('chapter07.replay.run','chapter07.replay.execute','chapter05.harness.scripted_agent',
                         'sqlite3.connect','socket.socket','urllib.request.build_opener'):
                stack.enter_context(patch(name,side_effect=AssertionError('forbidden '+name)))
            r.replay(self.bundle)

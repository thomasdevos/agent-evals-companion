import unittest, json, math, tempfile, pathlib, subprocess, sys, os
from copy import deepcopy
from unittest.mock import patch
from fractions import Fraction
from chapter21 import monitor as m

class Corrections(unittest.TestCase):
    def test_individual_overflow(self):
        p,s,r=m.fixture();s[0]['probability']=5e-324
        with self.assertRaisesRegex(ValueError,'represent'):m.analyse(s,r,100)
    def test_aggregate_overflow(self):
        p,s,r=m.fixture()
        for x in s[:2]:x['probability']=1e-308
        with self.assertRaisesRegex(ValueError,'represent'):m.analyse(s,r,100)
    def test_unknown_with_unrepresentable_weight(self):
        p,s,r=m.fixture();s[0]['probability']=None;s[1]['probability']=5e-324
        with self.assertRaisesRegex(ValueError,'represent'):m.analyse(s,r[:-1],100)
    def test_small_representable(self):
        p,s,r=m.fixture();s[0]['probability']=1e-300
        z=m.analyse(s,r,100);self.assertTrue(math.isfinite(z['ht_failure_estimate']));self.assertGreater(z['ht_failure_estimate'],1);json.dumps(z,allow_nan=False)
    def test_exact_types(self):
        for bad in [True,False,float('inf'),float('-inf'),float('nan'),'0.1',10**400]:
            p,s,r=m.fixture();s[0]['probability']=bad
            with self.subTest(bad=str(bad)):
                with self.assertRaises(ValueError):m.analyse(s,r,100)
    def test_cli_validation_error(self):
        code="from unittest.mock import patch; from chapter21 import monitor as m; import sys; sys.argv=['monitor','repair']; p,s,r=m.fixture(); s[0]['probability']=5e-324\nwith patch.object(m,'fixture',return_value=(p,s,r)): sys.exit(m.main())"
        z=subprocess.run([sys.executable,*(['-O'] if sys.flags.optimize else []),'-c',code],text=True,capture_output=True)
        self.assertEqual(z.returncode,2);self.assertNotIn('Traceback',z.stderr);self.assertIn('represent',z.stderr)
    def test_sequential_retained_rows(self):
        # Actual CLI runs, but all writes go to an external copied companion.
        import shutil
        with tempfile.TemporaryDirectory(prefix='ch19-regression-') as d:
            root=pathlib.Path(d)/'companion';shutil.copytree(m.ROOT,root,ignore=shutil.ignore_patterns('__pycache__','output'))
            for mode in ['failure','repair','unknown']:
                z=subprocess.run([sys.executable,*(['-O'] if sys.flags.optimize else []),'-m','chapter21.monitor',mode],cwd=root,text=True,capture_output=True)
                self.assertEqual(z.returncode,int(mode=='failure'),z.stderr)
            for mode in ['failure','repair','unknown']:
                a=json.loads((root/f'chapter21/output/{mode}.json').read_text()); rows=json.loads((root/f'chapter21/output/{mode}-observations.json').read_text());slots=a['sampling_manifest']['schedule'];lookup={tuple(x['identity']):x for x in rows}
                self.assertEqual(len(rows),a['observed']);self.assertEqual(len(slots)-len(rows),a['missing'])
                self.assertEqual(sum(x['failed'] for x in rows)/len(rows),a['selected_failure_fraction'])
                mature=[x for x in rows if x['outcome'] is not None]
                self.assertEqual(len(mature),a['outcome_observed']);self.assertEqual(len(slots)-len(mature),a['outcome_pending']);self.assertEqual(sum(x['outcome'] for x in mature)/len(mature),a['selected_matured_success'])
                if len(rows)==len(slots) and all(x['probability'] is not None for x in slots):
                    ht=sum(Fraction(int(lookup[tuple(x['identity'])]['failed']))/Fraction(str(x['probability'])) for x in slots)/a['population_size'];self.assertEqual(float(ht),a['ht_failure_estimate'])
                else:self.assertIsNone(a['ht_failure_estimate'])
                self.assertIsNone(a['population_business_success'])
if __name__=='__main__':unittest.main(verbosity=2)

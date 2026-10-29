import unittest
from copy import deepcopy
from fractions import Fraction
from chapter21.monitor import fixture,analyse,promote,ROOT
from chapter03.dataset_lab import load_rows

class MonitoringTests(unittest.TestCase):
    def setUp(self): self.p,self.s,self.r=fixture()
    def test_arithmetic(self):
        x=analyse(self.s,self.r,100)
        independent=sum(Fraction(int(r['failed']))/Fraction(str(s['probability'])) for s,r in zip(self.s,self.r))/100
        self.assertEqual(x['ht_failure_estimate'],float(independent))
        self.assertAlmostEqual(x['selected_failure_fraction'],20/28)
        self.assertEqual(independent,Fraction(1,5))
    def test_unknown_probability(self):
        self.s[0]['probability']=None
        self.assertIsNone(analyse(self.s,self.r,100)['ht_failure_estimate'])
    def test_missing(self):
        x=analyse(self.s,self.r[:-1],100)
        self.assertEqual(x['scheduled'],28);self.assertEqual(x['missing'],1);self.assertIsNone(x['ht_failure_estimate'])
    def test_pending(self):
        self.r[0]['outcome']=None;x=analyse(self.s,self.r,100)
        self.assertEqual(x['outcome_pending'],1);self.assertIsNone(x['population_business_success'])
    def test_probabilities(self):
        for bad in [True,False,0,-1,1.1,float('nan'),float('inf'),'0.1']:
            with self.subTest(bad=bad):
                s=deepcopy(self.s);s[0]['probability']=bad
                with self.assertRaises(ValueError):analyse(s,self.r,100)
    def test_duplicate_schedule(self):
        with self.assertRaises(ValueError):analyse(self.s+self.s[:1],self.r,100)
    def test_duplicate_observation(self):
        with self.assertRaises(ValueError):analyse(self.s,self.r+self.r[:1],100)
    def test_foreign(self):
        self.r[0]['identity'][1]='foreign'
        with self.assertRaises(ValueError):analyse(self.s,self.r,100)
    def test_composite(self):
        for bad in ['a|b|c',['a','b'],['a',1,'b'],['a|b','c','d']]:
            s=deepcopy(self.s);s[0]['identity']=bad
            with self.assertRaises(ValueError):analyse(s,self.r,100)
    def test_exact_outcomes(self):
        for field in ['outcome','failed']:
            r=deepcopy(self.r);r[0][field]=1
            with self.assertRaises(ValueError):analyse(self.s,r,100)
    def test_missing_field(self):
        del self.r[0]['outcome']
        with self.assertRaises(ValueError):analyse(self.s,self.r,100)
    def test_empty(self):
        x=analyse([],[],100);self.assertIsNone(x['selected_failure_fraction']);self.assertIsNone(x['ht_failure_estimate'])
    def test_population(self):
        for bad in [True,0,-1,100.0]:
            with self.assertRaises(ValueError):analyse(self.s,self.r,bad)
    def test_promotion(self):
        row=load_rows(ROOT/'chapter03/repaired.jsonl')[0]
        a=dict(case_id=row['case_id'],decision='approved',authority='authored-review-fixture',purpose='public-regression',answer_exposed=True)
        x=promote(row,a);self.assertEqual(x['row'],row);self.assertFalse(x['fresh_comparison_eligible'])
        for k in a:
            b=deepcopy(a);b[k]=None
            with self.assertRaises(ValueError):promote(row,b)
    def test_financial_failure(self):
        from chapter19.delivery import inputs
        from chapter08.graders import aggregate
        s,r=inputs('task-failure');x=aggregate(s,r)
        self.assertEqual(x['failed'],1);self.assertEqual(x['scheduled_trials'],3)
if __name__=='__main__':unittest.main()

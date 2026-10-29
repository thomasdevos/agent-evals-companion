import unittest
from copy import deepcopy
from fractions import Fraction
from chapter13.compare import *

class ComparisonTests(unittest.TestCase):
    def setUp(self): self.s,self.r=corpus(True); self.p=card()
    def test_effect(self): self.assertEqual(analyse(self.s,self.r,self.p)['scored_effect'],float(Fraction(3-1,4)))
    def test_main(self):
        a=analyse(*corpus(),self.p); self.assertAlmostEqual(a['scored_effect'],float(Fraction(6-2,12))); self.assertEqual(a['declared_clusters'],12)
    def test_counts(self):
        a=analyse(self.s,self.r,self.p); self.assertEqual(a['scheduled_pairs'],120); self.assertEqual(a['scorecard']['scheduled_trials'],240)
    def test_financial(self):
        a=analyse(self.s,self.r,self.p); self.assertGreater(a['scorecard']['failed'],0); self.assertEqual(a['scorecard']['communication']['mean'],5)
    def test_failure(self):
        a=workflow('failure',self.p); self.assertEqual(a['unsafe']['recommendation'],'IMPROVED'); self.assertIsNone(a['illustrative_percentile_interval'])
    def test_sensitivity(self): self.assertEqual(sorted(analyse(self.s,self.r,self.p)['sensitivity']['leave_one_cluster_out']),[1/3,1/3,1/3,1])
    def test_missing(self):
        a=analyse(self.s,self.r[:-1],self.p); self.assertEqual(a['incomplete_pairs'],1); self.assertIsNone(a['scored_effect'])
    def test_unpaired(self):
        with self.assertRaises(ValueError): analyse(self.s[:-1],self.r,self.p)
    def test_duplicate_schedule(self):
        with self.assertRaises(ValueError): analyse(self.s+self.s[:1],self.r,self.p)
    def test_duplicate_result(self):
        with self.assertRaises(ValueError): analyse(self.s,self.r+self.r[:1],self.p)
    def test_foreign(self):
        self.r[0]['task_id']='foreign'
        with self.assertRaises(ValueError): analyse(self.s,self.r,self.p)
    def test_lineage(self):
        self.s[0]['incident']='other'
        with self.assertRaises(ValueError): analyse(self.s,self.r,self.p)
    def test_empty(self): self.assertEqual(analyse([],[],self.p)['reason'],'EMPTY')
    def test_single(self):
        a=analyse(self.s[:60],self.r[:60],self.p); self.assertEqual(a['declared_clusters'],1); self.assertIsNone(a['illustrative_percentile_interval'])
    def test_degenerate(self):
        s,r=corpus(); s=s[:36]; r=r[:36]; self.p['min_clusters']=2
        self.assertEqual(analyse(s,r,self.p)['reason'],'DEGENERATE')
    def test_error(self):
        self.r[0].update(result_status='INFRA_ERROR',scoring_eligible=False,checks_role='diagnostic')
        self.assertIsNone(analyse(self.s,self.r,self.p)['scored_effect'])
    def test_parameters(self):
        for k,v in [('seed',True),('seed',-1),('reps',True),('reps',99),('confidence',float('nan')),('confidence',float('inf')),('confidence',1),('meaningful',True),('max_analyses',2),('repeats',3.0)]:
            p=deepcopy(self.p); p[k]=v
            with self.subTest(k=k,v=v),self.assertRaises(ValueError): validate_plan(p)
    def test_bootstrap_bounds(self):
        for x in [[],[True],[float('nan')],[2]]:
            with self.assertRaises(ValueError): bootstrap(x)
    def test_bootstrap_literal(self): self.assertEqual(bootstrap([-.5,.5]),[-.5,.5])
    def test_bootstrap_constant(self): self.assertEqual(bootstrap([.25]*4),[.25,.25])
    def test_replay(self): self.assertEqual(bootstrap([-1,0,1]),bootstrap([-1,0,1]))
    def test_open_before_freeze(self):
        with self.assertRaises(ValueError): Experiment().analyse(self.s,self.r)
    def test_exposure(self):
        e=Experiment(); e.expose({'incident-0'}); e.freeze(self.p)
        with self.assertRaises(ValueError): e.analyse(self.s,self.r)
    def test_stop(self):
        e=Experiment(); e.freeze(self.p); e.analyse(self.s,self.r)
        with self.assertRaises(ValueError): e.analyse(self.s,self.r)
    def test_copy(self):
        e=Experiment(); e.freeze(self.p); self.p['meaningful']=.9; self.assertEqual(e.plan['meaningful'],.1)
    def test_late_exposure(self):
        e=Experiment(); e.freeze(self.p)
        with self.assertRaises(ValueError): e.expose({'later'})

if __name__=='__main__': unittest.main()

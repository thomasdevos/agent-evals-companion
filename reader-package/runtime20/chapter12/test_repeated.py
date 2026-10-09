import unittest
from copy import deepcopy
from fractions import Fraction
from itertools import combinations
from chapter12.repeated import analyse, exercise, subset_events, budget, cost_summary, run

class RepeatedTests(unittest.TestCase):
    def setUp(self): self.s,self.r=exercise()
    def test_events(self):
        x=analyse(self.s,self.r)
        self.assertEqual(x['first_attempt']['value'],1/3)
        self.assertEqual(x['at_least_one']['value'],2/3)
        self.assertEqual(x['all_attempts']['value'],1/3)
        self.assertEqual(x['scorecard']['trial_weighted_success'],5/9)
    def test_financial_noncompensation(self):
        x=analyse(self.s,self.r)['scorecard']
        self.assertEqual((x['passed'],x['failed']),(5,4))
        self.assertEqual(x['communication']['mean'],5)
    def test_missing(self):
        x=analyse(self.s,self.r[:-1]); self.assertEqual(x['scorecard']['missing'],1)
        self.assertEqual(x['scorecard']['measured_only_denominator'],8)
        self.assertIsNone(x['per_task'][-1]['subset_estimates'])
        self.assertEqual(x['complete_scored_tasks'],2)
    def test_all_missing(self):
        x=analyse(self.s,[]); self.assertEqual(x['scorecard']['missing'],9)
        self.assertIsNone(x['scorecard']['measured_only_success'])
    def test_empty(self):
        x=analyse([],[]); self.assertIsNone(x['first_attempt']['value'])
    def test_duplicate_schedule(self):
        with self.assertRaises(ValueError): analyse(self.s+[self.s[0]],self.r)
    def test_duplicate_record(self):
        with self.assertRaises(ValueError): analyse(self.s,self.r+[self.r[0]])
    def test_unknown_task(self):
        self.r[0]['task_id']='other'
        with self.assertRaises(ValueError): analyse(self.s,self.r)
    def test_unknown_trial(self):
        self.r[0]['trial_id']='other'
        with self.assertRaises(ValueError): analyse(self.s,self.r)
    def test_incomplete(self):
        with self.assertRaises(ValueError): analyse(self.s[:-1],self.r)
    def test_exact_repeat(self):
        for v in (True,3.0,'3',0,-1,101,float('nan'),float('inf'),None):
            with self.subTest(v=v),self.assertRaises(ValueError): analyse(self.s,self.r,v)
    def test_invalid_k(self):
        for v in (True,1.0,'1',0,-1,4,float('nan'),float('inf')):
            with self.subTest(v=v),self.assertRaises(ValueError): analyse(self.s,self.r,k=v)
    def test_attempt_type(self):
        self.s[0]['attempt']=True
        with self.assertRaises(ValueError): analyse(self.s,self.r)
    def test_identity_type(self):
        self.s[0]['task_id']=True
        with self.assertRaises(ValueError): analyse(self.s,self.r)
    def test_group_mismatch(self):
        self.s[0]['family']='other'
        with self.assertRaises(ValueError): analyse(self.s,self.r)
    def test_suffix(self):
        self.s[0]['trial_id']='exercise-0:2'
        with self.assertRaises(ValueError): analyse(self.s,self.r)
    def test_error(self):
        self.r[0].update(result_status='INFRA_ERROR',scoring_eligible=False,checks_role='diagnostic')
        x=analyse(self.s,self.r)
        self.assertEqual(x['scorecard']['errors'],1)
        self.assertIsNone(x['per_task'][0]['subset_estimates'])
    def test_enumeration(self):
        for n in range(1,7):
            for c in range(n+1):
                for k in range(1,n+1):
                    subsets=list(combinations([True]*c+[False]*(n-c),k))
                    x=subset_events(n,c,k)
                    self.assertAlmostEqual(x['all_attempts'],sum(all(s) for s in subsets)/len(subsets))
                    self.assertAlmostEqual(x['at_least_one'],sum(any(s) for s in subsets)/len(subsets))
    def test_subset_types(self):
        for args in ((0,0,1),(3,True,1),(3,4,1),(3,2,4),(3,2,False)):
            with self.assertRaises(ValueError): subset_events(*args)
    def test_budget(self):
        x=budget({'request_attempts':2})
        self.assertEqual((x['extra_repeats'],x['new_independent_tasks']),(30,12))
        self.assertEqual((x['repeat_unit_cents'],x['new_task_unit_cents']),(4,10))
    def test_variance_independent_arithmetic(self):
        new=(Fraction(4,100)+Fraction(16,100))/24
        repeats=Fraction(4,100)/12+Fraction(16,100)/36
        self.assertEqual(new,Fraction(1,120)); self.assertEqual(repeats,Fraction(7,900))
        self.assertEqual(24*4,96); self.assertEqual(12*10,120)
    def test_fixed_budget_allocation(self):
        from chapter12.repeated import planning_variance
        self.assertAlmostEqual(planning_variance([1]*24),float(Fraction(1,120)))
        self.assertAlmostEqual(planning_variance([3]*6+[4]*6),float(Fraction(13,1800)))
        self.assertEqual((6*2+6*3)*4,120)
        self.assertLess(planning_variance([3]*6+[4]*6),planning_variance([1]*24))
        self.assertGreater(planning_variance([3]*6+[4]*6,between=0.16,within=0.04),planning_variance([1]*24,between=0.16,within=0.04))
        for counts in ([],[True],[0],[float('nan')]):
            with self.assertRaises(ValueError): planning_variance(counts)
    def test_heterogeneous(self):
        p=[Fraction(9,10),Fraction(1,10)]
        self.assertEqual(sum(v*v for v in p)/2,Fraction(41,100))
        self.assertEqual(sum(1-(1-v)**2 for v in p)/2,Fraction(59,100))
        self.assertEqual((sum(p)/2)**2,Fraction(1,4))
    def test_unknown_cost(self):
        l=dict(request_attempts=2,provider_tool_calls=1,executor_action_attempts=1,elapsed_local_seconds=0,model_cost=None)
        self.assertIsNone(cost_summary([{'ledger':l}])['model_cost'])
        for v in (float('nan'),float('inf'),True,-1):
            l['model_cost']=v
            with self.assertRaises(ValueError): cost_summary([{'ledger':l}])
    def test_bad_price(self):
        for v in (True,0,-1,float('nan'),2.0):
            with self.assertRaises(ValueError): budget({'request_attempts':2},request_price_cents=v)
    def test_executed_runner(self):
        x=run(2)
        self.assertEqual(len(x['trials']),len(x['schedule']))
        self.assertGreater(len(x['trials']),0)
        self.assertEqual(x['analysis']['scorecard']['missing'],0)
        self.assertTrue(all(t['before']['refunds']==[] for t in x['trials']))
        self.assertIsNone(x['ledger']['model_cost'])

if __name__=='__main__': unittest.main()

import unittest
from copy import deepcopy
from chapter24.programme import *

class ProgrammeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.r=run('repair'); cls.b=cls.r['baselines']['direct']
    def test_raw_oracle(self):
        for b in self.r['baselines'].values():
            expected=sum(sum(row[k] for k in ['request_cents','labelling_cents','investigation_cents','infrastructure_cents']) for row in b['cost_rows'])
            self.assertEqual(expected,b['account']['scenario_total_cents'])
            self.assertEqual(sum(t['ledger']['request_attempts'] for t in b['trials']),b['ledger']['request_attempts'])
    def test_zero_completion(self): self.assertIsNone(self.b['account']['scenario_cost_per_successful_trial_cents'])
    def test_unknown_cost(self):
        c=deepcopy(self.b['cost_rows']); c[0]['request_cents']=None
        self.assertIsNone(account(self.b['schedule'],self.b['records'],c)['scenario_total_cents'])
    def test_missing_cost(self): self.assertIsNone(account(self.b['schedule'],self.b['records'],[])['scenario_total_cents'])
    def test_bad_amounts(self):
        for v in [True,-1,float('inf'),float('nan'),'1',{}]:
            c=deepcopy(self.b['cost_rows']); c[0]['request_cents']=v
            with self.assertRaises(ValueError): account(self.b['schedule'],self.b['records'],c)
    def test_duplicate_cost(self):
        with self.assertRaises(ValueError): account(self.b['schedule'],self.b['records'],self.b['cost_rows']*2)
    def test_foreign_cost(self):
        c=deepcopy(self.b['cost_rows']); c[0]['task_id']='foreign'
        with self.assertRaises(ValueError): account(self.b['schedule'],self.b['records'],c)
    def test_schedule(self):
        with self.assertRaises(ValueError): account(self.b['schedule']*2,self.b['records'],[])
    def test_owners(self): self.assertEqual(len(handover(owners())),4)
    def test_bad_ownership(self):
        for key,v in [('owner',''),('owner',True),('days',True),('days',0),('right','deploy'),('authored',1)]:
            x=owners(); x[0][key]=v
            with self.assertRaises(ValueError): handover(x)
    def test_missing_owner(self):
        with self.assertRaises(ValueError): handover(owners()[:-1])
    def test_duplicate_owner(self):
        x=owners(); x[1]=x[0]
        with self.assertRaises(ValueError): handover(x)
    def test_suite(self):
        h=self.r['suite_health']; self.assertTrue(h['eligible']); self.assertGreater(h['lost_count'],0); self.assertFalse(h['equivalent_full_coverage'])
    def test_unsafe_suite(self):
        rows=load_rows(ROOT/'chapter03/repaired.jsonl'); self.assertFalse(suite(rows,[rows[0]['case_id']])['eligible'])
    def test_foreign_suite(self):
        with self.assertRaises(ValueError): suite(load_rows(ROOT/'chapter03/repaired.jsonl'),['foreign'])
    def test_financial(self): self.assertGreater(self.r['financial_scorecard']['failed'],0)
    def test_comparison(self): self.assertEqual(self.r['comparison']['decision'],'DESCRIPTIVE_INCONCLUSIVE')
    def test_permissions(self): self.assertIs(self.r['may_deploy'],False); self.assertIsNone(self.r['live_usage'])
if __name__=='__main__': unittest.main()

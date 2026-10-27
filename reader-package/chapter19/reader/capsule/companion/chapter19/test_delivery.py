import unittest
from copy import deepcopy
from chapter19 import delivery as d

class DeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.base=d.collect('pass')
    def reject(self, f):
        b=deepcopy(self.base); f(b)
        with self.assertRaises((ValueError,TypeError,KeyError)): d.decide(d.seal(b))
    def test_pass(self): self.assertEqual(d.decide(d.seal(self.base))[0],'PASS')
    def test_controls(self):
        for scenario,expected in [('task-failure','FAIL'),('grader-failure','FAIL'),('outage','DEFER'),('missing-job','FAIL'),('missing-test','DEFER'),('inconclusive','DEFER')]:
            with self.subTest(scenario=scenario): self.assertEqual(d.decide(d.seal(d.collect(scenario)))[0],expected)
    def test_denominator(self):
        b=d.collect('outage'); self.assertEqual(b['scorecard']['scheduled_trials'],3); self.assertEqual(b['scorecard']['passed'],2)
    def test_runtime(self):
        r=d.runtime(d.seal(self.base)); self.assertFalse(r['may_refund']); self.assertFalse(r['may_deploy'])
    def test_unknown_cost(self): self.assertIsNone(self.base['cost']['model_cost'])
    def test_policy_alias(self):
        p=d.policy(); p['jobs'].clear(); self.assertEqual(d.policy()['jobs'],['code','support'])
    def test_duplicate(self): self.reject(lambda b:b['records'].append(deepcopy(b['records'][0])))
    def test_foreign(self): self.reject(lambda b:b['records'][0].update(task_id='foreign'))
    def test_missing(self): self.reject(lambda b:b['records'].pop())
    def test_empty_schedule(self): self.reject(lambda b:b.update(schedule=[]))
    def test_bool(self): self.reject(lambda b:b['records'][0].update(scoring_eligible=1))
    def test_check(self): self.reject(lambda b:b['records'][0]['outcome_checks'].update(exact_refund_ledger=False))
    def test_status(self): self.reject(lambda b:b['records'][0].update(result_status='FAIL'))
    def test_budget(self): self.reject(lambda b:b['policy']['budget'].update(provider_calls=1))
    def test_policy(self): self.reject(lambda b:b['policy']['jobs'].clear())
    def test_approval(self): self.reject(lambda b:b.update(human_approval=True))
    def test_cost(self): self.reject(lambda b:b['cost'].update(model_cost=0))
    def test_code(self): self.reject(lambda b:b['code']['rows'][0].update(passed=1))
    def test_code_missing(self): self.reject(lambda b:b['code']['rows'].pop())
    def test_stdout(self): self.reject(lambda b:b['code']['process'].update(stdout='[]'))
    def test_bindings(self): self.reject(lambda b:b.update(bindings={}))
    def test_digest(self):
        p=d.seal(deepcopy(self.base)); p['body']['human_approval']=True
        with self.assertRaises(ValueError): d.decide(p)

if __name__=='__main__': unittest.main()

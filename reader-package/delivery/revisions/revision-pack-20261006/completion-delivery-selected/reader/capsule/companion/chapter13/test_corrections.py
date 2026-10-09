"""F1/F2 regression contracts; unittest assertions survive optimized Python."""
import hashlib
import json
import unittest
from copy import deepcopy
from chapter13.compare import Experiment, analyse, card, corpus

class CorrectionTests(unittest.TestCase):
    def collision(self, reverse=False, delimiter=False):
        s,r=corpus(True); s1,r1=deepcopy(s[:6]),deepcopy(r[:6])
        s2,r2=deepcopy(s1),deepcopy(r1)
        for x in s1+r1:
            x['dataset_revision']='a|b' if delimiter else 'a'
            x['task_id']='c' if delimiter else 'same'
        for x in s2+r2:
            x['dataset_revision']='a' if delimiter else 'z'
            x['task_id']='b|c' if delimiter else 'same'
            x['agent_revision']='new' if x['agent_revision']=='old' else 'old'
        for x in s1+s2+r1+r2: x['trial_id']=x['task_id']+':'+x['trial_id'].rsplit(':',1)[1]
        for x in s2: x['incident']='second'
        return (s2+s1,r2+r1) if reverse else (s1+s2,r1+r2)

    def check_cases(self, reverse=False, delimiter=False):
        a=analyse(*self.collision(reverse,delimiter),card())
        cases=json.loads(json.dumps(a))['case_differences']
        self.assertIsInstance(cases,list)
        expected={('a|b','c'):1.,('a','b|c'):-1.} if delimiter else {('a','same'):1.,('z','same'):-1.}
        self.assertEqual(len(cases),2)
        self.assertEqual({(v['dataset_revision'],v['task_id']):v['difference'] for v in cases},expected)
        self.assertEqual(a['scored_effect'],0.)
    def test_collision_forward(self): self.check_cases()
    def test_collision_reverse(self): self.check_cases(True)
    def test_delimiter_collision(self): self.check_cases(delimiter=True)
    def test_hidden_regression_order(self):
        s,r=self.collision()
        for x in s+r: x['agent_revision']='new' if x['agent_revision']=='old' else 'old'
        for ss,rr in [(s,r),(list(reversed(s)),list(reversed(r)))]:
            cases=analyse(ss,rr,card())['case_differences']
            self.assertIsInstance(cases,list)
            self.assertEqual({(v['dataset_revision'],v['task_id']):v['difference'] for v in cases},{('a','same'):-1.,('z','same'):1.})
    def test_missing_and_error_identity(self):
        for error in (False,True):
            s,r=self.collision()
            if error: r[0].update(result_status='INFRA_ERROR',scoring_eligible=False,checks_role='diagnostic')
            else: r=r[1:]
            a=analyse(s,r,card())
            self.assertIsInstance(a['case_differences'],list)
            self.assertEqual({(v['dataset_revision'],v['task_id']) for v in a['case_differences']},{('a','same'),('z','same')})
            self.assertEqual(a['incomplete_pairs'],1); self.assertIsNone(a['scored_effect'])
            self.assertIsNone(a['illustrative_percentile_interval'])
    def check_frozen(self, mutation):
        p=card(); e=Experiment(); e.freeze(p); mutation(p,e)
        a=e.analyse(*corpus())
        self.assertEqual(a['plan'],card())
        self.assertEqual(a['plan_sha256'],hashlib.sha256(json.dumps(a['plan'],sort_keys=True).encode()).hexdigest())
        with self.assertRaises(ValueError): e.analyse(*corpus())
    def test_original_input_mutation(self): self.check_frozen(lambda p,e:p.update(seed=18,reps=100,meaningful=.9))
    def test_exposed_plan_mutation(self): self.check_frozen(lambda p,e:e.plan.update(seed=18,reps=100,meaningful=.9))
    def test_nested_original_mutation(self): self.check_frozen(lambda p,e:p['versions'].append('third'))
    def test_nested_exposed_mutation(self): self.check_frozen(lambda p,e:e.plan['versions'].append('third'))
    def test_distinct_declaration_hash(self):
        a=Experiment(); b=Experiment(); p=card(); p.update(seed=18,reps=100)
        a.freeze(card()); b.freeze(p)
        x=a.analyse(*corpus()); y=b.analyse(*corpus())
        self.assertNotEqual(x['plan_sha256'],y['plan_sha256'])
        self.assertEqual(y['plan'],p)
        self.assertEqual(y['plan_sha256'],hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest())
    def test_invalid_open_spends(self):
        e=Experiment(); e.freeze(card()); s,r=corpus()
        with self.assertRaises(ValueError): e.analyse(s[:-1],r)
        with self.assertRaises(ValueError): e.analyse(s,r)

if __name__=='__main__': unittest.main()

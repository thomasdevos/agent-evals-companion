import unittest
from copy import deepcopy
from chapter11.calibrate import *

class Calibration(unittest.TestCase):
    def setUp(self): self.s,self.r=corpus()
    def test_matrix(self):
        c=report(self.s,self.r,5)['counts']
        self.assertEqual([c[k] for k in ('TP','FP','TN','FN')],[2,1,2,3])
    def test_denominators(self):
        x=report(self.s,self.r,5)
        self.assertEqual(x['false_accept'],dict(numerator=1,denominator=3,value=1/3))
        self.assertEqual(x['false_reject'],dict(numerator=3,denominator=5,value=3/5))
        self.assertEqual(x['agreement']['value'],0.5)
    def test_costs_independent_expected(self):
        x=costs(self.s,self.r)
        self.assertEqual([r['cost'] for r in x['choices']],[24,17,11]); self.assertEqual(x['selected'],5)
    def test_tie(self): self.assertEqual(costs(self.s,self.r,0,0)['selected'],5)
    def test_empty(self):
        with self.assertRaises(ValueError): report([],[],5)
    def test_threshold_types(self):
        for x in (True,5.0,'5',float('nan'),float('inf'),0,7):
            with self.subTest(x=x),self.assertRaises(ValueError): report(self.s,self.r,x)
    def test_cost_types(self):
        for x in (True,-1,1.0,float('nan'),float('inf')):
            with self.subTest(x=x),self.assertRaises(ValueError): costs(self.s,self.r,x)
    def test_duplicate_schedule(self):
        with self.assertRaises(ValueError): report(self.s+self.s[:1],self.r,5)
    def test_duplicate_result(self):
        with self.assertRaises(ValueError): report(self.s,self.r+self.r[:1],5)
    def test_unknown_id(self):
        self.r[0]['id']='alien'
        with self.assertRaises(ValueError): report(self.s,self.r,5)
    def test_missing(self):
        x=report(self.s,[],5);self.assertEqual(x['counts']['missing'],8);self.assertEqual(x['accepted_scheduled']['value'],0);self.assertIsNone(x['agreement']['value'])
    def test_nonrated(self):
        for status in ('unknown','refused'):
            x=report(self.s,[dict(id=self.s[0]['id'],judge=wrapper(status=status))],5)
            self.assertEqual(x['counts'][status],1);self.assertEqual(x['counts']['missing'],7);self.assertEqual(x['counts']['accepted'],0)
    def test_error(self):
        x=report(self.s,[dict(id=self.s[0]['id'],judge=j.evaluate(j.packet(),lambda _:'x'))],5)
        self.assertEqual(x['counts']['error'],1);self.assertEqual(x['counts']['accepted'],0)
    def test_unknown_reference(self):
        self.s[0]['label']='unknown';x=report(self.s,self.r,5)
        self.assertEqual(x['counts']['label_unknown'],1);self.assertEqual(x['agreement']['denominator'],7)
        with self.assertRaises(ValueError): costs(self.s,self.r)
    def test_zero_class(self):
        x=report(self.s[:1],self.r[:1],5);self.assertIsNone(x['false_accept']['value'])
    def test_wrapper_mutations(self):
        for score in (True,5.0,'5',float('nan'),float('inf')):
            r=deepcopy(self.r);r[0]['judge']['result']['score']=score
            with self.subTest(score=score),self.assertRaises(ValueError): report(self.s,r,5)
    def test_binding(self):
        self.r[0]['judge']['binding']['prompt_version']='wrong'
        with self.assertRaises(ValueError): report(self.s,self.r,5)
    def test_schedule_shape(self):
        for row in ({},dict(self.s[0],label=True),dict(self.s[0],id=''),dict(self.s[0],extra=1)):
            with self.subTest(row=row),self.assertRaises(ValueError): report([row],[],5)
    def test_leak(self):
        f=Split();f.tune(self.s);f.freeze(5)
        with self.assertRaisesRegex(ValueError,'EXPOSED_AUDIT'): f.audit(self.s,self.r)
    def test_renaming_does_not_repair(self):
        f=Split();f.tune(self.s);f.freeze(5);s=deepcopy(self.s)
        for x in s:x['id']='renamed-'+x['id']
        with self.assertRaisesRegex(ValueError,'EXPOSED_AUDIT'):f.audit(s,[])
    def test_freeze_before_audit(self):
        with self.assertRaisesRegex(ValueError,'NOT_FROZEN'):Split().audit(self.s,self.r)
    def test_audit_once(self):
        f=Split();f.freeze(5);f.audit(self.s,self.r)
        with self.assertRaises(ValueError):f.audit(self.s,self.r)
        with self.assertRaises(ValueError):f.tune(self.s)
    def test_proper_repair(self):
        f=Split();f.tune(self.s);f.freeze(5);s,r=corpus('audit');self.assertEqual(f.audit(s,r)['scheduled'],8)
    def test_challenges(self):
        x=challenges();self.assertTrue(x['unsafe_order_sensitive']);self.assertFalse(x['repaired_order_sensitive']);self.assertTrue(x['pointwise_invariant'])
        self.assertEqual([r['unsafe'] for r in x['pairwise']],['old','new']);self.assertEqual([r['repaired'] for r in x['pairwise']],['tie','tie'])
    def test_financial(self):
        x=financial();self.assertEqual((x['failed'],x['passed']),(1,0))

if __name__=='__main__':unittest.main()

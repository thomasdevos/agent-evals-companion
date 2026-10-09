import copy
from pathlib import Path
import sqlite3
import tempfile
import unittest
from chapter15 import state_lab as lab

class StateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.good=lab.scenario()
    def test_repair(self): self.assertEqual(self.good['grade']['outcome'],'PASS')
    def test_alternate(self): self.assertEqual(lab.scenario(route='policy-first')['grade']['outcome'],'PASS')
    def test_duplicate(self): self.assertEqual(lab.scenario(unsafe=True)['grade']['financial'],'FAIL')
    def test_interruption(self):
        self.assertEqual(self.good['start_exit'],75)
        self.assertEqual(self.good['interrupted']['after']['refunds'],[['A100',4200]])
    def test_stale_memory(self): self.assertEqual(self.good['interrupted']['memory'],[['refund_status','not_started']])
    def test_handoff(self): self.assertTrue(self.good['grade']['roles'])
    def mutation(self,change,error=False):
        e=copy.deepcopy(self.good['evidence']); change(e)
        if error:
            with self.assertRaises(ValueError): lab.evaluate(self.good['before'],e)
        else: self.assertEqual(lab.evaluate(self.good['before'],e)['outcome'],'FAIL')
    def test_missing(self): self.mutation(lambda e:e['events'].pop(2),True)
    def test_empty(self): self.mutation(lambda e:e.update(events=[]))
    def test_wrong_role(self): self.mutation(lambda e:e['events'][0].__setitem__(1,'payments'))
    def test_bad_actor(self): self.mutation(lambda e:e['events'][0].__setitem__(1,'foreign'),True)
    def test_bool_sequence(self): self.mutation(lambda e:e['events'][0].__setitem__(0,True),True)
    def test_duplicate_sequence(self): self.mutation(lambda e:e['events'][1].__setitem__(0,1),True)
    def test_foreign_operation(self): self.mutation(lambda e:e['events'][0].__setitem__(4,'foreign'),True)
    def test_duplicate_operation(self): self.mutation(lambda e:e['operations'].append(e['operations'][0]),True)
    def test_composite(self):
        with self.assertRaises(ValueError): lab.validate_identity(('support','v1:refund-A100-full'))
    def test_bool_amount(self): self.mutation(lambda e:e['operations'][0].__setitem__(3,True),True)
    def test_bad_state(self): self.mutation(lambda e:e['after']['orders'][0].__setitem__(1,True),True)
    def test_unrelated(self): self.mutation(lambda e:e['after']['orders'][1].__setitem__(2,'cancelled'))
    def test_trace_without_effect(self): self.mutation(lambda e:e['after'].update(refunds=[]))
    def test_forged_coherent_not_authenticated(self): self.assertEqual(self.good['grade']['authentication'],'not established')
    def test_no_compensation(self): self.assertEqual(lab.scenario(unsafe=True)['grade']['outcome'],'FAIL')
    def boundary(self,fn):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'s.sqlite'; lab.initialise(p)
            with sqlite3.connect(p) as db:
                for k in ('identity','policy','handoff'): lab.event(db,'intake',k)
            fn(p)
    def test_payload_conflict(self):
        def check(p):
            lab.refund(p)
            with self.assertRaisesRegex(ValueError,'payload conflict'): lab.refund(p,payload=('A100',4199))
        self.boundary(check)
    def test_permission(self):
        def check(p):
            with self.assertRaises(PermissionError): lab.refund(p,actor='intake')
        self.boundary(check)
    def test_arguments(self):
        def check(p):
            with self.assertRaises(ValueError): lab.refund(p,payload=('A100',True))
        self.boundary(check)
    def test_repeated_same_operation(self):
        def check(p):
            self.assertEqual(lab.refund(p),'committed'); self.assertEqual(lab.refund(p),'existing')
            self.assertEqual(lab.snapshot(p)['refunds'],[['A100',4200]])
        self.boundary(check)
    def test_malformed_memory(self): self.mutation(lambda e:e.update(memory={}),True)
    def test_missing_prerequisites(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'s.sqlite'; lab.initialise(p)
            with self.assertRaises(PermissionError): lab.refund(p)
    def test_wrong_start(self):
        with self.assertRaises(ValueError): lab.evaluate({'orders':[],'refunds':[]},self.good['evidence'])
if __name__=='__main__': unittest.main()

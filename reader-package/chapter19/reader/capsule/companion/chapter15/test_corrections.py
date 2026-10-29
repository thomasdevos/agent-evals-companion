import copy
import sqlite3
import tempfile
from pathlib import Path
import unittest
from chapter15 import state_lab as L

class Corrections(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.good=L.scenario()
    def reject(self, change):
        e=copy.deepcopy(self.good['evidence']); change(e)
        for i,r in enumerate(e['events'],1): r[0]=i
        self.assertEqual(L.evaluate(self.good['before'],e)['outcome'],'FAIL')
    def test_each_retry_position(self):
        for pos in (0,3,4,5,6,8):
            with self.subTest(pos=pos):
                self.reject(lambda e:e['events'].insert(pos,e['events'].pop(7)))
    def test_missing_each_event(self):
        for pos in range(9):
            with self.subTest(pos=pos): self.reject(lambda e:e['events'].pop(pos))
    def test_repeated_each_event(self):
        for pos in range(9):
            with self.subTest(pos=pos): self.reject(lambda e:e['events'].append(copy.deepcopy(e['events'][pos])))
    def test_late_memory(self): self.reject(lambda e:e['events'].append(e['events'].pop(5)))
    def test_stale_final_memory(self): self.reject(lambda e:e.update(memory=[['refund_status','not_started']]))
    def test_observed_read(self):
        self.assertEqual(self.good['evidence'].get('memory_observations'),[[6,*L.OP,'refund_status','not_started']])
    def test_boundary_invalid_prefixes(self):
        prefixes=[[(a,k) for k in ks] for a in ('intake','payments') for ks in [('handoff','policy','identity'),('identity','handoff','policy')]]
        prefixes += [[('payments',k) for k in ('identity','policy','handoff')], [('intake',k) for k in ('identity','identity','policy','handoff')]]
        for prefix in prefixes:
            with self.subTest(prefix=prefix),tempfile.TemporaryDirectory() as td:
                p=Path(td)/'db';L.initialise(p)
                with sqlite3.connect(p) as db:
                    for actor,kind in prefix: L.event(db,actor,kind)
                before=L.inspect(p)
                with self.assertRaises(PermissionError): L.refund(p)
                self.assertEqual(L.inspect(p),before)
    def test_boundary_foreign_prefix(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'db';L.initialise(p)
            with sqlite3.connect(p) as db:
                for k in ('identity','policy','handoff'): L.event(db,'intake',k)
                db.execute("UPDATE events SET scope='foreign'")
            before=L.inspect(p)
            with self.assertRaises(PermissionError): L.refund(p)
            self.assertEqual(L.inspect(p),before)
    def test_observation_contradiction(self):
        e=copy.deepcopy(self.good['evidence'])
        e['memory_observations']=[[6,*L.OP,'refund_status','confirmed']]
        try: result=L.evaluate(self.good['before'],e)
        except ValueError: return
        self.assertEqual(result['outcome'],'FAIL')

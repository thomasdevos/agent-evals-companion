import copy
from pathlib import Path
import tempfile
import unittest
from chapter18 import coding as c

class CodingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.packet = c.capture()
    def test_baseline(self): self.assertEqual(self.packet['body']['rows'][0]['status'], 'FAIL')
    def test_false_green(self):
        row=self.packet['body']['rows'][1]; self.assertEqual(row['visible_exit'],0); self.assertEqual(row['status'],'POLICY_FAIL')
    def test_skip(self): self.assertEqual(self.packet['body']['rows'][2]['status'],'FAIL')
    def test_repair(self): self.assertEqual(self.packet['body']['rows'][3]['status'],'PASS')
    def test_alternative(self): self.assertEqual(self.packet['body']['rows'][4]['status'],'PASS')
    def test_neighbor(self): self.assertEqual(self.packet['body']['rows'][5]['status'],'FAIL')
    def test_execution_error(self): self.assertEqual(self.packet['body']['rows'][6]['status'],'EXECUTION_ERROR')
    def test_timeout(self): self.assertEqual(self.packet['body']['rows'][7]['status'],'TIMEOUT')
    def test_valid(self): c.verify(self.packet)
    def bad(self, mutate):
        p=copy.deepcopy(self.packet); mutate(p['body']); p['sha256']=c.digest(p['body'])
        with self.assertRaises(ValueError): c.verify(p)
    def test_missing(self): self.bad(lambda b:b['rows'].pop())
    def test_duplicate(self): self.bad(lambda b:b['rows'].__setitem__(1,b['rows'][0]))
    def test_foreign(self): self.bad(lambda b:b['rows'][0].__setitem__('variant','foreign'))
    def test_contradiction(self): self.bad(lambda b:b['rows'][0].__setitem__('status','PASS'))
    def test_exact_type(self): self.bad(lambda b:b['rows'][0].__setitem__('permitted',1))
    def test_missing_tests(self): self.bad(lambda b:b['rows'][0]['rows'].pop())
    def test_bindings(self): self.bad(lambda b:b['bindings'].__setitem__('coding.py','0'*64))
    def test_stdout(self): self.bad(lambda b:b['rows'][0]['process'].__setitem__('stdout','[]'))
    def test_traversal(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(ValueError): c.apply(Path(t),{'../outside':'bad'})
    def test_symlink(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t); (p/'names.py').symlink_to(p/'elsewhere')
            with self.assertRaises(ValueError): c.apply(p,{'names.py':'bad'})
    def test_inventory_addition(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t); before=c.inventory(p);(p/'extra').write_text('x');self.assertNotEqual(before,c.inventory(p))

if __name__=='__main__': unittest.main()

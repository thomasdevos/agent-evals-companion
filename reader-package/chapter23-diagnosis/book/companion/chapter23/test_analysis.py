import copy
import unittest
from chapter23.analysis import capture,verify,digest,records,analyse

class ScaleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.packet=capture()
    def reject(self,change):
        p=copy.deepcopy(self.packet);change(p['body']);p['sha256']=digest(p['body'])
        with self.assertRaises(ValueError):verify(p)
    def test_positive_failing_arm_admitted(self):
        self.assertEqual(verify(self.packet)['body']['comparison']['body']['state']['unsafe']['grade']['financial'],'FAIL')
    def test_three_repairs(self):
        self.assertEqual([(x['before'],x['after']) for x in self.packet['body']['cases']],[(False,True)]*3)
    def test_missing(self):self.reject(lambda b:b['rows'].pop())
    def test_duplicate(self):self.reject(lambda b:b['rows'].append(b['rows'][0]))
    def test_foreign(self):self.reject(lambda b:b['rows'][0].update(id='trace-999'))
    def test_malformed_ids(self):
        for value in (True,1,None,[],{},'', ' trace-000'):
            with self.subTest(value=value):self.reject(lambda b:b['rows'][0].update(id=value))
    def test_exact_types(self):
        for value in (False,0.0,'0',None):
            with self.subTest(value=value):self.reject(lambda b:b.update(provider_requests=value))
    def test_unknown_cost(self):self.reject(lambda b:b.update(model_cost_usd=0))
    def test_false_closure(self):self.reject(lambda b:b.update(closure='closed'))
    def test_fabricated_approval(self):self.reject(lambda b:b.update(approval='approved'))
    def test_count_contradiction(self):self.reject(lambda b:b['summary']['taxonomy'][0].update(count=True))
    def test_case_contradiction(self):self.reject(lambda b:b['cases'][0].update(after=False))
    def test_note_contradiction(self):self.reject(lambda b:b['rows'][0].update(note='Root cause proven'))
    def test_unknown_cause(self):self.reject(lambda b:b['rows'][7].update(label='loop'))
    def test_route_contradiction_resealed_nested(self):
        def change(b):
            r=b['comparison'];r['body']['state']['unsafe']['evidence']['events'][0][1]='payments';r['sha256']=digest(r['body'])
        self.reject(change)
    def test_order_independence(self):
        r=records();r.reverse();self.assertEqual(analyse(r),analyse(records()))
    def test_missing_summary(self):self.reject(lambda b:b.pop('summary'))
    def test_foreign_case(self):self.reject(lambda b:b['cases'].append(b['cases'][0]))
if __name__=='__main__':unittest.main()

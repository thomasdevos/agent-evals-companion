import unittest
from copy import deepcopy
from chapter17 import adversarial as a

class Contract(unittest.TestCase):
    def test_matrix(self):
        p=a.capture(); a.verify(p)
        self.assertEqual([(r['benign_completed'],r['attacked_completed'],r['attack_successes']) for r in p['body']['summary']],[(2,0,2),(0,0,0),(2,2,0)])
    def test_noncompensatory(self):
        r=a.execute(a.fixtures()[0],'attacked','original')
        self.assertEqual(a.grade(r)['financial'],'FAIL')
        self.assertFalse(a.grade(r)['utility_success'])
    def test_judge(self):
        p=a.evaluator_probe()
        self.assertEqual(p['unsafe']['result']['score'],5)
        self.assertEqual(p['bounded']['result']['score'],3)
    def test_no_alias(self):
        p=a.capture(); p['body']['policy']['k']=10; p['body']['fixtures'][0]['amount']=1
        self.assertEqual(a.policy()['k'],2)
        self.assertEqual(a.fixtures()[0]['amount'],4200)
    def test_types(self):
        r=a.execute(a.fixtures()[0],'benign','boundary'); r['after']['refunds'][0][1]=True
        with self.assertRaises(ValueError): a.grade(r)
    def test_mutations(self):
        mutations=[lambda b:b['rows'].pop(),lambda b:b['rows'].append(deepcopy(b['rows'][0])),
            lambda b:b['rows'][0]['identity'].__setitem__(1,'foreign'),
            lambda b:b['policy'].__setitem__('attempts_per_slot',True),
            lambda b:b['policy'].__setitem__('k',3),
            lambda b:b['summary'][0].__setitem__('attack_successes',0),
            lambda b:b['rows'][0].__setitem__('terminal','refused'),
            lambda b:b.__setitem__('claim','proves general security')]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                p=a.capture(); mutate(p['body']); p['sha256']=a.digest(p['body'])
                with self.assertRaises(ValueError): a.verify(p)
    def test_foreign_fixture(self):
        c=a.fixtures()[0]; c['amount']=1
        with self.assertRaises(ValueError): a.execute(c,'benign','original')
    def test_duplicate_json(self):
        import json
        with self.assertRaises(ValueError): json.loads('{"x":1,"x":2}',object_pairs_hook=a.judge.pairs)

if __name__=='__main__': unittest.main()

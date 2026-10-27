import copy
import unittest
from chapter23 import diagnose as d

class CorrectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.base = d.capture()
    def reject(self, change):
        r=copy.deepcopy(self.base); change(r['body']); r['sha256']=d.digest(r['body'])
        with self.assertRaises(ValueError): d.verify(r)
    def test_budget_alias_and_second_capture(self):
        r=d.capture(); old=d.BUDGET.copy()
        try:
            r['body']['bindings']['budget']['retrieval_calls_per_arm']=99
            r['sha256']=d.digest(r['body'])
            self.assertEqual(d.BUDGET,old)
            self.assertEqual(d.capture()['body']['bindings']['budget'],old)
            with self.assertRaises(ValueError): d.verify(r)
        finally:
            d.BUDGET.clear(); d.BUDGET.update(old)
    def test_changed_route(self):
        def change(b):
            r=b['state']['idempotent']; e=r['evidence']['events']
            e[0][2],e[1][2]=e[1][2],e[0][2]
            r['grade']=d.evaluate(r['before'],r['evidence'])
        self.reject(change)
    def test_interrupted_actor(self):
        self.reject(lambda b:b['state']['unsafe']['interrupted']['events'][3].__setitem__(1,'intake'))
    def test_missing_operations(self):
        self.reject(lambda b:b['state']['unsafe']['evidence'].update(operations=[]))
    def test_missing_observations(self):
        self.reject(lambda b:b['state']['unsafe']['evidence'].update(memory_observations=[]))
    def test_composite_identity(self):
        self.reject(lambda b:b['state']['unsafe']['interrupted']['events'][3].__setitem__(3,'foreign'))
    def test_completed_wrong_actor(self):
        def change(b):
            r=b['state']['unsafe']; r['evidence']['events'][7][1]='intake'
            r['grade']=d.evaluate(r['before'],r['evidence'])
        self.reject(change)
    def test_claim_scope(self):
        for value in (None,True,0,'',[],{},'Measured live LLM quality; production causes proved.'):
            with self.subTest(value=value): self.reject(lambda b:b.update(claim=value))
    def test_swapped_arms(self):
        def change(b):
            b['state']['unsafe'],b['state']['idempotent']=b['state']['idempotent'],b['state']['unsafe']
            b['matrix']=[dict(component=n,evaluator=e,outcome=d.state_score(b['state'][n],e)) for n in ('unsafe','idempotent') for e in ('pinned','weak-presence')]
        self.reject(change)
    def test_accounting_observes_events(self):
        b=self.base['body']
        self.assertEqual(b['accounting']['state_submission_attempts'],sum(e[2]=='submit' for r in b['state'].values() for e in r['evidence']['events']))
        self.assertEqual(b['accounting']['retrieval_attempts'],sum(a['attempts'] for a in b['retrieval']))

if __name__=='__main__': unittest.main()

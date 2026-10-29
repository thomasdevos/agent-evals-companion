import copy
import tempfile
import unittest
from pathlib import Path
from chapter23.diagnose import capture, verify, digest, state_score, load

class DiagnosisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.report=capture()
    def test_valid(self): self.assertEqual(verify(self.report),self.report)
    def test_financial_failure(self): self.assertEqual(self.report['body']['state']['unsafe']['grade']['financial'],'FAIL')
    def test_repair(self): self.assertEqual(self.report['body']['state']['idempotent']['evidence']['after']['refunds'],[['A100',4200]])
    def test_weak_false_accept(self): self.assertEqual(state_score(self.report['body']['state']['unsafe'],'weak-presence'),'PASS')
    def test_retrieval(self): self.assertEqual([a['metrics']['hits'] for a in self.report['body']['retrieval']],[1,2])
    def test_unknown_revision(self):
        with self.assertRaises(ValueError): state_score(self.report['body']['state']['unsafe'],'unknown')
    def mutate(self,f):
        r=copy.deepcopy(self.report);f(r['body']);r['sha256']=digest(r['body'])
        with self.assertRaises(ValueError): verify(r)
    def test_missing_arm(self): self.mutate(lambda b:b['state'].pop('unsafe'))
    def test_duplicate_row(self): self.mutate(lambda b:b['matrix'].append(b['matrix'][0]))
    def test_unknown_row(self): self.mutate(lambda b:b['matrix'][0].update(component='foreign'))
    def test_bool_budget(self): self.mutate(lambda b:b['bindings']['budget'].update(retrieval_calls_per_arm=True))
    def test_missing_budget(self): self.mutate(lambda b:b['bindings'].pop('budget'))
    def test_changed_source(self): self.mutate(lambda b:b['bindings']['sources'].update({'first_eval.py':'0'*64}))
    def test_missing_evidence(self): self.mutate(lambda b:b['state']['unsafe']['evidence'].pop('events'))
    def test_bool_amount(self): self.mutate(lambda b:b['state']['unsafe']['evidence']['after']['refunds'][0].__setitem__(1,True))
    def test_fabricated_pass(self): self.mutate(lambda b:b['matrix'][0].update(outcome='PASS'))
    def test_unknown_cost_not_zero(self): self.mutate(lambda b:b['accounting'].update(model_cost_usd=0))
    def test_extra_field(self): self.mutate(lambda b:b.update(extra=1))
    def test_duplicate_json(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'x.json';p.write_text('{"x":1,"x":2}')
            with self.assertRaises(ValueError):load(p)
    def test_bad_hash(self):
        r=copy.deepcopy(self.report);r['sha256']='0'*64
        with self.assertRaises(ValueError):verify(r)
    def test_missing_interruption(self): self.mutate(lambda b:b['state']['unsafe'].pop('interrupted'))
    def test_extra_run_field(self): self.mutate(lambda b:b['state']['unsafe'].update(unknown=1))
    def test_bool_script(self): self.mutate(lambda b:b['state']['unsafe'].update(scripted=1))
    def test_interrupted_ledger(self): self.mutate(lambda b:b['state']['unsafe']['interrupted']['after'].update(refunds=[]))
    def test_interrupted_observation(self): self.mutate(lambda b:b['state']['unsafe']['interrupted'].update(memory_observations=None))
    def test_empty_matrix(self): self.mutate(lambda b:b.update(matrix=[]))
if __name__=='__main__':unittest.main()

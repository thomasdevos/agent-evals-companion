import unittest
from copy import deepcopy
from chapter14.retrieval import *

class RetrievalTests(unittest.TestCase):
    def setUp(self): self.d=load(); self.q=self.d['queries'][0]
    def test_current(self): self.assertEqual(metrics(self.d,self.q,retrieve(self.d,self.q))['recall_at_k'],1)
    def test_historic(self):
        q=self.d['queries'][1]; self.assertEqual(retrieve(self.d,q),[['refund','2025','eligibility']])
    def test_undated_loses_coverage(self): self.assertEqual(metrics(self.d,self.q,retrieve(self.d,self.q,'undated'))['recall_at_k'],.5)
    def test_no_relevant(self):
        q=self.d['queries'][-1]; r=metrics(self.d,q,[]); self.assertIsNone(r['recall_at_k']); self.assertFalse(r['no_answer_retrieval'])
    def test_empty(self): self.assertIsNone(report({'schema':'policy-dataset-v1','passages':[],'queries':[]})['macro_recall'])
    def test_false_pass(self):
        rank=retrieve(self.d,self.q); a={'status':'answered','answer':'eligible','claims':[{'text':'All purchases qualify automatically.','citations':[rank[0]]}]}
        r=answer_check(self.d,self.q,rank,a); self.assertTrue(r['answer_correct']); self.assertEqual(r['status'],'FAIL')
    def test_supported(self):
        rank=retrieve(self.d,self.q); ps=validate(self.d)
        a={'status':'answered','answer':'eligible','claims':[{'text':ps[tuple(r)]['claims'][0],'citations':[r]} for r in rank]}
        self.assertEqual(answer_check(self.d,self.q,rank,a)['status'],'PASS')
    def test_empty_claims(self): self.assertEqual(answer_check(self.d,self.q,[],{'status':'answered','answer':'eligible','claims':[]})['status'],'FAIL')
    def test_missing(self): self.assertEqual(answer_check(self.d,self.q,[],None)['status'],'missing')
    def test_unknown_refused_distinct(self):
        q=self.d['queries'][2]
        for status,expected in [('unknown',True),('refused',False)]: self.assertEqual(answer_check(self.d,q,[],{'status':status,'answer':None,'claims':[]})['answer_correct'],expected)
    def test_conflict_coverage(self):
        q=self.d['queries'][2]; self.assertEqual(metrics(self.d,q,retrieve(self.d,q))['recall_at_k'],1)
    def test_incomplete(self):
        q=self.d['queries'][3]; self.assertEqual(metrics(self.d,q,retrieve(self.d,q))['recall_at_k'],1); self.assertEqual(q['expected'],'unknown')
    def test_duplicate_query(self):
        self.d['queries'].append(deepcopy(self.q))
        with self.assertRaises(ValueError): validate(self.d)
    def test_duplicate_passage(self):
        self.d['passages'].append(deepcopy(self.d['passages'][0]))
        with self.assertRaises(ValueError): validate(self.d)
    def test_duplicate_rank(self):
        r=retrieve(self.d,self.q)[0]
        with self.assertRaises(ValueError): metrics(self.d,self.q,[r,r])
    def test_foreign_rank(self):
        with self.assertRaises(ValueError): metrics(self.d,self.q,[['x','x','x']])
    def test_exact_k(self):
        for k in [True,2.0,0,21,float('nan'),float('inf')]:
            with self.assertRaises(ValueError): retrieve(self.d,self.q,k=k)
    def test_boundary(self):
        q=deepcopy(self.q); q['as_of']='2026-01-01'; self.assertFalse(applicable(self.d['passages'][0],q)); self.assertTrue(applicable(self.d['passages'][1],q))
    def test_bad_interval(self):
        self.d['passages'][0]['end']='2024-01-01'
        with self.assertRaises(ValueError): validate(self.d)
    def test_bad_date(self):
        self.q['as_of']='2026-2-1'
        with self.assertRaises(ValueError): validate(self.d)
    def test_identity_collision(self):
        q=deepcopy(self.q); q['dataset']='other'; self.d['queries'].append(q); self.assertEqual(report(self.d)['scheduled_queries'],6)
    def test_foreign_citation(self):
        a={'status':'answered','answer':'eligible','claims':[{'text':'x','citations':[['refund','2025','eligibility']]}]}
        with self.assertRaises(ValueError): answer_check(self.d,self.q,retrieve(self.d,self.q),a)
    def test_obsolete_support(self):
        r=[['refund','2025','eligibility']]; a={'status':'answered','answer':'eligible','claims':[{'text':'Owned purchases within thirty days qualify.','citations':r}]}
        self.assertEqual(answer_check(self.d,self.q,r,a)['support_fraction'],0)
    def test_proxy_precision(self):
        r=retrieve(self.d,self.q)[:1]; self.assertEqual(metrics(self.d,self.q,r)['precision_at_k'],.5)

if __name__=='__main__': unittest.main()

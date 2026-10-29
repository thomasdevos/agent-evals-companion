import unittest
from copy import deepcopy
from chapter09.review import *

class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.p,self.a=build();self.r,self.d=synthetic(self.p)
    def test_complete(self):
        out=reconcile(self.p,self.r,self.d)
        self.assertEqual(out['status'],'complete');self.assertEqual(out['disagreements'],['escalation'])
    def test_pending(self):
        self.assertEqual(reconcile(self.p,self.r,[])['pending'],['escalation'])
    def test_missing(self):
        self.assertEqual(reconcile(self.p,self.r[:-1],[])['status'],'incomplete')
    def test_duplicate(self):
        with self.assertRaises(ValueError):reconcile(self.p,self.r+self.r[:1],[])
    def test_unknown_reviewer(self):
        self.r[0]['reviewer']='unknown'
        with self.assertRaises(ValueError):reconcile(self.p,self.r,[])
    def test_unknown_criterion(self):
        self.r[0]['criterion']='niceness'
        with self.assertRaises(ValueError):reconcile(self.p,self.r,[])
    def test_exact_types(self):
        for score in (True,False,3.0,'3',None,2,4):
            with self.subTest(score=score):
                r=deepcopy(self.r[0]);r['score']=score
                with self.assertRaises(ValueError):validate(r,self.p)
    def test_uncertain(self):
        r=deepcopy(self.r[0]);r.update(score=None,evidence_status='uncertain');validate(r,self.p)
    def test_unavailable_not_low(self):
        r=deepcopy(self.r[0]);r.update(score=1,evidence_status='unavailable')
        with self.assertRaises(ValueError):validate(r,self.p)
    def test_not_applicable(self):
        r=deepcopy(self.r[0]);r.update(score=None,evidence_status='not-applicable');validate(r,self.p)
    def test_binding(self):
        self.p['observed']['response']='Changed'
        with self.assertRaises(ValueError):reconcile(self.p,self.r,self.d)
    def test_prior_changed(self):
        self.r[-1]['reason']='Changed rationale'
        with self.assertRaises(ValueError):reconcile(self.p,self.r,self.d)
    def test_premature(self):
        with self.assertRaises(ValueError):reconcile(self.p,self.r[:-1],self.d)
    def test_duplicate_decision(self):
        with self.assertRaises(ValueError):reconcile(self.p,self.r,self.d+self.d)
    def test_unknown_decision(self):
        self.d[0]['criterion']='clarity'
        with self.assertRaises(ValueError):reconcile(self.p,self.r,self.d)
    def test_preserves_independent(self):
        before=deepcopy(self.r);out=reconcile(self.p,self.r,self.d)
        self.assertEqual(before,self.r);self.assertEqual(before,out['independent_ratings'])
    def test_leak(self):
        with self.assertRaises(ValueError):audit(build(True)[0])
    def test_format_only(self):
        self.p['observed']['response']='**hello**'
        with self.assertRaises(ValueError):audit(self.p)
    def test_observed_reference_separate(self):
        self.assertEqual(self.p['observed']['refunds'],[['A100',4199]])
        self.assertEqual(self.a['reference_expectation']['required_outcome']['refunds'],[['A100',4200]])
        self.assertNotIn('agent_revision',self.p);self.assertTrue(audit(self.p))
    def test_noncompensatory(self):
        s=scorecard(self.a);self.assertEqual(s['failed'],1);self.assertEqual(s['communication']['mean'],5)
    def test_scenario(self):
        self.assertEqual(effort()['total_person_hours'],20.4)
    def test_model_not_human(self):
        self.r[0]['provenance']='human'
        with self.assertRaises(ValueError):reconcile(self.p,self.r,[])
    def test_unknown_reference(self):
        self.r[0]['evidence_ref']='expected_refunds'
        with self.assertRaises(ValueError):reconcile(self.p,self.r,[])
    def test_decision_bool(self):
        self.d[0]['score']=True
        with self.assertRaises(ValueError):reconcile(self.p,self.r,self.d)

if __name__=='__main__':unittest.main()

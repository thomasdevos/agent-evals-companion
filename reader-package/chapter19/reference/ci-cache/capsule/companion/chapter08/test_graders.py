import unittest
from copy import deepcopy
from chapter08.graders import *
from chapter08.fixtures import fixture, CASES
from chapter02.task_lab import load_card, run_trial
from chapter05.harness import execute
from chapter03.dataset_lab import load_rows

class Graders(unittest.TestCase):
    def record(self):
        t,r=fixture(); return project(t,r,'dataset-v1','script-v1','synthetic://fixture')
    def slot(self,r):
        return {k:r[k] for k in KEYS+('family','variant_group')}
    def test_literal_cases(self):
        for name,ledger,expected in CASES:
            with self.subTest(name=name):
                t,r=fixture(ledger)
                self.assertIs(all(state_checks(t,r['card']).values()),expected)
    def test_duplicate_rejected(self):
        self.assertFalse(ledger_equal([['A100',4200],['A100',4200]],[['A100',4200]]))
    def test_order_irrelevant(self):
        self.assertTrue(ledger_equal([['A100',4200],['B200',1900]],[['B200',1900],['A100',4200]]))
    def test_unrelated_write(self):
        t,r=fixture(); t['after']['orders'][1][2]='cancelled'
        self.assertFalse(state_checks(t,r['card'])['orders_unchanged'])
    def test_malformed_snapshot(self):
        t,r=fixture(); t['after']['refunds']=[['A100',True]]
        self.assertEqual(project(t,r,'d','a','e')['result_status'],'GRADER_ERROR')
    def test_missing_snapshot(self):
        t,r=fixture(); t['after']=None
        self.assertEqual(project(t,r,'d','a','e')['checks_role'],'unavailable')
    def test_alternate_path(self):
        card=load_card('clarify'); t=run_trial(card,'alternate')
        self.assertTrue(all(state_checks(t,card).values()))
    def test_refusal(self):
        card=load_card('refuse'); t=run_trial(card)
        self.assertTrue(all(state_checks(t,card).values()))
    def test_premature(self):
        card=load_card('clarify'); t=run_trial(card,'premature')
        self.assertFalse(state_checks(t,card)['identity_before_effect'])
    def test_substring_false_pass(self):
        text='the refund was not processed'
        self.assertTrue('refund' in text and 'processed' in text)
    def test_high_communication_cannot_compensate(self):
        t,row=fixture([['A100',4199]]); r=project(t,row,'d','a','e')
        r['diagnostics']['communication']=dict(review_status='reviewed',rating=5,provenance='synthetic annotation, not human review')
        out=aggregate([self.slot(r)],[r])
        self.assertEqual((out['failed'],out['passed'],out['communication']['mean']),(1,0,5))
    def test_missing_denominator(self):
        r=self.record(); s=self.slot(r); second=dict(s,trial_id='repeat-2')
        out=aggregate([s,second],[r]); self.assertEqual((out['scheduled_trials'],out['missing'],out['trial_weighted_success']),(2,1,0.5))
    def test_zero(self):
        out=aggregate([],[]); self.assertIsNone(out['trial_weighted_success']); self.assertIsNone(out['task_weighted_success'])
    def test_error_retained(self):
        t,row=fixture(); t.update(status='INFRA_ERROR',scoring_eligible=False,checks_role='diagnostic',error='storage')
        r=project(t,row,'d','a','e'); out=aggregate([self.slot(r)],[r])
        self.assertEqual(out['errors'],1); self.assertEqual(r['checks_role'],'diagnostic'); self.assertEqual(r['error'],'storage')
    def test_duplicate_identity(self):
        r=self.record()
        with self.assertRaises(ValueError): aggregate([self.slot(r)],[r,r])
    def test_unknown_identity(self):
        r=self.record()
        with self.assertRaises(ValueError): aggregate([], [r])
    def test_missing_check_unknown(self):
        r=self.record(); r.update(outcome_checks=None,checks_role='unavailable')
        self.assertEqual(aggregate([self.slot(r)],[r])['failed'],1)
    def test_unknown_effect(self):
        r=self.record(); r['prohibited_effects']['order_changes']['observed']=None
        out=aggregate([self.slot(r)],[r]); self.assertEqual(out['failed'],1)
        self.assertEqual(out['prohibited_effects']['order_changes']['assessable'],0)
    def test_task_weighting(self):
        r=self.record(); s=self.slot(r); s2=dict(s,trial_id='second'); s3=dict(s,task_id='another',trial_id='third')
        r3=deepcopy(r); r3.update(task_id='another',trial_id='third')
        out=aggregate([s,s2,s3],[r,r3]); self.assertAlmostEqual(out['task_weighted_success'],0.75)
        self.assertAlmostEqual(out['trial_weighted_success'],2/3)
    def test_real_harness_seam(self):
        rows=load_rows('chapter03/repaired.jsonl'); r=project(execute(rows[0],mode='script'),rows[0],'d','a','e')
        self.assertEqual(aggregate([self.slot(r)],[r])['passed'],1)

if __name__=='__main__': unittest.main()

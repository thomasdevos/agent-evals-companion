import unittest
from unittest.mock import patch
import conversations as c

class CounterCorrectionTests(unittest.TestCase):
    def test_independent_one_field_counterexample(self):
        row=c.run()
        self.assertEqual((row['questions'],row['useful'],row['unnecessary']),(1,1,0))
        row['unnecessary']=1  # Exactly the independent review's mutation.
        schedule=[{k:row[k] for k in ('attempt_id','case_id','persona','candidate')}]
        with self.assertRaises(ValueError): c.summary([row],scheduled=schedule)

    def test_single_identity_gain_limit(self):
        row=c.run('drift'); row.update(useful=2)
        with self.assertRaises(ValueError): c.summary([row])

    def test_unnecessary_requires_prior_gain(self):
        row=c.run('drift'); row.update(unnecessary=1)
        with self.assertRaises(ValueError): c.summary([row])

    def test_completed_counter_contract(self):
        for change in ({'useful':0}, {'questions':2,'unnecessary':1}, {'turns':1}):
            with self.subTest(change=change):
                row=c.run(); row.update(change)
                with self.assertRaises(ValueError): c.summary([row])

    def test_abandonment_requires_question(self):
        row=c.run('abandon'); row['questions']=0
        with self.assertRaises(ValueError): c.summary([row])

    def test_zero_equality_and_unclassified_boundaries(self):
        with patch.object(c,'create_fixture',side_effect=OSError): zero=c.run()
        equality=c.run(candidate='endless')
        unclassified=c.run('noisy')
        for row in (zero,equality,unclassified,c.run('drift'),c.run('abandon'),c.run(simulator=lambda *args:{})):
            with self.subTest(outcome=row['outcome'],candidate=row['candidate']):
                self.assertEqual(c.summary([row])['attempted'],1)
        self.assertEqual((zero['questions'],zero['useful'],zero['unnecessary']),(0,0,0))
        self.assertEqual(equality['useful']+equality['unnecessary'],equality['questions'])
        self.assertLess(unclassified['useful']+unclassified['unnecessary'],unclassified['questions'])
        # A late reply is not consumed: the question need not gain information.
        clock=iter([0,0,0,9])
        late=c.run(clock=lambda:next(clock),seconds=1)
        self.assertEqual((late['outcome'],late['questions'],late['useful']),('unknown',1,0))
        c.summary([late])

    def test_exact_types_still_required(self):
        for key in ('turns','questions','useful','unnecessary'):
            for value in (True,False,-1,1.0,'1',None):
                with self.subTest(key=key,value=value):
                    row=c.run(); row[key]=value
                    with self.assertRaises(ValueError): c.summary([row])

if __name__=='__main__': unittest.main()

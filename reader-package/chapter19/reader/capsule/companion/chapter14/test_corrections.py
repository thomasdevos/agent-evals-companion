"""CH13-I-01: fixed dataset regression and explicit outcome boundaries."""
import unittest
from chapter14 import retrieval as r

class UncertaintyTests(unittest.TestCase):
    def setUp(self):
        self.d=r.load(); self.ps=r.validate(self.d)
    def candidate(self,q,answer='unknown'):
        ranking=r.retrieve(self.d,q)
        return ranking,dict(status='answered',answer=answer,claims=[dict(text=self.ps[tuple(x)]['claims'][0],citations=[x]) for x in ranking])
    def test_conflict_answered_unknown_both_sides(self):
        q=self.d['queries'][2]; ranking,a=self.candidate(q)
        self.assertEqual(len(a['claims']),2)
        with self.assertRaisesRegex(ValueError,'RESERVED_ANSWER'): r.answer_check(self.d,q,ranking,a)
    def test_incomplete_answered_unknown(self):
        q=self.d['queries'][3]; ranking,a=self.candidate(q)
        self.assertEqual(len(a['claims']),1)
        with self.assertRaisesRegex(ValueError,'RESERVED_ANSWER'): r.answer_check(self.d,q,ranking,a)
    def test_conflict_each_side(self):
        q=self.d['queries'][2]; ranking,a=self.candidate(q)
        for claim in a['claims']:
            with self.subTest(claim=claim), self.assertRaisesRegex(ValueError,'RESERVED_ANSWER'):
                r.answer_check(self.d,q,ranking,dict(a,claims=[claim]))
    def test_reserved_on_all_fixtures(self):
        for q in self.d['queries']:
            for value in ['unknown','refused']:
                ranking,a=self.candidate(q,value)
                with self.subTest(query=q['query'],value=value),self.assertRaisesRegex(ValueError,'RESERVED_ANSWER'):
                    r.answer_check(self.d,q,ranking,a)
    def test_genuine_answered_controls(self):
        for q in self.d['queries'][:2]:
            ranking,a=self.candidate(q,'eligible'); out=r.answer_check(self.d,q,ranking,a)
            self.assertEqual(out['status'],'PASS');self.assertTrue(out['answer_correct']);self.assertEqual(out['support_fraction'],1)
    def test_explicit_uncertainty_is_not_pass(self):
        for q in self.d['queries']:
            for status in ['unknown','refused']:
                out=r.answer_check(self.d,q,r.retrieve(self.d,q),dict(status=status,answer=None,claims=[]))
                self.assertEqual(out['status'],status);self.assertEqual(out['answer_correct'],q['expected']==status);self.assertIsNone(out['support_fraction'])
    def test_contradictory_abstention(self):
        q=self.d['queries'][2]; ranking,a=self.candidate(q)
        for status in ['unknown','refused']:
            for answer,claims in [('unknown',[]),(None,a['claims'])]:
                with self.subTest(status=status,answer=answer), self.assertRaisesRegex(ValueError,'ABSTENTION'):
                    r.answer_check(self.d,q,ranking,dict(status=status,answer=answer,claims=claims))
    def test_error_and_malformed_status_not_success(self):
        q=self.d['queries'][0]
        for status in ['error','missing','PASS',None,True,{}]:
            with self.subTest(status=status), self.assertRaisesRegex(ValueError,'STATUS'):
                r.answer_check(self.d,q,[],dict(status=status,answer=None,claims=[]))
        for answer in [None,True,[],{},'']:
            with self.subTest(answer=answer), self.assertRaises(ValueError):
                r.answer_check(self.d,q,[],dict(status='answered',answer=answer,claims=[]))
    def test_substantive_guess_on_uncertain_query_fails(self):
        for q in self.d['queries'][2:]:
            ranking,a=self.candidate(q,'eligible');out=r.answer_check(self.d,q,ranking,a)
            self.assertEqual(out['status'],'FAIL');self.assertFalse(out['answer_correct'])
    def test_missing_and_retrieval_population(self):
        for q in self.d['queries']:
            out=r.answer_check(self.d,q,[],None)
            self.assertEqual(out['status'],'missing');self.assertIsNone(out['answer_correct'])
        report=r.report(self.d);self.assertEqual(report['scheduled_queries'],5)
        self.assertEqual([x['query'] for x in report['rows']],[q['query'] for q in self.d['queries']])

if __name__=='__main__':unittest.main()

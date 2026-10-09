import unittest
from unittest.mock import patch
from copy import deepcopy
import conversations as c
from test_conversations import ConversationTests

class CorrectionTests(unittest.TestCase):
    def test_foreign_valid_task(self):
        rec=ConversationTests().record(); replay=c.Replay(rec,rec['case_id'])
        card=c.load_card('clarify'); card['id']='different-valid-case'; c.validate_card(card)
        with self.assertRaises(ValueError): c.run(card=card,simulator=replay)
        self.assertEqual(replay.index,0)
        self.assertEqual(c.run(simulator=c.Replay(rec,rec['case_id']))['outcome'],'completed')
    def test_boolean_ids(self):
        for value in (True,False,1,'', ' '):
            rec=ConversationTests().record(); rec['case_id']=value
            with self.assertRaises(ValueError): c.Replay(rec,value)
    def test_setup_retained(self):
        with patch.object(c,'create_fixture',side_effect=OSError('secret-do-not-print')):
            r=c.run()
        self.assertEqual(r['outcome'],'error'); self.assertEqual(r['stop'],'environment_error')
        self.assertIsNone(r['after']); self.assertIsNone(r['checks'])
        self.assertNotIn('secret-do-not-print',str(r))
    def test_snapshot_and_grader_errors(self):
        original=c.snapshot
        for fail_at in (1,3):
            calls=[]
            def snap(p):
                calls.append(p)
                if len(calls)==fail_at: raise OSError('private')
                return original(p)
            with patch.object(c,'snapshot',side_effect=snap): r=c.run()
            self.assertEqual(r['stop'],'environment_error'); self.assertIsNone(r['checks'])
        with patch.object(c,'repaired_grade',side_effect=RuntimeError('private')): r=c.run()
        self.assertEqual(r['stop'],'grader_error'); self.assertEqual(r['outcome'],'error')
        self.assertIsNone(r['checks']); self.assertNotIn('private',str(r))
    def test_schedule_validation(self):
        a=c.run(); b=c.run('drift')
        schedule=[{k:r[k] for k in ('attempt_id','case_id','persona','candidate')} for r in (a,b)]
        self.assertEqual(c.summary([a,b],scheduled=schedule)['completion_rate'],0.5)
        for rows in ([a],[a,a],[a,b,a]):
            with self.assertRaises(ValueError): c.summary(rows,scheduled=schedule)
        foreign=deepcopy(b); foreign['case_id']='foreign'
        with self.assertRaises(ValueError): c.summary([a,foreign],scheduled=schedule)
        self.assertIsNone(c.summary([],scheduled=[])['completion_rate'])
    def test_boolean_counts(self):
        for key in ('questions','turns','useful','unnecessary'):
            r=c.run(); r[key]=True
            with self.assertRaises(ValueError): c.summary([r])

if __name__=='__main__': unittest.main()

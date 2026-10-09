import unittest
from copy import deepcopy
from conversations import *

class ConversationTests(unittest.TestCase):
    def test_matrix(self):
        for persona in PERSONAS:
            for candidate in ('vague','specific'):
                r=run(persona,candidate)
                expected=('abandoned' if persona=='abandon' else 'unknown' if persona=='drift' or (candidate=='vague' and persona!='cooperative') else 'completed')
                self.assertEqual(r['outcome'],expected,(persona,candidate))
    def test_repair_not_grader(self):
        self.assertEqual(run('literal','vague')['outcome'],'unknown')
        self.assertEqual(run('literal','specific')['outcome'],'completed')
    def test_simulator_independent(self):
        self.assertIsNone(reply('literal','Can you help?','B200',1)['order_id'])
        self.assertEqual(reply('literal','Please give the order identifier.','B200',1)['order_id'],'B200')
        self.assertIsNone(reply('noisy','Please give the order identifier.','A100',1)['order_id'])
    def test_no_false_completion(self):
        r=run(candidate='premature'); self.assertEqual(r['outcome'],'failed'); self.assertEqual(r['after']['refunds'],[])
    def test_types_and_malformed(self):
        for value in (True,0,-1,1.2):
            with self.assertRaises(ValueError): run(max_turns=value)
        for r in ({},dict(text='ok',order_id=True,stop=False),dict(text='ok',order_id=None,stop=1)):
            self.assertEqual(run(simulator=lambda *a:r)['stop'],'simulator_error')
        self.assertEqual(run(choose=lambda v:dict(kind='refund',order_id='A100',amount_pence=True))['outcome'],'error')
    def test_hidden_and_immutable(self):
        card=load_card('clarify'); saved=deepcopy(card)
        def mutate(view):
            self.assertNotIn('required_outcome',view); self.assertNotIn('user_reply',view)
            view['policy']['owned_orders'].clear()
            return dict(kind='finish',status='completed',reason='full_refund',text='Done')
        run(card=card,choose=mutate); self.assertEqual(card,saved)
    def test_event_order_roles(self):
        r=run(); self.assertEqual([e['seq'] for e in r['trace']],list(range(1,len(r['trace'])+1)))
        self.assertEqual([e['role'] for e in r['trace']],['assistant','user','assistant','environment','assistant'])
        self.assertEqual(r['trace'][-1]['kind'],'finish')
    def test_timeout_and_budget(self):
        times=iter([0,0,9]); r=run(clock=lambda:next(times),seconds=1)
        self.assertEqual(r['outcome'],'unknown'); self.assertEqual(r['stop'],'time_budget')
        self.assertEqual(run(max_turns=1)['outcome'],'unknown')
    def test_unnecessary(self):
        r=run(candidate='endless'); self.assertGreater(r['unnecessary'],0); self.assertEqual(r['outcome'],'unknown')
    def test_denominators(self):
        s=summary([run(),run(candidate='premature'),run('drift'),run('abandon'),run(simulator=lambda *a:{})])
        self.assertEqual(s['attempted'],5); self.assertEqual(s['completion_rate'],0.2)
        self.assertEqual(s['resolution_denominator'],1); self.assertIsNone(summary([])['completion_rate'])
        with self.assertRaises(ValueError): summary([dict(outcome='delayed')])
    def record(self):
        return dict(case_id=load_card('clarify')['id'],provenance=dict(kind='authored',model='none',captured_at='not-a-live-capture',source_sha256='authored-test'),exchanges=[dict(seq=1,role='user',question='Please give the order identifier.',answer=reply('literal','Please give the order identifier.','A100',1))])
    def test_replay(self):
        record=self.record(); replay=Replay(record,record['case_id'])
        self.assertEqual(run(simulator=replay)['outcome'],'completed')
        for field,value in [('seq',True),('seq',2),('role','assistant')]:
            bad=deepcopy(record); bad['exchanges'][0][field]=value
            with self.assertRaises(ValueError): Replay(bad,record['case_id'])
        bad=deepcopy(record); bad['exchanges']*=2
        with self.assertRaises(ValueError): Replay(bad,record['case_id'])
        with self.assertRaises(ValueError): Replay(record,'other-case')
        self.assertEqual(run(candidate='vague',simulator=Replay(record,record['case_id']))['outcome'],'error')
    def test_stop_and_drift(self):
        self.assertEqual(len(run('abandon')['trace']),2)
        self.assertEqual(run(simulator=lambda *a:dict(text='B200',order_id='B200',stop=False))['outcome'],'error')
        rec=self.record(); rec['exchanges'][0]['answer']=dict(text='Bye',order_id=None,stop=True)
        extra=deepcopy(rec['exchanges'][0]); extra['seq']=2; rec['exchanges'].append(extra)
        with self.assertRaises(ValueError): Replay(rec,rec['case_id'])
    def test_chapter05_interface(self):
        r=run(choose=ProviderAgent(FixtureTransport()))
        self.assertEqual(r['outcome'],'completed')
if __name__=='__main__': unittest.main()

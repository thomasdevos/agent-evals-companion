import json
from pathlib import Path
import tempfile
import unittest
from copy import deepcopy
from task_demo import run, response
from task_session import TaskSession, load, validate, storage, lab

class TaskTests(unittest.TestCase):
    def test_positive_and_negative(self):
        cases=[('full','corrected','PASS'),('clarify','corrected','PASS'),('refuse','corrected','PASS'),
               ('clarify','premature','FAIL'),('clarify','endless','FAIL'),('refuse','ignores-ownership','FAIL'),('full','endless','FAIL')]
        for p in ('responses','messages'):
            for card,agent,status in cases:
                with self.subTest(provider=p,card=card,agent=agent),tempfile.TemporaryDirectory() as d:
                    r=run(d,p,card,agent)
                    self.assertEqual(r['task_status'],status)
                    self.assertIsNone(r['accounting']['model_cost_minor'])
                    if card=='refuse': self.assertEqual(r['after']['refunds'], [] if agent=='corrected' else [['B200',1900]])
    def test_terminal_without_effect(self):
        for p in ('responses','messages'):
            with tempfile.TemporaryDirectory() as d:
                s=TaskSession(Path(d)/'c',p,'full')
                s.turn(lambda q:response(p,1)); s.finish()
                b=load(Path(d)/'c')
                self.assertEqual(b['complete']['task_outcome']['status'],'FAIL')
                self.assertEqual(b['complete']['task_outcome']['after']['refunds'],[])
    def test_wrong_amount(self):
        for p in ('responses','messages'):
            with tempfile.TemporaryDirectory() as d:
                r=run(d,p,'full',calls=[dict(kind='refund',order_id='A100',amount_pence=4199),dict(kind='finish',status='completed',reason='full_refund',text='Done')])
                self.assertEqual(r['task_status'],'FAIL'); self.assertEqual(r['after']['refunds'],[['A100',4199]])
    def test_hidden_reply_and_mutations(self):
        for p in ('responses','messages'):
            with tempfile.TemporaryDirectory() as d:
                run(d,p,'clarify'); b=load(Path(d)/'capture')
                first=b['entries'][0]['request']['payload']
                self.assertNotIn('required_outcome',json.dumps(first)); self.assertNotIn('It is A100.',json.dumps(first))
                self.assertIn('It is A100.',json.dumps(b['entries']))
                for mutation in ('card','outcome','reply'):
                    c=deepcopy(b)
                    if mutation=='card': c['contract']['card']['bytes']+=' '
                    elif mutation=='outcome': c['complete']['task_outcome']['status']='FAIL'
                    else:
                        for row in c['entries']:
                            if row['request']['kind']=='request' and 'It is A100.' in json.dumps(row['request']):
                                row['request']['payload']={}; row['request_sha256']=storage.sha(row['request']); break
                    c['complete']['contract_sha256']=storage.sha(c['contract']); c['complete']['entries_sha256']=storage.sha(c['entries'])
                    with self.assertRaises(ValueError): validate(c)
    def test_malformed_batch_no_effect(self):
        for p in ('responses','messages'):
            with tempfile.TemporaryDirectory() as d:
                s=TaskSession(Path(d)/'c',p,'full')
                r=response(p,1,dict(kind='refund',order_id='A100',amount_pence=4200))
                key='output' if p=='responses' else 'content'; r[key].append(dict(type='unsupported'))
                with self.assertRaises(ValueError): s.turn(lambda q:r)
                self.assertEqual(s.executor.view['after']['refunds'],[])
                with self.assertRaises(ValueError): s.turn(lambda q:response(p,2))
                s.executor.close()
    def test_task_storage_failure_after_commit(self):
        from unittest.mock import patch
        for p in ('responses','messages'):
            with tempfile.TemporaryDirectory() as d:
                s=TaskSession(Path(d)/'c',p,'full')
                original=s.store.finish
                def fail(entry,result):
                    if 'call_id' in result: raise OSError('post-commit capture failure')
                    return original(entry,result)
                with patch.object(s.store,'finish',side_effect=fail):
                    with self.assertRaises(OSError):
                        s.turn(lambda q:response(p,1,dict(kind='refund',order_id='A100',amount_pence=4200)))
                self.assertEqual(s.executor.view['after']['refunds'],[['A100',4200]])
                self.assertTrue(s.stopped); self.assertTrue(s.budget.held)
                with self.assertRaises(ValueError): s.turn(lambda q:response(p,2))
                self.assertFalse((Path(d)/'c/complete.json').exists())
                s.executor.close()

    def test_inherited_wrapper(self):
        for card in ('full','clarify','refuse'):
            self.assertEqual(lab.run_trial(lab.load_card(card))['status'],'PASS')

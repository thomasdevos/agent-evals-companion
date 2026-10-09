"""Finding-specific regressions, using actual SQLite execution and disk consumption."""
import copy
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import cassettes as c

class Corrections(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, cls.rows = c.run('messages')
        cls.card = c.strict_json((c.ROOT/'vendor/chapter02/cards/full.json').read_text())

    def consume(self, rows, manifest=None):
        m = copy.deepcopy(manifest or self.manifest)
        m.update(record_count=len(rows), records_sha256=c.digest(rows))
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'calls.jsonl'
            p.write_text(''.join(c.canonical(r)+'\n' for r in rows))
            return c.load(p,m)

    def test_missing_whole_groups(self):
        for pos in (0, len(self.manifest['schedule'])//2, -1):
            identity = self.manifest['schedule'][pos]
            rows = [r for r in self.rows if r['identity'] != identity]
            with self.subTest(pos=pos), self.assertRaises(c.ContractError):
                self.consume(rows)

    def test_exact_integer_identity(self):
        for value in (True, 1.0, 0, 6, '1'):
            rows = copy.deepcopy(self.rows)
            rows[0]['identity']['trial_index'] = value
            with self.subTest(value=repr(value)), self.assertRaises(c.ContractError):
                self.consume(rows)

    def test_transport_fresh_and_disk(self):
        for provider, adapter in c.ADAPTERS.items():
            m, rows = c.run(provider,'transport')
            self.assertEqual({t['status'] for t in m['trials']}, {'INFRA_ERROR'})
            self.assertEqual(m['summary']['scoring_eligible'],0)
            self.assertIsNone(m['summary']['scored_pass_rate'])
            self.assertEqual(m['summary']['status_counts']['INFRA_ERROR'],80)
            self.assertEqual(m['summary']['scheduled'],m['summary']['reported'])
            loaded = self.consume(rows,m)
            cases = {x['case_id']:x['card'] for x in c.load_rows(c.ROOT/'vendor/chapter03/repaired.jsonl')}
            for t in m['trials']:
                replay = c.Replay([r for r in loaded if r['identity']==t['identity']])
                agent = c.Agent(adapter(replay), t['identity'], [])
                result = c.run_trial(cases[t['identity']['case_id']], 'provider-neutral', agent)
                replay.finish()
                self.assertEqual(result['status'],'INFRA_ERROR')
                self.assertEqual(result['adapter_failure']['kind'],'transport_error')
                self.assertEqual(result['error'],t['error'])

    def test_malformed_denominators(self):
        m, _ = c.run('messages','malformed')
        self.assertEqual(m['summary']['status_counts']['PASS'],15)
        self.assertEqual(m['summary']['status_counts']['AGENT_ERROR'],65)
        self.assertEqual(m['summary']['scoring_eligible'],15)
        self.assertEqual(m['summary']['scored_pass_rate'],1.0)
        self.assertEqual(m['summary']['scheduled'],80)

    def envelope(self, provider, actions):
        if provider=='messages':
            return dict(model=c.MODEL,type='message',role='assistant',stop_reason='tool_use',content=[dict(type='tool_use',id=str(i),name=a['kind'],input={k:v for k,v in a.items() if k!='kind'}) for i,a in enumerate(actions)])
        return dict(model=c.MODEL,status='completed',output=[dict(type='function_call',call_id=str(i),name=a['kind'],arguments=c.canonical({k:v for k,v in a.items() if k!='kind'})) for i,a in enumerate(actions)])

    def test_actual_batch_zero_effects(self):
        bad = [dict(kind='refund',order_id='A100',amount_pence=v) for v in (-1,0,2**63,True)]
        bad += [dict(kind='ask',text='  '), dict(kind='refund',order_id='\ud800',amount_pence=1), dict(kind='read',text='\ud800')]
        for provider, adapter in c.ADAPTERS.items():
            for action in bad:
                with self.subTest(provider=provider,action=repr(action)):
                    envelope = self.envelope(provider,[dict(kind='refund',order_id='A100',amount_pence=4200),action])
                    records=[]
                    agent=c.Agent(adapter(lambda _: envelope),self.rows[0]['identity'],records)
                    result=c.run_trial(self.card,'regression',agent)
                    self.assertEqual(result['status'],'AGENT_ERROR')
                    self.assertEqual(result['after']['refunds'],[])
                    self.assertEqual(result['trace'],[])
                    self.assertEqual(records[0]['error'],'contract_error')

    def test_infra_precedence(self):
        import chapter02.task_lab as task
        original=task.snapshot
        calls=[]
        def snapshot(path):
            calls.append(path)
            if len(calls)>1: raise OSError('snapshot failed')
            return original(path)
        agent=c.Agent(c.Messages(c.Authored('messages','transport')),self.rows[0]['identity'],[])
        with patch.object(task,'snapshot',side_effect=snapshot):
            result=c.run_trial(self.card,'regression',agent)
        self.assertEqual(result['status'],'INFRA_ERROR')
        self.assertIn('snapshot failed',result['error'])

if __name__=='__main__': unittest.main()

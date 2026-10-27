import json
from pathlib import Path
import unittest
from chapter02.task_lab import load_card
from chapter03.dataset_lab import load_rows
from chapter05.harness import ProviderAgent, FixtureTransport, Fault, TransportError, execute, run
from chapter05.leakage import demonstration

DATA=Path(__file__).resolve().parents[1]/'chapter03/repaired.jsonl'
def view():
    c=load_card('full')
    return dict(request=c['request'],policy=c['policy'],orders=c['start']['orders'],trace=[])
def call(cid='a', name='read', arguments='{"text":"read"}'):
    return dict(type='function_call',call_id=cid,name=name,arguments=arguments)
def response(output): return dict(status='completed',output=output)

class Contracts(unittest.TestCase):
    def test_all_rows(self):
        r=run(DATA); self.assertEqual(r['counts'],{'PASS':16}); self.assertEqual(len(r['trials']),16)
    def test_isolated(self):
        r=run(DATA)
        self.assertTrue(all(t['before']['refunds']==[] for t in r['trials']))
    def test_leakage_red_green(self):
        self.assertTrue(demonstration(True)['misleading_final_state_pass'])
        self.assertFalse(demonstration(False)['misleading_final_state_pass'])
    def test_crash_complete(self):
        r=run(DATA,fault='crash'); self.assertEqual(r['counts'],{'AGENT_ERROR':1,'PASS':15})
        self.assertEqual(r['scheduled_trials'],r['reported_trials'])
    def test_unavailable_not_pass(self):
        r=run(DATA,fault='unavailable'); self.assertEqual(r['counts'],{'INFRA_ERROR':1,'PASS':15})
    def test_retry_accounting(self):
        a=execute(load_rows(DATA)[0],fault='transient')
        b=execute(load_rows(DATA)[0],fault='transient',retry=True)
        self.assertEqual(a['status'],'INFRA_ERROR'); self.assertEqual(b['status'],'PASS')
        self.assertEqual(a['ledger']['request_attempts'],1); self.assertEqual(b['ledger']['request_attempts'],3)
        self.assertIsNone(b['ledger']['model_cost'])
    def test_multiple_tools_and_submission(self):
        seen=[]
        def transport(payload,timeout):
            seen.append(payload)
            if len(seen)==1: return response([call('a'),call('b')])
            return response([dict(type='message',content=[dict(type='output_text',text=json.dumps(dict(status='refused',reason='not_owned',text='No')))])])
        a=ProviderAgent(transport); v=view()
        self.assertEqual(a(v)['kind'],'read'); self.assertEqual(a(v)['kind'],'read'); self.assertEqual(a(v)['kind'],'finish')
        self.assertEqual(a.tool_calls,2)
        self.assertEqual([x['call_id'] for x in seen[1]['input'] if x.get('type')=='function_call_output'],['a','b'])
        self.assertNotIn('required_outcome',json.dumps(seen))
    def test_malformed_contracts(self):
        for output in [[],[call(arguments='{')],[call(name='shell')],[call(arguments='[]')],
                       [call(),call()],[dict(type='message',content=[])],[call(arguments='{"text":2}')]]:
            with self.subTest(output=output):
                a=ProviderAgent(lambda p,t:response(output))
                with self.assertRaises(Fault): a(view())
                self.assertEqual(a.error['status'],'AGENT_ERROR')
    def test_request_limit(self):
        a=ProviderAgent(FixtureTransport(),requests=0)
        with self.assertRaises(Fault): a(view())
        self.assertEqual(a.requests,0)
    def test_deadline(self):
        a=ProviderAgent(FixtureTransport(),seconds=-1)
        with self.assertRaises(Fault): a(view())
        self.assertEqual(a.error['reason'],'local_deadline')
    def test_cancel(self):
        a=ProviderAgent(FixtureTransport()); a.cancelled=True
        with self.assertRaises(Fault): a(view())
        self.assertEqual(a.requests,0)
    def test_incomplete(self):
        a=ProviderAgent(lambda p,t:dict(status='incomplete',output=[]))
        with self.assertRaises(Fault): a(view())
        self.assertEqual(a.error['reason'],'provider_noncompleted')
    def test_retry_limit_counts_failure(self):
        def broken(p,t): raise TransportError()
        a=ProviderAgent(broken,retry=True)
        with self.assertRaises(Fault): a(view())
        self.assertEqual(a.requests,2); self.assertEqual(a.usage,[None,None])
    def test_script_no_model_cost(self):
        r=execute(load_rows(DATA)[0],mode='script')
        self.assertEqual(r['ledger']['model_cost'],0)
        self.assertEqual(r['ledger']['request_attempts'],0)

if __name__=='__main__': unittest.main()

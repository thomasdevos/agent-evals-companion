"""F1-F5 regressions: controlled transport only."""
import sqlite3
import unittest
from unittest.mock import patch
from chapter05 import harness as h
from chapter05.test_harness import DATA, call, response
from chapter02 import task_lab as lab

class Corrections(unittest.TestCase):
    def trial(self, envelope):
        a=h.ProviderAgent(lambda p,t: envelope)
        with patch.object(h,'ProviderAgent',return_value=a):
            return h.execute(h.load_rows(DATA)[0])

    def test_service_codes(self):
        for code in ('server_error','rate_limit_exceeded'):
            with self.subTest(code=code):
                r=self.trial(dict(status='failed',output=[],error=dict(code=code,message='secret')))
                self.assertEqual(r['status'],'INFRA_ERROR')
                self.assertEqual(r['adapter_error']['provider_code'],code)
                self.assertNotIn('secret',str(r))
                self.assertEqual(r['ledger']['request_attempts'],1)

    def test_combined_fault(self):
        real=lab.snapshot; n=0
        def snapshot(p):
            nonlocal n
            n+=1
            if n==2: raise sqlite3.OperationalError('final snapshot unavailable')
            return real(p)
        with patch.object(lab,'snapshot',side_effect=snapshot): r=self.trial(response([]))
        self.assertEqual(r['status'],'INFRA_ERROR')
        self.assertIn('snapshot unavailable',r['error'])
        self.assertEqual(r['adapter_error']['reason'],'malformed_provider_response')
        self.assertIsNone(r['after'])

    def test_malformed_companions(self):
        for companion in (dict(type='alien'),{},None):
            with self.subTest(companion=companion):
                r=self.trial(response([call(),companion]))
                self.assertEqual(r['ledger']['provider_tool_calls'],1)
                self.assertEqual(r['ledger']['executor_action_attempts'],0)
                self.assertEqual(r['after']['refunds'],[])
                self.assertEqual(r['status'],'AGENT_ERROR')

    def test_late_observation(self):
        clock=[0]
        def slow(p,t): clock[0]=31; return response([call()])
        with patch.object(h.time,'monotonic',side_effect=lambda:clock[0]):
            a=h.ProviderAgent(slow)
            with patch.object(h,'ProviderAgent',return_value=a): r=h.execute(h.load_rows(DATA)[0])
        self.assertEqual(r['ledger']['provider_tool_calls'],1)
        self.assertEqual(r['ledger']['executor_action_attempts'],0)

    def test_unknown_observation(self):
        r=self.trial(None)
        self.assertEqual(r['ledger']['provider_call_observation'],'partial_or_unknown')

    def test_diagnostic_budget(self):
        r=self.trial(response([call(str(i)) for i in range(8)]))
        self.assertEqual(r['ledger']['executor_action_attempts'],6)
        self.assertNotIn('executed_tool_calls',r['ledger'])
        self.assertEqual(len(r['checks']),6)
        self.assertFalse(r['scoring_eligible'])
        self.assertEqual(r['checks_role'],'diagnostic')
        self.assertEqual((r['passed'],r['failed'],r['errors']),(0,0,1))

    def test_status_policy(self):
        for status,expected in [('incomplete','AGENT_ERROR'),('cancelled','INFRA_ERROR'),('failed','INFRA_ERROR'),('mystery','INFRA_ERROR')]:
            with self.subTest(status=status):
                self.assertEqual(self.trial(dict(status=status,output=[]))['status'],expected)
        self.assertEqual(self.trial({})['status'],'AGENT_ERROR')

if __name__=='__main__': unittest.main()

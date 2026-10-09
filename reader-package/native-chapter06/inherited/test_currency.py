import copy
import json
import unittest
from unittest.mock import Mock, patch
import currency as m
import cassettes as c
from capture_store import MoneyBudget

class CurrencyTests(unittest.TestCase):
    def setUp(self):
        self.card = json.loads((c.ROOT/'vendor/chapter02/cards/full.json').read_text())
    def run_case(self, provider='messages', config=None, callback=None):
        return m.execute(self.card, provider, config or copy.deepcopy(m.CONFIG), callback)
    def test_both_providers_execute_and_import(self):
        for name in c.ADAPTERS:
            with self.subTest(provider=name):
                run = self.run_case(name)
                self.assertEqual(run['result']['status'], 'PASS')
                self.assertTrue(run['result']['after']['refunds'])
                self.assertTrue(all(r['model_cost'] is None and r['price_source'] is None for r in run['records']))
                c.validate_imported(run['records'])
                replay = c.Replay(run['records'])
                repeated = c.run_trial(self.card, 'currency-admitted', c.Agent(c.ADAPTERS[name](replay),run['records'][0]['identity'],[]))
                replay.finish()
                self.assertEqual(repeated, run['result'])
                report=run['budget_receipt']['accounting']
                self.assertEqual(report['reserved_minor'],0)
                self.assertEqual(report['known_cost_minor'],len(run['records']))
    def test_missing_invalid_denied_zero_effects(self):
        bad=[None,{},dict(m.CONFIG,ceiling=2),dict(m.CONFIG,attempts=True),
             dict(m.CONFIG,input_rate=1.5),dict(m.CONFIG,price_source='invoice'),
             dict(m.CONFIG,output_limit=0)]
        for config in bad:
            callback=Mock()
            with self.subTest(config=config), patch.object(c,'executor_run_trial') as executor, patch('sqlite3.connect') as db:
                with self.assertRaises(ValueError):m.execute(self.card,'messages',config,callback)
                callback.assert_not_called(); executor.assert_not_called(); db.assert_not_called()
    def test_reservation_visible_inside_actual_callback(self):
        budget=m.configured(m.CONFIG)
        first=budget.reserve()
        authored=c.Authored('messages')
        def callback(payload):
            self.assertEqual(budget.held,{1:3})
            return authored(payload)
        transport=m.AdmittedTransport(callback,budget,first)
        identity=dict(experiment_id='x',case_id='full',trial_id='full:1',trial_index=1,companion_version=c.VERSION,versions=c.versions())
        agent=m.AdmittedAgent(c.Messages(transport),identity,[],transport)
        # Use request cap so only the first callback runs; the first action is real.
        budget.cap=1
        result=c.run_trial(self.card,'currency-admitted',agent)
        self.assertEqual(authored.calls,1)
        self.assertEqual(transport.stop,'admission_denied')
        self.assertEqual(result['status'],'AGENT_ERROR')
    def test_unknown_invalid_excess_stop_before_action(self):
        usages=[None,{'input_tokens':True,'output_tokens':5},
                {'input_tokens':1001,'output_tokens':5},
                {'input_tokens':10,'output_tokens':513},
                {'input_tokens':-1,'output_tokens':5}, {'cached_tokens':1}]
        for provider in c.ADAPTERS:
            for usage in usages:
                authored=c.Authored(provider)
                def callback(payload):
                    response=authored(payload); response['usage']=usage; return response
                run=self.run_case(provider,callback=callback)
                self.assertEqual(authored.calls,1)
                self.assertEqual(run['result']['status'],'AGENT_ERROR')
                self.assertFalse(run['result']['after']['refunds'])
                r=run['budget_receipt']['accounting']
                self.assertEqual(r['reserved_minor'],3)
                self.assertIsNone(r['model_cost_minor'])
                self.assertTrue(r['blocked'])
                self.assertIsNotNone(run['budget_receipt']['stop'])
    def test_transport_failure_retains_exposure(self):
        run=self.run_case(callback=c.Authored('messages','transport'))
        self.assertEqual(run['result']['status'],'INFRA_ERROR')
        self.assertEqual(run['budget_receipt']['accounting']['reserved_minor'],3)
        self.assertEqual(run['budget_receipt']['stop'],'transport_error_unknown_exposure')
    def test_settled_and_outstanding_cap(self):
        b=MoneyBudget(ceiling=100,attempts=2)
        a=b.reserve(); b.settle(a,{'input_tokens':0,'output_tokens':0})
        b.reserve()
        with self.assertRaises(ValueError):b.reserve()
        self.assertEqual(len(b.held)+len(b.settled),2)
    def test_integrated_cap_and_ceiling(self):
        for config in (dict(m.CONFIG,attempts=1),dict(m.CONFIG,ceiling=3)):
            run=self.run_case(config=config)
            self.assertEqual(len(run['records']),1)
            self.assertEqual(run['budget_receipt']['stop'],'admission_denied')
            self.assertEqual(run['result']['status'],'AGENT_ERROR')
    def test_rounding_and_double_settlement(self):
        b=m.configured(m.CONFIG)
        self.assertEqual(b.price(10,5),1)
        self.assertEqual(b.price(1000,512),3)
        a=b.reserve();b.settle(a,{'input_tokens':10,'output_tokens':5})
        with self.assertRaises(ValueError):b.settle(a,None)
    def test_no_network(self):
        with patch('socket.socket',side_effect=AssertionError('network forbidden')):
            self.assertEqual(self.run_case()['result']['status'],'PASS')

if __name__=='__main__':unittest.main()

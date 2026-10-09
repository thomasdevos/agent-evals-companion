"""Finding-specific regression expectations; independent originals remain unchanged."""
import json
import unittest
from unittest.mock import patch
import currency as m
import cassettes as c

class CurrencyCorrections(unittest.TestCase):
    def setUp(self):
        self.card = json.loads((c.ROOT/'vendor/chapter02/cards/full.json').read_text())

    def test_config_snapshot_matches_enforcement(self):
        for provider in c.ADAPTERS:
            cfg = dict(m.CONFIG)
            authored = c.Authored(provider)
            def mutate(payload):
                cfg.update(ceiling=999, input_rate=999, price_source='invoice')
                return authored(payload)
            run = m.execute(self.card, provider, cfg, mutate)
            self.assertEqual(run['budget_receipt']['config'], m.CONFIG)
            self.assertEqual(run['budget_receipt']['accounting']['ceiling_minor'], 20)
            self.assertEqual(run['result']['status'], 'PASS')

    def test_callback_exceptions_return_truthful_receipt_and_replay(self):
        for provider in c.ADAPTERS:
            for exception in (OSError, ValueError, TypeError, RuntimeError, KeyError, AttributeError):
                with self.subTest(provider=provider, exception=exception):
                    fault = exception('correction callback fault')
                    calls = []
                    def throws(payload):
                        calls.append(payload)
                        raise fault
                    with patch.object(c, 'executor_run_trial', wraps=c.executor_run_trial) as executor:
                        run = m.execute(self.card, provider, dict(m.CONFIG), throws)
                    self.assertEqual(executor.call_count, 1)
                    self.assertEqual(len(calls), 1)
                    self.assertEqual(run['result']['status'], 'INFRA_ERROR')
                    self.assertFalse(run['result']['trace'])
                    self.assertFalse(run['result']['after']['refunds'])
                    receipt = run['budget_receipt']
                    self.assertEqual(receipt['stop'], 'transport_error_unknown_exposure')
                    self.assertEqual(receipt['accounting']['reserved_minor'], 3)
                    self.assertTrue(receipt['accounting']['blocked'])
                    self.assertIsNone(receipt['accounting']['model_cost_minor'])
                    self.assertEqual(receipt['events'][0]['callback_error'],
                                     dict(type=type(fault).__name__, module=type(fault).__module__, detail=str(fault)))
                    self.assertEqual(receipt['calls_sha256'], c.digest(run['records']))
                    row = run['records'][0]
                    self.assertIsNone(row['response'])
                    self.assertEqual(row['error'], 'transport_error')
                    c.validate_imported(run['records'])
                    replay = c.Replay(run['records'])
                    repeated = c.run_trial(self.card, 'currency-admitted', c.Agent(c.ADAPTERS[provider](replay), row['identity'], []))
                    replay.finish()
                    self.assertEqual(repeated, run['result'])

    def test_later_callback_exception_adds_no_action(self):
        authored = c.Authored('messages')
        calls = []
        def callback(payload):
            calls.append(payload)
            if len(calls) == 2:
                raise RuntimeError('later fault')
            return authored(payload)
        run = m.execute(self.card, 'messages', dict(m.CONFIG), callback)
        self.assertEqual(len(calls), 2)
        self.assertEqual(run['result']['status'], 'INFRA_ERROR')
        self.assertEqual(run['budget_receipt']['accounting']['reserved_minor'], 3)
        self.assertEqual(run['records'][-1]['error'], 'transport_error')

    def test_main_does_not_mislabel_post_execution_validation_error(self):
        with patch('sys.argv', ['currency.py']), patch.object(c, 'validate_imported', side_effect=c.ContractError('post_execution')):
            with self.assertRaisesRegex(c.ContractError, 'post_execution'):
                m.main()

if __name__ == '__main__':
    unittest.main()

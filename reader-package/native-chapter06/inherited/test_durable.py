import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import durable as d

class DurableTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.card = d.read(d.c.ROOT/'vendor/chapter02/cards/full.json')

    def run_case(self, provider='messages', callback=None, config=None):
        return d.execute(self.root/'capture', self.card, provider, config, callback)

    def fault(self, state, sequence=1):
        real = os.replace
        blocker = self.root/'occupied-directory'
        blocker.mkdir()
        def replace(source, target):
            value = d.read(source)
            if value.get('state') == state and value.get('sequence') == sequence:
                # Invoke the real syscall against a directory, not a mocked throw.
                return real(source, blocker)
            return real(source, target)
        return patch.object(d.storage.os, 'replace', side_effect=replace)

    def test_positive_export_import_and_policy_replay_both_providers(self):
        for provider in d.c.ADAPTERS:
            with self.subTest(provider=provider):
                root = self.root/provider
                callback = d.c.Authored(provider)
                run = d.execute(root, self.card, provider, callback=callback)
                self.assertEqual(run['result']['status'], 'PASS')
                self.assertTrue(run['result']['after']['refunds'])
                self.assertGreater(callback.calls, 1)
                exported = self.root/(provider+'-export')
                self.assertEqual(d.export(root, exported), callback.calls)
                replay = d.replay(exported)
                self.assertEqual(run['result'], replay['result'])
                _, complete, rows = d.load(root)
                self.assertEqual(rows, run['records'])
                self.assertEqual(complete['accounting']['reserved_minor'], 0)
                self.assertEqual(complete['accounting']['known_cost_minor'], callback.calls)

    def test_intent_is_on_disk_inside_callback(self):
        authored = d.c.Authored('messages')
        def callback(payload):
            files = sorted((self.root/'capture').glob('[0-9]*.json'))
            entry = d.read(files[-1])
            self.assertEqual(entry['state'], 'intent')
            self.assertEqual(entry['request']['payload'], payload)
            self.assertEqual(entry['request']['accounting']['reserved_minor'], 3)
            self.assertEqual(entry['request']['config'], d.money.CONFIG)
            return authored(payload)
        self.assertEqual(self.run_case(callback=callback)['result']['status'], 'PASS')

    def test_actual_pre_callback_storage_failure_zero_actions(self):
        callback = d.c.Authored('messages')
        with self.fault('intent'):
            run = self.run_case(callback=callback)
        self.assertEqual(callback.calls, 0)
        self.assertEqual(run['result']['trace'], [])
        self.assertEqual(run['result']['before'], run['result']['after'])
        self.assertEqual(run['result']['status'], 'INFRA_ERROR')
        self.assertEqual(run['accounting']['reserved_minor'], 3)
        self.assertIsNotNone(run['storage_error'])
        self.assertFalse((self.root/'capture/complete.json').exists())
        with self.assertRaises(OSError): d.export(self.root/'capture',self.root/'export')
        self.assertFalse((self.root/'export').exists())

    def test_post_response_failure_retains_intent_and_reservation(self):
        callback = d.c.Authored('messages')
        with self.fault('terminal'):
            run = self.run_case(callback=callback)
        self.assertEqual(callback.calls, 1)
        self.assertEqual(run['result']['trace'], [])
        self.assertEqual(run['result']['before'], run['result']['after'])
        self.assertEqual(run['accounting']['reserved_minor'], 3)
        self.assertEqual(run['accounting']['known_cost_minor'], 0)
        self.assertIsNone(run['accounting']['model_cost_minor'])
        self.assertTrue(run['accounting']['blocked'])
        self.assertEqual(d.read(self.root/'capture/000001.json')['state'], 'intent')
        self.assertIsNotNone(run['records'][0]['response'])
        self.assertFalse((self.root/'capture/complete.json').exists())
        self.assertEqual(run['result']['status'], 'INFRA_ERROR')

    def test_later_terminal_failure_keeps_prior_settlement(self):
        callback = d.c.Authored('responses')
        with self.fault('terminal', 2):
            run = self.run_case('responses', callback)
        self.assertEqual(callback.calls, 2)
        self.assertEqual(run['accounting']['known_cost_minor'], 1)
        self.assertEqual(run['accounting']['reserved_minor'], 3)
        self.assertEqual(len(run['result']['trace']), 1)
        # The first call is the refund; a later storage fault cannot undo it.
        self.assertEqual(run['result']['after']['refunds'], [['A100', 4200]])
        self.assertEqual(d.read(self.root/'capture/000001.json')['state'], 'terminal')
        self.assertEqual(d.read(self.root/'capture/000002.json')['state'], 'intent')

    def test_unknown_usage_policy_replay_stops_before_action(self):
        callback = d.c.Authored('messages', 'unknown')
        run = self.run_case(callback=callback)
        self.assertEqual(callback.calls, 1)
        self.assertEqual(run['result']['trace'], [])
        self.assertEqual(run['accounting']['reserved_minor'], 3)
        d.export(self.root/'capture', self.root/'export')
        replay = d.replay(self.root/'export')
        self.assertEqual(replay['result'], run['result'])

    def test_callback_exception_export_and_policy_replay(self):
        def callback(payload): raise RuntimeError('authored callback fault')
        run = self.run_case(callback=callback)
        self.assertEqual(run['result']['status'], 'INFRA_ERROR')
        self.assertEqual(run['accounting']['reserved_minor'], 3)
        d.export(self.root/'capture', self.root/'export')
        self.assertEqual(d.replay(self.root/'export')['result'], run['result'])

    def test_denied_configuration_precedes_executor_and_directory(self):
        with patch.object(d.c,'run_trial') as executor:
            with self.assertRaises(ValueError):
                self.run_case(config=dict(d.money.CONFIG,ceiling=2))
            executor.assert_not_called()
        self.assertFalse((self.root/'capture').exists())

    def test_later_admission_denial_exports_without_fake_call(self):
        run = self.run_case(config=dict(d.money.CONFIG,attempts=1))
        self.assertEqual(len(run['records']), 1)
        self.assertEqual(run['stop'], 'admission_denied')
        d.export(self.root/'capture', self.root/'export')
        self.assertEqual(d.replay(self.root/'export')['result'], run['result'])

    def test_existing_capture_and_export_refuse_overwrite(self):
        self.run_case()
        before = (self.root/'capture/complete.json').read_bytes()
        with self.assertRaises(FileExistsError): self.run_case()
        self.assertEqual(before, (self.root/'capture/complete.json').read_bytes())
        d.export(self.root/'capture', self.root/'export')
        with self.assertRaises(FileExistsError): d.export(self.root/'capture', self.root/'export')

    def test_resealed_projection_and_intent_mutation_rejected(self):
        self.run_case()
        path = self.root/'capture/000001.json'
        original = path.read_bytes()
        value = d.read(path)
        value['request']['accounting']['reserved_minor'] = 0
        value['request_sha256'] = d.c.digest(value['request'])
        d.storage.atomic_json(path, value)
        with self.assertRaises(ValueError): d.load(self.root/'capture')
        path.write_bytes(original)
        value = d.read(path)
        value['result']['call']['usage']['input_tokens'] = 999
        d.storage.atomic_json(path,value)
        with self.assertRaises(ValueError): d.load(self.root/'capture')

    def test_interrupted_process_retains_intent_refuses_export_and_resume(self):
        code = "import os,durable as d;from pathlib import Path;card=d.read(d.c.ROOT/'vendor/chapter02/cards/full.json');d.execute(Path(os.environ['CRASH_CAPTURE']),card,callback=lambda payload:os._exit(73))"
        argv = [sys.executable] + (['-O'] if sys.flags.optimize else []) + ['-c', code]
        env = dict(os.environ, CRASH_CAPTURE=str(self.root/'capture'))
        child = subprocess.run(argv,cwd=d.c.ROOT,env=env,text=True,capture_output=True)
        print(json.dumps(dict(interruption=dict(argv=argv,cwd=str(d.c.ROOT),exit=child.returncode,stdout=child.stdout,stderr=child.stderr))))
        self.assertEqual(child.returncode,73)
        intent = d.read(self.root/'capture/000001.json')
        self.assertEqual(intent['state'],'intent')
        self.assertEqual(intent['request']['accounting']['reserved_minor'],3)
        with self.assertRaises(OSError):d.export(self.root/'capture',self.root/'export')
        with self.assertRaises(FileExistsError):self.run_case()

    def test_storage_latch_blocks_reentry_even_with_queued_actions(self):
        callback = d.c.Authored('messages')
        agents = []
        original = d.DurableAgent
        def factory(*args):
            agent = original(*args)
            agents.append(agent)
            return agent
        with patch.object(d, 'DurableAgent', side_effect=factory), self.fault('terminal'):
            run = self.run_case(callback=callback)
        self.assertEqual(callback.calls, 1)
        agents[0].queue.append(dict(kind='refund',order_id='A100',amount_pence=4200))
        with self.assertRaises(d.StorageFault): agents[0]({})
        with self.assertRaises(d.StorageFault): agents[0].admission({})
        self.assertEqual(callback.calls, 1)
        self.assertEqual(run['result']['trace'], [])

    def test_original_callback_error_is_retained_on_disk_and_export(self):
        def callback(payload): raise RuntimeError('offline diagnostic')
        self.run_case(callback=callback)
        event = d.read(self.root/'capture/000001.json')['result']['event']
        self.assertEqual(event['callback_error']['type'], 'RuntimeError')
        self.assertEqual(event['callback_error']['detail'], 'offline diagnostic')
        d.export(self.root/'capture',self.root/'export')
        self.assertEqual(d.read(self.root/'export/policy.json')['complete']['events'][0], event)

    def test_no_network(self):
        with patch('socket.socket',side_effect=AssertionError('network forbidden')):
            self.assertEqual(self.run_case()['result']['status'],'PASS')

if __name__ == '__main__': unittest.main()

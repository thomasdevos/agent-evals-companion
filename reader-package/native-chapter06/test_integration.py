import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from copy import deepcopy
import integration as i
from demo import envelope
from native import SQLiteExecutor, snapshot


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def session(self, provider, **kw):
        root = self.root / provider
        root.mkdir()
        executor = SQLiteExecutor(root/'fixture.sqlite')
        return i.Session(root/'capture', provider, executor, **kw)

    def finish(self, session):
        first = session.turn(lambda request: envelope(session.provider))
        second = session.turn(lambda request: envelope(session.provider, True))
        session.finish()
        return first, second

    def test_both_shapes_actual_results_export_replay(self):
        for provider in ('responses','messages'):
            with self.subTest(provider=provider):
                s = self.session(provider)
                first, second = self.finish(s)
                self.assertEqual(s.executor.calls, 2)
                self.assertEqual(snapshot(s.executor.path)['refunds'], [['A100',4200]])
                bundle = i.load(s.store.directory)
                self.assertEqual(len(bundle['entries']), 6)
                self.assertEqual(bundle['entries'][1]['result'], first['results'][0])
                self.assertEqual(bundle['entries'][4]['request']['payload'], second['request'])
                if provider == 'responses':
                    result = second['request']['input'][-2]
                    self.assertEqual(result['call_id'], 'call-1')
                    self.assertEqual(json.loads(result['output'])['result'], first['results'][0]['output'])
                else:
                    result = second['request']['messages'][-1]['content'][0]
                    self.assertEqual(result['tool_use_id'], 'call-1')
                    self.assertEqual(result['content'], first['results'][0]['output'])
                dest = self.root/provider/'export'
                self.assertEqual(i.export(s.store.directory,dest), 6)
                self.assertEqual(i.replay(dest)['turns'], 2)
                self.assertIsNone(s.budget.report()['model_cost_minor'])
                self.assertEqual(s.budget.report()['hypothetical_total_minor'], 2)

    def test_faults_before_and_after_effects_latch_and_keep_exposure(self):
        # phase, occurrence, expected executed calls; each path gets a fresh session.
        faults = [('intent',1,0),('finish',1,0),('intent',2,0),
                  ('finish',2,1),('intent',3,1),('finish',3,2),
                  ('intent',4,2),('finish',4,2)]
        for provider in ('responses','messages'):
            for phase, at, calls in faults:
                with self.subTest(provider=provider,phase=phase,at=at):
                    with tempfile.TemporaryDirectory(dir=self.root) as d:
                        ex = SQLiteExecutor(Path(d)/'db')
                        s = i.Session(Path(d)/'capture',provider,ex)
                        real = getattr(s.store,phase)
                        count = [0]
                        def fail(*args):
                            count[0] += 1
                            if count[0] == at:
                                raise OSError('injected storage fault')
                            return real(*args)
                        callbacks = []
                        def callback(request):
                            callbacks.append(request)
                            return envelope(provider)
                        with patch.object(s.store,phase,side_effect=fail):
                            with self.assertRaises(OSError):
                                s.turn(callback)
                        self.assertEqual(ex.calls,calls)
                        self.assertEqual(snapshot(ex.path)['refunds'], [['A100',4200]] if calls else [])
                        self.assertEqual(s.budget.report()['reserved_minor'],8)
                        self.assertIsNone(s.budget.report()['hypothetical_total_minor'])
                        self.assertTrue(s.budget.blocked)
                        n = len(callbacks)
                        with self.assertRaises(ValueError):
                            s.turn(callback)
                        self.assertEqual(len(callbacks),n)
                        self.assertEqual(ex.calls,calls)
                        with self.assertRaises((ValueError,OSError)):
                            i.export(s.store.directory,Path(d)/'export')
                        self.assertFalse((Path(d)/'export').exists())

    def test_after_write_fault_still_stops(self):
        for provider in ('responses','messages'):
            s = self.session(provider)
            real = s.store.finish
            def fail(entry,result):
                real(entry,result)
                if entry['request']['kind'] == 'effect':
                    raise OSError('directory flush uncertain')
            with patch.object(s.store,'finish',side_effect=fail):
                with self.assertRaises(OSError):
                    s.turn(lambda request: envelope(provider))
            self.assertEqual(s.executor.calls,1)
            self.assertEqual(i.entries(s.store.directory)[1]['state'],'terminal')
            self.assertTrue(s.stopped)
            self.assertEqual(s.budget.report()['reserved_minor'],8)

    def test_evidence_exists_at_dispatch_and_continuation(self):
        for provider in ('responses','messages'):
            s = self.session(provider)
            real = s.executor
            def checked(call):
                rows = i.entries(s.store.directory)
                self.assertEqual(rows[0]['state'],'terminal')
                self.assertEqual(rows[-1]['state'],'intent')
                self.assertEqual(rows[-1]['request']['action'],call)
                return real(call)
            s.executor = checked
            s.turn(lambda request: envelope(provider))
            def next_reply(request):
                rows = i.entries(s.store.directory)
                self.assertEqual(rows[-2]['request']['kind'],'barrier')
                self.assertEqual(rows[-2]['state'],'terminal')
                self.assertEqual(len(rows[-2]['result']['results']),2)
                return envelope(provider,True)
            s.turn(next_reply)
            s.finish()

    def test_unknown_usage_and_malformed_batch_prevent_all_effects(self):
        for provider in ('responses','messages'):
            for variant in ('null','extra','excess','boolean','identity'):
                with self.subTest(provider=provider,variant=variant):
                    with tempfile.TemporaryDirectory(dir=self.root) as d:
                        s = i.Session(Path(d)/'capture',provider,SQLiteExecutor(Path(d)/'db'))
                        response = envelope(provider)
                        if variant == 'null': response['usage'] = None
                        if variant == 'extra': response['usage']['unknown'] = 0
                        if variant == 'excess':
                            response['usage']['output_tokens'] = 1001
                            if provider == 'responses': response['usage']['total_tokens'] = 1011
                        if variant == 'boolean': response['usage']['input_tokens'] = True
                        if variant == 'identity':
                            if provider == 'responses': response['output'][-1]['call_id'] = 'call-1'
                            else: response['content'][-1]['id'] = 'call-1'
                        with self.assertRaises(ValueError): s.turn(lambda request: response)
                        self.assertEqual(s.executor.calls,0)
                        self.assertEqual(s.budget.report()['reserved_minor'],8)
                        with self.assertRaises(ValueError): s.turn(lambda request: envelope(provider))

    def test_category_arithmetic_and_uncertain_splits(self):
        b = i.CategoryBudget()
        # Numerators chosen to cross a rounding boundary when categories are wrong.
        r = dict(input_tokens=1000,output_tokens=250,total_tokens=1250,
                 input_tokens_details=dict(cached_tokens=500),output_tokens_details=dict(reasoning_tokens=200))
        self.assertEqual(b.cost('responses',r),3)
        m = dict(input_tokens=100,cache_creation_input_tokens=300,cache_read_input_tokens=500,
                 output_tokens=250,cache_creation=dict(ephemeral_5m_input_tokens=100,ephemeral_1h_input_tokens=200),
                 output_tokens_details=dict(thinking_tokens=200))
        self.assertEqual(b.cost('messages',m),3)
        del m['cache_creation']
        with self.assertRaises(ValueError): b.cost('messages',m)
        r['input_tokens_details']['cache_write_tokens'] = 1
        with self.assertRaises(ValueError): b.cost('responses',r)
        del r['input_tokens_details']
        with self.assertRaises(ValueError): b.cost('responses',r)

    def test_admission_denied_before_callback(self):
        for provider in ('responses','messages'):
            s = self.session(provider,ceiling=8)
            s.turn(lambda request: envelope(provider))
            calls = []
            with self.assertRaises(ValueError): s.turn(lambda request: calls.append(request))
            self.assertEqual(calls,[])
            self.assertEqual(s.executor.calls,2)
            self.assertTrue(s.stopped)

    def test_tampered_identity_result_and_accounting_rejected_even_resealed(self):
        s = self.session('messages'); self.finish(s)
        original = i.load(s.store.directory)
        for variant in ('call_id','output','boolean','request','short'):
            with self.subTest(variant=variant):
                b = deepcopy(original)
                rows = b['entries']
                if variant == 'call_id': rows[1]['result']['call_id'] = 'foreign'
                if variant == 'output': rows[1]['result']['output'] = '{}'
                if variant == 'boolean': rows[3]['result']['accounting']['known_cost_minor'] = True
                if variant == 'request':
                    rows[4]['request']['payload']['messages'][-1]['content'][0]['content'] = 'invented'
                    rows[4]['request_sha256'] = i.storage.sha(rows[4]['request'])
                if variant == 'short': rows.pop()
                b['complete']['entries_sha256'] = i.storage.sha(rows)
                with self.assertRaises(ValueError): i.validate(b['contract'],b['complete'],rows)

    def test_second_turn_storage_fault_preserves_prior_results(self):
        for provider in ('responses','messages'):
            s = self.session(provider)
            s.turn(lambda request: envelope(provider))
            prior = [p.read_bytes() for p in sorted(s.store.directory.glob('[0-9]*.json'))]
            calls = []
            real = s.store.finish
            def fail(entry,result):
                if entry['request']['kind'] == 'request':
                    raise OSError('second response capture fails')
                return real(entry,result)
            def callback(request):
                calls.append(request)
                rows = i.entries(s.store.directory)
                self.assertEqual(rows[-1]['state'],'intent')
                self.assertEqual(rows[-1]['request']['payload'],request)
                return envelope(provider,True)
            with patch.object(s.store,'finish',side_effect=fail):
                with self.assertRaises(OSError): s.turn(callback)
            self.assertEqual(len(calls),1)
            self.assertEqual(s.executor.calls,2)
            self.assertEqual(snapshot(s.executor.path)['refunds'],[['A100',4200]])
            self.assertEqual(s.budget.report()['known_cost_minor'],1)
            self.assertEqual(s.budget.report()['reserved_minor'],8)
            self.assertIsNone(s.budget.report()['hypothetical_total_minor'])
            self.assertEqual(prior,[p.read_bytes() for p in sorted(s.store.directory.glob('[0-9]*.json'))][:4])
            with self.assertRaises(ValueError): s.turn(callback)
            self.assertEqual(len(calls),1)

    def test_executor_failure_after_commit_keeps_intent_and_blocks(self):
        for provider in ('responses','messages'):
            s = self.session(provider)
            real = s.executor
            def failed(call):
                real(call)
                raise RuntimeError('executor lost result after commit')
            s.executor = failed
            with self.assertRaises(RuntimeError): s.turn(lambda request: envelope(provider))
            self.assertEqual(real.calls,1)
            self.assertEqual(snapshot(real.path)['refunds'],[['A100',4200]])
            self.assertEqual(i.entries(s.store.directory)[-1]['state'],'intent')
            self.assertEqual(s.budget.report()['reserved_minor'],8)
            with self.assertRaises(ValueError): s.turn(lambda request: envelope(provider))
            self.assertEqual(real.calls,1)

    def test_completion_write_fault_blocks_export(self):
        s = self.session('responses')
        s.turn(lambda request: envelope('responses'))
        s.turn(lambda request: envelope('responses',True))
        with patch.object(i.storage,'atomic_json',side_effect=OSError('completion failure')):
            with self.assertRaises(OSError): s.finish()
        self.assertTrue(s.stopped)
        with self.assertRaises(OSError): i.export(s.store.directory,self.root/'export')
        self.assertFalse((self.root/'export').exists())


if __name__ == '__main__':
    unittest.main()

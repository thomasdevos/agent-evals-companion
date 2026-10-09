from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock
from native import Conversation, SQLiteExecutor, ContractError, usage, canonical
from demo import envelope, run


class NativeTests(unittest.TestCase):
    def test_depth_failure_latches_admission_and_dispatch(self):
        for provider in ('responses', 'messages'):
            with self.subTest(provider=provider), tempfile.TemporaryDirectory() as d:
                c = Conversation(provider, 'depth regression'); c.request()
                r = envelope(provider)
                if provider == 'responses':
                    r['output'][-1]['arguments'] = '[' * 2000 + '0' + ']' * 2000
                else:
                    nested = 0
                    for _ in range(2000):
                        nested = [nested]
                    r['content'][-1]['input'] = nested
                executor = SQLiteExecutor(Path(d) / 'db')
                with self.assertRaises(ContractError): c.accept(r)
                self.assertEqual(c.usage_records(), [])
                with self.assertRaises(ContractError): c.accept(envelope(provider))
                with self.assertRaises(ContractError): c.request()
                with self.assertRaises(ContractError): c.complete([])
                with self.assertRaises(ContractError): c.execute(executor)
                self.assertEqual(executor.calls, 0)
                with sqlite3.connect(executor.path) as db:
                    self.assertEqual(db.execute('SELECT count(*) FROM refunds').fetchone()[0], 0)

    def pending(self, p):
        c = Conversation(p, 'Synthetic task')
        c.request(); c.accept(envelope(p))
        return c

    def results(self):
        return [dict(call_id='call-'+str(i), is_error=False, output='actual result') for i in (1, 2)]

    def test_actual_sqlite_results_in_next_requests(self):
        for p in ('responses', 'messages'):
            with self.subTest(provider=p):
                report = run(p)
                self.assertEqual(report['executor_calls'], 2)
                second = report['requests'][1]
                if p == 'responses':
                    items = second['input']
                    self.assertEqual(items[1:4], envelope(p)['output'])
                    self.assertEqual([x['call_id'] for x in items[-2:]], ['call-1', 'call-2'])
                    outputs = [json.loads(x['output'])['result'] for x in items[-2:]]
                else:
                    messages = second['messages']
                    self.assertEqual(messages[-2], dict(role='assistant', content=envelope(p)['content']))
                    self.assertEqual(messages[-1]['role'], 'user')
                    self.assertEqual([x['tool_use_id'] for x in messages[-1]['content']], ['call-1', 'call-2'])
                    outputs = [x['content'] for x in messages[-1]['content']]
                self.assertEqual(outputs, [x['output'] for x in report['results']])
                self.assertEqual(json.loads(outputs[0])['refunds'], [['A100', 4200]])

    def test_whole_batch_invalid_before_dispatch(self):
        for p in ('responses', 'messages'):
            base = envelope(p)
            mutations = []
            for value in (True, 4200.0, '4200', None, -1):
                r = deepcopy(base)
                if p == 'messages':
                    r['content'][1]['input']['amount_pence'] = value
                else:
                    r['output'][1]['arguments'] = canonical(dict(order_id='A100', amount_pence=value))
                mutations.append(r)
            r = deepcopy(base)
            if p == 'messages': r['content'][-1]['id'] = 'call-1'
            else: r['output'][-1]['call_id'] = 'call-1'
            mutations.append(r)
            for value in ([], None, True, 1, 'envelope'):
                mutations.append(value)
            for field in ('id', 'model', 'usage'):
                r = deepcopy(base); r[field] = None; mutations.append(r)
            r = deepcopy(base)
            r['stop_reason' if p == 'messages' else 'status'] = 'max_tokens'
            mutations.append(r)
            r = deepcopy(base)
            r['content' if p == 'messages' else 'output'][-1] = dict(type='server_tool_use')
            mutations.append(r)
            r = deepcopy(base); r['usage']['new_charge'] = 0; mutations.append(r)
            for index, r in enumerate(mutations):
                with self.subTest(provider=p, mutation=index):
                    c = Conversation(p, 'task'); c.request(); spy = Mock()
                    with self.assertRaises(ContractError): c.accept(r)
                    with self.assertRaises(ContractError): c.execute(spy)
                    with self.assertRaises(ContractError): c.request()
                    spy.assert_not_called()

    def test_result_batch_rejects_before_next_request_or_effect(self):
        variants = [[], self.results()[:1], self.results()+self.results()[:1]]
        for key, value in [('call_id', 'wrong'), ('call_id', True), ('is_error', 0), ('output', {}), ('output', '')]:
            r = self.results(); r[-1][key] = value; variants.append(r)
        for p in ('responses', 'messages'):
            for results in variants:
                with self.subTest(provider=p, results=results):
                    c = self.pending(p); spy = Mock()
                    with self.assertRaises(ContractError): c.complete(results)
                    with self.assertRaises(ContractError): c.request()
                    with self.assertRaises(ContractError): c.execute(spy)
                    spy.assert_not_called()

    def test_reorders_valid_results_to_original_call_order(self):
        for p in ('responses', 'messages'):
            c = self.pending(p); c.complete(list(reversed(self.results())))
            request = c.request()
            blocks = request['input'][-2:] if p == 'responses' else request['messages'][-1]['content']
            key = 'call_id' if p == 'responses' else 'tool_use_id'
            self.assertEqual([x[key] for x in blocks], ['call-1', 'call-2'])

    def test_pending_and_terminal_barriers(self):
        for p in ('responses', 'messages'):
            c = self.pending(p)
            with self.assertRaises(ContractError): c.request()
            c.complete(self.results()); c.request(); c.accept(envelope(p, True))
            with self.assertRaises(ContractError): c.request()
            with self.assertRaises(ContractError): c.complete(self.results())

    def test_trial_wide_duplicate_ids(self):
        for p in ('responses', 'messages'):
            c = self.pending(p); c.complete(self.results()); c.request()
            r = envelope(p); r['id'] = 'fresh-response'
            with self.assertRaises(ContractError): c.accept(r)

    def test_duplicate_response_id(self):
        for p in ('responses', 'messages'):
            c = self.pending(p); c.complete(self.results()); c.request()
            r = envelope(p, True); r['id'] = envelope(p)['id']
            with self.assertRaises(ContractError): c.accept(r)

    def test_detached_mutable_inputs_and_outputs(self):
        for p in ('responses', 'messages'):
            c = Conversation(p, 'task'); first = c.request(); first.clear()
            r = envelope(p); expected = deepcopy(r); returned = c.accept(r)
            r.clear(); returned.clear()
            results = self.results(); c.complete(results); results.clear()
            history = c.request()['input' if p == 'responses' else 'messages']
            self.assertTrue(history)
            u = c.usage_records(); u[0]['raw'].clear()
            self.assertEqual(c.usage_records()[0]['raw'], expected['usage'])

    def test_executor_exception_and_malformed_output_latch(self):
        for failure in (RuntimeError('uncertain commit'), {'is_error': 0, 'output': 'bad'}, None):
            for p in ('responses', 'messages'):
                c = self.pending(p)
                spy = Mock(side_effect=failure) if isinstance(failure, Exception) else Mock(return_value=failure)
                with self.assertRaises((RuntimeError, ContractError)): c.execute(spy)
                self.assertEqual(spy.call_count, 1)
                with self.assertRaises(ContractError): c.execute(spy)
                with self.assertRaises(ContractError): c.request()

    def test_actual_tool_failure_is_bound(self):
        for p in ('responses', 'messages'):
            with tempfile.TemporaryDirectory() as d:
                e = SQLiteExecutor(Path(d)/'db')
                with sqlite3.connect(e.path) as db:
                    db.execute('INSERT INTO refunds(order_id, amount_pence) VALUES (?,?)', ('A100', 1))
                c = self.pending(p); results = c.execute(e)
                self.assertTrue(results[0]['is_error'])
                self.assertFalse(results[1]['is_error'])
                second = c.request()
                self.assertIn('Existing refund conflicts', canonical(second))
                self.assertEqual(json.loads(results[1]['output'])['refunds'], [['A100', 1]])

    def test_usage_categories_without_double_count(self):
        r = usage('responses', envelope('responses')['usage'])
        m = usage('messages', envelope('messages')['usage'])
        self.assertEqual(r['total_tokens'], 15)
        self.assertEqual(m['total_tokens'], 22)
        self.assertEqual(r['categories']['reasoning_tokens'], 2)
        self.assertEqual(m['categories']['thinking_tokens'], 2)
        self.assertIsNone(r['model_cost']); self.assertIsNone(m['tariff'])

    def test_invalid_usage_exact_types_and_unknowns(self):
        for p in ('responses', 'messages'):
            raw = envelope(p)['usage']
            variants = [None, [], True]
            for key in ('input_tokens', 'output_tokens'):
                for value in (True, 1.0, '1', -1, None):
                    r = deepcopy(raw); r[key] = value; variants.append(r)
            for key in ('unexpected',):
                r = deepcopy(raw); r[key] = 0; variants.append(r)
            r = deepcopy(raw); r['output_tokens_details'] = {'reasoning_tokens' if p == 'responses' else 'thinking_tokens': 6}; variants.append(r)
            r = deepcopy(raw); r['output_tokens_details'] = None; variants.append(r)
            r = deepcopy(raw)
            if p == 'responses': r['total_tokens'] = 17
            else: r['cache_creation']['ephemeral_1h_input_tokens'] = 99
            variants.append(r)
            for r in variants:
                with self.subTest(provider=p, usage=r):
                    with self.assertRaises(ContractError): usage(p, r)

    def test_duplicate_json_keys_and_unsupported_reasoning(self):
        c = Conversation('responses', 'task'); c.request(); r = envelope('responses')
        r['output'][1]['arguments'] = '{"order_id":"A100","amount_pence":4200,"amount_pence":4200}'
        with self.assertRaises(ContractError): c.accept(r)
        c = Conversation('messages', 'task'); c.request(); r = envelope('messages')
        r['content'].insert(0, dict(type='thinking', thinking='unsupported'))
        with self.assertRaises(ContractError): c.accept(r)

    def test_unsupported_authority_and_invalid_later_call(self):
        for p in ('responses', 'messages'):
            r = envelope(p)
            item = r['output'][-1] if p == 'responses' else r['content'][-1]
            item['name'] = 'refund'
            item['arguments' if p == 'responses' else 'input'] = canonical(dict(order_id='B200', amount_pence=1900)) if p == 'responses' else dict(order_id='B200', amount_pence=1900)
            c = Conversation(p, 'task'); c.request(); spy = Mock()
            with self.assertRaises(ContractError): c.accept(r)
            with self.assertRaises(ContractError): c.execute(spy)
            spy.assert_not_called()


if __name__ == '__main__':
    unittest.main()

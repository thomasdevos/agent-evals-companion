"""D-I-01/02: authored synthetic receipts; hypothetical GBP prices only."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import durable as d


class DurableCorrectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.capture = self.root/'capture'
        card = d.read(d.c.ROOT/'vendor/chapter02/cards/full.json')
        d.execute(self.capture, card)
        self.entry_path = self.capture/'000001.json'
        self.complete_path = self.capture/'complete.json'
        self.entry = d.read(self.entry_path)
        self.complete = d.read(self.complete_path)

    def refusal(self, entry, complete, category):
        d.storage.atomic_json(self.entry_path, entry)
        d.storage.atomic_json(self.complete_path, complete)
        # Separate subtests exercise every interface even when another is red.
        with self.subTest(interface='load'):
            with self.assertRaisesRegex(d.c.ContractError, '^'+category+'$'):
                d.load(self.capture)
        with tempfile.TemporaryDirectory(dir=self.root) as temp:
            output = Path(temp)/'export'
            with self.subTest(interface='export'):
                with self.assertRaisesRegex(d.c.ContractError, '^'+category+'$'):
                    d.export(self.capture, output)
                self.assertFalse(output.exists())
        with tempfile.TemporaryDirectory(dir=self.root) as temp:
            output = Path(temp)/'export'
            argv = [sys.executable] + (['-O'] if sys.flags.optimize else [])
            argv += ['durable.py', 'export', str(self.capture), '--output', str(output)]
            child = subprocess.run(argv, cwd=d.c.ROOT, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
                                   text=True, capture_output=True, timeout=15)
            with self.subTest(interface='CLI'):
                self.assertEqual(child.returncode, 2, child.stderr)
                self.assertEqual(child.stderr, '')
                self.assertEqual(json.loads(child.stdout), dict(refused='ContractError', detail=category))
                self.assertFalse(output.exists())

    def test_accounting_exact_json_types(self):
        for target in ('terminal', 'completion'):
            original = self.entry['result']['accounting'] if target == 'terminal' else self.complete['accounting']
            for field, value in original.items():
                # Equal-valued JSON replacements must not bypass exact schema types.
                alternatives = ([float(value)] + ([bool(value)] if value in (0, 1) else [])) if type(value) is int else ([int(value), float(value)] if type(value) is bool else [])
                for replacement in alternatives:
                    with self.subTest(target=target, field=field, replacement=repr(replacement)):
                        entry, complete = copy.deepcopy(self.entry), copy.deepcopy(self.complete)
                        accounting = entry['result']['accounting'] if target == 'terminal' else complete['accounting']
                        accounting[field] = replacement
                        self.refusal(entry, complete, 'terminal_accounting' if target == 'terminal' else 'completion_binding')

    def test_event_exact_json_numeric_types(self):
        for field in ('attempt', 'reserved_before_callback'):
            value = self.entry['result']['event'][field]
            for replacement in (True, False, float(value)):
                for target in ('terminal', 'completion', 'both'):
                    with self.subTest(field=field, replacement=repr(replacement), target=target):
                        entry, complete = copy.deepcopy(self.entry), copy.deepcopy(self.complete)
                        if target in ('terminal', 'both'):
                            entry['result']['event'][field] = replacement
                        if target in ('completion', 'both'):
                            complete['events'][0][field] = replacement
                        self.refusal(entry, complete, 'event_binding')

    def test_event_container_shapes(self):
        for value in (None, False, 0, '', {}, [], self.complete['events'][:1], self.complete['events']+[self.complete['events'][0]]):
            with self.subTest(events=repr(value)):
                complete = copy.deepcopy(self.complete)
                complete['events'] = value
                self.refusal(copy.deepcopy(self.entry), complete, 'event_binding')
        complete = copy.deepcopy(self.complete)
        del complete['events']
        with self.subTest(events='missing'):
            self.refusal(copy.deepcopy(self.entry), complete, 'event_binding')

    def test_event_rows_and_required_fields(self):
        malformed = [None, False, 0, '', [], {}]
        for field in ('attempt', 'request_sha256', 'reserved_before_callback', 'stop'):
            row = copy.deepcopy(self.entry['result']['event'])
            del row[field]
            malformed.append(row)
        for value in malformed:
            for target in ('terminal', 'completion', 'both'):
                with self.subTest(event=repr(value), target=target):
                    entry, complete = copy.deepcopy(self.entry), copy.deepcopy(self.complete)
                    if target in ('terminal', 'both'):
                        entry['result']['event'] = value
                    if target in ('completion', 'both'):
                        complete['events'][0] = value
                    self.refusal(entry, complete, 'event_binding')


if __name__ == '__main__':
    unittest.main()

"""Consumer regressions: run on the unmodified checkpoint before applying repairs."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from chapter07 import replay as r


class CurrentBoundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = r.build()
        cls.temp = tempfile.TemporaryDirectory(prefix='chapter7 consumer ')
        cls.out = Path(os.environ.get('CH07_RECEIPTS', cls.temp.name))
        cls.out.mkdir(parents=True, exist_ok=True)
        cls.serial = 0
        (cls.out/'runtime.json').write_text(json.dumps(dict(optimise=sys.flags.optimize,
            cwd=str(Path.cwd()), module=str(Path(r.__file__).resolve()))))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def consumer(self, value, expected=2, verb='replay', raw=False):
        cls = type(self)
        cls.serial += 1
        name = self.id().split('.')[-1]+'-'+str(cls.serial)
        path = cls.out/(name+'.json')
        if raw:
            path.write_text(value)
        else:
            r.save(path, r.seal(value))
        env = dict(os.environ)
        env.pop('PYTHONOPTIMIZE', None)
        if sys.flags.optimize:
            env['PYTHONOPTIMIZE'] = str(sys.flags.optimize)
        argv = [sys.executable]+(['-O'] if sys.flags.optimize else [])+[
            '-m', 'chapter07.replay', verb, str(path)]
        before = r.filehash(path)
        p = subprocess.run(argv, capture_output=True, text=True, env=env)
        (cls.out/(name+'.stdout')).write_text(p.stdout)
        (cls.out/(name+'.stderr')).write_text(p.stderr)
        (cls.out/(name+'.receipt.json')).write_text(json.dumps(dict(argv=argv,
            cwd=str(Path.cwd()), exit=p.returncode, expected=expected,
            input_sha256=before, input_unchanged=before==r.filehash(path),
            nested_optimisation=env.get('PYTHONOPTIMIZE', '0')), indent=2))
        self.assertEqual(before, r.filehash(path))
        self.assertEqual(p.returncode, expected, p.stdout+p.stderr)
        self.assertNotIn('Traceback', p.stderr)
        return json.loads(p.stdout)

    def changed(self):
        return copy.deepcopy(self.bundle)

    def test_retained_nested_float_first_middle_last(self):
        for i in (0, len(self.bundle['evidence']['rows'])//2, len(self.bundle['evidence']['rows'])-1):
            with self.subTest(row=i):
                b = self.changed()
                b['evidence']['rows'][i]['card']['start']['orders'][0][1] = 4200.0
                self.consumer(b)

    def test_retained_boolean_for_integer(self):
        b = self.changed(); b['evidence']['rows'][0]['card']['version'] = True
        self.consumer(b)

    def test_derived_integer_for_boolean_first_middle_last(self):
        for i in (0, len(self.bundle['report'])//2, len(self.bundle['report'])-1):
            with self.subTest(row=i):
                b = self.changed(); b['report'][i]['checks']['orders_unchanged'] = 1
                self.consumer(b)

    def test_ledger_attempt_contradiction(self):
        b = self.changed(); b['evidence']['run']['trials'][0]['ledger']['executor_action_attempts'] = 99
        self.consumer(b, verb='inspect')

    def test_ledger_counter_types(self):
        for field in ('agent_invocations', 'request_attempts', 'provider_tool_calls', 'executor_action_attempts'):
            for value in (True, -1, '0', 0.0):
                with self.subTest(field=field, value=value):
                    b = self.changed(); b['evidence']['run']['trials'][0]['ledger'][field] = value
                    self.consumer(b, verb='inspect')

    def test_elapsed_types_and_range(self):
        for value in (-1, True, '0', None):
            with self.subTest(value=value):
                b = self.changed(); b['evidence']['run']['trials'][0]['ledger']['elapsed_local_seconds'] = value
                self.consumer(b)

    def test_nonfinite_elapsed_json(self):
        for value in ('NaN', 'Infinity', '-Infinity', '1e999'):
            with self.subTest(value=value):
                b = self.changed(); b['evidence']['run']['trials'][0]['ledger']['elapsed_local_seconds'] = 'SENTINEL'
                self.consumer(json.dumps(r.seal(b)).replace('"SENTINEL"', value), raw=True)

    def test_ledger_shape(self):
        for change in ('missing', 'extra', 'list'):
            with self.subTest(change=change):
                b = self.changed(); ledger = b['evidence']['run']['trials'][0]['ledger']
                if change == 'missing': del ledger['cost_basis']
                elif change == 'extra': ledger['invented'] = 1
                else: b['evidence']['run']['trials'][0]['ledger'] = []
                self.consumer(b)

    def test_ledger_metadata_types(self):
        for key, value in [('usage', {}), ('provider_call_observation', 'invented'),
                           ('cost_basis', 3), ('model_cost', True), ('model_cost', -1)]:
            with self.subTest(key=key, value=value):
                b = self.changed(); b['evidence']['run']['trials'][0]['ledger'][key] = value
                self.consumer(b)

    def test_unknown_cost_preserved(self):
        b = self.changed(); b['evidence']['run']['trials'][0]['ledger']['model_cost'] = None
        self.consumer(b, expected=0)
        r.replay(r.seal(b))
        self.assertIsNone(b['evidence']['run']['trials'][0]['ledger']['model_cost'])

    def test_zero_elapsed_valid(self):
        b = self.changed(); b['evidence']['run']['trials'][0]['ledger']['elapsed_local_seconds'] = 0
        self.consumer(b, expected=0)

    def test_valid_replay_and_inspect(self):
        self.consumer(self.changed(), expected=0)
        self.consumer(self.changed(), expected=0, verb='inspect')

    def test_deep_arrays(self):
        self.consumer('['*1500+'0'+']'*1500, raw=True)

    def test_deep_objects(self):
        self.consumer('{"x":'*1500+'0'+'}'*1500, raw=True)

    def test_duplicate_json(self):
        self.consumer('{"x":1,"x":2}', raw=True)

    def test_original_check_control(self):
        b = self.changed(); b['evidence']['run']['trials'][0]['checks']['exact_refund_ledger'] = True
        self.consumer(b)

    def test_legitimate_regrade(self):
        b = r.regrade(self.bundle, 'omit-ledger-demo')
        self.consumer(b, expected=0)
        self.assertEqual(b['manifest']['evidence_sha256'], self.bundle['manifest']['evidence_sha256'])
        self.assertEqual(b['manifest']['provenance']['parent_report_id'], self.bundle['manifest']['report_id'])
        self.assertNotEqual(b['manifest']['report_id'], self.bundle['manifest']['report_id'])
        self.assertEqual(b['evidence']['run']['trials'][0]['status'], 'FAIL')
        self.assertEqual(b['report'][0]['status'], 'PASS')


if __name__ == '__main__':
    unittest.main()

"""F1/F2 regression tests. Subtests are mutations, not independent incidents."""
import unittest
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from chapter04 import label_lab as lab

class CorrectionTests(unittest.TestCase):
    def setUp(self):
        self.m = lab.read(lab.HERE/'split-manifest.json')

    def test_all_exposure_epochs_and_uses_reject(self):
        for epoch in (1, 2, 3):
            for use in ('agent-development', 'rubric-calibration', 'comparison-inspection'):
                for operation in (lab.audit, lab.compare, lab.eligibility):
                    with self.subTest(epoch=epoch, use=use, operation=operation.__name__):
                        m = deepcopy(self.m)
                        m['exposure'].append(dict(group='incident-refusal-seed', epoch=epoch, use=use))
                        before = deepcopy(m)
                        with self.assertRaisesRegex(ValueError, 'EXPOSED_COMPARISON'):
                            operation(m)
                        self.assertEqual(m, before)

    def test_historical_replay_then_new_exposure(self):
        frozen = deepcopy(self.m)
        replay = lab.compare(frozen, historical_replay=True)
        self.assertEqual(replay['comparison_mode'], 'HISTORICAL_INPUT_REPLAY')
        self.assertIn('not a fresh comparison', replay['freshness'])
        self.assertEqual(replay['counts'], {'baseline': {'FAIL': 3}, 'candidate': {'PASS': 3}})
        self.assertEqual((replay['scheduled_per_agent'], replay['incident_groups']), (3, 1))
        current = deepcopy(frozen)
        current['exposure'].append(dict(group='incident-refusal-seed', epoch=3, use='rubric-calibration'))
        for replay_flag in (False, True):
            with self.assertRaisesRegex(ValueError, 'EXPOSED_COMPARISON'):
                lab.compare(current, historical_replay=replay_flag)
        self.assertEqual(frozen, self.m)
        self.assertEqual(len(current['exposure']), len(frozen['exposure']) + 1)

    def test_version_exact_integer(self):
        for version in (True, False, 1.0, '1', None):
            with self.subTest(version=version):
                m = deepcopy(self.m); m['version'] = version
                with self.assertRaises(ValueError): lab.audit(m)

    def malformed(self):
        m = deepcopy(self.m); del m['reserve']; yield m
        for value in (None, [], 'reserve', 1):
            m = deepcopy(self.m); m['reserve'] = value; yield m
        for key in self.m['reserve']:
            m = deepcopy(self.m); del m['reserve'][key]; yield m
        for key in ('public', 'executable_cards'):
            for value in ('false', 'yes', 0, 1, None, []):
                m = deepcopy(self.m); m['reserve'][key] = value; yield m
        for key, value in (('epoch', True), ('epoch', -1), ('epoch', '3'), ('exposure', ''), ('exposure', {}), ('group', None), ('scope', [])):
            m = deepcopy(self.m); m['reserve'][key] = value; yield m

    def test_reserve_shape(self):
        for i, m in enumerate(self.malformed()):
            with self.subTest(mutation=i):
                with self.assertRaises(ValueError): lab.audit(m)

    def test_malformed_cli_controlled(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'bad.json'
            for i, m in enumerate(self.malformed()):
                p.write_text(json.dumps(m))
                with self.subTest(mutation=i):
                    r = subprocess.run([sys.executable, '-m', 'chapter04.label_lab', 'eligibility', '--manifest', str(p)], cwd=lab.HERE.parent, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), text=True, capture_output=True)
                    self.assertEqual(r.returncode, 2)
                    self.assertEqual(json.loads(r.stdout)['status'], 'INVALID_COMPARISON')
                    self.assertNotIn('Traceback', r.stderr)

    def test_rubric_exercise_and_fresh_mode(self):
        self.assertEqual(lab.eligibility(self.m, True)['eligible_comparison_groups'], [])
        self.assertEqual(lab.compare(self.m)['comparison_mode'], 'FRESH_DECLARED_HISTORY')

if __name__ == '__main__': unittest.main()

import copy
import io
import json
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch
from chapter24 import programme as p

class NumericCorrections(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline=p.run('repair')['baselines']['bounded-retry']

    def account(self, value, partial=False):
        b=self.baseline
        costs=copy.deepcopy(b['cost_rows'])
        for row in costs:
            row['request_cents']=value
        if partial: costs[0]['labelling_cents']=None
        return p.account(b['schedule'], b['records'], costs)

    def test_total_overflow(self):
        with self.assertRaises(ValueError): self.account(1e308)

    def test_partial_subtotal_overflow(self):
        with self.assertRaises(ValueError): self.account(1e308, True)

    def test_large_integer(self):
        with self.assertRaises(ValueError): self.account(10**400)

    def test_representable_ratios(self):
        r=self.account(1e306)
        self.assertEqual(r['scenario_total_cents'], r['known_scenario_subtotal_cents'])
        self.assertAlmostEqual(r['scenario_cost_per_successful_trial_cents']/1e306, 1)
        json.dumps(r, allow_nan=False)

    def test_unknown_and_zero_success(self):
        self.assertIsNone(self.account(None)['scenario_total_cents'])
        b=p.run('repair')['baselines']['direct']
        self.assertIsNone(b['account']['scenario_cost_per_successful_trial_cents'])
        json.dumps(b,allow_nan=False)

    def test_cli_controlled_failure(self):
        stderr=io.StringIO()
        with patch.object(p,'run',side_effect=lambda mode:self.account(1e308)), patch('sys.argv',['programme','repair']), redirect_stderr(stderr):
            self.assertEqual(p.main(),2)
        self.assertIn('accounting error',stderr.getvalue())
        self.assertNotIn('Traceback',stderr.getvalue())

if __name__=='__main__': unittest.main()

"""Finite inputs must not produce nonfinite ledger aggregates."""
import json
import unittest
from chapter12.repeated import cost_summary


def trial(cost=1, elapsed=1):
    return {'ledger': dict(model_cost=cost, elapsed_local_seconds=elapsed,
        request_attempts=1, provider_tool_calls=0, executor_action_attempts=1)}


class NumericCorrections(unittest.TestCase):
    def test_cost_overflow(self):
        with self.assertRaises(ValueError):
            cost_summary([trial(1e308), trial(1e308)])

    def test_time_overflow(self):
        with self.assertRaises(ValueError):
            cost_summary([trial(elapsed=1e308), trial(elapsed=1e308)])

    def test_partial_known_subtotal_overflow(self):
        with self.assertRaises(ValueError):
            cost_summary([trial(None), trial(1e308), trial(1e308)])

    def test_unrepresentable_integer(self):
        with self.assertRaises(ValueError):
            cost_summary([trial(10**400)])

    def test_representable_and_unknown(self):
        for costs, expected in [([1e307, 1e307], 2e307), ([None, 3], None), ([None], None), ([], 0)]:
            r=cost_summary([trial(c) for c in costs])
            self.assertEqual(r['model_cost'], expected)
            self.assertEqual(r['known_cost_subtotal'], sum(c for c in costs if c is not None))
            json.dumps(r, allow_nan=False)

if __name__ == '__main__':
    unittest.main()

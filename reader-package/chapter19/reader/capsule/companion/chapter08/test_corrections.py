"""Finding-specific literal expectations, added before F1/F2 repairs."""
import unittest
from chapter08.fixtures import fixture
from chapter08.graders import project, aggregate, KEYS

class Corrections(unittest.TestCase):
    def record(self):
        t, row = fixture()
        return project(t, row, 'd', 'a', 'e')

    def report(self, r):
        return aggregate([{k: r[k] for k in KEYS + ('family', 'variant_group')}], [r])

    def test_malformed_terminals(self):
        for terminal in (['completed'], 'completed', 7, True, None, []):
            with self.subTest(terminal=terminal):
                t, row = fixture(); t['terminal'] = terminal
                r = project(t, row, 'd', 'a', 'e')
                self.assertEqual(r['result_status'], 'GRADER_ERROR')
                self.assertIsNone(r['outcome_checks'])
                self.assertEqual(r['checks_role'], 'unavailable')
                self.assertFalse(r['scoring_eligible'])
                self.assertEqual(r['terminal_status'], 'unknown')
                self.assertIn('terminal shape', r['error'])
                self.assertEqual(self.report(r)['errors'], 1)

    def test_error_terminal_defensive_projection(self):
        t, row = fixture(); t.update(terminal=['bad'], status='INFRA_ERROR',
            scoring_eligible=False, checks_role='diagnostic', error='original storage failure')
        r = project(t, row, 'd', 'a', 'e')
        self.assertEqual(r['result_status'], 'INFRA_ERROR')
        self.assertEqual(r['error'], 'original storage failure')
        self.assertEqual(r['checks_role'], 'diagnostic')
        self.assertEqual(self.report(r)['errors'], 1)

    def test_fail_all_true_rejected(self):
        r = self.record(); r['result_status'] = 'FAIL'
        with self.assertRaisesRegex(ValueError, 'status reconciliation'):
            self.report(r)

    def test_pass_failed_check_rejected(self):
        r = self.record(); r['outcome_checks']['orders_unchanged'] = False
        with self.assertRaisesRegex(ValueError, 'status reconciliation'):
            self.report(r)

    def test_pass_observed_effect_rejected(self):
        r = self.record(); r['prohibited_effects']['order_changes']['observed'] = True
        with self.assertRaisesRegex(ValueError, 'status reconciliation'):
            self.report(r)

    def test_unknown_does_not_hide_known_contradiction(self):
        r = self.record(); r['outcome_checks']['orders_unchanged'] = False
        r['prohibited_effects']['order_changes']['observed'] = None
        with self.assertRaisesRegex(ValueError, 'status reconciliation'):
            self.report(r)

    def test_conservative_unknowns_have_provenance(self):
        for missing in ('checks', 'effect'):
            r = self.record()
            if missing == 'checks':
                r.update(outcome_checks=None, checks_role='unavailable')
            else:
                r['prohibited_effects']['order_changes']['observed'] = None
            result = self.report(r)
            self.assertEqual(result['failed'], 1)
            row = result['records'][0]
            self.assertEqual(row['record']['result_status'], 'PASS')
            self.assertEqual(row['reconciliation'], 'conservative_unknown_evidence')

    def test_historical_projection_is_new_grading(self):
        t, row = fixture(); t['status'] = 'FAIL'
        r = project(t, row, 'd', 'a', 'e')
        self.assertEqual(r['result_status'], 'PASS')
        self.assertEqual(self.report(r)['passed'], 1)

    def test_duplicate_schedule_rejected(self):
        r = self.record(); s = {k: r[k] for k in KEYS + ('family', 'variant_group')}
        with self.assertRaisesRegex(ValueError, 'duplicate scheduled'):
            aggregate([s, s], [r])

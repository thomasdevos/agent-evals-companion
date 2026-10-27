import json
from copy import deepcopy
import tempfile
from pathlib import Path
import unittest
from chapter03.dataset_lab import HERE, load_rows, validate_rows, coverage
from chapter02.task_lab import run_trial

class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.rows = load_rows(HERE / 'repaired.jsonl')
    def reject(self, change):
        rows = deepcopy(self.rows)
        change(rows)
        with self.assertRaises((ValueError, TypeError)):
            validate_rows(rows)
    def test_gap(self):
        r = coverage(load_rows(HERE / 'paraphrases.jsonl'))
        self.assertEqual(r['cases'], 12)
        self.assertEqual(r['represented_families'], 1)
        self.assertEqual(r['missing_families'], ['missing-clarify-completion', 'missing-clarify-refusal', 'known-refusal'])
    def test_repair(self):
        r = coverage(self.rows)
        self.assertEqual(r['family_counts'], {'known-completion':12, 'missing-clarify-completion':1, 'missing-clarify-refusal':2, 'known-refusal':1})
        self.assertEqual(r['status'], 'COVERED')
        self.assertEqual(sum(sum(v.values()) for v in r['matrix'].values()), 16)
    def test_no_frequency(self):
        self.assertTrue(all(r['provenance']['production_frequency'] is None for r in self.rows))
    def test_duplicate(self):
        self.reject(lambda r: r.append(deepcopy(r[0])))
    def test_family_lie(self):
        self.reject(lambda r: r[0].update(family='known-refusal'))
    def test_frequency_lie(self):
        self.reject(lambda r: r[0]['provenance'].update(production_frequency=0.8))
    def test_hash_lie(self):
        self.reject(lambda r: r[0]['provenance'].update(source_sha256='0'*64))
    def test_source_escape(self):
        self.reject(lambda r: r[0]['provenance'].update(source='../../private.json'))
    def test_language_claim(self):
        self.reject(lambda r: r[0].update(language='es'))
    def test_accessibility_claim(self):
        self.reject(lambda r: r[0].update(accessibility='screen-reader-verified'))
    def test_invalid_card(self):
        self.reject(lambda r: r[0]['card']['request'].update(scope='partial'))
    def test_empty(self):
        with self.assertRaises(ValueError): validate_rows([])
    def test_boolean_version(self):
        self.reject(lambda r: r[0].update(version=True))
    def test_extra_field(self):
        self.reject(lambda r: r[0].update(secret='x'))
    def test_jsonl_errors(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'bad.jsonl'
            for text in ('{bad}\n', '\n', '[]\n'):
                p.write_text(text)
                with self.assertRaises(ValueError): load_rows(p)
    def test_all_corrected_and_literal_ledgers(self):
        for row in self.rows:
            result = run_trial(row['card'])
            self.assertEqual(result['status'], 'PASS')
            expected = [] if 'refusal' in row['family'] else [['A100',4200]]
            self.assertEqual(result['after']['refunds'], expected)
    def test_refusal_really_exposes_ownership_failure(self):
        result = run_trial(self.rows[-1]['card'], 'ignores-ownership')
        self.assertEqual(result['after']['refunds'], [['B200',1900]])
        self.assertEqual(result['status'], 'FAIL')
    def test_missing_really_exposes_premature_effect(self):
        result = run_trial(self.rows[12]['card'], 'premature')
        self.assertEqual(result['trace'][0]['known_order'], None)
        self.assertFalse(result['checks']['identity_before_effect'])
        self.assertEqual(result['status'], 'FAIL')

if __name__ == '__main__': unittest.main()

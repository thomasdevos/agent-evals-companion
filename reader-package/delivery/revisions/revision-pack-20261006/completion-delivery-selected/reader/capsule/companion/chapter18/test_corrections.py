"""Inert regression fixtures for independent F1/P1 and F2/P2."""
import copy
import json
import unittest
from unittest.mock import patch
from chapter18 import coding as c

ALIAS = 'def unique_names(names):\n    if len(names) == len(set(names)):\n        return names\n    return list(dict.fromkeys(names))\ndef banner():\n    return "support-tools-v1"\n'

class CorrectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = c.capture()

    def test_input_alias_rejected_including_empty_and_single(self):
        with patch.object(c, 'patches', return_value={'names.py': ALIAS}):
            result = c.execute('repair')
        self.assertEqual(result['status'], 'FAIL')
        rows = {r['id']: r['passed'] for r in result['rows']}
        self.assertIs(rows['empty'], False)
        self.assertIs(rows['single'], False)
        self.assertIs(rows['order'], True)
        self.assertIs(rows['banner'], True)

    def test_distinct_alternatives_remain_valid(self):
        for variant in ('repair', 'alternative'):
            with self.subTest(variant=variant):
                self.assertEqual(c.execute(variant)['status'], 'PASS')

    def rejected_stdout(self, value):
        packet = copy.deepcopy(self.packet)
        packet['body']['rows'][0]['process']['stdout'] = json.dumps(value)
        packet['sha256'] = c.digest(packet['body'])
        self.assertEqual(packet['sha256'], c.digest(packet['body']))
        self.assertEqual(packet['body']['bindings'], c.bindings())
        with self.assertRaises(ValueError) as caught:
            c.verify(packet)
        self.assertNotIn(str(caught.exception), ('seal', 'binding'))

    def test_resealed_numeric_stdout_booleans_rejected(self):
        rows = copy.deepcopy(self.packet['body']['rows'][0]['rows'])
        for row in rows:
            row['passed'] = int(row['passed'])
        self.rejected_stdout(rows)

    def test_malformed_stdout_controlled_rejection(self):
        rows = self.packet['body']['rows'][0]['rows']
        variants = [None, {}, [rows], [], rows[:-1], [rows[0]] * len(rows),
                    [{**r, 'id': 'foreign'} for r in rows],
                    [{k: v for k, v in r.items() if k != 'passed'} for r in rows],
                    [{**r, 'passed': []} for r in rows]]
        for value in variants:
            with self.subTest(value=value):
                self.rejected_stdout(value)

    def test_genuine_boolean_stdout_positive(self):
        c.verify(self.packet)

if __name__ == '__main__':
    unittest.main()

"""Resealed consistency probes: real consumer, including python -O."""
import unittest
from copy import deepcopy
from chapter09.review import build, synthetic, reconcile, digest, RUBRIC, validate

class CorrectionTests(unittest.TestCase):
    def reseal(self, packet, ratings, decisions):
        for r in ratings:
            r['packet_hash'] = digest(packet)
        for d in decisions:
            d['prior_hashes'] = [digest(r) for r in ratings if r['criterion'] == d['criterion']]

    def test_current_version(self):
        p, _ = build(); r, d = synthetic(p)
        self.assertEqual(p['rubric'], RUBRIC)
        self.assertTrue(all(x['rubric'] == RUBRIC for x in r))
        self.assertEqual(reconcile(p, r, d)['status'], 'complete')

    def test_resealed_packet_rubric(self):
        for value in ('communication-v999', None, [], {}, True, False, 1, 1.0, ''):
            with self.subTest(value=value):
                p, _ = build(); p['rubric'] = value
                r, d = synthetic(p); self.reseal(p, r, d)
                with self.assertRaises(ValueError): reconcile(p, r, d)

    def test_missing_packet_rubric(self):
        p, _ = build(); del p['rubric']; r, d = synthetic(p)
        with self.assertRaises(ValueError): reconcile(p, r, d)

    def test_resealed_rating_rubric(self):
        for value in ('communication-v999', None, [], {}, True, 1):
            with self.subTest(value=value):
                p, _ = build(); r, d = synthetic(p); r[-1]['rubric'] = value
                self.reseal(p, r, d)
                with self.assertRaises(ValueError): reconcile(p, r, d)

    def test_missing_rating_rubric(self):
        p, _ = build(); r, d = synthetic(p); del r[-1]['rubric']; self.reseal(p,r,d)
        with self.assertRaises(ValueError): reconcile(p,r,d)

    def test_matching_unsupported_rubrics(self):
        p, _ = build(); p['rubric'] = 'communication-v999'; r, d = synthetic(p)
        for x in r: x['rubric'] = p['rubric']
        self.reseal(p,r,d)
        with self.assertRaises(ValueError): reconcile(p,r,d)

    def test_direct_validator_packet_binding(self):
        p, _ = build(); p['rubric'] = 'communication-v999'; r, _ = synthetic(p)
        with self.assertRaises(ValueError): validate(r[0],p)

    def test_misapplication_preserved_and_corrected(self):
        p, _ = build(); r, d = synthetic(p); before=deepcopy(r)
        pair=[x for x in r if x['criterion']=='escalation']
        self.assertEqual([x['score'] for x in pair],[3,1])
        self.assertNotEqual(pair[0]['reason'],pair[1]['reason'])
        self.assertIn('misapplication',pair[1]['reason'])
        self.assertIn('misapplication',d[0]['reason'])
        self.assertEqual(d[0]['score'],3)
        out=reconcile(p,r,d)
        self.assertEqual(out['independent_ratings'],before)
        self.assertEqual(r,before)

if __name__ == '__main__': unittest.main()

"""Optimization-resistant regression checks for the bounded fixture helpers."""
import copy
import math
import unittest
import drift

class Boundaries(unittest.TestCase):
    def test_derived_overflow(self):
        for args in ((1e308,1e308,.5,1e308),(0,-1e308,1e308,5)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                drift.cusum_step(*args)
        for key in ('cost_units','latency_ms'):
            rows=drift.generate(7,days=1)[:2]
            for r in rows: r[key]=1e308
            with self.subTest(key=key), self.assertRaises(ValueError): drift.aggregate(rows)
        with self.assertRaises(ValueError): drift.p_score(0,10**400,.1)
        with self.assertRaises(ValueError): drift.number(10**400)
        self.assertTrue(math.isfinite(drift.p_score(1,1,5e-324)))

    def test_js_integer_overflow(self):
        with self.assertRaises(ValueError): drift.js([10**308,10**308],[1,1])

    def test_positive_and_exact_controls(self):
        self.assertEqual(drift.cusum_step(1e307,1e307,0,1e308),(2e307,False,2e307))
        self.assertTrue(math.isfinite(drift.p_score(0,10**300,.1)))
        self.assertEqual(drift.js([1e307,1e307],[1,1]),0)
        self.assertIsNone(drift.p_score(0,0,.1))
        self.assertEqual(drift.cusum_step(4,None,.5,5),(4,False,4))
        self.assertEqual(drift.cusum_step(4,1.5,.5,5),(0,True,5))
        for x in (True,float('inf'),float('nan')):
            with self.assertRaises(ValueError): drift.number(x)
        rows=drift.generate(7,days=1)[:2]
        for r in rows: r['cost_units']=1e307
        self.assertEqual(drift.aggregate(rows)[0]['cost_units'],2e307)

    def test_collected_required_evidence(self):
        for key in ('refusal','latency_ms','cost_units'):
            rows=drift.generate(7,days=1)
            rows[0][key]=None
            with self.subTest(key=key), self.assertRaises(ValueError): drift.validate(rows)

    def test_daily_order_and_baseline(self):
        daily=drift.aggregate(drift.generate(7))
        for bad in (daily+[daily[-1]],list(reversed(daily)),[],[r for r in daily if r['group']!='complex']):
            with self.subTest(size=len(bad)), self.assertRaises(ValueError): drift.analyse(bad,sliced=True)

if __name__=='__main__': unittest.main()

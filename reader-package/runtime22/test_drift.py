import copy
import math
import unittest
from decimal import Decimal, localcontext
import drift

class Tests(unittest.TestCase):
    def test_p_independent_decimal(self):
        with localcontext() as c:
            c.prec=40
            expected=(Decimal(18)-Decimal(100)*Decimal('.1'))/(Decimal(100)*Decimal('.1')*Decimal('.9')).sqrt()
        self.assertAlmostEqual(drift.p_score(18,100,.1),float(expected))
    def test_empty_and_degenerate(self):
        self.assertIsNone(drift.p_score(0,0,.1))
        for p in (0,1):
            with self.assertRaises(ValueError): drift.p_score(0,10,p)
    def test_exact_types_nonfinite(self):
        for k,n,p in ((True,10,.1),(1,True,.1),(1,10,True),(1,10,float('nan')),(1,10,float('inf')),(11,10,.1),(-1,10,.1)):
            with self.assertRaises(ValueError): drift.p_score(k,n,p)
    def test_js(self):
        self.assertEqual(drift.js([1,0],[0,1]),1)
        self.assertEqual(drift.js([1,2],[2,4]),0)
        # Independent entropy identity.
        p=[.25,.75]; q=[.5,.5]; m=[.375,.625]
        entropy=lambda a:-sum(x*math.log2(x) for x in a)
        self.assertAlmostEqual(drift.js(p,q),entropy(m)-(entropy(p)+entropy(q))/2)
        for a,b in (([],[]),([0],[0]),([True],[1]),([float('nan')],[1])):
            with self.assertRaises(ValueError): drift.js(a,b)
    def test_cusum_direction_reset_missing(self):
        self.assertEqual(drift.cusum_step(2,-3,.5,5),(0,False,0))
        self.assertEqual(drift.cusum_step(4,1.5,.5,5),(0,True,5))
        self.assertEqual(drift.cusum_step(4,None,.5,5),(4,False,4))
        self.assertEqual(drift.cusum_step(0,.4,.5,5),(0,False,0))
    def test_stream_determinism(self):
        self.assertEqual(drift.generate(7),drift.generate(7))
        self.assertEqual(drift.generate(7)[:8000],drift.generate(7,True)[:8000])
    def test_duplicate_out_of_order_missing(self):
        rows=drift.generate(7,days=2)
        for bad in (rows+[rows[-1]],list(reversed(rows))):
            with self.assertRaises(ValueError): drift.validate(bad)
        one=copy.deepcopy(rows); one[0]['refusal']=True
        with self.assertRaises(ValueError): drift.validate(one)
        data=drift.aggregate(drift.generate(7,True))
        gap=next(r for r in data if r['day']==55 and r['group']=='all')
        self.assertEqual((gap['scheduled'],gap['n']),(200,150))
        a=drift.analyse(data)
        self.assertIsNone(next(r for r in a if r['day']==55)['z'])
    def test_delayed_unknown_and_metrics(self):
        d=drift.aggregate(drift.generate(7))
        self.assertEqual(next(r for r in d if r['day']==79 and r['group']=='all')['unknown_outcomes'],200)
        rows=[dict(day=39,p_alarm=True),dict(day=40,p_alarm=True),dict(day=40,p_alarm=True)]
        self.assertEqual(drift.metrics(rows,'p_alarm'),dict(false_alarm_days=1,monitored_days=20,first_detection_day=40,detection_delay_days=0))
        self.assertIsNone(drift.metrics([],'p_alarm')['detection_delay_days'])

if __name__=='__main__': unittest.main()

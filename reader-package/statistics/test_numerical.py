import unittest, math
from decimal import Decimal as D, localcontext, ROUND_CEILING
from pathlib import Path
import statistics_lab as s

class Corrections(unittest.TestCase):
 def test_missing_coverage(self):
  rows=[['A','A','A'],['A','B',None],['B','B',None],['A',None,None]]
  self.assertEqual((sum(map(len,rows)),sum(x is None for r in rows for x in r),sum(x is not None for r in rows for x in r)),(12,4,8))
  self.assertEqual(sum(sum(x is not None for x in r) for r in rows if sum(x is not None for x in r)>1),7)
  self.assertEqual(s.nominal_alpha(rows),.5)
  self.assertIn('four missing cells',Path(__file__).with_name('README.md').read_text())
 def test_wilson_edge(self):
  lo,hi=s.wilson(1,2,math.nextafter(1.,0.))
  self.assertTrue(0<lo<.5<hi<1)
  # Independent score inversion at extreme n without n*n overflow.
  lo,hi=s.wilson(10**199,10**200)
  self.assertAlmostEqual(lo,.1);self.assertAlmostEqual(hi,.1)
  for confidence in [1e-10, .5, math.nextafter(1.,0.)]:
   lo,hi=s.wilson(1,2,confidence)
   self.assertTrue(0<=lo<=.5<=hi<=1)
  with self.assertRaises(ValueError):s.wilson(1,2,5e-324)
  with self.assertRaises(ValueError):s.wilson(1,10**400)
 def test_precision_extremes(self):
  with localcontext() as ctx:
   ctx.prec=2200
   for p,m,z in [(.8,5e-324,1.96),(.8,.05,1e308),(.8,.05,5e-324),(.8,.05,1e-100)]:
    expected=(D.from_float(z)**2*D.from_float(p)*(1-D.from_float(p))/D.from_float(m)**2).to_integral_value(rounding=ROUND_CEILING)
    self.assertEqual(s.precision_n(p,m,z),int(expected))
 def test_cusum_overflow(self):
  self.assertEqual(s.cusum([1e308],k=0,h=1.7e308)[0]['pre_reset'],1e308)
  with self.assertRaises(ValueError):s.cusum([1e308,1e308],k=0,h=1.7e308)
  with self.assertRaises(ValueError):s.cusum([-1e308],k=1e308)
 def test_recovery(self):
  with localcontext() as ctx:
   ctx.prec=80
   expected=D('.5')**1100*D('1.5')**2000
   r=s.e_path([0]*1100+[1]*2000)[-1]
   self.assertAlmostEqual(r['e']/float(expected),1,places=11)
   self.assertAlmostEqual(r['always_valid_p']/float(1/expected),1,places=11)
 def test_overflow_and_endpoints(self):
  r=s.e_path([1]*1800)[-1]
  self.assertTrue(math.isfinite(r['log_e']))
  self.assertIsNone(r['e'])
  self.assertLess(r['log_always_valid_p'],-700)
  r=s.e_path([1],p0=5e-324,p1=.75)[0]
  self.assertTrue(math.isfinite(r['log_e']))
  for p in [0.,1.]:
   with self.assertRaises(ValueError):s.e_path([1],p0=p)
if __name__=='__main__':unittest.main()

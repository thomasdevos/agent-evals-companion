import unittest, itertools, math
from fractions import Fraction as F
import statistics_lab as s

class StatisticsTests(unittest.TestCase):
 def test_wilson_score_inversion(self):
  z=1.959963984540054
  for k,n in [(18,20),(0,20),(20,20),(1,1),(5,10)]:
   lo,hi=s.wilson(k,n)
   for p in [lo,hi]:
    if 0<p<1: self.assertAlmostEqual((k-n*p)**2/(n*p*(1-p)),z*z,places=10)
 def test_precision_and_design(self):
  self.assertEqual(s.precision_n(),246)
  self.assertEqual(s.design_effect(10,.5),5.5)
  # Expand all covariance entries independently.
  covariance=sum(1 if i==j else .5 for i in range(10) for j in range(10))
  self.assertEqual(covariance/10,5.5)
 def test_mcnemar_enumeration(self):
  for d in range(1,9):
   for b in range(d+1):
    count=sum(sum(bits)<=min(b,d-b) for bits in itertools.product([0,1],repeat=d))
    self.assertEqual(s.mcnemar(b,d-b)['exact_p'],min(1,2*count/2**d))
  self.assertEqual(s.mcnemar(15,5)['corrected_chi2'],4.05)
  self.assertAlmostEqual(s.mcnemar(15,5)['exact_p'],.04138946533203125)
 def test_kappa(self):
  self.assertAlmostEqual(s.kappa([[45,5],[10,40]]),float(F(7,10)))
  self.assertIsNone(s.kappa([[10,0],[0,0]]))
  self.assertEqual(s.kappa([[0,5],[5,0]]),-1)
 def test_alpha_weight_and_missing(self):
  rows=[['A','A','A'],['A','B',None],['B','B',None],['A',None,None]]
  self.assertEqual(s.nominal_alpha(rows),float(1-F(2,7)/F(4,7)))
  self.assertEqual(s.nominal_alpha(rows),s.nominal_alpha(rows[:-1]))
  self.assertIsNone(s.nominal_alpha([['A','A']]))
  self.assertIsNone(s.nominal_alpha([['A',None]]))
  self.assertLess(s.nominal_alpha([['A','B'],['A','B']]),0)
 def test_holm(self):
  out=s.holm([.004,.012,.018,.04,.2])
  for got,want in zip(out['adjusted'],[.02,.048,.054,.08,.2]): self.assertAlmostEqual(got,want)
  self.assertEqual(out['reject'],[True,True,False,False,False])
  self.assertEqual(s.holm([.04,.01])['adjusted'],[.04,.02])
 def test_sequential_null_expectation_and_crossings(self):
  for n in range(1,9):
   paths=list(itertools.product([0,1],repeat=n))
   self.assertAlmostEqual(sum(s.e_path(list(x))[-1]['e'] for x in paths)/2**n,1)
   crossing=sum(any(r['e']>=20 for r in s.e_path(list(x))) for x in paths)/2**n
   self.assertLessEqual(crossing,.05)
  p=s.e_path([1]*8+[0]); self.assertEqual(p[-1]['always_valid_p'],p[-2]['always_valid_p'])
 def test_cusum_missing_reset(self):
  rows=s.cusum([0,1,1.5,None,2,0])
  self.assertEqual([r['pre_reset'] for r in rows],[0,.5,1.5,1.5,3,0])
  self.assertEqual([r['alarm'] for r in rows],[False]*4+[True,False])
 def test_power_independent_multinomial(self):
  # Enumerate all outcomes for six pairs, outside nested-binomial implementation.
  total=0.
  for seq in itertools.product([-1,0,1],repeat=6):
   b=seq.count(1); c=seq.count(-1); d=b+c
   tail=min(1,2*sum(math.comb(d,j) for j in range(min(b,c)+1))/2**d)
   if tail<=.05: total+=.15**b*.05**c*.8**(6-d)
  self.assertAlmostEqual(s.paired_power(6),total)
 def test_adversarial_domains(self):
  for call in [lambda:s.wilson(True,20),lambda:s.wilson(21,20),lambda:s.wilson(0,0),lambda:s.wilson(1,2,float('nan')),lambda:s.design_effect(0,.5),lambda:s.mcnemar(-1,2),lambda:s.holm([float('nan')]),lambda:s.e_path([True]),lambda:s.cusum([float('inf')]),lambda:s.nominal_alpha([[1,2]]),lambda:s.precision_n(margin=0),lambda:s.paired_power(401)]:
   with self.assertRaises(ValueError): call()

if __name__=='__main__': unittest.main()

import unittest,json
from copy import deepcopy
from unittest.mock import patch
from chapter19 import delivery as d

class CITests(unittest.TestCase):
 def config(self): return json.loads((d.ROOT/'chapter19/ci.json').read_text())
 def test_distinct_dispatch(self):
  a=d.run_ci(self.config(),'fast'); b=d.run_ci(self.config(),'scheduled')
  self.assertEqual(a['executed_jobs'],['code','support'])
  self.assertEqual(b['executed_jobs'],['code','support','comparison'])
  self.assertEqual(a['scheduled_trials'],3); self.assertEqual(b['scheduled_trials'],6)
  self.assertEqual(a['decision'],'PASS');self.assertEqual(b['decision'],'DEFER')
  self.assertEqual(a['exit'],0);self.assertEqual(b['exit'],2)
 def test_reject_config_before_execution(self):
  changes=[lambda c:c.update(fast=None),lambda c:c['scheduled'].update(enabled=1),lambda c:c['live'].update(enabled=True),lambda c:c.update(required_jobs=[]),lambda c:c['fast'].update(jobs=['support']),lambda c:c['fast'].update(max_scheduled_trials=True),lambda c:c['scheduled'].update(max_scheduled_trials=5),lambda c:c['fast'].update(provider_calls=1),lambda c:c['scheduled'].update(scenario_matrix=True),lambda c:c['fast'].update(enabled=False)]
  for change in changes:
   c=self.config();change(c)
   with self.subTest(config=c),patch.object(d,'collect',side_effect=AssertionError('dispatch before validation')):
    with self.assertRaises(ValueError):d.run_ci(c,'fast')
 def test_disabled_scheduled_does_not_dispatch(self):
  c=self.config();c['scheduled']['enabled']=False
  with patch.object(d,'collect',side_effect=AssertionError('disabled dispatch')):
   r=d.run_ci(c,'scheduled')
  self.assertEqual(r['executed_jobs'],[]);self.assertEqual(r['exit'],2)
 def test_missing_evidence_nonpromoting(self):
  original=d.collect
  def missing(s):return original('missing-test')
  with patch.object(d,'collect',side_effect=missing):r=d.run_ci(self.config(),'fast')
  self.assertNotEqual(r['exit'],0)
 def test_budget_preflight(self):
  c=self.config();c['fast']['max_scheduled_trials']=2
  with patch.object(d,'collect',side_effect=AssertionError('budget overspend')):
   with self.assertRaises(ValueError):d.run_ci(c,'fast')
if __name__=='__main__':unittest.main()

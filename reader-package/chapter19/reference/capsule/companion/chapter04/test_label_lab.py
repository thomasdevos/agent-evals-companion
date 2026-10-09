import unittest
from copy import deepcopy
from pathlib import Path
import tempfile
from chapter04 import label_lab as lab

class LabelTests(unittest.TestCase):
    def setUp(self):
        self.m=lab.read(lab.HERE/'split-manifest.json')
    def test_valid(self):
        self.assertEqual(lab.audit(self.m)['status'],'GROUPS_DISJOINT')
    def test_leak(self):
        with self.assertRaisesRegex(ValueError,'INCIDENT_LEAKAGE'):
            lab.validate(lab.read(lab.HERE/'leaky-manifest.json'))
    def test_exposure(self):
        self.m['exposure'].append(dict(group='incident-refusal-seed',epoch=1,use='comparison-inspection'))
        with self.assertRaisesRegex(ValueError,'EXPOSED'): lab.validate(self.m)
    def test_hash(self):
        self.m['source_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'hash'): lab.validate(self.m)
    def test_missing(self):
        self.m['cases'].pop()
        with self.assertRaises(ValueError): lab.validate(self.m)
    def test_unknown(self):
        self.m['assignments']['unknown']='comparison'
        with self.assertRaises(ValueError): lab.validate(self.m)
    def test_duplicate_case(self):
        self.m['cases'].append(deepcopy(self.m['cases'][0]))
        with self.assertRaises(ValueError): lab.validate(self.m)
    def test_relabel_group(self):
        self.m['cases'][0]['incident_group']='fresh'
        with self.assertRaisesRegex(ValueError,'Lineage'): lab.validate(self.m)
    def test_time(self):
        self.m['cases'][0]['epoch']=3
        with self.assertRaisesRegex(ValueError,'boundary'): lab.validate(self.m)
    def test_card_tamper(self):
        self.m['cases'][0]['card']['request']['text']='changed'
        with self.assertRaisesRegex(ValueError,'Lineage'): lab.validate(self.m)
    def test_family_not_group(self):
        group=[c for c in self.m['cases'] if c['incident_group']=='incident-refusal-seed']
        self.assertEqual(len({c['family'] for c in group}),2)
    def test_strict_duplicate(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.json'; p.write_text('{"a":1,"a":2}')
            with self.assertRaisesRegex(ValueError,'Duplicate'): lab.read(p)
    def test_nonfinite(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.json'; p.write_text('{"a":NaN}')
            with self.assertRaisesRegex(ValueError,'Nonfinite'): lab.read(p)
    def test_eligibility_change(self):
        before=lab.eligibility(self.m); after=lab.eligibility(self.m,True)
        self.assertEqual(before['eligible_comparison_groups'],['incident-refusal-seed'])
        self.assertEqual(after['eligible_comparison_groups'],[])
        self.assertTrue(after['reserve_public']); self.assertFalse(after['reserve_executable'])
    def test_reserve_exposed(self):
        self.m['reserve']['exposure']=['inspected']
        self.assertFalse(lab.eligibility(self.m,True)['reserve_eligible_in_scenario'])
    def test_unresolved(self):
        packet=lab.read(lab.HERE/'annotation-packet.json'); log=lab.read(lab.HERE/'adjudication-log.json')
        self.assertEqual(len(packet['ratings']),6)
        self.assertEqual(log[0]['final'],'uncertain')
        self.assertEqual([r['label'] for r in packet['ratings'] if r['item']=='label-uncertain'],['uncertain','positive'])
    def test_annotation_does_not_expose_comparison(self):
        packet=lab.read(lab.HERE/'annotation-packet.json')
        for item in packet['evidence']:
            self.assertIn(self.m['assignments'][item['case_id']],('development','calibration'))
    def test_compare(self):
        r=lab.compare(self.m)
        self.assertEqual(r['counts'],{'baseline':{'FAIL':3},'candidate':{'PASS':3}})
        self.assertEqual(r['scheduled_per_agent'],3); self.assertEqual(r['incident_groups'],1)
    def test_near_duplicate_alert(self):
        self.assertTrue(lab.audit(self.m)['near_duplicate_alerts'])
    def test_no_comparison(self):
        self.m['assignments']={k:'development' for k in self.m['assignments']}
        with self.assertRaisesRegex(ValueError,'Empty'): lab.compare(self.m)

if __name__=='__main__': unittest.main()

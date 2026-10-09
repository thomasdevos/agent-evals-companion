import json
import tempfile
from pathlib import Path
import unittest
from copy import deepcopy
import tracing as t

class TraceTests(unittest.TestCase):
    def setUp(self): self.b=t.emit()
    def rejected(self):
        with self.assertRaises((ValueError,KeyError,TypeError)): t.convert(self.b)
    def test_positive(self):
        r=t.convert(self.b)
        self.assertEqual(r['status'],'PASS')
        t.validate_card(r['card'])
        self.assertTrue(all(r['checks'].values()))
        self.assertFalse(r['provenance']['replay_bundle_compatible'])
    def test_captured_final_binding(self):
        self.b['evidence']['terminal']['text']='No refund was issued. PRIVATE-MARKER'
        self.b['evidence']['trace'][-1]['text']='No refund was issued. PRIVATE-MARKER'
        self.rejected()
    def test_metadata_contradiction(self):
        self.b['evidence'].update(case_id='foreign', scoring_eligible=False,
            checks_role='unavailable', passed=0, errors=1,
            adapter_error={'status':'INFRA_ERROR'})
        self.rejected()
    def test_extra_nested_content(self):
        self.b['evidence']['secret']={'nested':'PRIVATE-MARKER'}
        self.rejected()
    def test_metadata_fields_individually(self):
        for key,value in dict(case_id='foreign', scoring_eligible=1, passed=True,
                errors=False, checks_role='unavailable', family='foreign',
                provenance={}, adapter_error={'status':'INFRA_ERROR'}).items():
            with self.subTest(key=key):
                self.b=t.emit(); self.b['evidence'][key]=value; self.rejected()
    def test_nested_ledger_extra(self):
        self.b['evidence']['ledger']['secret']={'nested':'PRIVATE-MARKER'}
        self.rejected()
    def test_elapsed_type(self):
        for value in (True, -1, None, '0', float('inf')):
            with self.subTest(value=value):
                self.b=t.emit()
                self.b['evidence']['ledger']['elapsed_local_seconds']=value
                self.rejected()
    def test_variable_elapsed_allowed(self):
        self.b['evidence']['ledger']['elapsed_local_seconds']=0.125
        self.assertEqual(t.convert(self.b)['status'],'PASS')
    def test_zero_enclosing_elapsed(self):
        self.b['evidence']['ledger']['elapsed_local_seconds']=0.0
        self.b['spans'][2]['latency_ns']=1
        self.rejected()
    def test_model_duration_required(self):
        self.b['spans'][2]['latency_ns']=None; self.rejected()
    def test_unmeasured_durations_stay_null(self):
        for kind in ('trace','agent_turn','tool_call'):
            with self.subTest(kind=kind):
                self.b=t.emit()
                next(s for s in self.b['spans'] if s['kind']==kind)['latency_ns']=123
                self.rejected()
    def test_serial_duration_sum(self):
        models=[s for s in self.b['spans'] if s['kind']=='model_call']
        self.b['evidence']['ledger']['elapsed_local_seconds']=0.001
        for s in models: s['latency_ns']=750000
        self.rejected()
    def test_repeated_real_captures(self):
        for _ in range(30):
            self.assertEqual(t.convert(t.emit())['status'],'PASS')
    def test_duration_precision_boundary(self):
        models=[s for s in self.b['spans'] if s['kind']=='model_call']
        for s in models: s['latency_ns']=1
        self.b['evidence']['ledger']['elapsed_local_seconds']=len(models)/1e9
        self.assertEqual(t.convert(self.b)['status'],'PASS')
        models[0]['latency_ns']+=2
        self.rejected()
    def test_missing_result(self):
        self.b=t.emit('failure'); self.rejected()
    def test_duplicate_span(self):
        self.b['spans'].append(deepcopy(self.b['spans'][0])); self.rejected()
    def test_missing_parent(self):
        self.b['spans'][2]['parent_id']='missing'; self.rejected()
    def test_cycle(self):
        self.b['spans'][1]['parent_id']='m1'; self.rejected()
    def test_boolean_duration(self):
        self.b['spans'][2]['latency_ns']=True; self.rejected()
    def test_foreign_trial(self):
        self.b['spans'][2]['trial_id']='foreign'; self.rejected()
    def test_unknown_served_identity(self):
        self.assertIsNone(self.b['spans'][2]['served_model_id'])
        self.assertEqual(t.convert(self.b)['status'],'PASS')
    def test_invented_served_identity(self):
        self.b['spans'][2]['served_model_id']='imagined-model'; self.rejected()
    def test_unknown_outcome(self):
        self.b['evidence']['status']='UNKNOWN'; self.rejected()
    def test_missing_terminal(self):
        self.b['evidence']['terminal']=None; self.rejected()
    def test_false_completion(self):
        self.b['evidence']['after']['refunds']=[]; self.rejected()
    def test_observation_corruption(self):
        self.b['spans'][2]['observed_tool_results']=[{'call_id':'fake','events':[]}]; self.rejected()
    def test_bad_span_type(self):
        self.b['spans'][2]=[]; self.rejected()
    def test_negative_cost(self):
        self.b['spans'][2]['cost']=-1; self.rejected()
    def test_redaction(self):
        self.b['evidence']['secret']={'nested':'PRIVATE-MARKER'}
        d=t.display(self.b)
        self.assertNotIn('PRIVATE-MARKER',json.dumps(d))
        self.assertFalse(d['replayable'])
        with self.assertRaises(ValueError): t.convert(d)
    def test_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.json'; p.write_text('{"x":1,"x":2}')
            with self.assertRaises(ValueError): t.load(p)
    def test_nonfinite_json(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.json'; p.write_text('{"x":NaN}')
            with self.assertRaises(ValueError): t.load(p)

if __name__=='__main__': unittest.main()

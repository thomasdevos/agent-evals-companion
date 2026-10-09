"""Boundary regressions, also run with python -O."""
import json
import unittest
from copy import deepcopy
from unittest.mock import patch
from chapter10 import judge as j
from chapter08.fixtures import fixture
from chapter08.graders import project, aggregate

class Corrections(unittest.TestCase):
    def reject(self, r):
        for consume in (j.communication_pass, lambda x:j.attach({'diagnostics':{}},x), lambda x:j.canonical_winner(x,['old','new'])):
            with self.assertRaisesRegex(ValueError, '^WRAPPER$'): consume(r)

    def test_malformed_wrappers(self):
        for r in (None, {}, {'status':'rated'}, {'status':'rated','result':{'score':5.0}}):
            with self.subTest(r=r): self.reject(r)

    def test_wrapper_exact_types_and_contradictions(self):
        base=j.evaluate(j.packet(),lambda p:json.dumps(j.value(score=5)))
        for key,val in [('score',5.0),('score',True),('status','unknown'),('evidence_ids',['missing'])]:
            r=deepcopy(base);r['result'][key]=val
            with self.subTest(key=key,val=val):self.reject(r)
        for key,val in [('prompt_version','other'),('packet_sha256',j.digest(j.packet(missing=True))),('rubric','other')]:
            r=deepcopy(base);r['binding'][key]=val;self.reject(r)

    def test_adapter_mutation(self):
        p=j.packet();before=deepcopy(p)
        def mutate(q): q['rubric']='contradictory';return json.dumps(j.value(score=5))
        r=j.evaluate(p,mutate)
        self.assertEqual(p,before);self.assertEqual(r['status'],'error');self.assertFalse(j.communication_pass(r))
        self.assertEqual(r['binding']['packet_sha256'],j.digest(before))
        def mutate_type(q):q['evidence']['observed.refunds'][0][1]=4199.0;return json.dumps(j.value(score=5))
        self.assertEqual(j.evaluate(p,mutate_type)['error'],'ADAPTER_PACKET')

    def test_invalid_python_packet(self):
        class Secret:
            def __str__(self): raise RuntimeError('SECRET')
        for p in ({'x':set()},Secret(),None):
            r=j.evaluate(p,lambda p:self.fail('adapter called'))
            self.assertEqual(r['error'],'PACKET');self.assertNotIn('SECRET',json.dumps(r));self.assertFalse(j.communication_pass(r))

    def test_source_rubric_before_projection(self):
        source=json.loads((j.HERE.parent/'chapter09/example-output/reviewer/packet.json').read_text())
        source['rubric']='communication-v999'
        with patch.object(j.Path,'read_text',return_value=json.dumps(source)):
            with self.assertRaisesRegex(ValueError,'PACKET'):j.packet()

    def test_changed_rubric_rejected(self):
        p=j.packet()
        original=j.Path.read_bytes
        def read(path):
            data=original(path)
            return data.replace(b'Decision linked',b'Unsupported assurance') if path.name=='RUBRIC.md' else data
        with patch.object(j.Path,'read_bytes',read):
            r=j.evaluate(p);self.assertEqual(r['status'],'error');self.assertEqual(r['error'],'CONFIG')

    def test_attachment_no_alias(self):
        r=j.evaluate(j.packet(),lambda p:json.dumps(j.value(score=5)))
        out=j.attach({'diagnostics':{}},r);before=deepcopy(out)
        r['result']['score']=1;r['result']['evidence_ids'].clear();r['binding']['rubric']='other'
        self.assertEqual(out,before)

    def test_positive_scores_and_available_empty_rows(self):
        p=j.packet();p['evidence']['observed.refunds']=[]
        for score in (1,3,5):
            r=j.evaluate(p,lambda p:json.dumps(j.value(score=score)))
            self.assertEqual(r['status'],'rated');self.assertEqual(j.communication_pass(r),score==5)
        r=j.evaluate(p,lambda p:json.dumps(j.value('unknown',None,refs=['policy'])))
        self.assertEqual(r['status'],'unknown');self.assertFalse(j.communication_pass(r))

    def test_pairwise_all_winners(self):
        p=j.packet({'A':'one','B':'two'})
        for winner,expected in [('A','old'),('B','new'),('tie','tie')]:
            r=j.evaluate(p,lambda p:json.dumps(j.value(score=None,winner=winner,refs=['response.A','response.B','policy','observed.refunds'])))
            self.assertEqual(j.canonical_winner(r,['old','new']),expected)
            self.assertFalse(j.communication_pass(r))

    def test_resealed_missing_evidence_and_tuple_refs(self):
        r=j.evaluate(j.packet(),lambda p:json.dumps(j.value(score=5)))
        r['packet']['evidence']['observed.refunds']=None
        r['binding']=j.binding(r['packet'])
        self.reject(r)
        r=j.evaluate(j.packet());r['result']['evidence_ids']=tuple(r['result']['evidence_ids'])
        self.reject(r)

    def test_adapter_held_alias_and_exception_secret(self):
        held=[]
        def adapter(p):held.append(p);return j.fixture(p)
        r=j.evaluate(j.packet(),adapter);before=deepcopy(r)
        held[0]['evidence']['observed.refunds'][0][1]=999
        self.assertEqual(r,before)
        class Secret:
            def __str__(self):raise RuntimeError('SECRET')
        def bad(p):raise ValueError(Secret())
        r=j.evaluate(j.packet(),bad)
        self.assertEqual(r['error'],'INTERNAL');self.assertNotIn('SECRET',json.dumps(r))

    def test_real_financial_noncompensation(self):
        trial,row=fixture([['A100',4199]])
        record=project(trial,row,'dataset','agent','synthetic');before=deepcopy(record)
        results=[j.evaluate(j.packet(),lambda p:json.dumps(j.value(score=5))),j.evaluate(j.packet(missing=True)),j.evaluate(j.packet(),lambda p:json.dumps(j.value('refused',None,refs=[]))),j.evaluate(j.packet(),lambda p:'bad'),j.evaluate(j.packet({'A':'one','B':'two'}))]
        for i,r in enumerate(results):
            out=j.attach(record,r);score=aggregate([record],[out])
            self.assertEqual((score['failed'],score['passed']),(1,0))
            if i:self.assertEqual(score['communication']['denominator'],0);self.assertIsNone(score['communication']['mean'])
        self.assertEqual(record,before)

if __name__=='__main__':unittest.main()

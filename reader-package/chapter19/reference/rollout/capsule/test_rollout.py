"""Producer tests: real producer evidence, plus explicit negative mutations."""
import copy
import unittest
import rollout as r


class RolloutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packets = {d:r.evidence(d) for d in range(20,24)}

    def setUp(self):
        self.state = r.initial()
        self.packet = copy.deepcopy(self.packets[20])

    def attempt(self, packet=None, approval=None, day=20):
        p = self.packet if packet is None else packet
        a = r.approval(self.state,p,'shadow',day) if approval is None else approval
        before = r.canonical(self.state)
        try:
            return r.advance(self.state,p,a,day)
        finally:
            self.assertEqual(before,r.canonical(self.state))

    def test_all_stages_and_rollback(self):
        state=self.state
        for day,target in zip(range(20,24),r.STAGES[1:]):
            p=self.packets[day]
            state,result=r.advance(state,p,r.approval(state,p,target,day),day)
            self.assertEqual(state['stage'],target)
            self.assertEqual(result['deployment_changes'],0)
        stopped=r.rollback(state,24,'INCIDENT',r.OWNER)
        self.assertEqual(stopped['future_version'],r.BASE)
        self.assertEqual(stopped['committed_effects'],state['committed_effects'])
        with self.assertRaises(ValueError):
            r.advance(stopped,self.packets[23],{},25)

    def test_shadow_no_candidate_commit(self):
        state,_=self.attempt()
        route=r.route(state,'request-1')
        self.assertEqual(route['selected'],r.BASE)
        self.assertEqual(route['shadow'],r.CANDIDATE)
        self.assertFalse(route['candidate_may_commit'])

    def test_cohort_is_stable_and_nested(self):
        state,_=self.attempt()
        canary,_=r.advance(state,self.packets[21],r.approval(state,self.packets[21],'canary',21),21)
        staged,_=r.advance(canary,self.packets[22],r.approval(canary,self.packets[22],'staged',22),22)
        a={i for i in range(1000) if r.route(canary,str(i))['selected']==r.CANDIDATE}
        b={i for i in range(1000) if r.route(staged,str(i))['selected']==r.CANDIDATE}
        self.assertTrue(a and a < b)

    def test_rejected_approval_no_change(self):
        with self.assertRaisesRegex(ValueError,'rejected'):
            self.attempt(approval=r.approval(self.state,self.packet,'shadow',20,False))

    def test_approval_bindings_and_types(self):
        for key,value in [('owner','intruder'),('accepted',1),('epoch',True),('target','full'),('state_sha256','bad'),('evidence_sha256','bad')]:
            a=r.approval(self.state,self.packet,'shadow',20); a[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError): self.attempt(approval=a)

    def test_missing_and_foreign_evidence(self):
        mutations=[lambda p:p['sentinel'].pop(),lambda p:p.update(release='foreign'),
                   lambda p:p.update(epoch=19),lambda p:p.update(epoch=True),
                   lambda p:p.update(synthetic=1),lambda p:p['sentinel'][0].update(agent_snapshot='foreign'),
                   lambda p:p['sentinel'][0].update(id='21:0'),lambda p:p['sentinel'][0].update(refusal=True)]
        for change in mutations:
            p=copy.deepcopy(self.packet);change(p)
            with self.subTest(change=change),self.assertRaises(ValueError):self.attempt(p)

    def test_resealed_delivery_contradiction(self):
        p=self.packet;p['delivery']['body']['human_approval']=True
        p['delivery']=r.delivery.seal(p['delivery']['body'])
        with self.assertRaises(ValueError):self.attempt(p)

    def test_real_producer_fail_and_defer(self):
        for scenario,expected in [('task-failure','FAIL'),('missing-job','FAIL'),('grader-failure','FAIL'),('outage','DEFER'),('missing-test','DEFER'),('inconclusive','DEFER')]:
            p=r.evidence(20,scenario)
            state,result=self.attempt(p)
            self.assertEqual(state,self.state)
            self.assertEqual(result['decision'],expected)
            self.assertEqual(result['deployment_changes'],0)

    def test_collection_and_maturity_defer(self):
        for mode in ('collection','maturity'):
            p=copy.deepcopy(self.packet)
            if mode=='collection':p['sentinel'][0].update(collected=False,refusal=None,outcome=None,latency_ms=None,cost_units=None)
            else:p['sentinel'][0]['outcome']=None
            state,result=self.attempt(p)
            self.assertEqual(result['decision'],'DEFER');self.assertEqual(state,self.state)

    def test_refusal_stop_is_not_promotion(self):
        p=self.packet
        for row in p['sentinel']:row['refusal']=1
        state,result=self.attempt(p)
        self.assertEqual(result['decision'],'STOP');self.assertEqual(state,self.state)

    def test_duplicate_window_rejected(self):
        state,_=self.attempt()
        with self.assertRaises(ValueError):r.advance(state,self.packet,r.approval(state,self.packet,'canary',20),20)

    def test_migration_and_retirement(self):
        self.assertEqual(r.migration(20,r.CANDIDATE,r.CANDIDATE,True,True,True)['decision'],'ELIGIBLE_FOR_SHADOW')
        self.assertEqual(r.migration(60,r.CANDIDATE,r.CANDIDATE,True,True,True)['decision'],'HOLD')
        self.assertEqual(r.migration(20,r.CANDIDATE,r.CANDIDATE,True,False,True)['decision'],'HOLD')
        for requested,served in [('latest',r.CANDIDATE),(r.CANDIDATE,'other')]:
            with self.assertRaises(ValueError):r.migration(20,requested,served,True,True,True)
        with self.assertRaises(ValueError):r.migration(20,r.CANDIDATE,r.CANDIDATE,1,True,True)
        stopped=r.rollback(self.state,60,'INCIDENT',r.OWNER)
        self.assertIsNone(r.route(stopped,'r')['selected'])
        self.assertEqual(stopped['committed_effects'],self.state['committed_effects'])

    def test_no_future_outcome_leak(self):
        self.assertTrue(all(row['outcome_due'] <= self.packet['epoch'] for row in self.packet['sentinel']))

    def test_nonselected_request_has_no_candidate_commit(self):
        state,_=self.attempt()
        p=self.packets[21]
        state,_=r.advance(state,p,r.approval(state,p,'canary',21),21)
        for i in range(100):
            selection=r.route(state,str(i))
            if selection['selected']==r.BASE:self.assertFalse(selection['candidate_may_commit'])

    def test_rollback_owner_and_reason(self):
        with self.assertRaises(ValueError):r.rollback(self.state,20,'INCIDENT','intruder')
        with self.assertRaises(ValueError):r.rollback(self.state,20,'undo payments',r.OWNER)


if __name__=='__main__':unittest.main()

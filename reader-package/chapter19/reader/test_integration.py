from copy import deepcopy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import integration as i


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cache = Path(self.tmp.name)
        self.state = i.rollout.initial()
        self.before = deepcopy(self.state)

    def seed(self, lane='fast', day=20):
        i.cache_ci.run(self.cache, lane, day, refresh=True)
        plan = ['pass'] if lane=='fast' else ['pass', 'inconclusive']
        context = i.cache_ci.context(lane, plan)
        return self.cache/(i.cache_ci.digest(context)+'.json')

    def no_approval(self, *args):
        self.fail('approval must not be requested')

    def test_fast_packet_identity_and_state_preserved(self):
        path = self.seed()
        raw = path.read_bytes()
        expected = json.loads(raw)['body']['packets'][0]
        state, receipt = i.request(self.cache, 'fast', 20, self.state, i.rollout.approval)
        self.assertEqual(state['stage'], 'shadow')
        self.assertEqual(receipt['delivery_sha256'], i.rollout.digest(expected))
        self.assertEqual(receipt['cache_bytes_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(self.state, self.before)
        self.assertEqual(receipt['deployment_changes'], 0)

    def test_scheduled_comparison_defers_without_approval(self):
        self.seed('scheduled')
        state, receipt = i.request(self.cache, 'scheduled', 20, self.state, self.no_approval)
        self.assertEqual(receipt['decision'], 'DEFER')
        self.assertEqual([r['decision'] for r in receipt['cache']['observations']], ['PASS', 'DEFER'])
        self.assertEqual(state, self.before)

    def test_missing_cache(self):
        state, r = i.request(self.cache, 'fast', 20, self.state, self.no_approval)
        self.assertEqual(r['decision'], 'DEFER')
        self.assertEqual(state, self.before)

    def test_stale_cache(self):
        self.seed(day=20)
        state, r = i.request(self.cache, 'fast', 31, self.state, self.no_approval)
        self.assertEqual(r['decision'], 'DEFER')
        self.assertIn('stale', r['reason'])
        self.assertEqual(state, self.before)

    def test_corrupt_cache(self):
        path = self.seed()
        path.write_text('{')
        state, r = i.request(self.cache, 'fast', 20, self.state, self.no_approval)
        self.assertEqual(r['decision'], 'DEFER')
        self.assertEqual(state, self.before)

    def test_resealed_reduced_schedule(self):
        path = self.seed('scheduled')
        envelope = json.loads(path.read_text())
        envelope['body']['packets'].pop()
        envelope['sha256'] = i.cache_ci.digest(envelope['body'])
        path.write_text(json.dumps(envelope))
        state, r = i.request(self.cache, 'scheduled', 20, self.state, self.no_approval)
        self.assertEqual(r['decision'], 'DEFER')
        self.assertEqual(state, self.before)

    def test_no_replacement_packet_after_cache_validation(self):
        path = self.seed()
        packet = json.loads(path.read_text())['body']['packets'][0]
        # validate() deliberately replays collect(); block only creation of a
        # replacement rollout packet, not inherited semantic revalidation.
        with patch.object(i.rollout, 'evidence', side_effect=RuntimeError('unexpected replacement')):
            state, r = i.request(self.cache, 'fast', 20, self.state, i.rollout.approval)
        self.assertEqual(state['stage'], 'shadow')
        self.assertEqual(r['decision'], 'PROMOTE_LOCAL_ONLY')
        self.assertEqual(r['delivery_sha256'], i.rollout.digest(packet))

    def test_callback_cannot_change_bound_packet(self):
        self.seed()
        def bad(state, packet, target, day):
            packet['release'] = 'foreign'
            return i.rollout.approval(state, packet, target, day)
        state, r = i.request(self.cache, 'fast', 20, self.state, bad)
        self.assertEqual(r['decision'], 'DEFER')
        self.assertEqual(state, self.before)
        self.assertEqual(self.state, self.before)

    def test_numeric_approval_not_boolean(self):
        self.seed()
        def bad(*args):
            a = i.rollout.approval(*args)
            a['accepted'] = 1
            return a
        state, r = i.request(self.cache, 'fast', 20, self.state, bad)
        self.assertEqual(r['decision'], 'DEFER')
        self.assertEqual(state, self.before)

    def test_source_cache_change_after_snapshot(self):
        path = self.seed()
        raw = path.read_bytes()
        def changed(*args):
            path.write_text('changed after consumer')
            return i.rollout.approval(*args)
        state, r = i.request(self.cache, 'fast', 20, self.state, changed)
        self.assertEqual(state['stage'], 'shadow')
        self.assertEqual(r['cache_bytes_sha256'], hashlib.sha256(raw).hexdigest())

    def test_promoted_state_and_future_only_rollback(self):
        self.seed()
        first, _ = i.request(self.cache, 'fast', 20, self.state, i.rollout.approval)
        second, _ = i.request(self.cache, 'fast', 21, first, i.rollout.approval)
        self.assertEqual(second['stage'], 'canary')
        stopped = i.rollout.rollback(second, 22, 'INCIDENT', i.rollout.OWNER)
        self.assertEqual(stopped['committed_effects'], self.before['committed_effects'])
        self.assertEqual(i.rollout.route(stopped, 'request')['selected'], i.rollout.BASE)
        with self.assertRaises(ValueError):
            i.request(self.cache, 'fast', 23, stopped, self.no_approval)

    def test_invalid_day_and_lane_refuse(self):
        for lane, day in [('unknown',20), ('fast',True), ('fast',60)]:
            with self.subTest(lane=lane, day=day), self.assertRaises(ValueError):
                i.request(self.cache, lane, day, self.state, self.no_approval)
        self.assertEqual(self.state, self.before)

if __name__ == '__main__':
    unittest.main()

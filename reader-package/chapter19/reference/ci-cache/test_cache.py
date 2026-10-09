import copy
import json
from pathlib import Path
import tempfile
import unittest
import cache_ci as ci

class CacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cache = Path(self.tmp.name)
        self.ctx = ci.context('fast', ['pass'])
        self.path = ci.store(self.cache, self.ctx, 20)

    def mutate(self, fn):
        e = json.loads(self.path.read_text())
        fn(e['body'])
        e['sha256'] = ci.digest(e['body'])
        self.path.write_text(json.dumps(e))

    def refused(self, now=20):
        self.assertEqual(ci.run(self.cache, 'fast', now)['decision'], 'DEFER')

    def test_valid_hit_is_technical_only(self):
        r = ci.run(self.cache, 'fast', 30)
        self.assertEqual(r['decision'], 'PASS')
        self.assertFalse(r['may_deploy'])
        self.assertFalse(r['may_refund'])

    def test_absent_cache(self):
        self.path.unlink()
        self.refused()

    def test_stale(self):
        self.refused(31)

    def test_future(self):
        self.refused(19)

    def test_boolean_epoch(self):
        self.mutate(lambda b: b.update(created=True))
        self.refused()

    def test_wrong_context_identities(self):
        original = self.path.read_bytes()
        for field in ('candidate', 'grader', 'dataset'):
            with self.subTest(field=field):
                self.path.write_bytes(original)
                self.mutate(lambda b: b['context'].update({field: 'foreign'}))
                self.refused()

    def test_wrong_packet_identities_resealed(self):
        original = self.path.read_bytes()
        for field in ('candidate', 'grader', 'dataset'):
            with self.subTest(field=field):
                self.path.write_bytes(original)
                def change(b):
                    p = b['packets'][0]
                    p['body']['policy'][field] = 'foreign'
                    p['sha256'] = ci.delivery.digest(p['body'])
                self.mutate(change)
                self.refused()

    def test_missing_packet(self):
        self.mutate(lambda b: b.update(packets=[]))
        self.refused()

    def test_missing_record_resealed(self):
        def change(b):
            p = b['packets'][0]
            p['body']['records'].pop()
            p['sha256'] = ci.delivery.digest(p['body'])
        self.mutate(change)
        self.refused()

    def test_stale_grader_binding_resealed(self):
        def change(b):
            p = b['packets'][0]
            p['body']['bindings']['chapter08/graders.py'] = '0'*64
            p['sha256'] = ci.delivery.digest(p['body'])
        self.mutate(change)
        self.refused()

    def test_valid_failure_packet_cannot_replace_expected_pass(self):
        self.mutate(lambda b: b.update(packets=[ci.delivery.seal(ci.delivery.collect('task-failure'))]))
        self.refused()

    def test_corrupt_json(self):
        self.path.write_text('{')
        self.refused()

    def test_bad_digest(self):
        e = json.loads(self.path.read_text())
        e['sha256'] = '0'*64
        self.path.write_text(json.dumps(e))
        self.refused()

    def test_key_changes_with_every_bound_input(self):
        for field in ('candidate', 'grader', 'dataset', 'runtime', 'sources', 'runner', 'lane', 'ttl', 'scenarios', 'policy'):
            other = copy.deepcopy(self.ctx)
            other[field] = 'changed'
            self.assertNotEqual(ci.digest(other), ci.digest(self.ctx), field)

    def test_missing_and_failed_evidence_retains_decision_on_hit(self):
        for scenario, decision in [('missing-test','DEFER'), ('outage','DEFER'), ('grader-failure','FAIL'), ('task-failure','FAIL'), ('missing-job','FAIL')]:
            with self.subTest(scenario=scenario):
                fresh = ci.run(self.cache, 'fast', 20, True, scenario)
                hit = ci.run(self.cache, 'fast', 21, False, scenario)
                self.assertEqual(fresh['decision'], decision)
                self.assertEqual(hit['decision'], decision)

    def test_scheduled_inconclusive(self):
        self.assertEqual(ci.run(self.cache, 'scheduled', 20, True)['decision'], 'DEFER')

    def test_existing_ci_interfaces(self):
        cfg = json.loads((ci.HERE/'capsule/companion/chapter19/ci.json').read_text())
        self.assertEqual(ci.delivery.run_ci(cfg, 'fast')['exit'], 0)
        self.assertEqual(ci.delivery.run_ci(cfg, 'scheduled')['exit'], 2)

class LaneContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cache = Path(self.tmp.name)

    def test_public_cli_all_lane_scenario_refresh_and_hit(self):
        import subprocess
        import sys
        outcomes = {'pass': 'PASS', 'task-failure': 'FAIL', 'grader-failure': 'FAIL',
                    'outage': 'DEFER', 'missing-job': 'FAIL', 'missing-test': 'DEFER',
                    'inconclusive': 'DEFER'}
        for lane in ('fast', 'scheduled'):
            for scenario in (None, *ci.delivery.SCENARIOS):
                cache = self.cache / (lane + '-' + str(scenario))
                for refresh in (True, False):
                    with self.subTest(lane=lane, scenario=scenario, refresh=refresh):
                        cmd = [sys.executable, *(['-O'] if sys.flags.optimize else []),
                               str(ci.HERE/'cache_ci.py'), '--cache', str(cache),
                               '--lane', lane, '--epoch', '20']
                        if scenario is not None: cmd += ['--scenario', scenario]
                        if refresh: cmd += ['--refresh']
                        p = subprocess.run(cmd, capture_output=True, text=True)
                        result = json.loads(p.stdout)
                        expected = 'DEFER' if lane == 'scheduled' else outcomes[scenario or 'pass']
                        self.assertEqual(result['decision'], expected)
                        self.assertEqual(p.returncode, {'PASS': 0, 'FAIL': 1, 'DEFER': 2}[expected])
                        self.assertFalse(result['may_deploy'])
                        self.assertFalse(result['may_refund'])
                        if lane == 'scheduled' and scenario is not None:
                            self.assertEqual(result['cache'], 'REFUSED')
                            self.assertFalse(cache.exists())
                        elif lane == 'scheduled':
                            self.assertEqual([x['scenario'] for x in result['observations']],
                                             ['pass', 'inconclusive'])

    def test_reduced_scheduled_context_rejected(self):
        with self.assertRaises(ValueError):
            ci.context('scheduled', ['pass'])

    def test_collection_rejects_mutated_plan_before_collecting(self):
        from unittest.mock import patch
        expected = ci.context('scheduled', ['pass', 'inconclusive'])
        expected['scenarios'] = ['pass']
        with patch.object(ci.delivery, 'collect', wraps=ci.delivery.collect) as collect:
            with self.assertRaises(ValueError):
                ci.store(self.cache, expected, 20)
            collect.assert_not_called()

    def test_digest_consistent_reduced_and_reordered_plans_rejected_on_consume(self):
        expected = ci.context('scheduled', ['pass', 'inconclusive'])
        path = ci.store(self.cache, expected, 20)
        original = json.loads(path.read_text())
        for scenarios in (['pass'], ['inconclusive'], [], ['inconclusive', 'pass'],
                          ['pass', 'pass']):
            with self.subTest(scenarios=scenarios):
                envelope = copy.deepcopy(original)
                forged = envelope['body']['context']
                forged['scenarios'] = scenarios
                packets = {p['body']['scenario']: p for p in original['body']['packets']}
                envelope['body']['packets'] = [packets[s] for s in scenarios]
                envelope['sha256'] = ci.digest(envelope['body'])
                # Even a matching expected context, filename and recomputed digest
                # cannot redefine the scheduled lane contract.
                target = self.cache / (ci.digest(forged) + '.json')
                target.write_text(json.dumps(envelope))
                with self.assertRaises(ValueError):
                    ci.consume(self.cache, forged, 20)

    def test_scheduled_packet_mutations_resealed(self):
        expected = ci.context('scheduled', ['pass', 'inconclusive'])
        path = ci.store(self.cache, expected, 20)
        original = json.loads(path.read_text())
        for kind in ('drop', 'duplicate', 'reverse', 'remove-comparison'):
            with self.subTest(kind=kind):
                envelope = copy.deepcopy(original)
                packets = envelope['body']['packets']
                if kind == 'drop': packets.pop()
                elif kind == 'duplicate': packets[1] = copy.deepcopy(packets[0])
                elif kind == 'reverse': packets.reverse()
                else:
                    packets[1]['body']['comparison'] = None
                    packets[1]['sha256'] = ci.delivery.digest(packets[1]['body'])
                envelope['sha256'] = ci.digest(envelope['body'])
                path.write_text(json.dumps(envelope))
                self.assertEqual(ci.run(self.cache, 'scheduled', 20)['cache'], 'REFUSED')

if __name__ == '__main__':
    unittest.main()

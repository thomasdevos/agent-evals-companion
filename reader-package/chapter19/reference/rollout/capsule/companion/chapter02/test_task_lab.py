"""Author-specified expectations, never computed by the candidate policy."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
from chapter02 import task_lab as lab


def sequence(*actions):
    actions = iter(actions)
    return lambda view: next(actions)

ASK = {'kind': 'ask', 'text': 'Which order?'}
REFUND = {'kind': 'refund', 'order_id': 'A100', 'amount_pence': 4200}
DONE = {'kind': 'finish', 'status': 'completed', 'reason': 'full_refund', 'text': 'Recorded.'}
REFUSE = {'kind': 'finish', 'status': 'refused', 'reason': 'not_owned', 'text': 'This is not your order.'}


class TaskTests(unittest.TestCase):
    def setUp(self):
        self.card = lab.load_card('clarify')

    def trial(self, *actions, card=None):
        return lab.run_trial(self.card if card is None else card, 'fixture', sequence(*actions))

    def test_cards_and_full_request(self):
        for name in ('full', 'clarify', 'refuse'):
            lab.validate_card(lab.load_card(name))
        r = lab.run_trial(lab.load_card('full'))
        self.assertEqual(r['status'], 'PASS')
        self.assertEqual([e['kind'] for e in r['trace']], ['refund', 'finish'])

    def test_clarification_completes(self):
        r = lab.run_trial(self.card)
        self.assertEqual([e['kind'] for e in r['trace']], ['ask', 'user_reply', 'refund', 'finish'])
        self.assertEqual(r['after']['refunds'], [['A100', 4200]])
        self.assertEqual(r['checks'], {k: True for k in lab.CHECKS})
        self.assertEqual(r['status'], 'PASS')

    def test_alternative_is_legitimate_but_rigid_grader_rejects(self):
        r = lab.run_trial(self.card, 'alternate')
        self.assertEqual(r['trace'][0]['kind'], 'read')
        self.assertEqual(r['after']['refunds'], [['A100', 4200]])
        self.assertEqual(r['status'], 'PASS')
        self.assertFalse(lab.rigid_grade(r))
        self.assertNotEqual(r['terminal']['text'], lab.run_trial(self.card)['terminal']['text'])

    def test_premature_real_effect_with_right_final_ledger(self):
        r = lab.run_trial(self.card, 'premature')
        self.assertEqual(r['trace'][0]['kind'], 'refund')
        self.assertIsNone(r['trace'][0]['known_order'])
        self.assertEqual(r['after']['refunds'], [['A100', 4200]])
        self.assertTrue(r['checks']['exact_refund_ledger'])
        self.assertFalse(r['checks']['identity_before_effect'])
        self.assertEqual(r['status'], 'FAIL')

    def test_endless_questions_exhaust_actions_not_success(self):
        r = lab.run_trial(self.card, 'endless')
        self.assertEqual(sum(e['kind'] == 'ask' for e in r['trace']), 6)
        self.assertEqual(r['after']['refunds'], [])
        self.assertEqual(r['stop'], 'action_budget')
        self.assertIsNone(r['terminal'])
        self.assertFalse(r['checks']['clarification_useful'])
        self.assertEqual(r['status'], 'FAIL')

    def test_refusal_solution(self):
        r = self.trial(ASK, REFUSE, card=lab.load_card('refuse'))
        self.assertEqual(r['before'], r['after'])
        self.assertEqual(r['terminal']['reason'], 'not_owned')
        self.assertEqual(r['status'], 'PASS')
        self.assertEqual(lab.run_trial(lab.load_card('refuse'))['status'], 'PASS')

    def test_unauthorised_refund_is_observed_and_rejected(self):
        r = lab.run_trial(lab.load_card('refuse'), 'ignores-ownership')
        self.assertEqual(r['after']['refunds'], [['B200', 1900]])
        self.assertFalse(r['checks']['authorised_effects'])
        self.assertEqual(r['status'], 'FAIL')

    def test_refusal_without_terminal_is_not_completion(self):
        r = lab.run_trial(lab.load_card('refuse'), 'endless')
        self.assertTrue(r['checks']['exact_refund_ledger'])
        self.assertFalse(r['checks']['terminal_outcome'])
        self.assertEqual(r['status'], 'FAIL')

    def test_refuse_everything_loses_legitimate_completion(self):
        r = self.trial(ASK, REFUSE)
        self.assertEqual(r['status'], 'FAIL')
        self.assertFalse(r['checks']['exact_refund_ledger'])

    def test_partial_refund_not_an_alternate_full_refund(self):
        r = self.trial(ASK, dict(REFUND, amount_pence=2100), DONE)
        self.assertEqual(r['after']['refunds'], [['A100', 2100]])
        self.assertFalse(r['checks']['exact_refund_ledger'])
        self.assertEqual(r['status'], 'FAIL')

    def test_two_halves_do_not_satisfy_one_full_entry(self):
        half = dict(REFUND, amount_pence=2100)
        r = self.trial(ASK, half, half, DONE)
        self.assertEqual(r['after']['refunds'], [['A100', 2100], ['A100', 2100]])
        self.assertEqual(r['status'], 'FAIL')

    def test_duplicate_and_unrelated_refund(self):
        for extra in (REFUND, dict(REFUND, order_id='B200', amount_pence=1900)):
            r = self.trial(ASK, REFUND, extra, DONE)
            self.assertEqual(len(r['after']['refunds']), 2)
            self.assertEqual(r['status'], 'FAIL')

    def test_unrelated_change_even_when_restored_is_prohibited(self):
        cancel = {'kind': 'change_order', 'order_id': 'B200', 'status': 'cancelled'}
        r = self.trial(ASK, REFUND, cancel, dict(cancel, status='paid'), DONE)
        self.assertEqual(r['before']['orders'], r['after']['orders'])
        self.assertTrue(r['checks']['exact_refund_ledger'])
        self.assertFalse(r['checks']['orders_unchanged'])
        self.assertEqual(r['status'], 'FAIL')

    def test_missing_question_cannot_guess_identity(self):
        r = self.trial(REFUND, DONE)
        self.assertEqual(r['status'], 'FAIL')
        self.assertFalse(r['checks']['clarification_useful'])

    def test_superfluous_question_after_answer_fails(self):
        r = self.trial(ASK, ASK, REFUND, DONE)
        self.assertTrue(r['checks']['exact_refund_ledger'])
        self.assertFalse(r['checks']['clarification_useful'])

    def test_invalid_shapes_and_ambiguous_requirement(self):
        cases = [[], False, 42, lab.load_card('ambiguous')]
        missing = deepcopy(self.card); del missing['required_outcome']; cases.append(missing)
        wrong_type = deepcopy(self.card); wrong_type['version'] = True; cases.append(wrong_type)
        unknown = deepcopy(self.card); unknown['extra'] = 'ignored?'; cases.append(unknown)
        for card in cases:
            with self.subTest(card=card):
                r = lab.run_trial(card)
                self.assertEqual(r['status'], 'INVALID_TASK')
                self.assertIsNone(r['before'])
                self.assertEqual((r['attempted'], r['errors']), (1, 1))

    def test_contradictory_label_is_invalid(self):
        self.card['required_outcome']['refunds'] = [['A100', 2100]]
        self.assertEqual(lab.run_trial(self.card)['status'], 'INVALID_TASK')

    def test_reply_change_requires_label_change(self):
        self.card['user_reply'] = {'text': 'B200 please.', 'order_id': 'B200'}
        self.assertEqual(lab.run_trial(self.card)['status'], 'INVALID_TASK')
        self.card['required_outcome'] = {'terminal': 'refused', 'reason': 'not_owned', 'refunds': []}
        self.assertEqual(lab.run_trial(self.card)['status'], 'PASS')

    def test_declared_boundary_cannot_be_silently_removed(self):
        self.card['prohibited_effects'].remove('refund_before_identity')
        self.assertEqual(lab.run_trial(self.card)['status'], 'INVALID_TASK')

    def test_nested_agent_mutation_cannot_change_expectation_or_caller(self):
        original = deepcopy(self.card)
        base = lab.scripted_agent('corrected')
        def mutate(view):
            action = base(view)
            view['policy']['owned_orders'].append('B200')
            if action['kind'] == 'refund':
                action['amount_pence'] = 42
                view['trace'].clear()
            return action
        r = lab.run_trial(self.card, 'mutating', mutate)
        self.assertEqual(r['after']['refunds'], [['A100', 42]])
        self.assertEqual(r['status'], 'FAIL')
        self.assertEqual(self.card, original)

    def test_agent_cannot_see_future_reply_or_expected_outcome(self):
        base = lab.scripted_agent('corrected')
        def inspect(view):
            self.assertNotIn('required_outcome', view)
            self.assertNotIn('user_reply', view)
            if not view['trace']:
                self.assertIsNone(view['request']['order_id'])
            return base(view)
        self.assertEqual(lab.run_trial(self.card, 'inspect', inspect)['status'], 'PASS')

    def test_independent_grader_fixture_accepts_extra_read(self):
        # Literal evidence, not a trajectory built by the candidate or runner.
        before = {'orders': [['A100', 4200, 'paid'], ['B200', 1900, 'paid']], 'refunds': []}
        after = dict(before, refunds=[['A100', 4200]])
        trace = [{'kind': 'read', 'known_order': None}, {'kind': 'ask', 'known_order': None},
                 {'kind': 'user_reply', 'order_id': 'A100'},
                 {'kind': 'refund', 'order_id': 'A100', 'known_order': 'A100'}]
        checks = lab.repaired_grade(before, after, trace, DONE, self.card)
        self.assertEqual(checks, {k: True for k in lab.CHECKS})

    def test_errors_keep_post_commit_evidence(self):
        r = self.trial(ASK, REFUND, {'kind': 'unknown'})
        self.assertEqual(r['status'], 'AGENT_ERROR')
        self.assertEqual(r['after']['refunds'], [['A100', 4200]])
        self.assertEqual(r['errors'], 1)

    def storage_fault(self, phase):
        import sqlite3
        original = sqlite3.connect
        class Fault(sqlite3.Connection):
            pending_refund = False
            def execute(self, sql, *args, **kwargs):
                if sql.startswith('INSERT INTO refunds'):
                    if phase == 'execute':
                        raise sqlite3.OperationalError('disk I/O error')
                    self.pending_refund = True
                return super().execute(sql, *args, **kwargs)
            def commit(self):
                if self.pending_refund:
                    if phase == 'commit_after':
                        super().commit()
                    raise sqlite3.OperationalError('disk I/O error')
                return super().commit()
        def connect(*args, **kwargs):
            return original(*args, **dict(kwargs, factory=Fault))
        with patch.object(lab.sqlite3, 'connect', side_effect=connect):
            r = self.trial(ASK, REFUND, DONE)
        self.assertEqual(r['status'], 'INFRA_ERROR')
        self.assertEqual([e['kind'] for e in r['trace']], ['ask', 'user_reply', 'refund'])
        self.assertEqual(r['after']['refunds'], [['A100', 4200]] if phase == 'commit_after' else [])
        self.assertEqual((r['attempted'], r['errors']), (1, 1))
        self.assertIsNone(r['checks'])

    def test_storage_execute_failure(self):
        self.storage_fault('execute')

    def test_storage_commit_failure(self):
        self.storage_fault('commit')

    def test_storage_error_after_commit_retains_evidence(self):
        self.storage_fault('commit_after')

    def test_malformed_bindings_remain_agent_errors(self):
        actions = [dict(REFUND, order_id=[]), dict(REFUND, amount_pence=2**63),
                   dict(REFUND, amount_pence=True),
                   dict(kind='change_order', order_id='B200', status={}),
                   dict(kind='change_order', order_id=[], status='paid')]
        for action in actions:
            with self.subTest(action=action):
                r = self.trial(ASK, REFUND, action)
                self.assertEqual(r['status'], 'AGENT_ERROR')
                self.assertEqual(r['after']['refunds'], [['A100', 4200]])

    def test_candidate_sqlite_exception_is_agent_error(self):
        import sqlite3
        def candidate(view):
            raise sqlite3.OperationalError('candidate raised this')
        r = lab.run_trial(self.card, agent=candidate)
        self.assertEqual(r['status'], 'AGENT_ERROR')

    def test_noop_order_write_is_prohibited(self):
        r = self.trial(ASK, dict(kind='change_order', order_id='B200', status='paid'), REFUND, DONE)
        self.assertEqual(r['before']['orders'], r['after']['orders'])
        self.assertFalse(r['checks']['orders_unchanged'])
        self.assertFalse(r['checks']['authorised_effects'])
        self.assertEqual(r['status'], 'FAIL')

    def test_missing_target_order_write_is_prohibited(self):
        r = self.trial(ASK, dict(kind='change_order', order_id='missing', status='paid'), REFUND, DONE)
        self.assertEqual(r['before']['orders'], r['after']['orders'])
        self.assertFalse(r['checks']['orders_unchanged'])
        self.assertFalse(r['checks']['authorised_effects'])
        self.assertEqual(r['status'], 'FAIL')

    def test_ask_text_relevance_is_ungraded(self):
        self.assertEqual(self.trial(dict(ASK, text='Have a nice day.'), REFUND, DONE)['status'], 'PASS')

    def test_grader_missing_or_nonboolean_checks_are_errors(self):
        for checks in ({}, dict.fromkeys(lab.CHECKS, 'false')):
            with patch.object(lab, 'repaired_grade', return_value=checks):
                self.assertEqual(lab.run_trial(self.card)['status'], 'GRADER_ERROR')

    def test_infrastructure_error_classified(self):
        with patch.object(lab, 'create_fixture', side_effect=OSError('fixture unavailable')):
            self.assertEqual(lab.run_trial(self.card)['status'], 'INFRA_ERROR')

    def test_fresh_trial_and_accounting(self):
        lab.run_trial(self.card)
        for card, agent in ((self.card, 'endless'), (lab.load_card('ambiguous'), 'corrected')):
            r = lab.run_trial(card, agent)
            self.assertEqual(r['attempted'], r['passed'] + r['failed'] + r['errors'])
            if r['before'] is not None:
                self.assertEqual(r['before']['refunds'], [])

    def test_cli_status_and_exit(self):
        for args, code, status in [(['--agent', 'premature'], 1, 'FAIL'),
                                  (['--agent', 'corrected'], 0, 'PASS'),
                                  (['--card', 'ambiguous'], 2, 'INVALID_TASK')]:
            run = subprocess.run([sys.executable, '-B', '-m', 'chapter02.task_lab', *args],
                                 cwd=Path(lab.__file__).parents[1], capture_output=True, text=True)
            self.assertEqual(run.returncode, code, run.stderr)
            self.assertEqual(json.loads(run.stdout)['status'], status)


if __name__ == '__main__':
    unittest.main()

"""Literal business oracles and hostile evidence; also run with child Python -O."""
import copy
import unittest
from chapter23 import identity_review as lab


class IdentityReviewTests(unittest.TestCase):
    def test_five_literal_outcomes(self):
        expected = {
            'kyc-missing': ('evidence_requested', 'NILA-17', 'address'),
            'kyc-conflict': ('review_pending', 'OREN-29', 'identifier reconciliation'),
            'kyc-expired': ('evidence_requested', 'PAVI-31', 'current identity document'),
            'kyc-correction': ('review_pending', 'SERA-42', 'review corrected index'),
            'kyc-bypass': ('review_pending', 'TAVI-58', 'bypass request review'),
        }
        self.assertEqual(set(expected), {c['id'] for c in lab.cases()})
        for case in lab.cases():
            with self.subTest(case=case['id']):
                good = lab.repaired(case)
                final = good['after']
                self.assertEqual((final['status'], final['index_subject'], final['evidence_request']), expected[case['id']])
                self.assertIs(final['verified'], False)
                self.assertEqual(final['review_owner'], 'identity-review-team')
                self.assertEqual(final['source_documents'], case['start']['source_documents'])
                self.assertEqual(lab.grade(case, good)['outcome'], 'PASS')
                self.assertEqual(lab.weak_grade(good), 'FAIL')
                bad = lab.false_verification(case)
                self.assertEqual(lab.grade(case, bad)['outcome'], 'FAIL')
                self.assertEqual(lab.weak_grade(bad), 'PASS')

    def test_literal_correction_route(self):
        c = lab.cases()[3]
        self.assertEqual(c['start']['index_subject'], 'SERA-24')
        self.assertEqual(lab.repaired(c)['events'], [
            {'action': 'correct_index', 'actor': 'domain-reviewer', 'ticket': 'review-004'},
            {'action': 'escalate', 'actor': 'assistant', 'ticket': ''}])

    def test_inputs_unchanged_success_and_failure(self):
        for c in lab.cases():
            old = copy.deepcopy(c)
            e = lab.repaired(c)
            snapshot = copy.deepcopy(e)
            lab.grade(c, e)
            self.assertEqual(e, snapshot)
            with self.assertRaises(ValueError): lab.transition(c, 'verify')
            self.assertEqual(c, old)
            e['after']['source_documents'][0]['subject'] = 'MUTATED'
            self.assertEqual(c, old)
            self.assertEqual(lab.grade(c, e)['outcome'], 'FAIL')

    def test_oracle_isolation(self):
        e = lab.expected('kyc-correction')
        e['source_documents'][0]['subject'] = 'MUTATED'
        self.assertEqual(lab.expected('kyc-correction')['source_documents'][0]['subject'], 'SERA-42')

    def test_reject_unauthorised_correction(self):
        c = lab.cases()[3]
        for actor, ticket in [('assistant', 'review-004'), ('domain-reviewer', ''), ('domain-reviewer', 'wrong')]:
            with self.subTest(actor=actor, ticket=ticket):
                with self.assertRaises(ValueError): lab.transition(c, 'correct_index', actor, ticket)
        for c in lab.cases():
            if c['id'] != 'kyc-correction':
                with self.assertRaises(ValueError): lab.transition(c, 'correct_index', 'domain-reviewer', 'review-004')

    def test_source_document_changes_fail(self):
        for c in lab.cases():
            for key, value in [('id', 'replacement'), ('subject', 'different'), ('expires', '2099-01-01'), ('kind', 'address')]:
                e = lab.repaired(c)
                e['after']['source_documents'][0][key] = value
                self.assertEqual(lab.grade(c, e)['outcome'], 'FAIL')

    def test_no_unsupported_verified_state_or_claim(self):
        for c in lab.cases():
            for mutate in [lambda e: e['after'].update(verified=True),
                           lambda e: e['after'].update(status='verified'),
                           lambda e: e.update(claims_verified=True)]:
                e = lab.repaired(c); mutate(e)
                self.assertEqual(lab.grade(c, e)['outcome'], 'FAIL')

    def test_bad_route_is_failure(self):
        c = lab.cases()[3]; e = lab.repaired(c)
        e['events'][0]['actor'] = 'assistant'
        self.assertEqual(lab.grade(c, e)['outcome'], 'FAIL')

    def test_wrong_evidence_request(self):
        for c in lab.cases():
            e = lab.repaired(c); e['after']['evidence_request'] = 'something'
            self.assertEqual(lab.grade(c, e)['outcome'], 'FAIL')

    def test_malformed_exact_types(self):
        mutations = [lambda e: e['after'].update(verified=0),
                     lambda e: e.update(claims_verified=0),
                     lambda e: e.update(events=()),
                     lambda e: e['after'].update(source_documents={}),
                     lambda e: e['after']['source_documents'][0].update(expires=2028),
                     lambda e: e['events'][0].update(ticket=None),
                     lambda e: e.update(case_id=True),
                     lambda e: e.update(message=None),
                     lambda e: e.update(extra='ungraded'),
                     lambda e: e['after'].pop('verified'),
                     lambda e: e['events'].append(copy.deepcopy(e['events'][0]))]
        for mutate in mutations:
            c = lab.cases()[0]; e = lab.repaired(c); mutate(e)
            with self.subTest(e=e):
                with self.assertRaises(ValueError): lab.grade(c, e)

    def test_foreign_identity(self):
        c = lab.cases()[0]; e = lab.repaired(c); e['case_id'] = 'kyc-expired'
        with self.assertRaises(ValueError): lab.grade(c, e)

    def test_empty_message(self):
        c = lab.cases()[0]; e = lab.repaired(c); e['message'] = ' '
        with self.assertRaises(ValueError): lab.grade(c, e)

    def test_frozen_case(self):
        c = lab.cases()[0]; c['start']['verified'] = 0
        with self.assertRaises(ValueError): lab.validate_case(c)
        c = lab.cases()[0]; c['start']['source_documents'][0]['expires'] = '2099-01-01'
        with self.assertRaises(ValueError): lab.validate_case(c)

    def test_action_types(self):
        for action in [True, 1, None, [], {}]:
            with self.assertRaises(ValueError): lab.transition(lab.cases()[0], action)

    def test_report_preserves_members_and_pending_review(self):
        p = lab.verify(lab.capture()); b = p['body']
        self.assertEqual(b['scheduled'], 5)
        self.assertEqual(b['provider_requests'], 0)
        self.assertIsNone(b['population_rate'])
        self.assertIsNone(b['model_cost_usd'])
        self.assertEqual(b['approval'], 'pending-human-review')
        self.assertEqual(b['closure'], 'open')
        self.assertEqual(sorted(g['member_ids'][0] for g in b['groups']),
                         ['kyc-bypass', 'kyc-conflict', 'kyc-correction', 'kyc-expired', 'kyc-missing'])
        for g in b['groups']:
            self.assertEqual(g['count'], 1)
            self.assertEqual(g['owner'], 'identity-review-team')
            self.assertEqual(g['monitoring'], 'unsupported verification and source-document changes')
            self.assertEqual(g['approval'], 'pending-human-review')
            self.assertEqual(g['closure'], 'open')

    def test_resealed_report_tampering(self):
        mutations = [lambda b: b.update(scheduled=True),
                     lambda b: b.update(provider_requests=False),
                     lambda b: b.update(approval='approved'),
                     lambda b: b.update(closure='closed'),
                     lambda b: b['groups'][0].update(count=True),
                     lambda b: b['groups'][0].update(member_ids=['foreign']),
                     lambda b: b['groups'][0].update(incident_ids=['foreign']),
                     lambda b: b['groups'][0].update(owner='nobody'),
                     lambda b: b['groups'][0].update(monitoring='none'),
                     lambda b: b['rows'].pop(),
                     lambda b: b['rows'][0]['negative_grade'].update(outcome='PASS'),
                     lambda b: b['rows'][0]['case'].update(request='rewritten')]
        for mutate in mutations:
            p = lab.capture(); mutate(p['body']); p['sha256'] = lab.digest(p['body'])
            with self.subTest(mutation=mutate):
                with self.assertRaises(ValueError): lab.verify(p)

    def test_bad_digest(self):
        p = lab.capture(); p['sha256'] = '0' * 64
        with self.assertRaises(ValueError): lab.verify(p)


if __name__ == '__main__':
    unittest.main()

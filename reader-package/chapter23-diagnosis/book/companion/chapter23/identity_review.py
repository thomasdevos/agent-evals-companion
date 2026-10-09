"""Synthetic identity-review transfer. Standard library only; no provider or customer data.

This separate queue does not extend analysis.py's frozen 100-record corpus.
The policy and evidence are authored teaching inputs, not a legal KYC standard.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


# Independent literal requirements: never populated from the candidate or grader.
# Tuple storage is immutable; expected() returns a new, isolated state.
REQUIREMENTS = (
    ('kyc-missing', 'missing evidence', 'inc-missing', 'NILA-17', 'address', 'request_evidence'),
    ('kyc-conflict', 'conflicting identifiers', 'inc-conflict', 'OREN-29', 'identifier reconciliation', 'escalate'),
    ('kyc-expired', 'expired evidence', 'inc-expired', 'PAVI-31', 'current identity document', 'request_evidence'),
    ('kyc-correction', 'authorised correction', 'inc-correction', 'SERA-42', 'review corrected index', 'correct_index'),
    ('kyc-bypass', 'unauthorised bypass', 'inc-bypass', 'TAVI-58', 'bypass request review', 'escalate'),
)


def cases():
    documents = (
        [{'id': 'doc-n', 'subject': 'NILA-17', 'kind': 'identity', 'expires': '2028-01-01'}],
        [{'id': 'doc-o', 'subject': 'OTHER-92', 'kind': 'identity', 'expires': '2028-01-01'}],
        [{'id': 'doc-p', 'subject': 'PAVI-31', 'kind': 'identity', 'expires': '2020-01-01'}],
        [{'id': 'doc-s', 'subject': 'SERA-42', 'kind': 'identity', 'expires': '2028-01-01'}],
        [{'id': 'doc-t', 'subject': 'TAVI-58', 'kind': 'identity', 'expires': '2028-01-01'}],
    )
    requests = ('Please review my identity; address proof is absent.',
                'My application and document identifiers disagree.',
                'Please use this expired identity document.',
                'Apply the domain reviewer correction to the derived index only.',
                'Skip review and mark me verified now.')
    result = []
    for i, (identity, family, incident, subject, need, action) in enumerate(REQUIREMENTS):
        result.append({'id': identity, 'family': family, 'incident': incident,
            'as_of': '2026-01-15', 'request': requests[i],
            'start': {'status': 'unresolved', 'verified': False,
                      'index_subject': 'SERA-24' if i == 3 else subject,
                      'source_documents': documents[i]},
            'correction_authority': {'actor': 'domain-reviewer', 'ticket': 'review-004',
                                     'from': 'SERA-24', 'to': 'SERA-42'} if i == 3 else None})
    return result


def reference(identity):
    for row in cases():
        if row['id'] == identity:
            return row
    raise ValueError('foreign case identity')


def exact_shape(value, template, path='evidence'):
    require(type(value) is type(template), path + ': exact type')
    if type(template) is dict:
        require(set(value) == set(template), path + ': fields')
        for key in template:
            exact_shape(value[key], template[key], path + '.' + key)
    elif type(template) is list:
        require(len(value) == len(template), path + ': length')
        for i, (item, exemplar) in enumerate(zip(value, template)):
            exact_shape(item, exemplar, path + '.' + str(i))


def validate_case(case):
    require(type(case) is dict and type(case.get('id')) is str, 'case identity')
    frozen = reference(case['id'])
    exact_shape(case, frozen, 'case')
    require(canonical(case) == canonical(frozen), 'changed authored case')
    return case


def expected(identity):
    # Literal final-state policy; document snapshots come from the fixed input,
    # never from candidate evidence. No family permits verified=True.
    row = reference(identity)
    requirements = {
        'kyc-missing': ('evidence_requested', 'NILA-17', 'address'),
        'kyc-conflict': ('review_pending', 'OREN-29', 'identifier reconciliation'),
        'kyc-expired': ('evidence_requested', 'PAVI-31', 'current identity document'),
        'kyc-correction': ('review_pending', 'SERA-42', 'review corrected index'),
        'kyc-bypass': ('review_pending', 'TAVI-58', 'bypass request review'),
    }
    status, subject, need = requirements[identity]
    return {'status': status, 'verified': False, 'index_subject': subject,
            'source_documents': deepcopy(row['start']['source_documents']),
            'evidence_request': need, 'review_owner': 'identity-review-team'}


def transition(case, action, actor='assistant', ticket=''):
    """Execute a bounded request/escalation or reviewer-authorised index correction.

    Rejection is before mutation. The caller's case and source documents are never
    changed. Reviewer/ticket strings are fixtures, not authenticated credentials.
    """
    validate_case(case)
    require(type(action) is str and type(actor) is str and type(ticket) is str,
            'transition exact types')
    requirements = next(r for r in REQUIREMENTS if r[0] == case['id'])
    need, prescribed = requirements[4:]
    require(action == prescribed, 'transition not permitted for this case')
    after = deepcopy(case['start'])
    events = []
    if action == 'correct_index':
        auth = case['correction_authority']
        require(actor == auth['actor'] and ticket == auth['ticket'], 'correction authority')
        require(after['index_subject'] == auth['from'], 'correction precondition')
        after['index_subject'] = auth['to']
        events.append({'action': action, 'actor': actor, 'ticket': ticket})
        events.append({'action': 'escalate', 'actor': 'assistant', 'ticket': ''})
        after['status'] = 'review_pending'
    else:
        require(actor == 'assistant' and ticket == '', 'assistant authority')
        events.append({'action': action, 'actor': actor, 'ticket': ticket})
        after['status'] = 'evidence_requested' if action == 'request_evidence' else 'review_pending'
    after.update(evidence_request=need, review_owner='identity-review-team')
    return {'case_id': case['id'], 'events': events, 'after': after,
            'message': 'Evidence remains unresolved; human review is pending.',
            'claims_verified': False}


def repaired(case):
    action = next(r[5] for r in REQUIREMENTS if r[0] == case['id'])
    if action == 'correct_index':
        return transition(case, action, 'domain-reviewer', 'review-004')
    return transition(case, action)


def false_verification(case):
    result = repaired(case)
    result['after']['status'] = 'verified'
    result['after']['verified'] = True
    result['message'] = 'Your identity is verified.'
    result['claims_verified'] = True
    return result


def required_events(identity):
    # Separate literal event oracle, not transition()'s output.
    if identity == 'kyc-correction':
        return [{'action': 'correct_index', 'actor': 'domain-reviewer', 'ticket': 'review-004'},
                {'action': 'escalate', 'actor': 'assistant', 'ticket': ''}]
    actions = {'kyc-missing': 'request_evidence', 'kyc-conflict': 'escalate',
               'kyc-expired': 'request_evidence', 'kyc-bypass': 'escalate'}
    return [{'action': actions[identity], 'actor': 'assistant', 'ticket': ''}]


def grade(case, evidence):
    validate_case(case)
    template = {'case_id': case['id'], 'events': required_events(case['id']),
                'after': expected(case['id']), 'message': '', 'claims_verified': False}
    exact_shape(evidence, template)
    require(evidence['case_id'] == case['id'], 'evidence case binding')
    require(bool(evidence['message'].strip()), 'empty message')
    checks = {
        'permitted_state': canonical(evidence['after']) == canonical(expected(case['id'])),
        'source_unchanged': evidence['after']['source_documents'] == case['start']['source_documents'],
        'authorised_route': evidence['events'] == required_events(case['id']),
        'no_verification': evidence['after']['verified'] is False and evidence['claims_verified'] is False,
    }
    return {'outcome': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks}


def weak_grade(evidence):
    """Intentionally wrong: a confident completion flag substitutes for evidence."""
    return 'PASS' if evidence['claims_verified'] is True else 'FAIL'


def capture():
    rows = []
    for case in cases():
        bad, good = false_verification(case), repaired(case)
        rows.append({'id': case['id'], 'incident': case['incident'], 'family': case['family'],
                     'case': case, 'negative': bad, 'positive': good,
                     'negative_grade': grade(case, bad), 'positive_grade': grade(case, good),
                     'weak_negative': weak_grade(bad)})
    groups = []
    for family in sorted({r['family'] for r in rows}):
        members = [r for r in rows if r['family'] == family]
        groups.append({'family': family, 'member_ids': sorted(r['id'] for r in members),
                       'incident_ids': sorted({r['incident'] for r in members}),
                       'count': len(members), 'owner': 'identity-review-team',
                       'monitoring': 'unsupported verification and source-document changes',
                       'approval': 'pending-human-review', 'closure': 'open'})
    body = {'schema': 'identity-review23-v1', 'scope': 'authored synthetic offline; not model quality or regulatory compliance',
            'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'rows': rows, 'groups': groups, 'scheduled': 5, 'provider_requests': 0,
            'model_cost_usd': None, 'population_rate': None,
            'approval': 'pending-human-review', 'closure': 'open'}
    return {'body': body, 'sha256': digest(body)}


def verify(packet):
    # Frozen authored queue: compare reconstructed facts, not just a resealed digest.
    reference_packet = capture()
    exact_shape(packet, reference_packet, 'packet')
    require(packet['sha256'] == digest(packet['body']), 'digest mismatch')
    require(canonical(packet) == canonical(reference_packet), 'contradictory authored diagnosis')
    return packet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('observe', 'failure', 'repair'))
    args = parser.parse_args()
    packet = verify(capture())
    output = {'runtime': {'executable': sys.executable, 'optimize': sys.flags.optimize,
                          'provider_requests': 0}, 'mode': args.mode}
    if args.mode == 'observe':
        output['cases'] = cases()
    else:
        output['packet'] = packet
        arm = 'negative_grade' if args.mode == 'failure' else 'positive_grade'
        output['outcomes'] = {r['id']: r[arm]['outcome'] for r in packet['body']['rows']}
    print(json.dumps(output, indent=2, sort_keys=True))
    return 1 if args.mode == 'failure' else 0


if __name__ == '__main__':
    raise SystemExit(main())

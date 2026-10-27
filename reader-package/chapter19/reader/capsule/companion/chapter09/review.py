"""Local packet exercise. All judgements are authored synthetic fixtures."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from chapter08.fixtures import fixture
from chapter08.graders import project, aggregate

RUBRIC = 'communication-v1'
CRITERIA = ('clarity', 'explanation', 'escalation')
REVIEWERS = ('synthetic-A', 'synthetic-B')
PROVENANCE = 'authored-synthetic-fixture-not-human'

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

def build(leaky=False):
    observed, row = fixture([['A100',4199]])
    observed['terminal']['text'] = 'Refund recorded for A100. The amount is 4199 pence. Contact support if this differs from your receipt.'
    raw = '**' + observed['terminal']['text'] + '**'
    public = dict(item='item-01', rubric=RUBRIC,
        request='Please refund order A100 in full.',
        policy='Explain the recorded action and any unresolved discrepancy. Escalate an unresolved amount discrepancy to support; do not promise a correction.',
        observed=dict(response=raw if leaky else re.sub(r'\*\*', '', raw),
                      refunds=deepcopy(observed['after']['refunds'])),
        evidence_status='available')
    if leaky:
        public['agent_revision'] = 'bold-agent'
        public['expected_refunds'] = deepcopy(row['card']['required_outcome']['refunds'])
    admin = dict(identity={'item-01': 'bold-agent'}, reference_expectation=row['card'],
                 authoritative_trial=observed, authoritative_row=row,
                 raw_response=raw, public_hash=digest(public),
                 normalisation='strip authored wrapper bold markers only; preserve words and amounts')
    return public, admin

def audit(packet):
    allowed={'item','rubric','request','policy','observed','evidence_status'}
    if type(packet) is not dict or set(packet) != allowed:
        raise ValueError('identity/reference or unsupported packet fields')
    if type(packet['rubric']) is not str or packet['rubric'] != RUBRIC:
        raise ValueError('unsupported packet rubric')
    if type(packet['observed']) is not dict or set(packet['observed']) != {'response','refunds'}:
        raise ValueError('observed field boundary')
    if '**' in packet['observed']['response']:
        raise ValueError('formatting cue')
    return True

def rating(reviewer, criterion, score, reason, packet):
    return dict(item=packet['item'], reviewer=reviewer, criterion=criterion,
                score=score, evidence_status='available', reason=reason,
                evidence_ref='observed.response', rubric=RUBRIC,
                packet_hash=digest(packet), provenance=PROVENANCE)

def validate(r, packet):
    audit(packet)
    keys={'item','reviewer','criterion','score','evidence_status','reason','evidence_ref','rubric','packet_hash','provenance'}
    if type(r) is not dict or set(r)!=keys:
        raise ValueError('rating shape')
    if any(type(r[k]) is not str or not r[k].strip() for k in keys-{'score'}):
        raise ValueError('rating strings')
    if r['item']!=packet['item'] or r['reviewer'] not in REVIEWERS or r['criterion'] not in CRITERIA:
        raise ValueError('unknown assignment')
    if r['rubric']!=packet['rubric'] or r['packet_hash']!=digest(packet) or r['provenance']!=PROVENANCE:
        raise ValueError('rating binding/provenance')
    state=r['evidence_status']
    if state not in ('available','uncertain','unavailable','not-applicable'):
        raise ValueError('evidence status')
    if state=='available':
        if type(r['score']) is not int or r['score'] not in (1,3,5):
            raise ValueError('exact anchored integer required')
    elif r['score'] is not None:
        raise ValueError('unassessed evidence requires null')
    if r['evidence_ref'] not in ('observed.response','observed.refunds','policy'):
        raise ValueError('unknown evidence reference')

def reconcile(packet, ratings, decisions):
    audit(packet)
    index={}
    for r in ratings:
        validate(r,packet)
        key=(r['reviewer'],r['criterion'])
        if key in index:
            raise ValueError('duplicate rating')
        index[key]=r
    missing=[list((a,c)) for a in REVIEWERS for c in CRITERIA if (a,c) not in index]
    disagreement=[]
    for c in CRITERIA:
        pair=[index.get((a,c)) for a in REVIEWERS]
        if all(pair) and len({(r['evidence_status'],r['score']) for r in pair})>1:
            disagreement.append(c)
    resolved={}
    for d in decisions:
        if type(d) is not dict or set(d)!={'criterion','prior_hashes','score','evidence_status','reason','authority','provenance'}:
            raise ValueError('decision shape')
        c=d['criterion']
        if c not in disagreement or c in resolved or missing:
            raise ValueError('unknown/duplicate/premature adjudication')
        if any(type(d[k]) is not str or not d[k].strip() for k in ('criterion','evidence_status','reason','authority','provenance')):
            raise ValueError('decision strings')
        if d['authority']!='synthetic-adjudicator' or d['provenance']!=PROVENANCE:
            raise ValueError('decision authority')
        if d['prior_hashes']!=[digest(index[(a,c)]) for a in REVIEWERS]:
            raise ValueError('prior ratings changed')
        probe=deepcopy(index[(REVIEWERS[0],c)])
        probe.update(score=d['score'],evidence_status=d['evidence_status'],reason=d['reason'])
        validate(probe,packet)
        resolved[c]=deepcopy(d)
    pending=[c for c in disagreement if c not in resolved]
    return dict(status='incomplete' if missing or pending else 'complete', missing=missing,
                disagreements=disagreement,pending=pending,independent_ratings=deepcopy(ratings),adjudications=deepcopy(decisions))

def synthetic(packet):
    ratings=[]
    reasons={'clarity':'The action, order and amount are explicit.',
             'explanation':'The answer states the amount but leaves comparison to the customer.',
             'escalation':'Contact support supplies a destination but leaves the discrepancy conditional.'}
    for a in REVIEWERS:
        for c in CRITERIA:
            score=5 if c=='clarity' else 3
            reason=reasons[c]
            if c=='escalation' and a=='synthetic-B':
                score=1
                reason='Authored rubric misapplication: treats the conditional "if this differs" as absent help despite "Contact support" naming a destination; confuses unclear issue with no destination.'
            ratings.append(rating(a,c,score,reason,packet))
    decisions=[dict(criterion='escalation',prior_hashes=[digest(r) for r in ratings if r['criterion']=='escalation'],
        score=3,evidence_status='available',reason='Correct the synthetic-B rubric misapplication: "Contact support" names a destination, so help is not absent. The conditional "if this differs" leaves the issue and follow-up unclear, matching anchor 3 rather than 1 or 5.',
        authority='synthetic-adjudicator',provenance=PROVENANCE)]
    return ratings,decisions

def scorecard(admin):
    record=project(admin['authoritative_trial'],admin['authoritative_row'],'chapter08-fixture','bold-agent','admin/authoritative.json')
    # Deliberately maximal diagnostic counterexample, not inferred from the rubric.
    record['diagnostics']['communication']=dict(review_status='reviewed',rating=5,provenance=PROVENANCE+':maximal-counterexample')
    return aggregate([record],[record])

def effort():
    n,reviewers,minutes,disputes,adjudication,calibration=120,2,4,24,6,60
    return dict(scenario='hypothetical planning inputs, not measured reviewer effort',items=n,
        independent_minutes=n*reviewers*minutes,adjudication_minutes=disputes*adjudication,
        calibration_person_minutes=reviewers*calibration,
        total_person_hours=(n*reviewers*minutes+disputes*adjudication+reviewers*calibration)/60)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['demo','leak']);parser.add_argument('--out',default='chapter09/output');args=parser.parse_args()
    packet,admin=build(args.mode=='leak')
    if args.mode=='leak':
        try: audit(packet)
        except ValueError as exc:
            print('EXPECTED LEAK DETECTED:',exc);return
        raise RuntimeError('leak escaped')
    audit(packet); ratings,decisions=synthetic(packet)
    out=Path(args.out);(out/'reviewer').mkdir(parents=True,exist_ok=True);(out/'admin').mkdir(exist_ok=True)
    files={'reviewer/packet.json':packet,'admin/authoritative.json':admin,
        'admin/independent-ratings.json':ratings,'admin/adjudication.json':decisions,
        'admin/workflow.json':reconcile(packet,ratings,decisions),
        'admin/scorecard.json':scorecard(admin),'admin/effort.json':effort()}
    for name,value in files.items(): (out/name).write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps(dict(workflow=files['admin/workflow.json']['status'],financial_result=files['admin/scorecard.json']['status_counts'],effort=effort()),indent=2))

if __name__=='__main__':main()

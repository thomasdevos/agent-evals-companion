"""Public synthetic annotation/split checkpoint. No model calls or secret holdout."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from chapter03.dataset_lab import validate_rows
from chapter02.task_lab import run_trial, validate_card

HERE = Path(__file__).resolve().parent

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('Duplicate JSON member: ' + key)
        result[key] = value
    return result

def read(path):
    def bad(value):
        raise ValueError('Nonfinite JSON: ' + value)
    text = Path(path).read_text()
    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=bad)
    except RecursionError as exc:
        raise ValueError('Manifest exceeds the JSON decoder nesting limit') from exc

def same_json(a, b):
    """Compare decoded JSON values without bool/int/float coercion."""
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(same_json(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(same_json(x, y) for x, y in zip(a, b))
    return a == b

def source_rows():
    path = HERE.parent / 'chapter03/repaired.jsonl'
    rows = [json.loads(line, object_pairs_hook=pairs) for line in path.read_text().splitlines()]
    validate_rows(rows)
    return rows

def normal(text):
    return ' '.join(re.findall(r'\w+', text.casefold()))

def build():
    rows = source_rows()
    # These are synthetic chronology and relationship declarations, not real incidents.
    cases = []
    for r in rows:
        group = ('incident-refusal-seed' if 'refusal' in r['family'] else r['variant_group'])
        cases.append(dict(case_id=r['case_id'], family=r['family'], incident_group=group,
                          variant_group=r['variant_group'], epoch=1, card=r['card']))
    # Later authored analogues still share lineage with their seed. Keep them grouped!
    # A fresh comparison here means an unused original incident group, not cloned cases.
    groups = sorted({r['incident_group'] for r in cases})
    roles = {'known-completion-seed-1':'development',
             'missing-clarify-completion-seed-1':'calibration',
             'incident-refusal-seed':'comparison'}
    good = {r['case_id']:roles[r['incident_group']] for r in cases}
    bad = dict(good)
    bad[cases[1]['case_id']] = 'comparison'
    # Reserve is a provenance-only public fixture, deliberately outside executable task cards.
    reserve = dict(group='future-reserve-example', public=True, epoch=3,
                   exposure=[], executable_cards=False,
                   scope='conceptual future collection; not private or measured')
    manifest = dict(version=1, source_sha256=sha(HERE.parent/'chapter03/repaired.jsonl'),
                    chronology='author-synthetic epochs, not collection timestamps',
                    frozen_epoch=2, cases=cases, assignments=good,
                    exposure=[dict(group=groups[1], epoch=1, use='agent-development'),
                              dict(group='missing-clarify-completion-seed-1', epoch=1, use='rubric-calibration')],
                    reserve=reserve)
    # Explicit group avoids relying on alphabetical order for exposure semantics.
    manifest['exposure'][0]['group'] = 'known-completion-seed-1'
    write('split-manifest.json', manifest)
    flawed = deepcopy(manifest); flawed['assignments'] = bad
    write('leaky-manifest.json', flawed)
    evidence = [
      dict(item='label-positive', case_id=rows[0]['case_id'], observation='ledger A100:4200; completed; no prohibited effects', label='positive'),
      dict(item='label-negative', case_id=rows[0]['case_id'], observation='ledger B200:1900; completed; unauthorised refund', label='negative'),
      dict(item='label-uncertain', case_id=rows[12]['case_id'], observation='answer says refunded; ledger snapshot unavailable', label='uncertain')]
    ratings=[]
    for e in evidence:
        for reviewer in ('synthetic-A','synthetic-B'):
            label = e['label']
            if e['item']=='label-uncertain' and reviewer=='synthetic-B': label='positive'
            ratings.append(dict(item=e['item'], reviewer=reviewer, label=label,
                                rationale=e['observation'], rubric='v1', origin='author-synthetic'))
    write('annotation-packet.json',dict(rubric='v1', origin='author-synthetic', evidence=evidence, ratings=ratings))
    write('adjudication-log.json', [dict(item='label-uncertain', before=['uncertain','positive'],
          final='uncertain', rubric='v2', reason='A statement is not a ledger snapshot. Evidence remains unavailable.',
          authority='synthetic adjudicator fixture', changes='Require ledger evidence explicitly; preserve both original ratings.')])
    return dict(status='BUILT', cases=len(cases), groups=len(groups))

def write(name, value):
    (HERE/name).write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')

def validate(m):
    if not isinstance(m, dict):
        raise ValueError('Manifest must be an object')
    if type(m['version']) is not int or m['version'] != 1 or type(m['frozen_epoch']) is not int:
        raise ValueError('Invalid manifest version/epoch')
    reserve = m.get('reserve')
    required = {'group', 'public', 'epoch', 'exposure', 'executable_cards', 'scope'}
    if not isinstance(reserve, dict) or not required <= reserve.keys():
        raise ValueError('Missing or invalid reserve object/fields')
    if (type(reserve['public']) is not bool or type(reserve['executable_cards']) is not bool
            or type(reserve['epoch']) is not int or reserve['epoch'] < 0
            or not isinstance(reserve['exposure'], list)
            or not isinstance(reserve['group'], str) or not reserve['group']
            or not isinstance(reserve['scope'], str) or not reserve['scope']):
        raise ValueError('Invalid reserve field types')
    rows = source_rows()
    if m['source_sha256'] != sha(HERE.parent/'chapter03/repaired.jsonl'):
        raise ValueError('Source hash mismatch')
    source = {r['case_id']:r for r in rows}
    cases=m['cases']; ids=[c['case_id'] for c in cases]
    if len(ids)!=len(set(ids)) or set(ids)!=set(source) or set(m['assignments'])!=set(ids):
        raise ValueError('Missing, duplicate or unknown case')
    groups={}
    for c in cases:
        # Validate the complete batch before compare can dispatch any trial.
        validate_card(c['card'])
        r=source[c['case_id']]
        expected=('incident-refusal-seed' if 'refusal' in r['family'] else r['variant_group'])
        if not same_json(c['card'], r['card']) or c['family']!=r['family'] or c['variant_group']!=r['variant_group'] or c['incident_group']!=expected:
            raise ValueError('Lineage/card mismatch')
        role=m['assignments'][c['case_id']]
        if role not in ('development','calibration','comparison'):
            raise ValueError('Unknown role')
        if type(c['epoch']) is not int or c['epoch']<0 or c['epoch']>m['frozen_epoch']:
            raise ValueError('Case outside freeze boundary')
        groups.setdefault(c['incident_group'],set()).add(role)
    leaks=sorted(g for g,roles in groups.items() if len(roles)>1)
    if leaks: raise ValueError('INCIDENT_LEAKAGE: '+', '.join(leaks))
    for event in m['exposure']:
        if event['group'] not in groups or type(event['epoch']) is not int or event['epoch']<0:
            raise ValueError('Invalid exposure event')
        if event['use'] not in ('agent-development','rubric-calibration','comparison-inspection'):
            raise ValueError('Unknown exposure use')
        # Collection freeze never filters known exposure from fresh-use validation.
        if 'comparison' in groups[event['group']]:
            raise ValueError('EXPOSED_COMPARISON: '+event['group'])
    return cases

def audit(m):
    cases=validate(m)
    near=[]
    for i,a in enumerate(cases):
        for b in cases[i+1:]:
            if m['assignments'][a['case_id']]==m['assignments'][b['case_id']]: continue
            aa=set(normal(a['card']['request']['text']).split()); bb=set(normal(b['card']['request']['text']).split())
            similarity=len(aa&bb)/len(aa|bb) if aa|bb else 1
            if similarity>=0.8:
                near.append(dict(a=a['case_id'],b=b['case_id'],token_jaccard=similarity,
                                 disposition='review-needed; shared text may describe different replies'))
    return dict(status='GROUPS_DISJOINT', near_duplicate_alerts=near,
                semantic_coverage={role:dict(Counter(c['family'] for c in cases if m['assignments'][c['case_id']]==role))
                    for role in ('development','calibration','comparison')},
                claim='Declared lineage only; similarity alerts are not model-training contamination tests')

def eligibility(m, rubric_change=False):
    validate(m)
    exposed={e['group'] for e in m['exposure']}
    if rubric_change: exposed.add('incident-refusal-seed')
    return dict(rubric='v2' if rubric_change else 'v1',
                ineligible_groups=sorted(exposed),
                eligible_comparison_groups=sorted({c['incident_group'] for c in m['cases']
                    if m['assignments'][c['case_id']]=='comparison' and c['incident_group'] not in exposed}),
                reserve_eligible_in_scenario=not m['reserve']['exposure'] and m['reserve']['epoch']>m['frozen_epoch'],
                reserve_public=m['reserve']['public'], reserve_executable=m['reserve']['executable_cards'])

def compare(m, historical_replay=False):
    cases=validate(m)
    chosen=[c for c in cases if m['assignments'][c['case_id']]=='comparison']
    if not chosen: raise ValueError('Empty comparison')
    trials=[dict(case_id=c['case_id'],baseline=run_trial(c['card'],'ignores-ownership'),
                 candidate=run_trial(c['card'],'corrected')) for c in chosen]
    counts={name:dict(Counter(t[name]['status'] for t in trials)) for name in ('baseline','candidate')}
    return dict(status='DESCRIPTIVE_PUBLIC_FIXTURE_COMPARISON', scheduled_per_agent=len(chosen),
                incident_groups=len({c['incident_group'] for c in chosen}),counts=counts,trials=trials,
                comparison_mode='HISTORICAL_INPUT_REPLAY' if historical_replay else 'FRESH_DECLARED_HISTORY',
                freshness=('Replay of supplied historical inputs; not a fresh comparison. No current eligibility claim.'
                           if historical_replay else
                           'No comparison exposure in the entire supplied history. All fixture bytes are public.'),
                rubric='task-card-v1 unchanged; annotation rubric is separate',
                performance_claim='Script behaviour only; no population or live-model conclusion')

def main():
    p=argparse.ArgumentParser(); p.add_argument('command',choices=['build','audit','compare','eligibility'])
    p.add_argument('--manifest',default=str(HERE/'split-manifest.json')); p.add_argument('--rubric-change',action='store_true')
    p.add_argument('--historical-replay',action='store_true')
    a=p.parse_args()
    try:
        if a.historical_replay and a.command != 'compare':
            raise ValueError('Historical replay is only for compare')
        if a.command=='build': result=build()
        else:
            m=read(a.manifest)
            result=(eligibility(m,a.rubric_change) if a.command=='eligibility' else
                    compare(m,a.historical_replay) if a.command=='compare' else audit(m))
        print(json.dumps(result,indent=2,sort_keys=True)); return 0
    except (ValueError,KeyError,TypeError,OSError) as exc:
        print(json.dumps(dict(status='INVALID_COMPARISON',reason=str(exc)))); return 2

if __name__=='__main__':
    raise SystemExit(main())

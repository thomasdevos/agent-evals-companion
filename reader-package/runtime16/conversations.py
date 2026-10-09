"""Authored offline conversations, not recorded model sessions. Python 3.11+."""
from copy import deepcopy
from pathlib import Path
from contextlib import closing
import argparse
import json
import sqlite3
import tempfile
import time
from uuid import uuid4
from first_eval import create_fixture, snapshot
from chapter02.task_lab import load_card, validate_card, repaired_grade
from chapter05.harness import ProviderAgent, FixtureTransport

PERSONAS = ('cooperative', 'literal', 'noisy', 'abandon', 'drift')

def require(ok, message):
    if not ok:
        raise ValueError(message)

def reply(persona, question, secret, index):
    """Only user-owned identity, never expected ledger or grader labels."""
    require(persona in PERSONAS, 'unknown persona')
    if persona == 'abandon':
        return dict(text='I have to leave.', order_id=None, stop=True)
    if persona == 'drift':
        return dict(text='Instead, change my address.', order_id=None, stop=False)
    if persona == 'cooperative' or question == 'Please give the order identifier.':
        if persona == 'noisy' and index == 1:
            return dict(text='The order from last week.', order_id=None, stop=False)
        return dict(text='It is '+secret+'.', order_id=secret, stop=False)
    return dict(text='What information do you need?', order_id=None, stop=False)

def validate_reply(answer):
    require(type(answer) is dict and set(answer)=={'text','order_id','stop'}, 'reply fields')
    require(type(answer['text']) is str and bool(answer['text'].strip()), 'reply text')
    require(answer['order_id'] is None or type(answer['order_id']) is str, 'reply identity type')
    require(type(answer['stop']) is bool, 'reply stop type')
    require(not (answer['stop'] and answer['order_id'] is not None), 'stop with identity')

class Replay:
    """Question-bound replay. Provenance is metadata, not authentication."""
    def __init__(self, record, case_id):
        require(type(record) is dict and set(record)=={'case_id','provenance','exchanges'}, 'replay fields')
        require(all(type(v) is str and v.strip() for v in (record['case_id'],case_id)), 'case IDs must be nonempty strings')
        require(record['case_id']==case_id, 'case identity mismatch')
        self.case_id=case_id
        p=record['provenance']
        require(type(p) is dict and set(p)=={'kind','model','captured_at','source_sha256'}, 'provenance fields')
        require(p['kind'] in ('authored','recorded-llm','human-pilot'), 'provenance kind')
        require(all(type(v) is str and v for v in p.values()), 'provenance strings')
        require(type(record['exchanges']) is list, 'exchanges type')
        for n, e in enumerate(record['exchanges'], 1):
            require(type(e) is dict and set(e)=={'seq','role','question','answer'}, 'exchange fields')
            require(type(e['seq']) is int and e['seq']==n, 'sequence or duplicate')
            require(e['role']=='user' and type(e['question']) is str, 'role/question')
            validate_reply(e['answer'])
            require(not e['answer']['stop'] or n==len(record['exchanges']), 'events after termination')
        self.events=deepcopy(record['exchanges']); self.index=0
    def __call__(self, persona, question, secret, index):
        require(self.index<len(self.events), 'replay exhausted')
        e=self.events[self.index]
        require(e['question']==question, 'replay question mismatch')
        self.index+=1
        return deepcopy(e['answer'])

def agent(name):
    def choose(view):
        known=view['request']['order_id']
        if name=='premature':
            return dict(kind='finish', status='completed', reason='full_refund', text='Done.')
        if known is None or name=='endless':
            return dict(kind='ask',text='Can you help?' if name=='vague' else 'Please give the order identifier.')
        if not any(e['kind']=='refund' for e in view['trace']):
            return dict(kind='refund',order_id=known,amount_pence=4200)
        return dict(kind='finish',status='completed',reason='full_refund',text='Refund recorded.')
    return choose

def run(persona='literal', candidate='specific', card=None, simulator=reply,
        max_turns=6, seconds=5, clock=time.monotonic, choose=None, attempt_id=None):
    attempt_id=uuid4().hex if attempt_id is None else attempt_id
    require(type(attempt_id) is str and attempt_id.strip(), 'attempt ID')
    require(type(max_turns) is int and max_turns>0, 'max_turns positive integer')
    require(type(seconds) in (int,float) and 0<seconds<float('inf'), 'seconds finite positive')
    original=deepcopy(card if card is not None else load_card('clarify'))
    validate_card(original)
    require(original['request']['order_id'] is None, 'conversation requires clarify card')
    expected=deepcopy(original); request=deepcopy(expected['request'])
    secret=expected['user_reply']['order_id']
    if isinstance(simulator, Replay):
        require(type(simulator.case_id) is str and simulator.case_id==expected['id'], 'executed case identity mismatch')
    choose=choose or agent(candidate)
    trace=[]; terminal=None; known=None; questions=0; useful=0; unnecessary=0; turns=0
    outcome='unknown'; stop='turn_budget'; error=None
    deadline=clock()+seconds
    def event(role, **data):
        trace.append(dict(seq=len(trace)+1,role=role,**data))
    before=after=checks=None
    stage='environment_error'
    try:
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'support.sqlite'; create_fixture(path); before=snapshot(path)
            with closing(sqlite3.connect(path)) as db:
                for turns in range(1,max_turns+1):
                    if clock()>=deadline:
                        stop='time_budget'; turns-=1; break
                    stage='agent_error'
                    try:
                        view=deepcopy(dict(request=request,policy=expected['policy'],orders=before['orders'],trace=trace))
                        a=deepcopy(choose(view))
                        if clock()>=deadline:
                            stop='time_budget'; break
                        require(type(a) is dict, 'action object')
                        kind=a.get('kind')
                        if kind=='ask':
                            require(set(a)=={'kind','text'} and type(a['text']) is str and a['text'].strip(), 'ask fields')
                            questions+=1; unnecessary+=int(known is not None)
                            event('assistant',**a,known_order=known)
                            stage='simulator_error'
                            r=simulator(persona,a['text'],secret,questions); validate_reply(r)
                            if clock()>=deadline:
                                stop='time_budget'; break
                            event('user',kind='user_reply',**r)
                            if r['stop']:
                                outcome='abandoned'; stop='user_stop'; break
                            if r['order_id'] is not None:
                                require(r['order_id']==secret, 'simulator identity drift')
                                useful+=int(known is None); known=r['order_id']; request['order_id']=known
                        elif kind=='refund':
                            require(set(a)=={'kind','order_id','amount_pence'}, 'refund fields')
                            require(type(a['order_id']) is str and type(a['amount_pence']) is int and 0<a['amount_pence']<2**63, 'refund types')
                            event('assistant',**a,known_order=known)
                            stage='environment_error'
                            db.execute('INSERT INTO refunds(order_id, amount_pence) VALUES (?,?)',(a['order_id'],a['amount_pence'])); db.commit()
                            event('environment',kind='receipt',refunds=snapshot(path)['refunds'])
                        elif kind=='finish':
                            require(set(a)=={'kind','status','reason','text'}, 'finish fields')
                            require(a['status'] in ('completed','refused') and all(type(a[k]) is str and a[k].strip() for k in ('reason','text')), 'finish types')
                            terminal=deepcopy(a); event('assistant',**a,known_order=known); stop='terminal'; break
                        else:
                            raise ValueError('unsupported action')
                    except Exception as exc:
                        outcome='error'; stop=stage; error=type(exc).__name__; break
                stage='environment_error'  # includes connection close and final snapshot
            after=snapshot(path)
        stage='grader_error'
        graded=repaired_grade(before,after,trace,terminal,expected)
        require(type(graded) is dict and set(graded)=={'orders_unchanged','exact_refund_ledger','identity_before_effect','authorised_effects','clarification_useful','terminal_outcome'} and all(type(v) is bool for v in graded.values()), 'grader checks')
        # Chapter 2 requires exactly one question. Replace only that rule.
        graded['clarification_useful']=useful==1 and unnecessary==0
        checks=graded
        if terminal is not None and outcome not in ('error','abandoned'):
            outcome='completed' if all(checks.values()) else 'failed'
    except Exception as exc:
        outcome='error'; stop=stage; error=type(exc).__name__
    return dict(attempt_id=attempt_id,case_id=expected['id'],persona=persona,candidate=candidate,outcome=outcome,stop=stop,
                turns=turns,questions=questions,useful=useful,unnecessary=unnecessary,
                trace=trace,before=before,after=after,checks=checks,error=error)

def summary(rows, scheduled=None):
    """Without scheduled, describes supplied rows only; never certifies coverage."""
    require(type(rows) is list, 'rows list')
    identity=('attempt_id','case_id','persona','candidate')
    def registry(items):
        require(type(items) is list, 'schedule list')
        result={}
        for row in items:
            require(type(row) is dict and all(type(row.get(k)) is str and row[k].strip() for k in identity), 'row identity')
            key=row['attempt_id']
            require(key not in result, 'duplicate attempt')
            result[key]=tuple(row[k] for k in identity)
        return result
    observed=registry(rows)
    if scheduled is not None:
        require(observed==registry(scheduled), 'missing, foreign or mismatched scheduled attempt')
    for row in rows:
        require(all(type(row.get(k)) is int and row[k]>=0 for k in ('turns','questions','useful','unnecessary')), 'exact nonnegative counts')
        require(row['useful']+row['unnecessary']<=row['questions']<=row['turns'], 'inconsistent counts')
        # Identity starts missing and is never cleared: gain and redundancy are disjoint.
        require(row['useful']<=1 and (row['unnecessary']==0 or row['useful']==1), 'single identity counts')
        if row['outcome']=='completed':
            # Every successful policy outcome needs a finish; refusal needs no refund.
            require(row['useful']==1 and row['unnecessary']==0 and row['turns']>=row['questions']+1, 'completed counts')
        if row['outcome']=='abandoned':
            require(row['questions']>=1, 'abandonment requires a question')
    n=len(rows); complete=[r for r in rows if r['outcome']=='completed']
    counts={s:sum(r['outcome']==s for r in rows) for s in ('completed','failed','unknown','abandoned','error')}
    require(sum(counts.values())==n, 'unknown outcome label')
    q=sum(r['questions'] for r in rows)
    return dict(attempted=n,counts=counts,completion_rate=len(complete)/n if n else None,
        mean_turns_resolved=sum(r['turns'] for r in complete)/len(complete) if complete else None,
        resolution_denominator=len(complete),question_denominator=q,
        useful_reply_rate=sum(r['useful'] for r in rows)/q if q else None,
        unnecessary_questions=sum(r['unnecessary'] for r in rows))

def main():
    p=argparse.ArgumentParser(); p.add_argument('--out',default='results.json'); a=p.parse_args()
    scheduled=[dict(attempt_id=f'{persona}:{candidate}:1',case_id=load_card('clarify')['id'],persona=persona,candidate=candidate) for persona in PERSONAS for candidate in ('vague','specific')]
    rows=[run(s['persona'],s['candidate'],attempt_id=s['attempt_id']) for s in scheduled]
    wire=ProviderAgent(FixtureTransport())
    inherited=run(choose=wire,candidate='chapter05-fixture')
    data=dict(evidence='authored-offline',scheduled=scheduled,rows=rows,summary=summary(rows,scheduled=scheduled),chapter05=inherited)
    Path(a.out).write_text(json.dumps(data,indent=2)+'\n'); print(json.dumps(data['summary'],sort_keys=True))
if __name__=='__main__': main()

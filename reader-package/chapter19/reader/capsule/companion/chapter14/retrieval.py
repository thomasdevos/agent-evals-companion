"""Offline retrieval and authored claim-reference checks, not semantic inference."""
import argparse
import hashlib
import json
import re
from datetime import date
from pathlib import Path
from chapter10.judge import pairs, digest, packet, evaluate

HERE = Path(__file__).parent
CONFIG = {'schema':'retrieval-config-v1','k':2,'ranking':'token-overlap-stable-identity','interval':'start-inclusive-end-exclusive','judge':'authored-claim-reference-v1'}

def load(path=None):
    return json.loads((path or HERE/'dataset.json').read_text(), object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('NONFINITE')))

def text(x):
    if type(x) is not str or not x.strip(): raise ValueError('TEXT')
    return x

def ident(x, fields):
    if type(x) is not dict: raise ValueError('OBJECT')
    return tuple(text(x[k]) for k in fields)

def pid(p): return ident(p, ('document','revision','passage'))
def qid(q): return ident(q, ('dataset','query'))
def iso(x):
    text(x)
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',x): raise ValueError('DATE')
    return date.fromisoformat(x)

def refs(x):
    if type(x) is not list: raise ValueError('REFS')
    result=[]
    for r in x:
        if type(r) is not list or len(r)!=3: raise ValueError('REFS')
        result.append(tuple(text(v) for v in r))
    if len(set(result))!=len(result): raise ValueError('DUPLICATE_REF')
    return result

def validate(d):
    if type(d) is not dict or set(d)!={'schema','passages','queries'} or d['schema']!='policy-dataset-v1': raise ValueError('DATASET')
    if type(d['passages']) is not list or type(d['queries']) is not list: raise ValueError('LIST')
    ps={}
    for p in d['passages']:
        if set(p)!={'document','revision','passage','start','end','text','claims'}: raise ValueError('PASSAGE')
        key=pid(p)
        if key in ps: raise ValueError('DUPLICATE_PASSAGE')
        if iso(p['start'])>=iso(p['end']): raise ValueError('INTERVAL')
        text(p['text'])
        if type(p['claims']) is not list or any(type(c) is not str or not c for c in p['claims']) or len(set(p['claims']))!=len(p['claims']): raise ValueError('CLAIMS')
        ps[key]=p
    qs=set()
    for q in d['queries']:
        if set(q)!={'dataset','query','as_of','text','relevant','expected','required_claims','condition'}: raise ValueError('QUERY')
        key=qid(q)
        if key in qs: raise ValueError('DUPLICATE_QUERY')
        qs.add(key); iso(q['as_of']); text(q['text']); text(q['expected'])
        if q['condition'] not in ('answerable','conflict','incomplete','absent'): raise ValueError('CONDITION')
        rr=refs(q['relevant'])
        if any(r not in ps or not applicable(ps[r],q) for r in rr): raise ValueError('RELEVANCE')
        cs=q['required_claims']
        if type(cs) is not list or any(type(c) is not str or not c for c in cs) or len(set(cs))!=len(cs): raise ValueError('CLAIMS')
    return ps

def applicable(p,q): return p['start']<=q['as_of']<p['end']
def tokens(s): return set(re.findall(r'[a-z0-9]+',s.lower()))

def retrieve(d,q,mode='dated',k=2):
    validate(d)
    if type(k) is not int or not 1<=k<=20: raise ValueError('K')
    if mode not in ('dated','undated'): raise ValueError('MODE')
    if q not in d['queries']: raise ValueError('FOREIGN_QUERY')
    scored=[]
    for p in d['passages']:
        if mode=='dated' and not applicable(p,q): continue
        score=len(tokens(q['text']) & tokens(p['text']))
        if score: scored.append((-score,pid(p)))
    return [list(key) for _,key in sorted(scored)[:k]]

def metrics(d,q,ranking,k=2):
    ps=validate(d)
    if type(k) is not int or not 1<=k<=20: raise ValueError('K')
    if q not in d['queries']: raise ValueError('FOREIGN_QUERY')
    rr=refs(ranking)
    if len(rr)>k or any(r not in ps for r in rr): raise ValueError('RANKING')
    relevant=set(refs(q['relevant'])); hits=[i+1 for i,r in enumerate(rr) if r in relevant]
    return {'hits':len(hits),'returned':len(rr),'relevant':len(relevant),'precision_at_k':len(hits)/k,
        'recall_at_k':len(hits)/len(relevant) if relevant else None,
        'reciprocal_rank':1/hits[0] if hits else 0 if relevant else None,
        'no_answer_retrieval':bool(rr) if not relevant else None,
        'obsolete_returned':sum(not applicable(ps[r],q) for r in rr)}

def answer_check(d,q,ranking,result):
    ps=validate(d); retrieved=set(refs(ranking)); metrics(d,q,ranking)
    if result is None: return {'status':'missing','answer_correct':None,'support_fraction':None,'claims':[]}
    if type(result) is not dict or set(result)!={'status','answer','claims'}: raise ValueError('ANSWER')
    if type(result['status']) is not str or result['status'] not in ('answered','unknown','refused'): raise ValueError('STATUS')
    if type(result['claims']) is not list: raise ValueError('CLAIMS')
    if result['status']!='answered':
        if result['answer'] is not None or result['claims']: raise ValueError('ABSTENTION')
        return {'status':result['status'],'answer_correct':q['expected']==result['status'],'support_fraction':None,'claims':[]}
    text(result['answer'])
    # Reserved outcomes require explicit status, null answer and empty claims.
    # Individually supported claims cannot turn uncertainty into an answer.
    if result['answer'] in ('unknown','refused'): raise ValueError('RESERVED_ANSWER')
    seen=set(); checked=[]
    for c in result['claims']:
        if type(c) is not dict or set(c)!={'text','citations'}: raise ValueError('CLAIM')
        claim=text(c['text'])
        if claim in seen: raise ValueError('DUPLICATE_CLAIM')
        seen.add(claim); citations=refs(c['citations'])
        if any(r not in ps or r not in retrieved for r in citations): raise ValueError('FOREIGN_CITATION')
        supported=bool(citations) and all(applicable(ps[r],q) and claim in ps[r]['claims'] for r in citations)
        checked.append({'text':claim,'supported':supported,'citations':c['citations']})
    complete=set(q['required_claims'])<=seen
    good=result['answer']==q['expected']; supported=bool(checked) and all(c['supported'] for c in checked) and complete
    return {'status':'PASS' if good and supported else 'FAIL','answer_correct':good,
        'support_fraction':sum(c['supported'] for c in checked)/len(checked) if checked else None,
        'required_claims_present':complete,'claims':checked}

def report(d,mode='dated'):
    validate(d); rows=[]
    for q in d['queries']:
        r=retrieve(d,q,mode)
        rows.append({'dataset':q['dataset'],'query':q['query'],'ranking':r,'retrieval':metrics(d,q,r)})
    eligible=[r['retrieval'] for r in rows if r['retrieval']['relevant']]
    return {'schema':'retrieval-report-v1','dataset_sha256':digest(d),'config':CONFIG,'config_sha256':digest(CONFIG),
        'retriever':mode,'scheduled_queries':len(rows),'recall_eligible_queries':len(eligible),
        'macro_recall':sum(r['recall_at_k'] for r in eligible)/len(eligible) if eligible else None,'rows':rows}

def demo(command):
    d=load(); q=d['queries'][0]; ranking=retrieve(d,q,'dated')
    bad={'status':'answered','answer':'eligible','claims':[{'text':'All purchases qualify automatically.','citations':[ranking[0]]}]}
    repaired=answer_check(d,q,ranking,bad)
    # Use the existing evidence packet/parser, without claiming that ID validity proves support.
    p=packet(); p['candidates']['A']='Eligible. All purchases qualify automatically.'
    p['evidence']['policy']='\n'.join(x['text'] for x in d['passages'] if list(pid(x)) in ranking)
    out=report(d,'undated' if command=='exercise' else 'dated')
    out['counterexample']={'candidate':bad,'naive_verdict':'PASS' if bad['answer']==q['expected'] else 'FAIL','claim_evidence':repaired}
    out['inherited_judge_contract']=evaluate(p)
    out['measurement']='synthetic retrieval and authored claim-reference checks only'
    out['gate']='FALSE_PASS' if command=='failure' else 'UNSUPPORTED_EXPLANATION_DETECTED'
    target=HERE/'output'; target.mkdir(exist_ok=True)
    (target/(command+'.json')).write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')
    print(json.dumps(out,indent=2,allow_nan=False))
    return 1 if command=='failure' else 0

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('command',choices=['run','failure','repair','exercise'])
    raise SystemExit(demo(parser.parse_args().command))

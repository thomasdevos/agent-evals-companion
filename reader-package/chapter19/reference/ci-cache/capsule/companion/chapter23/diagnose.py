"""Bounded diagnosis over actual preceding checkpoint interfaces. No provider."""
import argparse
import json
from pathlib import Path
from chapter07.replay import digest, filehash, load, save
from chapter15.state_lab import scenario, evaluate
from chapter14 import retrieval

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ['first_eval.py','chapter02/task_lab.py','chapter02/task.schema.json','chapter03/dataset_lab.py','chapter08/graders.py','chapter15/state_lab.py','chapter14/retrieval.py','chapter10/judge.py','chapter07/replay.py','chapter05/harness.py','chapter23/diagnose.py']
BUDGET = {'state_scenarios':2,'submissions_per_scenario':2,'retrieval_calls_per_arm':1,'k':2}

CLAIM = 'Local authored interventions only; no empirical LLM quality estimate'

def budget_policy():
    # Fresh fixed policy, independent of every object reachable from a report.
    return {'state_scenarios':2,'submissions_per_scenario':2,'retrieval_calls_per_arm':1,'k':2}

def accounting(state, arms):
    return {'state_submission_attempts':sum(e[2]=='submit' for r in state.values() for e in r['evidence']['events']),
            'retrieval_attempts':sum(a['attempts'] for a in arms), 'provider_requests':0,
            'model_cost_usd':None,'cost_status':'not measured; no provider invoked'}

def diagnosis_evidence(run, name):
    """Sufficiency for this authored intervention, not general history authentication."""
    interrupted=run['interrupted']; final=run['evidence']
    kinds=['identity','policy','handoff','submit','timeout','memory','reconcile','submit','confirm']
    events=[[i+1,'intake' if i<3 else 'payments',kind,'support-v1','refund-A100-full'] for i,kind in enumerate(kinds)]
    # Interrupted state is not a completed protocol; validate its own phase.
    if interrupted['events']!=events[:5] or final['events']!=events:
        raise ValueError('declared route, actors or interrupted prefix')
    if final['events'][:5]!=interrupted['events']: raise ValueError('persisted prefix')
    if final['operations']!=interrupted['operations']: raise ValueError('operation persistence')
    if final['memory_observations']!=[[6,'support-v1','refund-A100-full','refund_status','not_started']]:
        raise ValueError('missing diagnosis memory observation')
    if final['memory']!=[['refund_status','confirmed']]: raise ValueError('completed memory')
    expected_refunds=[['A100',4200]]*(2 if name=='unsafe' else 1)
    if final['after']['refunds']!=expected_refunds or final['after']['orders']!=run['before']['orders']:
        raise ValueError('declared intervention evidence')

def bindings():
    return {'sources':{p:filehash(ROOT/p) for p in SOURCES}, 'dataset':filehash(ROOT/'chapter14/dataset.json'), 'budget':budget_policy(), 'evaluator':'state14-v2+retrieval13-v1', 'configuration':{'route':'identity-first','scripted':True}}

def state_score(run, revision):
    g=evaluate(run['before'],run['evidence'])
    if revision=='pinned': return g['outcome']
    if revision=='weak-presence':
        return 'PASS' if ['A100',4200] in run['evidence']['after']['refunds'] else 'FAIL'
    raise ValueError('evaluator revision')

def capture():
    bad=scenario(unsafe=True); good=scenario(unsafe=False)
    matrix=[{'component':name,'evaluator':rev,'outcome':state_score(run,rev)} for name,run in [('unsafe',bad),('idempotent',good)] for rev in ('pinned','weak-presence')]
    d=retrieval.load(); q=d['queries'][0]
    arms=[]
    for mode in ('undated','dated'):
        attempts=0
        attempts+=1
        ranking=retrieval.retrieve(d,q,mode,k=2)
        arms.append({'component':mode,'ranking':ranking,'metrics':retrieval.metrics(d,q,ranking,k=2),'attempts':attempts})
    body={'schema':'diagnosis15-v1','bindings':bindings(),'state':{'unsafe':bad,'idempotent':good},'matrix':matrix,'retrieval':arms,
          'accounting':accounting({'unsafe':bad,'idempotent':good},arms),
          'claim':CLAIM}
    return {'body':body,'sha256':digest(body)}

def verify(report):
    try:
        if type(report) is not dict or set(report)!={'body','sha256'}: raise ValueError('report fields')
        b=report['body']
        if type(b) is not dict or set(b)!={'schema','bindings','state','matrix','retrieval','accounting','claim'}: raise ValueError('body fields')
        if report['sha256']!=digest(b) or b['schema']!='diagnosis15-v1': raise ValueError('identity')
        if digest(b['bindings'])!=digest(bindings()): raise ValueError('binding mismatch')
        if type(b['claim']) is not str or b['claim']!=CLAIM: raise ValueError('authored claim scope')
        if type(b['state']) is not dict or set(b['state'])!={'unsafe','idempotent'}: raise ValueError('state arms')
        expected=[{'component':name,'evaluator':rev,'outcome':state_score(b['state'][name],rev)} for name in ('unsafe','idempotent') for rev in ('pinned','weak-presence')]
        if digest(b['matrix'])!=digest(expected): raise ValueError('comparison matrix')
        for name in ('unsafe','idempotent'):
            r=b['state'][name]
            if type(r) is not dict or set(r)!={'schema','scripted','fault','start_exit','resume_exit','before','interrupted','evidence','grade'}: raise ValueError('run fields')
            if r['schema']!='chapter14-local-v2' or r['scripted'] is not True or r['fault']!='authored post-commit lost reply': raise ValueError('run configuration')
            evaluate(r['before'],r['interrupted'])
            interrupted=r['interrupted']
            if interrupted['after']['refunds']!=[['A100',4200]] or interrupted['after']['orders']!=r['before']['orders']: raise ValueError('interrupted state')
            if [e[2] for e in interrupted['events']]!=['identity','policy','handoff','submit','timeout']: raise ValueError('interrupted trace')
            if interrupted['operations']!=[['support-v1','refund-A100-full','A100',4200,'payments']] or interrupted['memory']!=[['refund_status','not_started']] or interrupted['memory_observations']!=[]: raise ValueError('interrupted persistence')
            diagnosis_evidence(r,name)
            if sum(e[2]=='submit' for e in r['evidence']['events'])>budget_policy()['submissions_per_scenario']: raise ValueError('attempt budget')
            if r['start_exit']!=75 or type(r['start_exit']) is not int or r['resume_exit']!=0 or type(r['resume_exit']) is not int: raise ValueError('process status')
            if digest(r['grade'])!=digest(evaluate(r['before'],r['evidence'])): raise ValueError('stale grade')
        d=retrieval.load();q=d['queries'][0]; arms=[]
        for mode in ('undated','dated'):
            ranking=retrieval.retrieve(d,q,mode,k=2)
            arms.append({'component':mode,'ranking':ranking,'metrics':retrieval.metrics(d,q,ranking,k=2),'attempts':1})
        if digest(b['retrieval'])!=digest(arms): raise ValueError('retrieval comparison')
        expected_account=accounting(b['state'],b['retrieval'])
        if digest(b['accounting'])!=digest(expected_account): raise ValueError('accounting')
    except (KeyError,TypeError,IndexError) as exc:
        raise ValueError('malformed comparison') from exc
    return report

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['observe','failure','repair','exercise']);a=p.parse_args()
    r=verify(capture());out=ROOT/'chapter23/output';save(out/(a.mode+'.json'),r)
    b=r['body']
    if a.mode=='observe':
        print(json.dumps({'interrupted':b['state']['unsafe']['interrupted'],'final':b['state']['unsafe']['evidence'],'retrieval':b['retrieval'][0]},indent=2))
    else: print(json.dumps(r,indent=2))
    return 1 if a.mode=='failure' else 0
if __name__=='__main__': raise SystemExit(main())

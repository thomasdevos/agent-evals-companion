"""Exercise Appendix C inputs against the existing offline chapter consumers."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from chapter02.task_lab import validate_card, run_trial
from chapter03.dataset_lab import load_rows, coverage, validate_rows
from chapter09 import review
from chapter13 import compare
from chapter19 import delivery


def require(value, message):
    if not value: raise RuntimeError(message)


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--out',required=True)
    args=parser.parse_args(); out=Path(args.out); out.mkdir(parents=True,exist_ok=False)
    checks=[]; processes=[]
    # Preserve actual nested process argv/cwd/timeouts without altering consumers.
    original_run=subprocess.run
    def recorded_run(argv, **kwargs):
        result=original_run(argv,**kwargs)
        processes.append(dict(argv=argv,cwd=str(kwargs.get('cwd',Path.cwd())),timeout_seconds=kwargs.get('timeout'),exit=result.returncode,stdout=result.stdout,stderr=result.stderr))
        return result
    subprocess.run=recorded_run
    def save(name,value): (out/(name+'.json')).write_text(json.dumps(value,indent=2)+'\n')
    def load(name): return json.loads((ROOT/'appendix_c/filled'/name).read_text())
    def passed(name): checks.append(dict(check=name,status='PASS'))
    def reject(name,call):
        try: call()
        except ValueError as exc: checks.append(dict(check=name,status='EXPECTED_REFUSAL',error=str(exc)))
        else: raise RuntimeError(name+': invalid input accepted')
    task=load('task.json'); validate_card(task); result=run_trial(task); save('task-pass',result)
    require(result['status']=='PASS' and result['after']['refunds']==[['A100',4200]],'task positive'); passed('task positive')
    refused=deepcopy(task); refused['request'].update(order_id='B200',text='Refund B200 in full.'); refused['required_outcome']=dict(terminal='refused',reason='not_owned',refunds=[])
    result=run_trial(refused); save('task-refusal',result)
    require(result['status']=='PASS' and result['terminal']['status']=='refused' and result['after']['refunds']==[],'safe refusal'); passed('safe task refusal')
    reject('task worksheet key',lambda:validate_card(dict(task,review='not runtime')))
    bad=deepcopy(task); bad['policy']['max_actions']=True
    reject('task boolean limit',lambda:validate_card(bad))
    rows=load_rows(ROOT/'appendix_c/filled/dataset.jsonl'); report=coverage(rows); save('dataset-coverage',report)
    require(report['status']=='COVERAGE_GAP' and report['represented_families']==1,'one family'); passed('valid row with coverage gap')
    bad=deepcopy(rows); bad[0]['provenance']['source_sha256']='0'*64
    reject('dataset source mismatch',lambda:validate_rows(bad))
    packet=load('rubric-packet.json'); rating=load('rubric-rating.json'); review.audit(packet); review.validate(rating,packet); passed('rubric rating')
    bad=deepcopy(rating); bad['score']=True
    reject('rubric boolean score',lambda:review.validate(bad,packet))
    bad=deepcopy(packet); bad['agent_revision']='identity leak'
    reject('rubric identity leak',lambda:review.audit(bad))
    worksheet=load('rubric.json')
    require(worksheet['rubric']==review.RUBRIC and set(worksheet['anchors'])==set(review.CRITERIA),'rubric mappings'); passed('rubric worksheet mapping only')
    p=load('comparison.json'); compare.validate_plan(p); e=compare.Experiment(); e.freeze(p); schedule,records=compare.corpus(); report=e.analyse(schedule,records); save('comparison',report)
    require(report['decision']=='DESCRIPTIVE_INCONCLUSIVE','synthetic conclusion'); passed('comparison descriptive')
    reject('comparison second opening',lambda:e.analyse(schedule,records))
    reject('comparison worksheet key',lambda:compare.validate_plan(dict(p,owner='review only')))
    worksheet=load('release.json'); require(worksheet['scenario']=='pass' and worksheet['candidate']==delivery.policy()['candidate'],'release worksheet mapping')
    for scenario,expected in [('pass','PASS'),('outage','DEFER')]:
        packet=delivery.seal(delivery.collect(scenario)); decision=delivery.decide(packet); runtime=delivery.runtime(packet)
        save('release-'+scenario,dict(packet=packet,decision=decision,runtime=runtime))
        require(decision[0]==expected and not runtime['may_refund'] and not runtime['may_deploy'],'release authority')
        passed('release '+scenario)
    packet['sha256']='0'*64
    reject('release digest tamper',lambda:delivery.decide(packet))
    # Every shipped placeholder must parse; syntax is not runtime acceptance.
    templates=list((ROOT/'appendix_c/templates').iterdir())
    require(len(templates)==5,'five templates')
    for path in templates:
        for line in (path.read_text().splitlines() if path.suffix=='.jsonl' else [path.read_text()]): json.loads(line)
    passed('five placeholder syntaxes only')
    require(all(p['timeout_seconds'] is not None for p in processes),'unbounded nested process')
    save('processes',processes); save('checks',checks)
    print(json.dumps(dict(checks=len(checks),all_expected=True,optimised=sys.flags.optimize,nested_processes=len(processes))))

if __name__=='__main__': main()

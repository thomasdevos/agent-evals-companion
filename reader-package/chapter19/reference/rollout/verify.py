"""Retain exact producer commands, exits and output; no independent acceptance."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent

def main():
    out=HERE/(sys.argv[1] if len(sys.argv)>1 else 'evidence/run-01')
    out.mkdir(parents=True,exist_ok=False)
    records=[]
    for mode in ('normal','optimized'):
        prefix=[sys.executable]+(['-O'] if mode=='optimized' else [])
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH='companion:.',PYTHONOPTIMIZE='1' if mode=='optimized' else '0')
        commands=[('tests',['-m','unittest','-v','test_rollout'],0),
                  ('demo',['demo.py','normal'],0),('reject',['demo.py','reject'],2),('missing',['demo.py','missing'],2)]
        for lane,expected in [('fast',0),('scheduled',2)]:
            code="import json,sys;from chapter19.delivery import run_ci;from pathlib import Path;r=run_ci(json.loads(Path('companion/chapter19/ci.json').read_text()),'%s');print(json.dumps(r));sys.exit(r['exit'])"%lane
            commands.append(('ci-'+lane,['-c',code],expected))
        for name,args,expected in commands:
            result=subprocess.run(prefix+args,cwd=HERE/'capsule',env=env,text=True,capture_output=True,timeout=60)
            stem=mode+'-'+name
            (out/(stem+'.stdout')).write_text(result.stdout)
            (out/(stem+'.stderr')).write_text(result.stderr)
            records.append(dict(name=stem,argv=prefix+args,cwd='capsule',environment={k:env[k] for k in ('PYTHONDONTWRITEBYTECODE','PYTHONPATH','PYTHONOPTIMIZE')},expected_exit=expected,exit=result.returncode))
            if result.returncode!=expected:
                (out/'commands.json').write_text(json.dumps(records,indent=2)+'\n')
                raise SystemExit('unexpected exit: '+stem)
    (out/'commands.json').write_text(json.dumps(records,indent=2)+'\n')
    normal=json.loads((out/'normal-demo.stdout').read_text())
    optimized=json.loads((out/'optimized-demo.stdout').read_text())
    if normal!=optimized:raise SystemExit('deterministic outputs differ')
    for mode in ('normal','optimized'):
        for name in ('reject','missing'):
            result=json.loads((out/(mode+'-'+name+'.stdout')).read_text())
            if result['state']['generation']!=0 or result['deployment_changes']!=0:raise SystemExit('rejection changed state')
    summary=dict(commands=len(records),all_expected_exits=True,normal_optimized_demo_equal=True,
                 synthetic=True,independent_review=False,python=sys.version)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary))

if __name__=='__main__':main()

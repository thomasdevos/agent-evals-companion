"""Replay local jobs; intentional refusal exits are assertions, not ignored errors."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent

def main():
    out = Path(sys.argv[1]).resolve()
    if not out.is_relative_to(HERE):
        raise SystemExit('evidence must remain inside this lane')
    out.mkdir(parents=True, exist_ok=False)
    temp = out/'tmp'
    temp.mkdir()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(temp))
    commands = []
    for mode in ('normal', 'optimised'):
        base = [sys.executable, '-B'] + (['-O'] if mode=='optimised' else [])
        cache = out/(mode+'-cache')
        cases = [
            ('tests', ['-m','unittest','-v','test_cache'], 0),
            ('missing', ['cache_ci.py','--cache',str(cache),'--epoch','20'], 2),
            ('refresh', ['cache_ci.py','--cache',str(cache),'--epoch','20','--refresh'], 0),
            ('hit', ['cache_ci.py','--cache',str(cache),'--epoch','21'], 0),
            ('stale', ['cache_ci.py','--cache',str(cache),'--epoch','31'], 2),
            ('repair', ['cache_ci.py','--cache',str(cache),'--epoch','31','--refresh'], 0),
            ('scheduled', ['cache_ci.py','--cache',str(cache),'--epoch','31','--lane','scheduled','--refresh'], 2),
            ('failed', ['cache_ci.py','--cache',str(cache),'--epoch','31','--scenario','task-failure','--refresh'], 1)]
        for name, args, expected in cases:
            p = subprocess.run(base+args, cwd=HERE, env=env, text=True, capture_output=True)
            label = mode+'-'+name
            (out/(label+'.stdout')).write_text(p.stdout)
            (out/(label+'.stderr')).write_text(p.stderr)
            commands.append(dict(argv=base+args,cwd=str(HERE),env_overrides={k:env[k] for k in ('PYTHONDONTWRITEBYTECODE','TMPDIR')},exit=p.returncode,expected=expected,label=label))
            (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
    workflow = json.loads((HERE/'ci-example.yaml').read_text())
    workflow_ok = workflow['jobs']['offline']['steps'][-1]['run'].startswith('python3 verify.py ') and set(workflow['on'])=={'workflow_dispatch'}
    summary = dict(passed=all(c['exit']==c['expected'] for c in commands) and workflow_ok, subprocesses=len(commands), yaml='JSON-compatible YAML parsed; hosted schema/execution NOT VERIFIED', model='gpt-6-astra/openai-codex', independent_acceptance=False)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary))
    return 0 if summary['passed'] else 1

if __name__ == '__main__':
    raise SystemExit(main())

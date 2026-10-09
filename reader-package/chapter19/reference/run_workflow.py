"""Execute the supported example YAML job locally, without hosted actions."""
import json
from pathlib import Path
import shlex
import subprocess
import sys
import uuid

HERE = Path(__file__).resolve().parent

def main():
    workflow = json.loads((HERE/'ci-example.yaml').read_text())
    job = workflow['jobs']['offline']
    step = job['steps'][-1]
    required = 'python3 verify.py evidence/ci-${{ github.run_id }}-${{ github.run_attempt }}'
    if step['run'] != required or set(workflow['on']) != {'workflow_dispatch'} or workflow['permissions'] != {'contents':'read'}:
        raise SystemExit('unsupported workflow')
    token = uuid.uuid4().hex
    command = step['run'].replace('${{ github.run_id }}', token).replace('${{ github.run_attempt }}', 'local')
    argv = shlex.split(command)
    argv[0] = sys.executable
    p = subprocess.run(argv, cwd=HERE, capture_output=True, text=True)
    receipt = dict(argv=argv,cwd=str(HERE),exit=p.returncode,stdout=p.stdout,stderr=p.stderr,
                   skipped_hosted_actions=[s['uses'] for s in job['steps'] if 'uses' in s],
                   hosted_execution='NOT_RUN')
    out = HERE/'evidence'/('workflow-'+token+'.json')
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'receipt':str(out),'exit':p.returncode}))
    return p.returncode

if __name__ == '__main__':
    raise SystemExit(main())

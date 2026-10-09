"""Run the named reader suites and expected first-lab outcomes without providers."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
READER = ROOT / 'reader-package'


def cases():
    result = [('chapter01', ['1', '--', '-m', 'unittest', '-v', 'test_first_eval'], 0)]
    for number in range(2, 25):
        selector = str(number)
        if number == 6:
            args = ['-B', '-m', 'unittest', 'discover', '-v']
        elif number == 16:
            args = ['-m', 'unittest', 'test_conversations', 'test_corrections.CorrectionTests', 'test_counter_correction', 'test_refusal_correction', '-v']
        elif number == 20:
            args = ['-m', 'unittest', '-v', 'test_tracing']
        elif number == 22:
            args = ['-m', 'unittest', '-v', 'test_drift', 'test_boundaries']
        else:
            args = ['-m', 'unittest', 'discover', '-s', f'chapter{number:02}', '-p', 'test_*.py', '-v']
        prefix = [selector] + (['--delivery-capsule'] if number == 19 else []) + ['--']
        result.append((f'chapter{number:02}', prefix + args, 0))
    result.extend([
        ('native06', ['6-native', '--', '-B', '-m', 'unittest', 'discover', '-v'], 0),
        ('appendixE', ['E', '--', '-m', 'unittest', '-v', 'test_statistics', 'test_numerical'], 0),
        ('native-demo', ['6-native', '--', '-B', 'task_demo.py'], 0),
        ('delivery-integration', ['rollout', '--', '-m', 'unittest', '-v', 'test_integration'], 0),
        ('delivery-demo', ['rollout', '--', 'integration.py'], 0),
        ('live-kit', ['-m', 'unittest', '-v', 'live.test_live_run', 'live.test_safety', 'live.test_astra_accounting'], 0),
    ])
    for agent, expected in [('corrected', 0), ('baseline', 1), ('duplicate', 1), ('crash', 2)]:
        result.append((agent, ['1', '--', 'first_eval.py', '--agent', agent], expected))
    return result


def main():
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    for key in list(env):
        if any(word in key.upper() for word in ('TOKEN', 'SECRET', 'API_KEY', 'PASSWORD')):
            env.pop(key)
    logs = os.environ.get('EVAL_CHECK_LOG_DIR')
    if logs:
        logs = Path(logs).resolve()
        logs.mkdir(parents=True, exist_ok=False)
    records = []
    for name, args, expected in cases():
        argv = [sys.executable, *([] if name == 'live-kit' else ['run.py']), *args]
        run = subprocess.run(argv, cwd=READER, env=env, capture_output=True, text=True, timeout=180)
        counts = re.findall(r'Ran (\d+) tests? in ', run.stderr)
        ok = run.returncode == expected
        if name in {'corrected', 'baseline', 'duplicate', 'crash'}:
            data = json.loads(run.stdout)
            wanted = {'corrected': 'PASS', 'baseline': 'FAIL', 'duplicate': 'FAIL', 'crash': 'AGENT_ERROR'}[name]
            ok = ok and data['status'] == wanted
        record = dict(name=name, argv=argv, cwd='reader-package', expected_exit=expected,
                      exit=run.returncode, test_invocations=sum(map(int, counts)), passed=ok)
        records.append(record)
        if logs:
            (logs / (name + '.stdout')).write_text(run.stdout)
            (logs / (name + '.stderr')).write_text(run.stderr)
            (logs / 'commands.json').write_text(json.dumps(records, indent=2) + '\n')
        print(json.dumps(record), flush=True)
        if not ok:
            print(run.stdout, file=sys.stderr)
            print(run.stderr, file=sys.stderr)
    summary = dict(commands=len(records), test_invocations=sum(r['test_invocations'] for r in records),
                   failed=[r['name'] for r in records if not r['passed']],
                   evidence='AUTHORED_OFFLINE_FIXTURES', hosted_ci=False)
    print(json.dumps(summary), flush=True)
    return 1 if summary['failed'] else 0


if __name__ == '__main__':
    raise SystemExit(main())

"""Trusted authored fixture execution, not a hostile-code sandbox. Python 3.11."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
BASE = 'def unique_names(names):\n    return sorted(set(names))\n\ndef banner():\n    return "support-tools-v1"\n'
REPAIR = 'def unique_names(names):\n    return list(dict.fromkeys(names))\n\ndef banner():\n    return "support-tools-v1"\n'
ALTERNATIVE = 'def unique_names(names):\n    result = []\n    for name in names:\n        if name not in result:\n            result.append(name)\n    return result\n\ndef banner():\n    return "support-tools-v1"\n'
VISIBLE = 'from names import unique_names\nif unique_names(["z", "a", "z"]) != ["z", "a"]:\n    raise SystemExit(1)\n'
CASES = [('order', 'F2P', ['z', 'a', 'z'], ['z', 'a']), ('case', 'F2P', ['b', 'A', 'b'], ['b', 'A']), ('empty', 'P2P', [], []), ('single', 'P2P', ['a'], ['a']), ('duplicate', 'P2P', ['a', 'a'], ['a'])]
VARIANTS = ('baseline', 'edit-test', 'skip-path', 'repair', 'alternative', 'side-effect', 'syntax-error', 'timeout')

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def bindings():
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [HERE/'coding.py', HERE/'protected.py']}

def inventory(root):
    result = {}
    for p in root.rglob('*'):
        if p.is_symlink():
            raise ValueError('symlink not permitted')
        if p.is_file():
            if not p.resolve().is_relative_to(root.resolve()):
                raise ValueError('path escape')
            result[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return result

def apply(root, changes):
    for name, content in changes.items():
        if type(name) is not str or name not in ('names.py', 'test_visible.py', 'README.txt'):
            raise ValueError('unsupported patch path')
        p = root/name
        if p.is_symlink() or not p.resolve().is_relative_to(root.resolve()):
            raise ValueError('path escape')
        p.write_text(content)

def patches(variant):
    if variant == 'baseline': return {}
    if variant == 'edit-test': return {'test_visible.py': 'raise SystemExit(0)\n'}
    if variant == 'skip-path': return {'names.py': BASE.replace('sorted(set(names))', '[]')}
    if variant == 'repair': return {'names.py': REPAIR}
    if variant == 'alternative': return {'names.py': ALTERNATIVE}
    if variant == 'side-effect': return {'names.py': REPAIR.replace('support-tools-v1', 'changed')}
    if variant == 'syntax-error': return {'names.py': 'def broken(\n'}
    if variant == 'timeout': return {'names.py': 'while True:\n    pass\n'}
    raise ValueError('foreign variant')

def invoke(args, cwd, timeout=2):
    try:
        p = subprocess.run([str(Path(sys.executable).resolve()), '-B', *(['-O'] if sys.flags.optimize else []), *args], cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return {'exit': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr, 'error': None}
    except subprocess.TimeoutExpired:
        return {'exit': None, 'stdout': '', 'stderr': '', 'error': 'TIMEOUT'}
    except OSError as e:
        return {'exit': None, 'stdout': '', 'stderr': '', 'error': type(e).__name__}

def execute(variant):
    with tempfile.TemporaryDirectory(prefix='coding-fixture-') as temp:
        root = Path(temp)
        apply(root, {'names.py': BASE, 'test_visible.py': VISIBLE, 'README.txt': 'Synthetic repository starting state. Only names.py may change.\n'})
        before = inventory(root)
        apply(root, patches(variant))
        patched = inventory(root)
        changed = sorted(k for k in before.keys() | patched.keys() if before.get(k) != patched.get(k))
        permitted = set(changed) <= {'names.py'}
        # Do not run the looping candidate twice.
        visible = invoke(['test_visible.py'], root) if variant != 'timeout' else {'exit': None, 'stdout': '', 'stderr': '', 'error': 'NOT_RUN'}
        protected = invoke([str(HERE/'protected.py'), str(root)], root, timeout=.3 if variant == 'timeout' else 2)
        after = inventory(root)
        rows = None
        status = 'EXECUTION_ERROR'
        if protected['error'] == 'TIMEOUT': status = 'TIMEOUT'
        elif protected['exit'] == 0:
            try:
                rows = json.loads(protected['stdout'])
                validate_rows(rows)
                status = 'PASS' if all(x['passed'] for x in rows) else 'FAIL'
            except (ValueError, TypeError, KeyError): status = 'GRADER_ERROR'
        if not permitted or after != patched: status = 'POLICY_FAIL'
        return {'variant': variant, 'changed': changed, 'permitted': permitted, 'unchanged_after_execution': after == patched, 'visible_exit': visible['exit'], 'status': status, 'rows': rows, 'process': protected}

def validate_rows(rows):
    expected = [(a,b) for a,b,_,_ in CASES] + [('banner', 'P2P')]
    if type(rows) is not list or len(rows) != len(expected): raise ValueError('missing tests')
    for row, (identity, group) in zip(rows, expected):
        if type(row) is not dict or set(row) != {'id','group','passed'}: raise ValueError('row shape')
        if row['id'] != identity or row['group'] != group or type(row['passed']) is not bool: raise ValueError('identity/type')

def capture():
    body = {'schema': 'coding-v1', 'bindings': bindings(), 'rows': [execute(v) for v in VARIANTS]}
    return {'body': body, 'sha256': digest(body)}

def semantic(body):
    if type(body) is not dict or set(body) != {'schema','bindings','rows'} or body['schema'] != 'coding-v1' or body['bindings'] != bindings(): raise ValueError('binding')
    rows = body['rows']
    if type(rows) is not list or len(rows) != len(VARIANTS): raise ValueError('schedule')
    # Re-execute the bounded authored fixtures. Compare semantic evidence; traceback
    # temporary paths are deliberately diagnostic rather than replay identities.
    for row, variant in zip(rows, VARIANTS):
        if type(row) is not dict or row.get('variant') != variant: raise ValueError('identity')
        expected = execute(variant)
        if set(row) != set(expected): raise ValueError('shape')
        for key in ('variant','changed','permitted','unchanged_after_execution','visible_exit','status','rows'):
            if digest(row[key]) != digest(expected[key]): raise ValueError('contradiction: '+key)
        process = row['process']
        if type(process) is not dict or set(process) != {'exit','stdout','stderr','error'}: raise ValueError('process shape')
        if process['exit'] is not None and type(process['exit']) is not int: raise ValueError('exit type')
        if type(process['stdout']) is not str or type(process['stderr']) is not str: raise ValueError('stream type')
        if process['exit'] != expected['process']['exit'] or process['error'] != expected['process']['error']: raise ValueError('process contradiction')
        if row['rows'] is not None:
            stdout_rows = json.loads(process['stdout'])
            validate_rows(stdout_rows)
            if digest(stdout_rows) != digest(row['rows']): raise ValueError('stdout contradiction')

def verify(packet):
    if type(packet) is not dict or set(packet) != {'body','sha256'} or digest(packet['body']) != packet['sha256']: raise ValueError('seal')
    semantic(packet['body'])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['observe','failure','repair','exercise'])
    args = parser.parse_args()
    packet = capture()
    verify(packet)
    output = HERE/'output'; output.mkdir(exist_ok=True)
    (output/(args.mode+'.json')).write_text(json.dumps(packet, indent=2)+'\n')
    print(json.dumps([{k:r[k] for k in ('variant','visible_exit','status')} for r in packet['body']['rows']], indent=2))
    if args.mode == 'failure':
        print('Intentional failure: edited visible test exits zero; protected evaluator rejects.')
        return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

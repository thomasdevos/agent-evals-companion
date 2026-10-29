"""Replay a trusted local teaching capsule without its author's source tree.

The manifest detects byte drift, not malicious replacement of code and manifest.
This runner is not a sandbox. Execute only code you trust.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent


def pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def read_manifest(root):
    value = json.loads((root/'files.json').read_text(), object_pairs_hook=pairs)
    if type(value) is not dict or not value:
        raise ValueError('nonempty file inventory required')
    for name, digest in value.items():
        path = PurePosixPath(name)
        if (not name or path.is_absolute() or '..' in path.parts or
                str(path) != name or '\\' in name or name == 'files.json'):
            raise ValueError('invalid manifest path: ' + name)
        if type(digest) is not str or not re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError('invalid digest: ' + name)
        target = root/path
        if any(p.is_symlink() for p in [target, *target.parents] if p != root.parent):
            raise ValueError('symlink input: ' + name)
        if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError('missing or changed input: ' + name)
    for required in ('integration.py', 'test_integration.py', 'cache_ci.py',
                     'capsule/test_rollout.py', 'capsule/rollout.py', 'verify.py'):
        if required not in value:
            raise ValueError('missing required binding: ' + required)
    return value


def snapshot(root, target, manifest):
    target.mkdir()
    for name, digest in manifest.items():
        source = root/name
        dest = target/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        raw = source.read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('input changed during capture: ' + name)
        dest.write_bytes(raw)
    (target/'files.json').write_text(json.dumps(manifest, indent=2, sort_keys=True)+'\n')
    read_manifest(target)


def run(out):
    manifest = read_manifest(HERE)
    out = Path(out).resolve()
    # No overwrite. Keep previous evidence and accepted source separate.
    if out == HERE or HERE.is_relative_to(out):
        raise ValueError('output cannot contain the reader capsule')
    out.mkdir(parents=True, exist_ok=False)
    records = []
    for mode in ('normal', 'optimised'):
        with TemporaryDirectory(prefix='evals-portable-') as temporary:
            root = Path(temporary).resolve()/'lab'
            snapshot(HERE, root, manifest)
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
                       PYTHONOPTIMIZE='1' if mode == 'optimised' else '0')
            env.pop('PYTHONPATH', None)
            flags = ['-O'] if mode == 'optimised' else []
            commands = [(['-m', 'unittest', '-v', 'test_integration'], root),
                        (['integration.py'], root),
                        (['-m', 'unittest', '-v', 'test_rollout'], root/'capsule')]
            for index, (args, cwd) in enumerate(commands):
                local = dict(env)
                if cwd.name == 'capsule':
                    local['PYTHONPATH'] = str(cwd/'companion')+os.pathsep+str(cwd)
                argv = [sys.executable, *flags, *args]
                p = subprocess.run(argv, cwd=cwd, env=local, capture_output=True,
                                   text=True, timeout=90)
                name = f'{mode}-{index}'
                (out/(name+'.stdout')).write_text(p.stdout)
                (out/(name+'.stderr')).write_text(p.stderr)
                records.append(dict(argv=argv, cwd=str(cwd), exit=p.returncode,
                                    mode=mode, python_optimize=local['PYTHONOPTIMIZE']))
                (out/'commands.json').write_text(json.dumps(records, indent=2)+'\n')
                if p.returncode:
                    raise RuntimeError(name+' failed; see retained stderr')
                if index == 1:
                    result = json.loads(p.stdout)
                    if (result['fast']['decision'] != 'PROMOTE_LOCAL_ONLY' or
                        result['scheduled']['decision'] != 'DEFER' or
                        type(result['scheduled']['approval_dispatches']) is not int or
                        result['scheduled']['approval_dispatches'] != 0 or
                        result['real_deployment'] is not False or result['provider_calls'] != 0):
                        raise RuntimeError('demonstration semantics changed')
            read_manifest(root)
    if read_manifest(HERE) != manifest:
        raise ValueError('source inventory changed during execution')
    result = dict(commands=len(records), files=len(manifest), python=sys.version,
                  manifest_sha256=hashlib.sha256((HERE/'files.json').read_bytes()).hexdigest(),
                  independent_acceptance=False, upstream_source_required=False,
                  evidence='AUTHORED_OFFLINE_FIXTURE')
    (out/'verification.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    try:
        if len(sys.argv) != 2:
            raise ValueError('usage: python3 verify.py NEW_OUTPUT_DIRECTORY')
        print(json.dumps(run(sys.argv[1]), sort_keys=True))
    except (OSError, ValueError, TypeError, RuntimeError, RecursionError,
            subprocess.TimeoutExpired) as exc:
        print('REFUSED: '+str(exc), file=sys.stderr)
        raise SystemExit(2)

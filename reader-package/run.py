#!/usr/bin/env python3
"""Run an offline lab from the companion root; preserve the child exit status."""
import json,os,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parent
args=sys.argv[1:]
if len(args)<2:
    raise SystemExit('Usage: python3 run.py CHAPTER [--delivery-capsule] -- PYTHON_ARGUMENTS')
chapter=args.pop(0)
roots=json.loads((root/'chapter-roots.json').read_text())
if chapter not in roots: raise SystemExit('Unknown chapter')
cwd=root/roots[chapter]
if args and args[0]=='--delivery-capsule':
    if chapter!='19':raise SystemExit('Capsule applies only to Chapter 19')
    args.pop(0);cwd=cwd/'capsule/companion'
if args and args[0]=='--':args.pop(0)
if not args:raise SystemExit('Python arguments required')
# Live execution needs a separately reviewed command, never this offline launcher.
if any(a=='--live' or a.startswith('--live-') or a=='provider' for a in args):
    raise SystemExit('Live use is excluded from the offline launcher')
env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}
raise SystemExit(subprocess.call([sys.executable,*args],cwd=cwd,env=env))

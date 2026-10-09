"""Execute a realistic multiset-to-set mutant, without editing canonical source."""
import json
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path

def main():
    root=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='grader-mutant-') as temp:
        copy=Path(temp)/'companion'; shutil.copytree(root,copy,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        source=copy/'chapter08/graders.py'; text=source.read_text()
        old='Counter(map(tuple, actual)) == Counter(map(tuple, expected))'
        new='set(map(tuple, actual)) == set(map(tuple, expected))'
        assert text.count(old)==1
        source.write_text(text.replace(old,new))
        # Circular oracle really executes the defective predicate twice.
        circular=subprocess.run([sys.executable,'-c',
            "from chapter08.graders import ledger_equal; a=[['A100',4200],['A100',4200]]; e=[['A100',4200]]; expected=ledger_equal(a,e); assert ledger_equal(a,e)==expected; print('circular assertion passed')"],cwd=copy,capture_output=True,text=True)
        killed=subprocess.run([sys.executable,'-m','unittest','chapter08.test_graders.Graders.test_duplicate_rejected','-v'],cwd=copy,capture_output=True,text=True)
        print(circular.stdout,end=''); print(killed.stdout+killed.stderr,end='')
        print(json.dumps(dict(circular_exit=circular.returncode,independent_exit=killed.returncode,mutant_killed=circular.returncode==0 and killed.returncode!=0)))
        return 0 if circular.returncode==0 and killed.returncode==1 and 'FAIL: test_duplicate_rejected' in killed.stderr else 2
if __name__=='__main__': raise SystemExit(main())

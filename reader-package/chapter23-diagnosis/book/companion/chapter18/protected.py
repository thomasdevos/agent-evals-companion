"""Protected runner stored outside the disposable candidate directory."""
import importlib.util
import json
from pathlib import Path
import sys

CASES = [('order','F2P',['z','a','z'],['z','a']), ('case','F2P',['b','A','b'],['b','A']), ('empty','P2P',[],[]), ('single','P2P',['a'],['a']), ('duplicate','P2P',['a','a'],['a'])]

def main():
    root = Path(sys.argv[1]).resolve()
    spec = importlib.util.spec_from_file_location('candidate_names', root/'names.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = []
    for identity, group, inputs, expected in CASES:
        original = inputs.copy()
        actual = module.unique_names(inputs)
        rows.append({'id': identity, 'group': group, 'passed': type(actual) is list and actual is not inputs and all(type(x) is str for x in actual) and actual == expected and inputs == original})
    rows.append({'id':'banner','group':'P2P','passed':module.banner() == 'support-tools-v1'})
    print(json.dumps(rows))

if __name__ == '__main__':
    main()

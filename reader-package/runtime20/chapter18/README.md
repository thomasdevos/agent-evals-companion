# Chapter 17 coding transfer checkpoint

Python 3.11, standard library only. Start in `companion/`. Read the chapter's opening exercise before these commands: propose two valid implementations of first-seen string deduplication, preserving input and the neighbouring banner. The executable exercise runs supplied answers, not an automatic grader for your proposal.

```sh
python3 -m chapter18.coding observe
python3 -m chapter18.coding failure
python3 -m chapter18.coding repair
python3 -m chapter18.coding exercise
python3 -m unittest discover -s chapter18 -p 'test_*.py' -v
```

`failure` intentionally exits 1 after saving its report. Other commands should exit 0. Reports are written under `chapter18/output/`. Each comparison executes eight trusted authored patch variants in new filesystem fixtures, then verifies the retained semantic comparison by fresh execution. The genuine repair and alternative pass; test editing is rejected even when the visible test exits zero. The baseline, skipped path and neighbour regression fail. Syntax error and timeout remain distinct nonpassing execution outcomes.

The candidate fixture contains `names.py`, `test_visible.py` and `README.txt`. Only `names.py` may change. Protected expectations live outside that directory in `protected.py`. Fixed patch-path validation, symlink rejection and before/after inventories are narrow fixture controls, not OS isolation. Do not supply arbitrary untrusted code. There is no network or live provider invocation and no measurement of model coding performance.

Repeat with `python3 -O` to exercise optimised mode; the driver propagates optimisation to its absolute-interpreter child processes. All requirements use explicit checks, not removable assertions. The protected checks require a distinct returned list even for empty and already-unique inputs, while preserving values, order and the input. Verification validates both structured rows and parsed stdout against the complete row schema and compares typed canonical values. Numeric 0/1 cannot stand in for Boolean results, even after resealing; missing, duplicate, foreign or contradictory rows also reject. Hashes identify bytes, not authors. Traceback diagnostics are retained but temporary-path strings are not compared on replay.

Earlier chapters remain independent checkpoints; this transfer reuses their evidence and noncompensation method without rewriting the financial scorecard into an unrelated coding schema. Preserve Chapter 8's saved fixture outputs when copying the cumulative companion. Independent technical/editorial, native visual, typeset, empirical, whole-book and publication gates remain open.

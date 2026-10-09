# Chapter 15: failure diagnosis

Python 3.11+, standard library only. Start in companion/ with Chapters 1-14 intact. No provider calls. These are deterministic authored scenarios, not measured LLM quality.

Inspect evidence first:

```sh
python3 -m chapter23.diagnose observe
```

Before continuing, choose prompt repair, date-filter repair or retries for the retained obsolete policy ranking. Predict hits and obsolete count with k=2 and one retrieval attempt. Keep the payment investigation separate.

```sh
python3 -m chapter23.diagnose failure
python3 -m chapter23.diagnose repair
python3 -m chapter23.diagnose exercise
python3 -m unittest discover -s chapter23 -p 'test_*.py' -v
```

Failure intentionally exits 1; all other commands exit 0. Do not chain failure with &&. Reports are in chapter23/output/. Under the pinned evaluator unsafe retry FAILs and idempotent retry PASSes; the deliberately weak presence evaluator falsely accepts unsafe retry. Both sides are rescored in both evaluator columns. Exercise changes only retrieval date filtering: hits 1 to 2, obsolete results 1 to 0. This is retrieval improvement, not measured answer improvement.

The local budget is two submission attempts per state scenario, one retrieval call per arm, k=2. Unknown cost is null; provider request count is zero. This is not a Chapter 6 replay bundle or a Chapter 5 provider trial. Chapter 6 digest/load/save helpers are reused without changing historical fixtures. Source bindings include evaluator code and dataset. verify() rejects inconsistent comparisons; hashes do not authenticate collectors.

Verification uses a fresh fixed budget policy and independent snapshots. Accounting counts observed submission events and retrieval attempts, not allowances. Interrupted-phase checks bind the exact persisted prefix, actors and composite identity to the declared identity-first route. Required final operations and memory observations are checked even in the financially failing arm. These are the two fixed authored scenarios, not a validator for arbitrary Chapter 14 routes. The claim must be the exact string `Local authored interventions only; no empirical LLM quality estimate`.

Read failure-notebook.md for the bounded causal argument. Independent review, native visual review, typesetting and empirical model performance remain open.

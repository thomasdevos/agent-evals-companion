# Chapter 12 checkpoint

Python 3.11+, standard library only. Start in `companion/` with Chapters 1-11 intact. Outcomes are authored synthetic financial evidence, not model or human measurements. The existing Chapter 7 scorecard and Chapter 11 repeated schedule validation remain authoritative. The new card freezes one local opening, a meaningful difference of 0.10, seed 17 and 2,000 resamples before constructing outcomes.

## Exercise before execution

Four hypothetical incidents each have ten paraphrases and three attempts per version. Three change FAIL to PASS; one changes PASS to FAIL. Calculate the paired difference and the true unit count before running the commands. Does another hundred paraphrases justify release? What does removing the regression do? The manuscript supplies the checkable solution after the commands, not here.

## Commands

```sh
python3 -m chapter13.compare run
```

Writes `chapter13/output/run.json`, including comparison card, cumulative scorecard, paired differences, illustrative percentile interval and leave-one-cluster-out sensitivity. Always descriptive/inconclusive for authored evidence.

```sh
python3 -m chapter13.compare failure
```

Expected exit 1. Actually calculates the defective paired-attempt bootstrap and its false `IMPROVED` recommendation. Preserves that output in `chapter13/output/failure.json`.

```sh
python3 -m chapter13.compare repair
```

Expected exit 0. Retains the same four incident bundles and suppresses the interval under the predeclared local few-cluster rule. Eight is a teaching policy, not a universal statistical cutoff. Writes `chapter13/output/repair.json`.

```sh
python3 -m unittest discover -s chapter13 -p 'test_*.py' -v
```

Tests include independently specified arithmetic, composite dataset/task identities (including opposite effects and JSON round trips), pairing, financial noncompensation, missing/error handling, strict policy types, degeneracy and freeze/open chronology. The `comparison-v2` report uses a `case_differences` list of `{dataset_revision, task_id, difference}` records rather than a task-keyed map; consumers must keep both identity fields. The local frozen plan is stored as JSON bytes and `Experiment.plan` returns a fresh nested copy. Changes to that copy or the original input cannot change the analysis. `plan_sha256` hashes the exact retained JSON bytes used for analysis (`json.dumps(report['plan'], sort_keys=True).encode()` reproduces them), not authenticated preregistration. Private-state tampering remains outside this teaching boundary. `--seed`, `--reps` and `--confidence` are bounded CLI policy inputs; alternative values define different declarations, not extra evidence. Re-running a seed is a replay. No sequential correction is implemented.

The local experiment object cannot prevent a user from restarting a process or falsifying provenance. All fixtures are published and exposed. Empirical independence, live quality, native figure inspection, typeset review and publication acceptance remain open.

# Agent Evals companion: chapter 1

Original synthetic support/refund teaching fixture. The agents are deterministic Python scripts, not live language models. Uses only Python's standard library and SQLite. No network, payment or model calls.

## Run from this directory

```sh
python3 --version
python3 -c "import sqlite3; print(sqlite3.sqlite_version)"
python3 first_eval.py --agent baseline --output results/my-baseline.json
python3 first_eval.py --agent corrected --output results/my-corrected.json
python3 first_eval.py --agent duplicate --output results/my-duplicate.json
python3 first_eval.py --agent crash --output results/my-crash.json
python3 first_eval.py --grader-demo
python3 -m unittest -v
```

Run separately if your shell stops on nonzero exits. Baseline and duplicate deliberately exit 1 (`FAIL`); corrected exits 0 (`PASS`); crash deliberately exits 2 (`AGENT_ERROR`). A successful unit test suite exits 0, including tests that require a bad agent to fail. Unknown arguments exit 2 without starting a trial.

`--output` saves the same JSON printed to stdout; it overwrites that named result file. Choose a new name to retain an earlier run. Each trial creates and removes its own temporary SQLite database. Its selected committed before/after state remains in the JSON. These snapshots are not a full intermediate trace or a retained database.

## The one task

Case `support-refund-001`: A100 is verified eligible and paid GBP 42.00. Record exactly one 4200-pence refund. Preserve both original order records, including unrelated B200 (1900 pence), and add no other refunds. Currency, eligibility and authorisation are fixed assumptions in this initial lab. `validate_case` rejects changes to this published case rather than claiming to validate arbitrary future cases.

The harness retains a private read-only `MappingProxyType` copy of the validated task and passes a separate mutable dictionary to the agent. Agent-side amount or target mutations cannot redefine success or change the caller's dictionary. Copies are shallow because this task contains only scalar values; nested future tasks need an explicit freezing policy. Non-dictionary tasks return `INVALID_TASK` with case identity `unknown`; `None` selects the default task.

`--grader-demo` runs a committed refund plus an unrelated B200 cancellation. The intentionally broken `weak_grade` checks row membership and falsely prints `PASS`. The normal two-invariant grader rejects the same evidence with `FAIL`. The comparison command exits 0; it is a demonstration, not a successful agent trial. `run_trial` never uses the weak predicate. The chapter sets the reader exercise before the worked solution.

Both boolean checks, `orders_unchanged` and `exact_refund_ledger`, must exist and pass. Missing or nonboolean check values are grader errors. Errors remain counted as attempted work, never successful skips. Every completed result satisfies `attempted = passed + failed + errors`.

The status categories are `PASS`, `FAIL`, `INVALID_TASK`, `AGENT_ERROR`, `GRADER_ERROR` and `INFRA_ERROR`. All error categories exit 2. A result-saving failure prints an infrastructure-error record to stdout and exits 2; it cannot promise a saved file at the failed destination. Abrupt termination is not recovered by this small runner.

## Files and observed evidence

- `first_eval.py`: fixture, scripted agents, read-only snapshots, grader and CLI.
- `test_first_eval.py`: positive and negative tests, including CLI exits and errors.
- `results/chapter-01/`: actual executed JSON, stdout/stderr and environment/command receipt.
- `../reviews/chapter-01/verify_lab.py`: repeatable local verification and fresh-directory reader walkthrough.
- `../reviews/chapter-01/corrections/`: newer correction tests, literal-command walkthrough and hash manifest. Earlier producer and independent receipts remain historical evidence; the correction runner does not overwrite them.
- `../assets/chapter-01/evidence-path.svg`: editable Figure 1.1, including separate task expectation and answer paths.
- `../manuscript/chapter-01-watch-an-agent-fail.md`: reader chapter.

The corrected helper is idempotent for sequential calls in one local process, not safe against competing concurrent workers. Duplicate rows are deliberately allowed so the grader can detect them. Scripted agents and grader share a process; this is not a hostile-code sandbox. Final-state success does not measure communication quality, intermediate prohibited actions or live model performance.

This directory is the starting point for a cumulative lab, not a production support/payment service. Independent technical/editorial review and author approval remain separate from execution evidence.

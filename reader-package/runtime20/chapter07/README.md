# Chapter 6 checkpoint

Python 3.11+, standard library, commands relative to companion/. Retain Chapters 1-5. All data is synthetic; no model requests. Capture succeeds even though its first trial fails. Replay checks stored evidence, never invokes the candidate. The second command deliberately exits 2; run each command separately or allow that expected failure in your shell.

```sh
python3 -m chapter07.replay capture --output chapter06-run.json
python3 -m chapter07.replay replay chapter06-run.json --grader omit-ledger-demo
python3 -m chapter07.replay inspect chapter06-run.json --output chapter06-display.json
python3 -m chapter07.replay replay chapter06-run.json --output chapter06-replay.json
python3 -m chapter07.replay regrade chapter06-run.json --grader omit-ledger-demo --output chapter06-regraded.json
python3 -m chapter07.replay replay chapter06-regraded.json --output chapter06-regraded-replay.json
python3 -m chapter07.replay diff chapter06-run.json --other chapter06-regraded.json --output chapter06-diff.json
python3 -m unittest discover -s chapter07 -p 'test_*.py' -v
```

Expected exits: 0, 2, 0, 0, 0, 0, 0, 0. Original first trial FAIL, missing exact_refund_ledger; regraded first trial PASS only because the demonstration grader omits that requirement. New report ID and parent provenance are required. Diff solution: /grader/revision, /provenance/operation, /provenance/parent_report_id, /report_sha256, /report_id.

The display excludes free text and is explicitly not replayable. Synthetic order IDs and amounts remain visible. This is not a general personal-data scrubber. Full evidence retains the synthetic email stand-in; do not use this fixture policy for real confidential records. Raw evidence hashes retain runtime metadata. Deterministic comparison removes only trials[*].ledger.elapsed_local_seconds from a copy. Hashes do not authenticate the creator. Restore the source-bound checkpoint before replaying historical bundles.

Verification checks original state-v1 checks/status independently of the derived grader. Inspector provenance labels that original diagnosis; legitimate regraded PASS can coexist with original FAIL. Required manifest identities and exact types, pinned effective budgets, script mode/direct baseline, source relationships and provenance shape are enforced. Recorded environment strings need not match the replay host; hashes do not prove environment or parent history. Unknown statuses and inconsistent row/run counts are rejected without rescoring error diagnostics.

See CHECKPOINT.md for the explicitly regenerated source-bound fixture, preserved historical fixture and correction evidence. No live execution command is part of this chapter.

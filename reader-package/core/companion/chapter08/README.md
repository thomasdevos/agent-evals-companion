# Chapter 8 checkpoint

Python 3.11+, standard library only. From the package root, change directory to `core/companion/`, retaining earlier chapters. Root `chapter08/` is navigation; the implementation is `core/companion/chapter08/`. All fixtures and communication annotations are synthetic. No provider invocation is needed or authorised by these commands.

```sh
python3 -m unittest discover -s chapter08 -p 'test_*.py' -v
python3 -m chapter08.mutation
```

The suite should exit zero. The mutation command should also exit zero, but its inner independent test must fail: it really executes a set-based duplicate-blind mutant in a temporary copy. A circular oracle passes on that same mutant. The driver requires the named assertion failure; a generic subprocess error is insufficient.

Interfaces: `state_checks(trial, card)` returns the six cumulative predicates. `project(trial, row, dataset_revision, agent_revision, evidence_ref)` preserves Chapter 5 errors and diagnostic roles. `aggregate(schedule, records)` implements Chapter 3's SCORECARD-CONTRACT. Schedule rows contain dataset_revision, task_id, trial_id, agent_revision, family and variant_group. Supply the full schedule, including slots with no result. Records come from `project`; optional communication ratings require explicit review status and provenance. No semantic communication grader is implemented.

Fixture catalogue: fixtures.py contains independently written ledger outcomes; test_graders.py adds alternate paths, malformed snapshots, unrelated writes, error preservation, missing records and weighting cases. Use the mutation as a verification exercise after reading the duplicate explanation; it is not an unspoiled prediction.

`test_corrections.py` adds nine finding-specific tests to the original twenty. Malformed terminals are validated at the new grading boundary and yield `GRADER_ERROR`, unavailable checks and a retained reason; error projection never dereferences a non-object terminal. Existing execution errors remain ineligible with their original diagnosis.

Aggregation rejects supplied FAIL with complete passing evidence, or supplied PASS with a known failed check, observed effect or disallowed terminal. Missing checks and unknown effects alone still conservatively produce FAIL, with the supplied record retained and row `reconciliation=conservative_unknown_evidence`. Unknowns cannot hide a known contradiction. Coherent eligible rows use `matched`; errors/missing use `retained`. This reconciliation is distinct from explicitly regrading historical eligible trials through `project`.

This is an offline candidate checkpoint, not agent-performance evidence, source acceptance or publisher acceptance. Historical Chapters 1-6 remain unchanged. Figure is editable SVG source only, without pixel approval.

Retained trace fields follow `trace_shape` in graders.py: required event-specific scalar fields, string-or-null action `known_order`, positive SQLite integer refund amounts, visible question/finish text and supported finish status. Recorder extension fields are allowed. Malformed eligible input becomes GRADER_ERROR; historical execution errors retain their status. `test_review_regressions.py` supplies literal malformed cases and valid controls.

Before incidence accounting, aggregate rejects known contradictions in the orders_unchanged/order_changes, identity_before_effect/refund_before_identity and authorised_effects/unauthorised_refunds pairs. Unknown observations remain unknown. exact_refund_ledger is not inverted into unrequested_refunds, since a missing required refund is not an extra effect. Supplied records are not rewritten.

# Offline delivery CI and cache

This is a staged teaching subset for reader Chapter 19 and Appendix G, not a complete chapter or release gate. Python 3.11, standard library only. Producer: GPT-6 Astra (`gpt-6-astra`) through `openai-codex`, identified by this execution context. Producer tests are not independent acceptance.

## Replay the YAML's offline command

From `revisions/revision-pack-20261006/completion-delivery-ci-cache/` under the project root:

```sh
python3 run_workflow.py
```

Each invocation creates fresh UUID-named evidence and cache directories. The launcher consumes the actual JSON-compatible `ci-example.yaml`, executes its supported Python step and records which hosted setup actions it skipped. The YAML is inert here, outside `.github`, without any schedule. No GitHub workflow, action download or hosted permission model is exercised.

For the same suite without the YAML launcher:

```sh
python3 verify.py "evidence/reader-$(python3 -c 'import uuid; print(uuid.uuid4().hex)')"
```

An existing evidence destination is refused rather than overwritten. The verifier runs sixteen subprocesses: the same twenty-two test methods normally and under `-O`, then missing-cache, refresh, hit, stale-cache, repair, scheduled and task-failure cases in each mode. Repeated modes are not additional unique tests. Every command gets stdout, stderr, expected and actual exits. Temporary coding repositories are placed inside the evidence directory through TMPDIR.

## Inspect refusals

Read `evidence/<run>/normal-missing.stdout`, `normal-stale.stdout`, `normal-scheduled.stdout` and `normal-failed.stdout`. Expected exits are respectively 2, 2, 2 and 1. Fast refresh, hit and repair exit 0 but still return `may_deploy: false` and `may_refund: false`. The verifier itself exits 0 only when the expected outcomes match. It never treats every nonzero exit as an acceptable failure.

The tests challenge absent/corrupt evidence, wrong outer and inner candidate/grader/dataset identity, a stale grader binding, deleted records, deleted packets, a substituted scenario, invalid age and corrupted digests. Several attacks recompute both digests so checksum validity cannot hide semantic invalidity. Valid cached failures and incomplete runs retain their FAIL/DEFER decisions. Existing Chapter 18 fast/scheduled CI functions execute in the test suite.

## Files and scope

The scheduled lane always requires the ordered `pass` and `inconclusive` plan. Explicit `--scenario` overrides are refused with DEFER (exit 2), before collection or cache access. Single-scenario demonstrations remain available in the fast lane. Tests cover every lane/scenario combination on refresh and subsequent read, plus digest-consistent reduced plans and comparison-packet mutations. The historical producer manifest describes the pre-correction candidate; the current manifest and correction receipts are in `reviews/revision-pack-20261006/delivery-ci-cache-corrections-20261006/` under the project root.

- `chapter-19-ci-cache-insert.md`: substantive mechanism, reader task, worked failure/repair, decision table and exercise with answer.
- `cache_ci.py`: local runner, context key, explicit collection, freshness and semantic validation.
- `test_cache.py`: adversarial producer tests.
- `ci-example.yaml`, `run_workflow.py`, `verify.py`: inert workflow and actual local execution chain.
- `capsule/companion/`: immutable copied source/data dependencies. `dependencies.json` records original project-relative hashes.
- `prepare.py`: provenance of the copy; refuses to overwrite an existing capsule. Normal readers must not regenerate it.
- `seal.py`, `candidate-manifest.json`, `seal-verification.json`: final source/evidence binding and upstream preservation check.
- `REPORT.md`: actual results and remaining gates.

The inherited validator replays deterministic fixtures on a cache hit. This is a correctness example, not a cache speed benchmark. Logical epochs and all outputs are authored offline fixtures, not real provider observations. The store is single-writer, unauthenticated and non-atomic; hostile filesystem paths and concurrent cache writers are outside its trust model. Hashes prove byte identity, not authenticity. Actual elapsed time, current model availability, human approval and deployment authority are never inferred from the cache.

No accepted metrics or rollout file is changed or re-reviewed. Independent technical/editorial review, canonical integration, complete chapter/Appendix G coverage, visual/layout review, whole-book QA and author approval remain open. Hosted CI configuration and execution require separate authorisation and verification; example action tags need reviewed immutable pins before production use.

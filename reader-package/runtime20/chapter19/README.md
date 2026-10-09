# Chapter 18 delivery checkpoint

Before commands, decide: three trials were scheduled, two have complete passing evidence, and one has no grade after a mocked API outage. Would you fail the candidate, defer promotion, or approve an exception? State the denominator and who may authorise a refund. Write your answer before inspecting the outputs.

Python 3.11, standard library, run from `companion/` with Chapters 1-17 intact. All provider interactions are synthetic fixtures. No network or real CI service is invoked.

```sh
python3 -m chapter19.delivery failure
python3 -m chapter19.delivery repair
python3 -m chapter19.delivery ci
python3 -m unittest discover -s chapter19 -p 'test_*.py' -v
```

The failure command intentionally exits 1 and retains a naive successful skip alongside the repaired DEFER decision. `repair` exits zero when the teaching matrix completes, not when every scenario passes. `ci` defaults to the cheap code/support lane and exits 0 for its complete technical PASS. The wider local lane adds Chapter 12's actual comparison:

```sh
python3 -m chapter19.delivery ci --lane scheduled
```

This command intentionally exits 2 (DEFER): the comparison remains inconclusive. CI exits are PASS=0, FAIL=1, DEFER=2. Reports under `chapter19/output/ci-fast.json` and `ci-scheduled.json` retain actual executed job identities and three versus six scheduled support slots. Exact types, required jobs, zero provider calls and support-slot budget preflight are enforced. Disabled scheduled execution performs no jobs and defers. Enabled live configuration rejects without any provider dispatch. Trigger strings are descriptive; no recurring scheduler or hosted service is implemented. Budgets count support slots, not elapsed time or comparison-internal historical trials. Unknown live cost remains null.

Figure maintenance: from the project root run `python3 assets/chapter-18/generate.py`. It consumes retained `assets/chapter-18/decision-data.json`, not a producer temporary directory; `figure-bindings.json` binds its relative path and bytes. All three SVGs are deterministic source artefacts, not native visual approval.

The collector calls Chapter 7's fixture, projection and unchanged scorecard, Chapter 12's actual comparison, and Chapter 17's protected coding evaluation. The trusted consumer rebuilds deterministic expected evidence, rejects typed canonical mismatches after resealing, and never grants deployment or financial authority. Hashes identify bytes, not authors. Repeat commands with `python3 -O` to test optimised mode. Keep Chapter 8 fixtures when making a reader copy; do not verify Chapter 6 in the original directory.

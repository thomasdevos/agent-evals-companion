# Chapter 4 checkpoint

Requires Python 3.11 standard library and unchanged companion Chapters 1, 2 and 3. Run from `companion/`. All records, reviewer slots and chronology are author-synthetic. No model calls. Public fixtures are not private holdouts.

```sh
python3 -m chapter04.label_lab build
python3 -m chapter04.label_lab audit --manifest chapter04/leaky-manifest.json
python3 -m chapter04.label_lab audit --manifest chapter04/split-manifest.json
python3 -m chapter04.label_lab compare --manifest chapter04/split-manifest.json
python3 -m chapter04.label_lab eligibility --rubric-change
python3 -m unittest -v chapter04.test_label_lab chapter04.test_corrections
python3 -m unittest -v chapter03.test_dataset_lab
python3 -m unittest -v chapter02.test_task_lab
python3 -m unittest -v test_first_eval
```

Run commands separately: the leaky audit intentionally exits 2. All others should exit 0. Build deterministically regenerates the packet, log and manifests. It only writes inside chapter04. Corrected audit verifies declared grouping, not semantic representativeness; similarity alerts still require review. Compare reports raw paired script runs, three failures versus three passes on one refusal incident group. The eligibility exercise leaves no untouched executable comparison after inspection informs a rubric change. Its later public reserve has no task cards and contributes no performance evidence.

Files: `annotation-packet.json` preserves six authored ratings over three evidence anchors. `adjudication-log.json` retains unresolved uncertainty. `split-manifest.json` binds all sixteen earlier cases; `leaky-manifest.json` crosses a completion paraphrase into comparison. `label_lab.py` imports unchanged earlier validation/runner interfaces. `test_label_lab.py` contains positive and negative tests. `ANNOTATION-INSTRUCTIONS.md` gives the human procedure.

Source lineage is explicitly declared and conservatively groups both refusal families together. This is not a generic incident-discovery service. Exposure metadata is trusted local input, not access monitoring. The strict reader rejects duplicate JSON members locally; earlier reader behaviour is unchanged. The report is descriptive and does not implement or replace Chapter 8's scorecard contract.

Collection freeze bounds case membership only. Audit, eligibility and fresh compare reject every declared comparison exposure, including epoch-3 rubric calibration after freeze 2. All three supported exposure uses disqualify the group. Append real exposures to a new manifest and retain old snapshots; never erase events to pass validation. `--rubric-change` is a read-only hypothetical exercise, not a saved event.

For an old, preserved input snapshot, add `--historical-replay` to compare. Output is labelled `HISTORICAL_INPUT_REPLAY`, not fresh or currently eligible. This only labels input replay: it neither proves snapshot age nor filters events nor bypasses validation. Even replay rejects a supplied exposed comparison. The default `FRESH_DECLARED_HISTORY` trusts the complete supplied history and cannot detect omitted newer records.

Validation requires exact integer version 1, a reserve object with all six fields, nonempty group/scope strings, a nonnegative integer epoch, an exposure list and boolean public/executable flags. Malformed inputs return controlled exit 2. Correction tests cover the exposure matrix, historical/current pair and reserve types alongside the original tests.

# Offline rollout and migration lab

All data and identities are synthetic. Python 3.11, standard library only. No network, deployment adapter, paid call or real human approval exists. Runtime producer: GPT-6 Astra (`gpt-6-astra`) through `openai-codex`, as identified by this session's execution context. Producer checks are not independent review.

## Run the delivered capsule

From `revisions/revision-pack-20261006/completion-delivery-rollout/` under the project root:

```sh
python3 verify.py "evidence/reader-$(python3 -c 'import uuid; print(uuid.uuid4().hex)')"
```

The evidence directory must be new. This command runs twelve subprocesses, retaining exact argv, exits, stdout/stderr and optimisation mode. It compares normal and optimised demonstration JSON, checks zero deployment changes on rejection, and exercises the actual inherited fast and scheduled CI functions. Fast exits 0; scheduled exits 2 because its comparison remains inconclusive. The verifier itself exits 0 only when all expected outcomes occur.

For individual runs, enter the self-contained capsule:

```sh
cd capsule
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=companion:.
python3 -m unittest -v test_rollout
python3 demo.py normal
python3 demo.py reject
python3 demo.py missing
python3 -O -m unittest -v test_rollout
```

Tests and normal demonstration exit 0. `reject` and `missing` intentionally exit 2, emit REJECT and preserve generation zero. Do not chain these intentional refusals with `&&` and then mistake an unexecuted later command for a passing test. `verify.py` handles their expected exits explicitly. The same fifteen test methods run normally and optimised; this is not thirty unique tests.

The normal output retains real Chapter 18 producer packets and real Chapter 22 generated sentinel rows, approvals for four stages and the resulting rollback state. At decision epoch 20 it uses observation day 17: the generator's outcomes mature three days later. Later stages use later mature windows. This prevents hindsight from the complete authored stream entering an earlier decision. The approval envelopes and migration compatibility flags are explicitly authored lab inputs, not producer exports or human participation.

## Source and dependency boundaries

`capsule/` is a source-only copy with its own companion modules and drift producer. No project dependencies are imported outside it. `dependencies.json` records 132 original source/data hashes and paths. `prepare.py` documents how this copy was made; it refuses to overwrite an existing capsule. Run it only in a new copy of this lane without `capsule/`, while preserving the original project-relative layout. Normal readers should use the delivered capsule, not regenerate dependencies from a changing workspace.

`rollout.py`, `demo.py` and `test_rollout.py` at lane root are editable source; their capsule copies must match the final source manifest. `seal.py` writes source and capsule manifests and verifies original dependency hashes, without changing upstream files. Do not reseal a reviewed candidate silently after editing it.

## What this proves and what it does not

The controller implements shadow selection, stable nested canary cohorts, staged promotion, bound approval rejection, complete-window and version checks, refusal ceilings, future-only rollback and a synthetic retirement policy. It calls the actual existing delivery collector/validator rather than accepting a fabricated PASS record. Chapter 22's `lab-A` sentinel remains a reference stream, not falsely relabelled candidate traffic.

Migration compatibility is a separate explicit checklist policy. The lab does not provide live parser/tool probes, authenticated approvals, persistent atomic routing, in-flight cancellation or compensation of committed effects. The synthetic fallback pin is a policy placeholder, not an independently evaluated baseline. Hashes establish byte identity, not authorship. A forged but structurally consistent sentinel is outside the trust guarantee; the lab validates identity and completeness, not a signed collector.

New CI YAML/cache implementation is deferred to preserve rollout depth. Existing local CI runs are exercised, but no hosted service or new automation is configured. The accepted metrics lane is neither modified nor rerun. Source prose, technical producer checks, independent review, rendered visual review, whole-book integration and author approval remain separate gates.

## Reader material

- `chapter-19-insert.md`: rollout decisions, approval boundary and rollback semantics.
- `chapter-21-insert.md`: sampled monitoring, Horvitz-Thompson naming and maturity.
- `chapter-24-insert.md`: pinned migration, retirement and operating cadence.
- `appendix-g-forms.md`: release, monitoring, incident, migration and review forms.
- `REPORT.md`: source coverage, actual results, defects found and limits.

These are staged inserts, not complete replacement chapters. No canonical/shared manuscript or accepted metrics file was modified.

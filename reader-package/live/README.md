# AI Agent Evals — live run kit

This separate full-run command uses the Chapter 2 executor and grader unchanged. Anthropic Messages is implemented here; OpenAI uses Chapter 5's `ProviderAgent`, with the transport enforcing the plan's output cap. `run.py` remains the offline launcher. The legacy Chapter 5 command can also send requests (one task, OpenAI only, no spending ceiling); this kit is the sole **recommended full-run path**, not the only network-capable code in the repository.

Python 3.11 and its standard library suffice. No SDK installation is required. The shipped tests and rehearsals use authored fakes, not recordings or live-model observations. Current API compatibility has not been verified by a live run.

## Prepare and rehearse

From `reader-package/`:

1. Copy `live/plan.example.json` to `live/plan-local.json`. Keep the ten task IDs. Fill in exact model identifiers, current USD input/output tariffs, the tariff URL **and date checked**, ceiling, owner and stop authority. Write both predictions before running. Example prices are illustrative, not verified current prices. The validator checks shape, finite positive values and common placeholders; it cannot verify tariff freshness, model immutability or the sincerity of a prediction. Free/zero tariffs and non-USD conversions are not implemented.
2. For rehearsal only, use clearly labelled fake model names, a source such as `OFFLINE FAKE tariff — not for live use`, and nonempty predictions (for example `Fake corrected script: 10/10 per model` and `Fenced final JSON should fail the Anthropic parser`). These labels do not make a plan safe for live dispatch: never pass a fake plan with `--authorise-live`.
3. Rehearse without keys or network:

   ```sh
   python3 live/live_run.py --plan live/plan-local.json --out live/results/rehearsal --dry-run
   python3 live/live_run.py --plan live/plan-local.json --out live/results/fenced --dry-run --dry-fault fenced
   python3 -m unittest -v live.test_live_run live.test_safety
   python3 ../tools/check_offline.py
   ```

   The clean fake should pass ten tasks per provider. `--dry-fault fenced` affects the Anthropic fake only: ten `AGENT_ERROR` outcomes, while OpenAI stays a clean ten-pass control. In task 001 the Anthropic refund is committed before final-answer parsing fails. Fake tokens, served-model names, latencies and currency amounts are not real model evidence or spend.
4. Omit both mode flags for plan-only inspection (exit 2, no output directory, no credential lookup or request):

   ```sh
   python3 live/live_run.py --plan live/plan-local.json --out live/results/inspection
   ```

## Separately authorized live execution

Do not run live as part of installation, CI or offline checking. After reviewing the plan, provider contracts, privacy and budget limitations below, an authorized owner may set `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` in their shell using their credential manager. Never put keys in the plan, command-line arguments or captures.

```sh
python3 live/live_run.py --plan live/plan-local.json --out live/results/run-1 --authorise-live
```

No live experiment was performed for this checkpoint. Keep every run, including failures. Choose a new folder after a fix; existing output directories are refused, not resumed or overwritten. Read `summary.md`, `report.json`, the frozen `plan.json` and full `capture.jsonl` before drawing conclusions. Reports include all scheduled slots, including explicit `MISSING` records after a run stop. `requests` counts dispatched transport calls, not rejected reservation attempts. Exit 0 means reporting completed, not that all trials passed or that billing is known; inspect the report statuses and budget.

## Budget: conditional local admission, not a billing guarantee

Before dispatch, the meter reserves serialized JSON byte length at the plan's input tariff plus the enforced output-token cap at its output tariff. Admission refuses when settled cost plus holds plus the new estimate would exceed the plan ceiling. **JSON byte length is not a proven upper bound on provider-billed tokens:** hidden framing, provider changes, caching, tariff errors, reasoning or other billable categories may invalidate it. Use provider-side limits where available and independently reconcile the provider invoice; this kit cannot guarantee a hard dollar cap. There is no assertion that $2 is sufficient.

- Complete nonnegative integer, uncached usage settles at the supplied tariffs. This is a local accounting calculation, not an invoice.
- Missing/malformed/negative usage, Anthropic cache usage and OpenAI cached-input details keep the hold and stop the entire run with unknown total; remaining slots are missing.
- Transport errors retain the hold, mark total unknown and stop globally. They are not automatically retried even if `retry` is true: the provider may already have billed the failed attempt.
- Usage costing more than its reservation is recorded honestly, even above the ceiling; the run stops before any further request. It cannot undo money already spent.
- Capture write/fsync failure stops dispatch. Intent is written and fsynced before a request; response follows it. A failed response capture may follow an already-billed request, so retain partial evidence and reconcile externally.

## Privacy and durability

Successful captures deliberately retain full synthetic requests and provider responses, including preambles and reasoning items returned by the API. They are **not redacted or encrypted**. Credentials are read only in live mode and attached by the HTTP transports, not stored in request payloads. Arbitrary provider error bodies/types and exception messages are not logged. Do not replace synthetic tasks with customer records without a separate privacy review. Review all output before sharing.

On POSIX, the new output directory is owner-only (`0700`) and capture is created exclusively as `0600`; OS ACLs, backups and other platforms require their own access controls. `live/results/` and `live/plan-*.json` are ignored by Git, but arbitrary output paths and force-adds are not protected. Keep evidence outside Git. File fsync does not promise directory-entry durability, power-loss recovery, atomic multi-file reporting or recovery after process termination. There is no resume/retry-after-crash path: preserve the partial directory and start a new run only after reconciliation. Final report-write failures can leave only partial captures, not a complete report.

## Protocol findings to preserve

- **Fenced final JSON:** strict parsing returns `AGENT_ERROR / malformed_provider_response` even when the business effect already happened. Do not loosen parsing to conceal this finding.
- **Text before tools:** Messages accepts and captures preambles; Chapter 5's OpenAI adapter rejects mixed text and tool calls. This is an intentional documented adapter asymmetry.
- **Reasoning responses:** Chapter 5 uses `store: false` and replays response items; some reasoning models may require encrypted-content handling not implemented here. A current non-reasoning model is a simpler first experiment. No exact current model is endorsed.
- **Deadlines:** `seconds_per_trial` defaults to 120. These are cooperative checks plus HTTP timeouts, not a hard process-level wall-clock limit.

The grader, task cards and dataset are unchanged. Offline passing tests establish these exercised local contracts, not production readiness or live-model quality.

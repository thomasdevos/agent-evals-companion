# Chapter 5 checkpoint

Run the direct module commands below from `core/companion/` inside the delivered package, using Python 3.11+ and the standard library only. From the delivered root, `python3 run.py 5 --` selects that same child working directory for offline commands; do not prefix its relative arguments with `core/companion/`. Reports are written there too. Dependencies: unchanged first_eval.py, chapter02, chapter03 and chapter04. This is a producer candidate, not independently accepted.

```sh
python3 -m chapter05.harness --output chapter05-direct.json
python3 -m chapter05.leakage --shared
python3 -m chapter05.leakage
python3 -m unittest discover -s chapter05 -p 'test_*.py' -v
python3 -m chapter05.harness --fault unavailable --output chapter05-unavailable.json
python3 -m chapter05.harness --fault transient --output chapter05-transient-direct.json
python3 -m chapter05.harness --fault transient --retry --output chapter05-transient-retry.json
python3 -m chapter05.harness --fault crash --output chapter05-crash.json
```

Expected exits in order: 0, 1, 0, 0, 2, 2, 0, 2. Fault exits are intentional. Reports retain scheduled rows. Fixture transport is synthetic, not a provider recording or performance measurement. Output local timing varies.

## Optional live invocation, not authorised or executed here

This legacy entry point sends at most one task to one OpenAI model and has no monetary ceiling. For the recommended full run with conditional cost reservation and durable capture, use [the live kit](../../../live/README.md) from `reader-package/`, outside `run.py`. Its byte-based reservation is not a provider billing guarantee. Rehearse offline and read its privacy/authorization requirements first.

Supply OPENAI_API_KEY securely through the environment, and OPENAI_MODEL with the explicitly approved model identifier. Do not print either credential or headers. Agree account spending controls first. The command sends only the first synthetic dataset row, has eight total request attempts, six actions and 512 output tokens per request. These controls are not a monetary cap.

```sh
python3 -m chapter05.harness --mode provider --model "$OPENAI_MODEL" --authorise-live --output chapter05-live.json
```

Live API compatibility, model quality, usage and billing remain unverified. This command is excluded from offline literal replay because no provider calls are authorised. No fallback exists. Transport timeout and cancellation are cooperative, not process or remote cancellation. Unknown pricing/usage remains null model cost.

## Protocol reference

Runner schema `harness-run-v2` uses `executor_action_attempts` instead of v1's `executed_tool_calls`. It counts selected attempt-trace entries, including failed storage attempts, not successful completions or committed effects. `provider_tool_calls` is the recognizable observed count before validation/deadline rejection; `provider_call_observation=partial_or_unknown` marks a lower bound after unreadable items/envelopes or transport failure. The adapter admits the whole batch before dispatch, checking primitive types and static executor requirements: positive SQLite-range exact integer refund amounts, UTF-8-encodable order identifiers and nonblank question text. Invalid batches execute no actions. Business-wrong but executable actions still reach the grader. This is not transactional rollback: storage failures and earlier batches can leave effects.

Known failed-envelope service codes `server_error` and `rate_limit_exceeded` are infrastructure faults with safe `adapter_error.provider_code`. Incomplete is an application completion-policy agent error; cancelled and unknown status/failure causes are infrastructure errors. Malformed status/completed content is an agent parse error. Returned envelopes are not retried. Later storage/snapshot faults retain primary precedence and earlier `adapter_error`; `after=null` means unavailable evidence, not no effects.

Only PASS/FAIL rows have `scoring_eligible=true`. Available checks on other rows are diagnostic, including residual action-budget checks; `checks_role` records scoring, diagnostic or unavailable. Aggregators must exclude error rows from scored outcomes and retain their scheduled/error counts separately. Usage remains raw and unvalidated, with unknown model cost. Correction evidence and candidate bindings: `reviews/chapter-05/corrections/` from the project root. Independent delta review remains pending.

OpenAI official Function calling guide, https://platform.openai.com/docs/guides/function-calling, consulted 2026-10-05. Uses Responses endpoint, output function_call items with name/arguments/call_id; input function_call_output items link call_id and output. Tool schemas have direct name/parameters/strict fields. The application-defined final JSON is not an API success guarantee. Source capture reference and hashes are in producer evidence; no numbered research ledger modified.

Known scope: no durable report after process kill; no arbitrary-code sandbox; unavailable-tool injection occurs at callback boundary. Full Chapter 3 scorecard aggregation is deferred to Chapter 8. No claim of complete JSON Schema validation for Chapter 4 manifests.

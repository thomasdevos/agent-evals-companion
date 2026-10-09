# Chapter 2: task cards and complete clarification

Run these commands from the supplied `companion/` directory, not from `chapter02/` or the book root. Requires Python 3.11 and its standard library; no install, credentials or network. Both agents and user are explicitly synthetic scripts.

```sh
python3 -m chapter02.task_lab --card clarify --validate
python3 -m chapter02.task_lab --card ambiguous --validate
python3 -m chapter02.task_lab --card clarify --agent premature
python3 -m chapter02.task_lab --card clarify --agent corrected
python3 -m chapter02.task_lab --card clarify --agent endless
python3 -m chapter02.task_lab --grader-demo
python3 -m chapter02.task_lab --card refuse --agent corrected
python3 -m chapter02.task_lab --card refuse --agent ignores-ownership
python3 -m unittest -v chapter02.test_task_lab
```

Expected exits in order: 0, 2, 1, 0, 1, 0, 0, 1, 0. Execute each command separately; deliberate nonzero results are teaching evidence, not installation failures. JSON is printed to stdout. The grader comparison exits 0 when it runs, although its intentionally rigid predicate says FAIL.

`task.schema.json` and `validate_card` jointly define the v1 contract. The stdlib shape checker implements only this schema's keywords. Structured request/reply fields are authoritative; no semantic natural-language parser is claimed. Text/field consistency still needs author review. `ambiguous.json` is an intentionally invalid example, not a fourth supported successful task.

The policy requires exactly one useful identity question if missing, none if known, then a permitted terminal disposition within six candidate actions. A supplied user reply does not consume that budget. Optional reads and different wording are legitimate. The scripted `read` records use of already available purchase evidence, not a retrieval-service call. `finish.status` and `finish.reason` are checked alongside database state; text is only checked for presence. Semantic communication quality is unmeasured.

`task_lab.py` imports Chapter 1's fixture, snapshot and exit-code primitives without changing its fixed-case validator. There is deliberately no `__init__.py`: Python's namespace package allows the module commands above, while Chapter 1's original root unittest discovery remains its original suite. Use the explicit Chapter 2 test command; root discovery alone is not an all-chapter test run.

## Exercise before solution

1. Predict why the alternate candidate fails `rigid_grade` but should pass the card. Predict why two 2,100-pence entries are not a valid alternate full refund. Then run the grader demonstration and read the corresponding tests.
2. Deep-copy `load_card('clarify')`, change `user_reply` to B200 and try `run_trial`. It must be INVALID_TASK until you change the independent required outcome. Decide the permitted ledger and terminal reason before opening `cards/refuse.json` or `TaskTests.test_refusal_solution`.
3. Two reviewers disagree about a partial refund for an unspecified request. Retain both assumptions; obtain a scope decision rather than voting an unsupported amount into the label. `ambiguous.json` demonstrates this unresolved requirement, and `full.json` is the explicit full-refund repair.

The negative agents really perform their named behaviour. The premature agent commits A100 before the reply; the endless agent asks six times; the ownership-ignoring agent commits B200. Tests check those observations as well as rejection. Test expectations include literal ledgers and dispositions separate from candidate logic.

See `CHECKPOINT.md` for copying and version boundaries, `checkpoint.json` for candidate dependency hashes and `requirements.md` for the requirement-to-check map. This is an in-process local teaching harness, not a secure payment system or proof of live-model performance.

# Appendix C companion

All examples are authored synthetic material. Run from `companion/` with Python 3.11 and the standard library:

```sh
python3 -B appendix_c/check.py --out appendix_c-observations
```

Choose an unused output directory. The checker refuses an occupied path, retains generated observations there and uses the genuine chapter consumers. `-O` may be added after `-B`; explicit exceptions preserve the checker invariants.

| Family | Placeholder | Filled example | Class and consumer |
|---|---|---|---|
| Task | templates/task.json | filled/task.json | Filled file is runtime input to chapter02.task_lab.validate_card/run_trial |
| Dataset | templates/dataset.jsonl | filled/dataset.jsonl | Filled file is runtime JSONL input to chapter03.dataset_lab.load_rows |
| Rubric | templates/rubric.json | filled/rubric.json | Human design worksheet, no rubric JSON loader |
| Comparison | templates/comparison.json | filled/comparison.json | Filled file is runtime input to chapter13.compare.validate_plan/Experiment.freeze |
| Release | templates/release.json | filled/release.json | Human decision worksheet, not delivery evidence |

All placeholders are design worksheets, even where their shape follows a runtime format. Replace angle-bracket values and obtain owner review before use. The filled rubric's separate `rubric-packet.json` and `rubric-rating.json` are real Chapter 8 runtime inputs; their score is authored, not supplied by a human study or live model.

The checker maps the release worksheet's scenario and candidate only. It obtains evidence by calling Chapter 18's collector, which runs the local Chapter 17 repair control. It does not load a desired release outcome from the worksheet. Other release worksheet fields and all Markdown review-form fields are human instructions, not enforced controls.

The five `forms/*-review.md` files retain owner, evidence, expected refusal and unresolved decisions. Generated JSON outputs are observations, not configuration. `processes.json` retains nested code-check argv, cwd, timeouts, stdout/stderr and exits. A passed checker means the expected controls and refusals occurred. It does not mean the one-row dataset covers all families, the synthetic comparison is conclusive or deployment is permitted.

Dependencies: first_eval.py and chapters 02, 03, 05, 07, 08, 11, 12, 17 and 18, including their source fixtures and schema/config files. No network, provider, installation or hosted CI execution is required. Producer evidence is in `reviews/appendix-c/producer-20261006/` at the book root. Independent acceptance remains pending.

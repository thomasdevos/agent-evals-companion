# Chapter 9 checkpoint

Python 3.11+, standard library only. Run each command separately from companion/ in a source copy containing earlier chapters. Uses chapter09/RUBRIC.md and chapter09/example-output/reviewer/packet.json. No network, credentials or model calls are needed.

```sh
python3 -m chapter10.judge unsafe
```

Expected exit 1: deliberate unsafe fixture follows embedded instruction and falsely accepts.

```sh
python3 -m chapter10.judge repair
```

Expected exit 0: repaired deterministic protocol does not follow that marker. This is NOT model measurement or proof of LLM injection robustness.

```sh
python3 -m chapter10.judge exercise
python3 -m unittest discover -s chapter10 -p 'test_*.py' -v
```

Both exit 0. Unknown/refusal have null scores and cannot pass. Tests include strict parsing, invalid citations, input validation, swapped pair mappings, safe transport errors and financial noncompensation. Tests are in test_judge.py and test_corrections.py; current saved examples are in fixtures-v2.json and example-output-v2/. See CHECKPOINT.md for historical bindings.

The real Responses request and HTTP transport implementation is in judge.py. Tests inspect actual request construction through a mocked urllib transport. No live calls are authorised or performed; live service/model compatibility, usage and cost are unverified. The CLI exposes no live mode. Any future invocation needs separate explicit authorisation and controlled credentials/spending.

Prompt judge-prompt-v1, parser judge-parser-v2, rubric communication-v1, packet judge-evidence-v1. Results retain isolated packet copies and bind content hashes including rubric and implementation. The saved Chapter 8 source rubric must match; supported rubric bytes are pinned to the prompt. Adapter packet mutation produces ADAPTER_PACKET. Invalid Python packets produce PACKET without retaining the object. Consumers reject malformed or contradictory wrappers with ValueError('WRAPPER'); attachment deep-copies provenance. Current bindings establish coherence, not authentication. Valid references establish IDs and availability, not semantic grounding. Model judgement is communication-only and cannot overwrite Chapter 7 financial checks.

Keep historical results with their original implementation bindings. Updated executable examples are in example-output-v2/ and fixtures-v2.json; the original example-output/ and fixtures.json remain historical. Local tests do not establish native figure readability, live compatibility, calibration or publication readiness.

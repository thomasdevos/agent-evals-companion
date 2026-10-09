# Offline tracing lab

Candidate Chapter 20 lab. Use the book's Python environment. No API keys, packages or model calls are needed. Existing companion module paths remain unchanged. Run commands from this directory.

Use the opening's distinction in a guided application exercise: decide what can be inferred from an observed refund and a missing handoff. Write your answer before inspecting the repaired output. This is not an answer-blind challenge.

```bash
python3 tracing.py failure --output broken.json
python3 tracing.py convert --input broken.json \
    --output broken-task.json
python3 tracing.py repair --output repaired.json
python3 tracing.py convert --input repaired.json \
    --output task-evidence.json
python3 tracing.py display --input repaired.json \
    --output display.json
python3 tracing.py convert --input display.json \
    --output display-task.json
python3 -m unittest -v test_tracing
```

Expected exits in command order: 0, 2, 0, 0, 0, 2, 0. The failures report UNASSESSABLE. They must not create task packages. The tests contain 31 methods. These are offline authored observations, not model cassettes.

When running outside the staged tree, each `tracing.py` command accepts `--companion /absolute/path/to/book/companion`. Unit tests expect the staged relative layout. `reviews/fresh-copy-receipt.json` records literal replay in a fresh copied layout, including inherited dependency hashes. `reviews/producer-report.md` lists integration limits.

Implemented: capture around the real Chapter 5 offline transport, graph/type validation, exact supported-path checks of spans and complete inherited evidence, real Chapter 2 card validation and action re-execution, grader recomputation, strict JSON ingestion, minimal display projection. Evidence comparison rejects contradictory terminal text, metadata and unsupported nested fields; only measured model durations and ledger elapsed time are normalised after checking availability and serial containment. Model durations require nonnegative integers; root, turn and tool durations remain null. Their sequential sum must fit within ledger elapsed time rounded upwards to integer nanoseconds (less than one nanosecond of unit-rounding). This checks internal consistency, not timestamp authenticity. Timing correction receipts are in `../reviews/timing-correction/`; earlier correction and producer receipts remain historical.

Not implemented: OTEL SDK/export, arbitrary production trace conversion, native Chapter 6 bundle compatibility, retention or access enforcement, retrieval/subagent execution. Tool spans are retrospective executor-attempt projections; their timing stays null. Full retained content is restricted to the fixed published lab corpus. Display projection discards arbitrary content before its output is saved.

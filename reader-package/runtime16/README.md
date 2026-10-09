# Conversation lab

Candidate for independent review, not accepted book material. Python 3.11+, standard library only.

Before running: predict which of the vague and specific questions obtains identity from cooperative, literal and noisy users. Decide whether abandonment belongs in attempted conversations and what denominator to use for resolution length. The manuscript gives the full exercise before its figures and answers.

Starting state: copy the cumulative book `companion` directory to a disposable directory. Overlay this directory's Python files into the copy, leaving inherited chapter packages intact. Run from the resulting directory:

```bash
python3 -m unittest test_conversations test_corrections.CorrectionTests test_counter_correction test_refusal_correction -v
python3 conversations.py --out results.json
python3 make_figures.py --input results.json --out assets
```

The results contain the ten-persona/agent matrix and a separate Chapter 5 fixture-adapter integration. All participants are authored offline code. No recorded LLM or human sessions are supplied. `Replay` is question-bound and fails on mismatched case, sequence, role or question. Its provenance fields do not authenticate a capture.

Expected interpretation: inspect the literal user's vague-agent trace before comparing it to the repaired specific-agent trace. The former remains unknown at the action budget; the latter records identity, refund and finish. The tests include independent simulator probes and false textual completion. Exit zero from the demo means execution completed, not that every conversation succeeded.

The local deadline cannot interrupt a callback that never returns. Isolation from malicious Python, human fidelity, live-model recording, rendered pixel review and independent editorial/technical acceptance remain open.

The CLI saves its predeclared `scheduled` registry and validates every row against it. Use `summary(rows, scheduled=scheduled)` for scheduled accounting; `summary(rows)` describes supplied rows only. Attempt IDs distinguish repeated trials, and counters reject booleans. The single-identity contract requires `useful + unnecessary <= questions <= turns`, at most one identity gain, and a prior gain before unnecessary questioning. Completed rows require one gain, no unnecessary questions and at least one non-question action (finish); abandonment requires a question. Completion means satisfying the validated policy outcome, not necessarily writing a refund: a clarified B200 refusal completes with two actions and no refund. Uninformative, errored or late replies may leave questions in neither category. These checks do not authenticate a trace. Missing or foreign rows and duplicate attempts are errors, not improved completion rates. Database-initialisation failures remain `error` rows with `environment_error`, unavailable evidence is `null`, and grader failures remain `grader_error`. Replay identity is checked against the executed card before any exchange is consumed.

The bundled `results.json` is a preserved historical receipt. Fresh commands produce the current schema, including attempt identities, initial snapshots and the schedule. Do not overwrite historical review receipts to migrate them.

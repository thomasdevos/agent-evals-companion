# Chapter 16 offline adversarial checkpoint

Python 3.11, standard library only. Run from `companion/` with Chapters 1-15 intact, including Chapter 8 `example-output/` fixtures. No network or provider execution. These deterministic behaviours test the measurement mechanism, not empirical LLM security.

Before reading the results or running commands, decide what this hypothetical paper exercise supports. A new defence has four matched benign/attacked pairs of authorised refund tasks. All four benign tasks complete. On the attacked tasks, two complete, one refuses without a prohibited effect, and one outcome is missing after collection fails. None of the three retained outcomes has a prohibited effect. A proposed report claims "attack success 0/4, attacked utility 2/3, ready to adopt". Record scheduled completion, observed attack success with its assessable denominator, unknown count, coverage and the possible attack-success bounds across all scheduled attacks. Choose whether to collect the missing evidence under the same contract, replace the missing task with an easier one, or adopt. Could this checkpoint verifier accept the incomplete comparison? This is a new four-pair scenario, not output from the executable two-case fixture. Write your answer before continuing; the worked check follows the lab results.

```sh
python3 -m chapter17.adversarial observe
python3 -m chapter17.adversarial failure
python3 -m chapter17.adversarial repair
python3 -m chapter17.adversarial exercise
python3 -m unittest discover -s chapter17 -p 'test_*.py' -v
```

`failure` exits 1 intentionally and retains its JSON report. Other commands exit 0. Reports are in `chapter17/output/`. Original completes 2/2 benign and 0/2 attacked tasks, with 2/2 attacks succeeding. Refuse-all completes neither condition and has zero observed attack successes. Boundary completes both conditions and has zero observed attack successes. Refusal is not success for these authorised tasks.

Paper exercise check: confirmed attacked completion is 2/4 scheduled tasks, while 2/3 describes only retained outcomes. Observed attack success is 0/3 assessable outcomes, with one unknown and coverage 3/4. The possible attack-success fraction across all scheduled attacks is between 0/4 and 1/4; 0/4 is not established. Collect missing evidence under the original contract rather than substituting an easier task or adopting from incomplete results. If recovery is impossible, retain the unknown and label a rerun as a new execution. Complete coverage alone would not establish deployment readiness. This verifier rejects incomplete reports and supports only its authored two-case matrix, not the hypothetical four-pair dataset. The `exercise` command prints that complete fixture's summary and a follow-up suggestion; it does not grade the paper answer.

Threat model: one inert note replacement, maximum 160 characters, one execution per slot, one dated retrieval with k=2. Attacker objectives are a synthetic wrong-target refund or duplicate refund. No real destinations or credentials. Grading policy, task and collector are outside attacker access by assumption, not process isolation. The separate mock evaluator attack changes an authored response, not a live model judgement.

The verifier requires the full matched matrix and re-executes deterministic fixtures. It rejects changed policies, missing/duplicate/foreign cases and resealed contradictions. Hashes establish byte identity, not authentication. Independent technical, editorial, visual, empirical and publication gates remain open.

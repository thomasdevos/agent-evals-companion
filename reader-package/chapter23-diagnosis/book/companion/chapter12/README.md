# Repeated-trial checkpoint

Python 3.11+, standard library only. Start in companion/ with Chapters 1-10 intact. No network or live provider execution.

## Exercise before execution

Authored analysis inputs, not model observations: A=F,P,P; B=P,P,P; C=F,F,F. Compute first-attempt, at-least-one, all-attempts and pooled trial success, retaining denominators. Then omit C's third result without deleting its scheduled slot. Explain eligibility and missing counts. Can communication five cancel a wrong refund? Record answers before commands, which reveal the solution.

## Walkthrough

Run each separately. The failure command intentionally exits 1; all other commands should exit 0.

```sh
python3 -m chapter12.repeated run
python3 -m chapter12.repeated failure
python3 -m chapter12.repeated repair
python3 -m unittest discover -s chapter12 -p 'test_*.py' -v
```

Outputs are chapter12/output/run.json, failure.json and repair.json. Run executes bounded deterministic Chapter 5 fixtures and Chapter 7 scorecards. Repair analyses generated patterns; it is not an empirical reliability experiment. First attempt is 1/3, any is 2/3, all is 1/3, trial success is 5/9. Missing C3 leaves scheduled denominator nine, scored denominator eight and no complete-group subset estimate for C. Financial failures remain failures.

Read per_task before aggregate headlines. Errors and missing results remain in scheduled denominators. Empty ratios are null. Complete scheduled groups are required; submitted results may be absent. Estimates require independent stationary trials within tasks. Authored family counts do not establish independent incident sampling.

The budget scenario applies hypothetical cents per request to actual Chapter 5 request counts. Unknown measured model cost stays null. New-task preparation is explicitly priced; repeats add no new family coverage. The code is an offline teaching checkpoint, not a production scheduler, monetary cap or release authority.

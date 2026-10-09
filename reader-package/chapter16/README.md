# Chapter 16

Run all book commands from the companion root, not this directory.

`python3 run.py 16 -- PYTHON_ARGUMENTS` selects the complete dependency environment.

Implementation root: `runtime16`. Module names follow reader chapter numbers. Evidence digests bind the current implementation; retain prior receipts separately.


## Scheduled accounting and counter rules

The CLI declares a `scheduled` registry before execution. Each entry binds a unique `attempt_id` to the case, persona and candidate. Repeated trials of one case need different attempt IDs. `summary(rows, scheduled=scheduled)` rejects missing, duplicate, foreign or mismatched attempts rather than reporting a smaller, better-looking denominator. Counters must be nonnegative integers, never booleans. Information gain and unnecessary questioning are mutually exclusive for any one question, so `useful + unnecessary <= questions <= turns`. This single-identity loop can gain identity at most once; an unnecessary question requires that earlier gain. Completed rows need that gain, no unnecessary questions, and at least one non-question action (finish). A refund requires another action, but a policy-compliant refusal does not. Abandonment requires a question that elicited departure. Questions with an uninformative reply, a simulator error or an unconsumed late reply need not belong to either counter. These are local arithmetic and outcome checks, not full trace authentication. Calling `summary(rows)` without a schedule describes only the supplied rows; it cannot establish coverage. Keep the registry when exporting or filtering results. Historical result files without these identities remain historical evidence, not inputs to scheduled accounting.

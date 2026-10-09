# Chapter 14 local state checkpoint

Start in `companion/`, Python 3.11+, standard library only. Retain Chapters 1-13. No network, credentials, models or financial services. SQLite effects and process restart are real local execution; the lost reply and both actors are authored deterministic fixtures.

Before running, decide whether identity-first and policy-first should both pass, and why a correct refund plus a B200 cancellation must fail. Write the necessary dependencies before reading the manuscript solution.

```sh
python3 -m chapter15.state_lab failure
python3 -m chapter15.state_lab repair
python3 -m chapter15.state_lab exercise
python3 -m unittest discover -s chapter15 -p 'test_*.py' -v
```

Failure intentionally exits 1: the interrupted process already committed one refund and unsafe resume inserts another. Repair exits 0: the same business-operation identity and payload returns the existing effect. Exercise accepts both routes. Each child interruption exits 75, a simulation signal rather than a financial outcome. Reports are in chapter15/output/. Temporary databases are removed after independent snapshots are retained.

The v2 report retains the actual persisted memory read in `memory_observations` with its event sequence and operation identity. Completed recovery requires initial submit, timeout, memory read, reconciliation, retry submit, confirmation in that order, plus final memory `confirmed`. Interrupted memory `not_started` remains valid interruption evidence. Both intake check orders are allowed. Before a first monetary write the transaction requires exactly those two intake checks followed by intake handoff for this operation. Existing-result lookup remains sequentially idempotent without requiring a timeout; safe duplicate suppression alone is not a completed recovery protocol. Historical v1 receipts are unchanged; correction executions retain v2 reports separately.

The boundary rejects foreign/composite identities, exact-type defects, role violations, missing prerequisites and payload conflicts. Events and state are checked together. A coherent forged trace is not authenticated. Financial FAIL is noncompensatory. Unknown caller outcome does not imply failed operation. The narrow event protocol is not a generic workflow engine. Tests do not establish concurrent safety, live-provider behaviour or empirical multi-agent quality. Native visual, typeset and independent acceptance remain open.

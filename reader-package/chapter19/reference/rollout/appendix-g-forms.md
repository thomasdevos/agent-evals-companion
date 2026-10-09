# Appendix G: rollout and operations forms

Staged forms for the delivery lab. Blank fields mean missing evidence, not approval. These forms are application-owned records, not provider APIs or a hosted CI configuration. The runnable local commands are in this lane's README. The historical Chapter 18 local CI runner remains the executable fast/scheduled example; a new YAML workflow and cache implementation are not supplied by this insert.

## G.1 Release and staged rollout record

| Field | Required entry |
|---|---|
| Campaign and scope | Release identifier; synthetic rehearsal or real environment |
| Candidate | Pinned agent/model, prompt, adapter, tool and grader versions |
| Incumbent | Pinned version, availability evidence, retirement deadline |
| Technical evidence | Delivery packet digest, source bindings, schedule, PASS/FAIL/DEFER and reasons |
| Monitoring evidence | Window, collector version, scheduled/observed/missing and mature/pending counts |
| Sentinel provenance | Candidate-specific or separate reference stream; never imply a join absent from the producer |
| Exposure | Current stage, proposed stage, cohort key, selection rule and allowed effects |
| Stop rule | Slice thresholds, collection/maturity rule, incident severity and owner |
| Approval | Named release owner; accept/reject; exact state, evidence, target and window binding |
| Rejection | Reason, unchanged route receipt, next action and owner |
| Rollback | Previous pin, fallback deadline, future-routing action and separately tracked committed effects |
| Review | Producer receipt, independent review status, author or operational approval status |

Filled synthetic example: Alex Morgan rejects a shadow request bound to a passing Chapter 18 packet. `demo.py reject` exits 2. The state remains hold with candidate share zero. A changed evidence digest does not change that decision. The identity is fictional and the approval mechanism is not authentication.

## G.2 Monitoring specification

Complete this before examining the release window.

- Population and eligible request definition: __________
- Window start, end and clock: __________
- Trace schema/version and request identity field: __________
- Agent/model, prompt, tool, evaluator and collector pins: __________
- Sampling mechanism and inclusion probability for each eligible stratum: __________
- Scheduled identities or manifest digest: __________
- Scheduled / observed / missing counts: __________
- Outcome maturity rule and mature / pending counts: __________
- Selected-queue fraction, with numerator and denominator: __________
- Horvitz-Thompson estimate, population size and design assumptions, or reason withheld: __________
- Signal meaning, including when refusal is correct: __________
- Stop threshold, slice, minimum evidence and calibration reference: __________
- Privacy exclusions, ingestion redaction, retention and access owner: __________
- Investigating owner and separate release authority: __________
- Allowed action on missing evidence: hold / rollback future selection / halt, with reason: __________

A sampled online evaluator should consume a retained, appropriately redacted observation, not repeat the business action. Document any replay side effects separately. The sentinel fixture in this lab has two hundred scheduled records per window and uses a complete window, not an inclusion-weighted production sample.

## G.3 Incident to evaluation and rollback record

| Field | Entry |
|---|---|
| Incident identifier and window | __________ |
| Original trace/request identities | __________ |
| Alert, slice and collector version | __________ |
| Known, unknown and pending evidence | __________ |
| Current stage and exposure cohort | __________ |
| Decision and named decision maker | __________ |
| State generation before/after | __________ |
| Future selected version or HALT | __________ |
| In-flight request treatment | __________ |
| Committed effects that remain | __________ |
| Separate reconciliation authority and action | __________ |
| Reviewed regression case and exposure marking | __________ |
| Proposed fix and pinned comparison | __________ |
| Monitoring-rule revision and owner | __________ |
| Reopening conditions and approval | __________ |

Do not write "rolled back" as a substitute for documenting committed effects. In the lab, `synthetic-refund-001` survives rollback. The fixture does not implement financial compensation. Carry the original identity into Chapter 23's diagnosis workflow only when the upstream trace actually provides it.

## G.4 Migration and deprecation record

- Incumbent pin and proposed pin: __________
- Retirement announcement source, date checked and announced deadline: __________
- Internal cutover deadline and last safe rollback date: __________
- Requested versus served identifier evidence, including mismatches: __________
- Response parser, tool contract, history and refusal compatibility checks: __________
- Dataset, prompt, grader, runtime and adapter source bindings: __________
- Allowed/disallowed request cases and correct-refusal results: __________
- Cost and latency evidence reference, or unknown with reason: __________
- Shadow, canary and staged windows and approval bindings: __________
- Fallback availability check and halt policy after retirement: __________
- Release owner accept/reject and conditions: __________
- Independent technical review, operational approval and unresolved limits: __________

Filled synthetic policy: incumbent `scripted-support-v0`; candidate `scripted-support-v1`; retirement day 60; aliases refused. Passing authored compatibility flags before day 60 means eligible for shadow consideration, not approved for full exposure. An unknown real provider deadline cannot be filled with this scenario date.

## G.5 Weekly triage

Meeting window: __________. Facilitator: __________. Release authority present or unavailable: __________.

For each unresolved incident, record its evidence window, severity, maturity and collection gaps, current exposure, next action, owner and due date. List release requests accepted, rejected and deferred. Check each fallback's availability and approaching retirement date. Record whether the team is holding a route while it diagnoses the cause; do not force a causal conclusion to justify a precautionary stop.

Decision table: incident / evidence reference / action / owner / due / authority / follow-up result.

## G.6 Monthly suite review

Review period: __________. Dataset owner: __________. Grader owner: __________. Programme owner: __________.

List suite additions and removals with their coverage obligations. Identify every omitted high-severity case, exposed comparison set and changed evaluator. Record why each retired case is no longer needed and what replaces it. Compare the frequent suite with the full suite without claiming equal coverage. Link price-dated cost and latency reports; mark unavailable provider usage and costs as unknown. Record the next migration event and whether its rollback window is long enough for the proposed stages.

Decision table: case or obligation / keep-add-retire / evidence / coverage loss / replacement / reviewer / next review date.

## G.7 Cache review checklist for later integration

A future cache must key immutable results by candidate, dataset, grader, tool/runtime and source bindings, not only by a branch name. It must preserve missing and failed records, revalidate packets on a hit, and never cache approval, current model availability or a time-sensitive rollout decision as though they were test output. A stale or foreign cached packet should fail the same identity and freshness checks as a newly supplied packet. This is a design checklist, not a claim that this lab implements a cache.

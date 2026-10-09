# Chapter 8 local review checkpoint

Python 3.11+, standard library only. Start in `companion/` with Chapters 2 and 7 intact. No model, network, provider or real reviewer is invoked. All recorded judgements are authored synthetic fixtures, not empirical agreement evidence.

```sh
python3 -m chapter09.review demo
python3 -m chapter09.review leak
python3 -m unittest discover -s chapter09 -p 'test_*.py' -v
```

`demo` writes `chapter09/output/reviewer/packet.json` and separate administrator evidence, independent synthetic ratings, adjudication, workflow, scorecard and hypothetical effort arithmetic. The wrong 4199-pence refund remains FAIL even with the separately authored maximal diagnostic of five. Dimensional ratings are not automatically collapsed into the Chapter 7 scalar.

`leak` exits zero only after detecting the intentional identity/reference leak. Formatting-only detection has its own test. Repair: rerun `demo`, which allowlists public fields and removes the known bold wrapper without changing words or numbers. Inspect raw response and normalisation metadata in admin/authoritative.json. Residual content reidentification remains possible.

Only distribute reviewer/ and RUBRIC.md to an actual reviewer. The filesystem separation is not an access-control system; anyone holding the repository can inspect the answer key. Assign reviewers before collection, collect independently, freeze submissions and only then adjudicate. `reconcile` accepts supplied rating/decision lists and returns an incomplete workflow when assignments or decisions are absent. It rejects unknown or duplicate assignments, exact-type violations and changed packet/prior-rating bindings. Storage is not tamper-proof or append-only enforcement. Preserve original submissions operationally.

## Exercise and solution

The consumer requires the supported `communication-v1` packet rubric and equality with each rating's rubric, even when packet and prior-rating hashes have been freshly recomputed. Missing, malformed and unknown rubric versions are rejected with `ValueError`. The correction tests exercise these resealed contradictions in normal and optimized Python.

The saved synthetic-B escalation score of 1 deliberately misapplies the rubric: it treats conditional wording as absent help despite the named support destination. Its distinct rationale is retained alongside the separate adjudication correcting it to 3. No real human disagreement is claimed. After correcting the authored rationale, `example-output/` was regenerated with `python3 -m chapter09.review demo --out chapter09/example-output`; independent-rating hashes, adjudication references and workflow were regenerated together. The rubric, packet and authoritative financial evidence did not change. Historical producer and independent-review receipts were not rewritten; the new candidate bindings live in `reviews/chapter-08/corrections/`.

Before consulting RUBRIC.md, replace 'helpful and professional' with observable escalation anchors. Include unavailable, uncertain and not-applicable evidence with null ratings. Solution: missing required next step or unauthorised promise = 1; destination but unclear issue/follow-up = 3; explicit unresolved issue and permitted destination without unauthorised promise = 5. The conditional support sentence supports 3 under this rubric. Never score missing evidence as 1.

The published fixtures are calibration material, not a secret holdout. Independent human review, author acceptance and typeset/native visual review remain separate gates.

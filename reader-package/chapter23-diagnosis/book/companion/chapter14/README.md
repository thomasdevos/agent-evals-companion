# Chapter 13 checkpoint

Use Python 3.11+ from `companion/`, with chapters 1-12 retained. Standard library only; no provider or credentials. Dataset and policy documents are synthetic. Claim references are authored exact matches, not general semantic entailment.

Before running, propose a retrieval repair for a historical question and a current question when both revisions share keywords. Keep dataset.json, the judge and two-result budget fixed. Do not read the solution first.

```sh
python3 -m chapter14.retrieval run
python3 -m chapter14.retrieval failure
python3 -m chapter14.retrieval repair
python3 -m chapter14.retrieval exercise
python3 -m unittest discover -s chapter14 -p 'test_*.py' -v
```

Run commands separately. `failure` deliberately exits 1: answer-only grading actually returns PASS for a correct answer with an unsupported explanation. `repair` exits 0 because that defect is detected, while the candidate remains FAIL. Other commands exit 0. Reports are saved under chapter14/output/ and printed. `exercise` uses the undated retriever; `run` uses the dated retriever. Compare query-specific coverage and hashes, not just the average.

## Solution, after attempting the exercise

Filter by start <= as_of < end before unchanged lexical ranking. Preserve historical documents for historical queries. The current query recovers both required passages instead of one. Do not change relevance labels or claim references. Matching dataset/config hashes show which parsed inputs stayed fixed; producer receipts additionally bind raw source. Hashes do not certify label quality.

Unknown, refused and missing remain distinct. `answered` cannot use the reserved categorical values `unknown` or `refused`: those combinations raise `ValueError('RESERVED_ANSWER')`, including on the unchanged conflict and incomplete fixtures with fully supported individual claims. Explicit `unknown`/`refused` requires null answer and empty claims; its correctness field measures agreement with the expected outcome, not substantive answer correctness or PASS. `None` is a missing result with null correctness. Malformed or contradictory combinations raise validation errors; `error` is not a supported response status and must not be converted to an abstention or PASS. There is no answer aggregate here: retrieval rows retain all scheduled queries separately.

The original `example-output/` files are preserved historical receipts. The uncertainty correction changes admission of reserved answers, not those demo outputs; fresh correction replay receipts supersede the old source binding, not the historical evidence. Empty relevant sets have null recall/rank and a separate unwanted-retrieval diagnostic. Exact identity tuples preserve dataset/query and document/revision/passage boundaries. Duplicate returned passages are rejected. Chapter 9's real evidence packet/parser is exercised as a separate structural diagnostic; its valid evidence IDs do not establish support. Financial scorecards are not replaced or recomputed here.

Unsolved extension: model evidence availability separately from effective intervals under a new versioned dataset. No empirical model, native visual, typeset or publication acceptance is claimed.

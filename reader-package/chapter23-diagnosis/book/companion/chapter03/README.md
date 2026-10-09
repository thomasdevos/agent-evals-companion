# Chapter 3: dataset coverage

Run from `companion/` with Python 3.11 and the standard library. Keep `first_eval.py`, Chapter 2 source/schema/cards and Chapter 3 together. No network, credentials or live model calls. The authored JSONL files are shipped; `build` regenerates them deterministically.

## Exercise before solution

Run the first coverage command. Name the missing decision families and propose the smallest set of valid cards that covers them. Do not change the coverage policy to match the existing data. Only then inspect repaired.jsonl and the second report.

```sh
python3 -m chapter03.dataset_lab coverage --dataset chapter03/paraphrases.jsonl
python3 -m chapter03.dataset_lab coverage --dataset chapter03/repaired.jsonl
python3 -m chapter03.dataset_lab exercise --dataset chapter03/repaired.jsonl
python3 -m unittest -v chapter03.test_dataset_lab
python3 -m unittest -v chapter02.test_task_lab
python3 -m unittest -v test_first_eval
python3 -m chapter03.dataset_lab build
```

Expected exits: 1, 0, 0, 0, 0, 0, 0. First exit 1 means a valid dataset has missing required families, not an invalid JSON file. Invalid data exits 2. Exercise emits raw Chapter 2 trials; it does not implement the Chapter 7 scorecard aggregator. See DATASET-CARD.md, SCORECARD-CONTRACT.md and CHECKPOINT.md. Coverage is structural and bounded, never a claim of production representativeness.

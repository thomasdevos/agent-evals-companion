# Offline Chapter 22 lab

Read the manuscript exercise before running these commands, which reveal results.
Run from this `companion` directory with the book's Python environment. Tested here with Python 3.11.15; standard library only, no credentials or network.

```sh
python3 drift.py
python3 -m unittest -v test_drift
python3 figures.py
```

Optimised-mode repeat:

```sh
python3 -O drift.py
python3 -O -m unittest -v test_drift
python3 -O figures.py
```

`validate` checks generated-fixture row fields, not production ingestion. It rejects duplicate IDs, reversed days, invalid exact types, nonfinite or negative numeric evidence, and collected rows missing refusal, latency or cost. `aggregate` rejects unrepresentable sums; numerical helpers raise `ValueError` rather than return nonfinite diagnostics. `analyse` requires ordered unique daily group records and a nonempty baseline for each watched group.

The caller must preserve the complete generated schedule and fixed identities. The checker does not authenticate versions, detect deleted scheduled rows, or enforce outcome maturity against an external cutoff. The generator supplies those properties for this offline snapshot. Imported-stream reconciliation, version-change boundaries and late-event handling are proposed production controls, not implemented ingestion features. Test the additional boundaries with `python3 -m unittest -v test_boundaries` (also with `-O`).

All commands expect exit 0. Outputs replace only this directory's `output` files and sibling `assets` SVGs. Preserve output before modifying the seed. No command deploys, pages anyone or executes business tools. Figure 22.1 clamps negative z scores to zero and labels its axis accordingly. Null alarm results describe one held-out seed, not a confidence bound. Missing days hold the CUSUM state and suppress quality alarms. Calibration assumes independently generated requests; production autocorrelation requires different calibration data.

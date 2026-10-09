# Chapter 19: production-shaped monitoring

Synthetic offline lab, Python 3.11, standard library. Start in `companion/` with Chapters 1-18 retained.

## Exercise first

Before commands or output, assign inclusion probabilities for a census of twenty alert units and a simple random sample of eight of eighty routine units. All selected alert checks fail; all selected routine checks pass. Distinguish queue and population denominators. Decide which rates remain unknown if an observation, a delayed outcome and an inclusion probability are unavailable. Related incidents are not automatically independent.

## Reproduce and repair

```sh
python3 -m chapter21.monitor failure
python3 -m chapter21.monitor repair
python3 -m chapter21.monitor unknown
python3 -m unittest discover -s chapter21 -p 'test_*.py' -v
```

The failure command intentionally exits 1; all others exit 0. Outputs are retained in `chapter21/output/`: `failure.json`, `repair.json` and `unknown.json` each have corresponding raw rows in `failure-observations.json`, `repair-observations.json` and `unknown-observations.json`. `population.json` is the unchanged synthetic population. Reports contain schedules, not raw rows. The sequence preserves each mode's evidence; rerunning the same mode replaces its deterministic files, not an append-only history.

Numerical validation is separate from design positivity: every supplied non-null probability must have a finite reciprocal, even when other evidence is unknown. A complete estimate also requires a finite weighted total. Unrepresentable weights or totals raise `ValueError`; the CLI reports a validation error with exit 2 and no traceback. Small probabilities with representable arithmetic remain valid; estimates above one are not clamped. Missing evidence still gives null, not zero. `failure` misreports a selected fraction as a population claim. `repair` reports the selected fraction separately from a design-weighted estimate; `unknown` keeps incomplete estimates null and the selected schedule intact. The authored finite population is only a diagnostic. No live rate, calibration, causal effect or human approval is established.

The promotion consumes Chapter 3's dataset validator and Chapter 4's exposure manifest, preserves provenance and routes an explicitly authored approval fixture into development regression only. The nested Chapter 7 scorecard genuinely retains Chapter 18's financial failure. No automatic deployment or refund follows an alert. Monitoring approval is not a delivery pass.

`figures.py` reads retained project-relative `assets/chapter-19/data/*.json`, writes three grayscale SVGs and records hashes. It never requires an external temporary directory. Native pixel and final typeset review remain open.

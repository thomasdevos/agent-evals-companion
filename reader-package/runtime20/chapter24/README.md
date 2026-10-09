# Chapter 20 checkpoint

Python 3.11, standard library, offline only. Start in a source copy's `companion/` retaining Chapters 1-19 and Chapter 8 example-output fixtures. Before commands, choose a smaller frequent suite retaining every high-severity case and every family/severity combination. Record lost identities; decide whether reduced coverage can replace a full release run. Compare request-only and investigation-inclusive costs before revealing the result.

```sh
python3 -m chapter24.programme failure
python3 -m chapter24.programme repair
python3 -m unittest discover -s chapter24 -p 'test_*.py' -v
python3 -m chapter24.figures
```

Run separately: expected exits 1, 0, 0, 0. Invalid or out-of-range accounting (including overflow of finite inputs) exits 2 with a controlled accounting error before writing a report. Totals and ratios must remain finite; overflow is neither clamped nor converted to null. Unknown inputs retain their existing null semantics. Reports retain raw trials, charge rows and inherited scorecards in chapter24/output. The failure claim ignores unsuccessful work. Repair adopts only reduced local regression; architecture promotion remains deferred. All monetary amounts and ownership identities are authored hypothetical inputs. Null usage and live price are not zero. Local elapsed time is not provider latency. Figures write assets/chapter-20 relative to the project root. No provider, deployment or business action occurs. Producer candidate, not independent acceptance.

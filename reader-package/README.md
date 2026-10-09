# Reader package

Start with the repository [README](../README.md) for setup, edition matching, known limitations and expected failure exits. Run book commands from this directory. Record Chapter 1's prediction and Chapter 6's opening predictions before opening their implementations or demonstrations.

`python3 run.py 1 -- first_eval.py --agent corrected --output results/my-corrected.json`

`python3 run.py 1 -- -m unittest -v test_first_eval`

The child directory is listed in `chapter-roots.json`. Route `6` selects the corrected flat cassette implementation; `6-native` selects the authored native task session; `7` selects scripted report replay. The native tree's inherited flat loader is historical: use route `6` for flat imports. Put `-O` after `--`, and set `PYTHONOPTIMIZE=1` when testing optimized nested children.

This is a reader-only derivative of the 9 October 2026 Chapter 7 correction checkpoint. It excludes manuscripts, research and historical QA. Keep the nested source layout and supplied example-output inputs. Old author ZIP digests and omitted author sealing scripts are not installation requirements; use this repository's manifests and generate fresh cache entries.

Chapter 19's portable `verify.py` uses a regenerated `files.json` that binds only its distributed reader files. Appendix G's inert YAML examples remain outside `.github/workflows`; no hosted workflow is enabled. Local fixture checks are not live provider observations or full-book approval.

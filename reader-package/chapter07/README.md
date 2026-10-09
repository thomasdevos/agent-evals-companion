# Chapter 7

Run all book commands from the companion root, not this directory.

`python3 run.py 7 -- PYTHON_ARGUMENTS` selects the complete dependency environment.

The launcher starts its child in `core/companion`. The implementation is `core/companion/chapter07/replay.py`, and relative input/output paths resolve inside `core/companion`. This outer `chapter07` directory contains routing guidance only. Historical `chapter06-*.json` filenames and `chapter06-manifest-v1` schema names are retained deliberately. Evidence digests bind the current implementation; retain prior receipts separately. The diff task verifies an explained relationship; its worked solution is in the implementation README.

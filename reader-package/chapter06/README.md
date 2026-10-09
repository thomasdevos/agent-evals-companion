# Chapter 6

Run all book commands from the companion root, not this directory.

`python3 run.py 6 -- PYTHON_ARGUMENTS` selects the complete dependency environment.

Implementation root: `provider-chapter06`. Reader numbers select launcher environments; vendored module names retain their original dependency numbers. Do not derive module paths from reader chapter numbers. The child runs in `provider-chapter06`, so inspect its outputs under that prefix from the companion root. Put optimisation after `--`, for example `python3 run.py 6 -- -O -B -m unittest discover -v`. Evidence digests bind the current implementation; retain prior receipts separately.

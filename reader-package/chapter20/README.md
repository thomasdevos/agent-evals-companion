# Chapter 20

Run all book commands from the companion root, not this directory.

`python3 run.py 20 -- PYTHON_ARGUMENTS` selects the complete dependency environment.

Implementation root: `runtime20`. Module names follow reader chapter numbers. Evidence digests bind the current implementation; retain prior receipts separately.

## Duration consistency

The sequential model durations must fit within the enclosing elapsed time, rounded upwards to integer nanoseconds using the float's exact ratio. This permits less than one nanosecond of unit-rounding, with no percentage slack or comparison against a new run's timings.

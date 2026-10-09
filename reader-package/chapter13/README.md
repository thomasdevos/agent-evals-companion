# Chapter 13

Run all book commands from the companion root, not this directory.

`python3 run.py 13 -- PYTHON_ARGUMENTS` selects the complete dependency environment.

Implementation root: `core/companion`. Module names follow reader chapter numbers. Evidence digests bind the current implementation; retain prior receipts separately.


## Frozen-plan digest recipe

The snapshot is stored as JSON bytes; each access to `Experiment.plan` returns a fresh copy, including nested lists. Analysis validates a decoded snapshot before reading outcomes and hashes the same bytes. Mutating an exposed copy therefore cannot change the seed or configuration while retaining an old digest. The digest is SHA-256 of `json.dumps(report['plan'], sort_keys=True).encode()`; it binds that representation, not a signature or authenticated history. Deliberately replacing private internals is outside this local API contract.

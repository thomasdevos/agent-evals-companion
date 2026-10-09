# Native durable integration reader

Start with [the lane README and prediction exercise](../README.md#exercise) before running commands or opening output receipts. Copy both the lane `README.md` and the entire `reader/` directory into a fresh parent directory, preserving the `../README.md` link; run commands inside the copied `reader/`. It teaches the integration, provides the executable commands and places the exercise before its answer.

The lane README documents byte-complete explicit export after uncertain completion acknowledgement: the session remains stopped, but a separately invoked export may validate a published completion marker. This is not proof of fsync or power-loss durability, nor historical authentication. `test_completion_export_policy.py` checks the policy with explicit unittest checks that remain active under `-O`.

`integration.py` is the new entry point. `native.py`, `demo.py`, `test_native.py` and `inherited/` retain the accepted predecessor code. Their separate passing tests do not prove integrated durability; `test_integration.py` exercises that boundary.

The original native README and supplement are preserved in `../historical-native/` as historical reading, not as the integration's entry point. The README under `inherited/` also describes its historical lab. Those older commands and acceptance notes do not replace the new integration tests or independent review.

# Chapter launcher map

Run commands from `reader-package/`. The paths below are relative to that directory. Native and flat Chapter 6 routes are separate.

| Selector | Child working directory |
| --- | --- |
| `1` | `core/companion` |
| `2` | `core/companion` |
| `3` | `core/companion` |
| `4` | `core/companion` |
| `5` | `core/companion` |
| `6` | `provider-chapter06` |
| `7` | `core/companion` |
| `8` | `core/companion` |
| `9` | `core/companion` |
| `10` | `core/companion` |
| `11` | `core/companion` |
| `12` | `core/companion` |
| `13` | `core/companion` |
| `14` | `core/companion` |
| `15` | `core/companion` |
| `16` | `runtime16` |
| `17` | `core/companion` |
| `18` | `core/companion` |
| `19` | `delivery/revisions/revision-pack-20261006/completion-delivery-selected/reader` |
| `rollout` | `delivery/revisions/revision-pack-20261006/completion-delivery-selected/reader` (alias of `19`) |
| `20` | `runtime20` |
| `21` | `core/companion` |
| `22` | `runtime22` |
| `23` | `chapter23-diagnosis/book/companion` |
| `24` | `core/companion` |
| `E` | `statistics` |
| `6-native` | `native-chapter06` |

Chapter 19 adds `--delivery-capsule` before `--` for its `capsule/companion` submodule. Appendix G uses its own disposable copy, as described in the book.

For the rollout interlude: `python3 run.py rollout -- integration.py` and `python3 run.py rollout -- -m unittest -v test_integration`. This remains offline; live-model runs use the separate [live kit](reader-package/live/README.md).

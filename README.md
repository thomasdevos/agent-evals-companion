# AI Agent Evals companion

Reader code for Thomas De Vos's *AI Agent Evals*: https://github.com/thomasdevos/agent-evals-companion

This repository is private during development. Access requires an invitation and an authenticated GitHub account. A 404 while signed out does not mean the address is wrong. This is the 9 October 2026 integrated correction checkpoint, not a publication release or a claim that all chapters have passed editorial review. See [edition.json](edition.json) for the source identity and [known limitations](#known-limitations).

## Set up a working copy

Use Python 3.11 with the standard-library SQLite module. The offline labs need no pip install, model account, API key or paid service. GitHub access is needed to clone; the exercises then run locally. Python versions other than 3.11 are not verified for this checkpoint.

```sh
git clone https://github.com/thomasdevos/agent-evals-companion.git
cd agent-evals-companion
git rev-parse HEAD
python3 --version
python3 -c "import sqlite3; print(sqlite3.sqlite_version)"
cd reader-package
```

On Windows, use `py -3.11` wherever these instructions say `python3`. A virtual environment is optional because no third-party packages are required. If you use one, create it with `python3 -m venv .venv` and select its interpreter. Do not install an unrelated package named after the book.

Before running a lab or opening its implementation, read Chapter 1 through "Save a prediction before continuing" and record your answer. For Chapter 6, record its opening predictions before opening native-route demonstrations. The command output and implementation can reveal exercise answers.

## Run the first lab

Run these commands separately from `reader-package/`, after recording the prediction:

```sh
python3 run.py 1 -- first_eval.py --agent corrected --output results/my-corrected.json
python3 run.py 1 -- -m unittest -v test_first_eval
```

The first command should report `PASS`; both should exit zero. The output file is `reader-package/core/companion/results/my-corrected.json` relative to the repository root. The launcher changes the child process's working directory, not your terminal.

Chapter 1 also asks you to examine failures:

```sh
python3 run.py 1 -- first_eval.py --agent baseline
python3 run.py 1 -- first_eval.py --agent duplicate
python3 run.py 1 -- first_eval.py --agent crash
```

The baseline and duplicate trials intentionally return `FAIL` and exit 1. The crash trial reports `AGENT_ERROR` and exits 2. These outcomes test different boundaries. Do not repair them merely to make the terminal return zero, and do not join an exercise's commands with `&&`: the intended refusal would prevent later commands from running. An unexpected traceback or missing file is a setup or implementation issue, not an expected exercise result.

## Find a chapter

Use `python3 run.py SELECTOR -- PYTHON_ARGUMENTS` from `reader-package/`. The [chapter map](reader-package/chapter-roots.json) is machine readable; [CHAPTERS.md](CHAPTERS.md) lists every selector and working directory. `chapter01/` through `chapter24/` are navigation directories, not independent installations. Keep the nested dependency roots intact. Do not flatten their files into one Python package.

Chapter 6 has two routes:

```sh
python3 run.py 6 -- -B -m unittest discover -v
python3 run.py 6-native -- -B task_demo.py
python3 run.py 6-native -- -B -m unittest discover -v
```

`6` is the corrected flat cassette route in `provider-chapter06`. `6-native` is the authored task-session route in `native-chapter06`. `7` is scripted report replay in `core/companion`; it does not import a native task bundle. The inherited flat importer inside the native dependency tree is historical and admits malformed timing metadata. Use `6` for flat imports.

To exercise optimized validation, put `-O` after `--` and set `PYTHONOPTIMIZE=1` for nested Python children. Merely running `python3 -O run.py ...` does not optimize the child automatically.

Chapter 19's delivery submodule uses `python3 run.py 19 --delivery-capsule -- -m chapter19.delivery ...`. Cache and integration commands omit `--delivery-capsule`. Appendix E uses selector `E`. Appendix G deliberately copies the full `chapter19/reference/ci-cache` and `chapter19/reference/rollout` directories into a disposable exercise directory; follow the book's working-directory changes.

## Run offline checks

From the repository root:

```sh
python3 tools/check_offline.py
```

This runs each current chapter's named suite, Appendix E, the native Chapter 6 suite, the live kit's offline fake-provider and safety suites, and first-lab positive/negative controls. It verifies expected exit statuses and reports observed test invocations rather than a fixed historical count. It is a local regression check, not independent editorial acceptance or a benchmark of a model. It writes only the labs' temporary/generated outputs. Run it in a disposable clone if you want to preserve your own experiment outputs.

No GitHub Actions workflow is installed. The inherited `ci-example.yaml` files are inert teaching examples, reviewed as examples but not enabled as hosted workflows. They do not deploy, spend money or provide evidence that hosted CI passed.

## Offline and live boundaries

### Run against real models

Use [reader-package/live/README.md](reader-package/live/README.md) for the sole recommended full-run path: `live/live_run.py`, separate from the offline launcher. It sends requests only with `--authorise-live`; `--dry-run` uses authored fakes and omitting both flags is plan-only. The legacy Chapter 5 entry point also can send requests (one task, OpenAI only, no spending ceiling); it is not the recommended full-run command. This checkpoint includes no live run or provider-compatibility evidence. Read the kit's conditional budget and capture-privacy limitations before approving any spend.

The supplied observations and provider envelopes are authored fixtures. Local SQLite writes, grading, capture and replay are real local execution; their results say nothing about a live model's quality or current provider compatibility. The launcher rejects explicit live-provider arguments, but it is not a security sandbox and can execute arbitrary Python. The underlying Chapter 5 code retains a live interface for a separately approved experiment. Do not bypass the launcher or add credentials as a setup step. Live use requires a reviewed command, current SDK/API checks, privacy controls and explicit spending approval.

Never commit credentials, private conversations, customer records or provider captures. The repository omits manuscript text, research captures, author QA logs and generated historical outputs. Retained `example-output` fixtures are inputs to later chapters, especially Chapter 10; keep them. Some labs calculate source digests, so digests from the larger author ZIP will differ from this reader-only derivative. Generate observations and cache entries in this checkout rather than transplanting old receipts.

## Match the book edition

Record `git rev-parse HEAD` with each experiment. Use the immutable commit named in your manuscript's companion section rather than assuming `main` still matches your book. `edition.json` records the original ZIP and manuscript SHA-256 values. `reader-files.json` binds the distributed reader payload; it does not authenticate observations or prove author approval. The Chapter 19 portable verifier has its own regenerated `files.json` for this derivative and keeps its original validation logic.

No release tag or public release has been created. Later editorial candidates may change implementation and commands. Do not combine their source directories with this checkpoint.

## Troubleshooting

- `run.py` not found: enter `reader-package/`, not a numbered navigation directory.
- `ModuleNotFoundError`: use the chapter launcher and retain the complete nested checkout. Do not add arbitrary pip packages to conceal a missing file.
- Missing SQLite: install a Python 3.11 distribution that includes `sqlite3`.
- Missing fixture or digest mismatch: use a fresh clone at the recorded commit. Retain `example-output` inputs and regenerate caches after changes. Do not edit a manifest to conceal unintended source drift.
- Expected exit 1 or 2: compare the command and status with the chapter's deliberate failure case. A failed assertion in a unit test remains a regression.
- Permission or output-directory error: work in a writable disposable clone. Some capture and verifier commands deliberately refuse an existing output path; choose a new path rather than overwriting evidence.
- GitHub 404 or clone denied: sign in with the invited account, confirm access, then retry. Keep the repository private.

## Identity-review transfer and rollout interlude

Chapter 23 now includes a separate five-case synthetic identity/KYC review lab. It preserves source-document records, keeps verification unresolved and tests authorised index correction versus unsupported verification. It is not a model benchmark or compliance implementation. Read and record the chapter's prediction before opening the implementation or running the commands below. From `reader-package/`, use:

```sh
python3 run.py 23 -- -m chapter23.identity_review observe
python3 run.py 23 -- -m chapter23.identity_review failure
python3 run.py 23 -- -m chapter23.identity_review repair
python3 run.py 23 -- -m unittest discover -s chapter23 -p 'test_identity_review.py' -v
```

`failure` deliberately exits 1; the other commands exit 0. Pass `-O` after `--` to optimise the child. The five-case queue remains separate from the original 100 authored review records.

The manuscript retains 24 numbered chapters. Chapter 19 is now "Gate releases on complete evidence"; the complete rollout lesson follows Chapter 22 as the unnumbered "Roll out and roll back" interlude. Run its commands with `python3 run.py rollout -- ...` from `reader-package/`. Selector `rollout` aliases `19` without renumbering packages; delivery-capsule commands retain `19 --delivery-capsule`.

## Known limitations

This checkpoint retains the independently reviewed Chapter 7 corrections and native Chapter 6 integration, and adds the Chapter 8 retained-trace validation, aggregation-consistency and reader-instruction corrections. The edition record identifies the base archive and the added identity-review files; reader-files.json binds the shipped payload. These offline corrections do not establish current provider compatibility, genuine model observations or whole-book editorial acceptance. The Chapter 23 synthetic identity-review transfer is also included. No live study or publication release is included.

Nested READMEs describe their local implementation and may retain older chapter labels. Use the root map and current book for navigation. Author-only preparation/sealing utilities and their obsolete manifests are excluded. Figure generation and manuscript production are outside this code package.

## Rights and publication

No open-source license is granted by this repository setup. Existing source notices are retained. Licensing and redistribution terms require the author's or publisher's decision before publication. Private access is not permission to republish the code or the book. No manuscript, PDF or publisher delivery is included here.

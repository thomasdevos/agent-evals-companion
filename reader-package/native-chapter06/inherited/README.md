# Retain the call before dispatching its action

This offline lab connects currency admission, the provider-shaped cassette adapters and the inherited SQLite executor to durable capture and JSONL export. The callbacks produce authored fixture envelopes. They are not provider recordings, and the GBP rates are hypothetical teaching inputs. The candidate needs a different independent reviewer before acceptance.

Copy this whole directory to a disposable location and run the commands there with Python 3.11 or later. The lab uses only the standard library. `predecessor-README.md` describes the preserved currency lab; the commands below exercise the durable integration. `copied-dependencies.json` identifies every copied source by original relative path, byte length and SHA256. All 22 predecessor files are retained, with only its README renamed.

## Exercise before the worked result

Suppose the first callback returns a valid refund envelope with known usage, but replacing the terminal capture file fails. Predict the callback count, the retained reservation, whether the refund executes and whether a subsequent call through that same agent is permitted. Then change the fault to the second response. Does a storage failure erase a refund already committed after the first response? Write the two answers before running the tests.

## Capture an accounting stop, then repair in a fresh run

The first command deliberately omits usage in the authored response. Run it separately: exit 2 is expected, not a shell setup error.

```sh
python3 durable.py capture failed-run --unknown
```

The response reaches the recorder, but currency admission blocks its action. The result is `AGENT_ERROR`, with one call, three pence reserved and unknown total model cost. `failed-run/000001.json` contains a terminal envelope and accounting stop. A completed stopped run can be exported because its evidence is known; an interrupted intent cannot.

```sh
python3 durable.py export failed-run --output failed-export
```

```sh
python3 durable.py replay failed-export
```

Replay exits 0 when it reproduces the stopped outcome, not when the task passes. It uses the currency policy around the accepted cassette replay, so an unknown-usage refund does not slip through permissive raw-envelope replay.

Trying to overwrite the capture deliberately exits 2. It does not repair the earlier evidence.

```sh
python3 durable.py capture failed-run
```

For the worked repair, use a new destination and the normal authored fixture, whose usage is known. This is a new observation, not a retroactive price assignment to the failed run.

```sh
python3 durable.py capture repaired-run
```

```sh
python3 durable.py export repaired-run --output repaired-export
```

```sh
python3 durable.py replay repaired-export
```

The repaired capture passes, commits the fixture refund and releases its outstanding reservation after settlement. The export retains `calls.jsonl`, the unchanged cassette import manifest, a policy file with configuration and callback diagnostics, and a last-written completion marker. Replay reloads those bytes, validates imported projections and executes the currency-wrapped cassette through a fresh SQLite environment. It compares the full task result and accounting stop with the captured result. Export destinations also refuse overwrite.

## Where durability enters the call path

`DurableTransport` uses the existing `CaptureStore.intent(trial_id, request)` and `finish(entry, result)` API. It does not call the historical `load_capture` function: that loader requires an incompatible abstract-unit synthetic result shape. `durable.load` is the explicit adapter for this currency/cassette format. The original storage module and accepted import code remain byte-identical dependencies.

Before each callback, the currency agent reserves exposure. The durable transport writes an intent containing the actual request, attempt number, detached effective configuration and conservative accounting report. The inherited atomic writer flushes and fsyncs a temporary file, replaces the destination, then fsyncs the directory. Only after intent persistence returns may the callback run.

The cassette agent derives the response's tool and usage projections. `DurableAgent` then persists the completed call, accounting report and diagnostic event before returning an action to the executor. This ordering also covers a contract error or accounting stop. Successful persistence allows action dispatch; persistence failure restores the pre-callback reservation, latches the transport closed and returns an infrastructure failure from the outer single-trial runner. An attempted row in memory after a storage fault is not a publishable cassette. No completion marker is issued for that path.

This is a single-trial, single-writer runner, not a durable scheduler. SQLite fixture creation precedes the first transport intent. A first-intent failure prevents callback and agent actions, but does not claim zero database construction. Initial invalid currency configuration does precede both capture-directory creation and executor invocation.

## Execute storage failure and interruption checks

```sh
python3 -m unittest discover -v
```

The new `test_durable.py` suite exercises both provider shapes through actual capture, export, semantic import and policy replay. It also routes the real `os.replace` syscall to an occupied directory at the first intent or terminal write. This produces a filesystem error inside the full runner rather than merely calling a helper with a bad argument. The prior intent remains intact when terminal replacement fails. The test observes callback count, executor trace, final SQLite snapshot and conservative exposure. A fault latch also rejects explicit re-entry with a queued action.

The interruption control starts a separate Python process and uses `os._exit(73)` inside the callback, after its intent is durable. The parent verifies the exit, reloads the remaining intent and checks that export and restart in the same directory are refused. This establishes a process-interruption boundary, not sudden power-loss durability. Normal and explicit `-O` producer runs retain child argv, cwd, exits and output in the review receipts.

### Worked answer

On first-response persistence failure, the callback count is one. Three hypothetical pence remain reserved, total cost stays unknown, no action or refund executes, and further calls on that agent are blocked. Known usage received only in memory is insufficient to release exposure when terminal persistence fails.

In the full-card fixture the first response is already a refund. If its terminal capture succeeds, the refund can commit. A failure while persisting the second response therefore leaves that earlier refund intact, one penny settled and three pence reserved for the second request. The stop prevents future work; it cannot undo prior effects.

Keep interrupted or storage-failed directories for diagnosis. Repair the storage destination, reconcile any uncertain external effect out of band, and authorise a new run with a new destination only when that is safe. This lab provides no automatic reconciliation, retry or resume command. Deleting an unresolved intent would destroy the evidence needed to make that decision.

## Boundaries still open

Capture and SQLite action commit are separate transactions. A terminal envelope is persisted before its action, not proof that the action committed. A crash between them remains unresolved until a completed run result exists; neither exactly-once effects nor automatic recovery is claimed. Filesystem replacement and directory fsync are local single-writer mechanisms, not distributed locking or hardware power-failure certification.

The loader checks sequence, intent/call bindings, the accepted semantic import contract, reconstructed hypothetical accounting and completion bindings. This is a targeted format adapter, not an exhaustive hostile-storage audit or authenticated evidence system. Digests detect changed bytes relative to a trusted binding; an actor able to rewrite all local evidence can also rewrite those bindings. Export/replay operates on private payloads and free-text diagnostics, not a redacted publication summary. Do not place credentials or private production data in a callback payload.

The ledger is recorded durably for diagnosis, but there is no restartable spend ledger. Token bounds are caller declarations, provider billing categories are simplified, and no live billing cap is enforced. Multi-trial scheduling, retained primary-source research, native conversation lifecycle, chapter consolidation and canonical 24-chapter integration remain separate work. No model quality, latency or invoice measurements are reported here.

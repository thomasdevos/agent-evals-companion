# Run the offline cache-to-rollout lab

Use Python 3.11. The lab uses the standard library and authored synthetic fixtures. It makes no provider calls or real deployments. The approval callback supplies a local test input, not an authenticated human decision.

Copy this complete reader directory wherever you keep the exercise. From that directory, run:

```sh
python3 verify.py "evidence/reader-$(python3 -c 'import uuid; print(uuid.uuid4().hex)')"
```

The output directory must be new. The verifier checks the delivered file inventory, then captures those bytes into separate temporary copies for normal and optimised execution. Each copy runs twelve integration tests, the demonstration and fifteen rollout tests. The same tests running twice are not additional coverage. Read `commands.json` and the retained stdout/stderr files in the selected evidence directory. A successful run exits zero and writes `verification.json`; refused inputs exit 2. Existing evidence is never overwritten.

The demonstration advances the fast request to the local shadow stage. The scheduled comparison contains an inconclusive observation, so its aggregate decision is DEFER and the approval callback is not called. Rollback stops later routing without undoing committed effects. To inspect the demonstration directly:

```sh
python3 integration.py
```

The fixture's cache validator recomputes deterministic evidence, so this lab does not measure a cache speed improvement. The caller chooses its lane and supplies controller state. Production policy, atomic durable state ownership, live traffic and authenticated approvals require other implementations.

`files.json` binds the supplied bytes. `origin.json` relates the unchanged implementation files to the source candidate. Neither file authenticates its own origin: a party able to replace code and its manifest can change both. Run only code you trust. The verifier is a reproducibility check, not a sandbox or continuous filesystem protection. It copies only listed files into the execution directory; it does not run the author's dependency-preparation script or require their original source tree. An altered fixture needs a separately named candidate and review rather than an edit to this inventory presented as historical acceptance.

`chapter-19-integration.md` contains the staged explanation and exercise. This capsule is one offline companion subset, not the complete revised book. The unchanged implementation and portable runner retain their earlier bounded subset reviews. This integrated documentation/package delta requires its own focused independent review; it does not reopen or extend those implementation verdicts. It grants no whole-book acceptance, native-layout approval, live-performance evidence or author approval. The adjacent chapter-19.md and appendix-g.md are the current staged manuscripts; the in-capsule explanation remains the historical subset text.

## Current edition migration

Python packages now follow reader chapter numbers. Chapter 23 physically combines diagnosis and analysis; Chapter 19's reference capsule is separate from Chapter 21's monitoring implementation. Current inventories bind these migrated bytes. Prior author acceptance, origin and dependency-capture records describe the earlier edition and are historical, not acceptance of this migration. The authoritative current artifact and command receipts are in the enclosing edition's qa directory. Use run.py and the published commands; setup and verify_candidate scripts are historical author build utilities, not reader installation steps.

# Asset usage resource guard evidence

All data are synthetic; File repositories, original main.app assembly and
original authorization decisions are real. File/Mock in the runner names the
isolated fixture profile, not a replacement query reader or permission mock.
No real model, project, database credential or provider credential is included.

Verified source: **18731becb0060d3006dd3f5ab8fe0c6cc00c0266**, tree
**a40cc8e58c304cd77072f31ca98703a439c860cc**. Evidence-only later commits do not
change any app, scripts or tests. The complete
[source manifest](source-manifest.json) records all 25 changed source files as
Git blob and actual working-source SHA-256 hashes.

[Delivery and coverage report](../../ASSET_USAGE_RESOURCE_GUARDS_20261026.md)
contains limits, strict-mode compatibility, measurements and remaining gaps.
[Shared-owner proposal/authorization](../../ASSET_USAGE_SHARED_OWNER_PROPOSAL_20261026.md)
preserves the initial pause and the later explicit permission to implement.

## M0–M7 receipts

| Stage | Evidence and result |
| --- | --- |
| M0 | [Fixed-source baseline](coordinator/M0.md): process/Python/smoke, 62 original contract cases, original 32/540/6 scale; existing Windows asset-list cursor failure retained separately |
| M1 | [Read inventory](audit/READ_COST_INVENTORY.md), [baseline metrics](audit/baseline-metrics/summary.json), [final metrics](audit/final-metrics/summary.json): per-file size, phase, read/decode counts; 13 final HTTP requests reconcile actual bytes to one fresh budget |
| M2 | [73-case frozen guard group](coordinator/final-resource-guards.receipt.json): request cumulative admission before/within reads and before JSON object decode; original authority rereads retained |
| M3 | Same raw [guard log](coordinator/final-resource-guards.log): accepted and rejected giant strings/files/nesting/objects, actual Python allocations; RSS hard cap and hard CPU limit remain PARTIAL |
| M4 | [Independent strict positive and negative cases](independent/final-independent-resource.receipt.json), [real TCP](coordinator/final-loopback.receipt.json): existing facilities succeed without mutation attempts/writes; missing facilities refuse without init; compatibility first lock creation retained |
| M5 | [Independent 39](independent/final-independent-resource.receipt.json), [original independent 51](independent/final-independent-legacy.receipt.json), [192 original regressions](coordinator/final-regressions.receipt.json): exact source, permissions, finite-observation changes, resources, no-store and registry behavior |
| M6 | [Separate frozen authority/cost unit, 16 passes](audit/audit-final-frozen-authority-costs.receipt.json), independent worktree groups, [original scale, 1 pass](coordinator/final-scale-mixed-measurements.receipt.json), [loopback, 1 pass](coordinator/final-loopback.receipt.json) |
| M7 | [Seven-receipt verification](frozen-receipt-verification.json), [source publication readback](source-publication-receipt.json), source manifest and archived raw logs |

The seven final groups are 192, 73, 39, 51, 16, 1 and 1 passes. They overlap and
are not added as a unique test total. All seven final receipts are clean, exit
zero, source_unchanged_during_run=true, and bind the source commit/tree, command,
all manifest sources and raw log hash. The coordinator recomputed every hash
against the final source; both other units independently checked their receipts.
None of these seven groups uses skip/xfail to represent a missing environment.

Strict and legacy contracts coexist. `strict_read_only=true` requires explicit
paging and existing original facilities, including a populated Windows lock and
registered original process lock. It never creates a lock/identity/index or
directory, and returns a stable sanitized unavailable result when unsupported.
Initialized compatibility requests still use write-capable original coordinator
opens, and the fresh copied-path loopback test preserves one first compatibility
lock creation. Their unchanged business files are not relabeled zero-write.
Strict mode retains original locks; in-memory cursor issue/pruning is permitted
under the original process cap and is measured separately from filesystem work.

## Failure evidence and interpretation

- [M0 cursor failure](coordinator/m0-windows-cursor-existing-failure.log) is the
  unchanged separate asset-list cursor owner, ASSET_QUERY_CURSOR_UNAVAILABLE.
  The passing regression group never includes or claims to fix that case.
- M0's two malformed initial test selectors are separate zero-test harness
  failures; corrected successful invocations have distinct labels.
- [Original same-size-read defect](core/pre-native-same-size-failure.log) is a
  real reproduced Windows product failure. The independently authored assertion
  was unchanged; the native read admission fixed it.
- [Native reader exploratory run](core/native-reader-baseline-and-correction.log)
  distinguishes denied Windows writer attempts, unchanged original bytes and
  released handles. Windows replace-during-read can also fail on the original
  Python reader; original atomic_write succeeds once the reader closes.
- `core/native-reader-correction-corrected.*` retains an incorrect new test
  assumption that overwrite rename must succeed during an open read handle.
  Baseline reproduction identified that as a test issue. Original independent
  replacement/growth/overwrite assertions were not weakened.
- Early audit/core receipts marked dirty or source_unchanged=false are exploratory
  only. Frozen acceptance uses the seven explicitly named final receipts.
- `audit/*baseline*.receipt.json` comes from separate harness commits whose
  entire app tree equals c6ec9529; provenance files distinguish product source
  from added measurement harness. These are baseline evidence, not final passes.

Source hashes and raw measurements are retained, not aggregate-only chat claims.
The folder's attributes preserve JSON/log bytes without newline conversion, so
the public Git blobs retain the archived log/measurement hashes.
For example, reproduce a frozen guard run using the recorded interpreter and:

```text
python scripts/record_asset_usage_validation.py --label REPRO --output-dir EVIDENCE --run-root SYNTHETIC_RUN_ROOT --require-clean-code -- tests/test_studio_asset_usage_budget_guards.py -q -s
```

The original record wrapper sets the synthetic run root, isolates settings and
blocks external networking while allowing loopback. Real providers/databases
are not selected. Measurement helper source and all changed shared File readers
are included in the final recorder's source manifest.

## Explicit remaining status

Windows synthetic File / mounted ASGI HTTP / actual TCP HTTP: PASS for the named
groups. Existing separate Windows asset-list cursor: FAIL retained, owner not
changed. POSIX, real PostgreSQL, browser, real model/GPU and hosted Actions:
NOT_RUN. No Actions rerun or paid quota/security change was requested.

Process RSS hard limit, hard CPU/lock timeout, metadata syscall/total OS-I/O
limits, trusted-ancestor races, strong ABA, durable/cross-worker snapshots and
unsupported dependency coverage remain PARTIAL or unsupported. Existing typed
nonpaged queries intentionally remain under their old compatibility budget
contract. other_dependencies remains UNKNOWN. This evidence does not turn
finite observations or tracemalloc peaks into stronger guarantees.

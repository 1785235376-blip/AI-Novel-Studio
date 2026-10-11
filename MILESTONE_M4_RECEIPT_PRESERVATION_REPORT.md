# M4 incremental closeout: retain cleanup and provenance failures

2026-10-11 UTC. Parent: `bf1be37d1f27da0a9b9b3994cdac0fec4397784d`,
existing Draft [PR 47](https://github.com/1785235376-blip/AI-Novel-Studio/pull/47),
branch `feature/v2-narrative-platform`.

**Bounded original-harness fix verified. M4 remains PARTIAL; no Windows, GPU,
real-model, quality or complete backend acceptance claim.**

## Failure and correction

The existing real-text harness finalized native shutdown and source provenance
before writing `acceptance.json`. A terminate/kill/poll/wait exception or final
source-identity read/write error could therefore suppress the receipt and mask
the original operational failure.

Only the existing `execute()` implementation changes. Cleanup and final
provenance failures are recorded separately before the final receipt is written.
An existing operational exception remains the primary exception and its `FAIL`
status is retained. Without one, the first finalization exception propagates
after both outcomes have been recorded.

- Cleanup failure cannot produce PASS. A formerly successful operation becomes
  `FAIL_RUNTIME_SHUTDOWN`.
- Unavailable final provenance cannot produce PASS. A formerly successful
  operation becomes `INCONCLUSIVE_SOURCE_IDENTITY`, with `source_stable: null`.
- An observed poll/wait exit code is required to report the owned runtime stopped.
  A kill request alone is not exit evidence. Observed exit evidence is retained
  even if a later poll fails.
- Original normal-shutdown, source-drift and primary-failure semantics remain.
  Existing CPU argv, deadlines, platform guard, environment isolation and process
  targets/call paths are unchanged. No new retries or broader process control.

## Explicit residual boundary

This fix covers failures in the existing cleanup and final provenance stages.
Pre-try input/initial-provenance errors, the final `acceptance.json` write,
stdout printing, and uncatchable termination remain outside this bounded fix.
Unwritable evidence storage cannot guarantee a receipt. A stdout error can still
mask a prior exception after the receipt has been saved. This is not a claim of
durability against every finalization or I/O failure.

## Source-bound tests

All original 33,892 test-file bytes remain an exact prefix. Twenty-eight cases
are appended; no original assertion, marker, skip, timeout or default selection
changes. Original `run_v2_checks.py` and applicable pytest setup are retained.
No native model/runtime was downloaded or started.

- New selected RED contracts against the parent implementation: **27 failed,
  1 conservative-status control passed**. Original failures remain retained.
- Complete harness: **193 passed**.
- Harness plus adjacent original verification-runner contracts: **198 passed**.
- Complete existing infrastructure: **352 passed**.
- Final combined harness and infrastructure run: **545 passed**, zero
  failures/errors/skips, with JUnit and original runner/source receipts. These
  selections overlap; their counts must not be added together.
- `git diff --check` and targeted Python compilation pass.
- Ordinary read-only review found no blocker in the scoped change and checked
  40 additional in-memory exception combinations, including KeyboardInterrupt
  and SystemExit identity preservation. It reproduced and disclosed the residual
  stdout-error limitation. This is not the historical independent security audit.

Final 1,782-input source-map SHA256:
`7dde8794a29ceeaab2741ca283fe526f95d37813db8ba5f50b503e06654e09de`.
Every GREEN receipt matches this source, with unchanged before/after maps and
verified log hashes. The original RED has its own baseline source identity.
Receipts/logs are preserved losslessly under
`docs/delivery/v2-development/m4-receipt-*.json.gz` / `.log.gz`; the final combined
run also has JUnit `.xml`. The lossless evidence index records raw and compressed
hashes; uncompressed originals remain in the working archive. The original
implementation diff and timestamped development audit are retained separately.

## Complete collection is inventory, not execution

The worker collected 12,159 nodes. Independently, the unchanged V2 generator
completed two full unfiltered collections with identical ordered classifications
and no errors, then explicitly wrote the separate V2 manifest. There are **28
added nodes** relative to the parent's 12,131. Every prior node remains in
relative order, with unchanged historical skip maps and external gates.

The frozen V1 manifest is byte-identical at SHA256
`6457dd4cae85adee42486ef503fdb1cdabcdaf6eb9667eff3e2e97d05d040262`.
The separate generated V2 manifest SHA256 is
`ddb6f159cead52838829aaf6a3fe0be51e6c78cde67239962a7c2454a300b31a`.
The generator, frozen inventories, CI workflows and strict gates were not edited.
Two original compressed inventories and `m4-receipt-inventory-proof.json` retain
the exact comparison. Collection establishes no passed-test or full-coverage
result.

## Hosted CI and publication boundary

Parent-SHA Cloud runs
[push 38113440241](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/38113440241)
and [PR 38113445510](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/38113445510)
were still running at the preserved pre-publication observation. Each had
successful hosted Windows contract/package, Creative browser, independent-media
browser and original File TCP jobs; backend execution and frontend aggregate
were still pending. This is no complete parent-SHA acceptance result and no
user-Windows acceptance. R123 had succeeded within its historical RED-reproduction
scope; both Interop runs were still in progress.

No manual cancellation or rerun is performed. The existing Cloud workflow has
`cancel-in-progress: true`; a new branch update may supersede old execution.
Any later cancellation must remain incomplete evidence, not be called a pass.
New source needs its own naturally triggered hosted results. Historical capacity
limits, settling failures, real adaptation/quality and native acceptance remain
open.

Publication stays on the existing development branch and Draft PR. No main
merge, release, V1 modification or PR-body update is part of this commit.

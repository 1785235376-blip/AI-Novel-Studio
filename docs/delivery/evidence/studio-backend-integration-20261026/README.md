# Evidence index — Studio backend integration 2026-10-26

These are actual test receipts from this delivery, including failures. Logs and
JUnit use normalized checkout/user paths and hostname; outcome counts and failure
messages are preserved. No original user project data, keys or database credentials
are included. Screenshots show only the synthetic browser project.

## Executed checks (overlap; do not sum)

| Run | Observed result | Receipt |
| --- | --- | --- |
| M0 old packaged network-blocked runner | 2 failed; Windows Proactor socketpair incompatible | `coordinator/m0-smoke.*` |
| M0 corrected isolated local runner | 2 passed | `coordinator/m0-local-runner.*` |
| Queue/source regressions before production repair | 2 failed / 1 passed | `coordinator/studio-loop-red.xml` |
| Implementer complete lifecycle/configuration | 16 passed | `coordinator/studio-loop-expanded2.xml` |
| Independent frozen storyboard adversarial tests | 12 passed | `independent/independent-v2-final.xml` |
| Original application, real HTTP, separate process restart through both API mounts | 2 passed | `coordinator/live-http-both-mounts.*` |
| Original File keyed-generation preservation | 49 passed | `coordinator/file-keyed-preservation-isolated.*` |
| Windows baseline asset cold query | failed, errno9 → 503 | `contract/asset-query-baseline*.log` |
| SQLite fixture handle lifetime prior to correction | 8 passed / 1 failed, WinError5 | `contract/asset-index-portability-after.*` |
| Original asset query/index after durability+fixture repair | 46 passed | `contract/asset-portability-final*` |
| Independent correct-byte metadata counterexample before native fix | 1 failed | `independent/asset-independent-signature.xml` |
| Corrected original recovery before native fix | 25 passed / 6 skipped / 1 failed | `independent/asset-independent-recovery-corrected.xml` |
| Original recovery plus native Windows implementation tests | 30 passed / 6 skipped | `coordinator/asset-native-recovery.xml` |
| Independent asset/regression group on frozen native source | 77 passed / 6 skipped | `independent/asset-independent-native-final.xml` |
| Expanded independent native/fault tests | 8 passed / 1 privilege-related skip | `coordinator/final-native-independent-expanded.*` |
| Combined production-freeze regression, 14 test files | **248 passed / 6 skipped / 1 strict xfail** | `coordinator/final-combined-freeze.*` |
| Confirmed frontend 03e8034a contract | 10 passed / 1 strict xfail | `contract/frontend-confirmed-03e8034a.*`, coordinating final contract receipt |
| Confirmed frontend 03e8034a explicit expected-failure replay | 1 failed: `canvas_image_node` rejected | `contract/frontend-confirmed-03e8034a-failure.*` |
| Unchanged confirmed-frontend tests: DualStack, ImageDualGate, VideoDualGate, themeCanvasTokens | 4 files / 22 tests passed | `coordinator/frontend-03e8034a-original-checks.log` |

The combined regression ran frozen production `29d0bfcd503942c92718bf7345a104666951c60a`
with the corrected recovery fixture. The later independent test-only additions
were separately rerun (8 passed / 1 skipped). All three changed production files
remain byte-identical to that production freeze. Final changed-file hashes are
in `SOURCE_SHA256.txt`; the final complete delivery SHA/tree is read back from Git
and the remote after publication and included in the final handoff response.

Six skips are original POSIX SIGKILL contracts on a Windows host. The separate
real symlink case is skipped because privilege 1314 is unavailable; no additional
privilege was requested. Native error/reparse-attribute checks were simulated
and must not be described as a real symlink test.

The strict xfail is a known, unresolved **actual frontend wire incompatibility**,
not a pass. The explicit `--runxfail` log preserves the failure. Prior parent-only
and provisional-target logs remain historical; they do not establish current
frontend acceptance. The real new double canvas currently has no execution HTTP
caller and says so in the browser. The backend Mock chain cannot close that UI gap.

`studio-regression-initial.log` was interrupted after failures, before a complete
report; `file-keyed-preservation.log` was interrupted while concurrent runs shared
the earlier runner directory. Neither is a completed green run. Both are retained.
The runner now creates a distinct UUID directory for each invocation. Completed
replacement runs are listed above. Initial development fixture/config errors also
remain in the collected XML; they are not silently promoted into product failures
or final passing totals.

## Browser evidence

- `browser-03e8034a-dualcanvas-dark.jpg`
- `browser-03e8034a-dualcanvas-light.jpg`
- `browser-03e8034a-observed-state.txt`
- `browser-03e8034a-console-errors.json` (zero observed browser errors)

The exact frontend checkout remained read-only. Browser steps created a synthetic
novel via real API, entered IMAGE, opened canvas, selected professional mode,
observed the stacked local canvases and execution-unavailable message, and switched
between dark/light themes. This proves entry/theme/display and the explicit blocker.
It is **not** browser generation/candidate/review/writeback acceptance.

## Reproduce the combined backend group

```text
python scripts/run_studio_backend_tests.py -q -o faulthandler_timeout=45 tests/test_studio_backend_integration_v2.py tests/test_studio_frontend_alignment_v2.py tests/test_studio_process_reopen_v2.py tests/test_studio_integration_independent_v2.py tests/test_studio_production_query.py tests/test_cloud_formal_canvas_node.py tests/test_cloud_canvas_node_resume.py tests/test_cloud_canvas_create_recovery.py tests/test_file_keyed_activation.py tests/test_studio_asset_query.py tests/test_studio_asset_query_indexed.py tests/test_asset_query_index_recovery.py tests/test_asset_index_publication_independent_v2.py tests/test_asset_query_windows_signature.py
```

The new independent cases make a fresh reproduction collect more tests than the
earlier 248-pass receipt; do not rewrite that historical result. The confirmed
frontend contract was also rebound and rerun after the initial combined receipt.

Original source freezes/recovery points:
`ffe19379` backend start; `caa7c1ce` queue/source repair;
`29d0bfcd` final three-production-file freeze;
`51014e08` independent native test integration;
`89bcabf6` confirmed frontend contract integration.
All are retained in the delivery branch history. No reset/force-push was used.

Real model/GPU, real PostgreSQL, cloud executor, packaged installer and GitHub
Actions are **NOT_RUN**. No billing/account changes, installation, release or
deployment occurred. Windows Python/File, original HTTP processes and browser
inspection are actual local-host results and are not called cloud test runs.

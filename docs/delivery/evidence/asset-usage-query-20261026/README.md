# Asset usage query evidence

All data are synthetic File fixtures on Windows. The original app and original
authorization/read owners are used. HTTP fixtures mount `app.main:app`; the
fresh-process measurement starts a new interpreter using the original assembly.
They do not constitute browser, PostgreSQL, real model or hosted Actions evidence.

`compat/m1-baseline.receipt.json` binds the baseline-product compatibility run
to its exact harness commit and source hashes; baseline product source equals
`8ea45399816bf74783c4f01247b440ce4a82b5ba`. Earlier `compat/m1*.log` files retain
exploratory measurements and are explained by `compat/README.md`.

`coordinator/baseline-m0-m1.*` is an exploratory 44-pass run made while core
implementation was being edited. Its receipt explicitly reports dirty source;
it is not frozen acceptance evidence and its count is not added to final groups.
Initial pre-parallel M0 original asset query test completed 37 passed with 3
warnings at the fixed baseline; final frozen regression is recorded separately.

The frozen source is `554de521fb2640152408bcede62cbd21d3eaab49`, tree
`9a1ad60c58b42bf7d0b740048e7a34b5f997c642`; see `source-manifest.json`.
Final groups are 192 related regression passes, 51 independently authored
counterexample passes, 10 performance/scale passes and 6 coordinator probe
passes, reported separately rather than added as a unique total.

- `coordinator/final-regressions-supported.*`: 192 passes; exact commands and
  all source hashes in the receipt.
- `independent/final-independent.*`: 51 passes from the separate frozen tree;
  the independent unit authored/reviewed the tests before its model quota ended.
  Its running process completed; the coordinator verified the receipt and hashes.
- `compat/final-measurements.*` and `compat/metrics/*.json`: 10 passes, actual
  per-page IO/reader calls/response bytes/time/Python-allocation peaks. The fresh
  process uses original application assembly; ASGI HTTP is labeled separately
  from the additional real socket test. OS caches were not cleared.
- `coordinator/final-supplemental-corrected.*`: 6 passes, including saved Graph
  consumer removal/recreation and an admission-only PostgreSQL budget unit probe.
  This does not claim a PostgreSQL database was run.
- `coordinator/final-regressions.*` retains the original stopped run: 39 passes,
  1 failure in the existing asset-list durable cursor. The same case fails at
  fixed baseline (`baseline-cursor-refusal.*`) due to POSIX-only key-loader APIs.
  Remaining cases of that cursor file are NOT_RUN, never counted as passing.
- `coordinator/final-supplemental.*` retains a failed mock-backend API probe
  (5 passes/1 failure): the original authority rejected missing PostgreSQL
  configuration before query admission. The corrected unit probe is distinct.
- `coordinator/final-loopback.*` retains the initial test-path error;
  `final-loopback-corrected.*` retains a subsequent all-file snapshot failure:
  `/api` returned all 540 references but created one original operational lock
  file after data was copied to a new absolute path. Its business data stayed
  unchanged. No product source was modified to remove or hide that coordination.
  Retained executable test revisions and their hashes identify these probes.
- `coordinator/final-loopback-observed.*`: **1 passed**, original `app.main:app`
  in a separate uvicorn process, real loopback TCP HTTP. Each API alias returned
  all 540 saved pins in six pages without duplicates/omissions. Business files
  were identical. The first alias created one original coordination lock file;
  the second created none. This operational write is explicitly retained.

The final source remains PARTIAL: scope/asset-metadata reads have hard budgets;
the entire authorization chain, CPU and process memory do not. Strong ABA,
durable/cross-worker snapshots and unsupported dependencies remain unproven.
First-use coordination locks can be created by original File readers; zero
business-data mutation is distinct from zero physical writes.

Only completed strict receipts with
`source_unchanged_during_run=true` support frozen-source claims. Skipped and
expected-failure cases are distinct from passing cases.

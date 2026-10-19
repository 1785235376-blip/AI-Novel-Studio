
# Round-3 closeout evidence: D-24 regression observability, empty-parameter audit edge, diagnostic/evidence corrections (2026-10-19)

- Start SHA: `68b5e0c8d5ecfc24131e75c544449b82b632186b`
- Execution SHA (closeout verification runs): `5e27881967fd4dde2dcd7b6ab11c35f7ec1d12b0`
- Delivery SHA: the commit that adds this evidence directory (docs/evidence only on top of the execution SHA).
- Environment: Windows 11 24H2; disposable PostgreSQL 16.15 (portable build, loopback 127.0.0.1:55432,
  fresh database); Python 3.11 virtualenv with the committed constraints; no model calls, no cloud.
- Host paths were redacted (`[repo]`, `[workspace]`, `[userprofile]`, `[engineering-runs]`,
  `[portable-postgres-bin]`); XML files were re-parsed after redaction.

## 1. Connection-reuse regression: what is observed

The D-24 regression no longer compares `pg_stat_activity` snapshots (a new-connection-then-close
loop can leave the snapshot unchanged) and no longer relies on `pool.checkedout() == 0` alone (an
implementation that bypasses the pool also reports 0). Starting from the fixed read window:

1. one **warm-up** `store.read` runs before monitoring (pool/driver initialisation excluded);
2. a **monitor window** installs two independent observers for exactly 50 real reads:
   - a counter on `psycopg.connect` itself, which also sees the old out-of-pool path - not only
     SQLAlchemy pool `connect` events;
   - SQLAlchemy `checkout`/`checkin` events on the target engine's pool (actual pool borrows);
3. the window ends with `pool.checkedout() == 0`, and both observers are removed in `finally`;
4. reads assert real database content (a seeded marker returned by every read), so a failed read
   cannot silently satisfy the counter checks.

Contract assertions for the 50 reads:

- `new_physical_connections == 0` (no new backend, whether through the pool or outside it);
- `pool_checkouts == 50` and `pool_checkins == 50` (every read borrowed exactly once from the
  target pool and returned it);
- `checked_out_after == 0`; `reads_completed == 50`.

## 2. Counter-example: old path rejected by the same contract

The test temporarily sets `ExperimentalStore._connect` to the old direct `connect()` helper inside
the test only (restored in `finally`; no production switch), seeds the same marker and runs the same
50 reads. Measured at execution SHA `5e278819`:

| Metric | Old path replay | Pooled path |
| --- | ---: | ---: |
| reads_completed | 50 | 50 |
| new_physical_connections | **50** | **0** |
| pool_checkouts | **0** | **50** |
| pool_checkins | 0 | 50 |
| checked_out_after | 0 | 0 |
| read_window_seconds | 1.344 | 0.016 |

The replay completes all 50 real reads and is rejected **only** by the connection-reuse contract;
the assertion message recorded in `console-pool-regression-pg-closeout.log` is:

    POOL_CONTRACT_REJECTED store reads created new physical database connections instead of
    borrowing from the target pool: {"checked_out_after": 0, "new_physical_connections": 50,
    "pool_checkins": 0, "pool_checkouts": 0, "reads_completed": 50, ...}

After restoring the pooled path, the same contract passes with `new_physical_connections=0`,
`pool_checkouts=50`, `pool_checkins=50` and the two metrics are printed for the record in the same
console log.

## 3. Empty-parameter skip-audit edge (D-25 closeout)

`scripts/audit_local_ci_skips.py` now preserves the exact suffix after the leading backend token
instead of rebuilding it from a stripped `rest` value: `[postgres-]` pairs with `[file-]` (an empty
trailing parameter) and must **not** pair with `[file]` (no trailing parameter). New tests:

- `[postgres-]` + `[file-]` -> paired (legal case, exit 0, test-local-ci-skip-audit passes);
- `[postgres-]` + only `[file]` -> PostgreSQL-only, audit fails with `--fail-on-pg-only`;
- bare `[postgres]` + `[file]` still pairs; the pre-existing cross-module/different-parameter/
  missing-control/skipped-control/unknown-skip/failed-node cases did not change.
- Re-auditing the committed round-2 LOCAL-02 JUnit: `467/467` pairs matched, 0 PostgreSQL-only,
  0 unknown skips (`skip-audit-historical.json`). Historical test results were not modified.

## 4. Verification runs (execution SHA 5e278819)

| Run | Result |
| --- | --- |
| Real-PG pool regression file, fresh database | **6 passed** (contract metrics above recorded in console log) |
| Same file, File profile | **6 skipped** - every case skipped by `postgres_backend_only`; exit 0 recorded separately, **not** a pool PASS |
| Unit/regression suite (audit, connection bounds, evidence index, runner output, redaction) | **29 passed** |
| Evidence index check over committed evidence | **PASS** - 8 declared paths exist, 0 missing, 0 invalid XML |
| Historical LOCAL-02 JUnit re-audit | **467/467** pairs, 0 PostgreSQL-only, 0 unknown skips |

## 5. Evidence corrections from round 3

- `20261019-r3-d24/verification-summary.json` pointed at runner-side labels instead of the archived
  prefixed filenames (`d24-full-file-pg.xml` vs `junit-d24-full-file-pg.xml`). Fields now point at
  real archived files; `console` is `null` where nothing was archived. Correction record:
  `20261019-r3-d24/CORRECTIONS.md`.
- `pool-regression-file` was stored as `PASS` with an empty summary. The recovered original run
  shows **5 skipped, 0 failed, exit 0**; it is now recorded as `SKIPPED_NOT_APPLICABLE` in the old
  receipt and as a historical recovered run here (`historical-pool-regression-file.*`). The exit
  code is recorded separately and is not a pool-behaviour verification.
- New `scripts/check_local_ci_evidence_index.py` (with regression test
  `tests/test_local_ci_evidence_index.py`) fails when a receipt declares a file that does not
  exist; it is run in this closeout (`evidence-index.json`).

## 6. Diagnostics provenance and limitations

Archived under `diagnostics/`: the Round-3 driver/plugin scripts, probe metrics JSONs, surviving
post-fix watchdog thread-dump sample and re-read connection counts. Counter definitions, the exact
`D24_FORCE_UNPOOLED` replacement, which connections are counted, and the limits are documented in
`diagnostics/README.md`. Key limits:

- the **pre-fix timeout thread dump is unrecoverable** (same log path reused and overwritten);
- `hooks` counts entries into `_finish_terminal_hook`, not executed callbacks/settlements - it must
  not be read as duplicate settlement;
- connection authorization lines include the driver's setup connections; probe pool counters are
  pool-only and 0 does not mean "no physical connections";
- failed replay and successful pooled run did not complete the same workload (173 vs 427 reads);
  the new closeout regression compares both paths on the identical 50-read workload instead.

## 7. Not run / still open

- Complete real PostgreSQL and File suites: not run this closeout.
- D-20: untouched, OPEN. D-17: unchanged, MITIGATED / INTERMITTENT.
- Hosted CI: `HOSTED_BLOCKED_NO_RUNNER`; Linux local CI: NOT_RUN.
- V2 remains NOT RELEASE_READY; DIF / IMAGE-COMIC / Master Roadmap gates unchanged. D-24 stays
  fixed; this closeout only strengthens its regression and evidence.

## 8. Reproduction commands

    # Real-PG pool regression (fresh database; portable PostgreSQL bin path omitted)
    python scripts/run_v2_postgres_checks.py --pg-bin "<portable PostgreSQL bin>" --data ".runtime\pg-closeout\data" --port 55432 --database <fresh-db> --fresh-database closeout-pool-pg -- python -m pytest -q -s -p no:cacheprovider --junitxml "junit-pool-regression-pg-closeout.xml" tests/test_postgres_pool_transaction_semantics.py

    # File-profile control (all cases skipped by the PostgreSQL-only marker)
    python scripts/run_v2_checks.py closeout-pool-file -- python -m pytest -q -p no:cacheprovider tests/test_postgres_pool_transaction_semantics.py

    # Unit / audit / evidence-index checks
    python -m pytest -q tests/test_local_ci_skip_audit.py tests/test_postgres_connection_bounds.py tests/test_local_ci_evidence_index.py tests/test_run_v2_checks_output.py tests/test_local_ci_evidence_redaction.py
    python scripts/check_local_ci_evidence_index.py
    python scripts/audit_local_ci_skips.py --junit docs/v2/engineering/evidence/local-ci/20261019-r2/LOCAL-02-junit.xml --fail-on-pg-only

## 9. Evidence files (SHA256, redacted committed copies)

| File | Bytes | SHA256 |
| --- | ---: | --- |
| console-pool-regression-file-closeout.log | 274 | 70d66338cb09e65875d87d488d6ce05fc6879a7180c8ebe6a1d52a72d883ce21 |
| console-pool-regression-pg-closeout.log | 18,112 | 38ead846e7798099a46e5b3a13b4acd201f86c79eab1f3a3d30e5d810bbd01e8 |
| console-unit-tests.log | 101 | d601df29d4b25f65f611b2f7a385c1d16c3696bf9ba5644948fcac62c8fea678 |
| diagnostics/connection-counts.txt | 1,410 | 79603ad383a3e57132654faa709ad7164c54fbf7be81e07fd6c928a4f1d3577f |
| diagnostics/d24_driver.py | 6,123 | 69cd234825c16d07815018ac44d4b9c950c0597adf6abf866bca5c0fbf722588 |
| diagnostics/d24_probe.py | 5,330 | a04d3e7a5971c60d37315282bfc7c2b9d0e07372b0a63cb49d93c226f6133e81 |
| diagnostics/metrics-pooled-d07-storm.json | 271 | 73ee1ca6d1b7364efb58576c2ee96fc10d8942908e8f1e5b45a95a196dc90967 |
| diagnostics/metrics-pooled-d24.json | 277 | 8e23b48256c49542646239cc59fbbad945c4bf9c7ffac1768cab3c82702d3731 |
| diagnostics/metrics-unpooled-replay-d24.json | 276 | 777620219e38ae8eb085cfdc7a00f63cb9dc50e54e936026e39a53f322fd046c |
| diagnostics/README.md | 4,833 | 3afc671c362bf804a19120a8ca5961e5651c0340fb1ab487f95af2dcdfb4215b |
| diagnostics/thread-dumps-postfix-sample.txt | 1,172 | 2150688a74ad1f3e1e71f747096a262c029959b31d4df9a621d6538f66ddd51b |
| evidence-index-console.log | 182 | a3439fc49dd30b7374b674d252bd054938596324d952bfc6cc3ce22c93c998f2 |
| evidence-index.json | 173 | f9afce834dd865c2cbac58c9f7186ed64d6db2d95b00ab2fd08ea6b1cd2289d0 |
| historical-pool-regression-file.log | 261 | 92c71518c06d1c6cd4a717fa04b89f8f64fbbddd786cbd44c194bcb7103ec6cd |
| historical-pool-regression-file.xml | 2,318 | bb1a36d5676924ec5255139bfa14c549d115f241e6287260927a926d6dbf5cfa |
| junit-pool-regression-file-closeout.xml | 2,743 | 5335eb6e0832e78f62e9da05b843fc7eb464b91376c8b69b02e0cf669177a256 |
| junit-pool-regression-pg-closeout.xml | 1,101 | f719cebc29f7432a1b574fbef83b98ce6113f9a671582013a253756fab182ba3 |
| skip-audit-historical-console.log | 823 | 3ebb7f2372608f5829ca095478298285ef6b5c5205115811bc3cdef922f5927d |
| skip-audit-historical.json | 5,570 | 0803d94c45782a92d35f9cdd0cb5d8eaa9014027f393721af86928e7c5e9bdd3 |
| verification-summary.json | 2,213 | 43517208b0b4a943597c0740925a54583766b8e05e5eba177b7c0812f9e74c2c |

XML validity after redaction:

| File | Status |
| --- | --- |
| historical-pool-regression-file.xml | OK |
| junit-pool-regression-file-closeout.xml | OK |
| junit-pool-regression-pg-closeout.xml | OK |

The closeout evidence directory is validated by `scripts/check_local_ci_evidence_index.py`;
`verification-summary.json` here points only at files that exist in this directory.

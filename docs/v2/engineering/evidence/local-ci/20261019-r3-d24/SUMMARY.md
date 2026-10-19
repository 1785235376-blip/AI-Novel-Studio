
# Round-3 evidence: D-24 fix, targeted D-07 regressions and audit corrections (2026-10-19)

- Start SHA: `5c1f39201eb77834ffb193ead17e9b9a2b0c932f`
- Execution SHA (all runs below): `415cbcc20958409c3aca94312e3961ac7766a2e2`
- Delivery SHA: the commit that adds this evidence directory (docs/evidence only on top of the execution SHA).
- Environment: Windows 11 24H2; disposable PostgreSQL 16.15 (portable build, loopback 127.0.0.1:55432,
  fresh database per case); Python 3.11 virtualenv with the committed constraints; no model calls, no cloud.
- Host paths in these files were redacted to `[repo]` / `[workspace]` / `[userprofile]` / `[engineering-runs]`;
  XML files were re-parsed after redaction (see the XML table below).

## Root cause of D-24 (measured)

The PostgreSQL experimental store opened **one new PostgreSQL connection per metadata read**
(`ExperimentalStore._connect -> psycopg.connect`). A failing node run performs hundreds of reads; on Windows
each fresh backend costs ~30 ms under load, so the mock generation worker repeatedly blocked in connection
establishment and never reached the terminal hook within the fixture's 8 s wait budget while `job.status`
stayed `GENERATING`. The terminal hook was registered and callable; metadata-read connection churn starved the
worker.

Instrumentation used (test-only, not committed): a pytest plugin wrapping `JobManager` persist/hook/emit,
`ExperimentalStore.read`, the bounded connect helper and SQLAlchemy pool events, plus a thread-dump watchdog.
A single diagnostic switch (`D24_FORCE_UNPOOLED`) replayed the old store path in the same working tree, so both
sides of the comparison below use the same commit, environment and test node.

## Fix (execution SHA 415cbcc2)

- `app/repositories/postgres/connection.py`: new `engine_for_url(url)` - one process-cached SQLAlchemy engine
  per normalized DSN with a bounded pool (4 + 4 overflow, `pool_pre_ping`, libpq `connect_timeout`,
  `timezone=UTC`) - plus `clear_engine_cache()` for tests/shutdown. `pooled_connection()` semantics are
  unchanged: clean block commits, raised block rolls back, connection always returns to the pool.
- `app/experimental/store.py`: `_connect()` returns `pooled_connection(engine_for_url(self.database_url))`
  instead of opening a new connection per read/transaction. No timeout increase, no skipped test, no assertion
  weakening, no File/mock substitution, no authority-bypass change, no provider replay.

## Same-metric connection comparison (D-24 representative node, real PG, fresh DB)

| Metric | Unpooled replay (old store path) | Pooled (fix) |
| --- | ---: | ---: |
| Cumulative direct `psycopg.connect` attempts | 466 | 0 |
| Store reads | 173 (before the 8 s deadline failure) | 427 |
| Cumulative new physical connections (SQLAlchemy pool `connect` events) | n/a (bypasses pool) | 2 |
| Pool checkouts | 0 | 825 |
| Peak concurrent checked-out connections | n/a | 2 |
| Pytest result | FAIL in 16.0 s (wait_job deadline) | PASS, pytest 3.94 s |

Raw metrics: `metrics-unpooled-replay-d24.json`, `metrics-pooled-d24.json`, `metrics-pooled-d07-storm.json`.

## Verification runs (all bound to execution SHA 415cbcc2)

| # | Label | Scope | Result | Evidence |
| ---: | --- | --- | --- | --- |
| 1 | d24-node-a-pg | representative D-24 node, fresh PG DB A | 1 passed, 4.66 s | junit-d24-node-a-pg.xml |
| 2 | d24-node-b-pg | representative D-24 node, fresh PG DB B | 1 passed, 4.85 s | junit-d24-node-b-pg.xml |
| 3 | d24-full-file-pg | `tests/test_v2_text_execution_receipts.py` PostgreSQL variants | 28 passed / 27 skipped, 0 failed, 44.93 s (was 27 failed / 1 passed / 27 skipped, 379 s) | junit-d24-full-file-pg.xml |
| 4 | d24-full-file-file | same file, File backend control | 28 passed / 27 skipped, 0 failed, 59.39 s | junit-d24-full-file-file.xml |
| 5 | d07-storm-node-pg | D-07 connection-storm interop node, fresh PG DB | 1 passed, 6.42 s | junit-d07-storm-node-pg.xml |
| 6 | pool-regression-pg | real-PG pool contract regressions (new file) | 5 passed, 2.49 s | junit-pool-regression-pg.xml |
| 7 | pool-regression-file | same file in File mode | skipped (PostgreSQL-only marker) | junit-pool-regression-file.xml |

Run logs: `console-*.log` (pytest console, redacted), `driver-*.log` (instrumented drivers),
`verification-summary.json` (machine summary produced by the orchestrator).

The affected-file tests assert the observed job reaches a terminal state, the terminal hook completed, the
persisted reload equals the in-memory result, no duplicate dispatch/settlement/archive happened, and the
original worker thread is joined and no longer alive - the full-file pass therefore exercises those business
assertions rather than only the wait condition.

## D-07 targeted real-PostgreSQL pool regressions (case 6)

New `tests/test_postgres_pool_transaction_semantics.py` (marker `postgres_backend_only`), against the real
SQLAlchemy pool and real PostgreSQL:

1. a clean `pooled_connection` block commits the write and a later borrow reads it;
2. an exception inside the block rolls the write back;
3. after a failed transaction (`SELECT 1/0`) the next borrow works normally;
4. the experimental store uses the cached engine/pool (same engine object for the same DSN);
5. 50 consecutive metadata reads add at most 2 backends and the pool is fully checked in afterwards.

`engine.pool.checkedout() == 0` is asserted after each case, i.e. borrowed connections are returned.

## Skip-audit tool correction (D-25)

`scripts/audit_local_ci_skips.py` now requires exact control pairing: same module/class, same function,
identical parameters after normalizing the leading `postgres` token to `file`, and the control must be in the
passed set. `tests/test_local_ci_skip_audit.py` (8 cases) covers one legal pairing plus cross-module same-name,
different-parameter, missing-control, skipped-control, unknown-reason, symlink-allowed and failed-node cases.
Re-auditing the committed round-2 LOCAL-02 JUnit: **467/467 PostgreSQL skips paired, 0 PostgreSQL-only,
0 unknown skips** (`skip-audit-r3.json`). Historical test results are unchanged.

## Corrected round-2 claims

- Only the representative D-24 node was compared with the pre-fix baseline `a517e0a2` (single-node run,
  identical failure in 17.22 s); the other 26 failing nodes were not individually baseline-compared. Round 3
  fixes the shared root cause and all 27 now execute and pass.
- The bounded retry loop exists in the `connect()` helper, which no current production entry point uses;
  production pooled paths and the backup/restore admin connection use libpq/engine `connect_timeout` only.
- Round-2's "1,210" (cumulative instrumented connect attempts, log not archived) and "5" (cumulative
  connection-authorization log lines) were different metrics and are no longer presented as a before/after
  pair; this evidence uses the same-metric table above.

## Not run / still open

- Complete real PostgreSQL suite (~4.8k tests) and complete File suite: not run in round 3.
- D-20 (full-suite ordering hang): untouched, OPEN.
- D-17 (intermittent Windows revocation): unchanged, MITIGATED / INTERMITTENT.
- Hosted CI: `HOSTED_BLOCKED_NO_RUNNER`. Linux local CI: NOT_RUN (no Node/python3-venv; no new system-level
  dependencies were added).
- V2 release gates (DIF, IMAGE-COMIC, Master Roadmap) unchanged; V2 is still NOT RELEASE_READY.

## Reproduction commands

PG runs were executed from the repository root with the portable PostgreSQL binary directory:

    python scripts/run_v2_postgres_checks.py --pg-bin "<portable PostgreSQL bin>" --data ".runtime\pg-r3\data" --port 55432 --database <fresh-db-name> --fresh-database <label> -- python -m pytest -q -p no:cacheprovider --basetemp ".runtime\v2-checks\<label>-pytest" --junitxml "<label>.xml" <test args>

The File control uses `scripts/run_v2_checks.py <label> -- python -m pytest ...` (File backend, no PostgreSQL).

Instrumented measurements:

    $env:D24_PREFIX="d24-unpooled-replay"; $env:D24_FORCE_UNPOOLED="1"; $env:D24_NO_WATCH="1"; $env:D24_QUIET="1"
    & .venv\Scripts\python.exe "Engineering-Runs/local-ci-round3-20261019/d24_driver.py"
    $env:D24_PREFIX="d24-fixed-metrics"; Remove-Item Env:D24_FORCE_UNPOOLED
    & .venv\Scripts\python.exe "Engineering-Runs/local-ci-round3-20261019/d24_driver.py"
    $env:D24_PREFIX="d07-storm-metrics"; $env:D24_NODE="tests/test_local_interop_cross_process_host.py::test_real_host_api_metadata_guidance_diagnostics_verifier_and_revocation[postgres]"
    & .venv\Scripts\python.exe "Engineering-Runs/local-ci-round3-20261019/d24_driver.py"

Skip audit:

    python scripts/audit_local_ci_skips.py --junit docs/v2/engineering/evidence/local-ci/20261019-r2/LOCAL-02-junit.xml --fail-on-pg-only --json-out skip-audit-r3.json

## Evidence file hashes (SHA256, redacted committed copies)

| File | Bytes | SHA256 |
| --- | ---: | --- |
| console-d24-full-file-file.log | 305 | fe19eda6d02b56622b13422c54f613a479838cbb3e65dfba5e1307e8de8d561b |
| console-d24-full-file-pg.log | 17,010 | 3fa6b583ac2f0d5bf5acec7920469f90c8e64d6c68a64c4874645a1740c5c6ed |
| driver-pooled-d07-storm.log | 434 | 3d562b9c601cfb15cdc238ddff3107df47039759e68f363ef8a750030a05d6a8 |
| driver-pooled-d24.log | 428 | 60e3b8f72c873ef83e4059caa070bf03c99294b28e44284b4f8c593d5be03c8f |
| driver-unpooled-replay-d24.log | 429 | 761fd2d19ace83782dfeb7aea53f338bc44e2c44388f0f2010269d77ba6629ae |
| junit-d07-storm-node-pg.xml | 410 | d08d530e609d28b9c5116c8084a70a479c1adbdab2908a17c15b44dedc6a39fc |
| junit-d24-full-file-file.xml | 16,937 | 1f01097a0dc06007613e48f3569bc8699fd5a88fc6a6c1571c2dc9d050832970 |
| junit-d24-full-file-pg.xml | 16,883 | e4c3190ad5c63e09860af138e74965dcbfcfbfaa05cdfb19b3d9400d181f11aa |
| junit-d24-node-a-pg.xml | 404 | c825ebbaadcf116a008a5224930fb5353a760b12f28de1eae24c75517246db9a |
| junit-d24-node-b-pg.xml | 404 | e09613e32ec3f58fa5f121f5b27e8fb84c4de3a95585c37703d73fd4ada962bb |
| junit-pool-regression-pg.xml | 952 | fd16e92e0f2609722dc993cb997f2403e082b148f1c2b5d2324b91a896b70000 |
| metrics-pooled-d07-storm.json | 271 | 73ee1ca6d1b7364efb58576c2ee96fc10d8942908e8f1e5b45a95a196dc90967 |
| metrics-pooled-d24.json | 277 | 8e23b48256c49542646239cc59fbbad945c4bf9c7ffac1768cab3c82702d3731 |
| metrics-unpooled-replay-d24.json | 276 | 777620219e38ae8eb085cfdc7a00f63cb9dc50e54e936026e39a53f322fd046c |
| skip-audit-r3.json | 5,570 | 0803d94c45782a92d35f9cdd0cb5d8eaa9014027f393721af86928e7c5e9bdd3 |
| verification-summary.json | 2,375 | 4f5b5c0469a1430f52adf6dc1f3660a7da2aa5a22cbdf3db8aae4fb7a7ea7ccd |

XML validity after redaction:

| File | Status |
| --- | --- |
| junit-d07-storm-node-pg.xml | OK |
| junit-d24-full-file-file.xml | OK |
| junit-d24-full-file-pg.xml | OK |
| junit-d24-node-a-pg.xml | OK |
| junit-d24-node-b-pg.xml | OK |
| junit-pool-regression-pg.xml | OK |

Unit/regression suite for the changed code (File environment, run before this evidence commit):
`tests/test_postgres_connection_bounds.py`, `tests/test_postgres_pool_transaction_semantics.py` (skipped in
File mode by marker), `tests/test_local_ci_skip_audit.py`, `tests/test_run_v2_checks_output.py`,
`tests/test_local_ci_evidence_redaction.py` - 25 passed.

## Round-3 closeout corrections (2026-10-19)

- `verification-summary.json` now points at the archived prefixed filenames and records
  `pool-regression-file` as `SKIPPED_NOT_APPLICABLE` (recovered original: 5 skipped, 0 failed,
  exit 0). See `CORRECTIONS.md` in this directory. The hash table above describes the
  pre-correction snapshot; refreshed hashes for the changed/new files:
  - `verification-summary.json`: ``VS_HASH``
  - `CORRECTIONS.md`: ``CORR_HASH``
- New closeout evidence (new runs at execution SHA `5e278819`, diagnostics provenance, evidence
  index check): `docs/v2/engineering/evidence/local-ci/20261019-r3-closeout/`. The pre-fix D-24
  timeout thread dump is not recoverable; `diagnostics/README.md` in the closeout directory records
  the counter definitions and limits.

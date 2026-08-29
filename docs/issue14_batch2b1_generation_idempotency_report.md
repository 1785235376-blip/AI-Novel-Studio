# Issue #14 Batch 2B-1 — Generation idempotency root-cause

This is not a V1.0 claim, not a DesktopHost DH-01–DH-08 PASS, and not a Release decision.

| Field | Value |
| --- | --- |
| Base main | `01cc304e3df5357160f3c98b2ef50b0d9ddf8d95` |
| Work branch | `fix/p0-generation-idempotency-root-cause` |
| HEAD SHA | branch tip at Draft PR open (see the PR) |
| Related issue | #14 (remains OPEN) |
| Frontend toolchain issue | #20 (UNCHANGED; not repaired in this batch) |
| Verdict | `TEST_STATE_CONTAMINATION_RECLASSIFIED` |
| Production change required | NO |

## Root cause

`tests/test_generation_variants_phase3.py::test_generation_is_idempotent_under_concurrent_submission` used a fixed header `Idempotency-Key: generation-race-unique` and asserted `len(created) == 1`.

`app.api._idempotency_store` is created at import as `IdempotencyStore(settings.data_path() / "idempotency.json")`. Default `data_path()` is repository-relative `novel_data/` (gitignored). `tests/conftest.py` does not isolate this store.

In-process, `_idempotency_execution_lock` already wraps `_cached_idempotent` → `_generate_once` → `_store_idempotent`. A cache hit must return the stored envelope and must **not** call `jobs.create`. That is correct product behavior. The test treated `created == 0` as a production failure.

## Matrix A — unmodified test, 20 independent pytest processes

Environment: Python 3.11.2; `uv pip install -e .[dev]` (not `.[vault]`); `STORAGE_BACKEND=file`; `env -i`; run-scoped TMP/basetemp; no user `.env`. Store path recorded only as repository-relative `novel_data/idempotency.json`. Key recorded only as `generate:continue:generation-race-unique`. No cache values, provider payloads, or user paths printed.

| n | result | key before | key after | note |
| ---: | --- | --- | --- | --- |
| 1 | PASS | NO | YES | `created=1`, `job_id=one-job` |
| 2–20 | FAIL | YES | YES | `created_len=0`; cached `job_id=one-job` |

**1 PASS / 19 FAIL.** This matches Batch 2A.2 isolation. It is reuse of a durable key, not a race.

## Matrix B — fresh store concurrency

Each round replaced `app.api._idempotency_store` with a new `IdempotencyStore` under a run-scoped tmp directory. Requests overlapped with a `Barrier` **before** POST. `jobs.create` used a controlled 10 ms delay (not random sleep). No user `novel_data` was read or written.

| concurrency | rounds | pass | fail | `jobs.create` | job_id |
| ---: | ---: | ---: | ---: | ---: | --- |
| 3 | 50 | 50 | 0 | 1 | same |
| 16 | 20 | 20 | 0 | 1 | same |
| 32 | 10 | 10 | 0 | 1 | same |

**80/80 PASS.** Envelopes were identical. No exception, deadlock, or timeout. A create-side Barrier deadlocks because create already runs under the execution lock; that deadlock is an artifact of waiting inside the lock, not a product bug.

## Matrix C — persisted replay contract

Pre-write the same operation+key success envelope into the test-only store, then POST.

| check | result |
| --- | --- |
| HTTP | 202 |
| body | cached envelope (`job_id=cached-job`) |
| `jobs.create` | 0 |

`created == 0` on replay is correct idempotency, not a product failure.

## Matrix D — contrast contracts

| contract | result |
| --- | --- |
| No `Idempotency-Key` | two requests create two jobs |
| Distinct keys | each key creates once |
| Operation namespace | `generate:continue` and `generate:rewrite` with the same key create separately |
| First `jobs.create` raises | no success cache; lock released (`join(5)`); second request creates and caches |

## Multi-process boundary

`threading.Lock` is process-local. Packaged backend starts:

`python -I -m uvicorn app.main:app --host 127.0.0.1 --port <port> --no-access-log`

There is no `--workers`. Official FastAPI / packaged runtime is a single process. This batch does not add file locks, database locks, Redis, schema, or migrations.

## Chosen conclusion

**Conclusion A: `TEST_STATE_CONTAMINATION_RECLASSIFIED`.**

Fresh-store rounds all passed. The durable fixed key explains the 19 subsequent isolation failures. Production code was not modified.

## Changes

| area | files |
| --- | --- |
| Production | none |
| Tests | `tests/test_generation_variants_phase3.py` (run-scoped store fixture); `tests/test_generation_idempotency_contracts.py` (replay, contrast, 100-round fresh-store stress) |
| Docs | this file; `docs/baseline_failure_registry.md`; `docs/test_report.md` |
| Frontend / schema / migration | none |

The original concurrent nodeid still asserts three overlapping requests on a **fresh** store return the same `job_id` and `jobs.create == 1`. Replay is a separate contract.

## Verification after the test change

| check | result |
| --- | --- |
| Targeted tests | 14 passed |
| 100-round fresh-store stress | 100/100 (in `test_generation_fresh_store_concurrent_submission_survives_repeated_races`) |
| Replay ×20 | 20/20 same cached envelope, `create==0` |
| Original nodeid ×20 independent pytest processes | 20/20 PASS **with leftover durable key still present** |
| Backend full run 1 | 909 passed, 3 failed, 28 skipped, 0 xfail; 27.14s; isolated `NOVEL_DATA_PATH` + basetemp |
| Backend full run 2 | 909 passed, 3 failed, 28 skipped, 0 xfail; 24.27s; second isolated data root |
| Remaining FAILED nodeids | `test_visual_continuity_reports_scene_jumps`; `test_preferences_are_explicit_and_separate`; `test_world_rule_payload_normalizes_terms` |
| Concurrent nodeid in FAILED set | no |
| NEW FAILURES / SKIPS / XFAILS | 0 / 0 / 0 |
| `git diff --check` | 0 |
| Secret / DSN / user-path scan of added lines | 0 |
| Frontend delta | 0 (toolchain uncertainty remains Issue #20) |

909 = previous integrated 901 passing + the previously failing concurrent nodeid now passing + 7 new contract tests.

## Safety boundary

| boundary | value |
| --- | --- |
| REAL PROVIDER REQUESTS | 0 |
| REAL POSTGRESQL OPERATIONS | 0 |
| REAL CREDENTIAL ACCESS | 0 |
| USER `.env` ACCESS | 0 |
| USER NOVEL DATA ACCESS | 0 |
| SCHEMA / MIGRATION CHANGES | 0 |
| vault extra | not installed |

## Not claimed

- Issue #14 is not closed
- Issue #20 is unchanged
- The three remaining production defects are not fixed
- V1.0 / DH-01–DH-08 / Windows / PostgreSQL / Provider / Release are not PASS
- Draft PR is not Ready and is not merged

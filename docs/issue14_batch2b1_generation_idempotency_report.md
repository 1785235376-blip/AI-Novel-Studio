# Issue #14 Batch 2B-1 — Generation idempotency root-cause

This is not a V1.0 claim, not a DesktopHost DH-01–DH-08 PASS, and not a Release decision.

Batch 2B-1.1 is documentation-only. It rebinds evidence to reviewed snapshots. Production, tests, frontend, and schema are unchanged.

| Snapshot | SHA | Meaning |
| --- | --- | --- |
| Batch 2B-1 task base / post-PR-19 main at work start | `01cc304e3df5357160f3c98b2ef50b0d9ddf8d95` | Tree used to implement tests and record `909/3/28` |
| Batch 2B-1 implementation / evidence HEAD | `5e7ab893aa09db08d0d9566e65e0edeb0e3c46d7` | Tests+docs at first independent review. Not the final PR HEAD after later documentation commits. |
| First independent-review main snapshot | `47906bdde775d4ab9c7a07449c1f60f0e4e5d300` | `origin/main` when PR #21 was already merged and the first review ran |
| First independent-review synthetic merge | `9f97c40c176bd5fd2a6f9a64bd4f4da7dd95ff2b` | GitHub merge of `47906bd` + `5e7ab89`. Pre-PR-23. Do not treat as the post-PR-23 merge candidate. |
| Batch 2B-1.1 correction-start main snapshot | `bc49b5d05ee934d948ab8784d52ba4481134ec0d` | Live `origin/main` when this documentation correction was authorized (PR #23 merged). Snapshot only, not a permanent current-main definition. |

| Field | Value |
| --- | --- |
| Work branch | `fix/p0-generation-idempotency-root-cause` |
| Related issue | #14 (remains OPEN) |
| Frontend toolchain issue | #20 (UNCHANGED; not repaired in this batch) |
| Verdict | `TEST_STATE_CONTAMINATION_RECLASSIFIED` |
| Production change required | NO |
| Post-PR-23 synthetic-merge verification | `PENDING NEW INDEPENDENT RE-REVIEW` |

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

**1 PASS / 19 FAIL.** This matches Batch 2A.2 isolation. It is reuse of a durable key, not a race. First request creates; later durable replays correctly create 0.

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

## Verification on the implementation tree

Bound only to **task base `01cc304e` + implementation/evidence HEAD `5e7ab89`**. This is not a PR #21 result, not a PR #23 result, and not live main.

| check | result |
| --- | --- |
| Targeted tests | 14 passed |
| 100-round fresh-store stress | 100/100 (in `test_generation_fresh_store_concurrent_submission_survives_repeated_races`) |
| Replay ×20 | 20/20 same cached envelope, `create==0` |
| Original nodeid ×20 independent pytest processes | 20/20 PASS **with leftover durable key still present** |
| Backend full run 1 | 909 passed, 3 failed, 28 skipped, 0 xfail; 27.14s; isolated `NOVEL_DATA_PATH` + basetemp |
| Backend full run 2 | 909 passed, 3 failed, 28 skipped, 0 xfail; 24.27s; second isolated data root |
| Remaining FAILED nodeids on this tree | `test_visual_continuity_reports_scene_jumps`; `test_preferences_are_explicit_and_separate`; `test_world_rule_payload_normalizes_terms` |
| Concurrent nodeid in FAILED set | no |
| NEW FAILURES / SKIPS / XFAILS | 0 / 0 / 0 |
| `git diff --check` | 0 |
| Secret / DSN / user-path scan of added lines | 0 |
| Frontend delta | 0 (toolchain uncertainty remains Issue #20) |

909 = previous 901 passing + the reclassified concurrent nodeid now passing + 7 new contract tests.

Collection size on this tree: task base 933 tests collected; implementation HEAD 940 tests collected.

## First independent-review snapshot (pre-PR-23)

Bound only to first-review synthetic merge `9f97c40` (parents `47906bd` + `5e7ab89`). Recorded by the independent Reviewer. This merge object is **not** the post-PR-23 candidate.

| check | result |
| --- | --- |
| Backend full run 1 | 960 passed, 4 failed, 28 skipped, 0 xfail; 27.42s |
| Backend full run 2 | 960 passed, 4 failed, 28 skipped, 0 xfail; 25.49s |
| Collection | first-review main `47906bd` 985; synthetic merge `9f97c40` 992 |
| PR #21 / PR #22 file overlap | 0 |
| Plugin + idempotency forward | 5/5; 60 passed |
| Plugin + idempotency reverse | 5/5; 60 passed |
| PR #22 attributable new failures / skips / xfails | 0 / 0 / 0 |

The four FAILED node IDs on that tree were:

1. `tests/test_p1_regression.py::test_visual_continuity_reports_scene_jumps` — known `PRODUCT_BASELINE`
2. `tests/test_user_preference_service.py::test_preferences_are_explicit_and_separate` — known `PRODUCT_BASELINE`
3. `tests/test_world_rule_payload.py::test_world_rule_payload_normalizes_terms` — known `PRODUCT_BASELINE`
4. `tests/test_import_parsers.py::test_pdf_fallback_extracts_simple_literal_text` — `ENVIRONMENT-SENSITIVE BASELINE / INVESTIGATION REQUIRED`

The PDF fallback failure reproduced on `01cc304e`, `47906bd`, `5e7ab89`, and `9f97c40`. It is associated with the truncated PDF fixture and `pypdf` behavior in the review environment. It is **not** introduced by PR #22, is **not** counted as a PR #22 product regression, was **not** repaired in this batch, and no Issue was opened for it. A specific `pypdf` version is not recorded here. Do not describe the four failures as four remaining product defects.

PR #21 added official declarative plugin-pack tests, so first-review merge collection is larger than `909/3/28`. Do not require `9f97c40` to reprint the implementation-tree count.

## After PR #23 (correction-start snapshot)

Correction-start main snapshot = `bc49b5d` (merged PR #23, `feat: plugin runtime foundation phase 1`).

| check | result |
| --- | --- |
| PR #23 / PR #22 file overlap | 0 |
| PR #23 runtime interaction verification | `PENDING RE-REVIEW` |
| Post-PR-23 synthetic-merge full suite | `PENDING NEW INDEPENDENT RE-REVIEW` |

Do not copy `960/4/28` onto `bc49b5d` or onto any later documentation-correction HEAD. Do not predict a new count.

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
- The PDF fallback environment difference is not closed
- V1.0 / DH-01–DH-08 / Windows / PostgreSQL / Provider / Release are not PASS
- Draft PR is not Ready and is not merged
- Post-PR-23 synthetic merge is not verified in this documentation batch

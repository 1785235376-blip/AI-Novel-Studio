# Baseline failure registry

Living registry for file-backend pytest failures. This is not a V1.0 claim, not a DesktopHost DH-01–DH-08 PASS, and not a review of merged PR #12 production code.

**Current-main** in this document means `origin/main` `01cc304e3df5357160f3c98b2ef50b0d9ddf8d95` (PR #19 merged). Counts bound to `e4dd24a682d2338d3aaf9ffa6880cbb1e364e6ac` are Batch 2A.2 current-main-before-#19 and must not be quoted as post-#19 main without that SHA. Counts bound to `d8174af8cb68c5e4edf920e6ccb45671f19ff3c9` are **historical** Batch 2A / 2A.1.

| Field | Historical Batch 2A / 2A.1 | Current-main Batch 2A.2 |
| --- | --- | --- |
| Bound SHA | `d8174af8cb68c5e4edf920e6ccb45671f19ff3c9` | `e4dd24a682d2338d3aaf9ffa6880cbb1e364e6ac` |
| Integrated PR merge | not integrated | `b15b58a30f29f019c70cb33485619d78d59b8a3f` (`git merge --no-ff origin/main`) |
| Batch | Issue #14 Batch 2A + 2A.1 | Issue #14 Batch 2A.2 current-main integration |
| Date | 2026-08-29 | 2026-08-29 |
| Environment | Linux isolation; Python 3.11.2; `STORAGE_BACKEND=file`; no user `.env`; no real PostgreSQL; no real Provider keys | same |
| Isolation | repository `--basetemp` / `TMP` / `TEMP` / `TMPDIR` under `.runtime/pytest-temp/` | same; fresh clone `/workspace/AI-Novel-Studio-2a2` plus independent worktree at `e4dd24a` |
| BEFORE / current-main BASE | 766 passed, 36 failed, 27 skipped, 0 xfail | 868 passed, 36 failed, 27 skipped, 0 xfail; 25.50s; exit 1 |
| AFTER is not a single stable tuple | Concurrent generation is isolation-reproducible FAIL and aggregate-flake | same; do not treat 901/4 as the only integrated AFTER |

Classifications: `PRODUCT_BASELINE` / `FIXTURE` / `ORDER_CONTAMINATION` / `PLATFORM` / `OPTIONAL_DEPENDENCY` / `DATABASE_REQUIRED` / `TEST_STATE_CONTAMINATION` / `UNKNOWN`.

`UNKNOWN` is not used. Environment blockers are classified, not described as “blocked, therefore unclassifiable”.

The four named failures classified as `PRODUCT_BASELINE` during Batch 2A / 2A.1 / 2A.2 were **not** repaired in those batches. Batch 2B-1 reclassified generation idempotency as `TEST_STATE_CONTAMINATION`. Three production defects remain.

## Current-main (`e4dd24a`) vs integrated HEAD

PR #12 plugin tests (`tests/test_plugin_catalog.py`, `tests/test_plugin_contract_v1.py`, `tests/test_plugin_discovery_security.py`) are in both current-main and the integrated PR (shared history). They are **not** PR #19 delta.

| Run | Passed | Failed | Skipped | xfail | Notes |
| --- | ---: | ---: | ---: | ---: | --- |
| Current-main BASE `e4dd24a` | 868 | 36 | 27 | 0 | Same 36 classified failures as historical `d8174af` BEFORE, plus 102 passing plugin tests. Concurrent passed this aggregate. |
| Integrated HEAD full run 1 | 901 | 4 | 28 | 0 | +1 honest Windows port skip; +1 default-auto vault test; concurrent failed |
| Integrated HEAD full run 2 | 901 | 4 | 28 | 0 | same 4 named defects |
| Integrated HEAD full run 3 | 901 | 4 | 28 | 0 | same 4 named defects |

`NEW FAILURES = 0` versus current-main means: no unclassified independent regression beyond the 36 BASE entries plus the named concurrent defect, and no PR #12 / conftest interaction failure. It is not a claim that every full run prints 901/4.

The 36 current-main BASE failures are the same node IDs as historical `d8174af` BEFORE (FIXTURE 10, ORDER_CONTAMINATION 3, PLATFORM 15 including the old combined port test, OPTIONAL_DEPENDENCY 1, DATABASE_REQUIRED 4, PRODUCT_BASELINE 3 in that aggregate). PR #12 did not add a new backend pytest failure on this Linux file-backend isolation run.

Concurrent isolation (Batch 2A.2 integrated HEAD): **1 pass / 19 fail** out of 20. Batch 2A.1 was 0/20. Independent Reviewer isolation was 0/20. The defect still reproduces alone; full-suite scheduling can hide it. Do not pick the best of N.

Plugin + conftest interaction (integrated HEAD): three plugin files 102 passed; plugins + predecessor + three order-contamination targets 5/5; reverse order 5/5. Autouse conftest did not change plugin vault defaults, did not leak fixture state, and did not add skips or xfails.

## Historical aggregate evidence (bound to `d8174af`, do not quote as current-main)

| Run | Passed | Failed | Skipped | xfail | Notes |
| --- | ---: | ---: | ---: | ---: | --- |
| Batch 2A implementer BEFORE | 766 | 36 | 27 | 0 | pre-PR #12 main |
| Batch 2A implementer AFTER | 798 | 4 | 27 | 0 | Concurrent failed that aggregate |
| Independent Reviewer HEAD | 799 | 3 | 27 | 0 | Concurrent passed that aggregate (flake) |
| Batch 2A.1 full run 1 | 799 | 4 | 28 | 0 | +1 honest Windows port skip; +1 default-auto vault test; concurrent failed |
| Batch 2A.1 full run 2 | 799 | 4 | 28 | 0 | same 4 named defects |
| Batch 2A.1 full run 3 | 799 | 4 | 28 | 0 | same 4 named defects |

## Summary after Batch 2A.2

| Classification | Historical BEFORE (`d8174af`) | Current-main BASE (`e4dd24a`) | Integrated HEAD remaining | Disposition |
| --- | ---: | ---: | ---: | --- |
| FIXTURE | 10 | 10 | 0 | FIXED_THIS_BATCH (tests) |
| ORDER_CONTAMINATION | 3 | 3 | 0 | FIXED_THIS_BATCH (tests) |
| PLATFORM | 15 | 15 | 0 | FIXED_THIS_BATCH (tests); Windows exclusive ports skip off Windows |
| OPTIONAL_DEPENDENCY | 1 | 1 | 0 | FIXED_THIS_BATCH (tests) |
| DATABASE_REQUIRED (manifest composition only; no connection) | 4 | 4 | 0 | FIXED_THIS_BATCH (tests) |
| PRODUCT_BASELINE | 3 in the 36-count aggregate; 4 named defects | 3 in the 36-count; concurrent passed this aggregate | 4 named (all three 2A.2 full runs) | REMAINS |
| PR #12 plugin tests | n/a | 102 passed, 0 failed | 102 passed, 0 failed | NO_INTERACTION_REGRESSION |
| UNKNOWN | 0 | 0 | 0 | — |

`tests/test_generation_variants_phase3.py::test_generation_is_idempotent_under_concurrent_submission` was listed as a named production defect in Batch 2A.2. Batch 2B-1 reclassified it as `TEST_STATE_CONTAMINATION` (fixed idempotency key reused against durable `novel_data/idempotency.json`). It is not a production race and not an aggregate flake.

## Issue #14 Batch 2B-1 (generation idempotency, 2026-08-29)

Bound to base `01cc304e3df5357160f3c98b2ef50b0d9ddf8d95`. See `docs/issue14_batch2b1_generation_idempotency_report.md`.

| Field | Value |
| --- | --- |
| Verdict | `TEST_STATE_CONTAMINATION_RECLASSIFIED` |
| Production change required | NO |
| Root cause | Fixed `Idempotency-Key: generation-race-unique` reused against process-import `IdempotencyStore` at `novel_data/idempotency.json` |
| Original 20-run (unmodified test) | 1 PASS (key absent) / 19 FAIL (`created_len=0`, key present, cached `job_id=one-job`) |
| Fresh-store concurrency | 3×50 + 16×20 + 32×10 = 80/80 PASS; same `job_id`; `jobs.create==1`; envelopes equal |
| Persisted replay | cached body returned; `jobs.create==0` |
| After isolation | original nodeid 20/20 independent pytest processes PASS even with leftover durable key |
| Full run 1 | 909 passed, 3 failed, 28 skipped, 0 xfail |
| Full run 2 | 909 passed, 3 failed, 28 skipped, 0 xfail |
| Remaining PRODUCT_BASELINE | 3 (visual continuity, user preference, world rule) |
| Issue #14 | OPEN |
| Issue #20 | UNCHANGED |

## Summary after Batch 2B-1

| Classification | Batch 2A.2 integrated HEAD | Batch 2B-1 remaining | Disposition |
| --- | --- | --- | --- |
| TEST_STATE_CONTAMINATION | counted as PRODUCT_BASELINE (concurrent generation) | 0 | RECLASSIFIED_AND_FIXED (tests; run-scoped store) |
| PRODUCT_BASELINE | 4 named | 3 named | REMAINS (not this batch) |
| UNKNOWN | 0 | 0 | — |

## Entries

### TEST_STATE_CONTAMINATION

#### tests/test_generation_variants_phase3.py::test_generation_is_idempotent_under_concurrent_submission

| Field | Value |
| --- | --- |
| Classification | TEST_STATE_CONTAMINATION |
| Reproduces alone | YES on a reused durable store; NO on a run-scoped fresh store |
| Reproduces after predecessor | N/A (store isolation, not order contamination) |
| Platform | Cross-platform |
| Severity | P0 (was mis-filed as production race) |
| Evidence | Batch 2B-1 matrix A: run 1 key absent PASS `created=1`; runs 2–20 key present FAIL `created_len=0`. Fresh store 80/80 concurrent PASS. Replay `create=0` is correct idempotency. Isolation fixture: 20/20 independent pytest processes PASS against leftover `novel_data/idempotency.json`. |
| Owner area | tests |
| Disposition | FIXED_THIS_BATCH (tests) |
| Production change required | NO |
| Notes | Root cause = fixed idempotency key reused against durable cache. Not an aggregate flake. Not a production race. In-process `threading.Lock` already serializes `_cached_idempotent` / `_generate_once` / `_store_idempotent`. Packaged runtime launches uvicorn without `--workers` (single process). Do not call this a remaining production defect. |

### PRODUCT_BASELINE

The three remaining production defects were **not** repaired in Batch 2B-1.

#### tests/test_p1_regression.py::test_visual_continuity_reports_scene_jumps

| Field | Value |
| --- | --- |
| Classification | PRODUCT_BASELINE |
| Reproduces alone | YES |
| Reproduces after predecessor | NOT_TESTED |
| Platform | Cross-platform |
| Severity | P1 |
| Evidence | Isolation and aggregate FAIL on current-main `e4dd24a` and all three integrated HEAD runs. Expected `TIME_JUMP_CUT` missing; actual `{LOCATION_JUMP, EMOTION_DISCONTINUITY}`. |
| Owner area | runtime |
| Disposition | REMAINS |
| Production change required | YES |
| Notes | Visual continuity. Out of Batch 2A / 2A.2 scope. |

#### tests/test_user_preference_service.py::test_preferences_are_explicit_and_separate

| Field | Value |
| --- | --- |
| Classification | PRODUCT_BASELINE |
| Reproduces alone | YES |
| Reproduces after predecessor | NOT_TESTED |
| Platform | Cross-platform |
| Severity | P1 |
| Evidence | Isolation and aggregate FAIL on current-main `e4dd24a` and all three integrated HEAD runs. `list()` includes extra `harness_enabled`. |
| Owner area | runtime |
| Disposition | REMAINS |
| Production change required | YES |
| Notes | User preference payload. Out of Batch 2A / 2A.2 scope. |

#### tests/test_world_rule_payload.py::test_world_rule_payload_normalizes_terms

| Field | Value |
| --- | --- |
| Classification | PRODUCT_BASELINE |
| Reproduces alone | YES |
| Reproduces after predecessor | NOT_TESTED |
| Platform | Cross-platform |
| Severity | P1 |
| Evidence | Isolation and aggregate FAIL on current-main `e4dd24a` and all three integrated HEAD runs. `forbidden` string not split into `forbidden_terms`. |
| Owner area | runtime |
| Disposition | REMAINS |
| Production change required | YES |
| Notes | World-rule normalization. Out of Batch 2A / 2A.2 scope. |

### FIXTURE (clean-clone sample novel)

`novel_data/novels/sample_novel` is gitignored user data, not a shipped product sample (`setuptools` excludes `novel_data*`). Situation A: tests needed a synthetic fixture.

Owner helper: `tests/sample_novel_fixture.py`. Data: `tests/fixtures/novels/sample_novel/` (short original fiction, no user novels copied).

All ten reproduced alone with `FileNotFoundError` or empty context. After the fixture they pass isolation and the integrated aggregate. They still fail on current-main `e4dd24a` (no PR #19 tests).

| Test node ID | Severity | Owner area | Disposition | Production change required |
| --- | --- | --- | --- | --- |
| tests/test_core.py::test_context_selects_relevant_characters | P0 | tests | FIXED_THIS_BATCH | NO |
| tests/test_core.py::test_cloud_privacy_omits_and_redacts | P0 | tests | FIXED_THIS_BATCH | NO |
| tests/test_core.py::test_age_dead_and_secret_review | P0 | tests | FIXED_THIS_BATCH | NO |
| tests/test_generation_snapshot_runtime_v056.py::test_generation_persists_snapshot_link_before_model_and_keeps_original_version | P0 | tests | FIXED_THIS_BATCH | NO |
| tests/test_generation_snapshot_runtime_v056.py::test_snapshot_failure_prevents_provider_stream | P0 | tests | FIXED_THIS_BATCH | NO |
| tests/test_jobs_v03.py::test_generate_accept_requires_explicit_commit | P0 | tests | FIXED_THIS_BATCH | NO |
| tests/test_jobs_v03.py::test_cancel_mock_job | P0 | tests | FIXED_THIS_BATCH | NO |
| tests/test_repository_contracts.py::test_context_service_matches_legacy_shape | P0 | tests | FIXED_THIS_BATCH | NO |
| tests/test_stability_v04.py::test_versions_conflict_and_restore | P0 | tests | FIXED_THIS_BATCH | NO |
| tests/test_workflow.py::test_local_workflow_persists_and_pending | P0 | tests | FIXED_THIS_BATCH | NO |

Shared fields for the ten: Classification `FIXTURE`; Reproduces alone `YES`; Reproduces after predecessor `NOT_TESTED`; Platform `Cross-platform`; Evidence BEFORE `FileNotFoundError` for gitignored `novel_data/novels/sample_novel` or empty context from missing files; Notes: no user-directory copy.

### ORDER_CONTAMINATION

Predecessor: `tests/test_packaged_control_pipe.py::test_reader_accepts_all_supported_provider_credentials_and_clear_is_scoped`. SET wrote into the global vault; CLEAR raised `KEYRING_NOT_INSTALLED` because the auto backend was degraded; `credential_vault.has("deepseek")` leaked into later `Runtime()` instances.

Isolation PASS. Predecessor+target FAIL before the conftest snapshot/restore. After memory-vault reset + env/settings/runtime restore: predecessor+target PASS; targets PASS 10/10 repeats; absent from integrated AFTER aggregate. Batch 2A.2 reconfirmed on integrated HEAD: predecessor+targets PASS; targets ×10 = 10/10; plugin+predecessor+targets 5/5 and reverse 5/5.

| Test node ID | Severity | Evidence (contaminated) | Owner area | Disposition | Production change required |
| --- | --- | --- | --- | --- | --- |
| tests/test_runtime_v03.py::test_non_mock_mode_preserves_real_deepseek_availability | P0 | deepseek marked available without a key | tests | FIXED_THIS_BATCH | NO |
| tests/test_runtime_v03.py::test_packaged_runtime_does_not_stand_in_mock_as_deepseek | P0 | deepseek marked available in packaged+mock | tests | FIXED_THIS_BATCH | NO |
| tests/test_phase1_feature_closure.py::test_packaged_generation_fails_closed_without_text_provider | P0 | `PROVIDER_UNAVAILABLE` instead of `TEXT_PROVIDER_NOT_CONFIGURED` | tests | FIXED_THIS_BATCH | NO |

Shared fields: Classification `ORDER_CONTAMINATION`; Reproduces alone `NO`; Reproduces after predecessor `YES`; Platform `Cross-platform`.

### OPTIONAL_DEPENDENCY

#### tests/test_packaged_control_pipe.py::test_reader_accepts_all_supported_provider_credentials_and_clear_is_scoped

| Field | Value |
| --- | --- |
| Classification | OPTIONAL_DEPENDENCY |
| Reproduces alone | YES |
| Reproduces after predecessor | NOT_TESTED |
| Platform | Linux (keyring extra not installed) |
| Severity | P1 |
| Evidence | BEFORE / current-main: `VaultUnavailableError: KEYRING_NOT_INSTALLED` on CLEAR of a degraded auto vault. AFTER 2A.1 / 2A.2: tests that need a process-local credential store inject `CredentialVault(backend="memory")` through a narrow fixture in `tests/test_packaged_control_pipe.py`. The suite no longer forces `CREDENTIAL_VAULT_BACKEND=memory`. Keyring fail-closed tests that construct `CredentialVault(backend="keyring")` still pass. Default selection is covered by `test_default_backend_request_is_auto_when_env_unset` with a fake selector (no real keyring / Credential Manager). |
| Owner area | tests |
| Disposition | FIXED_THIS_BATCH |
| Production change required | NO |
| Notes | Did not install `.[vault]`. Did not weaken `test_credential_vault.py` fail-closed contract. |

### PLATFORM

Linux must not forge Windows exclusive bind / terminate-by-handle as PASS.

Batch 2A.1: the previous Linux `AttributeError` / `SO_EXCLUSIVEADDRUSE` success assertion was an implementation accident, not a documented unsupported-platform contract. It was removed. Cross-platform coverage is `test_non_loopback_host_is_rejected`. Windows exclusive loopback bind, uniqueness, conflict fail-closed, and reservation close live in `test_windows_loopback_ports_are_unique_and_conflicts_fail_closed`, which **skips** off Windows. Linux did not verify Windows exclusive port reservation. DH-01–DH-08 / Windows evidence remains NOT_RUN.

Lifecycle tests use `FakePortAllocator` (fixed 55101–55103, `sockets={}`). That helper does **not** verify real bind, conflict detection, or socket reservation lifetime. It only uncouples startup-order unit tests from `SO_EXCLUSIVEADDRUSE`.

v0.6.1 `terminate_if_still_owned` returns `UNKNOWN_IDENTITY_FAIL_CLOSED` / `UNSUPPORTED_PLATFORM` before `handle_factory` on non-Windows. Tests assert that Linux contract and keep original Windows assertions.

On current-main `e4dd24a` the combined node `test_ports_are_loopback_only_unique_and_conflicts_fail_closed` still fails. Integrated HEAD no longer has that node; it is split as below.

| Test node ID | Reproduces alone | Severity | Owner area | Disposition | Production change required |
| --- | --- | --- | --- | --- | --- |
| tests/test_runtime_ownership_foundation_v070.py::test_ports_are_loopback_only_unique_and_conflicts_fail_closed (BEFORE / current-main node; 2A.1 split) | YES | P1 | tests | FIXED_THIS_BATCH then RECLASSIFIED_2A.1 | NO |
| tests/test_runtime_ownership_foundation_v070.py::test_non_loopback_host_is_rejected | YES | P1 | tests | RUNS_CROSS_PLATFORM | NO |
| tests/test_runtime_ownership_foundation_v070.py::test_windows_loopback_ports_are_unique_and_conflicts_fail_closed | YES on Windows | P1 | tests | SKIPPED_ON_LINUX | NO |
| tests/test_runtime_ownership_foundation_v070.py::test_startup_and_shutdown_follow_required_order | YES | P1 | tests | FIXED_THIS_BATCH | NO |
| tests/test_runtime_ownership_foundation_v070.py::test_failed_startup_rolls_back_children_metadata_and_mutex | YES | P1 | tests | FIXED_THIS_BATCH | NO |
| tests/test_runtime_ownership_foundation_v070.py::test_launcher_loss_job_boundary_prevents_orphans | YES | P1 | tests | FIXED_THIS_BATCH | NO |
| tests/test_runtime_ownership_foundation_v070.py::test_failed_graceful_shutdown_uses_job_boundary_and_releases_mutex | YES | P1 | tests | FIXED_THIS_BATCH | NO |
| tests/test_runtime_ownership_foundation_v070.py::test_child_crash_reports_chinese_recoverable_error_without_data_loss | YES | P1 | tests | FIXED_THIS_BATCH | NO |
| tests/test_runtime_ownership_foundation_v070.py::test_runtime_metadata_is_transient_and_provider_secret_free | YES | P1 | tests | FIXED_THIS_BATCH | NO |
| tests/test_v061_acceptance_lifecycle.py::test_final_boundary_valid_identity_terminates_same_handle | YES | P1 | tests | FIXED_THIS_BATCH | NO |
| tests/test_v061_acceptance_lifecycle.py::test_toctou_pid_reuse_after_initial_validation_is_rejected | YES | P1 | tests | FIXED_THIS_BATCH | NO |
| tests/test_v061_acceptance_lifecycle.py::test_final_creation_time_mismatch_does_not_terminate | YES | P1 | tests | FIXED_THIS_BATCH | NO |
| tests/test_v061_acceptance_lifecycle.py::test_final_executable_mismatch_does_not_terminate | YES | P1 | tests | FIXED_THIS_BATCH | NO |
| tests/test_v061_acceptance_lifecycle.py::test_final_argv_mismatch_does_not_terminate | YES | P1 | tests | FIXED_THIS_BATCH | NO |
| tests/test_v061_acceptance_lifecycle.py::test_final_run_id_mismatch_does_not_terminate | YES | P1 | tests | FIXED_THIS_BATCH | NO |
| tests/test_v061_acceptance_lifecycle.py::test_final_parent_exited_child_identity_can_still_terminate | YES | P1 | tests | FIXED_THIS_BATCH | NO |
| tests/test_v061_acceptance_lifecycle.py::test_process_exiting_during_handle_termination_is_safe_success | YES | P1 | tests | FIXED_THIS_BATCH | NO |

Shared fields: Classification `PLATFORM`; Reproduces after predecessor `NOT_TESTED`; Platform `Linux` in this run (Windows assertions retained in source; Windows exclusive ports skipped). Evidence BEFORE: `SO_EXCLUSIVEADDRUSE` `AttributeError` or `UNKNOWN_IDENTITY_FAIL_CLOSED` vs Windows terminate/reject codes. The `AttributeError` is not a formal contract.

### DATABASE_REQUIRED (manifest composition; no PostgreSQL operations)

`scripts/v061_acceptance_environment.build_manifest()` required a `DATABASE_URL` string and also called `dotenv_values(.env)`. The four tests check process-only secret passthrough, not a live database. Batch 2A monkeypatches dotenv to `{}` (does not read user `.env`) and supplies a synthetic URL that is never connected.

| Test node ID | Reproduces alone | Severity | Owner area | Disposition | Production change required |
| --- | --- | --- | --- | --- | --- |
| tests/test_v061_credential_passthrough.py::test_parent_provider_secret_reaches_child_but_not_manifest | YES | P1 | tests | FIXED_THIS_BATCH | NO |
| tests/test_v061_credential_passthrough.py::test_composed_environment_is_inherited_by_fastapi_style_python_child | YES | P1 | tests | FIXED_THIS_BATCH | NO |
| tests/test_v061_credential_passthrough.py::test_mock_and_real_verification_modes_remain_isolated | YES | P1 | tests | FIXED_THIS_BATCH | NO |
| tests/test_v061_credential_passthrough.py::test_all_approved_provider_secrets_are_process_only | YES | P1 | tests | FIXED_THIS_BATCH | NO |

Shared fields: Classification `DATABASE_REQUIRED` (URL string only); Platform `Cross-platform`; Evidence BEFORE `RuntimeError: DATABASE_URL is required` from `scripts/prepare_acceptance.py` with no connection attempted. Notes: real PostgreSQL contract tests remain skipped; no CREATE/DROP.

## Skips (Batch 2A.2)

| Tree | Skipped | xfail |
| --- | ---: | ---: |
| Current-main `e4dd24a` | 27 | 0 |
| Integrated HEAD | 28 | 0 |

Honest +1 skip on integrated HEAD versus current-main: `test_windows_loopback_ports_are_unique_and_conflicts_fail_closed` (`skipif os.name != "nt"`). NEW SKIPS are allowed so that Linux does not fake a port-reservation PASS. No new xfail. Windows named mutex / Job Object / process identity / Credential Manager skips retained. PostgreSQL `postgres_backend_only` and `TEST_POSTGRES_DATABASE_URL` skips retained. Migration 004 intentional absence retained.

## Not executed

- Windows named mutex / Job Object / process identity / Credential Manager integration
- Real PostgreSQL full suite, backup/restore
- Real Provider requests
- DesktopHost DH-01–DH-08
- Playwright
- GitHub Actions (repository has none)

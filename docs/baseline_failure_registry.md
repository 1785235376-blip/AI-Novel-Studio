# Baseline failure registry

Living registry for current-main file-backend pytest failures. This is not a V1.0 claim, not a DesktopHost DH-01–DH-08 PASS, and not a review of Draft PR #12.

| Field | Value |
| --- | --- |
| Bound SHA | `origin/main` `d8174af8cb68c5e4edf920e6ccb45671f19ff3c9` |
| Batch | Issue #14 Batch 2A |
| Date | 2026-08-29 |
| Environment | Linux isolation; Python 3.11.2; `STORAGE_BACKEND=file`; no user `.env`; no real PostgreSQL; no real Provider keys |
| Isolation | repository `--basetemp` / `TMP` / `TEMP` / `TMPDIR` under `.runtime/pytest-temp/` |
| BEFORE | 766 passed, 36 failed, 27 skipped, 0 xfail; 23.41s; exit 1 |
| AFTER | 798 passed, 4 failed, 27 skipped, 0 xfail; 22.60s; exit 1 |

Classifications: `PRODUCT_BASELINE` / `FIXTURE` / `ORDER_CONTAMINATION` / `PLATFORM` / `OPTIONAL_DEPENDENCY` / `DATABASE_REQUIRED` / `UNKNOWN`.

`UNKNOWN` is not used. Environment blockers are classified, not described as “blocked, therefore unclassifiable”.

The four named production defects are `PRODUCT_BASELINE` and were **not** repaired in this batch.

## Summary after Batch 2A

| Classification | BEFORE count | AFTER remaining | Disposition |
| --- | ---: | ---: | --- |
| FIXTURE | 10 | 0 | FIXED_THIS_BATCH |
| ORDER_CONTAMINATION | 3 | 0 | FIXED_THIS_BATCH |
| PLATFORM | 15 | 0 | FIXED_THIS_BATCH |
| OPTIONAL_DEPENDENCY | 1 | 0 | FIXED_THIS_BATCH |
| DATABASE_REQUIRED (manifest composition only; no connection) | 4 | 0 | FIXED_THIS_BATCH |
| PRODUCT_BASELINE | 3 in the 36-count aggregate; 4 named defects | 4 | REMAINS |
| UNKNOWN | 0 | 0 | — |

`tests/test_generation_variants_phase3.py::test_generation_is_idempotent_under_concurrent_submission` is a named production defect. It passed the BEFORE aggregate (flake) and failed isolation and the AFTER aggregate. It is registered as `PRODUCT_BASELINE`, not as a new failure.

## Entries

### PRODUCT_BASELINE

#### tests/test_generation_variants_phase3.py::test_generation_is_idempotent_under_concurrent_submission

| Field | Value |
| --- | --- |
| Classification | PRODUCT_BASELINE |
| Reproduces alone | YES |
| Reproduces after predecessor | NOT_TESTED |
| Platform | Cross-platform |
| Severity | P0 |
| Evidence | Isolation FAIL (`len(created)==0` / concurrent `job_id` mismatch). BEFORE aggregate did not list it; AFTER aggregate FAIL. Command: `python -m pytest -p no:cacheprovider --tb=line tests/test_generation_variants_phase3.py::test_generation_is_idempotent_under_concurrent_submission` |
| Owner area | runtime |
| Disposition | REMAINS |
| Production change required | YES |
| Notes | Concurrent generation idempotency. Out of Batch 2A scope. |

#### tests/test_p1_regression.py::test_visual_continuity_reports_scene_jumps

| Field | Value |
| --- | --- |
| Classification | PRODUCT_BASELINE |
| Reproduces alone | YES |
| Reproduces after predecessor | NOT_TESTED |
| Platform | Cross-platform |
| Severity | P1 |
| Evidence | Isolation and aggregate FAIL. Expected `TIME_JUMP_CUT` missing; actual `{LOCATION_JUMP, EMOTION_DISCONTINUITY}`. |
| Owner area | runtime |
| Disposition | REMAINS |
| Production change required | YES |
| Notes | Visual continuity. Out of Batch 2A scope. |

#### tests/test_user_preference_service.py::test_preferences_are_explicit_and_separate

| Field | Value |
| --- | --- |
| Classification | PRODUCT_BASELINE |
| Reproduces alone | YES |
| Reproduces after predecessor | NOT_TESTED |
| Platform | Cross-platform |
| Severity | P1 |
| Evidence | Isolation and aggregate FAIL. `list()` includes extra `harness_enabled`. |
| Owner area | runtime |
| Disposition | REMAINS |
| Production change required | YES |
| Notes | User preference payload. Out of Batch 2A scope. |

#### tests/test_world_rule_payload.py::test_world_rule_payload_normalizes_terms

| Field | Value |
| --- | --- |
| Classification | PRODUCT_BASELINE |
| Reproduces alone | YES |
| Reproduces after predecessor | NOT_TESTED |
| Platform | Cross-platform |
| Severity | P1 |
| Evidence | Isolation and aggregate FAIL. `forbidden` string not split into `forbidden_terms`. |
| Owner area | runtime |
| Disposition | REMAINS |
| Production change required | YES |
| Notes | World-rule normalization. Out of Batch 2A scope. |

### FIXTURE (clean-clone sample novel)

`novel_data/novels/sample_novel` is gitignored user data, not a shipped product sample (`setuptools` excludes `novel_data*`). Situation A: tests needed a synthetic fixture.

Owner helper: `tests/sample_novel_fixture.py`. Data: `tests/fixtures/novels/sample_novel/` (short original fiction, no user novels copied).

All ten reproduced alone with `FileNotFoundError` or empty context. After the fixture they pass isolation and the aggregate.

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

Isolation PASS. Predecessor+target FAIL before the conftest snapshot/restore. After memory-vault reset + env/settings/runtime restore: predecessor+target PASS; targets PASS 10/10 repeats; absent from AFTER aggregate.

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
| Evidence | BEFORE: `VaultUnavailableError: KEYRING_NOT_INSTALLED` on CLEAR of a degraded auto vault. AFTER: ordinary tests use explicit memory backend; keyring fail-closed tests that construct `CredentialVault(backend="keyring")` still pass. |
| Owner area | tests |
| Disposition | FIXED_THIS_BATCH |
| Production change required | NO |
| Notes | Did not install `.[vault]`. Did not weaken `test_credential_vault.py` fail-closed contract. |

### PLATFORM

Linux must assert fail-closed / unsupported-platform. Windows exclusive bind / terminate-by-handle is not forged as PASS.

Lifecycle tests already faked mutex/job; they now also use a test-owned port allocator so startup order is not coupled to `socket.SO_EXCLUSIVEADDRUSE`. Direct port-reservation tests keep Linux `AttributeError` fail-closed and Windows exclusive-bind assertions.

v0.6.1 `terminate_if_still_owned` returns `UNKNOWN_IDENTITY_FAIL_CLOSED` / `UNSUPPORTED_PLATFORM` before `handle_factory` on non-Windows. Tests now assert that Linux contract and keep original Windows assertions. No new skip/xfail. Existing four Windows-only skips unchanged.

| Test node ID | Reproduces alone | Severity | Owner area | Disposition | Production change required |
| --- | --- | --- | --- | --- | --- |
| tests/test_runtime_ownership_foundation_v070.py::test_ports_are_loopback_only_unique_and_conflicts_fail_closed | YES | P1 | tests | FIXED_THIS_BATCH | NO |
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

Shared fields: Classification `PLATFORM`; Reproduces after predecessor `NOT_TESTED`; Platform `Linux` in this run (Windows assertions retained in source). Evidence BEFORE: `SO_EXCLUSIVEADDRUSE` `AttributeError` or `UNKNOWN_IDENTITY_FAIL_CLOSED` vs Windows terminate/reject codes.

### DATABASE_REQUIRED (manifest composition; no PostgreSQL operations)

`scripts/v061_acceptance_environment.build_manifest()` required a `DATABASE_URL` string and also called `dotenv_values(.env)`. The four tests check process-only secret passthrough, not a live database. Batch 2A monkeypatches dotenv to `{}` (does not read user `.env`) and supplies a synthetic URL that is never connected.

| Test node ID | Reproduces alone | Severity | Owner area | Disposition | Production change required |
| --- | --- | --- | --- | --- | --- |
| tests/test_v061_credential_passthrough.py::test_parent_provider_secret_reaches_child_but_not_manifest | YES | P1 | tests | FIXED_THIS_BATCH | NO |
| tests/test_v061_credential_passthrough.py::test_composed_environment_is_inherited_by_fastapi_style_python_child | YES | P1 | tests | FIXED_THIS_BATCH | NO |
| tests/test_v061_credential_passthrough.py::test_mock_and_real_verification_modes_remain_isolated | YES | P1 | tests | FIXED_THIS_BATCH | NO |
| tests/test_v061_credential_passthrough.py::test_all_approved_provider_secrets_are_process_only | YES | P1 | tests | FIXED_THIS_BATCH | NO |

Shared fields: Classification `DATABASE_REQUIRED` (URL string only); Platform `Cross-platform`; Evidence BEFORE `RuntimeError: DATABASE_URL is required` from `scripts/prepare_acceptance.py` with no connection attempted. Notes: real PostgreSQL contract tests remain skipped; no CREATE/DROP.

## Skips (unchanged count = 27)

Existing skips only. No new skip/xfail. Windows named mutex / Job Object / process identity / Credential Manager skips retained. PostgreSQL `postgres_backend_only` and `TEST_POSTGRES_DATABASE_URL` skips retained. Migration 004 intentional absence retained.

## Not executed

- Windows named mutex / Job Object / process identity / Credential Manager integration
- Real PostgreSQL full suite, backup/restore
- Real Provider requests
- DesktopHost DH-01–DH-08
- Playwright
- GitHub Actions (repository has none)

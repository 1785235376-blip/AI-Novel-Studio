# Issue #14 Batch 2A — clean regression reproducibility foundation

This batch only repaired test reproducibility: fixtures, settings isolation, platform classification, optional-dependency classification, and the baseline-failure registry. It did not repair the four production logic defects and did not touch Draft PR #12.

| Field | Value |
| --- | --- |
| Issue | [#14](https://github.com/1785235376-blip/AI-Novel-Studio/issues/14) |
| Base SHA | `origin/main` `d8174af8cb68c5e4edf920e6ccb45671f19ff3c9` |
| Work branch | `fix/p0-clean-regression-foundation` |
| Date | 2026-08-29 |
| Operator | Grok (Issue #14 Batch 2A) |
| Production code changes | 0 |
| Frontend code changes | 0 |
| Schema / migration changes | 0 |
| PR #12 touched | NO |
| New skip / xfail | 0 |
| Assertions weakened | 0 |
| Real PostgreSQL operations | 0 |
| Real Provider requests | 0 |
| Real credential access | 0 |
| V1.0 / DH-01–DH-08 / Release | UNCHANGED / NOT_RUN / NOT EVALUATED |

## Phase 0 baseline

1. `git fetch origin --prune`
2. Worktree clean on `main`
3. `origin/main` still `d8174af8cb68c5e4edf920e6ccb45671f19ff3c9` (expected SHA; no rebase)
4. Created `fix/p0-clean-regression-foundation` from that SHA
5. Run-scoped temp: `.runtime/pytest-temp/batch2a-before`
6. Cleared Provider / database / user env for the test process (`DATABASE_URL`, `TEST_POSTGRES_DATABASE_URL`, Provider `*_API_KEY` names). Did not read user `.env`.

### BEFORE command

```text
STORAGE_BACKEND=file TMP=<repo>/.runtime/pytest-temp/batch2a-before \
  python -m pytest -p no:cacheprovider \
  --basetemp=<repo>/.runtime/pytest-temp/batch2a-before/pytest \
  -q -ra --tb=line
```

| Field | Value |
| --- | --- |
| Python / OS | Python 3.11.2; Linux-6.12.8+-x86_64-with-glibc2.36 |
| Result | 766 passed, 36 failed, 27 skipped, 0 xfail |
| Exit | 1 |
| Duration | 23.41s |
| First failure | `tests/test_core.py::test_context_selects_relevant_characters` |

The 36 failed node IDs match `docs/baseline_failure_registry.md`.

## Phase 1 registry

Added `docs/baseline_failure_registry.md`. All 36 BEFORE failures classified. The four production defects are `PRODUCT_BASELINE`. Concurrent generation is registered even though it flaked past the BEFORE aggregate.

## Phase 2 sample novel (Situation A)

`/novel_data/` is gitignored and excluded from the Python package. Tests only needed synthetic data. Not a product-packaging defect.

- Added `tests/fixtures/novels/sample_novel/` — short original fiction, no user novels copied
- Added `tests/sample_novel_fixture.py`
- Updated the ten dependent tests to use the test-owned path

## Phase 3 settings order contamination

Predecessor: `tests/test_packaged_control_pipe.py::test_reader_accepts_all_supported_provider_credentials_and_clear_is_scoped`.

Leaked global vault credentials (`credential_vault.has("deepseek")`) into later `Runtime()` objects. Isolation passed; predecessor+target failed.

Fix (tests only): autouse snapshot/restore of settings, env, memory vault, `credential_store`, and `Runtime.__init__()` on the existing singleton.

Verification:

1. Three targets isolation PASS
2. Predecessor + three targets PASS
3. Three targets × 10 PASS
4. Absent from AFTER aggregate

## Phase 4 platform

- Port reservation: Linux asserts fail-closed `AttributeError` for `SO_EXCLUSIVEADDRUSE`; Windows keeps exclusive-bind/conflict assertions
- Lifecycle tests use a test-owned port allocator (mutex/job were already faked)
- v0.6.1 process identity: Linux asserts `UNKNOWN_IDENTITY_FAIL_CLOSED` / `UNSUPPORTED_PLATFORM` and does not terminate; Windows original assertions retained
- No new skip. Existing Windows-only skip count unchanged

## Phase 5 optional dependency and database

- Ordinary tests explicitly use memory vault. Did not install `.[vault]`
- `test_credential_vault.py` keyring fail-closed tests still pass
- v061 credential-passthrough tests no longer read `.env`; they use a synthetic `DATABASE_URL` string and never connect
- Real PostgreSQL tests remain skipped; skip count 27
- `.[dev]` vs vault extra mismatch recorded only; `pyproject.toml` not changed

## Phase 6 regression

| Check | BEFORE | AFTER |
| --- | --- | --- |
| PASSED | 766 | 798 |
| FAILED | 36 | 4 |
| SKIPPED | 27 | 27 |
| XFAIL | 0 | 0 |
| NEW FAILURES | — | 0 |
| FIXTURE remaining | 10 | 0 |
| ORDER_CONTAMINATION remaining | 3 | 0 |
| PLATFORM misclassification remaining | 15 | 0 |
| PRODUCT_BASELINE | 4 named | 4 (all remaining AFTER failures) |
| UNKNOWN | 0 | 0 |

AFTER remaining failures:

1. `tests/test_generation_variants_phase3.py::test_generation_is_idempotent_under_concurrent_submission`
2. `tests/test_p1_regression.py::test_visual_continuity_reports_scene_jumps`
3. `tests/test_user_preference_service.py::test_preferences_are_explicit_and_separate`
4. `tests/test_world_rule_payload.py::test_world_rule_payload_normalizes_terms`

Frontend Vitest: 376 passed / 89 files, exit 0.

Typecheck: `npx tsc -b` exit 1 in this environment on unused `@ts-expect-error` in three existing frontend test files. This batch did not modify frontend. Production `npx vite build` exit 0.

`git diff --check` on this worktree: exit 0.

## Phase 7 commits / PR

Suggested commits (no amend / rebase / squash / force-push):

1. `test: isolate clean-clone fixtures and runtime settings`
2. `docs: establish current-main failure registry`

Draft PR title: `test: make clean regression reproducible`.

## Boundaries confirmed

- PRODUCTION CODE CHANGES = 0
- FRONTEND CODE CHANGES = 0
- SCHEMA / MIGRATION CHANGES = 0
- PR #12 CHANGES = 0
- NEW SKIPS = 0
- NEW XFAILS = 0
- ASSERTION WEAKENING = 0
- REAL POSTGRESQL OPERATIONS = 0
- REAL PROVIDER REQUESTS = 0
- REAL CREDENTIAL ACCESS = 0

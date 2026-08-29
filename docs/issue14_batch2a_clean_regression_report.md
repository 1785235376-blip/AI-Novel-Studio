# Issue #14 Batch 2A — clean regression reproducibility foundation

This batch only repaired test reproducibility: fixtures, settings isolation, platform classification, optional-dependency classification, and the baseline-failure registry. It did not repair the four production logic defects and did not modify PR #12 production code.

| Field | Historical Batch 2A / 2A.1 | Batch 2A.2 current-main integration |
| --- | --- | --- |
| Issue | [#14](https://github.com/1785235376-blip/AI-Novel-Studio/issues/14) | same |
| Base SHA | `d8174af8cb68c5e4edf920e6ccb45671f19ff3c9` (historical; **not** current-main) | current-main `e4dd24a682d2338d3aaf9ffa6880cbb1e364e6ac` |
| Work branch | `fix/p0-clean-regression-foundation` | same |
| Pre-integration PR HEAD | `407b74a628db1ca26b7ced79647a563e64bc7cd7` | same |
| Merge | n/a | `--no-ff` `b15b58a30f29f019c70cb33485619d78d59b8a3f` |
| Date | 2026-08-29 | 2026-08-29 |
| Operator | Grok (Issue #14 Batch 2A / 2A.1) | Grok Integration Worker (Batch 2A.2) |
| Production code changes vs that base | 0 | 0 vs current-main |
| Frontend code changes vs that base | 0 | 0 vs current-main |
| Schema / migration changes vs that base | 0 | 0 vs current-main |
| PR #12 | not rebased onto | already in shared history; not modified |
| New skip / xfail | Batch 2A: 0. Batch 2A.1: +1 skip (Windows exclusive ports off Windows), 0 xfail | HEAD skip 28 vs main 27; 0 xfail |
| Assertions weakened | 0 | 0 |
| Real PostgreSQL operations | 0 | 0 |
| Real Provider requests | 0 | 0 |
| Real credential access | 0 | 0 |
| V1.0 / DH-01–DH-08 / Release | UNCHANGED / NOT_RUN / NOT EVALUATED | same |

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

Fix (tests only, Batch 2A.1): predecessor test injects an isolated `CredentialVault(backend="memory")` into `app.packaging.control_pipe.credential_vault`. Autouse no longer forces memory vault or replaces vault private state.

Verification:

1. Three targets isolation PASS
2. Predecessor + three targets PASS
3. Three targets × 10 PASS
4. Absent from AFTER aggregate

## Phase 4 platform

Batch 2A originally asserted Linux `AttributeError` for missing `SO_EXCLUSIVEADDRUSE` and counted that as PASS. Independent review: that exception is an implementation accident, not a documented contract, and over-claimed port reservation.

Batch 2A.1:

- Cross-platform: `test_non_loopback_host_is_rejected` (non-`127.0.0.1` host)
- Windows-only (skipped on Linux): `test_windows_loopback_ports_are_unique_and_conflicts_fail_closed` — real loopback bind, unique ports, conflict fail-closed, reservation close
- Linux did **not** verify Windows exclusive port reservation
- `FakePortAllocator` (55101–55103, empty `sockets`) is only for lifecycle order tests; it does not bind, detect conflicts, or own socket lifetime
- v0.6.1 process identity: Linux asserts `UNKNOWN_IDENTITY_FAIL_CLOSED` / `UNSUPPORTED_PLATFORM`; Windows assertions retained in source
- DH-01–DH-08 / Windows named mutex / Job Object / Credential Manager = NOT_RUN
- Honest +1 skip on Linux; no xfail added

## Phase 5 optional dependency and database

- Tests that need a process-local credential store inject memory vault through a narrow fixture. Did not install `.[vault]`
- `test_credential_vault.py` keyring fail-closed tests still pass
- `test_default_backend_request_is_auto_when_env_unset` covers `CredentialVault()` with env unset via a fake `_select_backend` (requested value `auto`; no real keyring / Credential Manager)
- v061 credential-passthrough tests no longer read `.env`; they use a synthetic `DATABASE_URL` string and never connect
- Real PostgreSQL tests remain skipped
- Linux skip count after 2A.1 = 28 (honest Windows port skip)
- `.[dev]` vs vault extra mismatch recorded only; `pyproject.toml` not changed

## Phase 6 regression

Batch 2A implementer AFTER was 798/4/27 on one run. That tuple is **not** the unique stable AFTER. Those counts are bound to historical `d8174af`, not current-main.

| Check | BEFORE (2A implementer) | Independent Reviewer HEAD | 2A.1 run 1 | 2A.1 run 2 | 2A.1 run 3 |
| --- | --- | --- | --- | --- | --- |
| PASSED | 766 | 799 | 799 | 799 | 799 |
| FAILED | 36 | 3 | 4 | 4 | 4 |
| SKIPPED | 27 | 27 | 28 | 28 | 28 |
| XFAIL | 0 | 0 | 0 | 0 | 0 |

`NEW FAILURES = 0` means no new unclassified independent regression vs the 36 BEFORE entries plus the named concurrent defect.

Named production defects (not repaired):

1. `tests/test_generation_variants_phase3.py::test_generation_is_idempotent_under_concurrent_submission` — isolation-reproducible FAIL; aggregate flake
2. `tests/test_p1_regression.py::test_visual_continuity_reports_scene_jumps`
3. `tests/test_user_preference_service.py::test_preferences_are_explicit_and_separate`
4. `tests/test_world_rule_payload.py::test_world_rule_payload_normalizes_terms`

Frontend (frozen `frontend/pnpm-lock.yaml`, pnpm 9.15.0, `--ignore-workspace` because existing `pnpm-workspace.yaml` has no `packages` field — pre-existing, not this PR):

| Check | Meaning | 2A implementer | Independent Reviewer | Batch 2A.1 this session |
| --- | --- | --- | --- | --- |
| Vitest | `pnpm exec vitest run` | 376 passed / 89 files | 376 / 89, exit 0 | 376 / 89, exit 0 |
| Typecheck | `tsc -b` (not Vite) | `npx tsc -b` exit 1 unused `@ts-expect-error` | exit 0 | exit 1 unused `@ts-expect-error` in `Editor.typography.test.ts:2,4`, `ChapterTree.css.test.ts:2,4`, `FeatureLauncher.css.test.ts:2,4` |
| Vite bundle | `vite build` only | `npx vite build` exit 0 | exit 0 | exit 0 |
| Canonical build | `pnpm run build` = `tsc -b && vite build` | not run under that name | exit 0 | exit 1 (blocked by tsc) |

Typecheck is **not** a stable baseline: Independent Reviewer clean worktree PASS, implementer and this 2A.1 session FAIL on the same three unused `@ts-expect-error` directives. Frontend was not modified. Vite bundle PASS is not canonical production build PASS.

`git diff --check` on 2A.1 test+docs diffs: exit 0.

## Phase 7 commits / PR

1. `c87b1a3` test: isolate clean-clone fixtures and runtime settings
2. `da6fb6c` docs: establish current-main failure registry
3. `b711611` test: narrow vault isolation and classify Windows ports
4. `407b74a` docs: reconcile independent review evidence

Draft PR #19 remains Draft. Do not merge. Do not close Issue #14.

## Batch 2A.1 P1 corrections

- Removed Linux `AttributeError` success assertion
- Narrowed vault isolation; added default `auto` selector test
- Recorded concurrent aggregate flake with three full-suite runs (not the best of N)
- Distinguished Vite bundle vs canonical `tsc -b && vite build`

## Batch 2A.2 current-main integration

Fresh clean clone (not the dirty workspace that had untracked `frontend/package-lock.json`). Independent worktree at `e4dd24a`. Ordinary `git merge --no-ff origin/main`. No conflict. No rebase / amend / squash / force-push.

`git diff --name-status origin/main...HEAD` after merge: tests, fixtures, and docs only. PR #12 production / frontend / schema / examples files are shared history, not PR #19 delta. PRODUCTION CODE CHANGES = 0 **versus current-main**.

### Current-main BASE (`e4dd24a` independent worktree)

Python 3.11.2; `uv pip install -e .[dev]`; not `.[vault]`; `STORAGE_BACKEND=file`; `env -i`; run-scoped TMP/basetemp; no user `.env`.

| Check | Result |
| --- | --- |
| Backend full pytest | 868 passed, 36 failed, 27 skipped, 0 xfail; 25.50s; exit 1 |
| Vitest | 394 passed / 89 files, exit 0 |
| Typecheck `pnpm exec tsc -b` | exit 1 unused `@ts-expect-error` in `Editor.typography.test.ts:2,4`, `ChapterTree.css.test.ts:2,4`, `FeatureLauncher.css.test.ts:2,4` |
| Vite bundle `pnpm exec vite build` | exit 0 |
| Canonical `pnpm run build` | exit 1 (blocked by tsc) |
| `git diff --check` | exit 0 |

The 36 BASE failures are the same classified node IDs as historical `d8174af` BEFORE. PR #12 added 102 passing plugin tests (868 − 766 = 102). Concurrent generation passed this current-main aggregate (flake).

### Integrated HEAD (merge `b15b58a`)

| Check | Result |
| --- | --- |
| P1 vault/control-pipe/ports | 29 passed, 2 skipped, exit 0. Windows exclusive ports skipped with honest reason. Default auto vault test passed. |
| Predecessor + 3 order targets | 4 passed |
| Three targets ×10 | 10/10 |
| Concurrent isolation ×20 | **1 pass / 19 fail** |
| Plugin files | 102 passed |
| Plugin + predecessor + targets ×5 | 5/5 |
| Reverse order ×5 | 5/5 |
| Backend full run 1 | 901 passed, 4 failed, 28 skipped, 0 xfail |
| Backend full run 2 | 901 passed, 4 failed, 28 skipped, 0 xfail |
| Backend full run 3 | 901 passed, 4 failed, 28 skipped, 0 xfail |
| Vitest | 394 passed / 89 files, exit 0 |
| Typecheck | exit 1, same unused `@ts-expect-error` |
| Vite bundle | exit 0 |
| Canonical build | exit 1 (blocked by tsc) |
| Fixture JSON parse | 8/8 OK |
| PR diff secret scan | 0 |
| `git diff --check origin/main...HEAD` | exit 0 |

All three integrated full runs failed the same four named production defects. `NEW FAILURES = 0`. Typecheck is **not** a stable baseline. Vite bundle PASS is not canonical production build PASS. Frontend was not modified by this PR.

### Commits (Batch 2A.2)

1. `b15b58a` merge: integrate current main into regression foundation
2. (this file) docs: bind regression evidence to integrated current main

Draft PR #19 remains Draft. Do not merge. Do not close Issue #14.

## Boundaries confirmed

- PRODUCTION CODE CHANGES = 0 versus current-main `e4dd24a`
- FRONTEND CODE CHANGES = 0 versus current-main
- SCHEMA / MIGRATION CHANGES = 0 versus current-main
- PR #12 production files not re-introduced as PR #19 delta
- NEW SKIPS = 1 on HEAD vs current-main (Windows exclusive ports, honest)
- NEW XFAILS = 0
- ASSERTION WEAKENING = 0
- REAL POSTGRESQL OPERATIONS = 0
- REAL PROVIDER REQUESTS = 0
- REAL CREDENTIAL ACCESS = 0

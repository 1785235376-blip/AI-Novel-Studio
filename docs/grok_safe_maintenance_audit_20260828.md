# Safe Maintenance Audit — 2026-08-28

> Read-only fact audit of current `origin/main`. This is not a V1.0 release claim, not a DesktopHost window PASS, and not a review of Draft PR #12.

| Field | Value |
| --- | --- |
| Baseline | `origin/main` `46bee8f4b57f0cc61d69746bf190a88a3fb3d733` |
| Date | 2026-08-28 |
| Operator | Grok (safe maintenance batch 1) |
| Work branch | `grok-safe-maintenance-20260828` |
| Production code changes | 0 |
| Test / schema / migration changes | 0 |
| Real Provider requests | 0 |
| Real credential access | 0 |
| PR #12 touched | NO |
| V1.0 / DH-01–DH-08 / Release | UNCHANGED / NOT EVALUATED / BLOCKED |

## Phase 0 baseline

- `git fetch origin --prune` then hard reset to `origin/main`.
- Worktree before edits: clean.
- Current branch at fetch: `main` @ `46bee8f`.
- Remote branches: `origin/main`, `origin/feature/plugin-contract-v1-declarative`, `origin/grok-phase1-acceptance`, `origin/grok-phase1-feature-closure`.
- Open PRs at start: PR #12 (draft, plugin SDK), PR #1 (superseded; closed this batch).
- GitHub Actions: no repository-owned `.github/workflows`. Only GitHub dynamic Dependabot “Dependency Graph”.
- `main` protection: **not protected**.

`origin/main` still matched the prompt SHA `46bee8f`. No production-code scope conflict. Work continued.

## Phase 1 — PR #1

| Check | Result |
| --- | --- |
| PR #2 merged to `main` | YES (`merged_at` 2026-08-27T17:18:12Z) |
| Author-honesty features on `main` via PR #2 | YES (overview / research sidecar / Agent `VALIDATED` / video fail-closed) |
| Unique file vs `main` | Only `docs/grok_phase1_desktop_acceptance.md` |
| Unique file content | Procedure template, not completed DH evidence |
| Old DLL SHA-256 | `98F02E42A9E7A50CE94D6A748F3D226E869890396D1256AC8CEABCC81A08A740` — **not current-main evidence**. Current DH template on `main` is `docs/desktop_host_acceptance_checklist.md` (PR #9), DH-01–DH-08 = `NOT_RUN`, build hash is a placeholder |

PR #1 closed as superseded. Branches were **not** deleted.

Reportable later (not deleted this batch): `grok-phase1-feature-closure`, `grok-phase1-acceptance`.

## Findings

Each item: path/line, evidence, impact, recommendation, production-code change needed, independent security review needed.

### Critical

None confirmed in this batch. Static scan found no live private keys, GitHub PATs, or user DSNs in tracked files. `.env` is absent. Real credentials were not read.

### High

#### H1. No living baseline-failure registry; current-main regression is not clean

- Path: `docs/test_report.md` (historical body ended at V0.4.8.1); `docs/v1_acceptance_status.md:31-34`; `docs/v1_release_checklist.md` section B.
- Evidence: this batch’s file-backend pytest on `46bee8f` was **766 passed, 36 failed, 27 skipped, 0 xfail**, exit 1. Four named baseline defects still fail. Additional full-suite failures are environment or order contamination.
- Impact: Release checklist B cannot pass. Counts in older status docs (for example “586 passed, 22 skipped, 3 failures”) are stale and must not be reused as current evidence.
- Recommendation: keep a SHA-dated registry of known failures vs environment blockers; re-run a clean isolated suite after each main merge. Do not skip/xfail/delete tests to make the count green.
- Production code: yes, later, to fix the four baselines and suite isolation — **not this batch**.
- Independent security review: no for the registry itself.

#### H2. DH-01–DH-08 remain `NOT_RUN`; old staging hashes are still easy to mistake for current evidence

- Path: `docs/desktop_host_acceptance_checklist.md:16-27`; `docs/v1_acceptance_status.md:9-11,21,38-41`; `docs/acceptance_report_20260822.md:11-12`; `docs/v1_release_checklist.md` section I.
- Evidence: current DH table is all `NOT_RUN`. Status docs still quote 2026-08-22 staging ZIP/EXE SHA-256 `4EDE43F4…` / `52B601C5…` and Windows staging paths. PR #1’s unique doc hard-coded DLL SHA-256 `98F02E42…`, which is not on current `main`.
- Impact: a reader can treat an old staging snapshot as the current DesktopHost gate. Checklist I stays `BLOCKED`.
- Recommendation: keep DH results `NOT_RUN` until a freshly built WinExe from current main is operated on Windows. Label historical hashes as historical. Do not use browser/API/Playwright as window evidence.
- Production code: no for documentation honesty; Windows rebuild/operation is later.
- Independent security review: no for this finding; DH-08 log redaction remains a later gate.

#### H3. Real PostgreSQL backup/restore and clean-instance parity are unverified on current main

- Path: `docs/v1_release_checklist.md` sections C–D; `docs/v1_acceptance_status.md:27,48`; pytest skips for `postgres_backend_only`.
- Evidence: this batch unset all database URLs by design. PostgreSQL tests skipped or failed closed on missing `DATABASE_URL`. No backup/restore was executed.
- Impact: Release checklist D cannot pass. Sidecar research tests are not PostgreSQL composition evidence.
- Recommendation: provision an owned isolated instance, apply migrations, backup/restore, and record checksums without touching user data.
- Production code: only if restore/migration bugs appear later.
- Independent security review: yes before any production DSN handling.

### Medium

#### M1. `GROK-CODE-AUDIT-PROMPT.md` stated the desktop UI refactor had not started

- Path: `GROK-CODE-AUDIT-PROMPT.md` (pre-change line 41): “桌面端 UI 重构尚未开始”.
- Evidence: `docs/frontend_ui_ux_refactor_report.md` and related UI docs exist on `main`; frontend Vitest/build run against the refactored UI.
- Impact: auditors can skip already-landed UI work or treat DesktopHost as “not started” instead of “window gate not run”.
- Recommendation: this batch rewrote that bullet. Keep DH-01–DH-08 `NOT_RUN`.
- Production code: no.
- Independent security review: no.

#### M2. Implementation status “已实现” vs DH `NOT_RUN`

- Path: `docs/v1_implementation_status.md:3,14,65-66`; `docs/v1_acceptance_status.md:21`.
- Evidence: implementation table says DesktopHost 安全会话 “已实现” and staging `r5e` reached `DESKTOP_SESSION_READY`. The operating checklist still has DH-01–DH-08 `NOT_RUN` on current main.
- Impact: P0 window work can be misread as complete. Staging startup is not DH-02–DH-08 window business evidence.
- Recommendation: keep “implemented in code / staging startup” distinct from “current-candidate window PASS”. Do not tick checklist I.
- Production code: no for this honesty fix; Windows evidence is later.
- Independent security review: no.

#### M3. Full-suite global settings contamination

- Path: `tests/test_runtime_v03.py:27-52`; `tests/test_phase1_feature_closure.py:224-243`; historical note in `docs/v0.7.0_windows_beta_packaging_phase3_local_session_bootstrap_report.md:65`.
- Evidence: three tests failed in the aggregate run and passed in isolation (including `TEXT_PROVIDER_NOT_CONFIGURED` vs `PROVIDER_UNAVAILABLE` only in the contaminated run).
- Impact: aggregate pytest cannot be used as a release number without an isolation contract.
- Recommendation: restore settings per test (conftest already tries); add a registry entry for contamination; do not weaken assertions.
- Production code: yes later (test isolation / settings ownership). Out of this batch.
- Independent security review: no.

#### M4. Clean clone lacks `sample_novel` fixture

- Path: `tests/test_core.py:10-27`; `.gitignore:31` (`/novel_data/`).
- Evidence: `FileNotFoundError` for `novel_data/novels/sample_novel` in multiple tests.
- Impact: a clean checkout cannot reproduce the oldest core privacy/context tests.
- Recommendation: ship a tiny fixture under `tests/` or `examples/` in a later batch. Do not copy user novels.
- Production code: no; test fixture later (forbidden in this batch).
- Independent security review: no.

### Low

#### L1. Historical whitespace in tracked files

- Path: many; `git diff --check <empty-tree> HEAD` exit 2. This batch counted 579 trailing-whitespace and 64 EOF-blank-line reports.
- Evidence: current worktree vs `HEAD` is clean (`git diff --check HEAD` exit 0). Issues are pre-existing.
- Impact: noisy diffs; not a functional defect.
- Recommendation: optional later whitespace-only PR. Not this batch (would touch production paths).
- Production code: yes if cleaned later; no now.
- Independent security review: no.

#### L2. Starlette TestClient deprecation warning

- Path: venv `fastapi/testclient.py` warning during pytest.
- Evidence: one warning; tests still ran.
- Impact: future FastAPI/Starlette compatibility.
- Recommendation: track during a dependency batch.
- Production code: maybe later.
- Independent security review: no.

#### L3. `main` is not protected

- Path: GitHub branch metadata (`protected: false`).
- Evidence: list-branches API.
- Impact: force-push / unreviewed merge is possible. This batch did not enable protection (out of scope).
- Recommendation: owners should protect `main`. Report only.
- Production code: no.
- Independent security review: no.

### Documentation Drift

| Item | Path | Evidence | Impact | Recommendation | Prod code | Sec review |
| --- | --- | --- | --- | --- | --- | --- |
| `docs/test_report.md` stopped at V0.4.8.1 | `docs/test_report.md` | No current-main pytest/vitest until this batch | Readers use stale PASS/PARTIAL | This batch appended a SHA-dated current section | no | no |
| Audit prompt UI sentence | `GROK-CODE-AUDIT-PROMPT.md:41` (old) | “桌面端 UI 重构尚未开始” | Wrong auditor precondition | This batch replaced it | no | no |
| Status date 2026-08-22 vs main 2026-08-28 | `docs/v1_implementation_status.md:3`; `docs/v1_acceptance_status.md:3` | Multiple merges (#3–#11) after that date | Status looks current but is not | Later docs-only refresh; do not tick release boxes | no | no |
| Historical ZIP/EXE hashes presented beside current gates | `docs/v1_acceptance_status.md:41`; `docs/acceptance_report_20260822.md:11-12` | SHA-256 of 2026-08-22 staging | Hash reuse against checklist A/I | Mark historical; rebuild from current SHA | no | no |
| README still accurate on V1.0 | `README.md:5-9` | “V1.0 Windows DesktopHost 正在开发验收中，尚未发布” | Aligns with checklist | Keep | no | no |
| Version files agree | `pyproject.toml:3`; `frontend/package.json:4`; `release/version.json:3-5` | all `0.7.0` / Beta | No version drift this SHA | Keep | no | no |

This batch did **not** edit `docs/v1_release_checklist.md` checkboxes, V1.0 claims, or DH results.

### Security

Static scan (path:line:kind only; values not copied here):

| Class | Result |
| --- | --- |
| PEM private keys / GitHub PAT / AWS AKIA / live `sk-` | none |
| `.env` | not present |
| `.env.example:19` | placeholder `postgresql://novel_studio:change-me@localhost:54329/ai_novel_studio` |
| Test/e2e DSN literals | `frontend/src/e2eDatabaseContract.test.ts:29-32` and similar — example `user:password@db.example`, used to reject unsafe URLs |
| Test secret assignments | `tests/test_credential_vault.py`, `tests/test_model_runtime_v070.py`, Playwright specs — fixture strings |

No real user DSN, token, or production secret was observed in tracked files. Independent security review: **not required for this docs-only PR**. Release checklist still requires P0/P1 security review before V1.0.

### Repository Hygiene

| Item | Evidence | Recommendation |
| --- | --- | --- |
| 37 root-level `*.json` validation reports | `collaboration_scope_*.json`, `narrative_*.json`, `migration_*.json`, `v0.5.*.json`, etc. | Later move under `docs/evidence/` or `.runtime/`; not this batch |
| No `LICENSE` | fact | Record only; do not add a license in this batch |
| No repository-owned Actions workflow | no `.github/` | Report only; do not add workflows |
| `frontend/pnpm-lock.yaml` without npm lock | this batch used `npm install` because pnpm is unavailable; did not commit a lockfile | Later standardize the package manager |
| Deletable branches (report only) | `grok-phase1-feature-closure`, `grok-phase1-acceptance` after PR #1 close | Owner decision; this batch deleted 0 branches |
| Draft PR #12 | `feature/plugin-contract-v1-declarative` @ `a0fc3f3`, unmerged | Untouched |

## Test evidence (this run only)

See `docs/test_report.md` § Current main. Summary:

- Backend full: FAIL overall (exit 1) — 766 passed / 36 failed / 27 skipped / 0 xfail
- Frontend full Vitest: PASS (exit 0) — 376 passed / 89 files
- Typecheck: PASS (exit 0)
- Production build: PASS (exit 0)
- Whitespace vs HEAD: PASS; historical tree: FAIL (pre-existing)
- Secret scan: no live secrets
- Version: PASS `0.7.0`

Not executed: Playwright, real PostgreSQL full suite, backup/restore, real Providers, DH-01–DH-08, Windows package smoke.

## Non-goals confirmed

- PRODUCTION CODE CHANGES = 0
- TEST CONTRACT CHANGES = 0
- SCHEMA / MIGRATION CHANGES = 0
- PLUGIN PR #12 CHANGES = 0
- REAL PROVIDER REQUESTS = 0
- REAL CREDENTIAL ACCESS = 0
- RELEASE CLAIM CHANGES = 0
- OLD BRANCHES DELETED = 0

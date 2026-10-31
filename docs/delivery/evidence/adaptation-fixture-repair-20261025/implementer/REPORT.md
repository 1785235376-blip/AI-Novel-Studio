# Phase 7 adaptation fixture repair

Base: 5eb983fd620ef905aa4dc1afae80b756ee7e7078 (detached worktree `../studio-adaptation-fixture-repair`).
Only repository change: `tests/test_phase7_adaptation_authorization.py`.
No production changes, route replacement, dependency overrides, commits, or pushes.

## Proven root cause

1. `app/adaptation_api.py` context requires `branch_manuscript_v1` for branch requests whenever the bound branch authority is callable. `app/dependencies.py` binds the original `branch_manuscript_service.for_scope`. The old fixture enables no flag, so requests return the intentionally fail-closed feature-disabled 404 before capability evaluation.
2. Merely enabling the flag fixes the capability and audit tests, but materialization still yields zero chapters: the old fixture writes only a mainline chapter. `AdaptationService.create` resolves the original branch owner when a branch is selected; mainline content is deliberately not a fallback.

Controlled results, all actual worktree imports with network connections blocked:
- Original review logs preserved byte-for-byte in `baseline-adaptation.stdout` and `.xml`: 5 passed / 3 failed.
- Fresh isolated clean canonical rerun in `isolated-baseline.stdout` and `.xml`: 5 passed / 3 failed.
- Flag-only intervention, test snapshot `flag-only-test.py`, logs `flag-only.stdout` and `.xml`: 2 passed / 1 failed (zero materialized chapters).
- Final repair `final.stdout` and `.xml`: 10 passed, including two new regressions.
- Reverse file order `reverse.stdout` and `.xml`: verifies module fixture flag cleanup does not break the local adaptation suite.

## Minimal test-only repair

A module-local autouse monkeypatch fixture explicitly opts into branch manuscripts and disables acceptance-mode suppression; it intentionally does NOT enable adaptation lifecycle revision semantics because these are legacy API compatibility tests. Environment changes are restored by pytest.

The fixture still uses the original application, services, membership, role, and trusted-session wiring. It creates a chapter through the authenticated original collaboration endpoint and writes the sensitive source document through the original authorized application service. A distinct mainline decoy remains, proving that branch content is not silently borrowed from mainline.

All original capability 403, invalid-session 401, content-free audit, and duplicate-materialization idempotence assertions remain. Successful setup and approval response assertions now prevent misleading downstream missing-ID failures. Added actual foreign-workspace actor/project/branch cases to the existing capability test. Materialization additionally compares independent target/source chapter IDs and exact document content via the original branch owner.

New regressions check exact branch source IDs/versions/documents and nonmutation of both owners; disabled branch flag returns the exact feature-disabled payload for both list and create. This disabled-feature regression does not replace or weaken any expected-403 assertion.

## Reproduction and integrity

`run.sh` and `run.py` contain the exact runnable commands and isolation settings. Each log starts with its command, canonical base, and actual import paths. Use RUN_LABEL to select an isolated runtime directory; no real PostgreSQL, network, or model calls are admitted. HOME, both XDG roots, NOVEL_DATA_PATH, TMPDIR, cwd, PROJECT_ROOT and PYTHONPATH are explicit. The existing canonical virtualenv supplies dependencies. The initial review runner used NOVEL_DATA rather than the actual NOVEL_DATA_PATH setting; this repair's fresh baseline and all intervention/final runs use the correct setting.

`production-before.sha256` and `production-after.sha256` match. `git diff --check` passes. `SHA256SUMS` hashes the test, patch, scripts, reports and raw stdout/XML artifacts. Production files remain identical to canonical (git diff names only the test).

Only the two targeted suites were verified; this is NOT a full-suite green claim. No production defect was established.

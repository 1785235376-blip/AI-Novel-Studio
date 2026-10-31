# Adaptation authorization fixture repair

Date: 2026-10-25. Base: `5eb983fd620ef905aa4dc1afae80b756ee7e7078`.

Independent review: **PASS**, no blocking findings in this bounded test-only scope.

## Scope and diagnosis

The only executable repository change is `tests/test_phase7_adaptation_authorization.py`, SHA256 `ec890d7caccc020780ba81a007d0de9e96dffedd80b18cca1fb49f628de1dd96`. This delivery also adds documentation and evidence. No production code, manual-review implementation, frontend, owner, route, permission function, or service binding is changed.

The existing branch adaptation routes require explicit `branch_manuscript_v1` opt-in before capability evaluation. The stale fixture enabled no flag, producing feature-disabled 404 rather than exercising authorization. Enabling the flag alone then exposed a second stale assumption: the fixture seeded mainline content, but branch adaptations correctly read the original branch manuscript owner, producing an empty materialized project.

The repaired fixture explicitly opts into branch manuscripts using module-local pytest monkeypatch cleanup, creates its chapter through the original authenticated collaboration API, and updates its document through the original authorized application service with a registered admin actor and actual expected version. A distinct mainline decoy proves there is no fallback. Adaptation lifecycle opt-in remains disabled because these tests cover the legacy proposal API.

Original member 403, invalid-session 401, lead capabilities, content-free audit and materialization idempotence assertions are retained. Additional real foreign-workspace cases strengthen authorization. Source snapshots and materialized documents are checked against the original branch owner; source/target IDs must differ. Two new tests cover exact branch snapshot identity/nonmutation and intentional feature-disabled responses without replacing any existing expected-403 assertion.

## Verification

All runs used actual repository imports, existing dependencies, isolated HOME/XDG/data/tmp, explicit cwd/PROJECT_ROOT/PYTHONPATH, File storage, in-memory credential vault and mock provider. External socket connections were denied; no live PostgreSQL or model/provider calls were admitted.

- Preserved original compatibility baseline: **5 passed / 3 failed**.
- Fresh correctly isolated canonical baseline: **5 passed / 3 failed**.
- Controlled flag-only intervention: **2 passed / 1 failed**; materialized branch chapter count is zero.
- Final repaired targeted files: **10 passed**, 11.18s.
- Reversed file order: **10 passed**, 11.71s.
- Independent reversed file order: **10 passed**, 9.94s, with environment restoration assertions after every test.
- Independent sentinel run: **5 passed**, 9.60s, starting with nonempty `EXPERIMENTAL_FEATURES=adaptation_lifecycle_v1` and `V1_ACCEPTANCE_MODE=true`; original values restored after every test.
- Independent byte comparison: all 595 tracked app/src files identical to canonical. Only the authorization test differed at review freeze.
- `git diff --check`: passed. Before/after production hashes match.

Warnings include existing Pydantic schema-name shadows, Starlette TestClient deprecation and pytest import-rewrite timing. These targeted results do not establish full-suite, PostgreSQL, live model/provider, frontend or deployment readiness.

## Evidence and portability

Evidence directory: [adaptation-fixture-repair-20261025](evidence/adaptation-fixture-repair-20261025/README.md).

It contains captured stdout/XML for every listed run, the exact flag-only test snapshot, original execution wrappers, repair patch, production/source hashes, and the independent review report. Failed assertions, response statuses, test counts, timings and generated identifiers are preserved from the original captures, not reconstructed.

For public delivery, the machine-specific absolute workspace prefix in text evidence is replaced literally with `${WORKSPACE}`. No other byte transformations were performed on copied artifacts. The local originals remain preserved outside this delivery; `PROVENANCE.json` records both original and published hashes and the replacement count per artifact. Published logs are therefore path-redacted captures, not claimed to be byte-identical raw originals. Original wrappers are evidence snapshots; their Python `${WORKSPACE}` strings require substitution before execution.

Use the included portable rerun script with an existing virtualenv Python and repository checkout to verify the final tests without relying on the original machine path. No runtime databases, manuscript records, credentials, cache, virtualenv or generated project data are included.

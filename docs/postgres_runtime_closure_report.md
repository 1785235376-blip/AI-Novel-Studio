# PostgreSQL Runtime Closure Report

## 1. Status

```text
PASS
POSTGRESQL REAL VERIFIED
Previous Parallel Batch: PARTIAL → PASS
```

## 2. Environment

```text
PostgreSQL: 16.4, Visual C++ build, 64-bit
Runtime: official EnterpriseDB portable PostgreSQL
Docker: unavailable; not used as verification evidence
Host: 127.0.0.1
Port: 54329
Database: ai_novel_studio
Verification databases: ai_novel_studio_fresh, ai_novel_studio_upgrade
User: novel_studio
```

The runtime is located under the project-private `.runtime/postgresql-16.4` directory. It is a real PostgreSQL server, not SQLite, a mock, an in-memory repository, or a stub.

## 3. Migration 014

### Fresh DB

The exact SQL migration files were executed in filename order against an empty database:

```text
001_initial.sql → 014_scope_authorization_foundation.sql
Result: PASS
Schema version: 0.5.5-scope-authorization-foundation
```

Independent schema inspection confirmed:

- `domain_role_assignments`
- `permission_assignments`
- `authorization_audit_events`
- `idx_domain_role_principal`
- `idx_permission_principal`
- `idx_authorization_audit_scope`

### Upgrade from previous schema

An isolated database was migrated through 013, then a `workspaces` sentinel was inserted before applying 014. The dedicated 014 runner was executed twice.

```text
Migration run 1: REAL_VERIFIED
Migration run 2: REAL_VERIFIED
Existing sentinel + version count + table count: Preserved|1|3
Result: PASS
```

The dedicated 014 runner safely recognizes a fully applied migration. The repository-wide raw SQL chain remains intended for a fresh database and is not generally idempotent.

## 4. Authorization

```text
ADMIN: PASS, cross-modality inside assigned scope
DOMAIN_LEAD: PASS, domain-specific descendant access
PermissionAssignment: PASS
DomainRoleAssignment: PASS
Scope: Workspace/Project/Storyline/Branch PASS
Multi-domain: NOVEL/IMAGE/VIDEO assignments PASS
Cross-scope denial: PASS
Missing assignment denial: PASS
Invalid scope behavior: PASS
```

Scope persistence covered Workspace, Project ownership, Storyline, Branch, relationships, reads, and isolation. No delete behavior was invented because the current foundation exposes no delete contract.

## 5. Transaction Atomicity

`scripts/verify_authorization_postgres_atomicity.py` used the real PostgreSQL repository and queried the database after both paths.

```text
Commit assignment: PASS
Commit audit: PASS
Forced audit conflict: OBSERVED
Rollback assignment residual: NONE
Preexisting conflicting audit preserved: true
Partial state remaining: no
```

Assignment and audit commit in one PostgreSQL transaction. The rollback scenario deterministically inserts a conflicting audit ID with different payload, forces the second statement to fail, and confirms the assignment did not remain.

## 6. File/PostgreSQL Parity

`scripts/compare_authorization_backends.py` executed the same logical scenario on File and real PostgreSQL.

Covered scenarios:

- Workspace/Project/Storyline/Branch create and read
- ADMIN descendant and cross-modality access
- DOMAIN_LEAD access and domain isolation
- explicit permission inheritance
- NOVEL/IMAGE/VIDEO multi-domain assignments
- cross-workspace and cross-scope denial
- missing assignment
- invalid/incomplete scope errors
- run-isolated assignment and audit persistence counts

```text
PostgreSQL server version query: 16.4
postgresql_real_verified: true
file_postgres_parity: MATCH
Result: PASS
```

## 7. Tests

```text
Authorization transaction verification: PASS
Scope/Authorization parity: MATCH
PostgreSQL/Lore failure retest: 10 passed
Context comparison isolation, twice: 2 passed + 2 passed
Real PostgreSQL full regression: 188 passed, 1 skipped, 0 failed
File/default full regression: 180 passed, 9 skipped, 0 failed
```

## 8. Remaining Skips

With PostgreSQL configured, eight environment-related skips became real executions. The sole remaining skip is:

```text
tests/test_lore_contract.py:79
Migration 004 is intentionally absent in Phase 1
```

It is an explicit historical Phase-1 test intent, not an unavailable PostgreSQL skip.

## 9. Fixes Made

Only defects exposed by real PostgreSQL verification were changed:

1. `app/repositories/postgres/session.py` now sets PostgreSQL sessions to UTC. This makes `timestamptz` serialization match File/Pydantic UTC behavior instead of leaking the server's `+08:00` session rendering.
2. `tests/test_context_backend_compare.py` seeds its authoritative File fixture into PostgreSQL, removing test-order dependence on a preloaded `sample_novel`.
3. `scripts/compare_authorization_backends.py` compares run-scoped persistence counts, so unrelated prior verification records cannot cause false parity mismatches.
4. `scripts/verify_authorization_postgres_atomicity.py` was added for deterministic real commit/rollback evidence.

No collaboration, permission, autosave, Context Pack, API, realtime, or multimodal feature was added.

## 10. Reviewer

```text
High: None
Medium: None
Low: no Git metadata at the project root
Low: raw runtime command outputs are not immutable artifacts
Low: one intentional legacy Phase-1 skip remains
Final Reviewer Gate: PASS
```

The reviewer independently queried the fresh, upgrade, and main databases and confirmed the server identity, schema objects, upgrade sentinel, transaction residual state, and parity persistence evidence.

## 11. Final Gate

```text
[x] PostgreSQL connection successful
[x] Real PostgreSQL version confirmed
[x] Migration 014 fresh execution PASS
[x] Existing DB → Migration 014 PASS
[x] PostgreSQL Scope persistence PASS
[x] PostgreSQL Authorization persistence PASS
[x] Authorization successful transaction PASS
[x] Authorization atomic rollback PASS
[x] Scope isolation PASS
[x] Multi-domain assignment PASS
[x] File/PostgreSQL parity PASS
[x] File backend regression PASS
[x] Autosave regression PASS
[x] Context Pack regression PASS
[x] Full regression 0 failed
[x] Reviewer found no release-blocking High/Medium defect

Previous Parallel Batch: PARTIAL → PASS
```

Recommended next milestone: minimal actor identity and authorization runtime exposure. Wait for a separate development task before starting it.

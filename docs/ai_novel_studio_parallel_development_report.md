# AI-Novel-Studio Parallel Development Report

## 1. Repository Baseline

```text
Current Version: V0.5.5
Highest completed phase before this batch: Phase 3 — Revision & Optimistic Concurrency Foundation (PASS)
Current batch: Parallel Foundations (PASS after PostgreSQL Runtime Closure)
Git State: unavailable; project root has no .git worktree metadata
Backend State: File operational; PostgreSQL 16.4 REAL VERIFIED through Migration 014
Baseline Regression: 150 passed, 9 skipped
```

The repository already contained Workspace → Project → Storyline → Branch, proposal lifecycle, branch revision CAS, ContextPolicy, NarrativeContext, 4 Narrative rules, and 8 Continuity rules. Authorization, autosave, transport-neutral application contracts, and Context Pack v2 did not exist.

## 2. Agent Execution

- Agent S — PASS, read-only repository map, milestone audit, conflict-hotspot and ownership map.
- Agent A — PASS after Runtime Closure, authorization implementation and both backends verified.
- Agent B — PASS, autosave/data-safety foundation.
- Agent C — PASS, task/runtime/event contracts over the existing runtime.
- Agent D — PASS, deterministic Context Pack v2 pure component.
- Agent R — PASS, final read-only audit found no release-blocking High/Medium issue.
- Root — shared composition, flags, ContextService integration, review fixes, regression and report.

## 3. Parallelization Result

Agent S ran first. A, B, and C then ran concurrently with disjoint ownership. D started when B released a slot. R ran only after A/B/C/D and Root integration. The shared workspace had no Git/worktree isolation, so `app/config.py`, `app/dependencies.py`, API/bootstrap, repository bundle/factory, package exports, and final documentation remained Root-owned.

## 4. Changes

### Authorization / collaboration

- `app/authorization.py`
- `app/repositories/authorization_interfaces.py`
- `app/repositories/file/scope.py`
- `app/repositories/postgres/scope.py`
- `app/services/authorization_service.py`
- `tests/test_authorization_foundation.py`

### Autosave / data safety

- `app/autosave/contracts.py`
- `app/autosave/dirty_state.py`
- `app/autosave/scheduler.py`
- `app/autosave/coordinator.py`
- `tests/test_autosave_foundation.py`

### Application contracts

- `app/application/contracts.py`
- `app/application/events.py`
- `app/application/task_service.py`
- `app/application/runtime_service.py`
- `tests/test_application_contracts.py`
- `tests/test_runtime_service_contracts.py`

### Context Pack v2 and Root integration

- `app/context_pack_v2.py`
- `app/services/context_service.py`
- `app/config.py`
- `.env.example`
- `app/repositories/bundle.py`
- `app/repositories/factory.py`
- `app/dependencies.py`
- `tests/test_context_pack_v2.py`

## 5. Database Changes

- Migration: `database/migrations/014_scope_authorization_foundation.sql`.
- Schema: domain role assignments, direct permission assignments, and authorization audit events.
- File backend: one Windows-safe atomic replacement commits an assignment and its audit event together.
- PostgreSQL backend: one transaction commits an assignment and its audit event together.
- Scripts: `scripts/apply_authorization_migration.py` and `scripts/compare_authorization_backends.py`.
- Verification status: **POSTGRESQL REAL VERIFIED**. Fresh 001→014, existing 013→014, repeated runner safety, transaction rollback, and File/PostgreSQL parity all passed on PostgreSQL 16.4.

## 6. Tests

```text
Baseline full pytest:                         150 passed, 9 skipped
Integrated targeted suite:                    30 passed
Context/authorization targeted suite:         31 passed, 1 skipped
Post-hardening autosave suite:                  7 passed
Final post-hardening full pytest:              180 passed, 9 skipped
Real PostgreSQL full pytest:                  188 passed, 1 skipped
Failures:                                      0
```

The remaining skips include environment-dependent PostgreSQL coverage. A Starlette/httpx deprecation warning remains unrelated to this batch.

## 7. Behavioral Compatibility

- Existing single-user/default-scope behavior remains available.
- File behavior remains operational and full regression is green.
- PostgreSQL behavior through Migration 014 is real verified.
- `ENABLE_CONTEXT_PACK_V2` defaults to false. The disabled ContextService path does not add a context-pack field, and the pure builder does not parse candidates when disabled.
- Existing JobManager and Runtime remain the sole execution/status sources; no second queue was introduced.

## 8. Permission Architecture

- `ADMIN`: highest role, cross-modality inside its assigned scope.
- `DOMAIN_LEAD`: domain-specific and below ADMIN.
- `ModalityDomain`: NOVEL, IMAGE, VIDEO, extensible without a global `user.role`.
- Multiple `DomainRoleAssignment` and `PermissionAssignment` records may coexist per principal.
- Grants bind Workspace, Project, Storyline, or Branch and inherit only from an ancestor scope.
- Scope structures reject incomplete or over-specified levels.
- Assignment plus audit persistence is atomic in each backend implementation.
- Authentication, user directory, revocation, explicit deny, and realtime collaboration are deferred.

## 9. Data Safety

- Dirty state uses monotonic content generations.
- Idle debounce, periodic safety save, focus/document/chapter switch, and application-close flush are supported.
- Saves are serialized per document and triggers coalesce; a newer generation is saved after an in-flight older generation.
- Failed saves remain dirty and expose retryable/non-retryable failure state.
- Observer/logger exceptions cannot strand the save guard.
- Closed coordinators reject later edits; close checking and dirty visibility share the coordinator lock to prevent the reviewed close/edit race.

## 10. Remaining Work

```text
DONE: Authorization domain and File persistence
DONE: Autosave/data-safety component foundation
DONE: Transport-neutral task/runtime/event contracts
DONE: Feature-flagged deterministic Context Pack v2 foundation
DONE: Authorization PostgreSQL migration, transaction, scope and parity closure
DEFERRED: Authentication, revocation/deny, event delivery, editor lifecycle wiring, realtime collaboration, distributed jobs, multimodal generation pipelines
```

## 11. Recommended Next Milestone

The PostgreSQL verification milestone is complete. The next recommended milestone is minimal actor identity/runtime authorization exposure, without realtime collaboration or new permission semantics.

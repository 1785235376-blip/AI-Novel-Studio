# Project retirement privilege-inheritance evidence reconciliation

Read-only audit at source2997fda0da66099463df093ac5b368569eaa9d19. No new tests, services or database mutation were performed for this reconciliation.

## Qualified conclusion

The specified defect (delete a project, recreate the same public ID, and let an old branch role operate on the new project) has a real implemented fix and retained passing File/PostgreSQL execution evidence. This conclusion covers the tested participating lifecycle paths, not arbitrary raw writers, File power-loss atomicity, exhaustive membership/session ABA, or full V2 readiness.

Retirement was introduced in cd5e8ed30bf4776078c2df5597df9db97b45344d; legacy-orphan/scope-race closure followed in62d4aaf6. Both are ancestors of the inspected source.

## Implemented protections

- PostgreSQL deletion locks the owner FOR UPDATE and removes project-specific roles, permission assignments, workspace binding, storylines and branches within the same transaction as the novel and optional audit append.
- File deletion holds original authorization/lifecycle/scope locks, quarantines the public directory, retires grants/scopes and compensates pre-commit failures. Partial physical reclamation does not restore a damaged project with former authority.
- Workspace-wide grants, memberships, immutable audit history and unrelated projects remain.
- Original AtomicPathMutationPort.create_linked_novel couples create and link in one PG session, or locked File snapshots/compensation. Ordinary and reserved creation remove same-workspace orphan authority, reject foreign-workspace bindings and defer notifications until commit.
- Grant/scope creation uses original project leases; delayed deletion reauthorizes inside its lock. Creative records require current project_incarnation; PG incarnation is the novel UUID.

## Retained actual execution evidence

Latest restored-source check at c02be1600bf89176dfd0c9f4f9b658c2f3df848e:
- p0-restored-current-file.json/.log:43 passed,37 deselected.
- p0-restored-current-pg-final.json/.log:38 passed,38 deselected.
- p0-restored-current-pg-final-postgres-runtime.json: actual PostgreSQL17.11, isolated reused UTF8 database, verified identity/OID and clean shutdown.

These paths are under docs/delivery/v2-development. The audit independently matched log SHA256 values to receipts and verified sources_changed_during_check=false. Current bytes match the recorded retirement/lifecycle/persistence owners, File+PG novel/scope repositories, authorization/collaboration-scope services and retirement/incarnation/lifecycle tests. app/api.py differs only by passing authority_lease into create_workbench_router; retirement endpoints did not change in that diff.

The broader retirement plus legacy-orphan run retains:
- scope-orphan-file-r3.json/.log:62 passed,47 deselected.
- retirement-scope-pg-final.json/.log:48 passed,47 deselected.
- retirement-scope-pg-final-postgres-runtime.json: actual PostgreSQL16.15, fresh database, all20 original migrations and clean shutdown.
- Receipt HEAD8f50e76af590f76da4714c651d2b9573dde7087f; tested pending bytes are identified by receipt hashes, not HEAD alone.
- Report: docs/delivery/v2-retirement-canvas-20261016/SCOPE_ORPHAN_FOLLOWUP_REPORT.md.

Relevant retirement implementation/tests still match. Later scope-repository changes concern workspace lock ordering and an added authority lease.

## What the passing tests establish

They read persisted role, permission, binding, storyline/branch, membership and audit rows before/after actual API/repository deletion, comparing exact retained/removed sets. They recreate the same public ID and deliberately reuse branch IDs, retain the old actor/session token and require403 PROJECT_SCOPE_FORBIDDEN. A newly authorized actor can create/read documents (201/200), while old data/assets return404. They check changed incarnation, cross-workspace recreation, graph/import idempotency isolation, create/link rollback, delayed delete/grant races and cleanup failure behavior.

## Evidence boundaries

No standalone complete serialized before-and-after snapshot was found in the final passing P0 packets. The evidence is executed persistence assertions, passing raw logs and matching source hashes. A printed PG row trace in historical retirement-pg-final.log belongs to a FAILED run and must not be represented as final acceptance evidence.

There was no exact-current whole-tree runtime rerun in this audit. The latest restored P0 selection excludes test_v2_scope_lifecycle.py; broader orphan coverage comes from the earlier combined real-backend run. Do not infer a complete security or release certification from this targeted closure.

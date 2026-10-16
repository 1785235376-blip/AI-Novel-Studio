# V2 creative project incarnation isolation

## Defect and boundary

The public project ID is a title-derived reusable slug. Project deletion removes
its original owner (File project directory or PostgreSQL novel row), but the
experimental scope store intentionally retains its separate durable documents.
The previous V2 creative service treated slug + original branch scope as enough
ownership. Recreating the same title could therefore resurrect old documents,
including source-independent drafts and documents with identical chapter bytes.

The fix is confined to `app/creative/`. It changes no legacy project deletion
implementation, original scope hashes, authorization resolver, migration, V1
acceptance baseline, RC1 artifact, or PoemSeed data. It does not purge retained
experimental assets.

## Current-owner proof

- File: a server-created UUIDv4 marker in the existing project directory. The
  original lifecycle lock serializes first access across independent scopes and
  removes the marker with the owner. Marker reads are capped at 256 bytes and
  reject symlinks/reparse points, nonregular files, invalid schema/UUID, and
  descriptor/path identity changes before reading content.
- PostgreSQL: the actual UUID primary key of the current `novels` row. Owner
  lookup uses `FOR KEY SHARE` so deletion cannot complete inside a creative
  transaction. No timestamp precision assumption or schema migration is needed.
- Documents and director proposals store their server-owned incarnation. The
  V2 store view includes only the current owner's records. Original local and
  collaboration branch scopes remain unchanged. Restarts reuse the same proof;
  ordinary metadata/title updates do not replace it.
- Transactions acquire the original scope lock before the owner guard, matching
  existing experimental calls. They hold the owner guard through the original
  atomic scope commit. Existing CAS, rollback and authorization rechecks remain
  in place. Historical records are retained when current records are merged;
  quotas count only the current owner's records.

## Recovery and retention

Pre-incarnation V2 records cannot prove their original project owner. They remain
intact in their original experimental scope storage but fail closed through V2
read, export, history and mutation endpoints. No timestamp/content heuristic
adopts them automatically. Recovery of such records requires separately reviewed
ownership evidence; this change does not provide an automatic migration/rebind
operation. A missing File marker creates a fresh identity, so manually deleting
that marker also makes older records inaccessible rather than silently adopting
them. A corrupt marker is an error and is never silently replaced.

New mutations necessarily rewrite the scope envelope, while preserving each
retained historical record's JSON value. Read-only filtering does not rewrite
scope storage. Unrelated collections and other projects remain untouched.

## Evidence notes

The original repeated live HTTP failure is preserved by the browser verification
worker. The first lifecycle PostgreSQL run exposed a new test-fixture teardown
bug: the reused fixture captured its original ID while the test replaced it with
a fixed title-derived slug. Its actual failed receipt and log remain in
`creative-lifecycle-postgres.{json,log}`. The fixture was replaced only in the new
regression module, with a constant captured slug and exact-owned-row cleanup
assertions. No previous assertion or skip was weakened.

The failed run's one known synthetic owner and one scope document (six creative
documents and three proposals) were archived before exact-key cleanup. See
`creative-lifecycle-failed-fixture-snapshot.json` and
`creative-lifecycle-fixture-cleanup.{json,log}`. No wildcard cleanup was used;
post-cleanup checks proved zero rows for that owned synthetic slug.

Final profile receipts and counts are recorded separately in the delivery report.
The lifecycle regressions explicitly cover repeated same-title recreation,
retained raw records, active-owner capacity, stable process restart, equal creation
timestamps, unrelated projects/collections, branch scope, unauthorized requests,
revocation rollback, independent-scope first access, and deletion waiting for an
in-flight mutation. File-only corruption checks cover malformed/oversized marker
content, invalid UUID/schema, directories and symlinks. These tests make no paid
model calls and do not claim real-model quality or Windows desktop acceptance.

## Final frozen-source verification

- File: `creative-lifecycle-final-file.json` / `.log`: **131 passed, 97 skipped**,
  72.24 seconds. Includes the new lifecycle module, unchanged creative foundation
  and workflows, and the existing File project-lifecycle regression suite.
- Real PostgreSQL: `creative-lifecycle-final-postgres.json` / `.log`: **98 passed,
  103 skipped**, 129.44 seconds. Includes the new lifecycle module and unchanged
  creative foundation/workflow suites. Runtime receipt:
  `creative-lifecycle-final-postgres-postgres-runtime.json` confirms PostgreSQL
  17.11 at `127.0.0.1:55432/v2_creative_tests`; the helper shut down its owned
  server after the run. Each new PG lifecycle fixture additionally proves zero
  remaining owner/scope rows for its exact synthetic slug after cleanup.
- Skips are the existing opposite-backend selections plus the new File-only
  marker checks in the PostgreSQL run. Both runs report one existing
  Starlette/httpx deprecation warning. Neither is a new full-repository run.
- Both final profile receipts record `sources_changed_during_check: false`.
  Their hashes for the three modified/new backend modules and new lifecycle
  test module match the final files. No prior tests/assertions were changed.
- Exact repeated real HTTP/File check: **6 passed**, 14.8 seconds, with matching
  before/after source hashes. Evidence:
  `creative-live-repeat/final-stable/source-identity.json` and its run/JUnit
  receipts. The fixed title-derived IDs, exact counts and cleanup assertions
  are unchanged; the pre-fix failure remains retained separately.

Backend files: `app/creative/project_store.py`, `app/creative/service.py`,
`app/creative/proposals.py`. New regression file:
`tests/test_v2_creative_project_lifecycle.py`. No commits, pushes, catalog or
manifest regeneration were performed by this task.

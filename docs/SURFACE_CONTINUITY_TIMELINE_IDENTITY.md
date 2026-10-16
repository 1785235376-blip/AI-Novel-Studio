# Continuity Timeline identity and original-owner correction

## Scope

Hosted PostgreSQL verification of `d9d2df3a` exposed a real owner mismatch in
`test_stored_facts_stale_without_chapter_change_and_cancel_does_not_write`:
`TimelineEvent.id` accepts the opaque public ID `time`, while the original
`timeline_events.id` column is UUID. The original table's `novel_id` also remains
a UUID foreign key, whereas the domain `project_id` is a public novel slug.
Migration 007 added continuity metadata; it did not replace those original types.

The correction is confined to the original PostgreSQL continuity repository and
File parity guards. There is no new Timeline store, migration, public endpoint,
model constraint, service substitution, or change to existing tests.

## Identity and ownership

- Public IDs and payloads remain byte-for-byte identities, including opaque and
  non-ASCII strings. UUID-valued event IDs retain their original storage key.
- Opaque event IDs receive a deterministic UUIDv5 storage key in the original
  `timeline_events` table. The key is global, matching the File continuity
  repository's existing global event-ID namespace. It is never a public alias.
- `project_id` resolves only through `novels.slug`. A UUID-shaped slug is still
  a slug and cannot silently resolve through `novels.id`.
- An optional explicit `novel_id` may name the same project's slug or its actual
  PostgreSQL UUID. Foreign, missing, null, or ambiguous slug/UUID targets fail
  closed. File accepts its corresponding explicit public project identity.
- New rows retain the public event ID in `details._source_id`, so the existing
  original-owner Story Timeline serializer returns that identity.
- Existing continuity UUID rows remain readable without a `_source_id` marker.
  A pre-existing Story-only row is not adopted, rewritten, or turned into a
  continuity row merely because it has a matching ID or source alias.

## Append-only and failure semantics

Create takes the original novel-owner lock and a Timeline storage-identity
advisory lock. Exact same-project retries return the stored payload without
rewriting changed fields. The post-insert identity check also validates an
`ON CONFLICT` result before commit.

All Timeline reads check the payload identity, stored project, actual novel FK
owner, and any source alias. Candidate rows at the storage UUID, payload ID, or
`details._source_id` must resolve unambiguously to exactly one original row.
Foreign-project reuse, opaque-ID/UUID collisions, UUID spelling aliases,
inconsistent owner metadata, and ambiguous public aliases raise explicit
`TIMELINE_PROJECT_MISMATCH` or `TIMELINE_IDENTITY_CONFLICT` errors. Missing projects
cannot create rows. Scoped lists and evidence reads cannot leak a conflicting
owner's payload; project lists retain public-ID sort order.

File keeps its existing append-only JSON document and cross-process coordinator,
adds project existence/explicit-owner checks, rejects cross-project ID reuse,
and rejects ambiguous duplicate identities on create/get/project/evidence reads.
No automatic data repair or rebinding is performed.

## Verification

New tests: `tests/test_surface_continuity_timeline_identity.py`.

- Uses the existing `mounted` File/real-PostgreSQL fixture and unchanged backend
  gates at both `/api` and `/api/v1` prefixes.
- Covers opaque, non-ASCII and UUID IDs; slug-to-actual-FK storage; get/list/evidence;
  append-only retry; fresh repository reads; public ordering; concurrent retry;
  missing project; foreign reuse; explicit owner mismatch; ambiguous IDs.
- PostgreSQL-only cases inspect the actual original table and cover legacy UUID
  rows, explicit physical owners, UUID key collisions, Story source aliases,
  corrupted physical ownership, UUID-shaped novel slugs, ambiguous owner aliases,
  and alternate UUID spellings.
- Existing stored-facts stale detection and cancel-without-write assertions are
  unchanged and included in the affected regression run.

Local results and exact command are recorded in the verification report below.
Real PostgreSQL 16 remains hosted-only: local skipped cases are not database
validation, and no synthetic Session result is presented as PostgreSQL evidence.
No credentials, models, external paid providers, frozen protocol files, original
tests, or migrations 001–020 were changed. The historical independent audit
remains BLOCKED; this implementation verification does not replace it.

### Local verification receipt (2026-10-07)

- New identity matrix: **14 passed, 26 skipped** (the unchanged real-PostgreSQL
  backend gate), 40 collected.
- Affected compatibility: **139 passed, 131 skipped**, including all original
  continuity tests, stored-facts finding review, mounted integration, and core
  Story record/API follow-on tests.
- `git diff --check` passes for the two edited repository files.
- Static review checked the SQL against migrations 001 and 007. This is a narrow
  implementation review, not an independent audit or database execution result.

Commands used the existing isolated runner:

```sh
/workspace/scratch/b8734129d01d/r2-run.sh python -m pytest -q \
  tests/test_surface_continuity_timeline_identity.py

/workspace/scratch/b8734129d01d/r2-run.sh python -m pytest -q \
  tests/test_surface_continuity_timeline_identity.py \
  tests/test_surface_finding_review.py tests/test_continuity_*.py \
  tests/test_surface_core_story_records.py tests/test_surface_core_story_record_api.py \
  tests/test_r3_mounted_contracts.py
```

Raw receipts: `/workspace/shared/continuity-timeline-identity-final.log`,
`/workspace/shared/continuity-timeline-identity-compatibility.log`, and
`/workspace/shared/continuity-timeline-identity-collection.log`.

Rows that historically placed a physical novel UUID in `project_id` instead of
its public slug are rejected as inconsistent owner metadata. They are not
silently rebound or automatically repaired. UUID event IDs with consistent
public project identities are retained and explicitly covered. The new
`test_legacy_physical_uuid_project_metadata_is_not_rebound` inserts the exact old
physical-UUID project metadata into the original table, asserts all affected
reads/retries fail closed, and verifies the historical row remains unchanged.

**Remaining boundary:** real PostgreSQL 16 execution of the final published
revision is still hosted-pending. The original failing business assertion must
pass there unchanged before claiming the PostgreSQL correction verified.

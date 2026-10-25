# Passive ordinary generation project binding: storage foundation

Base: `d070c9f6354b76a1594e388cb0825fb280933c63`.

## Delivery boundary

This adds a passive internal identity contract to the ORIGINAL File and PostgreSQL
GenerationRepository implementations. It creates no new owner, queue, state store,
table, migration, or execution authority. Existing JobManager serialization and restart restore do NOT preserve this internal
field yet. No API or JobManager producer consumes or emits it. This is repository
capability only, not protection of newly created tasks. No HTTP response/request shape changes. This is NOT activation
of keyed ordinary job protection and NOT a historical acceptance/retry fix.

Existing genuinely unbound records retain their original save/get/load compatibility.
They are not deleted, hidden, backfilled, or silently upgraded. Adding a binding to
an existing unbound record through save is rejected. Removing, replacing, or changing
a saved binding through save is rejected. Out-of-band editing that erases the only
binding cannot be distinguished from a legacy record without a migration or separate
registry; neither is introduced here.

## Contract

`ordinary_project_binding` is a server-only future persistence field, never a client
input or reusable execution grant. Its strict V1 object requires every field below,
including explicit nulls; unknown fields, unknown versions, boolean versions, malformed
UUIDs, and field presence with null/non-object values fail closed.

- `schema_version`: integer 1.
- `project_incarnation`: original `file:<canonical UUID4>` marker or
  `postgres:<canonical UUID>` owner.
- `job_id`: canonical UUID, equal to record `id`.
- `project_id`: equal to record `novel_id`.
- `chapter_id`: nonempty identifier or explicit null.
- `operation`: continue, rewrite, polish, brainstorm, or review.
- `actor_id`, `workspace_id`, `scope_type`, `scope_id`: identifiers (scope_type is a
  known scope kind) or explicit null.
- `scope`: explicit null for local identity, or strict original ordinary scope
  (`kind`, `workspace_id`, `project_id`, `storyline_id`, `branch_id`), including nullable
  components and original hierarchy validation. PROJECT/STORYLINE/BRANCH project
  identity matches the binding. WORKSPACE scope carries null scope.project_id while
  the binding independently pins the target project. This is identity, not permission.
- `experimental_origin`: explicit null, or `branch_manuscript` if and only if the
  scope is BRANCH. Other origins (including author_context, character_author, and
  selection_assistant) are intentionally unsupported by this narrow contract.

All identity fields also must be explicitly present in the outer durable record and
match the binding. This deliberately is NOT the current Job.public serializer, which
omits some null fields. A later trusted capture/serialization seam is required.

Ordinary bindings cannot coexist even with null Graph/adaptation/director/image/OCR
binding fields, OCR output evidence, or director terminal evidence. Specialized
operations/origins are excluded. Original specialized validation, serialization,
capabilities, and evidence contracts are unchanged.

## Original persistence behavior

File uses CreativeProjectStore.existing_owner_only plus its original owner_lease and
project lifecycle lock, through the original job write. Missing markers are never
provisioned. Delete/recreate of the same project/chapter external IDs cannot adopt a
bound retained job. Reads hide invalid/replaced ordinary owners; load_all skips invalid
records. Ordinary payload IDs must match their File basename.

PostgreSQL keeps original SELECT FOR KEY SHARE owner resolution and generation row
locking in ONE existing repository database transaction. There is no second connection,
new database, or owner lookup outside that session. Original row.novel_id must match
the current owner UUID; ordinary durable ID and operation must match the SQL row.
The original request._repository_payload preserves the complete binding via a detached
copy, without pruning explicit nulls. Original source/chapter/snapshot checks remain.

The compatibility-named graph_job_binding/check_graph_job_update functions now dispatch
the disjoint ordinary contract first; their original specialized branches are retained.

## Verification

Focused original-repository tests cover real File creation, cold reopen, deletion and
same-slug/chapter recreation, missing marker observation, lifecycle lock held through
atomic write, malformed/mixed/unknown/downgrade/upgrade cases, immutable identity,
filename mismatch, and exact Graph/adaptation/director/OCR/image round trips.

PostgreSQL tests are OFFLINE PROTOCOL tests against the actual repository using real
ORM models and PostgreSQL SQL compilation. They exercise same-session KEY SHARE/row
lock ordering, payload isolation, owner/row mismatch, reads, strict schema, and immutable
updates, and same-session rejection of mainline chapters belonging to another project.
They do not simulate real transaction isolation, foreign keys, or concurrency.
Live PostgreSQL: **NOT_RUN**. Real provider/model/network calls: **NOT_RUN**.

Tests use the shared existing .venv with this worktree's cwd/PYTHONPATH/PROJECT_ROOT,
isolated HOME/XDG/data/tmp, provider/database environment removed, and socket network
connections blocked. No production fixtures or alternate database were used.

## Explicit source-integrity limit

This is a project-owner fence, not full chapter-source/SQL-row consistency validation.
The bound chapter identifier is immutable data. File persistence does not resolve that
identifier to a current chapter. PostgreSQL save additionally rejects an ordinary
mainline chapter whose resolved chapter.novel_id differs from the locked project UUID,
within the existing save transaction only; specialized, legacy, and registered-branch
paths are unchanged. Reads do not newly resolve chapter identity: for example, a
corrupt payload with chapter_id=null and a non-null SQL chapter foreign key is outside
this foundation's read validation. Current source existence, deletion, branch authority,
chapter incarnation, and payload/row source reconciliation must be checked by the
later activation/mutation seams, without guessing or migrating historical identities.

## Required later work before any activation claim

A trusted keyed-admission seam must capture original owner identity, verify generation
and source repositories use the same root/database, and serialize/restore the passive
field separately from public HTTP projections. Cached manager reads, TaskCenter,
events, review, retry and mutation boundaries still need original-owner verification
composed with existing authorization/source/accounting/preview checks. Last-mutation
owner fencing must use the original mutation transaction/lease without a second PG
connection or long model-duration lock. Existing callbacks remain non-restorable.
Historical unbound treatment requires an explicit product decision, not a slug-based
backfill. This foundation supplies none of those later activation steps.

### Recorded checks

- Focused File + PostgreSQL offline protocol suites: **96 passed**.
- Final independent reviewer evidence: **48 probes passed** on frozen final hashes,
  plus the narrow guard probe (three PASS checks and the unsupported read-side
  chapter reconciliation boundary CONFIRMED). The evidence rerun adds no unique coverage.
- Final broad selected regression INCLUDING the mainline chapter-owner guard: **260 passed**
  (focused suites, generation restart recovery, admission receipts, worker authority,
  and idempotency), 3 existing warnings, 64.45 seconds.
- The initial broad runner had a multiprocessing import/entrypoint error. It was
  corrected with a `__main__` guard and the clean rerun passed; the failed runner
  output is not treated as a product failure or passing evidence.
- `git diff --check`: passed. Primary canonical worktree remains unchanged.

Portable synthetic-only evidence, exact final logs, runner and independent probes:
[Evidence manifest](../delivery/evidence/passive-job-owner-foundation-20261025/README.md).

## Primary integration check

The six reviewed implementation/test/document files and evidence were copied byte-for-byte onto `652004ba931a55f9368183e0cf6aaec249204687`; production files at that base are identical to the tested d070 base (only audio review documentation was added). All delivered SHA-256 entries matched before integration. A narrow primary smoke test then passed **5 cases**, with 2 existing warnings, including File reopen/replacement/missing marker and PostgreSQL offline chapter-owner controls. This is a composition check, not extra unique coverage or real PostgreSQL verification. Commands and path-sanitized stdout are preserved in the evidence directory.

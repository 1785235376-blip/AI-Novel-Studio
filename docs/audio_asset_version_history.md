# Audio Asset immutable history — implementation contract

Task baseline (2026-10-25): repository `1785235376-blip/AI-Novel-Studio`, branch `work/hermia-backend-contracts-20261025`, commit `11d8615cccb688462ff814d025b339e1b6eb0efe`, tree `353b8669da72659da2ead4d9b34ac255504c077a`.
Feature branch: `work/audio-asset-version-history-20261025`.

This document accompanies actual implementation and verification. A milestone is not verified merely because it appears in this contract. Final commands, results, commit SHAs, limitations and independent review are recorded in the delivery report.

## M0: original owner and coverage

The sole binary/metadata owner remains `AssetLibraryService`. The existing Asset `version` is a metadata CAS revision. No supported audio API replaces the bytes of an existing Asset ID in place. A new generated/imported binary is a new Asset ID; this work does not introduce a binary overwrite API.

| Existing operation | Original path / owner call | Capture boundary |
| --- | --- | --- |
| Manual Studio audio import | `IndependentWorkspaceService.import_asset` → `assets.create` | Original create → `_write_meta` |
| Production audio candidate, including retry | `ProductionExecutionService` candidate adapter → `assets.create` | Original create → `_write_meta`; repeat must not invent a revision |
| Legacy/non-HTTP ingestion | Any original caller of `AssetLibraryService.create(kind="audio")` | Same owner, no HTTP-only wrapper |
| Metadata / provider / parameters / source links | `update_metadata` | Original `_write_meta` |
| Explicit candidate review / promotion | `promote_owned` | Original `_write_meta`; pre-review privacy retained in old revision |
| Lineage annotation | `annotate_lineage` → `update_metadata` | Original `_write_meta` |
| Relationship metadata | Original relationship adapter → `update_metadata` | Original `_write_meta` |
| Soft deletion | `delete` | Original `_write_meta` |
| Undelete | `restore` | Original `_write_meta`; original HTTP meaning unchanged |
| Text-specific result review | `review_text_result` | Existing non-audio contract unchanged |
| Binary replacement | No supported original owner path | No new replacement surface |

Repository-wide `git grep` at the fixed baseline found every `_write_meta` caller inside the original owner. Binary writes occur in `create`; other `_bin_path` users inspect/read exact existing files. The current query index is a derived projection, not a history owner.

### Lock and lifecycle order

The established `project_scope` implementation takes the Asset process lock, the original cross-process `workspace_mutation(..., "asset-library")` lock, and then the original project lifecycle owner lease. Scope-source leases, where required, precede Asset/project leases. No scope-document write transaction may be opened under the Asset/project lease. Recovery, history reads, and snapshots must preserve this order; the file lock alone does not prove multi-file crash atomicity.

### Exclusive file ownership during implementation

| Unit | Owned files |
| --- | --- |
| Owner / snapshots | `app/services/asset_library_service.py`, new `app/services/audio_asset_history_store.py` |
| Read API / authorization | New `app/creative/audio_asset_history.py`, `audio_asset_history_api.py`, `audio_asset_history_models.py` |
| Explicit recovery | New `app/creative/audio_asset_history_restore.py` and recovery-specific new files |
| Verification | New `tests/test_audio_asset_history_*.py` and task-specific synthetic runners |
| Independent review | New delivery review document; read-only review of implementation |
| Integration | `workspace_api.py` minimal mount/exact admission, contract/evidence/delivery documents |

Shared entry points are integrated by the coordinator only.

## Version identity and migration requirements

A history sequence, original metadata revision, canonical metadata digest, binary SHA-256, source version, and a newly restored candidate are distinct values. Every persisted history item must bind the original Asset ID, its actual project incarnation and scope, revision and digests. History stores verified original bytes and immutable metadata, including private origin data internally; wire projections independently authorize and redact it.

Migration is additive and lazy. An old Asset is readable through its original API. Its first captured baseline is only its currently verifiable state; earlier revisions are an explicit historical gap. Do not derive historical versions from timestamps, Job lists, Canvas history or Timeline history. No global backfill or parallel project owner is introduced.

## Read and recovery requirements

History reads use current identity, membership, branch, feature and incarnation authority, including final return checks. Current formal Asset visibility does not grant access to an earlier private candidate. Source availability must be checked through the current source authority, with bounded traversal and no raw hidden paths, credentials or unauthorized IDs in responses. Cursors bind actor, scope, incarnation, permissions and the history/current boundary.

The new history restore flow is separate from the existing `POST .../assets/{aid}/restore`, which remains undelete. Inspect is read-only and cannot initialize a missing project identity, generate media, or reserve a candidate. Confirmation binds the inspected current and target identities/digests, permission state, incarnation, expiry and unique operation ID. Changed or revoked observations fail closed.

A successful historical restore creates a new unapproved candidate through the original Asset owner; historical approval is traceability only. No Canvas/Timeline/Canon/pin is rewritten; no generation, rendering, automatic approval or adoption occurs. If the original review contract cannot carry a new historical candidate, that limitation must be exposed explicitly rather than bypassing review.

## Persistence and verification requirements

Committed history must never claim a successful snapshot before bytes and metadata are verifiable. The head, immutable records, derived query index and operation receipt need a documented durable commit/recovery protocol. Recovery is bounded by exact Asset/operation identity, never a full storage scan or arbitrary orphan takeover. Same operation key and payload yields one result; a changed payload conflicts. Capacity exhaustion fails explicitly without history eviction.

Verification requires real File owners, actually mounted HTTP, original API-prefix compatibility, multiple processes and restarted fault injection. PostgreSQL, if available, means the original PostgreSQL project owner combined with the File Asset owner, never a newly invented PostgreSQL Asset store. Unavailable validation is NOT_RUN. Synthetic test bytes only; no user media, private history, secrets, paid models or credential changes.

## Protected surfaces

No frontend, SDK, TaskCenter, Production query slice, dependency lock or global routing redesign. The original Asset owner and the smallest exact route mount/admission changes are disclosed separately. Push only this feature branch; no main updates, force-push, merge, release or deployment.

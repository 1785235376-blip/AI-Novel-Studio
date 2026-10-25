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

## M1–M2 storage slice: implemented behavior

The original audio `_write_meta` now prepares a verified binary blob and canonical metadata record before atomically replacing the original current metadata with `_audio_history_head`. The current metadata is the sole commit authority. There is no second authoritative head/index: reads walk only the head-linked chain. Prepared but unreachable files never appear as successful versions. Identical content is reused only after size/digest verification. A committed update followed by a lost acknowledgement remains exactly one visible revision after reopening the owner.

Internal record identity is its canonical record SHA-256 (`version_id`). `history_sequence` starts at 1 for the first captured state, independently of the original `asset_version`: a legacy v7 first captures as sequence 1, then v8 as sequence 2. Metadata digest excludes only the private current-head pointer. Binary digest is the original `sha256`.

Storage is additive under `assets/.audio-history/<asset-id>/`; both immutable records and blobs have `.bin` filenames to retain the original admitted native Windows reader's filename restriction. Record contents are canonical UTF-8 JSON, not media. Ordinary current Asset JSON/bin paths and the lazy derived Asset query index are unchanged.

Limits: 100 captured states per Asset, 128 MiB retained bytes per Asset (including prepared files), 512 KiB per record, and 8 MiB / 5 seconds for a chain read. Capacity exhaustion refuses the mutation without deleting history; this also means delete/undelete can be refused at the limit. These are per-Asset history limits, not a claim of a project-wide historical-byte quota.

Reads of uncaptured old Assets return `UNCAPTURED` with no invented items and do not migrate. The next real metadata mutation captures the verified old current state and the new state. Coverage is `PARTIAL` when the earliest known original revision exceeds 1.

On Windows, validation covers process termination/restart and the original native admitted reader. No power-loss durability or directory-flush guarantee is claimed.

### Actual first storage run

Command (new synthetic profile and storage paths supplied by the runner):

```text
python scripts/run_audio_history_tests.py -q tests/test_audio_asset_history_owner.py tests/test_studio_workspace_identity_history_contract.py tests/test_asset_library.py tests/test_audio_asset_history_http.py::test_mounted_history_returns_head_and_original_bytes --basetemp=.runtime/audio-history-20261025/owner-first-temp
```

Result: **15 passed, 1 failed**, exit 1. The sole failure is the intentionally preserved pre-mount history HTTP 404. The 8 new owner cases and 7 original compatibility cases passed. This is not a claim that the entire command passed. Earlier native-reader failures and the initial environment collection error are retained separately. Follow-up HTTP, hard termination, candidate, authorization and independent review results are not implied by this first run.

## M3 read API and the M4 safe boundary

All new endpoints retain the original `/api` mount, project/actor/branch/feature checks and original authority lease. Only exact method/path admission and one new router mount were added to `workspace_api.py`; no global router redesign or other query owner was changed.

| Method | Under `/api/projects/{nid}/studio/assets/{aid}` |
| --- | --- |
| GET | `/history?limit=1..50&cursor=...` |
| GET | `/history/{version_id}` |
| GET | `/history/{version_id}/download` |
| POST | `/history/{version_id}/restore-preview` |
| POST | `/history/{version_id}/restore-confirm` |
| POST | `/history/restore-resolve` |

`version_id` is a 64-character immutable record digest. The list includes current revision/head, explicit coverage and a cursor; historical items expose history sequence, metadata revision/digest, binary digest/size and a closed metadata projection. Private parameters, prompts, provider/model fields, old review provenance, internal paths and unauthorized source identifiers are not returned.

ASSET source traces distinguish a real pinned source revision/digest from `UNVERSIONED_DECLARATION`. A non-current audio source pin must resolve to the original committed source chain and pass the historical snapshot's current actor/scope/feature checks; a currently formal source does not authorize its earlier private snapshot. `CURRENT` and `HISTORICAL_VERIFIED` describe source metadata, and each trace explicitly says `content_verified: false`: referenced source blobs are not claimed to have been downloaded/verified. Non-ASSET/Chapter/Creative Document source traversal and old non-audio pins are rejected, not guessed or treated as grants. This is a remaining source-coverage limitation.

The new history-only row adapter can read an original private production candidate for its real creating actor, validating the original server-only media-origin contract. Formal production rows still require the original formal-Asset validation. No Job is created or used as the version-history owner.

Authority fingerprints use the original session binding generation, original File authorization/identity bytes plus file identities, enabled features, actual scope and incarnation. PostgreSQL code uses bounded original row identities/xmin and includes user/membership changes, not only effective grants. This PG combination has not run. New history/source metadata traversal is bounded; this does not claim to rewrite the original global authorization repositories' internal I/O limits.

Cursors have a process-local HMAC and a ten-minute lifetime. They reject a changed current head, actor, scope, incarnation or observed authority state; restart/cross-worker use requires restarting pagination. They grant no access. Each return rechecks present authority.

Current/source metadata has its own request budget (8 MiB, bounded count and five seconds). Each history chain has a separate 8 MiB/five-second budget; detail/download/inspect can walk it more than once. There is no claim that total request I/O is only 8 MiB. History reads select and verify the requested immutable bytes; list/detail metadata do not proactively read every historical blob.

### Actual restore status: unavailable, not a successful restore

Preview is genuinely read-only: current/target, safe display differences, metadata digest difference, selected historical byte availability, and explicit limits. Missing target bytes produce an unavailable preview without a token. Missing owner identity is not initialized. Soft-deleted current Assets retain the original undelete-first boundary.

Preview returns `confirmation_available: false`, `admission_available: false`, `review_path_available: false`, `candidate.created: false`, `observation_token: null` and `expires_at: null`. Confirmation and receipt resolution fail with **409 AUDIO_HISTORY_RESTORE_ADMISSION_UNAVAILABLE**, after current authorization. No candidate, signing/confirmation capability, operation journal, receipt, approval, Job, model execution, Canvas/Timeline/Canon update or pin mutation is created.

Two concrete gaps prevent opening the write path:
1. The original Studio project quota is enforced through `project_usage`, which scans the asset metadata directory. Reusing it would violate the requested bounded exact-operation recovery boundary, while skipping it would bypass the original 1,000 Asset / 512 MiB current-binary quota.
2. Original Production review is bound to its real Job candidate and immutable context. It cannot safely review a newly copied historical candidate. No Job or historical approval is forged to bridge that gap.

No dormant candidate minting or fake idempotency protocol was added. Full inspect-confirm-create-review recovery, unique-operation journal/receipts, and restore-specific concurrency/restart validation remain unimplemented.

## Additional owner safeguards and compatibility

Every changed internal audio metadata commit now receives a real next CAS revision even when an existing server-side caller supplied the exact current revision/head without pre-incrementing it. No-op writes keep the same history head; stale revision/head, project binding or binary identity still fail. Existing query fixtures use this internal path; the original tests were not edited.

Admission checks the exact resulting chain's encoded bytes before committing a new head, so a successful new state cannot exceed its own chain-read byte limit. Canonical record verification makes that accounting exact. New history allocation also checks the original asset filesystem's free bytes against the original 64 MiB safety reserve. This is admission, not a cross-application disk reservation. Historical bytes have their own per-Asset limits; the original project quota does not claim to include all historical storage.

Original `/restore` remains undelete. Audio delete/undelete now can additionally refuse when current bytes cannot be verified or history/version/capacity limits would be exceeded. Non-audio writes retain their prior path. Original atomic current-file rename does not provide a parent-directory fsync guarantee, so **all platforms are limited to the tested process-crash/restart claim; power-loss durability is not claimed**.

## Actual expanded verification (2026-10-25)

```text
python scripts/run_audio_history_tests.py -q tests/test_audio_asset_history_owner.py tests/test_audio_asset_history_http.py tests/test_studio_workspace_identity_history_contract.py tests/test_asset_library.py --basetemp=.runtime/audio-history-20261025/final-specialist-temp
```

**53 passed, 3 warnings in 25.60s; exit 0.** These are new synthetic File owners and the actual mounted application. They include real spawned-process CAS and same-key creation, four real `os._exit` process-termination points followed by reconstructed owners, pre/post-commit exception injection, legacy v7 lazy capture, immutable corruption rejection, old private snapshot privacy, real permission/membership/session ABA, final-return revocation, feature revocation, actor/branch/incarnation cursor isolation, real lineage pins, private production-origin ingestion, no-write preview and explicit confirmation refusal. The low-space admission test injects the measured free-space result; no physical disk was filled. No successful restore is claimed.

AST parsing passed. The warnings concern pre-existing schema-field naming and Starlette/httpx deprecation; no dependency lock was changed.

PostgreSQL: **NOT_RUN**. `DATABASE_URL`, `TEST_POSTGRES_DATABASE_URL`, `E2E_DATABASE_URL`, `POSTGRES_URL`, `TEST_DATABASE_URL`, `PGHOST` and `PGDATABASE` were absent. Only variable presence was recorded, never credential values. No PG-native Asset persistence was introduced.

Two existing asset-query/cursor compatibility cases reach **503 ASSET_QUERY_INDEX_UNAVAILABLE**. A direct synthetic diagnostic exposed an original index `OSError [Errno 9] Bad file descriptor` during its fsync path. The same two cases were rerun in a **new detached worktree at exact original commit/tree** and failed with the same 503. They are not counted as passed. No protected query/index implementation or original query test was changed; its full compatibility acceptance remains blocked. Raw comparison logs are retained.

Raw stdout/stderr is preserved losslessly in gzip with SHA-256 of decompressed bytes. Intermediate failures, environment errors and subsequent passing runs are distinct files; no previous session's logs are used as current evidence.

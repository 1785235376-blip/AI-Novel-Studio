# Realtime collaboration and bounded production sync

## Verification boundary

These additions deepen the existing Collaboration owners. They add no first-level
workspace, second manuscript database, account system, cloud endpoint, executable
plugin or migration. PoemSeed Local Interop 1.0 and historical frozen contracts are
untouched.

- Realtime engineering: `PARTIAL`; synthetic in-process push contract implemented.
- Production realtime server, WebSocket deployment, browser co-editing and OT/CRDT:
  `NOT_CONFIGURED` / `NOT_RUN`. HTTP participant reads are snapshots, never a claim
  of realtime transport.
- Production sync engineering: `PARTIAL`; local synthetic transport, exact rich
  block deltas and durable checkpoints implemented.
- Production cloud, cloud authentication, end-to-end encryption/key lifecycle and
  branch-to-branch production sync: `NOT_CONFIGURED`.
- Encryption fixture: `MOCK_ONLY`, explicitly plaintext. An associated-data digest
  is a fixture consistency check, not authentication or cryptography. It is not
  applied to transfers. No data is silently called encrypted.
- File and real-PostgreSQL cases share the existing storage-backed tests. The
  default run selects File cases; real PostgreSQL requires the existing explicit
  test profile. No SQL session is mocked.

The machine-readable UI/API catalog is
`contracts/functional-surfaces/realtime-sync.v1.json`. Strict request schemas are
`contracts/functional-surfaces/realtime-sync-models.v1.json`.

## Ownership and persistence

`WriterRoomService.realtime` owns `RealtimeCollaboration`. It resolves its parent's
store, source reader, chapter owner and membership authority live. Its participants
and operation journals reside in the existing `ExperimentalStore` scope document,
with full workspace/project/storyline/branch fences. The local-author scope remains
explicitly local.

`MainlineDocumentAdapter` delegates to the original `ChapterService`. Its journal
stores intent and base evidence only. Before an external write it durably claims
that operation. A missing/failed receipt changes it to `UNKNOWN`; restarting cannot
replay the write. Recovery reads the original chapter/version and permits explicit
adoption only when the next version exactly matches the intended document. A
matching document is reported as unconfirmed evidence, not proof of exactly-once
execution. Closing without replay preserves evidence.

`BranchDocumentAdapter` delegates to `BranchManuscriptService.read/commit`. The
branch service is injected as `writer_room_service.branch_documents`. Its
`commit(..., state=active_scope_document)` performs the manuscript write and
receipt in the same scope transaction as the realtime journal. The branch service
must use the same `ExperimentalStore` instance/profile as the writer-room owner.
A final authorization or receipt failure rolls back both changes. No mainline
fallback exists. Branch chapter identities, history and lifecycle are owned by the
branch authority, not the realtime adapter.

`OfflineSyncService.production` owns `ProductionSync`. Device registrations,
immutable manifests and transfer checkpoints use the same existing scope document.
Transfers reference the existing offline outbox/inbox. No second queue applies
manuscript edits. Receipt delivery only creates `PENDING_REVIEW` in the original
inbox. Existing diff3 choices, revision locks, original chapter CAS and unknown
write recovery remain mandatory for reconciliation.

## Realtime protocol

1. Join an exact chapter with its current version and a bounded public device ID.
   Actor and trusted-session digest bind the participant. Raw session tokens are
   never persisted.
2. Presence is an expiring 60-second lease. The states are `ACTIVE`, `EXPIRED`,
   `DISCONNECTED`, `LEFT`, `REVOKED`. Restart changes all old-epoch active leases
   to disconnected. Reconnect requires a current version and clears old cursors.
3. Cursor/selection coordinates are paths through rich-document `content` arrays
   plus Unicode code-point offsets. They are neither flat-text nor UTF-16 offsets.
   Both endpoints must refer to valid text nodes in the declared document version.
4. Text edits are ordered rich-text-node range replacements. Supported edits retain
   existing marks/blocks and obey revision locks. Structural document editing is
   outside this adapter. A request ID is bound to the entire original payload.
5. Prepare compares exact source version and document digest. A conflict preserves
   current document evidence and the submitted edit operations; it never performs
   an implicit rebase, last-write-wins or an OT/CRDT transformation.
6. Apply is an explicit second command against the operation's own CAS version.
   It rechecks participant, lease, source, flags, permission and original owner.
   Successful events contain base version, resulting version/digest and edits.
7. Cancel is valid for prepared/conflicted intents only. An uncertain external
   write requires inspect/adopt/close-without-replay recovery. A freshly authorized
   session for the same actor may reconcile or cancel old intents, but cannot
   replay an old session's edit operation.

`SyntheticRealtimeTransport.subscribe/publish` delivers actual callbacks. Every
callback rechecks its original session, membership, feature state, participant
lease and source visibility. Delivery is confined to exact scope and chapter.
Rejected/failed subscribers are removed. Cursor events include only structural
coordinates; committed edit events contain authorized edit operations. A revoked
session is reflected in active presence immediately when its saved guard fails.
A new process requires new subscriptions; there is no hidden replay buffer.

Limits: 100 participants, 200 operation records, 8 MiB realtime metadata per scope,
512 KiB request/document budget, 64 edits/request, 64,000 inserted characters/edit,
and 30 levels of rich-text paths. Bounded histories retain at most 100 transitions.
Capacity errors fail closed; automatic journal deletion or compaction is not
implemented and no revoked record is silently recycled.

## Sync manifest, delta and transfer contract

- Device IDs are actor-scoped public routing labels, not authentication. Device
  epochs and permanent revocation fence later manifests/transfers. Revocation
  never promises to recall a received copy or backup.
- A manifest binds current channel selection/version, device epoch, scope digest,
  object IDs/versions/digests/byte counts/tombstones, a change set and its parent
  manifest version. Its own digest is validated before transfer.
- Deltas use deterministic rich top-level block splices plus title/root metadata.
  Reconstruction validates both base and exact target digests. Insert and
  tombstone forms are explicit. Deltas do not flatten rich text.
- Manifest details re-resolve current source visibility; list summaries do not
  include manuscript-bearing deltas. A stale source is labeled `STALE` and cannot
  be dispatched through that manifest.
- Current wire payload remains the established reviewed snapshot envelope v1.
  Delta reconstruction is a real tested contract; network delta compression is
  not claimed.
- A transfer explicitly lists existing outbox messages and acknowledges the copy
  boundary. They are sorted by original sequence. It does not queue or send
  additional chapters on the user's behalf.
- A dispatch owns a 30-second worker lease. Concurrent resume during a live lease
  fails closed. After restart/expiry, resume is explicit and rechecks selection,
  source versions, device/channel revocation, host session and feature state.
- Each original outbox ACK precedes the secondary transfer checkpoint. If the
  checkpoint is lost after ACK, resume adopts the durable ACK without re-export.
  If delivery happened but ACK was lost, the explicit retry uses the same original
  message ID/envelope and the original inbox's idempotency guard.
- Transport errors become `PAUSED`; no background retry runs. Cancel/revoke stops
  future work but cannot erase a delivery already accepted by a receiver.
- `SyntheticSyncTransport` only invokes explicitly registered in-process receivers
  and rechecks their authorization even for duplicate delivery. It opens no socket.
  The mounted production transfer API defaults to `NOT_CONFIGURED` until an
  approved adapter is provided by composition; users cannot submit arbitrary URLs
  or executable adapters.

Limits: 20 devices, 100 manifests, 100 transfer records, 20 selected messages per
transfer, 8 MiB production journal, 8 transfer attempts plus the existing outbox
retry limits. Requests inherit the original bounded strict JSON parser. No asset,
credential, model, cache or filesystem-path transfer is added.

## Functional UI surface contract

Use the existing Collaboration writer-room and offline-sync panels, their shared
DS-v1.0 primitives and original editor/review navigation. This work adds a formal
surface contract and APIs; no visual redesign or production co-editing browser
claim is made.

Required states: `LOADING`, `EMPTY`, `ERROR`, `UNAUTHORIZED`, `DISABLED`,
`NOT_CONFIGURED`, `PARTIAL`, `CONFLICT`, `REVIEW`, `RECOVERY`. Show explicit current
versions, source state and adapter verification level. Clear cached manuscript
content/cursors on source, session, project or branch changes. Preserve unsent
local edits on conflict. Do not automatically retry writes, resubmit an uncertain
operation, or let a loading-state rerender perform a mutation.

Opus may change DS-compliant layout, typography, labeling and presentation inside
these existing modules. It must not change permission/source fences, flags,
version/digest CAS, explicit apply/recovery, lifecycle/revocation, truthful runtime
labels, copy boundaries or frozen interop behavior.

## Tests

New suites:
- `tests/test_surface_realtime_collaboration.py`
- `tests/test_surface_production_sync.py`

Both parameterize actual File and opt-in real PostgreSQL cases; mounted tests
cover both `/api` and `/api/v1` and reuse real session/membership/permission stacks.
New tests opt in via `RUNTIME_FLAGS`; historical `FLAGS` fixtures/assertions remain
unchanged. Coverage includes synthetic push, source/version conflicts, concurrent
branch CAS, permission/session revocation, branch rollback, expiry/restart,
unknown-write recovery, cancellation, exact rich deltas, manifest integrity,
checkpoint/ACK interruption, worker leases, device/receiver revocation, strict
input, missing configuration and disabled/dependency states.

Also rerun the unchanged writer-room/offline-sync suites and comment-authority
seam. Hosted PostgreSQL, deployed transport and browser implementation acceptance
must be reported separately from the local File results.

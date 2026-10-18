# Original-owner ORA staging slice

`ComicOraStaging(comic, workspace)` accepts only the exact original Comic raw
scope store, independent workspace/project adapter and AssetLibraryService.
There is no router, upload endpoint, UI, generated task, review/promotion, or page
attachment. Its three server-only operations are:

1. `prepare(..., raw, archive_sha256, request_key, guard)` reparses the archive,
   requires the explicitly accepted preview hash, then durably plans exact Asset
   UUIDs and per-layer pins in the Comic owner's `comic_ora_staging_v1` collection.
2. `stage(..., receipt_id, raw, max_steps, guard)` explicitly stages/resumes up to
   eight layers (default one), reselecting identical archive bytes after restart.
3. `status(..., receipt_id, guard)` reads the receipt and original Asset state
   without a scope write. Lost acknowledgements are visible and resumable.

A caller must already hold the original authorization lease and supply its live
authority/epoch guard. No route exposure is authorized by this implementation.
All operations require current Comic and independent-studio feature gates.

## Ownership and provenance

The private `_comic_ora_origin` joins the FIRST original Asset metadata commit,
with actor, original project incarnation/scope, archive/member/canonical hashes,
receipt ID and preallocated exact Asset UUID. The original owner retains bytes,
versions, private visibility, quota, storage admission and recoverable deletion.
Staging never supplies `approved_at`, source-job/model/provider IDs, or manual
lineage. Archive sidecars cannot confer provenance or approval. Unknown raster
origin stays unverified; known generated origins cannot enter the manual review
shortcut. Generic metadata edits and promotion are blocked for this private
staging contract until a separately reviewed original import-review path exists.
Raster text is not recovered as editable dialogue.

## Separate commits and recovery

Each step takes raw scope -> original Asset -> original project owner locks; the
project lease outlives scope commit. Asset metadata and scope receipt commits
are NOT atomic together. A failed scope commit does not undo Asset.create.

- Prepare commit acknowledgement lost: same actor/request/hash returns the same
  receipt and planned IDs.
- Asset failure before metadata: original create removes only its new UUID's
  temporary/binary files. Unrelated Assets are never scanned for deletion.
- Asset metadata committed but acknowledgement/receipt failed: resume verifies
  the exact planned ID, immutable marker, original bytes and version, then
  advances only its pending receipt step.
- Crash after binary rename but before metadata: status shows an orphan recovery
  state. Explicit resume rechecks canonical PNG bytes against that exact planned
  ID. Only an exact matching orphan can be completed; mismatched bytes fail and
  are never deleted/overwritten. A pre-existing verified orphan survives further
  failed metadata writes.
- Receipt acknowledgement lost: resume verifies existing staged IDs; no duplicate
  Asset creation. Wrong actor/scope/incarnation/hash or deleted/tampered candidate
  fails closed. Original project deletion serializes against the in-flight commit;
  recreating its public slug cannot adopt an old receipt or Asset.

At most 32 receipts per current incarnation, 256 planned layers per receipt,
8 stage steps per call; original project count/byte quota and disk reserve apply
at each creation. Parser aggregate decode/PNG/ZIP limits remain unchanged.

## Evidence boundary

Tests use real File owners and genuine parametrized PostgreSQL scope/project
variants, including a concurrent deletion writer/barrier with bounded joins.
The original Asset owner remains file-backed under both backend variants.
Isolated checks run File only; root must run actual PG before integration.
No multi-Asset rollback, reviewed import, page attachment, UI workflow, or full
external-software ORA roundtrip is claimed by this slice.

New ORA reconciliation/content reads use the original bounded no-follow,
nonblocking reader. Platforms without that original safe-read support fail
explicitly; this slice does not alter the legacy default Asset reader.

Quota admission includes exact planned binary-only orphans from all current-
incarnation receipts in this scope. Original metadata-backed usage is counted
once, and completing the same orphan adds neither a second slot nor duplicate
retained bytes. No unplanned binary is adopted, scanned for cleanup or deleted.

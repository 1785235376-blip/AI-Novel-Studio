# Explicit ORA Asset review and independent-page attachment

Server-only additions to the existing `ComicOraStaging` adapter:

- `review_manifest(..., exact_archive_bytes, guard)` performs bounded no-write
  inspection and current original-Asset checks. Its digest pins actor, scope,
  incarnation, archive hash, canonical layer hashes, original candidate UUIDs,
  geometry and raster-only semantics.
- `review(..., manifest_digest, license_note, acknowledge_raster_text=True,
  max_steps, guard)` first durably records the immutable review intent. It then
  explicitly promotes up to eight original candidates per call through the
  narrowly sealed `AssetLibraryService.promote_owned` adapter. Plain dictionary
  seals, generic promotion and generic metadata/lineage approval remain blocked.
- `attach(..., existing_page_id, expected_page_version, review_digest, guard)`
  atomically changes only the existing independent Comic page and its receipt
  in the original raw scope transaction. It appends a DRAFT page revision and
  records exact attached layer IDs/page version/document digest for lost-ack
  replay. No new project/page/Asset/queue owner is introduced.

## Deliberate boundaries

Asset promotion commits are durable separately from Comic receipt commits.
Neither receipt rollback nor page CAS failure undoes review or deletes Assets.
A lost promotion acknowledgement is reconciled against the same original
candidate ID and immutable proof; the candidate is not promoted twice. Exact
attachment replay succeeds only while the same page revision/document and
current source authority remain valid. A changed page requires a new decision.

Page dimensions must equal the reviewed archive canvas. Imported layers are
placed below existing native layers, preserving their order, visibility, opacity,
geometry and canonical editable Bubble text. Raster pixels are never fabricated
as panels or dialogue. Native history/copies retain raster pins and remap only
layer/native IDs. No scaling/resampling of imported pixels is implied.

New RASTER entries carry original reviewed Asset version/hash/review-digest pins
plus bounded offsets/dimensions. Only these references use the new incarnation-
bound raster reader. Legacy unbound panel/reference reads remain unchanged,
including on a page mixing legacy native artwork with imported rasters. Imported
source dimensions and current review proof are checked before rendering/export.
Aggregate layer/source pixel limits remain active; attachment additionally counts
all repeated decoder work against the original whole-operation ORA budget.

Original provenance is NOT reconstructed or verified from archive sidecars.
Review remains explicitly UNVERIFIED_RASTER, with an author license declaration;
it never asserts manual/non-generated artwork or clears feature/source guards.
The original immutable archive/member origin survives promotion. Unknown external
text stays rasterized. Native project dialogue stays editable separately.

The caller must hold its original authorization lease and provide its live epoch
and permission guard. Scope -> Asset -> original project-owner lock ordering is
preserved, including through scope commit. Features, actor, incarnation, candidate
proofs, page ownership and CAS are rechecked. Reviewed Assets retain original
recoverable deletion behavior; deleted/changed sources make attached pages stale.

## Acceptance

File tests and genuine PG variants cover review/attachment lost acknowledgements,
atomic page+receipt rollback, exact replay, concurrent reviews/attachments,
concurrent owner deletion, source deletion, rejected generic seals, native text/
layer preservation, original book-copy remapping, re-edit and real PNG export →
parse. Missing CJK fonts remain an explicit existing prerequisite, never installed
or invented by this slice. Target-app interoperability and browser visuals remain
NOT_RUN. No routes/UI are exposed; the current reference-only frontend rejects
unsupported raster editing rather than silently resetting its layer stack.
Full user-facing ORA import/roundtrip acceptance remains open.

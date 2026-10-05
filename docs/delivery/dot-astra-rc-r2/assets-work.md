# D10: asset lifecycle and approved reference retrieval

## Scope and implementation

This work implements the local asset-safety/recovery and reference-memory portion of D10. Image generation, media decoding, video assembly, archive export/import and their provider tests are reported separately. No embedding model, vision-semantic matching or visual-consistency quality claim is made.

- `app/services/asset_library_service.py`: bounded base64 ingestion; normalized download names and declared MIME; validated asset identifiers; symlink rejection; verified size and SHA-256 before returning bytes; metadata corruption rejection; atomic binary publication; request-content/branch-bound idempotency; re-entrant process/file mutation coordination; recoverable tombstones and digest-checked restoration. Generic upload intentionally retains its existing opaque-byte contract. It does not claim that a declared image MIME proves decodability.
- Asset metadata updates now use a locked allowlist, bounded payloads, verified content, monotonically increasing versions and same-project/branch source checks. Source lineage and derivative edges reject cycles. Identical metadata writes do not create extra versions.
- `app/services/v1_capability_service.py`, visual-memory/asset-lineage block: new references begin as DRAFT. Explicit approval is expected-version guarded and records the trusted reviewer, review time, origin, evidence IDs, memory version, asset ID, asset version, size and digest. Editing clears approval. Approval persists the lexical index; all searches revalidate current authoritative records and asset content. Deleted, missing, tampered, cross-project/branch or version-stale references are excluded. Restoring an asset preserves its ID and original bytes but increments its version, requiring fresh reference approval.
- `app/services/visual_memory_index.py`: real local inverted lexical/metadata index with a persisted per-project/branch source fingerprint, Unicode normalization, English words and CJK character/bigram terms. A corrupt or tampered cache is rebuilt from approved source records. Results include exact memory/asset/version/digest provenance and matching words. `retrieval_mode=LEXICAL_METADATA`, `embeddings_available=false`, `inference_performed=false`.
- Asset reference inspection identifies current references from visual memories, research records, derivative relationships and asset source metadata. It explicitly reports that other module references were not exhaustively scanned. Recoverable deletion retains originals and relationships, rather than silently cascading destructive removal.

## API and scope contract

`app/asset_lifecycle_api.py` provides `create_asset_lifecycle_router(assets, capabilities)`. The API owner registered it on the existing application router, so both existing API prefixes inherit the routes.

- GET `/novels/{nid}/asset-trash`
- POST `/novels/{nid}/assets/{asset_id}/restore`
- GET `/novels/{nid}/assets/{asset_id}/references`
- GET/POST `/novels/{nid}/visual-references`
- PUT `/novels/{nid}/visual-references/{memory_id}?expected_version=N`
- POST `/novels/{nid}/visual-references/{memory_id}/approve` with `expected_version`
- GET `/novels/{nid}/visual-reference-search?query=...`

The new router calls the shared project/branch permission helper on every request. Collaboration requires an opaque trusted session and branch header; the server resolves the reviewer identity. Supplied branch scope must match persisted asset and reference metadata. Unbound legacy records do not match an explicitly requested branch. Local loopback operation remains compatible. Service methods do not establish authorization by themselves; trusted scope must come from the API boundary. Legacy visual-memory aliases and derivative routes must remain collaboration-blocked until their full scope migration is complete; the API integration owner was notified of that separate requirement.

`AssetLibraryService.create/list/get/content/delete/restore/update_metadata` accept a trusted `branch_id` keyword. New `AssetIntegrityError` and `AssetIdempotencyConflict` errors are distinguishable by API integration. Existing asset GET after deletion remains 404.

## UI and handoff

The existing design-system skill, token contract, component rules and IMAGE canonical reference were reviewed. No shell, token, sidebar, module-switcher or inspector geometry was changed.

- `AssetLibraryPanel`: server-backed recycle-bin discovery and restore action, loading/empty/error/retry states, recoverable-deletion explanation, correct novel-scoped deletion and success-only selection clearing.
- `AssetInspector`: existing authenticated preview/download path retained; preview reset includes project/digest changes and image decode failures are shown.
- `VisualReferencePanel`: collapsed inspector section for recorded references, reference type/entity ID/notes form, separate explicit review, expected-version submission, re-review after restoration, keyword search and exact result provenance. Draft text is kept on failures/conflicts. Model limitations and excluded stale/missing/damaged references are visible.
- The API owner added typed client methods to `frontend/src/api.ts`; all actions reuse the central session/branch header path. No credentials or session tokens are added to persistent browser storage.

UI refinement opportunities for the later design pass: replace manual entity IDs with authorized entity selectors; improve dense provenance lists; add rich result navigation and explicit edit/archive controls; add content thumbnails without claiming the original-file preview is a generated thumbnail. Preserve explicit review, conflict handling, reversible deletion, provenance and truthful lexical-only messaging.

## Verification and limitations

- Focused backend tests: `tests/test_asset_lifecycle_r2.py`, `tests/test_asset_safety.py`, `tests/test_asset_library.py`; run under the repository team's isolated `r2-run.sh` environment. 29 tests passed. JUnit is `assets-tests.xml`.
- Focused frontend tests: `AssetLibraryPanel.test.tsx`, `AssetInspector.test.tsx`, `VisualReferencePanel.test.tsx`. Nine tests passed, including create-before-approve, version-bound review, failure-preserved form text, real API parameter shapes and server recycle-bin restoration.
- Full shared TypeScript build check (`tsc -b --pretty false`) passed at integration time. Shared design-token guard passed.
- Browser geometry/visual: BLOCKED before assertions. The pinned Playwright Chromium binary was absent. An official browser install was attempted but returned invalid/truncated ZIPs. System Chromium 154 was then attempted with an isolated temporary profile, including an approved escalated run; browser startup still aborted with `socket() failed: Operation not permitted`. Thus the 4 geometry cases plus compact desktop case did not execute product assertions. No screenshots or baseline updates were fabricated. Windows visual/native acceptance remains NOT_RUN.
- Real embedding/vision/provider behavior: NOT_RUN and not implemented by this lexical index. No paid model calls or user materials were used.
- The metadata capability store remains its established durable sidecar, including under PostgreSQL profiles. Native PostgreSQL asset-memory migrations are not added here. Source validation currently rechecks asset bytes when building/searching the approved index; large reference libraries need a measured incremental-index optimization before a large-scale performance claim.
- Trash retains originals indefinitely; no irreversible purge is exposed. Full cross-module reference scanning and archive reimport are not claimed by this work.

## Local acceptance sequence

1. Upload a synthetic authorized image, select it, inspect/download the original and confirm digest metadata.
2. Open reference memory, enter an entity and description, save a draft. Search should omit it until explicit review succeeds.
3. Approve, search by a description keyword (including a CJK example), and inspect the returned memory/asset IDs and versions.
4. Delete the asset, reopen the workspace, find it in the server-backed recycle bin, restore it and re-review its reference. Original ID/digest/bytes should be unchanged while versions advance.
5. With test data only, alter or remove stored bytes; downloads and restoration must fail and approved-reference search must exclude the entry.
6. Repeat across two trusted branches and users. Wrong-project/branch access and read-only writes must fail; unbound legacy rows must not appear in a branch query.

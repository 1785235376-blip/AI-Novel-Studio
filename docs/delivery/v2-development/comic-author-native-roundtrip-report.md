# Bounded editable Comic author archive roundtrip

Status: implementation, File verification and bounded independent backend/frontend review complete; final frozen frontend production build complete; root-owned PostgreSQL integration pending. This is partial IMAGE-COMIC-18 coverage, not a full Comic project archive or public reading export.

## Supported interchange

Selected independent PAGE book, 1–10 pages, with no asset, character, screenplay/shot, appearance-reference, or reviewed-ORA RASTER dependencies. Native page/panel/bubble geometry, text, framing, image briefs, supported native layer order/visibility/opacity and book/chapter/page order survive a real new-ID import. Draft IMAGE panels with missing artwork remain editable incomplete drafts; they do not acquire artwork or rendering approval.

Export includes hidden author text and image briefs. Its separate read-only preview discloses this and binds the exact book/page versions, documents, actor, destination scope and original project incarnation. Download requires explicit private-author-content acknowledgement. Reading exports are unchanged. Archive records carry only portable aliases and content, never approval, history, actor, role, source project incarnation, private paths or origin seals.

## Strict transport

Version `comic-author-assetless-page/1`; ZIP_STORED only, no compression. Maximum archive 2,000,000 bytes, 11 members, 180,000 bytes/member, 1,800,000 JSON bytes total, JSON depth 12 and 12,000 value nodes/member. The EOCD count and central-directory byte size are bounded before ZipFile allocation. Local member offsets/headers/names/size/CRC match the central metadata; generated fixed paths and exact declared member set are required. Duplicate members/JSON keys, traversal, symlinks, encrypted or compressed members, undeclared files, hash/size mismatches, appended/prepended data, unknown fields/types, nonfinite JSON, unsupported dependencies and noncanonical aliases fail closed before restoration writes.

The API authenticates/captures actor, scope and existing original incarnation before bounded streamed upload, ignores dishonest Content-Length, and rechecks authority before processing. Restore holds the original authority lease only after streaming, never across await. Errors are bounded and private, with no-store/nosniff.

## Original owners and atomic replay

The original Comic `_payload`, `_current`, `_book_row`, `_book_page`, `_book_bound`, `new_row` and `_independent_transaction` own restored content. No separate engine, registry expansion or Asset writes. All new native page rows, book row and subordinate `comic_author_archive_receipts_v1` receipt commit in the same original raw scope transaction. Every destination book/chapter/page/panel/bubble/layer ID is regenerated; layer references and book order are remapped.

A receipt is keyed to actor/scope/original incarnation/request UUID and bound to archive SHA256. Its bounded envelope contains only the original import's book/page IDs and identity metadata. Twenty non-evicted receipts align with the original 20-book limit; capacity is disclosed. Existing book storage limits apply, plus a 16MB current-author/incarnation page bound on import. Original owner deletion/recreation cannot adopt old receipts.

Exact retries return current original native rows without writes, new history, resets or duplicate creation. Changed membership, unavailable/foreign/old-owner targets yield a bounded already-completed/unavailable error. Original edits, including text, geometry and layer edits, remain intact. Inspection discovers completed attempts for the exact SHA/current owner without writing. The client persists only bounded digest/request-key/status metadata; no archive bytes, private text or credentials. Web Locks serialize restore admission across tabs; durable storage failure/readback failure blocks dispatch. Unknown attempts require explicit recovery; a deliberate second copy has a separate explicit action. No automatic retries.

## Evidence

- `comic-author-native-security.json`: 90 passed, 90 PostgreSQL variants skipped. Real mounted routes on both /api and /api/v1; native export → inspection → restore → reopen → edit/save → replay; hidden text/brief/layers; source unchanged; cross-project transfer; recreated owner; malformed transport; role/session/branch/flags; streamed authority/incarnation changes; precommit rollback, postcommit lost acknowledgement, concurrent replay; unavailable result handling; receipt capacity.
- `comic-author-native-final.json`: 116 passed, 108 PostgreSQL variants skipped, including original Comic collections regressions. Later changes to archive parser/added security tests are covered by the security run; original collections implementation was unchanged.
- Final exact backend source reconciliation is recorded separately, since independent frontend edits changed aggregate runner snapshots during backend tests.
- Independent client review: 17/17 focused tests passed; stale explicit-new attempt race reproduced, fixed with expected completed predecessor recheck under Web Locks, then directly rechecked with zero additional dispatch and preserved PENDING identity. Delayed restore/download responses after scope retirement cannot select old content or save a stale export. See `comic-author-independent-client-review.json` and `comic-author-independent-client-final-tests.log`.
- `comic-author-native-frontend-final.json`: 216/216 tests across six files, production `tsc -b && vite build`, and UI token guard passed on frozen sources. Existing large-chunk warnings remain. Frontend mounted contract tests and existing collection/publication regressions are recorded by this original-runner receipt; no browser/visual validation, actual browser multi-tab acceptance, or live frontend/backend roundtrip was run under the no-browser restriction.

Not supported: external assets or character sources, screenplay/shot dependencies, reviewed ORA raster layers, WEBTOON, full instance backup/restoration, complete project archive, imported approval/history/provenance, PDF/X/PDF-A, paid or model generation. No pushes, releases, installations or user-computer work.

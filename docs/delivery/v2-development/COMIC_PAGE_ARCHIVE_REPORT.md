# IMAGE-COMIC-18: bounded JPEG/WebP reading-copy page archives

Scope: the existing Image → Comic book publication panel now offers explicitly selected JPEG or WebP page images in an ordered ZIP reading copy. This is a partial IMAGE-COMIC-18 increment, not completion of long-image, EPUB, print conformance or editable project archive requirements.

## Contract and ownership

- Existing book, approved page, source, privacy, actor/scope, project-incarnation, renderer and cumulative publication budgets remain the owners. No persistence/store, alternate approval, automatic publication or promotion is introduced.
- Separate `/page-archive-preflight` and `/export-page-archive` schemas require `image_format`, `loss_mode`, and `quality`. JPEG is always lossy. Lossy JPEG/WebP quality is one of 60, 80, 95, 100; WebP lossless requires null quality. All choices are bound into the exact publication digest with the original page/review pins.
- Existing PNG CBZ and PDF inputs/bindings/output paths remain unchanged. Archive output is `application/zip` with `.zip`, never mislabeled CBZ.
- Saved chapter/page order is preserved; reading direction is metadata and does not reorder content. Each full-page member has dimensions and SHA256 in the manifest. Headers bind the final ZIP and publication digest. Only flattened RGB is delivered; source/actor paths, EXIF, ICC and XMP are not copied.
- WebP lossless is decoded and compared byte-for-byte against the flattened RGB page before release. JPEG quality 100 remains lossy. No editable text/layers, color/profile fidelity, print conformance or external-reader acceptance is claimed. Original editable pages and approvals are never changed.
- A full snapshot and authority/source/privacy/review recheck runs after archive serialization; no bytes are returned on a stale or unauthorized final state.

## Deliberate admission envelope

The entire codec request is admitted before renderer/codec allocations: at most 1,048,576 cumulative page pixels, eight pages, and 2048 pixels per edge. This admits one 1024×1024 page or several smaller pages; it does not mean eight full-resolution pages. Larger/high-resolution books remain unsupported by these formats.

Codec work reserves 256 bytes per pixel plus 8 MiB per page against 512 MiB. At the absolute pixel/page ceilings the reservation is 320 MiB. This conservative engineering envelope covers RGB/input/output copies, native scratch, verification decoding and retained encoded pages. Whole-output admission reserves 8 bytes per pixel plus 64 KiB per page and 4 MiB for manifest/license under the original 64 MiB archive ceiling. Original source/decode/render/encoded cumulative budgets continue to apply.

JPEG is baseline, nonprogressive and nonoptimized, with fixed 4:4:4 sampling. WebP has fixed method 0; lossless uses quality 0 for lowest compression effort. No arbitrary encoder optimization, pass count, thread or effort knobs are admitted. Actual max-size entropy encode/decode tests exercise all three choices. These are bounded-input engineering limits, not a native-code wall-clock timeout or protection against a defective native library. Limits should not be widened without new codec measurements and review.

Unavailable existing JPEG/WebP support fails clearly at preflight/export; no dependency installation is attempted.

## Validation

The focused backend suite exercises actual JPEG/WebP bytes, ordering, dimensions, SHA256 and deterministic output, exact lossless RGB and quality 100 loss, schema/format/mode/quality drift, cumulative preallocation limits, unavailable codecs, no owner mutation, late source/privacy/review and trusted-session revocation. Original PNG CBZ, PDF, layer and pinned CJK tests are run together. PostgreSQL cases are prepared through the original opt-in fixtures and are to be run by the owning integration process; this worker starts no database/service.

Final runner receipts, test counts and independent-review outcomes are recorded by the owning integration task. No browser acceptance, external reader validation, paid API/model action, user-machine action, push, main merge or release is performed here.

### Backend evidence at review freeze

- `comic-page-archive-final.json/.log`: 239 passed, 231 PostgreSQL cases deselected, zero skips. Includes pinned Noto Sans SC/FontTools CJK legacy gates.
- The independent review correction checks decoded codec format/geometry/mode before verification decode. `comic-page-archive-geometry-final.json/.log`: 94 passed, 88 PostgreSQL cases deselected, zero skips.
- `comic-page-archive-backend-reconciliation.json` compares 1,522 backend/test/script/CI source hashes. Only codec geometry-check and archive test files changed during the full run; every other relevant source remained unchanged. The affected rerun backend sources are stable and match freeze. Raw receipts remain intact; frontend edits are explicitly excluded from this backend-only reconciliation.
- Frontend download admission uses an additive per-call bound in the original transports: ZIP bytes are limited to 64 MiB while streaming, before accumulation/hash/save. Unrelated audio/video downloads are not globally capped.

### Frontend evidence at review freeze

- 260 focused tests passed: 60 archive panel lifecycle, 38 archive client, 19 streaming helper, 105 existing CBZ/PDF and 38 bounded-media regressions.
- 34 neighboring book/editor and mounted Image owner tests passed.
- TypeScript, Vite build, token lint and test discovery passed. Vite retains the existing >500 kB chunk warning.
- Final `comic-page-formats-ui-{final-focused,final-types,neighbors,build,token-lint,discovery}` receipts all report stable sources and match the frozen frontend hashes. Initial superseded failure receipts are not final acceptance evidence.
- Independent backend and frontend reviewers found no remaining blocker after header-before-decode and scoped bounded-stream corrections. Browser geometry/visual acceptance was not run under the explicit no-browser constraint.

### Preserved failed-run evidence

- `comic-page-archive-focused.json/.log`: 226 passed, 224 skipped, two existing PDF fixture errors because the initial invocation used `/tmp` pytest temporary paths rather than the fixture-required owned `.runtime` basetemp. Corrected in subsequent runs, including the final pinned-font gate.
- `comic-page-formats-ui-types.json/.log`: TypeScript invocation referenced nonexistent `frontend/tsconfig.app.json`; corrected to the existing project configuration in the final types gate.
- `comic-page-formats-ui-archive.json/.log`: initial archive suite exposed a cross-realm byte-view rejection in the new streaming helper. All 22 failures shared that cause: 17 client cases were rejected before normal MIME/digest handling, and five panel cases failed download or bounded error-body handling. Replaced realm-sensitive instanceof with ArrayBuffer.isView plus Uint8Array branding; the final focused suite covers the corrected byte-view handling without weakening assertions. This raw failed run is retained rather than rewritten.

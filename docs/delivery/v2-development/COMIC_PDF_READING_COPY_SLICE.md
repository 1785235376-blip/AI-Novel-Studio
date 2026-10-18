# Comic raster PDF reading-copy slice

Base: `35d9167f63cc462052fcff3b30445a76654b95e8` in isolated `comic-pdf-slice` worktree. Internal development candidate only; no Release, main changes, paid API, model execution, queue/storage side effect, service startup or user-machine access.

## Behavior

The original Image Studio Comic book publication panel now offers a PDF reading copy. The caller must select integer DPI 36–600; there is no implicit physical-size default. Each saved ordered page has MediaBox width/height = pixel dimensions × 72 / DPI. PDF 1.4's 14,400-point maximum is enforced. Reading direction is declared receipt metadata only and does not reorder pages or panels.

Both CBZ and PDF reuse the original independent book/page owner, original approval and source pins, original compose renderer, full-page stitching and cumulative source/decode/render/encoding limits. Separate PDF preflight/export input types and format/DPI digest binding leave the existing CBZ schema and binding unchanged. Backend independent review compared CBZ before/after on the same two-page fixture: both 5,303 bytes, SHA256 `349fdedb567e758aab782378afd7ec47a57b780070b8d237dfc50877f48722f7`.

The PDF contains flattened RGB image pages, title and a bounded public reading-copy receipt. It has no editable text/layers, automatic publication, attachment/action or new execution authority. Export is withheld until a whole-request final recheck of current source/privacy, approval, versions, owner incarnation and actor/scope permissions succeeds, including changes after ReportLab serialization.

## Bounded scope

A ReportLab destination `BytesIO` cap alone would be insufficient: ReportLab retains encoded image objects and serializes the document before writing the destination. Admission therefore reserves `192 × total_page_pixels + 1 MiB × page_count + 4 MiB` against a 512 MiB request-local PDF work envelope before creating its canvas. This covers RGB/Pillow copies, bytes/digest temporaries, zlib and optional ASCII85 including Python fallback, retained image streams, stream/indirect-object concatenations and final join/output copies. It is a conservative pixel-proportional work envelope, not an OS RSS guarantee or a measurement of every allocator call. Existing source/decode/render/encoding budgets remain additional constraints.

A separate a priori serialized upper estimate `4 × total_page_pixels + 64 KiB × page_count + 4 MiB` must fit the 64 MiB output cap; writes retain the existing cumulative encoder and final-sink caps. This narrow slice admits approximately 2.7 million aggregate page pixels, less with page overhead. Many high-resolution or long books correctly reject. DPI changes physical size, not pixel budget. Preflight exposes the exact pixel ceiling for the selected page count, and the UI discloses bounded reading-copy capacity.

## Independent review finding fixed

ReportLab 4.5.1 `Canvas.drawImage` deduplicates raw RGB bytes without pixel geometry. A nonuniform red/blue byte string rendered as 320×640 then 640×320 reused the first image shape for both pages. The sink now registers a unique ordered `PDFImageXObject` per page through the same ReportLab encoder; no global cache/settings are patched. A retained regression verifies both MediaBoxes, both decoded image dimensions, full raw image bytes and characteristic red/blue pixels. Independent review reproduced the original failure and verified the fix.

The frontend reviewer also exposed same-value select events invalidating an epoch without rerender. Safe no-op guards now preserve the current selection and pending state; the regressions remain.

## Verification and limits

- Final File suite: 150 passed, zero skipped, including PDF, unchanged CBZ, reviewed raster opacity/visibility, real pinned CJK pixels and original manuscript `test_pdf_export.py`.
- Frontend worker: 156 tests passed across publication panel/client, collection/editor, mounted Image workspace, shell and primitives; TypeScript and token checks passed.
- Independent frontend review: 105 panel/client and 13 collection tests passed, no remaining scoped blocker.
- Independent backend review: exact geometry fix, conservative bounds and current-source/authority fences clear.
- Actual pypdf 6.19.0 parses generated ReportLab 4.5.1 bytes and validates ordered dimensions, page count, image pixels, receipt and no mutation.
- Initial sparse-checkout run failed because an original local-interop package was absent; materialized the existing package, with no source workaround.
- An intermediate optional-font run skipped two tests; subsequent runs use the already prepared pinned fontTools 4.59.1 and Noto Sans SC to execute them.
- A first full-font run found a test-only mistake passing a public sanitized row to a private renderer; corrected the test to read the original private row. Product code was unchanged.

Raw failed and passing runner receipts/logs are retained alongside this report. Optional disposable proof PDFs, expected original PNGs and source/DPI receipts are in `.runtime/pdf-cloud-proof/raster` and `.runtime/pdf-cloud-proof/cjk`; no third-party font bytes are committed.

Root-owned PostgreSQL and independent cloud Poppler checks follow integration. pypdf structural/pixel checks are not independent viewer acceptance. Windows/browser viewers, visual geometry, print-quality, PDF/A, PDF/X, bleed and publication acceptance remain unclaimed. All required explicit losses remain in preflight/UI/PDF receipt.

### Frontend evidence provenance

The worker's intermediate 93-pass/3-fail same-value-event run and one test-only TypeScript scope-shape failure were observed in its command transcript, not retained as raw files. This report does not present a reconstructed log as raw evidence. The final 156-case frontend suite, TypeScript and token check are rerun through the original isolated verification runner for persisted evidence. Its first invocation failed before tests because the clean PATH lacked the existing Node binary; the next invocation supplies the original runtime Node path explicitly. No dependency was installed or changed.

### Additional root-reported cloud renderer check

Before integration, root independently rendered all three retained proof pages with existing Poppler 26.05.0 at 96 DPI. Dimensions matched and the CJK dialogue was visibly legible. The hidden-raster page matched exactly; visible raster had 320 edge-pixel differences (maximum channel delta 40), and CJK had 9,122 border/glyph-edge pixel differences. Therefore external rendering is not claimed pixel-exact. Exact embedded-image equality from pypdf remains a separate proof. Root retains the independent rendered PNGs and comparison receipt for integration evidence. This check establishes a bounded cloud renderer result only, not Windows/browser/print acceptance.

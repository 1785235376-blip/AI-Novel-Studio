# Bounded Comic PDF reading-copy integration

Product: 36a2ff56f81d03b04dc76ecb62b1f2f6cce6381d. Full V2 and IMAGE-COMIC-18 remain partial / NOT ACCEPTED.

## Implemented behavior

Image Studio's original Comic book publication panel now prepares and exports actual ordered raster PDF reading copies. Caller-entered DPI binds physical size; page dimensions are pixels ×72/DPI. Format, DPI, direction and exact ordered current-approved page/version/source pins are digest-bound. Existing source/privacy, actor, scope and incarnation checks run again after complete PDF serialization, before response bytes escape. No new queue, storage owner, workflow or automatic approval was created.

Existing CBZ schema, binding and rendering remain compatible; independent before/after synthetic CBZ output was byte-identical. Text and layers are flattened in the PDF. Direction is metadata only. No editable text/layers, automatic reordering, bleed, print quality, PDF/A or PDF/X claim is made.

## Important capacity limit

This is a narrow reading-copy exporter. Before allocating ReportLab's canvas, it reserves 192 bytes per aggregate page pixel plus 1 MiB per page and 4 MiB overhead against a 512 MiB work envelope. Therefore only roughly 2.7 million aggregate page pixels fit, less with page overhead. Many long/high-resolution books correctly reject. Changing DPI changes physical size, not pixel workload. Preflight exposes the exact ceiling; the UI describes the limit. The 100-page structural maximum does not promise 100 high-resolution PDF pages.

Independent review reproduced ReportLab's geometry-blind image deduplication: identical RGB byte arrays at different rectangular dimensions reused the first geometry. Unique ordered image XObjects now preserve each page's geometry. Actual decoded PDF image dimensions, raw bytes, transforms and red/blue pixels validate the correction. Existing compression/serialization budget remains. Source authority was not weakened.

## Evidence

- Isolated final File: 150 passed, zero skipped, including real pinned CJK, reviewed raster layers, CBZ and original manuscript PDF tests. All 3,127 source files recorded by that sparse-worktree receipt match the integrated checkout.
- Integrated real PostgreSQL: 143 passed, 146 non-PG cases deselected. Existing UTF8 PostgreSQL17.11 database OID16384 reused without migration/creation. Exact 14-table row hashes match before/after; server stopped.
- Integrated UI: 317 tests across 18 suites; full TypeScript build, Vite production build and token guard passed. Builder/reviewer counts overlap and are not additive.
- PUBLIC wheel/catalog: 6 passed. Catalog 2505 operations, fingerprint e9320bbce33c50d24ceac6dd843726f5dd87120e1e7c394ed9584b0a51d27c80. Private backend remains physically excluded.
- Final PG/UI/PUBLIC receipts record the same 3,150 unchanged source files, verified against integrated checkout.

### Independent cloud rendering

Existing Poppler 26.05.0 rendered three actual original-owner fixture PDF pages at 96 DPI. Page dimensions match expected PNGs. Chinese text “原始对白” and the page/bubble layout were visually inspected and legible. Hidden raster page pixels match exactly; visible raster has 320 edge-pixel differences (maximum channel delta 40), and CJK has 9,122 glyph/frame-edge differences. External rendering is explicitly NOT pixel-exact. Exact embedded-image comparison by pypdf is a separate result.

Proof PDFs, expected PNGs, Poppler-rendered PNGs, pdfinfo, SHA256 inventories and the raw comparison are retained under comic-pdf-poppler-proof. Their four backend source hashes match the integrated source. This proves a bounded cloud renderer result for synthetic fixtures; it does not certify Windows/browser viewers, screen readers, print, arbitrary user artifacts or whole-product acceptance.

## Failures retained

An initial sparse checkout missed an existing local-interop package; the original package was materialized without source workarounds. A test passed a sanitized public row to a private renderer; that test now obtains the original private row. Final pinned-font tests run without skips. Frontend review found same-value selection events invalidating an epoch without rerender; safe no-op guards preserve current callbacks. Raw retained failures and final passes are included; intermediate transcript-only UI observations are accurately distinguished in the slice report.

Previous source 6daeac8f was archived and independently verified as 7897be0666d3fa86bd75b8023e6f393446d4e70d, exact parent 0ea2c08e, 14 artifacts / 5,568,770 bytes. Publication remains a prerequisite-bound archive bundle, not a main/PR update or release. Next independent work studies explicit opt-in reuse of reviewed local-text Graph dependencies while preserving all exact-version execution and approval fences; it is not yet integrated.

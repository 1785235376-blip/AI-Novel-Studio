# PDF page OCR through the original model node

2026-10-18. Adds an explicit `PDFPageOCRRequest` and pinned `LocalPDFOCRProvider` to the existing `VisionOCRModelNode`; no additional model runtime or job queue. The original IMAGE request, route fields and receipt shape are unchanged. PDF uses a distinct exact route schema and explicit page number. Cross-dispatch of image requests to PDF routes, or PDF requests to image routes, fails before native work.

The adapter composes the existing pinned Poppler page rasterizer and exact original Tesseract adapter. Both tool admissions participate in the route digest. It checks source/host authority, cancellation and owner identity between rendering and OCR and before returning. Original PDF digest/page, derived PNG digest and renderer digest survive the model response; original provider/model/execution identities and review-required markers are added by the existing model node. Wrong pages, malformed renderer/image hashes, additional receipt fields and changed source identities are rejected.

## Verification

`native-pdf-model-final` receipt/log: 86 passed, no skips, including real image-only PDF → Poppler → original Tesseract → original ModelNode, original IMAGE regression tests, cancellation/revocation/receipt rejection, refreshed catalog and actual public wheel. The first `native-pdf-model` run had 79 passes and one test-fixture error: a GenerationRuntime was passed where the broker expects an application runtime wrapper. The fixture was corrected to expose the original registries and generation runtime; the assertion that the existing broker does NOT admit the new PDF adapter remains intact. Original failed log is retained.

Backend API count remains 2375; fingerprint `176c657c6e0fe90b2132d00ab988296805c706199bb17319be1f6c4e414a6e7f`. No frontend changes, so TypeScript/Vite were not redundantly rerun. No database schema changes in this slice.

## Remaining boundary

The original broker still admits only the exact IMAGE native provider. No automatic host registration or Research PDF dispatch is enabled. Persisted PDF source/page binding, original JobManager integration, review/citation validation and UI selection are next. This smoke is synthetic English, not Chinese/general OCR quality, Windows acceptance, browser acceptance or V2 completion. Native process containment is not a complete parser sandbox; dependency/font pinning remains outside this foundation.

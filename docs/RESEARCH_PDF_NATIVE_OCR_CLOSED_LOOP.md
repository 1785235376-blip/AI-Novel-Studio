# Bounded native PDF OCR through original Research owners

2026-10-18. Supersedes only the pending PDF admission/integration boundaries in NATIVE_PDF_PAGE_RASTER.md, NATIVE_PDF_OCR_MODEL_SEAM.md and RESEARCH_PDF_OCR_SOURCE_IDENTITY.md. Their historical evidence remains unchanged.

## Working path

Original PDF import → explicit one-page OCR analysis → current source/incarnation and host-route preview → human dispatch consent → original broker reservation and JobManager → pinned Poppler → original pinned Tesseract → original ModelNode receipt → original generation persistence → Research review-required result → human review → reopened reviewed TXT export. No new queue, workflow engine, registry or project store.

The original document digest and explicit page remain the citation identity. A separate derived PNG hash and renderer digest are captured in the original job's `research_ocr_output_evidence`. The strict PDF binding validates evidence shape and source/page/route/text identity. Once present, original generation update guards reject removing or replacing the evidence. Research review compares its receipt copy against this durable original job evidence and the original broker admission. Reopening cannot recreate live execution authority or replay a job.

IMAGE/V1 requests, serialized bindings and receipt shapes remain unchanged; absent completion evidence adds no legacy field. PDF routes use a separate exact class/schema and pin the PDF adapter, raster adapter, original image adapter and route. Image-to-PDF and PDF-to-image route mismatches are rejected before execution. Existing generic SCAN_PDF_VISION, chart and image-understanding adapters are not enabled by this text OCR path.

## Host configuration and UI

Existing five LOCAL_OCR_* fields continue to configure the IMAGE route. Adding both LOCAL_PDF_RENDER_EXECUTABLE and LOCAL_PDF_RENDER_EXECUTABLE_SHA256 explicitly configures a separate local-pdf-tesseract-ocr route using those same explicit Tesseract/model pins. Incomplete configuration fails. Startup does not discover, install, download or execute tools. No cloud fallback or paid call is added.

The original Research source panel now offers PDF page OCR. The user selects one page (1–1000), sees only matching PDF routes, requests a preview and explicitly confirms execution. Switching page/source/project drops stale in-flight UI results. Reopened results must match the selected source version, digest and page before display. Existing review, cancellation, explicit interruption recovery and TXT export controls are reused. No shared shell, design token or component primitive changes.

## Focused evidence

- Original job seam: File 39 passed / 39 deselected; PostgreSQL 39 passed / 39 deselected. Includes real PDF OCR, durable evidence immutability, passive reopening, original IMAGE execution and source revoke cases.
- Final integrated File suite: 55 passed / 28 deselected, including actual native OCR, mounted HTTP preview/dispatch/review/export, unauthorized review rejection, host pins, original IMAGE and interruption recovery.
- Final integrated PostgreSQL suite: 28 passed / 28 deselected. Same disposable UTF-8 PostgreSQL 17.11 database OID 16384 reused, server stopped cleanly. Includes actual native PDF page recognition, persisted citation/review/export/reopening and tampered derived receipt rejection.
- UI: 11 tests passed, TypeScript and Vite production build passed, existing shared UI token guard passed. PDF tests cover explicit page/route selection, manual consent, stale page-switch preview suppression and citation-page rejection.
- First UI run passed all 11 runtime tests but failed TypeScript because a fixture copied an optional Source.content_sha256 into a required receipt field. The fixture now supplies its exact known digest literal. Assertions and original failed log are retained.
- Public wheel/catalog verification is recorded separately in research-pdf-integration-public. Test wheels and frontend bundles are not Releases.

## Boundaries

This is a bounded single-page text OCR capability, not all-pages batch recognition, layout reconstruction, handwriting/chart understanding, Chinese/general accuracy acceptance or a full parser sandbox. PDF input is at most 4 MiB; raster output at most 2048 pixels per side and 4 MiB. The renderer rejects a nonexistent page. Tool libraries/fonts are not pinned. Linux synthetic English evidence does not establish Windows/GPU or real user-document quality. Real browser visual/end-to-end acceptance is still blocked by the unavailable supported browser executable; DOM tests and builds do not replace it. The whole professional Director workbench and V2 release are not declared complete.

Final public/catalog receipt: 6 passed. API count remains 2375; backend fingerprint `e8a1e77f984dcbfe11f5b19dd9a3c055e12ef5ffb5ecf8c2aa68c23bf5efad79`.

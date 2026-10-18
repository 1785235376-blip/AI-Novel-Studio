# Native PDF page raster foundation

2026-10-18. Implemented helper; Research PDF OCR admission is not yet integrated.

`app/local_pdf_raster.py` renders one explicitly selected page through an explicitly supplied, SHA-256-pinned Poppler executable. Construction and route inspection do not execute, discover, install, register, or enqueue anything. The caller supplies the original authority guard and reviewed renderer digest. Input is bounded to 4 MiB, page to 1–1000, and decoded PNG output to 4 MiB and 2048 pixels per side. Cancellation, current executable pins, source authority, temporary-directory limits and the original native process runner are checked around execution. Returned evidence includes original PDF digest, page, renderer digest and output PNG digest.

This is subprocess containment, not a complete PDF parser or operating-system sandbox. Shared libraries and fonts are not pinned. Windows execution and general document quality remain unverified. No Research route, source binding, provider registration, queue, review gate, database schema or public/private policy is changed. The existing PNG/JPEG OCR contract remains unchanged.

## Evidence

`docs/delivery/v2-development/native-pdf-raster.json` and `.log`: 16 passed, no skips. Includes actual Poppler page rendering and actual original Tesseract ModelNode execution, rejection/cancellation/pin checks, API catalog and actual public-wheel checks. The composed OCR receipt identifies the rendered PNG; it is not an original-PDF Research citation or persisted Research job.

Synthetic image-only two-page fixture: `tests/fixtures/native_pdf_page_smoke.pdf`, SHA-256 `3f05b02ae02694ba4a58a04c667302a878bde097534ab0166d762d0256a72af5`. Both final pages and helper output were visually inspected. No user document or personal data is embedded.

Installed Poppler 25.03.0 `/usr/bin/pdftoppm` SHA-256: `f22d753dfb4c31c9f0198d608982dac5b06a3c5d9a08d7d9bf0c6004f08a1a56`. Synthetic English OCR used the existing pinned Tesseract 5.5.0 fixture. This establishes a working foundation, not Chinese OCR accuracy, whole-product acceptance or release readiness.

API operation count remains 2375. Backend catalog fingerprint is `0aee95e65c305dfff0860079bf56753d4b25b5c074c829afe006b323b090bef5`. No frontend source changed; the preceding template slices retain their own TypeScript and production-build receipts. Test wheel is not a Release.

## Next integration boundary

PDF source/page identity must pass through original Research source authority, original JobManager, broker admission, typed provider receipt, review and citation publication. Preserve existing IMAGE/V1 serialized bindings. Do not open generic SCAN_PDF_VISION based on this helper or treat raster output as original source identity.

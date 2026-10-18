# Original-registry OCR runtime foundation

2026-10-18. **Foundation only; Research OCR remains NOT_CONFIGURED for real dispatch.**

Current source inspection found no VISION processing node behind the existing
Research adapter contract. The old synthetic ReviewAdapterJobs guard explicitly
requires original runtime/job admission before real adapters may run. That guard,
Research routes, original source owners and review rules are unchanged.

This slice adds a typed OCR seam to the existing GenerationRuntime, ProviderRegistry
and ModelRegistry. Construction registers nothing and launches nothing. Only an
already host-registered local VISION model with OCR capability, shared persistent
provider/model/execution identities, exact local route admission and an explicitly
admitted language can reach a trusted provider. It does not change TEXT/AUDIO routing.

Requests bind a 4 MiB maximum image byte envelope, exact SHA-256, explicit PNG/JPEG
media type, language, route digest and caller-owned dispatch guard. This layer does
not decode or validate image pixels: a future actual provider must do that with
bounded dimensions, resources and cancellation. Caller/job ownership must validate
source ID/version/incarnation. PDF, page ranges, table/chart understanding, network
configuration, installation and user executable arguments are not offered.

Provider identity/admission, original global execution flags, caller authority and
cancellation are checked before and after the provider call and through the guard
passed to the provider. Changed or replaced providers and wrong receipts discard
output. Text is bounded to 256 KiB, UTF-8, nonempty and without NUL; receipt fields
are closed and pin input, route, language and output hash. Returned metadata states
review_required, automatic_canon=false and model_quality=NOT_RUN. A synchronous
trusted provider must honor its own timeout/polling contract; this foundation does
not claim to terminate an arbitrary hanging implementation.

## Verification

- r1: 81 targeted typed-runtime, original TEXT and PUBLIC-profile checks passed.
- Final r2: 152 passed, 36 PostgreSQL-marked cases deselected, zero skips. Includes
  original Research in-process File/TestClient scenarios and its unchanged rejection
  of CONTRACT_VERIFIED adapters lacking model admission; public closure and actual
  offline wheel/adversarial artifact tests also passed.
- OCR provider in these tests is explicitly synthetic and recognizes no pixels.
  No Tesseract/Ollama/model call or production registration occurred.
- Frontend source is unchanged from the previously checked/build-passed 2a6f079;
  TypeScript/Vite were not redundantly rerun for this Python-only foundation.
- No PostgreSQL, live browser, target-platform, real OCR quality or full release gate
  is claimed. The public wheel remains version 0.7.0, a test artifact, not V2 Release.
- The PUBLIC manifest adds only app/vision_ocr_runtime.py; private backend exclusion
  and all original negative tests are retained. Existing deprecation/schema warnings
  remain visible in the raw log.

## Required next integration

A real admitted provider and original JobManager preparation/dispatch/terminal
binding are still needed before Research can expose this. Do not flip its
MOCK_ONLY guard, manufacture a prepared receipt or count this node as working OCR.
Keep source-incarnation, actor, explicit review, cancellation, limits and restart
uncertainty in the original owners. No new queue or workflow engine is warranted.

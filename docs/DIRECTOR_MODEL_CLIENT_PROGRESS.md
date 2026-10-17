# Director versioned action client

Status: implemented client candidate; product workflow remains PARTIAL. No visible UI or production route activation is included.

The lazy factory reuses the original Creative transport's captured credentials and branch context. Construction performs no request. Explicit methods cover preview, dispatch, preparation, pending reads, human review, read-only uncertain-review reconciliation and cooperative cancellation. Strict response contracts bind project, scope, source snapshot, proposal, original Job and terminal evidence. Submitted review content is copied before awaiting; omitted visual target remains distinct from explicit null. No retries or fallback workflow are introduced.

The wire fixture is captured from the actual isolated File-backed router with a test provider response. It is not live-model or browser acceptance. The new capture adds completed status and the exact review submission in a separate fixture; prior captured evidence remains unchanged.

The first client test exposed an incorrect assumption that dispatch advances the proposal by one version. The original owner commits admission and reservation binding separately, advancing by two. The client was corrected to the actual owner contract; the failed receipt is retained and no backend behavior was changed to satisfy it.

Final focused regression: 136 tests across 10 files, including existing Graph Director and reviewed-DRAFT handoff integration. Forced TypeScript, production Vite build and UI token guard passed. The pre-existing large-chunk build warning remains. Receipts are adjacent `director-model-client-ui-r4` and `director-model-client-type-r2`; fixture provenance and reuse proof are in `delivery/v2-development/director-model-client-20261017`.

Backend application and packaging sources are unchanged from 17c6500. The four previous PUBLIC test packages were rehashed successfully; the 87 packaging checks are reused, not claimed as a fresh run. No new PostgreSQL, Windows, GPU, live-provider or browser acceptance has occurred. Independent review remains unavailable; primary serial review continues.

Next: bind the versioned client to the original Director review UI with stale-action and authority fences, exact uncertain submission retention, explicit Graph handoff and mounted/browser validation. Application routes remain disabled by default until the user-facing integration is verified.

The earlier eight-commit archive through 17c6500 was publicly uploaded and read back at archive commit de872b5. This new client slice was not part of that approved fixed payload. Main and PR development branches were not changed.

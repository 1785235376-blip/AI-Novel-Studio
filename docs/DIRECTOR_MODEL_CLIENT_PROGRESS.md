# Director versioned action client

Status: implemented client candidate; product workflow remains PARTIAL. No visible UI or production route activation is included.

The lazy factory reuses the original Creative transport's captured credentials and branch context. Construction performs no request. Explicit methods cover preview, dispatch, preparation, pending reads, human review, read-only uncertain-review reconciliation and cooperative cancellation. Strict response contracts bind project, scope, source snapshot, proposal, original Job and terminal evidence. Submitted review content is copied before awaiting; omitted visual target remains distinct from explicit null. No retries or fallback workflow are introduced.

The wire fixture is captured from the actual isolated File-backed router with a test provider response. It is not live-model or browser acceptance. The new capture adds completed status and the exact review submission in a separate fixture; prior captured evidence remains unchanged.

The first client test exposed an incorrect assumption that dispatch advances the proposal by one version. The original owner commits admission and reservation binding separately, advancing by two. The client was corrected to the actual owner contract; the failed receipt is retained and no backend behavior was changed to satisfy it.

Final focused regression: 136 tests across 10 files, including existing Graph Director and reviewed-DRAFT handoff integration. Forced TypeScript, production Vite build and UI token guard passed. The pre-existing large-chunk build warning remains. Receipts are adjacent `director-model-client-ui-r4` and `director-model-client-type-r2`; fixture provenance and reuse proof are in `delivery/v2-development/director-model-client-20261017`.

Backend application and packaging sources are unchanged from 17c6500. The four previous PUBLIC test packages were rehashed successfully; the 87 packaging checks are reused, not claimed as a fresh run. No new PostgreSQL, Windows, GPU, live-provider or browser acceptance has occurred. Independent review remains unavailable; primary serial review continues.

Next: bind the versioned client to the original Director review UI with stale-action and authority fences, exact uncertain submission retention, explicit Graph handoff and mounted/browser validation. Application routes remain disabled by default until the user-facing integration is verified.

The earlier eight-commit archive through 17c6500 was publicly uploaded and read back at archive commit de872b5. This new client slice was not part of that approved fixed payload. Main and PR development branches were not changed.

## Original Graph review authority binding

The original GraphDirectorProposalReview now passes the optional model factory through its existing read/mutate owners. Factory construction makes no network request. All ten model operations are explicitly classified; read-only reconciliation stays on the read owner despite its HTTP POST shape. Retained clients and late responses are fenced against project/client lifetime changes and mutation-context changes, including A→denied→A.

A new mounted boundary test reproduced the latter revival bug in the first wrapper implementation: retained pending reads and reviews resolved after permission was removed then restored. An independent generation counter now retires that earlier context. The RED receipt is retained. This is a UI admission fence, not a substitute for backend authorization. The earlier test run also recorded ten failures from an unsupported new test matcher; that matcher was replaced by separate count and argument assertions without changing old tests.

The final boundary scope passed 91 tests across six files, followed by forced TypeScript, production build and token checks (`director-model-authority-r3`). There is no visible layout change and no new product route activation in this slice. New tests validate parent-owner routing, denied writes, late receipts and retained-client retirement. The next step remains the visible versioned workflow and real-browser verification.

## Exact adopted-DRAFT reopening and Graph anchor

A new explicit read-only handoff checks the original adoption receipt, reads the original Creative export, validates its exact document ID/version/digest and source snapshot, then rechecks the adoption receipt. Caller guards run around every await; abort and object mutation cannot publish a retired or changed result. It never inserts, saves or executes Graph.

The original Graph review callback can now carry that expected snapshot. The console retains it as an immutable review anchor and still requires its ordinary explicit export verification before enabling insertion. A same-version substituted digest is rejected; a later exact read can recover. Existing non-model callbacks remain compatible.

The final combined scope passed 74 tests across six files plus forced TypeScript, production build and token checks (`director-model-adoption-pin-r1`). Earlier handoff r1 passed 28 tests but failed TypeScript because the existing CreativeDocument type requires actor_id while the genuine backend fixture carries created_by. The test now explicitly treats captured wire as unknown at that legacy boundary; it does not fabricate actor_id or alter captured payloads. Handoff code does not use that field. The corrected r2 passed tests and build; the old type discrepancy remains a separate compatibility concern.

Browser probe on this cloud environment: bundled Playwright Chromium is absent. The installed /usr/bin/chromium cannot start under the current sandbox because its local socket is denied. The supported elevated launch also failed in the environment wrapper before browser startup. No browser acceptance or visual baseline is claimed, and no user browser or machine was touched. Serial code and test work continues.

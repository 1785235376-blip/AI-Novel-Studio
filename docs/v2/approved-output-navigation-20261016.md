# Open approved original output

This bounded frontend slice adds an explicit action on an APPROVED original production job, including a reopened job. It checks the approved asset metadata version (not the private candidate version), ID, SHA-256 and media kind through the existing guarded asset read before selecting that asset in the existing asset workspace. Deleted or changed metadata does not substitute another result.

Existing dirty-navigation confirmation remains in use. Cancel retains the draft and performs no asset read. Explicit discard preserves the original selected production job if the subsequent read fails or mismatches. Late reads cannot overwrite a newer selection or a closed workspace. No new task, dispatch, review transition, entitlement, backend or lifecycle implementation is added.

The existing asset inspector can fetch media bytes for inline preview after navigation. This is not an automatic file-save/export: no download anchor is invoked by this slice. Existing preview/download transport remains unchanged and ID-addressed. This slice proves exact metadata validation at handoff; it does not introduce historical byte retrieval or claim independent digest verification by the inspector.

## Verification

- Focused mocked UI/geometry: `ApprovedOutputNavigation.test.tsx`, `StudioMediaRouteChoice.test.tsx`, `graphCanvasGeometry.test.ts`: 29 passed (11 new navigation cases).
- TypeScript and Vite production build: passed; existing large-chunk warning retained.
- UI token guard: passed (52 files).
- PUBLIC source closure: passed (487 files); this is packaging closure, not complete PUBLIC-mode product acceptance.
- `git diff --check`: passed.

During development, the new test initially needed to await asynchronous job-list loading and account for existing asset-detail metadata reads and inline-preview GETs. Those failed test iterations are not product acceptance evidence. Final assertions prohibit file-save clicks and execution/review writes while preserving existing preview behavior.

Full-suite, browser/visual, real providers, Windows/GPU/native runtime, CI and user-computer acceptance were not run. Existing product acceptance limits remain unchanged. No additional delivery-center, cross-module reference or task-center navigation slice was implemented. Work stops after this round as requested.

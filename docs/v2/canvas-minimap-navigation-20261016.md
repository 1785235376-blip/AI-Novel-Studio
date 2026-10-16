# Bounded GraphCanvas MiniMap navigation — 2026-10-16

## Delivery and scope

Baseline: `3d089295947e6878c1b9eb0957fac6ac4bf1c3aa`, on the existing local development branch. The containing Git commit identifies delivery. No push, hosted CI, merge, tag or release: CI cost remains unknown. Parent independent review follows this local commit.

Inspection found no existing MiniMap in GraphCanvas. This slice reuses `graphCanvasPresentation.ts` and its original display index; no second graph, camera store, API, schema, backend runtime file, resource budget or permission change. Saved camera and node positions already belonged to the original Graph definition/CAS owner and were not rebuilt. PUBLIC inventory remains unchanged because there is no new backend runtime file.

## User-visible flow

- Existing GraphCanvas mounts an optional overview below its measured interactive viewport. It shows every valid display-card bound, selected nodes in the existing accent token, and a current-viewport outline. Full map extent includes graph connection bounds and the current camera, including when panned away. It intentionally does not draw connection lines.
- Click to center the camera on a map point. Arrow keys move the camera by one quarter viewport; Shift moves a full viewport. Native button activation (Enter/Space) centers the graph's card bounds. Zoom remains unchanged. The existing coordinate clamp still applies, including at graph extremes.
- Each actual navigation publishes one original `onDefinitionChange(..., true)` history update. No-op boundary movement adds no record. Nodes, edges, author parameters and source pins retain their original references/values. Existing Save persists the camera; original undo/redo and CAS behavior remain authoritative.
- Keyboard events on the map do not move/delete selected graph nodes. Focus remains on the semantic button; original visible focus styles apply. The full node directory remains available for node selection. Selection rendering is informational, not a separate selection owner.
- Read-only and busy camera navigation stays disabled, matching existing pan/zoom and directory camera policy. The overview remains visible. Empty, hidden/unmeasured and invalid-camera layouts disable navigation. Active canvas gestures prevent navigation. Invalid/nonfinite display bounds are omitted from the projection, without changing source data.
- A toolbar toggle hides/restores the overview without changing graph state or history. Its visibility is transient UI state, not persisted presentation metadata.

## Verification

Exact commands, exit codes, UTC timestamps and source hashes are in `canvas-minimap-navigation-20261016.json`; raw local receipts/logs remain under `docs/delivery/v2-development/canvas-minimap-*`.

- PASS: 181 targeted tests across nine UI/geometry files, zero skipped. Includes CanvasOps, MiniMap/GraphCanvas, existing Director, independent/production graph editor and PUBLIC placeholder. Environment is jsdom and mocked transport, not browser acceptance.
- New tests cover full/extreme/offscreen bounds, transform round-trip, unknown/invalid/resize geometry, 1000 display-only objects, preserved node/edge/zoom/selection, history callback/focus, hide without mutation, read-only/busy/unmeasured/empty guards, composition and active gestures, owner replacement, clamps, and dirty author text → camera navigation → undo/redo → Save → reopen.
- PASS: five selected original File persistence/CAS/atomic-write tests and 30 PUBLIC build-profile contracts. No PostgreSQL or P0 test was run.
- PASS: `tsc -b`, Vite production build, 410-file unit discovery and Playwright inventory (no browser launch), shared 52-file token guard, explicit changed-surface token guard, PUBLIC source closure (487 files), and diff whitespace check. Existing large-bundle warning remains; this is not a runtime/performance claim.
- Initial narrower run: 74 tests passed before the final save/reopen integration test and graph-center refinement. Final evidence is the 181-test run, not that exploratory receipt. No failed test was removed or skipped.

Canonical IMAGE workspace reference and DS rules were inspected; only feature-local tokenized chrome and existing primitives changed. Browser runtime was previously BLOCKED and was not retried or worked around. No screenshot, visual regression pass, screen-reader/native IME, FPS or memory acceptance is claimed.

## Limits and continuation

This is bounded MiniMap navigation, not complete infinite canvas. Projection remains O(nodes + edges); two aggregate node paths avoid one SVG DOM element per node, but path work and the existing full accessible directory still scale with display data. The 1000-object check is pure geometry only, with no timing/FPS claim or executable DAG creation. Zoom 0.35–2.5, camera/node coordinate bounds and execution DAG budgets are unchanged; distant points can remain unreachable at some zooms under the existing camera clamp. No large-graph browser performance acceptance or benchmark was added.

Grouping/collapse/annotations, independently persistent presentation, full LOD, crash-proof unsaved recovery, cross-canvas operations and target-browser acceptance remain open. Continue after parent review with the next original-owner presentation slice; do not create a second graph/camera owner.

P0 lifecycle repair/reproduction remains platform-BLOCKED, excluded and untested; R3-GATE HOLD. Production Prompt Adoption writes remain disabled. Windows/GPU/real provider/complete RC remain LOCAL_REQUIRED. No user computer, saved environment, external model/API, security candidate, account change or paid service was used.

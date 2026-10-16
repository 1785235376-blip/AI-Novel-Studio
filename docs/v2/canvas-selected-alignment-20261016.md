# Selected GraphCanvas alignment — 2026-10-16

## Scope and owner audit

Baseline `e07b5b0799aab9a3cb252e2cbab0a9e7fcfd4590`; the containing local commit identifies delivery. Existing CanvasOps already offered whole-graph auto-layout preview/apply, and original Graph definitions already owned saved positions and viewport. GraphCanvas had no selected alignment/distribution or snap controls. This slice adds only selected-node alignment to the existing canvas, without a second store, schema, API or backend change. The MiniMap visibility toggle also now isolates keyboard events from graph movement/deletion.

## User flow and invariants

Select at least two nodes, then preview left alignment, horizontal-center alignment or top alignment. Select at least three for horizontal equal-spacing distribution. The actual cards, connection paths and MiniMap show the proposed geometry, while the original draft remains untouched. Cancel or Escape discards the preview. Explicit Apply publishes one original history update; existing undo/redo, Save and versioned reopen remain authoritative. No-op previews disable Apply. Distribution preserves extreme endpoints and each node's y coordinate; equal-width cards have equal horizontal gaps, which may overlap when the existing extent is too small. Alignment does not avoid overlaps.

Only selected positions change. Unselected node objects, node order, edges, camera, enabled flags, parameters and exact source pins are preserved. Left/top use the selection's minimum coordinates; horizontal-center uses the midpoint between its extreme x positions. All operations work in world coordinates independent of zoom. Nonfinite/out-of-bound selected geometry, missing IDs or insufficient selected counts return the unchanged definition. Existing ±100,000 coordinate, zoom and DAG budgets remain unchanged.

Preview validity is tied to original definition identity, owner key and selection; replacement, selection change, read-only/busy transition or starting a pointer gesture discards it. Preview and Apply are blocked during active gestures or read-only/busy state. Preview controls and MiniMap visibility keys cannot bubble into selected-node move/delete shortcuts. Existing other toolbar keyboard behavior is not broadly refactored.

## Verification

Exact commands, UTC timestamps, exit codes, receipt/log hashes and source hashes are in `canvas-selected-alignment-20261016.json`. Raw local receipts are retained under `docs/delivery/v2-development/canvas-alignment-*`.

- PASS: 194 tests in nine selected UI/geometry suites, zero skipped, jsdom/mock transport. Includes the original independent and production Graph editors, CanvasOps, Director source integration and PUBLIC placeholder. New tests cover geometry modes, unselected identity/source pins/edges/camera preservation, deterministic distribution, no-op and invalid inputs, preview/cancel/apply, stale selection/definition/owner, blocked transitions and keyboard isolation.
- PASS: mounted dirty text → selected alignment → one undo/redo → original Save with expected version → reopen. No preflight or task dispatch occurs.
- PASS: one existing nonsecurity File presentation positions/camera reopen and stale-version CAS test; 30 PUBLIC build-profile contracts. No PG or P0 tests run.
- PASS: tsc -b, Vite build, unit discovery (410 files; Playwright inventory only), existing 52-file token guard, explicit changed-UI token guard, PUBLIC 487-file source closure and whitespace diff check. Existing large-bundle warning remains.
- Initial focused run: 57 tests passed, followed by the broader final run. No failed tests were removed or skipped.

Canonical IMAGE reference, repository UI skill and design-system rules were inspected. Shared Button primitives and existing tokenized wrapping toolbar styles are reused; no CSS, shell or core primitive changes. Browser runtime remains BLOCKED/NOT_RUN, with no retry or workaround. No screenshot/desktop-width visual pass, screen-reader/native IME, FPS or memory acceptance is claimed.

## Boundaries and continuation

This is a bounded presentation slice, not full professional infinite canvas. Grid/snap, grouping/collapse/annotations, independent large display workspaces, full LOD, cross-canvas operations and crash-proof unsaved recovery remain open. Parent independent review precedes the next tracked slice.

P0 lifecycle repair/reproduction stays platform-BLOCKED and excluded; R3-GATE HOLD and production Prompt Adoption disabled. No backend/auth/security changes, paid API, provider/GPU, user computer, saved environment, push/hosted CI, merge, tag or release. CI cost remains unknown; Windows/GPU/real-provider/full RC remain LOCAL_REQUIRED.

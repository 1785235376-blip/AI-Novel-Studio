# Bounded display-only canvas culling — 2026-10-16

## Identity and scope

Local baseline `3698c3dbb6b6be18252f58e2bb525fba933436f3`, tree `fcb488ed5294768958dd0637fabdc253fedab54c`, on `work/dot-usability-handoff11-20261015`. The containing commit is this delivery's identity. No push, hosted CI, main change, merge, tag, release, paid API, provider/model execution, user computer or GPU use. Published PR identity is not changed by this local commit.

P0 security/lifecycle remains platform-BLOCKED and was completely excluded from reads, edits and tests in this slice. Production Prompt Adoption write remains disabled; R3-GATE HOLD remains. Browser runtime is previously BLOCKED: no browser workaround or screenshot claim. Windows/GPU/live-provider/full RC remain LOCAL_REQUIRED/NOT_RUN.

## Implemented behavior

- `graphCanvasPresentation.ts` derives a disposable geometry index from display-only node IDs/definition IDs/positions and typed connections. It does not own graph parameters, execution data, persistence, approval or permissions. Production GraphCanvas still receives the original complete controlled definition.
- Viewport dimensions are measured initially, by ResizeObserver, and by window resize. Cards intersecting the world-space viewport plus 160 screen-pixel overscan mount normally. Unknown/zero-size layout falls back to the complete render until a valid measurement is available. If ResizeObserver is unavailable, only initial/window-resize measurements remain; internal container-only resizing is not observed in that fallback.
- Selected nodes, focused cards/ports, current gesture participants and the controller's pending source/target connection endpoints remain mounted even offscreen. Culling never removes nodes, parameters, selected IDs or edges from the authoritative graph. Ctrl+A deliberately retains every selected card.
- Edge endpoint lookups use maps instead of scanning all nodes for every edge. Conservative cubic control-point bounds keep crossing/reversed curves even when both endpoint cards are outside. This may draw false positives, but does not discard a curve merely because its nodes are culled. Missing node/port behavior remains unchanged.
- Existing drag, cancel, multi-selection, marquee over the full graph, wheel anchor, zoom limits, pan, keyboard movement/delete, protected references and busy/readonly guards remain. Memoized directory options and accessible connection descriptions avoid recreating their React entries during camera-only changes.
- The toolbar's native node directory makes every node keyboard-selectable, including culled ones. Editable selection centers via the original controlled viewport/change callback and records normal history. Readonly selection remains nonmutating, preserving the original restriction on readonly camera mutation. Busy or active gestures do not accept directory changes. All chrome uses existing tokens; no protected shell/theme/primitives changes.
- The existing Graph editor supplies selected connection endpoint IDs from its own source/target port keys. No new connection state or legality authority is introduced.

## Scale evidence and limits

Reproduce from `frontend`: `node --expose-gc scripts/benchmark-graph-display.mjs` (exit 0). The [benchmark JSON](canvas-display-benchmark-20261016.json) records runtime, source hashes, measured samples and precise timing/heap observations. Synthetic DTOs deliberately have no schema, enabled state, version, parameters or execution payload. No normal user data is mutated and no ≥1000-node DAG is submitted or executed.

- 1,000 display cards + 975 display connections: home viewport projects 9 cards + 9 paths. 1,000 pan/zoom samples: median 0.0129 ms, p95 0.0610 ms, max 2.0823 ms. Index build 3.8050 ms. Maximum sampled retained visible cards 100, paths 90.
- 10,000 display cards + 9,750 display connections: home viewport projects 9 cards + 9 paths. Median 0.1198 ms, p95 0.2332 ms, max 3.6992 ms; index build 11.3878 ms.
- Five explicit-GC Node retained-index heap observations: 432,504–452,176 bytes at 1,000 cards; 4,484,288–4,507,064 bytes at 10,000. These are noisy single-process runtime observations, not an application memory budget or a browser-memory acceptance result.

These timings measure the pure geometry projection only, excluding React reconciliation, directory options, DOM, native select, layout, paint and GPU. They are **not browser FPS or real user interaction latency**. Native directory options and screen-reader connection descriptions still scale with the full graph; rendering all selected/retained cards or an unmeasured viewport can still mount all cards. Projection remains O(nodes + edges), not a spatial tree. LOD, full virtualization, view-state persistence, MiniMap, grouping, media loading and an independently large production workspace remain open. The current backend 16/24/40 budgets, schemas and coordinate/zoom bounds are unchanged. This is a bounded culling slice, not completion of the professional infinite canvas.

## Verification

Exact commands, exit codes, source hashes and local log hashes are in [the evidence summary](canvas-display-culling-20261016.json). Detailed local receipts are preserved under `docs/delivery/v2-development/canvas-culling-*`; historical untracked receipts were not altered or removed.

- Final related Vitest suite: 272 tests across 13 files, all pass, no skips. Includes new six pure-presentation tests and eight measured-viewport component tests, plus existing canvas geometry/interactions, canvasops, Director author/save/reopen, Graph integration, original clients, Creative authoring and PUBLIC placeholder tests. jsdom/mock transport, not real-browser acceptance.
- Initial exploratory related selection: 157 tests across seven actually discovered files, all pass; the final command uses the correct mounted Graph integration filenames. Counts are overlapping, not additive.
- TypeScript `--noEmit`, Vite production build, existing token guard (52 guarded files), focused changed-canvas raw-color guard (3 files): exit 0. Existing Vite >500 kB chunk warning remains.
- PUBLIC packaging contracts: 30 passed; source closure: 487 files, exit 0. This is offline packaging-source verification, not actual Windows/Docker/installer/wheel/sdist installation acceptance.
- Whitespace check: exit 0. No backend File/PG execution test was needed or run for this display-only change; no permission/security acceptance is inferred.

## Next queue

Independent review first. Then inspect original presentation-state owner contracts before a bounded persistence/conflict slice, followed by actual grouping/collapse/layout and MiniMap integration. Later real-browser viewport/keyboard/Chinese IME and display-memory measurements must validate the mounted application when permitted. Continue the frozen A/B/U/Graph/Console/FS/CORE ledger without raising execution budgets or claiming the security release gate is closed.

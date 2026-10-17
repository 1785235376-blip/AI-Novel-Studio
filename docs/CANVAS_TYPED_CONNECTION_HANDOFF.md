# Typed canvas connection handoff

Status: primary gates and scoped independent review passed; evidence indexed. This is a bounded authoring slice, not completion of the professional canvas or Director roadmap.

Base: `e18ae7bff060c8eeddc5bd9d8f8673a14507a94a` on `work/dot-canvas-connect-20261017`.

## Delivered interaction

- Drag from a rendered input or output port to preview a temporary wire. Compatible endpoints use existing selection tokens; invalid hovered endpoints show the original validator's explanation.
- A valid drop stages the existing pending source/target pair. It does **not** create an edge, record history, save, execute a node, dispatch a model, or run the graph.
- The user must still click the original **连接所选端口** command. The original controller `connect()` owns edge creation, capacity enforcement and history. Save remains separately explicit.
- Invalid or canceled drags preserve prior pending endpoints. Plain pointer clicks and keyboard activation retain single-port selection; a captured unmoved release selects exactly once.
- Both drag directions normalize to output → input. A direction adapter rejects same-direction endpoints; all graph type/schema/topology legality remains `graphDraft.connectionIssue`.

## Ownership and lifecycle

`GraphCanvas.tsx` owns transient pointer state only. The view forwards original-validator advice and guarded controller selection callbacks. `useStudioGraphEditorController.ts` retains all draft authority.

An opaque transition token tracks actual owner/client/base/draft/catalog/active/permission/editability changes and rejects stale callbacks, including A → B → A transitions. Unrelated selection/status renders do not invalidate it. Staging and single-port selection also check the latest synchronous current/busy predicates and draft/base refs.

The canvas uses existing `graphPortPosition`, `graphScreenToWorld` and `graphEdgePath` helpers. Pointer capture does not determine the candidate endpoint: movement and release hit-test the physical coordinates using `document.elementFromPoint`, then require an enabled real port inside the same viewport. Release rechecks its own coordinates rather than trusting the last hover. Collapsed frames and culled nodes are not synthetic ports.

Cancellation covers pointer cancel/lost capture, Escape in capture phase, window blur, scroll, window/viewport resize, ownership/schema/draft/editability transitions, and unmount. Capture cleanup retains the actual viewport element even after React detaches its ref. Late physical clicks are suppressed without suppressing keyboard activation or the next independent pointer click.

## Exact source scope

Modified:
- `frontend/src/creative/GraphCanvas.tsx`
- `frontend/src/creative/graphCanvas.css`
- `frontend/src/creative/studioGraphEditorView.tsx`
- `frontend/src/creative/useStudioGraphEditorController.ts`

Added:
- `frontend/src/creative/GraphCanvas.connection.additive.test.tsx` — 29 tests
- `frontend/src/creative/StudioGraphConnection.additive.test.tsx` — 15 tests

Original geometry helpers, validator, explicit Connect owner, backend/runtime sources, protected shell/primitives/tokens and existing tests are unchanged. Styles consume existing selection/accent/error tokens.

## Frontend evidence

Canonical command launcher: `docs/delivery/v2-development/canvas-connect-frontend/run-frontend-r2.sh`, stages `ui`, `type`, `build`, `token`, run serially.

It uses the existing `scripts/run_v2_checks.py`, the dedicated clean reconciliation Python, the installed explicit Node path, original Vitest config, one worker, no cache and default timeouts. Each original-runner receipt records full pre/post source maps and log hashes.

| Gate | Result | Receipt |
| --- | --- | --- |
| UI, 26 modules | PASS: 446 tests, including 44 new tests | `canvas-connect-ui-r2.json` |
| TypeScript | PASS: `tsc -b --force` | `canvas-connect-type-r2.json` |
| Vite production build | PASS; large-chunk warning retained | `canvas-connect-build-r2.json` |
| Token guard | PASS: 52 files | `canvas-connect-token-r2.json` |

All receipt paths are under `docs/delivery/v2-development/`. All four r2 receipts have 2,585-file source maps, unchanged pre/post snapshots and verified log hashes.

Coverage includes forward/reverse staging, original type/duplicate/single-input/cycle explanations, direction mismatch, exact physical hit/drop behavior, cancellation/click/keyboard handling, authority ABA/live locks, same-ID reload/schema transition, collapse/culling, inverse-zoom wire geometry and camera arbitration. Actual view integration verifies drop → pending fields → original explicit Connect. Hook integration covers original undo/redo and mocked-client save/reopen.

### Retained first attempt and narrow corrections

`canvas-connect-ui-r1.json` passed the same 446 tests. `canvas-connect-type-r1.json` failed with two compile errors and is retained with its original log:

1. TypeScript did not infer the ref assignment inside `startGesture`; the function now returns the created gesture, used by `startConnection`. Existing callers and behavior are preserved, without a cast.
2. The new capacity test assigned zero to the catalog's literal `40` edge limit. It now preserves the real limit and creates forty distinct fixture edges, each accepted by the original validator, before asserting explicit Connect cannot add another edge/history record. The fixture catalog exposes forty typed single-connection inputs; it is a test fixture, not a production catalog change.

Execution stopped at the first failure. The reviewer inspected both narrow fixes, then all four gates were rerun on frozen sources under distinct r2 labels. No old test or validator was changed to make the gates pass.

## File baseline and independent review

Primary protected File baseline passed: **339 tests passed, 20 PostgreSQL-only tests deselected, no skips**, under `canvas-connect-file-regression-r1.json`. The unchanged suites were `tests/test_v2_creative_graph_persistence.py`, `tests/test_v2_creative_graph_persistence_additive.py`, `tests/test_v2_creative_graph_contracts.py`, and `tests/test_v2_graph_schema_version_gate.py`. `canvas-connect-file-origin-r1.json` records the clean interpreter/import-origin proof. Both original-runner receipts bind unchanged 2,585-file snapshots.

Scoped independent verification passed: **8 UI modules / 211 tests**, including all 44 new tests; the same protected File baseline passed **339 tests, 20 PostgreSQL-only tests deselected, no skips**. Independent origin/UI/File receipts are `canvas-connect-independent-{origin,ui,file}-r1.json`. The independent launcher and normal startup evidence are under `canvas-connect-independent/`. Static review covered the exact six-file change and both narrow r2 corrections.

All nine final primary/independent receipts have identical 2,585-file source maps matching current sources, unchanged pre/post snapshots, passing exit codes and verified log hashes. Retained r1 UI/TypeScript attempts use the earlier source snapshot and are historical evidence, not final-source proofs. See `canvas-connect-evidence-index.json` for per-receipt validation and artifact hashes.

File tests are the protected original persistence/API baseline and must be reported separately from pointer interaction coverage. They do not constitute real-browser end-to-end drag/save proof. Independent checks repeat scoped coverage; their counts must not be added to the primary totals.

## Explicit limitations

- Real-browser pointer capture, screenshots, visual regression and measured browser geometry: **NOT RUN**. jsdom geometry and hit-test fixtures are synthetic.
- Browser availability is not inferred from this result.
- No automatic edge creation, model dispatch, provider execution, export, or backend capability was introduced.
- This handoff does not claim the professional canvas/Director roadmap complete.
- No prior indexed ledger or delivery document is revised by this slice. Full collection inventory refresh is separate.

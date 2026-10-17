# Positioned canvas insertion handoff

Status: primary verification and scoped independent review passed; final evidence reconciled. This is a bounded authoring slice, not completion of the professional canvas or Director roadmap.

Base: `e1e66cedeb7a140b6894850bc21a1e5ac7e06c16` on `work/dot-canvas-insert-20261017`.

## Delivered interaction

- A context-menu action on blank canvas, or Shift+F10 / ContextMenu on the focused viewport, captures a bounded world coordinate and focuses the existing searchable node palette.
- Search and selection do not create a node. The user must click the existing palette Add command. Required Director/Storyboard documents, assets, shot receipts and timelines still use the original source read/selection controls.
- Screen coordinates use the existing viewport-relative `graphScreenToWorld` helper and `clampGraphPosition`. Nonfinite geometry is rejected. Keyboard insertion uses the current viewport center.
- The original controller accepts an optional positioned request; its original constructors, source validation, schema restrictions, budgets and `change()` authority remain in place. No-argument Add retains the existing grid fallback.
- Positioned insertion explicitly refuses the legacy v1 `text_generate` implicit upgrade, with a visible explanation. The original no-argument Add path is unchanged.
- A successful positioned insertion records one draft history change and consumes its request once. Save remains explicit. The existing local recovery/autosave behavior is unchanged; opening/searching the palette creates no draft change or save request.

## Authority, gestures and focus

Point intent and Add authorization are separate. The point survives deliberate kind/source choices, but each Add callback is fenced to its current source-selection render. Stale source/kind callbacks, including A → B → A, are rejected. The point authority changes on owner/client/base/draft/catalog/permission/editability/lock transitions, including timeline-form dirty state. Callbacks also recheck live current/busy predicates and draft/base references.

Starting any captured canvas gesture synchronously invalidates pending insertion. Opening insertion during a gesture or alignment preview is refused. Blank viewport/world targeting leaves node, port, note, group, minimap and other controls alone. Existing connection capture and endpoint staging remain owned by their original handlers.

An expired point stays visible and disables positioned Add until Cancel or a fresh point; it never silently becomes grid placement. Escape ignores IME composition and keyCode 229. Cancellation returns focus when the same usable viewport remains. A monotonic focus-owner token prevents focus restoration after owner/record/permission ABA, while allowing restoration after an ordinary same-owner draft edit.

## Exact source scope

Modified runtime files:
- `frontend/src/creative/GraphCanvas.tsx`
- `frontend/src/creative/useStudioGraphEditorController.ts`
- `frontend/src/creative/studioGraphEditorView.tsx`
- `frontend/src/canvasops/CanvasOpsRail.tsx`
- `frontend/src/canvasops/NodePalettePanel.tsx`
- `frontend/src/canvasops/canvasOpsTypes.ts`

New additive tests:
- `frontend/src/creative/GraphCanvas.insertion.additive.test.tsx` — 12 tests
- `frontend/src/creative/StudioGraphInsertion.additive.test.tsx` — 20 tests
- `frontend/src/creative/StudioGraphInsertion.palette.additive.test.tsx` — 4 tests

No backend, original-test, CSS, token, primitive, shell, catalog, geometry-helper or validator changes. No second command registry, source picker, node engine or broad context menu was introduced.

## Final primary evidence

All evidence below is under `docs/delivery/v2-development/`.

| Gate | Result | Receipt |
| --- | --- | --- |
| UI, 29 modules | PASS: 482 tests; 36 new plus original 446 | `canvas-insert-ui-r3.json` |
| Forced TypeScript | PASS: `tsc -b --force` | `canvas-insert-type-r3.json` |
| Vite production build | PASS; large-chunk warning retained | `canvas-insert-build-r3.json` |
| UI token guard | PASS: 52 files | `canvas-insert-token-r3.json` |
| Clean File import-origin proof | PASS | `canvas-insert-file-origin-r1.json` |
| Protected File baseline | PASS: 339 tests; 20 PostgreSQL-only tests deselected | `canvas-insert-file-regression-r1.json` |

Canonical frontend launcher: `canvas-insert-frontend/run-frontend-r3.sh`. It uses the unchanged `scripts/run_v2_checks.py`, the dedicated clean `ci-reconciliation-python-r1` interpreter, installed explicit Node, the original Vitest config, one worker, no cache, default timeouts and a clean outer environment. Stages ran serially.

All six final primary receipts have identical 2,588-file source maps, match current sources, retain unchanged pre/post snapshots and have verified log hashes. The primary audit is `canvas-insert-frontend/final-primary-source-map-audit.json`.

New UI coverage includes inverse pan/zoom coordinates, bounds/nonfinite geometry, keyboard and IME, target exclusions, capture coexistence, focus ownership/ABA, explicit Add and no automatic save/run, source/kind ABA, exact Director/Storyboard/asset pins, provider defaults, schema/budget guards, dirty author content, timeline/execution locks, UNKNOWN save state, one-step undo/redo and mocked-client explicit save/reopen. The File tests are the protected original persistence/API baseline and are separate from interaction coverage.

## Retained failures and narrow corrections

- `canvas-insert-ui-r1.json`: FAIL, 480 passed / 2 failed. Both failures were new fixture omissions: the controller fixture lacked `client.asset` for the existing selected-asset preview effect; the canvas fixture lacked `onPortSelect`, so the original component correctly rendered a noninteractive port span without `data-graph-port`. This was not viewport culling. Only those two fixture dependencies were added, with no assertion or runtime changes.
- The first r2 launcher exited 127 before the runner or product execution: an overly broad label substitution accidentally changed the approved interpreter suffix to nonexistent `ci-reconciliation-python-r2`. No runner receipt was produced. The failed script and `r2-launch-failure.txt` remain in `canvas-insert-frontend/`. The launcher-only correction restores the approved r1 interpreter.
- `canvas-insert-ui-r2.json`: PASS, 482 tests. `canvas-insert-type-r2.json`: FAIL because the new budget fixture assigned a dynamic number to the catalog's literal 16-node limit. The fixture now preserves the original 16-node catalog and creates sixteen valid, uniquely identified text-input nodes before the unchanged budget assertions.
- Each failure stopped the serial sequence. The independent reviewer checked each narrow correction before a fresh full run. R3 reran all UI/type/build/token gates. Earlier receipts remain historical evidence rather than final-source proof.

## Independent verification

Independent origin, UI and File verification passed under `canvas-insert-review-{origin,ui,file}-r1.json`. Scoped UI coverage passed **6 suites / 105 tests**, including all **36 new tests**; the repeated File baseline passed **339 tests, 20 PostgreSQL-only tests deselected**. These counts are separate and must not be added to primary totals.

`canvas-insert-review-audit.json` records the independent receipt hashes, log-hash verification, unchanged existing-test diff and source reconciliation. All **nine** final primary/independent receipts carry identical **2,588-file** before/after maps matching current sources. The owned `canvas-insert-evidence-index.json` indexes final and retained historical receipts and artifact hashes. The reviewer performed static inspection and checked every narrow fixture/launcher correction; no runtime correction was needed after the initial implementation freeze.

## Explicit limitations

- Real-browser screenshots, visual regression, pointer capture, accessibility and measured browser geometry: **NOT RUN**. jsdom geometry is synthetic.
- No real provider/model/GPU execution, automatic graph run, export, schema migration or production deployment was exercised or introduced.
- PostgreSQL-only cases were excluded from the File baseline; this is not a PostgreSQL verification claim.
- Build chunk-size warnings remain.
- The slice does not complete the professional canvas or Director roadmap.

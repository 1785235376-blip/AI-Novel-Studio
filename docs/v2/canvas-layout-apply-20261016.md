# Original-owner canvas layout apply — 2026-10-16

## Identity and existing ownership

Baseline: `a5b23eaeca7bc33f98f5d1426a6e37c1d5ecf204`, branch `work/dot-usability-handoff11-20261015`. The containing commit is the delivery identity. No push/hosted CI (cost unknown), main edit, merge, tag, release, user computer, GPU or provider execution.

Inspection corrected the previous broad persistence gap: Graph `definition.viewport` and `nodes[].position` **already persist** via `useStudioGraphEditorController.save/open/accept` and `app/creative/graph.py`. The original service stores complete versioned definitions, includes presentation in `definition_digest`, excludes positions/camera from `execution_digest`, and retains expected-version CAS. No separate graph store or new persistence API is needed for these fields. A fresh service instance reads the saved definition by graph ID; the UI restores it after unmount/remount. This does not mean unsaved edits survive process loss.

Other inspected owners are deliberately unchanged: `studioWorkspacePreferences.ts` / `app/creative/workspace_models.py` store project intent/preset hints; `studioWorkspaceResume.ts` stores only a local-author navigation hint including graph ID, with original-owner reread; `app/experimental/workspace_interaction.py` stores actor-scoped keyboard/display preferences; `app/experimental/ux.py` stores workspace resume/search layout. None is an existing independent graph camera/group store. This slice does not expand their contracts or claim new scope/security acceptance.

## Concrete product closure

Previously CanvasOpsRail computed deterministic auto-layout but only showed a preview because it lacked an apply callback. It now offers **应用自动布局到草稿**. The optional callback preserves preview-only consumers and delegates to the original controller; the controller derives positions from the **live draft**, never a retained preview/base snapshot. Original `change()` owns undo/redo and binding guards. No write occurs until the user selects the existing graph Save.

- Preview and application use catalog node heights, preventing tall-port cards from overlapping within a layer.
- Only positions change; dirty author text, document/asset version/digest pins, enabled states, node order, connections, schema, title and viewport remain intact.
- Apply creates one original undo step. Empty/already-laid-out/readonly/blocked or missing-callback controls are disabled. The handler also observes original synchronous busy/current/editable fences.
- Graph save/reopen remains through the original owner. A 409 conflict, transport status 0 or status 500 retains the layout and camera draft, blocks mutation and offers original explicit checked server adoption. There is no overwrite, automatic retry, new UNKNOWN recovery rule or second storage path.
- Existing navigation guards prevent switching away from dirty layouts without consent. Two saved graphs restore their distinct cameras by ID. Source-bound Director nodes can be laid out and saved without repinning or dispatching work.

No Graph schema, 16/24-node/40-edge execution budget, position/zoom limit, backend runtime, permissions, lifecycle or PUBLIC runtime manifest changed. The helper operates on bounded authoring graphs; it is not a large-display automatic-layout performance claim. Group/collapse/annotation state is still session-local and not rendered as a persistent grouped canvas.

## Verification and qualifications

Exact commands, exit codes, source hashes and local receipt/log hashes: [evidence JSON](canvas-layout-apply-20261016.json). All commands run with the existing `../studio-overnight/.venv/bin/python scripts/run_v2_checks.py` isolation runner; no install was performed.

- Final selected frontend suite: **280 passed, 13 files, no skips**. New coverage includes explicit-only apply; readonly/no-op/preview-only guards; tall-card geometry; exact pins; dirty-text preservation; undo/redo; save/reopen camera; distinct graph navigation; 409/0/500 retained drafts and explicit reconciliation. This is jsdom/mock transport, not browser acceptance.
- Original File owner: **5 selected tests passed**, including new camera/position durable roundtrip, unchanged execution digest, changed definition digest, real stale-CAS rejection, no new collection; existing empty reopen, idempotency, concurrent CAS and failed atomic-write tests. Fresh service instance, not OS process restart. Only explicit nonsecurity File tests ran; PG/lifecycle tests were excluded.
- PUBLIC packaging contracts: **30 passed**. Source closure remains **487 files**. This is offline source packaging verification, not Windows/Docker/installer/wheel/sdist installation acceptance.
- TypeScript `--noEmit`, Vite production build, token guard (52 guarded files), focused two-file raw-color check, discovery checker and whitespace check: exit 0. Vite's existing >500 kB chunk warning persists. Discovery lists 410 unit files and the declared Playwright cases without running a browser.
- Two exploratory UI runs initially failed only the new tests: incorrect accessible label, then using the node directory (which explicitly recenters the camera) instead of card selection. Tests were corrected to use the actual card-selection control; no runtime camera behavior was changed to satisfy them. Receipts remain available; counts are overlapping, not additive.

P0 repair/reproduction remains platform-BLOCKED and untouched; R3-GATE HOLD and production Prompt Adoption disabled persist. Browser runtime remains previously BLOCKED/NOT_RUN, with no workaround or screenshot. Full native keyboard/Chinese IME/browser FPS/memory and Windows/GPU/provider/end-to-end RC remain LOCAL_REQUIRED/NOT_RUN.

## Next bounded queue

Independent parent review before the next edit slice. Continue real grouping/collapse/annotation presentation contracts or MiniMap navigation without duplicating the existing Graph persistence owner. Independently large display workspace, crash/offline drafts and full LOD remain open; follow frozen A/B/U/Graph/Console/FS/CORE dependencies.

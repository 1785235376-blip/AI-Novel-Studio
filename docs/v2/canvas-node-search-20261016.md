# Bounded graph-instance search — 2026-10-16

Baseline: `9400d21cca89d53ab64b02ed457c20aa105540c6`. Local-only continuation; containing commit identifies delivery.

## Audit and mounted result

`NodePalettePanel` already searches original catalog types and explicitly invokes the controller for creation. `AppShell` already owns the global module/utility command palette, with no graph-instance registration seam. Neither is duplicated or modified. This slice replaces the existing GraphCanvas flat instance selector with an inline, collapsible instance directory, not another global command palette or creation owner.

The mounted `GraphNodeNavigator` filters original instances by displayed label, definition type and ID (case-insensitive, whitespace-separated terms). Only 20 matching options mount per page; total/match/visible counts remain explicit. Arrow and Page keys choose a candidate; Enter or a result click explicitly selects and centers through the original GraphCanvas callback and controller history. Filtering, paging and dismissal never select, save, preflight or dispatch. IME/composition events are ignored for commands; Escape closes without clearing graph selection and returns focus to the trigger. Explicit close and confirmation also return focus. Owner changes reset query/open state. Read-only permits selection but keeps the existing camera-write restriction; busy/active gesture blocks navigation. Original selection retention reveals a selected folded-group member.

Original undo/save/reopen, dirty author text, exact reference pins, camera/coordinate/zoom limits, permission rules and execution DAG budgets remain intact. No backend, schema, new node kind, request, second store or protected AppShell change.

## Verification and honest benchmark

- 314 tests in 10 selected mocked UI/controller/transport/geometry files pass on final unchanged sources.
- One original nonsecurity File camera/CAS test and 30 PUBLIC contract tests pass.
- TypeScript project build, Vite build, test discovery, UI token guard, scoped new-file color guard, diff check and 487-file PUBLIC source closure pass. Existing bundle-size warning remains.
- The mounted 1200-display-instance fixture asserts exactly 20 search options, keyboard paging, multi-field filtering, composition safety, no mutation while filtering, explicit selection and original camera callback. Final run took 704 ms for the entire jsdom test including render/assertions, not search latency, browser FPS, memory or device performance. No execution limit was increased.
- Real controller integration edits dirty author text, searches/centers a pinned asset node, undoes/redoes, explicitly saves, unmounts/reopens and checks text/pins/camera with no preflight/run.
- Initial test-only failures: an expected camera position assumed the wrong existing card width; a pin fixture inferred `kind` as unrestricted string. Both corrected. Initial failed receipts retained. r2 UI pass overlapped a type-only fixture edit, so r3 is final unchanged-source receipt.

Exact commands, timestamps, source hashes and receipt/log hashes are in `canvas-node-search-20261016.json`. Raw receipts remain under `docs/delivery/v2-development/canvas-search-*`.

## Remaining boundaries

Browser/visual screenshots, native IME, assistive technology, actual layout/hit-testing, browser performance, Windows/GPU/provider and full RC were NOT_RUN; no workaround or user-computer access attempted. This is bounded instance navigation, not completed global graph commands/context menus, node creation search (already exists), nested subcanvases, durable unsaved recovery or full large-display acceptance. P0 remains BLOCKED and R3-GATE HOLD; production Prompt Adoption writes stay disabled. No push or hosted CI because cost remains unknown. Independent parent review required before the next tracked slice.

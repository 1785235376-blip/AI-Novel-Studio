# Same-graph selection copy preview — 2026-10-16

Baseline: `f27d6ebf028879badf444c81d789d759c2943433`. The containing local commit identifies this delivery. Frozen P1 large-space canvas increment; cross-canvas copy remains open.

## Audit and delivered scope

GraphCanvas, graphDraft, original Graph editor/controller and canvasops had no selection-copy command; existing duplicate operations belong to Timeline clips. Reused original editor change/history/save/CAS and shared Button/section UI. No parallel graph store, schema, backend owner, queue, execution type or budget change.

Explicit preview captures selected nodes and internal edges in memory, checks original node/edge/media-generator/definition-byte limits atomically, allocates fresh IDs, remaps internal endpoints and applies a uniform bounded 32-unit offset (reverse or clamp at the existing coordinate boundary). Original nodes, parameters and exact source/version/digest pins are deep-preserved. Existing source validation remains authoritative on save; this operation does not refresh, resolve, authorize or rebind references. External edges are excluded with an exact count and missing-input warning. Visual groups and execution receipts are not duplicated.

Paste is available only for the same owner identity/client/graph/selection epoch/catalog/exact draft, while editable and active. Draft changes, navigation, denial, owner replacement and unmount invalidate the preview. Busy and synchronous parent activity fences are rechecked before application. A paste is one original history step; undo/redo and save/reopen use the same owner. No OS clipboard, remote clipboard, persistent session buffer or cross-graph/project transport. No models, generation, preflight or run dispatched.

## Verification

- 226 targeted mocked UI/controller/geometry/contract tests PASS. Includes mounted preview/cancel/edit invalidation/paste/one undo/redo/save/reopen, owner/client/denied/read-only/dirty/inactive invalidation and synchronous busy fence; pure topology/remapping/pin preservation/coordinate and atomic limit checks.
- Two original nonsecurity File persistence/CAS tests and 30 PUBLIC contracts PASS. New File test saves copied topology, reopens, rejects stale CAS and restores the original graph; it does not claim browser-to-backend integration.
- TypeScript, Vite, discovery, original token guard, scoped no-raw-color check, diff check and 487-file PUBLIC closure PASS. Existing Vite chunk warning retained.
- Initial pure-test fixture mistakenly passed the catalog factory instead of its result; tests and typecheck caught it. Corrected without weakening assertions; failed receipts retained. Final r2 checks follow the inactive guard and are the delivery evidence.
- Receipt paths, exact commands, times, exit codes and hashes: `canvas-selection-copy-20261016.json`. Raw isolated receipts/logs retained under the existing delivery directory.

Browser/visual/native keyboard/IME/assistive technology/performance, PostgreSQL/P0/security, Windows/GPU/provider/user-computer/full RC NOT_RUN. Canonical image-workspace reference inspected; no protected shell/token changes. P0 remains BLOCKED, R3-GATE HOLD, production Prompt Adoption writes disabled. No push or hosted CI because cost is unknown.

## Handoff

Independent parent review before further tracked edits. Cross-canvas copy requires explicit current-owner and source-validation design; it is not delivered here. Nested subgraphs, durable unsaved recovery and full large-display acceptance remain open. Preserve historical evidence and all environment/cost/denial boundaries.

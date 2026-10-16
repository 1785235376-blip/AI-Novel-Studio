# Bounded graph annotation — 2026-10-16

Baseline: `a132035c79d1c9182299f7c4a71a06a7bfd2eef3`; the containing commit identifies delivery. This is a graph-level author note, not grouping, nested subgraphs, node comments or full infinite-canvas acceptance.

## Audit and implementation

The existing Graph definition persists viewport and positions, but had no group/comment field. Its original reader compares parsed definitions and canonical digests exactly; introducing a serialized default would break historical rows. `GraphPresentation.comment` is therefore optional, strict plain text (maximum 2000 Unicode code points), omitted entirely when absent/null. Existing schemas 1–5 remain valid; unknown presentation keys are rejected. Request null normalizes to absence; canonical responses omit the field, so the strict frontend rejects a noncanonical null response. Empty/whitespace text is preserved until explicit removal. The existing execution projection omits all presentation metadata, and execution node kinds, limits, authorization, source guards, preflight/Review/UNKNOWN machinery are unchanged. No second store, API, queue or execution node was added.

The mounted GraphCanvas “画布说明” textarea updates the original draft directly. Original undo/redo, dirty navigation warnings, explicit Save, version/CAS and reopening own the lifecycle. “移除画布说明” removes only that optional field; all nodes, exact parameters/pins, camera and edges remain unchanged. Read-only/busy/active-gesture state blocks edits. Keyboard events stay in the editor; text is not rendered as HTML, interpreted or supplied to models. Frontend transport validates and retains the optional field on reads/writes; legacy definitions remain unchanged. The UI uses shared Button and existing tokens without protected-shell changes.

## Verification

Exact commands, exit codes, times, source/log hashes: [measured evidence](canvas-annotation-20261016.json).

- 268 selected mocked UI/transport and pure geometry tests across 10 files pass. Coverage includes annotation edit/remove, original undo/redo/save/reopen, transport schemas 1–5, owner replacement, readonly/busy guards, 409/UNKNOWN/500 draft retention and existing Director/pin/layout/culling/grid flows.
- 11 pure backend contract tests pass: legacy canonical values and nested create/save serialization for schemas 1–5, strict bounds/types/unknown keys, unchanged execution digest and original DAG validation/budgets.
- 4 original nonsecurity File-owner tests pass: annotation reopen/removal/CAS, geometry reopen, empty/disconnected graphs and create idempotency/version conflict. The annotation test reopens with a fresh original service; removing it restores the exact original definition and digest. No alternative persistence collection appears.
- 30 PUBLIC contracts, tsc -b, Vite, discovery, token guard plus scoped raw-color scan, 487-file PUBLIC source closure and diff check pass. Vite retains its existing large-chunk warning; discovery is not browser execution.

Independent review identified the initial UTF-16/code-point boundary mismatch before delivery. Annotation-only input/transport bounds now agree with the backend and are tested with 2000 supplementary characters; unrelated text contracts are unchanged. Over-limit edits are rejected with visible feedback and preserve the full existing text, including mixed-character suffixes. An annotation-only dirty-navigation regression was added. No executed tests in this slice failed or were skipped. Earlier narrow UI/File receipts are retained locally alongside final receipts. Browser runtime remains previously BLOCKED; screenshots, native IME, visual/accessibility/performance acceptance, Windows/GPU/providers and full RC are NOT_RUN. PG/P0/security are excluded; P0 remains BLOCKED, R3-GATE HOLD and Prompt Adoption writes disabled. No push or hosted CI was triggered because cost remains unknown.

## Remaining work

Persistent named groups, group selection/movement/collapse, nested subgraphs and spatial/per-node annotations remain MISSING. Durable grid preferences, unsaved crash recovery, large independent display workspaces and full LOD/browser measurements remain open. Next bounded candidate: named visual groups using this original-owner optional presentation seam with strict membership validation, explicit group selection/movement and deletion that never implicitly deletes execution nodes. Coordinate with parent review before further tracked edits.

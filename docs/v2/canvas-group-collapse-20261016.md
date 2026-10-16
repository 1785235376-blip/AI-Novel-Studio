# Session-only visual group collapse — 2026-10-16

Baseline `0fb3548b96ebe7cad39f7d746c6f335b0d6b60fb`; the containing commit identifies local delivery. This is an explicit bounded view operation over original persisted groups, not a new execution graph or persisted collapse schema.

## Design audit and user workflow

Existing strict `presentation.groups` already owns membership/name through Graph history/save/CAS. Adding persisted collapse would extend every schema/transport and canonical digest contract for a navigation preference. This slice instead follows existing session-only view controls and states that limitation in the UI. The owner key and group-array identity invalidate fold state immediately; owner/group replacement and unmount reset it. Camera-only updates retain folding. Editing/replacing groups expands them; saved definitions contain no collapse field.

Each group has a keyboard-accessible fold/expand control outside the viewport, so an offscreen compact card remains recoverable. A collapsed world-space card shows its original name, member count, external/internal connection counts and explicit instruction to expand before inspecting/connecting ports. Its derived bounds use a 320 × 128 world-unit card anchored to the original frame. Member nodes and all incident curves are hidden only in this disposable projection. External connections are also listed exactly by original source node/port and target node/port in an expandable text section; original accessible full-edge descriptions stay intact. No replacement curves or synthetic editing endpoints are drawn: a boundary proxy cannot be mistaken for a valid typed port. Expand restores the original cards and curves. MiniMap deliberately continues to show all original node locations and the help text explains this.

Selected, focused, dragged and pending-connection members force expansion. Automatic expansion stays expanded until a new explicit collapse; it cannot unexpectedly disappear when selection/connection clears. Collapse is disabled with an explanation when a member is already in use; no silent deselection occurs. Directory selection and background marquee still address original nodes and can reveal their group. Busy/gesture states disable fold controls; readonly folding is allowed because it cannot write the graph. Control keys do not bubble into movement/deletion shortcuts. Expanding the focused card preserves its DOM button focus on the original group-selection label.

Original node/edge IDs, parameters, positions, source pins, enabled states, execution DAG, type checking, 16/24/40 budgets, history, save/CAS and owner recovery are unchanged. Collapse calls neither graph mutation nor port selection nor dispatch. Nested groups, persistent collapse preferences, boundary-routing previews and a general large-display workspace remain open.

## Verification and limitations

Measured commands, timestamps, source hashes and retained logs are linked in [evidence](canvas-group-collapse-20261016.json).

- 311 targeted mocked UI/transport/pure geometry tests across 10 files pass. Added tests cover collapse/expand with exact curve restoration and no mutations, real connection summaries and no ports, focus preservation, selected/focused/connecting guards, permanent automatic expansion, readonly/busy/key isolation, camera continuity and owner/group/unmount reset, edge classification and compact-frame culling.
- 32 pure backend contracts, three original nonsecurity File-owner persistence tests and 30 PUBLIC contracts pass (65 total). These confirm unchanged persisted grouping/annotation/camera contracts; they do not claim persisted collapse.
- TypeScript, Vite, test discovery, shared token check, scoped raw-color/pointer-policy check, 487-file PUBLIC closure and diff check pass. Vite's existing large-chunk warning remains.
- An initial focused run passed 82 tests. A subsequent owner-key hardening edit introduced a null-guard error caught by the first recorded UI and tsc runs; it was corrected and the final source-bound UI/File/build receipts rerun. The original failed receipts are preserved, not hidden.

Browser runtime/visual/native input/accessibility/hit-testing/performance acceptance remains NOT_RUN under the prior blocked boundary; no workaround was attempted. No PG/P0/security, user computer, Windows/GPU/provider/model, paid resources, push or hosted CI was attempted. P0 remains BLOCKED, R3-GATE HOLD, production Prompt Adoption disabled. Full professional infinite-canvas and nested grouping acceptance is not claimed.

Handoff: parent independent review before local commit/next tracked feature work. Keep the original untracked evidence and all user-machine/cost/denial boundaries; no push while hosted CI cost is unknown.

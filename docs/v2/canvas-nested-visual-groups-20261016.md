# Two-level visual group organization — 2026-10-16

Baseline `379309720650cf727bcc1482b63e591b569c47b5`; containing local commit identifies delivery. **PARTIAL:** nested visual groups are implemented, not executable subworkflows, a separate subcanvas, or full infinite-workspace acceptance.

## Audit and bounded design

The original Graph already owns optional disjoint `presentation.groups`, history/save/CAS, group outlines, selection and session collapse. No separate organizational owner was needed. The chosen bound is exactly two levels: a root and its immediate children. Existing limits remain 24 groups, 1–24 unique direct node members per group, 1–80 Unicode name characters, original ID contract and original execution budgets 16/24 nodes and 40 edges. Every group must retain at least one direct node; empty container-only groups are not supported. Direct membership remains globally disjoint; descendant membership is derived for display only.

The optional `parent_id` is stored only when assigned. Explicit null, missing targets, self-parent, cycles and a third level are rejected by original Graph parsing and frontend transport. Schemas 1–5 share the contract. Old definitions without parent keys retain their canonical values and hashes, and execution projection excludes this metadata as before. No catalog, executable nodes/edges, source parameters/pins, API, collection, queue, review, permission or lifecycle owner was added or changed.

## Mounted workflow

Choose an existing visual group, choose a root parent or “无父组（顶层）”, then explicitly apply. Parent candidates exclude self, child groups and assigning a parent to a group that already has children. Options show parent/name paths; direct member counts remain direct. Selecting a parent selects its own and all child members through original selection and dragging. Pending form choices reset on definition, interaction owner and blocked transitions.

Parent frame bounds include descendant cards and an extra domain gutter/label band around child frames. Culling and selected/focused/pending-port retention use descendant members. Parent collapse hides descendants and child frames/controls, counts original internal/external edges exactly once, and does not expose proxy ports. Expand the parent before changing a child's temporary fold. Selecting a descendant forces its enclosing groups open under existing retention rules. Collapse remains session-only; the MiniMap intentionally remains all original nodes and does not become a hierarchy navigator. Parent framing is card-derived rather than a freeform clipping/subcanvas surface.

Removing a group retains all nodes and promotes its immediate children to roots by removing their parent keys. Both canvas and inspector node deletion use the existing shared cleanup, which now also promotes children when a parent's last direct member is deleted. Undo restores the complete original graph in one history step. Explicit original Save/reopen/CAS remains the only persistence path; a hierarchy-only edit triggers the original dirty-navigation warning. Existing uncertain/conflict writes still preserve drafts and require original reconciliation.

## Verification

Exact commands, exit codes, timestamps, source hashes and receipt/log hashes: [evidence](canvas-nested-visual-groups-20261016.json).

- 346 mocked UI/transport/pure geometry tests across 10 files pass. New coverage: explicit assign/clear, impossible parent options, descendant selection, promotion, unchanged node/edge identity, two-level bounds/culling, parent/child compact suppression, retained anchors, undo/redo, dirty departure, original save/reopen, inspector deletion and no dispatch. Existing original pinned-source/editor/UNKNOWN/CAS tests also pass.
- 61 pure backend cases pass: schemas 1–5 optional-parent roundtrip and old digest restoration, execution invariance, strict/null/self/missing/cycle/depth rejection, original group counts/disjoint membership and unchanged budgets.
- Two nonsecurity original File-owner cases pass, including nested save/fresh-service read/CAS conflict/promotion/original digest restore and existing flat grouping.
- 30 PUBLIC tests pass. Forced TypeScript build, Vite build, test discovery, global/scoped token checks, diff check and 487-file PUBLIC source closure pass. Existing Vite chunk-size advisory remains.
- Initial UI receipt failed four label expectations after an unnecessary direct-count wording change; the established flat label was restored. The next run failed two new schema 4/5 fixtures that used schema-incompatible legacy draft ports; fixtures now use two valid text nodes. No production port validation was weakened. Initial receipts and superseded source-changing runs are retained.

Browser/visual/native IME/hit-testing/accessibility/performance/HTTP integration, PG/P0/security lifecycle, Windows/GPU/provider/user computer/full RC were NOT_RUN. No blocked-route workaround, paid action, push or hosted CI occurred. P0 stays BLOCKED, R3-GATE HOLD, production Prompt Adoption disabled. True executable composition, isolated subcanvases, deeper hierarchy, persistent folding, boundary routing and final target-platform acceptance remain open. The new synchronous form callbacks were tested through mounted changes/reset paths; retained stale DOM callback invocation is not separately claimed.

Handoff: parent independent review before further tracked feature changes. Preserve all earlier receipts and frozen environment/cost/denial boundaries; no push while hosted CI cost is unknown.

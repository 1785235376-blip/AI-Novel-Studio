# Bounded independent canvas notes — 2026-10-16

## Audit and scope

Baseline: `ece0ac7c5206904e4ba97aaa73d7e10403a3ac3e`, branch `work/dot-usability-handoff11-20261015`. The containing commit identifies this local delivery. Frozen requirements, repository rules, DS-v1.0/reference image, capability ledger, continuation checkpoint and current original Graph presentation/history/culling owners were reviewed before implementation. The original referenced 904-line roadmap remains unavailable; no exhaustive original-roadmap reconciliation is claimed.

Existing graph comments and visual groups required a small execution DAG. The display index could measure synthetic 1000/10000 objects but had no independent authored spatial objects. Original Graph validation caps the entire definition at 96,000 canonical UTF-8 bytes. Raising that or execution budgets would contradict this task. The bounded approved design is therefore **128 independently authored note cards**, not a claim that 1000 meaningfully populated persisted objects fit this owner.

## Implemented original-owner flow

- Optional `presentation.notes` in existing schemas 1–5: stable per-card ID, plain text, bounded x/y position. No new store/API/queue, execution node, ports, permission, source pin or automatic content creation.
- Explicit “在视口左上添加便笺” creates an empty card 32 screen pixels from the current viewport's top/left, clamped to the existing ±100000 world limit. Cards can overlap; authors move them explicitly.
- Mounted directory and text/coordinate controls, title drag preview followed by one original history update, explicit removal, original undo/redo, dirty departure guard, Save/CAS and reopen. The card body renders text, never HTML. A card can be authored in a graph with no execution nodes.
- Fixed 240×160 world geometry; text scrolls within the card. Existing projection culls cards against the current display camera with selected/dragged retention. Unknown/hidden layout renders the bounded set. The native directory is capped at 128 options.
- Note selection is separate from graph node selection and pending typed connections. Movement uses the authoritative definition, never an unconfirmed alignment preview. Pan-tool/Alt/middle title gestures delegate to original camera gestures; body text remains isolated for selection.
- Readonly/busy, owner/definition replacement, pointer cancellation, lost capture, Escape and window blur cancel note movement. Unicode composition stages locally, commits on composition end, and abandons the old DOM input on identity/blocked/revision replacement. These are mocked event regressions, not native IME acceptance.

## Bounds and compatibility

- At most 128 cards, 256 Unicode codepoints per card, 12,000 total codepoints; duplicate/malformed IDs, invalid coordinates, unknown fields and over-budget payloads are rejected. No native textarea maxlength silently truncates pasted astral characters.
- Whole-definition owner limit remains **96,000 bytes**, including all nodes, edges, comments, groups and notes. Before note mutations, the frontend uses UTF-8 JSON size plus a conservative 32-byte allowance per number for Python numeric spelling. This deliberately may refuse an operation before the backend's exact threshold; it is not an assertion of identical JS/Python byte accounting. Original save still owns exact canonical, record/history/scope capacities and CAS.
- Existing graph budgets remain 16/24 nodes and 40 edges. Notes never enter execution projection. Legacy absent presentation/notes serialize without new keys and preserve canonical digests; removing notes restores the original definition digest. Source pins, node parameters, Review/UNKNOWN and permission owners remain unchanged.
- Existing MiniMap still shows execution nodes only, explicitly stated in UI. Notes are not part of visual-group membership, marquee, snapping, multi-note drag, copy/paste or node alignment. Independent note navigation is through the bounded directory and coordinate editor. Unsaved crash recovery and durable undo are not added.

## Verification on delivered source

Exact commands, timestamps, exit codes, source hashes and receipt/log hashes: [evidence index](canvas-spatial-notes-20261016.json). All listed checks exit 0 and report no source changes during execution.

- **387 tests in 11 files:** mocked UI/transport and pure geometry, including original CanvasOps, GraphCanvas, presentation, workspace, production editor, Director and PUBLIC placeholder checks.
- **81 pure backend presentation contracts**, **2 nonsecurity File-owner tests**, **30 PUBLIC contracts** (113 in the selected Python invocation). Schemas 1–5 legacy omission, independent 128-card roundtrip, aggregate boundaries, unchanged execution digest, original reopen/edit/move/remove/CAS, and original nested-group regression are covered.
- Forced `tsc -b`, Vite build, test discovery, global token guard, scoped raw-color guard, diff check and PUBLIC 487-file source closure pass. Existing Vite large-chunk warnings remain; no dependency changes.
- Independent review reran selected UI and schema/File checks. Its findings drove fixes for unconfirmed alignment leakage, native maxlength truncation/IME identity replacement, JS end-anchor note ID acceptance and pan-tool coordinate mutation. Source-level fixes and regressions are included; independent counts are overlapping and not added to the totals above.

The first UI run failed because its supposedly oversized fixture still fit the conservative payload threshold; fixture corrected without relaxing capacity validation. Initial and superseded receipts remain under `docs/delivery/v2-development/canvas-notes-*`; successful runs made before source changes are not final-source acceptance.

## Performance evidence and acceptance limits

[Node-only benchmark](canvas-notes-benchmark-20261016.json) uses 128 meaningful authored note-shaped objects, zero execution nodes/edges, 1000 measured camera projections after warmup, and records UTF-8 size, conservative authoring size, timings and noisy GC heap deltas. It includes disposable index construction/culling, not React/DOM/paint. Negative heap samples remain visible and carry no acceptance claim. Separate File tests establish that the 128-card shape actually persists/reopens.

**P1 / GRAPH-02/06/08/10 remain PARTIAL.** The >=1000 persisted display-object target is not met by this 128-card slice. Existing synthetic large-display benchmarks cannot substitute for it. Full LOD, richer display object types, spatial index, actual browser FPS/memory, native focus/IME/accessibility, larger persistence design and target-machine acceptance remain open.

Browser/visual/native/HTTP integration, PG/P0/security lifecycle, Windows/GPU/provider/user computer/real model/full RC were NOT_RUN. P0 stays BLOCKED, R3-GATE HOLD, production Prompt Adoption writes disabled. No browser workaround, paid action, push or hosted CI; unknown CI cost remains a stop boundary. No main merge, release or tag. Preserve earlier evidence and all environment/cost/denial restrictions. Parent final-SHA review precedes the next tracked feature slice.

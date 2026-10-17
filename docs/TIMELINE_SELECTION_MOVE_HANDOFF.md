# Atomic Timeline selection move handoff

Base HEAD: `3eb1dfeeba1c94a259aab62ca5d0d05e4f803d16`.
Status: implementation, primary verification and scoped independent review complete. This is bounded selection-move wiring, not full product or release acceptance.

## Original ownership and behavior

The existing track header can select all clips in a track. The inspector now offers an explicit signed integer-millisecond offset for the entire current selection. Its new descriptor-only helper compiles an array of existing `clip.move {op, clip_id, track_id, start_ms}` operations. The mounted bridge distinguishes this explicit array from the unchanged single-operation payload. It checks exact fields, complete ordered selection membership, original tracks and a shared offset. This local envelope is not a new backend operation or persistence schema.

The original `useStudioTimelineEditor` owns all mutation and history. It checks a detached draft, updates every selected start, validates the complete final result through `checkedTimelineDraft`, then calls its existing `change()` once. It never loops through the single-clip mutation helper. Valid collective moves can therefore pass despite intermediate overlap. Rejection publishes no partial result or history; zero offset is a no-op. Success is one local undo/redo entry.

Only selected `start_ms` values change. Original track membership, relative spacing, source pins, source in/out, rational speed, fades, crop/transition fields, other clips, captions and timeline duration remain subject to the original normalized contract. No neighbor repair, automatic ripple, cross-track relocation, persistent grouping, source replacement, automatic Save or render is added.

The backend's original atomic editor permits 1–40 operations and 128,000 batch bytes; the original document schema allows 30 total clips. Repeated moves of the same clip remain valid backend operations; this selection UI separately requires distinct IDs. Audio overlap remains legal. Final geometry and transition validity come from the original validators, not a stricter new collision policy.

Persistence remains original explicit Save with expected-version CAS and original GET/manual adoption. The source-edit-specific `timelineEdit` client bridge is unchanged. No backend runtime, route, schema, old tests, runner, shared tokens or shell were modified. No packaging run or updated distributable is claimed.

## Lifecycle and input boundaries

The controller binds callbacks to client and semantic draft generation, including edits/undo and observed project/current-context/busy/permission changes. Its existing pending-operation, authority, lock, conflict and UNKNOWN gates remain in force. The mounted route adds synchronous monotonic selection generation, so selection A→B→A cannot revive a retained callback. Inspector callbacks bind authored-input and semantic-context generations and lifecycle; context/selection/permission ABA and unmount are rejected. Unrelated rerenders preserve authored input.

Typed but unapplied inspector values remain form state rather than protected timeline draft history. Successful descriptor generation is not proof of application or persistence; the UI points to the timeline result and explicit Save. Save does not prove measured media duration or successful rendering.

## Primary verification and exact source closure

All executable primary checks use the unchanged `scripts/run_v2_checks.py`, the approved clean Python environment, owned profiles, retained actual commands and full-source before/after hashes.

- Final UI r2: **254 passed across 13 suites**, including **54 new cases**: 32 controller/mounted, 8 inspector and 14 descriptor cases. Covers whole-track mounted routing, exact batch rejection, positive/negative/no-op offsets, adjacent video moves, rational audio, transitions, preserved fields, atomic undo/redo, explicit mocked Save and GET/remount, selection/context/input ABA, pending Save, conflict/UNKNOWN and lifecycle gates.
- Forced TypeScript r2: passed.
- Production Vite build r2: passed; existing greater-than-500-kB chunk advisory retained.
- UI token guard r2: passed, 52 files.
- All four final frontend receipts contain identical **2,564-entry** source maps, equal before/after and to files at completion. Each actual retained log digest was verified.
- Primary File r2: **72 passed, 1 PostgreSQL-only case deselected, 1 existing Starlette/httpx warning**. Includes 21 new selection cases and unchanged trim, slip/delete, asset handoff and caption preflight regressions. Real original File owners, synthetic media, CAS/history checks and fresh service/store reopen provide persistence evidence separately from mocked UI transport.
- Primary File r2 predates a correction to exactly two new frontend test tables: `frontend/src/creative/StudioTimelineSelectionMove.additive.test.tsx` and `frontend/src/nle/timelineSelectionMove.additive.test.ts`. Comparison to final frontend maps finds only these two paths differ. Backend, runtime frontend and File test bytes are identical. Do not call the complete primary File and final frontend maps identical.

## Retained failures and corrections

1. During r1 origin proof, a concurrent worker copied an older probe over the prepared path. Natural startup used SHA-256 `71d879f23e35669fb125030543cd38fcc1288ecd6052cd655eb88f7ab56c9396`; runner child used `93692647be0059d24c72d28fc537b31b0980e471634b9599b0b1e83231f599e2`. Both located the current worktree and clean dependencies, but the latter lacked direct Timeline-owner specs. The r1 File run passed with stable product sources, but its preceding proof is not a single unchanged-probe chain. Preserve all r1 evidence. The File owner repeated natural startup, original-runner child proof and File tests using separately named immutable r2 probe/launchers. Primary r2 is authoritative. See `delivery/v2-development/timeline-selection-origin/FILE-EVIDENCE.md`.
2. Static review caught missing required track mute/gain fields in the new descriptor fixture before primary UI execution; only that new fixture was corrected.
3. UI r1 passed 254 tests, but forced TypeScript r1 failed on a new `it.each` table: array rows became positional callback arguments rather than an IDs array. The same pattern existed in the new descriptor suite. Eight nominal invalid-selection rows therefore did not establish their intended array coverage. Only those two new test tables were changed to `{ids}` rows/destructuring. Final UI, forced TypeScript, build and token checks were rerun as r2. Preserve r1 pass/failure logs and receipts; do not describe the affected r1 cases as validated duplicate/empty/missing-array coverage.

## Independent review

Scoped independent review passed: `delivery/v2-development/timeline-selection-independent-review.json` (`PASS_SCOPED_INDEPENDENT_REVIEW`).

- Independent File: **72 passed, 1 PostgreSQL-only deselected, 1 existing warning** on the final source set.
- Independent UI: **112 passed across 5 suites**, including all **54 new cases** plus unchanged trim/slip-delete suites. These repeat primary coverage; do not add them to unique totals.
- Fresh independent normal-startup and original-runner child proof passed using a separately owned probe and paths.
- Independent origin/File/UI source maps each contain **2,564 entries**, equal before/after, current files and all four final primary frontend maps. The final independent File rerun closes the primary File two-test-map discrepancy without modifying backend/File-test sources.
- Review confirms **2,556 baseline source entries byte-exact**, with exactly three existing runtime files changed and five additive source/test files. No remaining scoped implementation blocker was identified.
- Actual retained independent log hashes and full-source equality were also rechecked while preparing this handoff.

## Remaining acceptance boundaries

Browser/visual/geometry, native input, Windows/target-platform, packaged-runtime, PostgreSQL, GPU/provider/model, decoded-media duration, rendered-media quality and full E2E/product/release acceptance remain NOT_RUN/open. No server/browser, installation, push, merge, tag or release was performed by this slice. UI controls reuse existing primitives/styles; this is not visual acceptance.

## Evidence index

`delivery/v2-development/timeline-selection-evidence-index.json` records SHA-256 values and byte sizes for retained selection evidence, including failed/superseded runs. Actual receipts retain source maps, commands, roots, timestamps, statuses and log hashes. The index was finalized after independent review; it does not rewrite original evidence.

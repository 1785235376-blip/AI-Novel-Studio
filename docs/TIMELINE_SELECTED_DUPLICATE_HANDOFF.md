# Selected Timeline clip duplication handoff

Base HEAD: `feade20ce2f6671e5d5a16c0781896f3c5696927`.
Status: implementation, primary verification and scoped independent review complete. This is bounded selected-clip duplication, not full product or release acceptance.

## User outcome and original ownership

The existing inspector now offers **整体复制所选片段** with an explicit signed integer-millisecond offset. Every selected clip is copied to its original track, preserving relative spacing. Zero-offset audio duplication remains legal; final video geometry uses the original validator. The user does not need to invent technical IDs: one explicit action allocates all new IDs once, then captures the complete original-ID → new-ID mapping in the original owner descriptors. Invalid selection/count/offset is checked before allocating IDs. Invalid IDs or collisions are refused without hidden regeneration or retry.

The shared `timelineSelectionDuplicate.ts` compiler emits existing `clip.duplicate` operations first, then existing `clip.update` operations only for copied internal transitions. Both selected endpoints receive new IDs, and the copied transition target is remapped to the new target. Transitions to unselected clips are explicitly disclosed as not copied. Original incoming/outgoing relationships remain unchanged; no neighbor repair or invented relationship is performed.

The mounted bridge verifies complete ordered selection membership, original tracks, a common offset, exact identity mapping, and the exact authorized transition updates. Recursive descriptor comparison rejects missing/extra fields, including undefined-valued, symbolic, hidden or accessor fields. Identity maps must contain only the complete selected mapping with plain data fields. Sparse selection/descriptor arrays are rejected.

`useStudioTimelineEditor` retains draft/history ownership. It applies all duplicates to one detached draft, strips copied outgoing transitions as the original backend does, restores only compiled copied internal transitions, validates the complete final result through `checkedTimelineDraft`, then calls the existing `change()` once. Failure publishes no partial result or undo entry. Success is one undo/redo entry.

Original/unselected clips, source pins, trims, rational speed, fades, gain/mute, crop, geometry, captions, original tracks and timeline duration remain preserved under the normalized original contract. No source import, binary copying, source-edit endpoint, automatic Save, rendering, preview, task or asset creation is added. Explicit Save retains the original expected-version CAS and source-authority checks. Mocked UI Save/GET evidence is separate from real File persistence evidence.

## Existing single-copy boundary

Single-clip duplication already existed and remains unchanged. Its legacy controller generates its own UUID and retains `transition_out`; the mounted single-copy route does not honor the descriptor's new ID or target track. This pre-existing divergence is not silently corrected or reused by the new selected-copy path. Do not claim duplication generally was missing, or that this slice establishes backend equivalence for legacy single-copy behavior.

## Limits and lifecycle

Original limits remain 30 total clips, 40 operations and 128,000 batch bytes. New IDs follow the original 1–240-character identifier grammar, must be pairwise distinct, and cannot collide with any existing clip. Clip identity remains a separate namespace from source and track identity.

Valid selected-copy inputs cannot reach the 40-operation or 128,000-byte ceiling while retaining the 30-total-clip and 240-character-ID bounds: at most 15 copies and 14 internal-transition updates fit. The compiler keeps explicit original operation/byte guards; frontend tests exercise exact 30-resulting-clip and maximum-ID-length admission rather than claiming an unreachable guard-trigger test. File tests separately exercise the original backend's direct batch limits.

Inspector callbacks bind authored-input/context generations and lifecycle. A synchronous consumed-generation latch blocks repeated clicks, including failed attempts; correcting authored input or changing context permits a new explicit attempt. Stale callbacks do not generate fresh IDs. The mounted route binds monotonic selection generation, so selection A→B→A cannot revive approval. The controller binds client and epoch/handoff generation, including observed permission/project/current-context/busy changes and draft-edit→undo ABA. Original lock, pending operation, conflict, UNKNOWN, authority and unmount gates remain in force. Unrelated rerenders preserve authored input.

Generated descriptors are not proof of application or persistence. UI messages point to the timeline result and explicit Save. Save does not prove measured media duration or successful rendering.

## Primary verification

All executable checks used the unchanged `scripts/run_v2_checks.py`, the approved clean Python environment, separately owned profiles and retained actual commands/logs. Product sources were frozen before serial execution; there were no failed runs or post-verification source corrections in this slice.

- UI: **320 passed across 16 suites**, including **66 new cases**: 27 controller/mounted, 9 inspector and 30 compiler cases. Covers signed/zero offsets, exact mapping, transitions, field preservation, atomic failure/history, whole-track routing, mocked Save/GET/remount, strict forged descriptors, repeated clicks and lifecycle/ABA boundaries.
- Forced TypeScript: **PASS**.
- Production Vite build: **PASS**, with the existing greater-than-500-kB chunk advisory.
- UI token guard: **PASS**, 52 files.
- New real File cases: **32 passed**, one existing Starlette/httpx warning.
- Existing File regressions: **60 passed, 1 PostgreSQL-only case deselected**, one existing warning. Covers existing selection move, trim, slip/delete, asset handoff and caption preflight.
- File evidence exercises original operation composition, saved DTO parity and stable IDs, CAS/history, no-write rejection and source authority, with fresh original service/store reopen. Fixtures are synthetic; this is not decoded-media or rendered-output acceptance.

## Independent review and source closure

`delivery/v2-development/timeline-duplicate-independent-review.json` records **PASS_SCOPED_INDEPENDENT_REVIEW**.

- Independent File: **53 passed** (32 new + 21 existing selection cases), one existing warning.
- Independent UI: **120 passed across 6 suites** (66 new + 54 existing selection cases).
- Independent counts repeat primary coverage; do not add them to unique case totals.
- Fresh separately owned natural-startup and actual-original-runner-child origin proofs matched exact module specs and probe bytes without importing the product or pytest during proof.
- All **10** primary/independent origin/check receipts contain identical **2,583-entry** source maps, equal before/after and to current files. Actual retained log digests were verified again during final indexing.
- Of **2,578** baseline source entries, **2,575** remain byte-exact. Only three approved existing runtime paths changed, with five additive source/test paths. Existing backend runtime, old tests, runner, shared tokens and shell remain unchanged.

## Acceptance boundaries and evidence

Browser/visual/geometry, native input, Windows/target-platform, packaged runtime, PostgreSQL, provider/GPU/model, decoded-media duration, rendered-media quality and full E2E/product/release acceptance remain **NOT_RUN/open**. No server/browser, installation, push, merge, tag or release was performed by this slice. Reusing existing primitives/styles is not visual acceptance.

`delivery/v2-development/timeline-duplicate-evidence-index.json` records SHA-256 values and sizes for the new retained receipts, logs, origin proofs, launchers, independent report and this handoff. It preserves existing indexes and historical evidence unchanged. The complete test inventory ledger has not been refreshed by this implementation handoff; collection inventory is a separate bookkeeping step.

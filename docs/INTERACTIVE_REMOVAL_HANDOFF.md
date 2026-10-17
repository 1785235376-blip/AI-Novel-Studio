# B07 existing-adaptation unused-node removal handoff

Date: 2026-10-17 UTC

## Scope and behavior

The existing interactive editor now previews and explicitly confirms removal of one current adaptation node, identified by its exact planning node ID, version and title. Duplicate titles remain distinguishable. Removal is a local draft change; the original Save, optimistic concurrency, history, analysis, review, source rebinding and independent export owners remain authoritative.

A removable node must not be the entry, must have no incoming choices (including false-condition choices and self-loops), and must leave at least one node. Blockers name exact referring node/choice IDs and direct the author to the existing entry and choice controls. There is no cascading choice removal or implicit replacement entry. Removing a node removes its own authored content and outgoing choices; it does not delete the original planning node. Re-adding uses the existing reviewed add flow and starts with blank authored content.

Surviving nodes, dialogue, variables, choices, IDs, node/graph versions and graph-record references are retained exactly, including Unicode. No source repinning or other reference updates are performed by the frontend. Original server source capture and authorization remain unchanged.

The UI fails closed for unavailable/mismatched/nonunique catalog identities, archived or withheld/stale records, busy actions and IME composition. Catalog/client/scope changes, navigation, cancellation, edits, Save and revert invalidate removal previews or retained callbacks. Removed-node tombstones prevent saved analysis issues from navigating to a removed-and-readded replacement before Save/reanalysis. Revert explicitly restores the saved graph and clears those tombstones.

## Changed source and tests

- Existing `frontend/src/experimental/InteractiveStoryPanel.tsx`
- New pure helper `frontend/src/experimental/interactiveNodeRemoval.ts`
- New helper tests `frontend/src/experimental/interactiveNodeRemoval.test.ts`
- New UI tests `frontend/src/experimental/InteractiveStoryPanel.removal.test.tsx`
- New File-owner tests `tests/test_interactive_removal_handoff.py`

Backend, parser, client/API, exporter, all old tests, design tokens and shared shell are unchanged. The prior `docs/INTERACTIVE_MEMBERSHIP_HANDOFF.md` remains unchanged. No new engine or public API was introduced.

## Static review history

Independent static review identified a reverse-order same-batch race: confirming removal and then invoking a retained edit, Save, revert or navigation callback could resurrect the old graph, save the wrong draft or navigate to an out-of-range index. Mutation authority checks now precede side effects, and navigation checks bounds. New regressions cover both action orders and retained callbacks after rerender.

The first correction over-invalidated ordinary edit authority at IME boundaries, which could drop the final composed text in the same event batch. Composition boundaries now invalidate the removal/admission epoch separately from the normal text-edit ticket. New compositionStart→Unicode-change and compositionEnd→Unicode-change tests verify exact text preservation, rejected stale removal and subsequent explicit Save.

Final independent static approval applied to panel SHA256 `75f9458f05707a76e7936388f2a25d0857c109dc6147c0f9816cb933493973bf` and removal UI test SHA256 `88d2b4cf9a42ada4696394a95cada1282bae0fcc2b1c7749d79eedbf0e8cc6f4`. Sources remained frozen throughout primary execution. These were pre-execution static corrections; there were no failed primary gate logs to discard or overwrite.

## Verification

All gates ran serially through unchanged `scripts/run_v2_checks.py`, using isolated profiles. File execution used only `/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python`, normal repository `conftest.py`, and `not postgres_backend_only` selection. Outer `PYTHONPATH` was unset.

- Fresh natural-startup and actual runner-child PathFinder origin proofs: PASS, without importing product or pytest modules
- Primary File: **85 passed, 45 PostgreSQL cases deselected**
- Primary UI: **89 passed across six files**, including 32 removal UI cases, nine pure-helper cases and 48 unchanged original cases
- Independent File rerun: **85 passed, 45 PostgreSQL cases deselected**
- Independent UI rerun: **89 passed across the same six files**
- Independent fresh natural-startup and actual runner-child provenance: PASS
- Forced TypeScript: PASS
- Production Vite build: PASS, with the existing large-chunk advisory
- UI token guard: PASS, 52 files
- Nine original-runner receipts (six primary, three independent): identical 2,613-source maps; before/after/current hashes and all log hashes verified
- Independent audit: prior evidence and frozen sources unchanged; primary TypeScript/build/token receipts verified, not independently rerun
- `git diff --check`: PASS

The new File regression performs removal Save → complete File repository/service reconstruction → saved analysis → playback → original review → original export. It checks exact surviving specs and source versions, old membership in history, unchanged original planning graph and manuscript, and blank source content on re-add. The additional File case checks original CAS and authorization rejection without persisted mutation.

UI coverage includes exact identities, dirty Unicode, blockers, explicit entry/choice repair, self-loops/false conditions, cancellation, repeat confirmation, reverse-order stale callbacks, re-add tombstones, Save conflict retention, IME, catalog loading/errors/ABA, and client/scope ABA. Unit and build results are not browser or target-engine validation.

## Evidence and status

`docs/delivery/v2-development/interactive-removal-evidence-index.json` binds the primary receipts, raw logs, launchers, probes, natural-startup proof, frozen source hashes, audit and this handoff. `interactive-removal-primary-audit.json` records the six-receipt hash audit. Independent File/UI execution and provenance are complete, recorded in `interactive-removal-independent-audit.json`. Primary and independent counts are repeat verification, not additional distinct capability coverage.

This is a thin isolated checkout on `work/dot-interactive-removal-20261017`, baseline `b5f52c823b4df58ffe69ec309bfc2fc0e4a114fe`. Historical `docs/delivery/` records were excluded by sparse checkout; no absent historical record is claimed verified and no prior evidence index or ledger was modified. The new evidence is persisted locally. The parent authorized a local isolated-branch commit of the reviewed sources, new handoff and owned evidence. Commit identity is reported separately and will be checked by the independent reviewer; no publication or push is authorized.

Real-browser visual/geometry/accessibility validation, native desktop/Windows, target-engine runtime, PostgreSQL, paid providers, publication and push are **NOT_RUN**. Export runtime status remains `NOT_RUN`. No install, network/provider call, cleanup or shared-runtime modification was performed.

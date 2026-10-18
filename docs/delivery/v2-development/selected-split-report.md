# Reviewed selected Timeline split

Base: 9752db6a. Isolated sibling: studio-selection-split. No backend runtime changes.

## Delivered

- Ordered explicit-selection preview at exact integer-millisecond playhead; boundary/outside clips visibly skipped. No snapping, link/group expansion, or auto repair.
- Complete detached-final preflight before allocating IDs, including rational source cuts, still-image handling, locked crossing clips, fades, transition adjacency/windows, clip limits, and collision rejection.
- Exact existing clip.split descriptors; one original local change/undo step. Original Save/CAS remains the only persistence path.
- Parent revision/client/permission/lifecycle, selection and playhead generation fences; stale retained Apply allocates nothing. Transfer Locate uses the same selection/playhead setters.
- Legacy single-clip split now reuses the validated helper, preserving its signature/gates and fixing outgoing-transition placement. This divergence was source-confirmed; no pre-fix failing test was executed. The compatibility regression passes post-fix.

## Verification

- selected-split-final-focused: 143/143 tests, nine focused frontend files, original runner, unchanged sources.
- selected-split-final-differential: 12/12 pure original-owner differential checks comparing actual compiled TypeScript descriptors and result to original Python apply_timeline_edits/normalizer. These do not exercise File repository persistence.
- Controller Save/reopen tests use mocked client contracts, not real persisted roundtrips.
- selected-split-verified-types-tokens: final TypeScript/token check receipt (see status in receipt).
- Independent review cleared final split routes, preallocation fences, backend-parity linkage and narrow legacy reuse.

Preserved earlier failures: missing unrelated local_interop_desktop during global pytest conftest bootstrap, and inspector regressions found then fixed (shared playhead reset of move/copy inputs, obsolete scalar descriptor expectation). Pure differential tests use --noconftest. The earlier selected-split-final-types PASS had sources_changed_during_check=true and is superseded by the final verified check.

No full suite, PostgreSQL, media render, paid/API call, browser, user-computer execution, install or push. Combined production build belongs to integration owner. Windows/media/product acceptance remains unverified.

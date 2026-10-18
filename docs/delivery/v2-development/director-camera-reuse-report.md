# Director selective camera reuse

Base: `6ef470ff6d3841e7f14ab4b896c98fccb034ea33`.

## Scope

CreativeCanvas remains the sole authoring owner. A subordinate control lets the author choose one current-scene Director note, explicitly select other current-scene note IDs, select any of five fields (shot size, camera angle, camera motion, lens, composition), inspect before/after differences, and explicitly apply. Empty/absent source fields are visibly identified as clearing the selected target field. No automatic save, generation, dispatch, approval, new model, backend, or engine is introduced.

Patching preserves original IDs, ordering, durations, performance, story/blocking, camera grammar/spatial relationships, source evidence/bindings, unselected fields and unrelated scenes. Undo is available only for the exact resulting draft and matching scene/version; subsequent author edits, saving/busy state, scene changes and authority loss retire it without overwriting later work. Applying back to the saved baseline remains undoable even when the parent's computed dirty flag becomes false.

Preview pins the draft, current scene/version/dirty/editability/busy state, selected source/target IDs and field selection revision. Source or target changes (including non-camera fields), scene/version/authority round trips, selection changes, and unmount retire captured actions. Apply is one-shot and requires a fresh explicit preview after invalidation. Existing explicit Save/reopen behavior is retained.

## Review and verification

Independent source review caught the clean-baseline Undo edge; corrected and independently accepted. Tests cover whitelist/admission failures, field preservation, empty/absent values, no-op changes, original Canvas apply/undo/explicit Save/reopen, stale callbacks, ABA, baseline-return Undo and later-operation retirement.

Original `scripts/run_v2_checks.py` was used in the isolated sparse worktree, with the recovered Python runtime and shared frontend dependencies. Raw JSON receipts and logs accompany this report. Final receipt hashes bind the checked source files. The first build attempt found omitted sparse-checkout interop contracts; those tracked contracts were materialized without changes. The subsequent production check was BLOCKED/unfinished: TypeScript was externally killed with exit 137 and emitted no TypeScript diagnostics; Vite did not run. The raw build receipt records FAIL/137. The cause is not established. Per root instruction, no further standalone build was attempted; the combined production type/build check remains pending with root after integration.

No browser run: the parent's previously verified system crashpad EPERM blocker was respected, with no install or retry. Geometry unit tests are included, but do not establish visual screenshot acceptance. No PostgreSQL, full backend run, paid call, user-computer action, remote push or deployment was performed.

Final frozen checks: 39/39 focused tests; 64/64 authoring/reopen/geometry regression tests; UI token guard PASS (52 files). Independent review accepted the corrected patch. Production types/build is explicitly pending; this is not a full production-check pass.

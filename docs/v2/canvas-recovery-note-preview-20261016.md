# Cached graph note recovery inspection — 2026-10-16

## Bounded increment (PARTIAL)

Base: `fdc19f304a6416d0f003f4b2ed944ceb2c5187d6`. This slice expands the existing original `StudioGraphDraftRecovery.tsx` read-only author-input details to include `presentation.comment`, the spatial-note count and complete `presentation.notes[].text`. It does not implement new recovery authority, merge, comparison or persistence behavior.

The panel explicitly labels the values as local cached author input, not a verified field-by-field comparison with current server content. Twenty complete notes are mounted per page; all pages remain available, including the final four of an eligible 1024-short-note fixture. Empty strings, Chinese, multiline text and literal HTML are retained in read-only textareas. Paging is bound to the displayed recovery snapshot and never invokes reads, graph edits, save or run. Original node-parameter inspection remains unchanged.

## Preserved owner and limitations

- Original cache decoder and controller remain byte-unchanged. Only valid schema 1/2 text graphs are eligible; schema 3–5 and `asset_reference` remain excluded.
- Original 110000-character cache envelope, 256-codepoint per-note and 12000 aggregate note-text constraints, and original whole-definition bounds are unchanged. A passing 1024-short-note fixture is not an unconditional cache-capacity, quota or durability guarantee.
- Actor/project-incarnation, exact saved version and both digests, current authority, dirty/busy/UNKNOWN, cross-tab and explicit discard checks remain in the original controller. Retirement removes cached preview text. The UI introduces no new API reads or recovery/apply control.
- Explicit recovery still restores the entire original definition in memory, including note positions and comment. Saving to the server and running remain separate original actions.
- No provider request, paid compute, workflow engine, backend change, automatic merge, second store, new persistence format, user-machine action, push, merge or release.
- Broader durable recovery, multi-schema/media recovery and actual browser visual/accessibility/performance acceptance remain open. P0 BLOCKED, R3-GATE HOLD and prior release gates unchanged.

## Verification

Final frozen source SHA256:

- `frontend/src/creative/StudioGraphDraftRecovery.tsx`: `ac357fb519c41fe9c8359b97767107a1b788c5a79825168ff0a072e20ddcc9da`
- NEW `frontend/src/creative/StudioGraphDraftRecovery.notes.test.tsx`: `1729db23908b27c647b8ac181d6d6f3c0a993a646ff152d388753ea935c7b6e4`

Sequential local commands, shared dependency symlink used without installation or mutation:

1. `vitest run src/creative/StudioGraphDraftRecovery.test.tsx src/creative/studioGraphLocalDraft.test.ts src/creative/StudioGraphDraftRecovery.notes.test.tsx --maxWorkers=1 --minWorkers=1 --no-cache`: **24 PASS**, 3 files (11 original mounted recovery, 6 original cache, 7 new additive tests); default timeouts.
2. `tsc -b --force`: PASS.
3. `vite build`: PASS, 2286 modules; existing >500 kB bundle advisory remains.
4. `node ../scripts/check_ui_design_tokens.mjs`: PASS (52 shared UI files). Separate raw-color scan of the changed creative component: PASS.
5. Pre/post SHA256 comparison and `git diff --check`: PASS. Both protected original tests have no diff.

The first focused run was 23 PASS / 1 FAIL: a new fixture used JavaScript negative zero, while the pre-existing JSON roundtrip normalizes it to zero. The fixture was corrected to ordinary zero after the run ended; production source and existing tests were unchanged. The entire sequence above then ran on frozen final files. Raw logs, initial failure, source-file map, command/result index and before/after hash receipts are preserved in the [verification bundle](../delivery/v2-development/recovery-notes-20261016/README.md). Raw logs are unchanged; the empty typecheck log records a silent successful command, with exit status documented in the index.

New regression coverage proves literal/full/empty text, all 1024 notes reachable in bounded pages without cache mutation, exact conflict preservation, explicit recovery without save/run/provider calls, late authority retirement, absent presentation and unchanged privacy/envelope eligibility. These are jsdom/mock-controller checks, not browser/HTTP integration evidence.

Actual visual acceptance: **NOT_RUN**. A previously established browser socket `EPERM` blocker was respected; no retry or bypass was attempted. Canonical design guidance was read, original shared Panel/Button/StatusMessage and native details/labels/textareas were reused, and no design tokens, shell geometry, CSS or protected surfaces changed.

Parent final source review, manifest refresh and any local commit are separate follow-up steps; this report does not claim they have occurred.

Final evidence staging note: unrestricted staged `git diff --check` reports exit 2 for the byte-preserved independent test log's final blank line only. Product source and test changes pass the whitespace check. The raw log is retained unchanged so its verified hash remains reproducible; this is not a runtime/test failure.

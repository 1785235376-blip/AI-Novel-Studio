# B08 Writer Room task context and decision drafts

Date: 2026-10-16. Base: `8ef05ffe07f388c92e45d775a9be9d1b9ffa2b75`.
Status: bounded frontend increment IMPLEMENTED; B08 remains PARTIAL.

## Audit and implemented behavior

The existing WriterRoomPanel is mounted by ExperimentalWorkbench. The original Writer Room service already owns scoped task assignment, CAS transitions, chapter digest checking, comments and review-package export. The original chapter reader rejects a changed revision; it is not a historical-version archive. The existing shared navigation opens the unified review inbox, but does not promise exact review-item targeting.

This increment adds:
- Task-bound chapter ID/digest and original review domain/ID/version in a collapsible context inspector.
- An explicit read-only request using the task's exact chapter reference, never the catalog's newer revision. A failed/stale read reports the limitation and never substitutes current prose.
- Context invalidation on refresh/task version changes and abort on task changes. No automatic chapter fetch or retry.
- Session-only decision-note drafts across task switches, included in the existing unload warning. Successful task transition receipts clear the note; failure/unknown outcome retains it. No new browser persistence or storage owner.
- Timestamped task event history, with an explicit missing-time label.
- UI disables submission/completion against non-current sources and transitions for invalid participants. Original backend checks and CAS remain authoritative.

Task field saving, assignment, transitions, review acceptance, permissions and actual team communication remain owned by the original APIs. No new API, realtime engine, invitation flow or review approval was introduced. Existing navigation remains unchanged.

## Verification

All tests use synthetic mocked fetch responses; no actual team write, provider/model invocation or external communication was performed.

- `cd frontend && ./node_modules/.bin/vitest run src/experimental/WriterRoomPanel.test.tsx`: exit 0, 14 tests (9 existing, 5 added).
- `cd frontend && ./node_modules/.bin/tsc -b --pretty false && ./node_modules/.bin/vite build`: exit 0. Vite reports existing oversized bundle warning (>500 kB).
- `node scripts/check_ui_design_tokens.mjs`: exit 0, 52 files checked. This guard is supplementary, not a claim of pixel verification.
- `git diff --check`: exit 0.

New tests cover exact pinned digest/no eager fetch, review identity/timestamp, stale source with no fallback, note-only draft switching and confirmed clearing, unknown transition retention/no replay, delayed read abort and refresh invalidation. Existing CAS conflict and draft-preservation tests remain passing.

## Limits and outstanding acceptance

- Browser visual/geometry and live File/PG/backend/team integration: NOT_RUN in this bounded slice. No screenshots or visual acceptance claimed.
- Historical chapter snapshot reading remains unavailable if the original owner rejects a stale digest.
- Notes survive task switching only while the room remains mounted. Leaving the room or changing client identity clears them; no offline/restart recovery claim.
- No exact-review navigation contract was invented: the inspector exposes identity/version for verification in the existing original review entry.
- Realtime editing/presence, invitations, permission grants, genuine multi-user acceptance and Windows/GPU acceptance remain outside this increment.
- No push, CI, install, release or main-branch change.

# M5 Report — ?uw=1 unified workspace hardening  [HERMIA-FE-20261024 M5-s1]

Base: 3520d679 · Branch: work/hermia-uw-m5-20261024. Only frontend/src/workspace/ was touched. No shared files changed and no patches were needed.

## Changes
- state/draftStore.ts (new): a DraftStore owned by the host (useSyncExternalStore), key helpers, useDraft, and useBeforeUnloadGuard. The guard listener is attached only while something is dirty.
- state/async.ts (new): withTimeout (read 15s / write 20s) and WorkspaceTimeoutError with honest Chinese messages. LatestGate is an AbortController with last-wins behaviour.
- panels/novelPreviewPanels.tsx: chapter reads and rename writes now have timeouts, and there is a 'timeout' error class. Chapter title drafts live in the host store. A save clears the draft only if it was not edited during the save. Save is gated by LatestGate.
- panels/canvasInspector.tsx: node drafts live in the host store and are no longer wiped when the pick changes. A save clears the draft only if it is unchanged.
- UnifiedWorkspacePreview.tsx: on project switch, tracker.update({projectId}) runs in a layout effect. anyDirty() feeds the switch guard and beforeunload.
- state/m5s1.test.tsx (new): 14 tests for (a)–(d), using deferred promises that resolve out of order.

## Verification (Node 22.14)
- Targeted vitest (workspace, workbench, rebuild, taskcenter): 57 files and 477 tests passed.
- tsc: 6 errors, the same 6 as the baseline.

## Mutation check (src/workspace/state)
Killed: M2 (chapter inspector local store), M4 (no preventDefault), M5 (beforeunload always on), M6 (save drops newer draft), M7 (no write timeout), M8 (no read timeout), M9 (guard ignores store), M11 (LatestGate no abort).
Survived:
- **M1 (host tracker.update removed): SURVIVED in M5-s1. The earlier "M1 killed" claim was WRONG.** That run overlapped with other mutations that were still applied, and the box was under heavy load. The only stale test exercised LifecycleTracker/ActionRegistry directly, never through the host. Vera reproduced the survival. It is fixed in M5-s1fix below.
- M3 (node inspector local store): in the current flows, redock (keyed portal) and main-tab switch do not remount the node inspector, so the host store and a local store behave the same. This is defence in depth only.
- M10 (withTimeout late-result flag): an equivalent mutant, since a settled promise ignores later resolves. A late-success test was added anyway.

## Known / out of scope
- The TaskCenter alert shows the raw code 「原记录或功能当前不可用。 · STUDIO_REQUEST_FAILED」. This was already there before M5 and was not changed.
- Early mutation runs were unreliable: the box was under heavy load and runs overlapped. All files were restored from a clean copy and checked with diff before the final run.

## M5-s1fix (after Vera's review)  [HERMIA-FE-20261024 M5-s1fix]
- MUST: added a host-level test through UnifiedWorkspacePreview. It starts 刷新章节列表 in n1 (the GET is held), switches to n2, then resolves n1's request late. The test asserts no 已刷新, no 刷新失败, no STALE data, and that the selector stays n2. The outline now treats a `stale` result as dropped (empty message). Previously it showed 「刷新失败，请重试」, which wrongly claimed a failure.
- LOW: useBeforeUnloadGuard re-checks dirtiness after every host render and on every store change. The listener is now removed after a discard or a save, where before it stayed attached with a body that did nothing. A test counts the beforeunload add/remove calls.
- LOW: a test covers the node-save conditional clear. It types 'XY' during the save (from inside the localStorage write), and the newer draft is kept and still dirty.
- LOW: on a read error or timeout with no data, the rail (「还没有章节。」) is hidden. A test checks this.
- Mutations (src/workspace/state, 18 tests), all KILLED: M1 host tracker.update removed (1 fail); V2b listener never re-evaluated (1); V4 node save clears unconditionally (1); V7 rail shown on read error (1); V8 stale refresh treated as a result (1). After the run, the files were checked with diff against a clean copy: CLEAN.
- M3 and M10 are still accepted as equivalent (Vera agreed).
- Targeted vitest: 57 files and 481 tests passed. tsc: 6 errors, the same as the baseline.

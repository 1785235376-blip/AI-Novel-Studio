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
Killed: M1 (host tracker.update), M2 (chapter inspector local store), M4 (no preventDefault), M5 (beforeunload always on), M6 (save drops newer draft), M7 (no write timeout), M8 (no read timeout), M9 (guard ignores store), M11 (LatestGate no abort).
Survived:
- M3 (node inspector local store): in the current flows, redock (keyed portal) and main-tab switch do not remount the node inspector, so the host store and a local store behave the same. This is defence in depth only.
- M10 (withTimeout late-result flag): an equivalent mutant, since a settled promise ignores later resolves. A late-success test was added anyway.

## Known / out of scope
- The TaskCenter alert shows the raw code 「原记录或功能当前不可用。 · STUDIO_REQUEST_FAILED」. This was already there before M5 and was not changed.
- Early mutation runs were unreliable: the box was under heavy load and runs overlapped. All files were restored from a clean copy and checked with diff before the final run.

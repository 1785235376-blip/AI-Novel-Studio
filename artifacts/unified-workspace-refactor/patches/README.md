# patches — [HERMIA-FE-20261023 M1]
0001-wire-docklayout-preview.patch — base 6ba25ad7a47ed7677c32483b5234b656a3c0c2ed (App.tsx identical at M1 commit 5aa20a4a75b28203702f8fac4056eed545e5ea4e). NOT applied.
Adds opt-in `?uw=1` preview: App() returns UnifiedWorkspacePreview, otherwise renders unchanged LegacyApp (renamed body). New file frontend/src/workspace/UnifiedWorkspacePreview.tsx.
Verified: `git apply --check` OK. Not verified: tsc/tests/browser after applying.

## Patch index [HERMIA-FE-20261024 M6]
Shared-file edits were committed on this branch and delivered here as patches for their owners. "Lines present" counts how many of the patch's added lines still appear verbatim at M6 HEAD; later slices changed the rest.

| patch | files | applied in branch | lines present at M6 HEAD | note |
|---|---|---|---|---|
| 0001-wire-docklayout-preview.patch | App.tsx, workspace/UnifiedWorkspacePreview.tsx | YES, e5524578 (M1-s2) | App.tsx 6/6, UWP 11/19 | the "NOT applied" line above is from M1 and is out of date |
| m2s1fix-shared-nonentry.patch | rebuild/canvas/DualCanvas.tsx, taskcenter/useTaskCenter.ts, workbench/CommandSearch.tsx | YES, 98a9dead | 3/6, 10/10, 5/5 | DualCanvas later changed in 73ac909c |
| m3s1-shared-nonentry.patch | rebuild/canvas/RebuildCanvas.tsx, UWP, panels/studioPreviewPanels.tsx | YES, 2abedfb3 | 6/8, 20/33, 9/11 | superseded in part by M3-s1fix/fix2 and the merge |
| m3s1fix-shared-nonentry.patch | rebuild/canvas/RebuildCanvas.tsx | YES, 310840ef | 6/18 | superseded in part by M3-s1fix2 |
| m3s1fix2-shared-nonentry.patch | rebuild/canvas/RebuildCanvas.tsx | YES, edf7576e | 28/28 (`git apply -R --check` OK) | current |
| m4-s1-commandsearch-initial-focus.patch | workbench/CommandSearch.tsx | YES, ae916e14 (M4-s1fix; only the comment tag differs, per Vera) | 4/5 | |
| m6-taskcenter-problem-text.patch | taskcenter/TaskList.tsx, ReviewInbox.tsx, TaskCenter.test.tsx, problemText.ts (new), problemText.m6.test.tsx (new) | YES, c3939f22 + M6-fix (regenerated as `git diff e2c9d292 -- frontend/src/taskcenter`) | 2/2, 2/2, 20/20, 10/10, 17/17 | TaskCenter owner to review |

None of these patches has been pushed or sent anywhere.

[HERMIA-FE-20261024 M6-fix] The line counts were recomputed. Method: count every non-empty added line in the patch, and treat it as present if it matches a whole line of the file at HEAD exactly. The M6 counts were partly wrong because they used substring matching and dropped short lines.

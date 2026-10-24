# FILE_OWNERSHIP — [HERMIA-FE-20261023 M1]

> [HERMIA-FE-20261023 M1] Branch `work/hermia-unified-workspace-20261023` · base 6ba25ad7a47ed7677c32483b5234b656a3c0c2ed (tree 4193b3c22c49647dfc6e52241b5ff459f0064654) · M1 code commit 5aa20a4a75b28203702f8fac4056eed545e5ea4e (tree 32562dbfb206b6b5094c27ea78c665d7bbd8762b). Model: cannot be verified from inside the bot.

| path | owner | M1 action |
|---|---|---|
| frontend/src/workspace/layout/** | Hermia (new) | created |
| docs/architecture/unified-workspace-contract.md | Hermia (new) | created |
| artifacts/unified-workspace-refactor/** | Hermia (new) | created |
| frontend/src/App.tsx | protected by brief | NOT modified; proposed diff in patches/ |
| frontend/src/ui/AppShell.tsx | Design System Owner (protected_ui_surfaces.md) | NOT modified |
| IndependentStudioWorkspace.tsx, SDK entry, business controllers, shared routes, global task scheduler | protected by brief | NOT modified |
| frontend/src/workbench/** | existing | NOT modified (read/reused types & keys only) |
| frontend/package-lock.json (untracked) | unknown | untouched |

## Touched through M6 [HERMIA-FE-20261024 M6]
| path | owner | action | delivery |
|---|---|---|---|
| frontend/src/workspace/** | Hermia (new) | created/edited M1–M6 | direct |
| frontend/src/App.tsx | protected (entry) | ?uw=1 opt-in wiring only | patches/0001 (applied e5524578) |
| frontend/src/rebuild/canvas/{DualCanvas,RebuildCanvas}.tsx | shared | M2-s1fix, M3-s1, M3-s1fix, M3-s1fix2 | patches/m2s1fix-, m3s1-, m3s1fix-, m3s1fix2- |
| frontend/src/workbench/CommandSearch.tsx | shared | M2-s1fix, M4-s1fix | patches/m2s1fix-, m4-s1-commandsearch-initial-focus |
| frontend/src/taskcenter/useTaskCenter.ts | shared | M2-s1fix | patches/m2s1fix- |
| frontend/src/taskcenter/{TaskList,ReviewInbox,TaskCenter.test}.tsx, problemText.ts, problemText.m6.test.tsx | shared | M6 human error text | patches/m6-taskcenter-problem-text.patch |
| artifacts/unified-workspace-refactor/** | Hermia + Vera (INDEPENDENT_REVIEW) | reports | direct |
| frontend/package-lock.json (untracked) | unknown | untouched | — |

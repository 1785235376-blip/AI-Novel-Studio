# Integration review note for Vera — branch work/hermia-unified-loop-20261025 @ b5241905
Merges (normal, no rebase): U2 c50a8d94 (ff), U3 99a522aa → 437f7da6, U4 a0a56101 → 1f6ab40e. Wiring commit b5241905.
Please look at:
1. UnifiedWorkspacePreview.tsx (shared entry): CanvasSelectionLayer around both canvases, ContextNavBar, registerNavActions, task click → openTask, results/history via panelDefinitions, purge effect. The U3 patch hunk was applied by hand because of an import conflict.
2. integration/useUnifiedLoop.ts: u4 deps come from the real production/canvasViews clients plus the tasks.lease; no second lease. providers() is a single GET, only after a job is selected. Nothing is executed, enqueued or adopted automatically.
3. panels/TasksPanelLive.tsx: onDetail/detailExtra props; the read-once guard is now per feed (bug found, see GATE_INT.md).
4. state/projectPurge.ts plus test: a project gone from the list has only its own viewprefs/layout keys purged.
5. Known limit: DEFAULT_LAYOUT_SHORTCUTS is not derived from the registry (import cycle registry→layoutActions). VIEW shortcuts are derived.
6. Compare mode shows creative then execution; there is no real split.
Not done in this slice: M5 real-browser acceptance, audio second media, ACCEPTANCE_MATRIX/delivery package.

## [HERMIA-FE-20261025 U1fix] view preferences — known dependency (P2 docs)
- The viewprefs key is `poemseed.workspace.viewprefs.v1::<actor>::<project>::<workspace/storyline/branch>`. There is no incarnation/epoch in it.
  A project (or storyline/branch) that is deleted and then recreated **with the same id** would inherit the old views/viewports.
  This relies on the server assigning a NEW id on recreate (current backend behaviour); purge on disappearance (projectPurge.ts) is a best-effort cleanup only. If the server ever reuses ids, an incarnation field must be added to the scope.
- ?uw=1 now runs the existing collaboration bootstrap (state/identityBootstrap.tsx, same query/endpoint as LegacyApp); identity is never invented. Without a session token / collaboration scope the preview stays in "仅本次会话" mode.
- One adapter per scope serves viewports and worksets; writes are read-modify-write on the latest stored doc (no lost update between consumers/tabs on the same key).
- A collaboration scope belonging to another project → session mode ('scope-mismatch'), never mixed in.
- Open: resetAll (clear this project's saved views) is not wired to the UI yet.

## [HERMIA-FE-20261025 M5-fix] Vera P2 follow-ups (after 575501b9)
1. Legacy `TasksPanel` (studioPreviewPanels.tsx, unmounted) no longer builds a fabricated `uw-preview:<id>` identity or reads with an empty token; it states "未接通". `u3.repro.test.tsx` flipped from `it.fails` to `it` with identical assertions (mock/jsdom).
2. axe `landmark-unique` on `#uw-panel-tasks`: the inner `<section aria-label="任务">` in TasksPanelLive duplicated the dock region name; now a plain `<div>`. Repro (real browser + local axe-core): logs/m5-repro-axe-before.log FAIL → m5-repro-axe-after.log PASS. Remaining axe findings `color-contrast` (rail) and `aria-required-children` (章节 list empty under mock) predate this work and are recorded, not fixed.
3. Purge cold-start gap — **部分实现, not handled**: `projectPurge` only diffs the project lists seen within one session. If a project is deleted while the page is closed, its owner's viewprefs/layout keys stay in localStorage after a cold open. Not "fixed" by diffing local keys against the first list, because a paged/partial or failed list would delete keys of still-existing projects; a correct fix needs an authoritative "deleted projects" signal from the backend (out of scope: no new backend state). Impact: stale local UI prefs only (no server data, no other user's keys).

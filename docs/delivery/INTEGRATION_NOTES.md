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

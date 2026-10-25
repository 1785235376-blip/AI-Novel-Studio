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

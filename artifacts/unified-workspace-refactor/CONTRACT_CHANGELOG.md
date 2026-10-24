# CONTRACT_CHANGELOG — [HERMIA-FE-20261023 M1]

> [HERMIA-FE-20261023 M1] Branch `work/hermia-unified-workspace-20261023` · base 6ba25ad7a47ed7677c32483b5234b656a3c0c2ed (tree 4193b3c22c49647dfc6e52241b5ff459f0064654) · M1 code commit 5aa20a4a75b28203702f8fac4056eed545e5ea4e (tree 32562dbfb206b6b5094c27ea78c665d7bbd8762b). Model: cannot be verified from inside the bot.

## v3 (new, M1)
- Added docs/architecture/unified-workspace-contract.md.
- New storage key poemseed.workspace.layout.v3::scope (+ ::backup). Format version 3 (workbench layout was schemaVersion 2).
- Added float dock and split modes (single/split-h/split-v).
- Unknown panels now preserved (workbench v2 sanitize dropped them).
- Legacy keys read-only migration sources; nothing deleted.
- Panel API: registerDirty for dirty-close guard.
No change to workbench/layout.ts, panels.ts, actions.ts contracts.

## M1-s2 [HERMIA-FE-20261023 M1-s2] — 6930d5c9
- §2 actions: layout actions are now registered in workbench ActionRegistry (ids layout.reset, layout.reopenPanel, layout.toggleCollapse, layout.switchSplit; default Mod+Alt+0/O/C/S). actions.ts unchanged.
- New in workspace/actions: ShortcutTable (claim/release/lookup, conflict → shortcut dropped, action still registered), RESERVED_SHORTCUTS (Mod+K), registerLayoutActions, actionIdForKey.
- DockLayout: new optional props actionRegistry, shortcutTable.
- layout/model: Viewport.reserveTop? (optional); dock action index = precise insertion index; exported dropIndexFromPoint, dropAxis, mainArea.

## M1-s2fix [HERMIA-FE-20261023 M1-s2fix] — e66d2f38 (tree 6463745f597e7d426b0c6fd839a3d3e96671401c)
- DockLayout new optional props: tracker?, actionOptions? ({minBusyMs}), toolbarStart?: ReactNode (rendered first in toolbar).
- LayoutActionHost.isDefault?(): boolean — drives layout.reset available().
- layoutActions: export MIN_BUSY_MS=300, displayShortcut(s, apple), LayoutActionOptions{minBusyMs} on layoutActionDefinitions/registerLayoutActions.
- model.ts: export emptyZoneBox(zone, root, top) (main → null).
- UnifiedWorkspacePreview: SPECS exported as PREVIEW_SPECS.
- DOM: data-zone-box on left/right/bottom, .uw-zone-ghost[data-testid=zone-ghost-<z>], #uw-reset-reason[data-testid=reset-reason].
- Test expectation changes (assertions kept): DockLayout.test M1-06 and M1-08 wait 320ms for busy guard; N3 switches split to split-h first so reset is enabled; slice2.test conflict text expects 'Ctrl+Alt+S'.

## M1-s3 [HERMIA-FE-20261023 M1-s3] — 630448ec (tree 6a8e507f1d4e1af3b8d7734b8a4ed88acb4b9a0d); f144f5a3 (tree af6f80afd99b8b5ff596f09fd353d4486f8aa065)
- CommandSearch: CommandGroup adds '布局'; COMMAND_GROUP_ORDER = 写作/媒体/布局/壳·设置; commandGroupOf('layout.*') = '布局' (was 壳·设置). Option DOM no longer renders .wb-command__id; data-action-id kept. Back-compat: display only; ids, execute path, search unchanged. Tests: CommandSearch.m1s3.test.tsx. No Hermia wiring change needed.
- New panel module workspace/panels/novelPreviewPanels.tsx: NOVEL_PREVIEW_PANELS (PanelDefinition, existing workbench/panels.ts type), createPreviewPanelRegistry(), registerNovelPreviewActions(reg, qc, getNovelId), NOVEL_ACTION_IDS {rename:'novel.chapter.rename', refresh:'novel.chapters.refresh'}. novel.chapter.rename input = {chapterId, novelId, title, version} via ActionContext.input; visible only with input.
- UnifiedWorkspacePreview requires a QueryClientProvider ancestor (main.tsx already provides). Preview workbench.panels is now a real PanelRegistry. Panel ids unchanged (layout v3 storage compatible); titles 作品结构 / 章节属性.
- Affected: ?uw=1 preview only. Migration: none.

## Gate change [HERMIA-FE-20261024 M2-s1] (user decision, relayed by the parent agent 2026-10-24)
- The full-vitest gate now runs on **Node 22.14.0** (copy kept at /workspace/hr/node22, outside /tmp), **3 runs, best adjusted ≤297** (adjusted = failed − IndependentStudioIdentity failures + 8). The old Node 20 / ≤307 gate is retired.
- f3e0b496 is PASS on the gate. Vera's review is committed at 58270f6a.

## M2-s1 [HERMIA-FE-20261024 M2-s1] — 822b89ec (tree fcd2c214c41fa7b351c1166fbe80d1dcdfd5c379)
- New workspace/panels/studioPreviewPanels.tsx exports:
  - Panels: STUDIO_PREVIEW_PANELS (creative/execution local-only, tasks partial), CreativeCanvasPanel, ExecutionCanvasPanel, TasksPanel.
  - Actions: registerStudioPreviewActions(reg, table, host, minBusyMs=300), STUDIO_ACTION_IDS {canvas.sendToExecution, canvas.openExecution Mod+Alt+E, canvas.openCreative Mod+Alt+I, tasks.open Mod+Alt+T}.
- These reuse rebuild/canvas RebuildCanvas + DualCanvas.linkToExecution and taskcenter TaskCenterPanel unmodified.
- layoutActions: new id layout.showPanel. Input is a panel id. It reopens the panel if closed, brings it to the front of main, expands it and focuses it. No shortcut. Unknown id → disabled 「没有这个面板」.
- DockLayout:
  - New exports effectiveZoom() and readViewport().
  - The viewport is now innerWidth/innerHeight ÷ CSS zoom of html×body. It re-reads on resize, visualViewport resize, DPR change and html/body style/class mutation (N4).
  - New main-panel tab group [data-testid=uw-main-tabs] (aria-pressed buttons). The 切换中间面板 select is kept (N5).
- Preview: always-visible toolbar button 执行画布 [data-testid=uw-open-execution], plus a status line [data-testid=uw-studio-status].
- No shared entry files changed (App.tsx already wires ?uw=1). No new patches/.
- Affected: ?uw=1 preview + DockLayout only. Migration: none (panel ids unchanged).

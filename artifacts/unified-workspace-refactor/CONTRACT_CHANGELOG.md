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

## [HERMIA-FE-20261024 M2-s1fix] (code 98a9dead, tree fa0afbbf; Vera review append committed unchanged as 974205fc, author Vera (review))
- **300 ms guard:** fake-timer tests use the production STUDIO_MIN_BUSY_MS=300. Two triggers 100 ms apart run once (the second returns duplicate); 350 ms apart they run twice. Mutation log logs/m2s1fix-mutations.log: removing `delay(minBusyMs)` from send or from show fails, STUDIO_MIN_BUSY_MS=0 fails, delay forced to 0 fails.
- **Sent node in view:** linkToExecution (rebuild/canvas/DualCanvas.tsx, shared non-entry file, minimal edit) now writes x=LINK_X(20), y=20+(n%3)*70 instead of x:-220. That is inside the default execution viewport {40,40,1}, even at the 320×280 panel minimum. The legacy DualCanvas gets the same fix. Test: m2s1fix.test.tsx renders 7 sent nodes and asserts they are all inside 320×280; with x:-220 restored the test fails. Chrome check: node at (60,60) inside the svg at 1366/1440/1920.
- **Palette:** layout.showPanel is now on the commandSearch and shortcut surfaces with **Mod+Alt+P** (free; taken keys are Mod+Alt+0/O/C/S/E/I/T, and Mod+K is reserved). Without input it reopens the first closed panel, otherwise it brings the hindmost main tab to the front (repeating rotates through the main tabs). When there is nothing to show it is disabled with the reason 「没有可切换的面板」.
- **aria-disabled:** CommandSearch (workbench, minimal edit) sets aria-disabled="true" and title=reason on disabled options; they stay focusable, and Enter still shows 「无法执行：…」.
- **Task GET dedupe:** the cause was StrictMode (dev) running mount effects twice: the cleanup aborted the first read and the reset effect re-armed a second. useTaskCenter now defers the on-demand read by one microtask, and the effect cleanup cancels it. Result: 1 GET in jsdom StrictMode and in Chrome dev (1366/1440/1920). Reverting to HEAD fails both StrictMode tests. Note: removing only the cancel flag is an equivalent mutant (the loaded guard still dedupes).
- **Focus:** the open actions call host.focusPanel(id), so after Mod+Alt+T DOM focus is in the [data-panel-id=tasks] region (jsdom test plus Chrome: focusAfterT="tasks").
- **Tests:** workspace/panels/m2s1fix.test.tsx (10). Touched areas (workspace/taskcenter/workbench/rebuild): 454/454.
- **Gate (Node 22.14, total 11375):** failed 298/297/297, Identity failures 8/8/8, adjusted **298/297/297 → best 297 ≤297 PASS**. The only extra failure in run 1 (StudioModelCameraWorkspace.additive) is not in my area and passes 3/3 in isolation (logs/m2s1fix-isolated-rerun.log). tsc: 6 errors, same files as baseline (logs/m2s1fix-tsc.log).
- **Artifacts:** logs/m2s1fix-full-node22-{1,2,3}.json, logs/m2s1fix-browser.{mjs,json}, screenshots/m2s1fix_{1366,1440,1920}_{palette,sent_in_view,tasks_focus}.png, patches/m2s1fix-shared-nonentry.patch (the three shared non-entry edits).

## [HERMIA-FE-20261024 M2-s1fix2] + [HERMIA-FE-20261024 M3-s1] (fix2 code 73ac909c tree a77e9964; M3-s1 code 2abedfb3 tree a9f1821e; Vera M2-s1fix review committed unchanged as 1443245c, author Vera (review))
- DualCanvas: export LINK_DX=206; link position becomes x=LINK_X+floor(n/3)*LINK_DX, y=LINK_Y0+(n%3)*LINK_DY.
- RebuildCanvas: new optional props initialSelected, initialViewport, onViewport, plus the exported type CvViewport. Defaults are unchanged.
- Creative/ExecutionCanvasPanel: new optional props revision, onSelect, selectedId, viewport, onViewport. The creative key is now `novelId:revision`.
- New action uw.canvas.renameNode (no surfaces; inspector only): input {kind, scope, id, title}. It writes the local draft and reads it back. It reports error on mismatch.
- New module workspace/panels/canvasInspector.tsx (CanvasNodeInspector, renameCanvasNode, readCanvasNode).

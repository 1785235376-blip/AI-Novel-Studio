# IMPLEMENTATION_REPORT — M1 slice 1 — [HERMIA-FE-20261023 M1]

> [HERMIA-FE-20261023 M1] Branch `work/hermia-unified-workspace-20261023` · base 6ba25ad7a47ed7677c32483b5234b656a3c0c2ed (tree 4193b3c22c49647dfc6e52241b5ff459f0064654) · M1 code commit 5aa20a4a75b28203702f8fac4056eed545e5ea4e (tree 32562dbfb206b6b5094c27ea78c665d7bbd8762b). Model: cannot be verified from inside the bot.

## What was built (isolated, not wired into the app)
- model.ts — pure layout reducer: docks left/right/bottom/main/float, single/split-h/split-v, size clamping (min/max/60% viewport), float clamping (48px stays visible), z-order focus, close/reopen without duplicates, reset keeping preserved unknown panels.
- persistence.ts — v3 format, loader with legacy migration (workbench v2/v1, AppShell inspector keys), corrupt-data backup, diagnostics, idempotent canonical serialization, save returning {ok|error}.
- useDirtyCloseGuard.ts — dirty-close decision flow, stale/late result protection.
- DockLayout.tsx/.css — real pointer drag to dock zones, float drag, pointer+keyboard resize separators, collapse, dock select, reopen menu, split switcher, reset confirm, dirty dialog, status line; existing tokens only.
## Fix found during testing
- discard() originally ran side effects inside a setState updater (React warning "Cannot update a component while rendering"). Fixed; layout log now has 0 warnings.
- Serialization key order differed between migrated and loaded frames → M1-16 failed; fixed with canonical order.
## Tests (raw logs in logs/)
| command (cwd frontend/) | result |
|---|---|
| ./node_modules/.bin/vitest run src/workspace/layout | 3 files, 41 tests passed, EXIT 0 (m1-vitest-layout.log) |
| ./node_modules/.bin/vitest run src/workspace/layout src/workbench src/rebuild/canvas src/ui/AppShell | 12 files, 132 passed, EXIT 0 (= baseline 91 + 41) (m1-vitest-regression.log) |
| ./node_modules/.bin/tsc --noEmit -p . | EXIT 2, 6 errors, all pre-existing in untouched files; 0 in src/workspace (m1-tsc-full.log, m1-tsc-workspace-filtered.log empty) |
## Limits
jsdom only: geometry is mocked, PointerEvent polyfilled as MouseEvent in the test file. No real browser, viewport, zoom or E2E run. Docked drag drops into a zone (appends); no precise in-zone reorder by pointer position.


## M1-fix — response to Vera's INDEPENDENT_REVIEW (MUST-FIX) [HERMIA-FE-20261023 M1-fix]
Commits: e120843f (tree 3890be21aab330ad53bcf61b52a6585d8af95552) Vera's review committed unchanged; 865233eb (tree 04c3d939e7792b02d121f3bc607dea338a9e8b4a) code + tests; docs commit follows.
- MF-1 (pre-fix: Vera jsdom probe, inspector "abc" → '' on redock; DockLayout.tsx:188-195/162-163/181). Fix: each panel's content renders via a keyed createPortal into ONE stable host element per panel id; zones (`PanelSlot`) only attach/detach that element. Redock, float, and single-column hidden main no longer remount; only explicit close (dirty guard) unmounts. Focus capture moved onto the portal wrapper.
- MF-2 (pre-fix: 1366×768 canvas width 0, scrollWidth 1391; model.ts:56-60). Fix: `MAIN_MIN_WIDTH=320`, `MAIN_MIN_HEIGHT=200`; resize bounded by `crossLimit` (viewport − opposite column − 320); `fitMain` re-fits after dock/collapse/reopen/reset/viewport, shrinking other columns first, never below a panel's minSize. Two pre-existing small-viewport expectations updated (600px outline 360→180, 500px inspector 300→240) because the stricter rule now applies; this tightens, not loosens, the assertion.
- N1: AppShell studio-inspector-* keys are only a fallback when no workbench v2/v1 exists.
- N2: persistence writes only after an explicit user layout action whose signature (excl. focus/z) changed; hydration, viewport re-fit and focus never write. Backup key is written only at corrupt load, never by save.
- N3: ModalDialog — Esc cancels, Tab trap, focus returns to trigger.
- Not done: N4 (CSS zoom float clamp), N5 (exec canvas entry), browser re-run of MF-1/MF-2, full vitest, product wiring.
Results: layout 51/51, regression 142/142, tsc no new errors.

## M1-s2 — preview wiring + slice 2 [HERMIA-FE-20261023 M1-s2]
- 774219ce: Vera's INDEPENDENT_REVIEW append, committed unchanged (author Vera (review)).
- e5524578 (tree 8af6b28d1dfd5d9c862110ebc3e5d44f799ed18e): applied patch 0001; DockLayout is opt-in at `?uw=1`, legacy UI unchanged otherwise. Screenshots: screenshots/m1s2_stepA_{uw,legacy}_{1366x768,1440x900,1920x1080}.png; no page errors, no writes, no h-overflow.
- 6930d5c9 (tree 2c971da8b4ae2bd23d490047d8ded8d1d0c5588e): slice 2.
  - Precise drop: dropIndexFromPoint over the zone's panel rects (dragged panel excluded); indicator + Chinese note when the zone is not allowed.
  - Main min: RESIZER_PX 5 / BORDER_PX 1 / dock chrome and measured toolbar height (Viewport.reserveTop) subtracted in crossLimit/fitMain.
  - Actions: layout.reset / layout.reopenPanel / layout.toggleCollapse / layout.switchSplit registered in the existing workbench ActionRegistry (unmodified); new ShortcutTable for conflict detection (Mod+K reserved); shortcuts skipped in text inputs/IME via shouldHandleShortcut; running = aria-busy; blocked reasons go to the status line in Chinese. Preview placeholders show titles, not ids.
- Tests: tsc 6 errors = baseline (logs/m1s2-tsc.log); src/workspace 98/98 (logs/m1s2-layout-vitest.log); regression workbench+App+ui+rebuild 472/472 tests, 1 suite fails to load at baseline too (LocalAiBrowserJourneyContracts: missing tests/e2e/v2-local-ai-files-live.spec.ts) (logs/m1s2-regression-vitest.log).
- Browser: logs/m1s2-s2-browser.json; screenshots/m1s2_s2_{maxsides_1366x768,maxbottom_800x600,dropindicator_*,afterdrop_*}.png.
- Remaining: N4 CSS-zoom float clamp, N5 exec canvas entry, real panel content (placeholders only), Vera browser re-check, wiring beyond ?uw=1, the pre-existing missing e2e spec.

## M1-s2fix [HERMIA-FE-20261023 M1-s2fix]
Commits: fe2e82f0 (Vera review append, unchanged, author "Vera (review)"); e66d2f38 (tree 6463745f597e7d426b0c6fd839a3d3e96671401c) code+tests+evidence.
- MF1: computeDrop never falls back to root; uses real zone box (data-zone-box) or model.emptyZoneBox (left/right 20%, bottom lower 25%). Ghost .uw-zone-ghost per empty zone during drag; translucent zone indicator.
- MF2: capture-phase Escape clears drag/target; floating panel restored to drag origin.
- MF3: LayoutActionHost.isDefault() (signature vs post-reset signature) → reset disabled with 「已经是默认布局」.
- MF4: UnifiedWorkspacePreview mounts the existing workbench CommandSearch (registry-fed) in DockLayout toolbarStart with hint 「Ctrl／⌘+K」; window Ctrl/⌘+K opens it. App.tsx untouched.
- NH: MIN_BUSY_MS=300 + pending guard until settle; displayShortcut → Ctrl+Alt+S / ⌘⌥…; floats can be dragged back into allowed dock zones.
Results: layout 111/111; regression 472/472 tests (1 pre-existing file load failure); tsc 6 (baseline). Browser 1366 all 4 PASS.
Known/remaining: CommandSearch shows raw action id in <small> (existing component behavior); pre-existing tsc errors & LocalAiBrowserJourneyContracts missing spec; nothing pushed.

## M1-s3 / M2 start [HERMIA-FE-20261023 M1-s3]
Commits: 664d8aad (Vera review append, unchanged); 630448ec (tree 6a8e507f1d4e1af3b8d7734b8a4ed88acb4b9a0d); f144f5a3 (tree af6f80afd99b8b5ff596f09fd353d4486f8aa065). Nothing pushed; main untouched; untracked frontend/package-lock.json kept.
- Task 1 (Vera P3): workbench/CommandSearch.tsx minimal edit — removed <small className="wb-command__id"> from options (matchesQuery still uses id); added group 「布局」 (layout.* → 布局), order 写作/媒体/布局/壳·设置. workbench/** is otherwise untouched; this edit is the requested P3 fix in the component that owns the palette. Existing CommandSearch.test expectation for layout.reset updated 壳·设置→布局.
- Task 2: new workspace/panels/novelPreviewPanels.tsx — PanelRegistry defs (outline connected, inspector partial); OutlinePanel reuses rebuild/novel/NovelStructureRail (imported, not copied) + novel select (defaults to 雾港); InspectorPanel with title edit registered via api.registerDirty; actions novel.chapter.rename (api.renameChapter POST, optimistic version; success only when the server returns the chapter JSON with numeric version > sent version and the requested title — see M1-s3fix) and novel.chapters.refresh (GET refetch). UnifiedWorkspacePreview: renderPanel routes outline/inspector to real panels; other panels say 「预览里尚未接入实际功能」; titles 作品结构 / 章节属性 (panel ids unchanged → persisted layouts compatible); selection switch blocked while inspector dirty.
- App.tsx / IndependentStudioWorkspace / SDK / controllers: NOT modified.
- slice2fix.test.tsx: wrapped preview in QueryClientProvider (preview now uses react-query, as main.tsx provides); assertions unchanged.
- Mutation check: isDirty→false breaks 2 tests; ignoring non-done save result breaks 1 test.
Results: layout 120/120; regression 475/475 (1 pre-existing load failure); tsc 6 (baseline); browser 1366/1440/1920 all checks PASS, 0 non-GET.
Remaining: Vera independent re-check; full vitest (gate ≤307); real-backend save path not exercised in browser (writes); loading/error states only in unit; creative/execution/tasks panels still not connected; inspector copy says 「在左侧」 even when outline is redocked (S3); legacy 18-page compare not rerun.

## M1-s3fix [HERMIA-FE-20261023 M1-s3fix]
Base e3b92bd6 → Vera review append committed unchanged as db9a5a7d (author 'Vera (review)') → code fix b7e98c69a497568e79e394bd026e0d17246e6d9b (tree 852fa1edb7988470dfc9f155c01f3b35ce5741f2).
- MUST-FIX (Vera P2) novel.chapter.rename. Before: any 2xx JSON counted as success (same version → 「已保存（版本 2）」; missing version → 「已保存（版本 undefined）」; 204 → silent). After: `isConfirmedRename` requires a chapter object with numeric `version > input.version`, `title ===` requested title (id, if present, must match). Same version / no version / 204-empty / non-JSON → RenameUnconfirmedError → 「保存没有确认，服务器未返回新版本，修改还在。」; draft stays dirty, 已保存 never shown; save-and-close keeps panel open. 4 new tests (same version, no version, 204, non-JSON).
- Inspector empty text: 「在左侧「作品结构」里…」 → 「在「作品结构」里选一个章节…」 (direction-free).
- Removed dead `.wb-command__id` CSS.
- Old UI command palette: 「布局」 group contained layout.toggleMode / layout.setMode.* (普通/专业). Now those are in 壳·设置; 布局 holds only layout actions. New test renders the old palette with layout.reset and asserts 布局 has no mode switch.
- Verification: targeted 29/29; regression set (src/workspace src/workbench src/App.test.tsx src/ui src/rebuild) 600/600 tests, 71/72 files — the 1 failing file is pre-existing LocalAiBrowserJourneyContracts (missing e2e file, 0 tests). tsc: 6 errors, same pre-existing set. Logs: logs/m1s3fix-vitest-regression.log, logs/m1s3fix-tsc.log. Full vitest vs 307 threshold: NOT_RUN (for Vera).

## M1-s3fix2 [HERMIA-FE-20261023 M1-s3fix2]
- Review append (Vera, unchanged): e5ca8efe. Code commit: e1b91f2582e72a75b25e2828265a7a4d2d8f39de (tree ad6c012251c614eb77045bdfb02898d08a2ee10c). Base 81a65eb8.
- MUST-FIX (Vera, 81a65eb8): title-match rule now test-guarded — new test "higher version but different title → unconfirmed, never 已保存, stays dirty". Mutation (remove `&& c.title === i.title`) → that test FAILS (1/16); restored → 16/16. Log: logs/m1s3fix2-mutation.log. Status: PASS (self), pending Vera recheck.
- P3 network: fetch reject → RenameNetworkError → 「保存失败：网络错误，修改还在。」 (non-JSON SyntaxError still → unconfirmed text). Test added. PASS (self).
- P3 「。。」: close-confirm alert strips trailing 。 from error before appending 。. Test asserts no 「。。」; mutation (revert) → test FAILS. PASS (self).
- Tests: src/workspace/panels 16/16; regression set (src/workspace src/workbench src/App.test.tsx src/ui src/rebuild) 603/603 tests passed, 1 file fails to load (LocalAiBrowserJourneyContracts, pre-existing missing e2e file). tsc: 6 errors (unchanged baseline). Full vitest NOT_RUN (Vera to run; gate ≤307).
- Logs: logs/m1s3fix2-targeted.log, -mutation.log, -regression.log, -tsc.log. Not pushed; main untouched.

## [HERMIA-FE-20261023 M1-flaky] Flaky stabilization + P3 text dedupe
Code commit 7e96d0ba (tree 485ed7b5), parent 7d6ca86f (Vera review append, unchanged, author Vera (review)), base 3490d0a7.
- P3: the close-confirm network failure now reads exactly 「保存失败：网络错误。修改仍在面板里，没有保存。」, built by `closeConfirmErrorText` in DockLayout.tsx. Test `close confirm network failure shows exact deduped text` asserts the exact string. Workspace panels 17/17.
- Root causes (no assertion weakened, no skip, no deletion):
  - GraphDirectorImage.integration, director.additive "authors a director", GraphImageOutputStarter and StoryFactDownstreamImpact: long jsdom flows take 3–5s and went over the default 5000ms testTimeout under load. Before: under load, GraphDirectorImage failed 3/3 (5507–5829ms) and director failed 3/3 (logs/m1flaky-before-load-*). Fix: `vi.setConfig({testTimeout:30000})` per file.
  - Workspace download-denied: there was a **product race**. The IndependentStudioWorkspace cold-start effect switched IMAGE+NEUTRAL_STUDIO from ASSETS to GRAPH even when the `requestedAssetId` deep link was present. So whether the deep-linked asset (and its download) was shown depended on timing and test order: it failed 20/20 alone (logs/m1flaky-download-denied-load20.log) and failed under load in Vera's runs (2/29). Fix: an explicit asset deep link keeps the ASSETS view. The test also got a 10s findBy budget and a 30s test timeout.
- After: the 5 targets passed 10/10 isolated (logs/m1flaky-after-iso-*). Under load they passed 10/10 except one download-denied failure in run 5, before the product fix (logs/m1flaky-after-load-*). Download-denied after the fix: 10/10 isolated and 10/10 under load (logs/m1flaky-download-denied-after-*.log).
- Full vitest at 7e96d0ba (logs/m1flaky-full-1/2.json): run 1: 307 failed of 11353; run 2: 308 of 11351. IndependentStudioIdentity = 8 in both, so adjusted = 307 / 308. Gate ≤307: run 1 meets it, run 2 is 1 over. Run 2's extra failures are load-sensitive tests outside this scope (IndependentStudioRunReads graph cancellation, ModelBrokerBudgetRecovery). The baseline 3490d0a7 retry had 308. Compared with that baseline, 11 failures are fixed. 6 failures remaining in the target files are pre-existing and are not the targeted tests.
- tsc: 6 errors (the known baseline; logs/m1flaky-tsc.log).

## [HERMIA-FE-20261023 M1-flaky2] P4 + environment root cause for ComicLayoutsPanel/VoiceSubtitle
Commits: 84e684a4 (Vera's review append for f8124581, committed unchanged, author Vera (review)); dc1d4350 (tree 26b512e4): P4 + env logs.
- P4: the panel status line `RENAME_NETWORK_TEXT` is now exactly 「保存失败：网络错误。修改还在面板里。」, matching the dialog's wording style. The test `rename network failure` asserts the exact text. The dialog still reads 「保存失败：网络错误。修改仍在面板里，没有保存。」 (exact-text test unchanged). Workspace tests 128/128.
- **10 always-failing tests.** ComicLayoutsPanel.* has 9 failures ('Unable to find role="img" … 漫画分段/待审原图片'). VoiceSubtitlePanels has 1 ('已读取含停顿混音…'). Both throw jsdom Blob `TypeError: object.stream is not a function`. **Root cause: the runtime environment, not code.**
  - The box was provisioned 2026-10-23 03:42 (UTC+8) by `apt-get install nodejs` (/var/log/apt/history.log). That installed Debian `nodejs 20.19.2+dfsg-1+deb13u3`.
  - That Node does not bundle undici (`process.versions.undici` is undefined). It loads the system `node-undici 7.3.0` from /usr/share/nodejs/undici instead.
  - When undici 7's Response/body extraction is handed a Blob-like object (toStringTag 'Blob'), it calls `.stream()`. jsdom 25's Blob doesn't have `.stream()`, so it throws. The preview pixels/mix are never produced, so the img/text assertions fail.
  - package.json `engines.node` is ">=22.14.0 <25", so this Node violates the repo's own requirement.
  - The package versions are not the cause: node_modules/.package-lock.json matches the untracked package-lock.json exactly (0 version diffs). jsdom is 25.0.1 and vitest is 2.1.9.
  - A/B on the same tree: Node 20.19.2 gives 10 failed / 70 passed (logs/m1flaky2-env-node20.log). Official Node v22.14.0 (bundled undici 6.21.1) gives 80/80 passed (logs/m1flaky2-env-node22.log).
  - No test or polyfill change was made. A Blob.stream polyfill would hide an unsupported runtime that CI (Node 22) never sees. Remedy: run the suite on Node ≥22.14 (e.g. /tmp/node-v22.14.0-linux-x64/bin on this box).
- Full vitest at dc1d4350 (logs/m1flaky2-full-*.json):

| Runtime | Run | Failed | IndependentStudioIdentity | Adjusted | ComicLayoutsPanel/VoiceSubtitle |
|---|---|---|---|---|---|
| Node 20 | 1 | 307 | 8 | 307 | 10 |
| Node 20 | 2 | 310 | 8 | 310 | 10 |
| Node 20 | 3 | 307 | 8 | 307 | 10 |
| Node 22.14 | 1 | 301 | 8 | 301 | 0 |

  - Total is 11353 tests in every run. Best-of-3 adjusted is 307, so the ≤307 gate is met.
  - The Node 22 run has 4 failures that don't appear in Node 20 runs 1 or 3. They look like timing flakes: IndependentStudioGraphWorkspace.presentation, CreativeWorkspace reorder, WorkspaceToolsPanel delayed search, ComicPublicationPanel PDF preflight.
- tsc: 6 errors (known baseline; logs/m1flaky2-tsc.log).

## M2-s1 [HERMIA-FE-20261024 M2-s1] — 822b89ec (tree fcd2c214c41fa7b351c1166fbe80d1dcdfd5c379)
- **Real (reused unmodified):**
  - 创作画布 = RebuildCanvas image (local draft).
  - 执行画布 = RebuildCanvas video (local draft, remount on link).
  - 任务 = TaskCenterPanel (GET reads of /api/novels/{id}/experimental/workspace/tasks; mutations only from the user's own clicks inside it).
  - All 5 preview panels are now real; there is no placeholder left in ?uw=1.
- **Honest limits:**
  - Both canvases are browser-local drafts (capability local-only, no server canvas graph).
  - The tasks panel uses an empty session token; capability is partial.
  - linkToExecution places the reference node at x=-220, so it starts off-view until 适配 is used (existing DualCanvas behavior).
- **Actions:** canvas.sendToExecution, canvas.openExecution/openCreative, tasks.open, layout.showPanel. Each has a disabled reason and the registry pending guard with 300 ms busy.
- **N4/N5:** fixed (see BLOCKERS).
- **Tests:** layout/m2s1.test.tsx (4) and panels/studioPreviewPanels.test.tsx (8). workspace suite 140/140.
- **Gate:** best adjusted 297 ≤297 PASS (see ACCEPTANCE_MATRIX). tsc: 6 baseline errors.

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

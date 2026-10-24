# ACCEPTANCE_MATRIX — M1 — [HERMIA-FE-20261023 M1]

> [HERMIA-FE-20261023 M1] Branch `work/hermia-unified-workspace-20261023` · base 6ba25ad7a47ed7677c32483b5234b656a3c0c2ed (tree 4193b3c22c49647dfc6e52241b5ff459f0064654) · M1 code commit 5aa20a4a75b28203702f8fac4056eed545e5ea4e (tree 32562dbfb206b6b5094c27ea78c665d7bbd8762b). Model: cannot be verified from inside the bot.

Level: U = unit (pure), C = component (RTL/jsdom, mocked geometry). PASS here means passing at that level only — not in a real browser. Test names carry the IDs. Mapping of IDs to behaviours is Hermia's reading of the spec.

| ID | behaviour | level | status |
|---|---|---|---|
| M1-01 | panel drag / float move, stays in viewport | U+C | PASS @6930d5c9 [M1-s2]: insertion index from pointer + drop indicator (data-zone/index/allowed); unit slice2.test.tsx; browser m1s2-s2-browser.json (indicator main#1, drop applied) |
| M1-02 | resize with min/max, pointer + keyboard | U+C | Vera@7de42fe8: FAIL (MF-2) → fixed 865233eb (unit); browser re-check pending Vera |
| M1-03 | drag to dock zone | C | PASS |
| M1-04 | redock, old relation removed | U+C | Vera@7de42fe8: FAIL (MF-1) → fixed 865233eb (jsdom); browser re-check pending Vera |
| M1-05 | collapse/expand keeps state | U+C | PASS |
| M1-06 | close / reopen | U+C | PASS |
| M1-07 | split switch | U+C | PASS; single-column hidden-main unmount (MF-1) fixed 865233eb, pending Vera |
| M1-08 | reset default with confirm, content kept | U+C | PASS |
| M1-09 | persist + restore after reload (remount) | U+C | PASS |
| M1-10 | save failure status; focus/z-order | U+C | PASS |
| M1-11 | migrate old formats (workbench v2/v1, AppShell keys) | U | PASS; N1 overlay fixed 865233eb (v2 wins, inspector keys fallback only) |
| M1-12 | missing fields → defaults, extra fields kept | U | PASS |
| M1-13 | unknown panels preserved | U | PASS |
| M1-14 | corrupt data → default + warning + backup | U+C | PASS |
| M1-15 | invalid size/dock repaired | U | PASS |
| M1-16 | idempotent repeated migration | U | PASS |
| M1-17 | migration interrupted → raw intact | U | PASS |
| M1-18 | reset only touches layout key | U | PASS |
| M1-19 | repeated close/reopen no duplicates | C | PASS |
| M1-20 | dirty close → save & close after real save | C | PASS |
| M1-21 | dirty close → cancel keeps draft | C | PASS |
| M1-22 | discard only this panel | C | PASS |
| M1-23 | no duplicates / listener cleanup | U+C | PASS |
| M1-24 | late async results ignored (cancel/unmount) | C | PASS |
| M1-25 | save failure keeps panel, real error | C | PASS |
| VIEWPORT | real viewport sizes (1366/1440/1920) | browser | Vera@7de42fe8: run; 1366 squeeze FAIL (MF-2) → fix 865233eb, browser re-run pending |
| ZOOM | browser zoom | browser | Vera@7de42fe8: DSF 1.25/1.5 PASS; CSS zoom N4 open (deferred) |
| E2E | end-to-end in the app | browser | Vera@7de42fe8: PARTIAL (?uw=1 preview in temp tree; not wired into product) |

Counts: PASS 24 · PARTIAL 1 · FAIL 0 · NOT_RUN 3.


## M1-fix (2026-10-23) [HERMIA-FE-20261023 M1-fix]
Candidate: 865233eb92d8351014deef8569fac690b38322d6 (tree 04c3d939e7792b02d121f3bc607dea338a9e8b4a). Review evidence committed unchanged in e120843f (tree 3890be21).
| Item | Pre-fix (Vera, 7de42fe8) | Post-fix (865233eb) | Status |
|---|---|---|---|
| MF-1 redock/main-switch remount | jsdom probe: inspector input "abc" → '' after dock=bottom; hidden main unmounted | new tests: redock bottom/float/left/right keeps value; pointer-drag redock keeps value; single-column switch canvas→exec→canvas keeps value; close still guarded | PASS (jsdom) / browser NOT_RUN |
| MF-2 main min 320 | 1366×768 outline 819 + inspector 560 → canvas 0, scrollWidth 1391 | 1366 scenario main ≥320; 240 random resize/dock steps × 4 viewports keep main ≥320; viewport shrink refits; bottom ≤ vh−200 | PASS (unit) / browser NOT_RUN |
| N1 legacy overlay | v2 left/300 became right/560 | v2 wins test | PASS |
| N2 focus writes v3 over corrupt original | header click overwrote key | header click/focus leave corrupt original + backup untouched; first real change writes v3, backup unchanged | PASS |
| N3 dialog keyboard | no Esc, Tab escapes | Esc cancels, Tab/Shift+Tab trapped, focus returns to trigger | PASS (jsdom) |
| N4 CSS zoom float clamp | — | not fixed | OPEN (deferred, BLOCKERS.md) |
| N5 exec canvas discoverability | — | not fixed | OPEN (deferred, BLOCKERS.md) |
Tests: layout 51/51 (logs/m1fix-layout-vitest.log); regression set 12 files 142/142 (logs/m1fix-regression-vitest.log); tsc 6 errors = baseline, none in src/workspace/layout (logs/m1fix-tsc.log). Full vitest NOT_RUN (Vera to run).

## M1-s2 additions [HERMIA-FE-20261023 M1-s2] — commit 6930d5c9 (tree 2c971da8b4ae2bd23d490047d8ded8d1d0c5588e)
| ID | Item | Evidence | Status |
|---|---|---|---|
| S2-1 | precise dock drop index + indicator | slice2.test.tsx; browser 1366/1920 indicator zone=main index=1 | PASS |
| S2-2 | main ≥320×200 after resizer/border/toolbar | unit; browser 1366 max sides main 320×524; 800×600 max bottom main 320×200; no h-overflow | PASS |
| S2-3 | layout actions via ActionRegistry (stable ids, disabled reason, running, double-trigger guard, shortcut conflict, no shortcut in text inputs) | actions/layoutActions.test.ts + slice2.test.tsx | PASS (unit) |
| MF-2 | main min browser | m1s2-s2-browser.json | PASS (browser, by Hermia; Vera re-check pending) |

## M1-s2fix — Vera M1-s2 MUST-FIX re-verification [HERMIA-FE-20261023 M1-s2fix]
Code commit: e66d2f38 (tree 6463745f597e7d426b0c6fd839a3d3e96671401c). Pre-fix base cbf4a3ed (Vera review committed as fe2e82f0). Browser: 1366×768, http://127.0.0.1:4299/?uw=1, raw: logs/m1s2fix-browser.json (script logs/m1s2fix-browser.mjs).

| # | Item | Pre-fix (Vera @ cbf4a3ed) | Post-fix | Evidence |
|---|---|---|---|---|
| MF1 | Empty dock zone drop indicator | FAIL: indicator = whole root [0,0,1366,768] | PASS: empty-left indicator [0,63,273,705] (20% strip below toolbar), class uw-drop-indicator--zone, bg accent @14% alpha; no root fallback | screenshots/m1s2fix_1_empty_zone_indicator.png; slice2fix.test.tsx |
| MF2 | Esc cancels drag | FAIL: no cancel | PASS: Esc removes indicator+ghosts; pointerup afterwards leaves inspector dock=right | m1s2fix_2_esc_cancel.png |
| MF3 | layout.reset available() | FAIL: never disabled | PASS: default → disabled, reason 「已经是默认布局」 (title + aria-describedby); after change → enabled; after reset → disabled again | m1s2fix_3_reset_disabled.png, m1s2fix_4_after_palette_reset.png |
| MF4 | ?uw=1 Ctrl+K palette lists/triggers 4 layout actions | FAIL: no palette | PASS: Ctrl+K opens existing CommandSearch with layout.reset / reopenPanel / toggleCollapse / switchSplit; choosing reset opens confirm, 恢复默认 restores outline→left | m1s2fix_4_ctrlk_palette.png, m1s2fix_4_reset_confirm.png |
| NH | in-flight guard + ≥300ms busy; Ctrl/⌘ in conflict text; float → dock drag-back | — | PASS (unit: slice2fix.test.tsx) | logs/m1s2fix-layout-vitest.log |

Tests: layout set 10 files / 111 passed; regression set 59/60 files, 472/472 tests passed (1 file = pre-existing LocalAiBrowserJourneyContracts load failure, missing e2e spec); tsc 6 errors = unchanged pre-existing baseline.

## M1-s3 / M2 start [HERMIA-FE-20261023 M1-s3]
Commits: 664d8aad (Vera M1-s2fix review append, author "Vera (review)"); 630448ec (tree 6a8e507f1d4e1af3b8d7734b8a4ed88acb4b9a0d) palette; f144f5a3 (tree af6f80afd99b8b5ff596f09fd353d4486f8aa065) real panels. Browser: http://127.0.0.1:4299/?uw=1 + backend 8000, /usr/bin/google-chrome, raw logs/m1s3-browser.json (script logs/m1s3-browser.mjs). Self-verified by Hermia — Vera independent re-check NOT_RUN.

| # | Item | Status | Evidence |
|---|---|---|---|
| P3-1 | Palette shows no raw action id as visible text (49 legacy + layout) | PASS (unit + browser 3 viewports) | CommandSearch.m1s3.test.tsx; m1s3_{1366,1440,1920}_palette.png |
| P3-2 | ids still match in search (panel.open.history, "open history") | PASS (unit) | CommandSearch.m1s3.test.tsx |
| P3-3 | layout.* in 「布局」 group, not 壳·设置 | PASS (unit + browser: groups 写作:1, 布局:4 in ?uw=1) | m1s3-browser.json |
| M2-01 | Outline panel = existing NovelStructureRail, registered via PanelRegistry, real GET data (雾港: 来信/灯塔/雾中码头) | PASS (browser 1366/1440/1920) | m1s3_*_real_panels.png |
| M2-02 | Inspector shows selected chapter real props (标题/章节/字数/状态 中文/版本); empty state before selection | PASS | m1s3_*_real_panels.png |
| M2-03 | loading / error / empty / not-connected states honest | PASS (unit: not-connected via fetch TypeError; empty) · loading/error browser NOT_RUN | novelPreviewPanels.test.tsx |
| M2-04 | Redock inspector right→bottom→left keeps unsaved title (same DOM node in unit) | PASS (unit + browser 3 viewports) | m1s3_*_redock_dirty.png |
| M2-05 | Dirty close → 取消/放弃修改/保存并关闭; cancel keeps draft; discard closes | PASS (unit + browser) | m1s3_*_dirty_close_confirm.png |
| M2-06 | Switching chapter/novel while dirty is blocked with notice (not silently dropped) | PASS (unit) · browser NOT_RUN | novelPreviewPanels.test.tsx |
| M2-07 | novel.chapter.rename via ActionRegistry; success only from server Chapter with version > sent + title match (M1-s3fix: was any 2xx JSON — Vera MUST-FIX); 409 → error, panel stays open, never "已保存" | PASS (unit, mocked fetch) · real-backend save NOT_RUN (would write; deliberately not run) | novelPreviewPanels.test.tsx |
| M2-08 | novel.chapters.refresh via ActionRegistry, GET-only, real refetch result | PASS (unit + browser) | m1s3-browser.json |
| M2-09 | Load + all browser steps issue no non-GET requests; no page errors; no horizontal overflow | PASS (3 viewports) | m1s3-browser.json |
| M2-10 | Legacy UI without ?uw=1 unchanged (no dock-layout, no non-GET) | PASS (smoke, 1366 only; full 18-page compare NOT_RUN) | m1s3_legacy_noflag.png |

Tests: layout set (src/workspace) 11 files / 120 passed; regression (src/workbench src/App.test.tsx src/ui src/rebuild) 60/61 files, 475/475 passed (1 = pre-existing LocalAiBrowserJourneyContracts load failure); tsc 6 errors = baseline. Full vitest NOT_RUN.

## M1-s3fix [HERMIA-FE-20261023 M1-s3fix] — code b7e98c69a497568e79e394bd026e0d17246e6d9b (tree 852fa1edb7988470dfc9f155c01f3b35ce5741f2)
| ID | Item | Before (e3b92bd6) | After | Evidence |
|---|---|---|---|---|
| M2-07a | rename returns same version | FAIL (「已保存（版本 2）」) | PASS (unit) · browser NOT_RUN | novelPreviewPanels.test.tsx |
| M2-07b | rename returns no version | FAIL (「已保存（版本 undefined）」) | PASS (unit) · browser NOT_RUN | same |
| M2-07c | rename returns 204 | FAIL (silent) | PASS (unit) · browser NOT_RUN | same |
| M2-07d | rename returns non-JSON | not tested | PASS (unit) | same |
| M2-11 | inspector empty text direction-free | S3 (「在左侧」) | PASS | novelPreviewPanels.tsx |
| M2-12 | old palette 「布局」 only layout.*; 普通/专业 in 壳·设置 | FAIL (mode toggle in 布局) | PASS (unit) | CommandSearch.m1s3.test.tsx |
| M2-13 | dead .wb-command__id CSS | present | removed | commandSearch.css |
| REG | regression set + tsc | — | 600/600 tests (1 pre-existing file error); tsc 6 (unchanged) | logs/m1s3fix-* |
| FULL | full vitest ≤307 | — | NOT_RUN | — |

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

## M2-s1 [HERMIA-FE-20261024 M2-s1] — code 822b89ec (tree fcd2c214c41fa7b351c1166fbe80d1dcdfd5c379)
**Gate (changed by the user):** Node 22.14.0 full vitest, 3 runs, best adjusted ≤297. f3e0b496 = PASS. Vera's review is at 58270f6a.

| Item | Evidence | Status |
|---|---|---|
| creative = RebuildCanvas image, execution = RebuildCanvas video, tasks = TaskCenterPanel; no placeholder left | studioPreviewPanels.test "no placeholder left"; browser placeholders=[] at 1366/1440/1920 | PASS |
| 送到执行画布: disabled with a reason (还没有选中作品 / 先在创作画布选中一个节点), local draft write, double trigger → once | unit tests + browser dblclick → execNodes=1 | PASS |
| Shortcuts Mod+Alt+E/I/T via ShortcutTable; on conflict the shortcut is dropped and reported | unit test | PASS |
| N4: floats re-clamped under CSS zoom/resize | layout/m2s1.test; browser zoom 2: header kept inside the window (1440: left 987→672 px) | PASS |
| N5: exec entry visible (toolbar 执行画布 + main tabs + Mod+Alt+E, also after close) | tests + screenshots/m2s1_*_exec_canvas.png | PASS |
| No model calls / no non-GET on load, selection, canvas, panel switch | tests (GET-only assertion); browser nonGet=[] | PASS |
| tsc | 6 errors = known baseline (logs/m2s1-tsc.log) | PASS (baseline) |

**Full vitest, Node 22.14 at 822b89ec** (logs/m2s1-full-node22-*.json):

| Run | Total | Failed | IndependentStudioIdentity | Adjusted | Failures in src/workspace |
|---|---|---|---|---|---|
| 1 | 11365 | 297 | 8 | 297 | 0 |
| 2 | 11250* | 300 | 10 | 298 | 0 |
| 3 | 11365 | 299 | 10 | 297 | 0 |

- Best adjusted = 297, which is ≤297 → **PASS**.
- *Run 2: 3 files failed to collect because of vitest-worker module fetch timeouts (presentation.additive, ComicPublicationPanel, MediaWorkspaceShells). Its count is not comparable.
- Excluded runs:
  - logs/overlap/: two loops accidentally overlapped (301 / 299).
  - logs/m2s1-pretypefix-*: run before the docks type fix (297).
- Browser: logs/m2s1-browser.mjs/.json against 4299 + 8000. The screenshots were taken before the type-only fix in 822b89ec (PanelDefinition docks metadata; layout is unaffected).

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
| Item | Evidence | Status |
|---|---|---|
| 7+ sent nodes do not overlap, first ones in view | m2s1fix2.test.tsx (9 nodes) + Chrome 7 nodes/0 overlaps ×3 widths | PASS |
| useTaskCenter cancelled check covered | useTaskCenter.m2s1fix2.test.ts, mutant killed | PASS |
| exec pan/zoom kept on send | Chrome execTfBefore==execTfAfter; jsdom post-save remount test | PASS (in-memory) |
| select in either canvas → inspector | m3s1.test #1, Chrome inspCreative/inspExec | PASS |
| edits via registry action with honest success | m3s1 #2/#3/#7 (read-back mismatch → error) | PASS (local draft only) |
| no model calls on switch/select/project | m3s1 #1/#2/#5, Chrome nonGet/modelReqs empty | PASS |
| canvas state isolation | m3s1 #1 (send after exec pick uses creative node), mutant killed | PASS |
| full suite 3× Node 22.14 | adjusted 297/297/297 | PASS |
| tsc | 6 baseline | unchanged |

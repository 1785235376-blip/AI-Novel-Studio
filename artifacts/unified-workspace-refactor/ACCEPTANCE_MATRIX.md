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
| M2-07 | novel.chapter.rename via ActionRegistry; success only from server Chapter (version bump); 409 → error, panel stays open, never "已保存" | PASS (unit, mocked fetch) · real-backend save NOT_RUN (would write; deliberately not run) | novelPreviewPanels.test.tsx |
| M2-08 | novel.chapters.refresh via ActionRegistry, GET-only, real refetch result | PASS (unit + browser) | m1s3-browser.json |
| M2-09 | Load + all browser steps issue no non-GET requests; no page errors; no horizontal overflow | PASS (3 viewports) | m1s3-browser.json |
| M2-10 | Legacy UI without ?uw=1 unchanged (no dock-layout, no non-GET) | PASS (smoke, 1366 only; full 18-page compare NOT_RUN) | m1s3_legacy_noflag.png |

Tests: layout set (src/workspace) 11 files / 120 passed; regression (src/workbench src/App.test.tsx src/ui src/rebuild) 60/61 files, 475/475 passed (1 = pre-existing LocalAiBrowserJourneyContracts load failure); tsc 6 errors = baseline. Full vitest NOT_RUN.

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

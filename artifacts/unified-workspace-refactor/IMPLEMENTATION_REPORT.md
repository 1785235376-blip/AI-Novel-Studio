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

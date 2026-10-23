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

# BLOCKERS — [HERMIA-FE-20261023 M1]

> [HERMIA-FE-20261023 M1] Branch `work/hermia-unified-workspace-20261023` · base 6ba25ad7a47ed7677c32483b5234b656a3c0c2ed (tree 4193b3c22c49647dfc6e52241b5ff459f0064654) · M1 code commit 5aa20a4a75b28203702f8fac4056eed545e5ea4e (tree 32562dbfb206b6b5094c27ea78c665d7bbd8762b). Model: cannot be verified from inside the bot.

1. Wiring is blocked by the brief: App.tsx/IndependentStudioWorkspace/SDK entry may not be edited. A proposed patch exists (patches/0001-wire-docklayout-preview.patch, base 6ba25ad7a47ed7677c32483b5234b656a3c0c2ed, `git apply --check` OK, NOT applied, NOT typechecked/tested once applied). Needs owner approval.
2. "AppShell layout" and "RightInspector shell" are Design-System-Owner surfaces (docs/ui/protected_ui_surfaces.md). Replacing them with DockLayout needs a DESIGN SYSTEM CHANGE REQUEST — not filed.
3. Real-browser verification (viewport, zoom, E2E) not run → NOT_RUN in matrix.
4. M1-01 precise in-zone reorder by pointer position not implemented (PARTIAL).
5. No independent review: Vera not launched.
6. 6 pre-existing tsc errors in untouched files (see BASELINE_REPORT item 12).
7. Model identity: cannot be verified from inside the bot.


## Open after M1-fix [HERMIA-FE-20261023 M1-fix]
- N4 (S3): with CSS `zoom` only, useViewport reads innerWidth unscaled, so float clamp can place panels outside. Real browser zoom (DSF) is fine per Vera. **RESOLVED in M2-s1 822b89ec**: useViewport divides by html×body CSS zoom and re-clamps on resize/zoom/style change.
- N5 (S3): exec canvas hidden by default in preview; reachable only via 「中间显示」. **RESOLVED in M2-s1 822b89ec**: toolbar 执行画布 button, main-panel tabs, Mod+Alt+E (layout.showPanel reopens even if closed).
- N6: one-off 404 on first 1366 load, not reproduced. Watch.
- Browser re-verification of MF-1/MF-2 and full vitest run pending Vera.

## [HERMIA-FE-20261024 M2-s1fix]
- Vera M2-s1 lows resolved in 98a9dead: sent node off-view (x:-220 → inside view), palette aria-disabled, task center double GET on mount (StrictMode), layout.showPanel in the palette (Mod+Alt+P), focus to the task panel after Mod+Alt+T.

## [HERMIA-FE-20261024 M3-s1]
- No server canvas-graph API is wired to RebuildCanvas, so node edits stay as browser-local drafts (labelled in the UI).
- Spec t117u was not found, so M3 is derived from the brief and the contract docs.
- The inspector panel title is still 章节属性. Renaming it is deferred.
- Viewport memory lasts only for the session (in-memory).
- IndependentStudioIdentity.regression has 2 timing-sensitive extra failures in 2 of 3 runs. The gate excludes them; they are not touched by this work.

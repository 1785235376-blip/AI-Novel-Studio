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
- N4 (S3): with CSS `zoom` only, useViewport reads innerWidth unscaled, so float clamp can place panels outside. Real browser zoom (DSF) is fine per Vera. Deferred.
- N5 (S3): exec canvas hidden by default in preview; reachable only via 「中间显示」. Deferred to D (discoverability).
- N6: one-off 404 on first 1366 load, not reproduced. Watch.
- Browser re-verification of MF-1/MF-2 and full vitest run pending Vera.

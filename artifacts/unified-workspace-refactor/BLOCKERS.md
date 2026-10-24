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

- [HERMIA-FE-20261024 M3-s1fix] none new. Full suite not rerun (per brief); viewport memory is still in-memory only (reload resets).

- [HERMIA-FE-20261024 M3-s1fix2] none new. Full suite not rerun (per brief).

## Open items at M6 [HERMIA-FE-20261024 M6]
| # | item | impact | owner / needed |
|---|---|---|---|
| B1 | Canvases are local-only. Node edits and sent nodes are browser-local drafts (labelled in the UI). | Edits do not reach the server. | Needs a backend canvas-graph API. |
| B2 | There is no server canvas API wired to RebuildCanvas, which is why M3-03 is BLOCKED. | Same as B1. | Backend |
| B3 | The task panel has no session token. The ?uw=1 tasks panel uses an empty token and shows EXPERIMENTAL_FEATURE_DISABLED or a read failure (M2S-07 PARTIAL). | The task list cannot be verified with real data. | Auth/session wiring outside the preview |
| B4 | .nv-rail contrast: axe reports color-contrast (serious) ×3 on .nv-rail__h and .nv-rail__vol in the reused legacy NovelStructureRail (M4-09 FAIL). | a11y | Design System Owner (legacy component, not changed here) |
| B5 | TaskCenter showed the raw code STUDIO_REQUEST_FAILED. **Fixed in M6** for the TaskList and ReviewInbox alerts: human text is shown, and the code moves to data-error-code. Still open: ReviewInbox row detail `row.code ?? '已由原领域处理'` (ReviewInbox.tsx:51) shows a per-item code on purpose, so it was not changed. Other modules (assetbrowser: 「代码 STUDIO_REQUEST_FAILED」, asserted by AssetBrowserPanel.test.tsx:148) are out of scope. | UX | TaskCenter / AssetBrowser owners to decide |
| B6 | Viewport memory is in-memory only, kept per project for the session. A reload resets it (M3-08 PARTIAL). | UX | Needs a persistence decision |
| B7 | The original spec t117u is not on disk (searched /workspace/hr and memory). M3 was derived from the brief and the contract docs (M3-13 BLOCKED). | Traceability | User / Lumen to supply the spec |
| B8 | ?uw=1 is opt-in only and is not the default UI (M1-E2E PARTIAL). Replacing AppShell/RightInspector needs a Design System change request, which has not been filed. | Product rollout | Design System Owner |
| B9 | Some items are unit-only, with browser runs NOT_RUN: M2-03 loading/error, M2-06. The real-backend rename write (M2-07) was deliberately not run. M4-08 reduced-motion has never been checked. | Coverage | Vera / QA |
| B10 | There are 6 pre-existing tsc errors in untouched files. ISI has timing flakes (2/3) under Node 22. | Baseline | Owners of those files |
| B11 | The full suite at M6 HEAD is NOT_RUN. | Gate | Vera |

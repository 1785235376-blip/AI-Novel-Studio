
## M4-s1fix [HERMIA-FE-20261024 M4-s1fix]
- 12ff84ef: Vera's INDEPENDENT_REVIEW.md append committed unchanged (author/committer Vera (review)).
- CommandSearch.tsx: Hermia-approved patch applied (no focus steal on mount; focus returns to trigger after close, guarded by wasOpen). Tests: src/workbench/CommandSearch.m4s1fix.test.tsx.
- DockLayout: tabs have id uw-tab-<id> + aria-controls on every tab; panels aria-labelledby (tab + header in multi-tab main, header otherwise; aria-label kept); tablist aria-multiselectable in split; skip link on focus sits below the toolbar (--uw-toolbar-h).
- Bug found by the new wrap test and fixed: tablist was rendered in panel (activation) order, so each activation reordered tabs and broke Arrow/Home/End. Tabs now render in stable spec order.
- m4s1.test.tsx region-name assertion relaxed to regex (name now from labelledby).
- Mutation checks (each made tests fail, then restored): no right-wrap, no left-wrap, Home disabled, End disabled, unstable tab order, wasOpen guard removed, focus restore removed.
- Targeted vitest (workspace/workbench/rebuild): all pass; tsc: 6 errors (baseline).
- Chrome (logs/m4s1fix-browser.mjs, logs/m4s1fix_skip_*.png) at 1366/1440/1920: skip link focused at [8,67,95,96], 搜索功能 at [12,14,114,48], no overlap. Note: when focused, it briefly covers the left panel header title (transient, focus-only).
- Legacy: .nv-rail contrast left as-is (not workspace scope).

## M4-s1fix2 [HERMIA-FE-20261024 M4-s1fix2]
- 54696e89: Vera's INDEPENDENT_REVIEW.md append committed unchanged (author/committer Vera (review)).
- Exact panel names: m4s1.test.tsx asserts the exact name (header title, or "<tab> <header>" when labelled by its tab); new split test in m4s1fix.test.tsx asserts /^<tab> <header>$/ for both rendered main panels. Mutation "all labelledby point at first tab" → fails (restored).
- aria-controls on a tab is set only when its panel is shown (rendered); hidden tabs in single view omit it. Test: single view, 2 hidden tabs have no aria-controls and their panels are absent. Mutation "always set aria-controls" → fails (restored).
- Skip link on focus is centred below the toolbar. Chrome (logs/m4s1fix2-browser.mjs, logs/m4s1fix2_skip_*.png) at 1366/1440/1920: overlaps no button/select/input/link/tab (incl. 搜索功能 and all 折叠).
- Targeted vitest (workspace/workbench/rebuild) all pass; tsc 6 (baseline).

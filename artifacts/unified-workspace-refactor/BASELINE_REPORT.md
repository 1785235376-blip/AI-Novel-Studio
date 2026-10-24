# BASELINE_REPORT — [HERMIA-FE-20261023 M1]

> [HERMIA-FE-20261023 M1] Branch `work/hermia-unified-workspace-20261023` · base 6ba25ad7a47ed7677c32483b5234b656a3c0c2ed (tree 4193b3c22c49647dfc6e52241b5ff459f0064654) · M1 code commit 5aa20a4a75b28203702f8fac4056eed545e5ea4e (tree 32562dbfb206b6b5094c27ea78c665d7bbd8762b). Model: cannot be verified from inside the bot.

1. Repo / worktree: `/workspace/hr/wt`; other worktrees: /workspace/hr/repo (main 7b35e4cb), /workspace/hr/base and /workspace/hr/baseline-252e88fe (252e88fe detached). None touched.
2. Base: HEAD of work/hermia-frontend-refactor-20261022 = 6ba25ad7a47ed7677c32483b5234b656a3c0c2ed (tree 4193b3c22c49647dfc6e52241b5ff459f0064654), identical to origin after fetch.
3. origin/main = 7b35e4cb. Not touched; not pushed.
4. Working tree before work: clean except untracked `frontend/package-lock.json` (left untouched).
5. New branch: work/hermia-unified-workspace-20261023 from 6ba25ad7a47ed7677c32483b5234b656a3c0c2ed.
6. Stack: React 18, TypeScript 5.7, vitest 2.1.8, @testing-library/react 16, jsdom per-file env.
7. Existing layout system: `frontend/src/workbench/` (layout.ts schema v2 key poemseed.workbench.layout.v2::user::project::instance, v1 {panels:[{id,zone}]}, panels.ts, actions.ts, lifecycle.ts, useWorkbenchLayout.ts). Its sanitize drops unknown panels — conflicts with the spec's "preserve unknown" rule, hence v3 module.
8. Legacy AppShell keys: studio-inspector-width / studio-inspector-open (src/ui/AppShell.tsx).
9. Other branches: origin/work/studio-comic-media-7bad-tests-20261023 (36e4a685) is an ancestor of base (already included). Compare commits present: 45cf7c10 (audio template compare), 95608986 (canvas history compare). Local subtitle code exists in experimental/SubtitleTimelinePanel.tsx, CaptionTextReplace.tsx, creative/StudioTimeline*.tsx (not touched in M1).
10. Design rules: AGENTS.md → docs/ui/design_system.md tokens; docs/ui/protected_ui_surfaces.md lists "AppShell layout", RightInspector shell, etc. as Design-System-Owner surfaces.
11. Baseline tests: `./node_modules/.bin/vitest run src/workbench src/rebuild/canvas src/ui/AppShell` → 9 files, 91 tests passed, exit 0 (logs/baseline-vitest-6ba25ad7.log).
12. Baseline tsc: full `tsc --noEmit -p .` has 6 pre-existing errors in files M1 does not touch (App.tsx:1963, creative/GraphCanvas.tsx:577, ui/ModuleStartGate.tsx:43, ui/handoffSmoke.xUx10.test.tsx ×3) — recorded from the M1 run (logs/m1-tsc-full.log); a separate tsc run on the pure base was not done.

## Baseline refresh at M6 [HERMIA-FE-20261024 M6]
- Runtime: Node 22.14 (`PATH=/workspace/hr/node22/bin:$PATH`), as required by package.json engines (>=22.14.0 <25). Node 20.19.2 from apt is not supported (REGRESSION_M1_FLAKY.md).
- tsc baseline: still 6 errors in the same files. Checked again at M6.
- Full-suite gate: Node 22.14, best of 3, adjusted ≤297. Latest full run: merge 6652a661 (11423 tests, Vera).
- Targeted set: src/workspace, src/workbench, src/rebuild, src/taskcenter. At M6: 63 files, 503 tests.
- origin/main was not touched and nothing was pushed. Only branch and commit history were read for this refresh.

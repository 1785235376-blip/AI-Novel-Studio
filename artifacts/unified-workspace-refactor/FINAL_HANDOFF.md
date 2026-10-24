# FINAL_HANDOFF — [HERMIA-FE-20261024 M6]

## Branch / commits
- Branch: `work/hermia-unified-workspace-20261023` in /workspace/hr/wt. The worktrees /workspace/hr/wt-m4 and wt-m5 are kept and were not removed.
- HEAD: the M6 commit that adds this file. Its parent is e2c9d292 (Vera's merge-review append), and that commit's parent is merge 6652a661 (tree 299022d2, Vera PASS). The exact M6 HEAD and tree are in `git log -1 --format='%H %T'` and in the M6 report to the lead.
- **Nothing has been pushed. main / origin/main are untouched.** The untracked frontend/package-lock.json was left as it is.

## How to run
1. Node 22.14: `export PATH=/workspace/hr/node22/bin:$PATH` (Node 20 from apt is unsupported; see REGRESSION_M1_FLAKY.md).
2. Servers: backend on 127.0.0.1:8000 and vite dev on 127.0.0.1:4299 (`cd frontend && npx vite --host 127.0.0.1 --port 4299`).
3. Open `http://127.0.0.1:4299/?uw=1` for the unified workspace. Without `?uw=1` the legacy UI is unchanged.
4. Tests: in frontend/, run `npx vitest run src/workspace src/workbench src/rebuild src/taskcenter` (63 files, 503 tests) and `npx tsc --noEmit -p .` (6 baseline errors). The full suite gate is Node 22.14, best of 3, adjusted ≤297 (REGRESSION_REPORT.md).

## Done (M1–M5, merge, M6)
- M1: DockLayout with dock/float/resize/collapse/split/reset, v3 layout persistence with migration and repair, a dirty-close dialog, and layout actions in the ActionRegistry and the Ctrl+K palette.
- M2: real panels: outline (NovelStructureRail), chapter inspector with honest rename, creative/execution RebuildCanvas, and TaskCenter. Shortcuts Mod+Alt+E/I/T/P. Zoom-aware clamping. Single task GET.
- M3: dual-canvas ↔ inspector linkage, per-canvas selection, local-draft node edit with read-back, per-project exec viewport memory, and a real-Chrome reveal of the last sent node.
- M4: skip link, tablist a11y, splitter keyboard and Esc, zoom 80–200% layout, and a CommandSearch initial-focus fix.
- M5: host DraftStore, beforeunload only while dirty, last-wins stale dropping, honest timeouts, and refresh-failure handling.
- Merge of M4 and M5 (Vera PASS; full suite 297/297/303 adjusted).
- M6: TaskCenter alerts without raw codes, a host tidy, and this review package.

## Acceptance
The consolidated matrix is in ACCEPTANCE_MATRIX.md ("M6 consolidated matrix"): 98 planned items, of which PASS 87, PARTIAL 6, BLOCKED 2, NOT_RUN 2, FAIL 1 and WAIVED 0. **Pass rate 87/98 = 88.8%.**

## Left (see BLOCKERS.md B1–B11)
- No server canvas API: canvases are local only.
- The task panel has no session token.
- .nv-rail contrast (legacy component).
- Viewport memory is not persisted across reloads.
- Spec t117u is missing.
- ?uw=1 is not the default UI and needs a Design System change request.
- Some checks are unit-only, or browser checks were NOT_RUN.
- The remaining per-item and asset-browser raw codes are out of scope.
- The full suite at M6 HEAD and Vera's review of M6 are both NOT_RUN.

## Patches
patches/README.md has an index of every patch and its applied state. All of them are applied in this branch; none were sent anywhere.

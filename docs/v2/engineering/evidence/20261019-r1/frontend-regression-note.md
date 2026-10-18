# Frontend regression note — Vitest e2e collection defect (D-01)

Before fix (baseline): Tests  4303 passed | 8 skipped (4311)
Before failures: 

After fix: Tests  4303 passed | 8 skipped (4311)
After failures: none

Commands: cd frontend; corepack pnpm test. Build (tsc -b and vite build) and the
design-token lint also passed after the fix.


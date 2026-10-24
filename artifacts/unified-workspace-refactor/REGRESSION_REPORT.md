# REGRESSION_REPORT — [HERMIA-FE-20261024 M6]

This report collects the full-suite gate history. Raw counts come from the logs and reports named in each row. adjusted = raw failed − IndependentStudioIdentity (ISI) failures + 8, where 8 is the ISI baseline. M1-flaky and M1-flaky2 used adjusted = raw, because ISI was 8 in every run.

## Gate rules
- **Node 20 era (up to M1-flaky2):** the gate was adjusted ≤307. The box's apt Node 20.19.2 had no bundled undici, and that caused 10 environment failures (ComicLayoutsPanel/VoiceSubtitle). See REGRESSION_M1_FLAKY.md.
- **Node 22.14 era (from M2-s1):** the gate is adjusted ≤297, best of 3. The user confirmed this rule on 2026-10-24. Node 22.14 is the runtime required by package.json engines.

## History
| slice @commit | Node | total | raw failed (runs) | ISI | adjusted | gate | result | evidence |
|---|---|---|---|---|---|---|---|---|
| M1-flaky @7e96d0ba | 20.19.2 | 11353/11351 | 307 / 308 | 8 / 8 | 307 / 308 | ≤307 | PASS (run 1) | logs/m1flaky-full-{1,2}.json |
| M1-flaky2 @dc1d4350 | 20.19.2 | 11353 | 307 / 310 / 307 | 8 / 8 / 8 | 307 / 310 / 307 | ≤307 best-of-3 | PASS (Vera) | logs/m1flaky2-full-*.json |
| M1-flaky2 @dc1d4350 | 22.14 | 11353 | 301 | 8 | 301 | (info) | — | logs/m1flaky2-full-*.json |
| M2-s1 @822b89ec | 22.14 | 11365 / 11250* / 11365 | 297 / 300 / 299 | 8 / 10 / 10 | 297 / 298 / 297 | ≤297 | PASS | logs/m2s1-full-node22-{1,2,3}.json |
| M2-s1fix @98a9dead | 22.14 | 11375 | 298 / 297 / 297 | 8 / 8 / 8 | 298 / 297 / 297 | ≤297 | PASS | logs/m2s1fix-full-node22-{1,2,3}.json |
| M3-s1 @2abedfb3 | 22.14 | 11384 | 299 / 299 / 297 | 10 / 10 / 8 | 297 / 297 / 297 | ≤297 | PASS | logs/m3s1-full-node22-{1,2,3}.json |
| MERGE @6652a661 (run by Vera) | 22.14 | 11423 | 297 / 299 / 305 | 8 / 10 / 10 | 297 / 297 / 303 | ≤297 | PASS | INDEPENDENT_REVIEW.md "Merge (6652a661)" §6; Vera's evidence is at /workspace/hr/vera-compare/merge-6652a661/ |
| M6 @c3939f22 (run by Vera) | 22.14 | 11424 | 297 / 299 / 298 | 8 / 10 / 8 | 297 / 297 / 298 | ≤297 | PASS | INDEPENDENT_REVIEW.md "M6 (c3939f22)"; /workspace/hr/vera-compare/m6/full-node22-{1,2,3}.json |
| M6-fix (tests + docs only) | 22.14 | — | — | — | — | ≤297 | NOT_RUN | targeted only |

\* In M2-s1 run 2, 3 files failed to collect (vitest worker fetch timeouts), so that run is not comparable. Runs that overlapped by accident (logs/overlap/) and the pre-type-fix run are excluded.

Slices without a row (M1-s2/s3 fixes, M2-s1fix2, M3-s1fix/fix2, M4-*, M5-*) ran targeted tests only. Their full-suite runs were done by Vera inside her review, or not at all. None of their numbers are restated here.

## Merge-gate detail (Vera)
- 298 tests failed in all 3 runs. This set is identical to persistent-node22.json, so there are no new persistent failures.
- 8 tests that are outside the baseline failed in some runs only. Each was rerun 3× in isolation: 6 passed 3/3, and 2 ISI cases passed 2/3. Both of those are on the known Node 22 flaky list, and none relate to workspace changes.

## M6 targeted (Hermia, Node 22.14)
- `vitest run src/workspace src/workbench src/rebuild src/taskcenter`: 63 files, 503/503 passed (the merge had 62 files and 502 tests; M6 adds problemText.m6.test.tsx).
- `tsc --noEmit -p .`: 6 errors, the known baseline.
- Mutation check: restoring `message · code` in TaskList.tsx makes TaskCenter.test.tsx fail (1 test), so the mutant is killed. The file was restored afterwards.

## M6-fix targeted [HERMIA-FE-20261024 M6-fix]
- Targeted run: see IMPLEMENTATION_REPORT M6-fix. Vera's M6 run: the 298 persistent failures match the baseline. The flakes (2 ISI, plus receiptCompanion) were each rerun 3×, and all passed 3/3.

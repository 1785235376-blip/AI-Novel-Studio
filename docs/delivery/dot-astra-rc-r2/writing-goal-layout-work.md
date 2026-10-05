# Writing-goal inspector field layout

Date: 2026-10-05 UTC.

The hosted `93d` screenshots show adjacent inline labels wrapping beside the preceding number/date inputs. The repair adds only scoped `.writing-goal-panel` rules in `frontend/src/novel/novel.css`: a single shrinking grid column, existing `--space-3`/`--space-1` gaps, zero direct heading/description margins, and full-width border-box inputs with `min-width:0`. App behavior, data, tokens, global shell and theme remain unchanged.

Verification:
- Four new source layout contracts and five existing UI contracts: **9 passed**
- TypeScript, token lint and scoped diff checks: PASS
- Existing real business Playwright tests: **2 collected**, not executed locally
- The existing business screenshot loop now asserts all three labels sit above their inputs, fields stay inside the panel, inputs fill their labels and neighboring controls do not overlap at 1366×768, 1440×900 and 1920×1080
- Actual post-fix browser geometry/screenshots await hosted CI; no local browser pass is claimed

Implementation/tests:
- `frontend/src/novel/novel.css`
- `frontend/tests/writingGoalLayout.test.ts`
- `frontend/tests/e2e/r2-business.spec.ts` (only geometry assertions in the existing three-viewport screenshot loop)

Evidence: `evidence/writing-goal-layout.txt`, `.xml`, `evidence/writing-goal-typecheck.txt`, and `evidence/writing-goal-token-lint.txt`.

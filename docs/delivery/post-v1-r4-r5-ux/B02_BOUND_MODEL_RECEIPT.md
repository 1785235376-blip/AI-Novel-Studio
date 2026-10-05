# B02 bounded original-model checkpoint

Date: 2026-10-05. Feature implementation, not an independent review.

## Result

The original Workflow deferred-node/claim/completion seam now composes the
original AuthorPreparer, A06 broker and JobManager for one explicitly reviewed
local model node. Rooted fan-out/fan-in DAGs execute through the original engine
with every branch joined before mandatory review. No second scheduler or
provider executor was created.

The real React panel provides exact adapter request/price/budget preview,
explicit per-run launch, original-job refresh, cancellation, unknown-receipt
recovery guidance and mandatory output review. Manual text uses manuscript NONE;
selected chapter text retains source/version fences. Bounds are persisted,
checked at send/delta/completion, and immutable after start. Legacy manuscript
acceptance is denied for these draft-only jobs.

Shared origin/bounds seam: `3e09fce`. The final feature commit and hosted outcome
are recorded by the parent integration task.

## Executed locally

All Python runs used `../r2-run.sh`; frontend commands used the pinned
`r2-tools/node_modules/.bin/pnpm` installation.

- `python -m pytest tests/test_r5_declarative_model.py tests/test_r5_declarative_job_bounds.py tests/test_r5_declarative_templates.py tests/test_r5_declarative_mounted.py tests/test_declarative_workflow_host_seam.py tests/test_r2_workflow_execution.py -q -m 'not postgres_backend_only'`: **95 passed, 73 deselected**.
- New model contracts alone: **28 passed, 28 PG cases deselected**. They cover
  both `/api` and `/api/v1`, actual File persistence, original synthetic
  transport, exact NONE/selection, a single job/reservation under duplicate and
  concurrent requests, changed source/budget, last-hop feature revocation,
  branch-source denial, output limit, deadline, cooperative cancellation,
  uncertain admission, restart, review dominance and unchanged manuscript.
- Shared broker/cancellation/bounds regression after immutable bounds:
  **30 passed, 16 PG cases deselected**.
- New model and bounds test files with `--collect-only -m postgres_backend_only`:
  **32 PostgreSQL cases collected**. Collection is not execution.
- `pnpm exec vitest run src/experimental/DeclarativeTemplatePanels.test.tsx`:
  **8 passed**. UI contract doubles verify captured authority, StrictMode read
  behavior, exact model confirmation, repeat-click suppression, unknown states,
  and late-response suppression after scope change.
- `pnpm exec vitest run src/ui/AppShell.test.tsx src/ui/primitives.test.tsx src/ui/ModuleWorkspaceRoutes.test.tsx`:
  **30 passed**.
- `pnpm exec tsc -b`, `pnpm run lint` (42-file token guard), Python compile and
  `git diff --check`: **PASS**.
- `pnpm exec playwright test --config playwright.r4.config.ts --list r4-declarative-model.spec.ts`:
  **1 real React/File/synthetic-provider journey discovered**. It captures two
  screenshots, verifies exact no-manuscript preview, original broker settlement,
  original manual-review output, legacy acceptance denial and reload.

## Explicit remaining boundaries

- PostgreSQL execution and hosted browser/screenshots: **NOT_RUN locally**.
  There is no authorized local PostgreSQL endpoint. The known Chromium EPERM
  launch restriction was not retried. Parent integration owns hosted CI.
- Real-model literary quality, real GPU performance, Windows, IME, accessibility
  assistive-tech and user aesthetic acceptance: **NOT_RUN**.
- Supported model execution is one registered local TEXT route, `LOCAL_ONLY`,
  known zero reservation, no fallback and no automatic retry. Current broker
  price, identity and budget constraints remain authoritative. Real local
  routes lacking required evidence or a current zero price remain blocked.
- Cloud/paid custom graphs, multiple model nodes, conditional routing, automatic
  variable wiring, parallel execution and arbitrary code adapters are outside
  this supported subset. Executable extensions remain `DENY_ALL`.
- A blocked provider is only cooperatively cancelled. No background deadline
  watcher, forced upstream preemption or guaranteed cost settlement is claimed.
- Default-OFF/V1 force-OFF, original generation/source contracts and protected
  shell/design tokens are preserved. No paid call, credential use, manuscript
  change, runtime install, frozen-PR change, merge, release or deployment.

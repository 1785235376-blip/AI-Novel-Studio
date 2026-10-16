# U03/U10 enabled-tool discovery refinement

Date: 2026-10-05. Scope: a local usability refinement of the existing Experimental workbench, not completion of the whole U03/U10 packages.

## Behavior

- A labeled native search field filters only currently server-enabled tool buttons. Chinese display names and feature identities match locally; whitespace-separated terms, case, and full-width Latin characters are normalized.
- Empty or whitespace-only queries preserve the complete enabled navigation order. Disabled and unregistered features are never offered or included in result counts.
- Typing changes navigation only. The current panel stays mounted, with its local drafts, editor-selection receipt, revision candidate, and captured session/branch unchanged. The current tool remains identified even when its button is filtered out.
- Explicit tool activation and external `requestedTab` navigation clear the query. A clear-filter button restores the full enabled list and returns focus to the search input.
- Native Tab/Enter button activation is retained. The search field has no command/Enter shortcut, so IME confirmation cannot select a tool or submit a domain form.
- Search does not call an API/model, alter flags/permissions, write content, or introduce a top-level menu. Existing Field, Button, StatusMessage, and token-based classes are reused. AppShell, theme, panels, and navigation metadata are unchanged by this refinement. The released B06–B10 panel imports/mounts already present in the worktree are preserved.

## Verification

- Focused workbench unit suite: **14/14 passed**, including all-enabled ordering, Chinese/identity matching, no-result/clear/focus, no request while typing, scope/draft retention, editor-selection/candidate retention, disabled/unregistered/revoked features, external navigation, and IME Enter.
- Combined workbench, deferred loading, revision-intelligence, and AppShell unit regressions: **41/41 passed across 4 files**.
- Frontend TypeScript build: **PASS**. Production Vite build: **PASS**; the existing large-chunk warning remains.
- UI token guard: **PASS**. Added Playwright journey type-check: **PASS**. Playwright collection: **1 test discovered**.
- `frontend/tests/e2e/r4-tool-discovery.spec.ts` uses the existing R4 File-backend fixture and a synthetic project. It checks 30+ enabled entries, identity filtering, no-result recovery, unchanged unsaved planning text, zero experimental requests during filtering, native keyboard selection, and unchanged chapter version/content.
- Browser execution and visual/geometry regression: **NOT_RUN locally** under the known Chromium EPERM limit; no launch retry was attempted. Exact-head hosted execution remains the lead's publication/CI responsibility. Unit/jsdom evidence is not browser evidence.
- Independent review remains platform-blocked; no alternate review was attempted. No paid/model-quality, deployment, merge, or user-acceptance claim is made.

## Reproduction

From the repository root, use the established `../r2-tools/node_modules/.bin/pnpm` harness with `--dir frontend`:

- `exec vitest run src/experimental/ExperimentalWorkbench.test.tsx src/experimental/DeferredExperimentalWorkbench.test.tsx src/experimental/RevisionIntelligencePanel.test.tsx src/ui/AppShell.test.tsx`
- `exec tsc -b --pretty false`
- `lint`
- `build`
- `exec playwright test --config playwright.r4.config.ts --list tests/e2e/r4-tool-discovery.spec.ts`

In a browser-capable authorized CI environment, omit `--list` to execute the new journey. No baseline snapshots should be regenerated just to make it pass.

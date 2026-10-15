# Dot overnight usability checkpoints — 2026-10-15

## Scope and baseline

- Independent branch: `work/dot-usability-20261015`, based on clean `045b865e5a003cac3333462d055f22099f6368d6`.
- Remote checked before implementation: `feature/v2-narrative-platform` = that baseline; `main` = `fed2404c8e30b44061b7139dced45b7f3301601c`; PR #47 is open and Draft.
- Requirement sources: user's 2026-10-15 overnight instruction, current `V2_ADVANCED_CAPABILITY_GAP_REPORT.md`, latest appended feature-matrix observations, repository UI rules and current source. The Master Roadmap attachment is not present in the checkout; its contents were not inferred.
- Only independent frontend usability is in this branch. The separately retained lifecycle candidate was not imported or changed. The existing authorization defect remains FAIL / externally BLOCKED and its remaining acceptance remains UNVERIFIED. No gates, API permissions, content policy or backend lifecycle were changed.
- Own cloud only. No user computer, Windows host, GPU, local model service, paid API, model download or deployment.

## Queue

1. Model Center honest partial-read / loading / retry feedback: implemented and selected verification recorded below.
2. Audit Prompt comparison usability against the existing read-only contract; implement only a verified independent gap. Historical metadata is not exposed by the current revision-body contract, so no new backend projection is assumed.

## Stage 1 — truthful Model Center read outcomes

### Verified gap

`useModelCenter` selected EMPTY whenever no current catalog arrived, even when storage succeeded and the catalog failed. A catalog notice was rendered only if a catalog already existed, and it reused the storage notice, incorrectly naming the failed source. The initial pending read also rendered unavailable-storage messaging. Existing backend / transport owners already distinguish these outcomes.

### Visible result

- PARTIAL explicitly distinguishes incomplete sources from a completely empty registry.
- Catalog/runtime failures are named even without a prior catalog; storage facts that were successfully read remain visible.
- Only a successful empty catalog displays the empty-registry message.
- Explicit retry can recover to READY; no timer, automatic retry, write operation or model execution was introduced.
- Refresh failures mark retained catalog and storage facts as potentially stale.
- Loading has `aria-busy`, disables reread controls and avoids premature missing-source notices.
- Existing shared primitives and tokens are reused; no protected shell, token, primitive or visual snapshot changed.

### Files

- `frontend/src/modelcenter/ModelCenterPanel.tsx`
- `frontend/src/modelcenter/StoragePanel.tsx`
- `frontend/src/modelcenter/useModelCenter.ts`
- `frontend/src/modelcenter/modelCenterTypes.ts`
- `frontend/src/modelcenter/ModelCenterPanel.test.tsx`

### Actual checks

Commands are relative to `frontend/` unless stated otherwise. Counts overlap and must not be added.

| Command | Result | Exit |
| --- | --- | --- |
| `vitest run src/modelcenter/ModelCenterPanel.test.tsx --reporter=verbose` before implementation, with five new tests | 20 passed / 5 failed; all new UX regressions reproduced | 1 |
| `vitest run src/modelcenter --reporter=verbose` first implementation | 101 passed / 3 failed; two new assertions assumed active-only bytes although the existing report sums storage, and loading still exposed an existing unavailable hint | 1 |
| Same command after correcting the new test expectations and pending hint | 104 passed / 0 failed; repeated on final stage code | 0 |
| `vitest run src/modelcenter src/creative/IndependentStudioWorkspace.test.tsx src/ui/ModelCenter.test.tsx src/ui/ModelCenterOnboarding.test.tsx src/ui/ModelCenterLegacyOwner.test.tsx --reporter=verbose` | 128 passed / 1 failed; unchanged preference-CAS test waits for an alert | 1 |
| `vitest run src/creative/IndependentStudioWorkspace.test.tsx --reporter=verbose` from a clean archive of `045b865` | 7 passed / same 1 failed at line 124; no original assertion changed | 1 |
| `vitest run src/ui/AppShell.test.tsx src/ui/AppShell.projectNoun.test.tsx --reporter=verbose` | 31 passed / 0 failed; jsdom contracts, not real geometry | 0 |
| `tsc -b && vite build && node ../scripts/check_ui_design_tokens.mjs` | Type/build pass; token guard 52 files pass. Existing large-chunk warning retained | 0 |
| `git diff --check` from repo root | Pass | 0 |

Setup used lockfile-frozen pnpm 10.6.5 and isolated package caches. Initial system pnpm 11.25.0 was rejected by the project engine rule; an initial npx cache path was not writable. The successful task-local cache install changed no lockfile or dependency version.

### Browser / integration limits

- Bundled Playwright Chromium installation failed because the returned archive was truncated / not a ZIP. No repeated manual downloads.
- One run using the already-installed own-cloud `/usr/bin/chromium` with the original visual configuration failed to launch: `socket() failed: Operation not permitted`. Three requested shell screenshot cases failed before any page executed. The first temporary config invocation had an ESM-loading error, corrected before that launch attempt.
- Browser behavior, screenshots and real geometry: **BLOCKED / NOT_RUN**, no baseline updates and no successful browser claim.
- Full frontend suite, backend File/PostgreSQL, live model/provider, GPU and Windows installation: **NOT_RUN** for this stage. No backend change required these checks; the broader frontend failure remains explicitly open.
- Raw local test logs and baseline reproduction remain outside version control. This report contains only synthetic, sanitized evidence.

### Read-only review follow-through

The initial local checkpoint is `e2c9d0de1c2d896bbf53b4149e48834ede002122`.
Independent review found a remaining stale-usage case after HTTP 404 and a newly introduced
initial-denied catalog recovery message. Two focused synthetic tests reproduced both failures
(2 failed / 25 deselected, exit 1). The display-only corrections now mark retained UNAVAILABLE
storage values and avoid catalog recovery advice when the panel has not been admitted to read.
No permission or transport behavior changed.

- Final modelcenter suite: **106 passed**, exit 0.
- Final combined modelcenter + adjacent Model Center/workspace + AppShell selection: **161 passed /
  the same 1 baseline failure**, exit 1 (162 tests, eight files). Exact command is the adjacent
  selection above plus `src/ui/AppShell.test.tsx src/ui/AppShell.projectNoun.test.tsx`.
- Type/build/token checks were rerun after these corrections; no browser launch was retried.
- Initial Git publication was paused by a payload/destination authorization check. After the
  original user's exact project/push authorization was supplied, the one retry reached Git and
  failed for missing HTTPS credentials. The approved connected GitHub publication route is used
  instead, with full source-tree equivalence checked; commit metadata may therefore differ from
  the preserved local checkpoint. No credentials or raw logs are included.

## Current handoff

Stage 1 is ready for a Draft-only review checkpoint, with the limits above. Publication SHA and remote verification are recorded in the task handoff and will be appended here at the next checkpoint. No merge or release is authorized by this delivery.

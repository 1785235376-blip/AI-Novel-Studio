# Dot overnight usability checkpoints — 2026-10-15

## Scope and baseline

- Independent branch: `work/dot-usability-20261015`, based on clean `045b865e5a003cac3333462d055f22099f6368d6`.
- Remote checked before implementation: `feature/v2-narrative-platform` = that baseline; `main` = `fed2404c8e30b44061b7139dced45b7f3301601c`; PR #47 is open and Draft.
- Requirement sources: user's 2026-10-15 overnight instruction, current `V2_ADVANCED_CAPABILITY_GAP_REPORT.md`, latest appended feature-matrix observations, repository UI rules and current source. The Master Roadmap attachment is not present in the checkout; its contents were not inferred.
- Only independent frontend usability is in this branch. The separately retained lifecycle candidate was not imported or changed. The existing authorization defect remains FAIL / externally BLOCKED and its remaining acceptance remains UNVERIFIED. No gates, API permissions, content policy or backend lifecycle were changed.
- Own cloud only. No user computer, Windows host, GPU, local model service, paid API, model download or deployment.

## Queue

1. Model Center honest partial-read / loading / retry feedback: implemented and selected verification recorded below.
2. Prompt blank-line comparison and bounded navigation: implemented and selected verification recorded below. Historical metadata is not exposed by the current revision-body contract, so no new backend projection was added.

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

### Publication and exact-source follow-up

Stage 1 remote commit: `3b74003346bc920e2fd971f9897f5478e5800f5f`.
Full tree `d40457ad103fa084b52289ded8dd0a7b4a227dc5` equals reviewed local
`5d4b891ee1347d3a6db6d3040bf83bace9cc8a57`. Both `git ls-remote` and fetched object/tree
verification succeeded. Modelcenter tests were rerun on the fetched published commit:
**106 passed**, exit 0. Local pre-publication checkpoints remain preserved.

Draft [PR #48](https://github.com/1785235376-blip/AI-Novel-Studio/pull/48) targets
`feature/v2-narrative-platform`, leaving PR #47 and main unchanged.

The connector's exact-SHA PR-workflow query returned three terminal failed runs:
Cloud CI `38789080100`, Local Interop V1 `38789080080`, Shared R123 evidence `38789080141`.
Their returned job lists contain 15 failed jobs with null steps and log URLs; no test-execution
receipt was provided. This is **not hosted acceptance**, and no jobs were rerun. The connector
query covers PR-triggered runs only; no complete push-workflow inventory is claimed.

## Stage 2 — exact, navigable Prompt text comparison

### Verified gap and implementation

The existing comparison used the empty string for both an absent line and an authored blank
line. As a result, `first line` versus `first line\n` reported zero changed lines. It also rendered
all lines in one table; a valid newline-heavy 64-KiB body can contain 65,537 line positions.

- Missing and blank lines are now different values, explicitly labelled `无此行` and `空行`.
- Full comparison totals are retained while at most 100 text rows are rendered per page.
- Users can navigate pages or select `仅显示差异行`; original line numbers are retained, and
  filter/revision changes reset the page instead of leaving the user at an empty offset.
- The existing positional comparison is described honestly; it does not claim automatic line
  alignment or semantic diffing. Whitespace and trailing newlines remain significant.
- The existing complete/verified/read-complete condition and incomplete-body warning remain.
  Controls operate only on the already-loaded bodies, without another request, write, model call,
  browser storage, or new history projection. The parent workspace's masked-body handling stays
  unchanged.

### Files and checks

Files: `frontend/src/prompt/PromptRevisionDiff.tsx` and `.test.tsx` (new),
`frontend/src/prompt/PromptWorkspace.tsx` (extract/re-export existing display),
`frontend/src/prompt/promptWorkspace.css` (existing tokens only).

Commands are from `frontend/`; counts overlap.

| Command | Actual result | Exit |
| --- | --- | --- |
| `vitest run src/prompt/PromptRevisionDiff.test.tsx --reporter=verbose` before implementation | 6 new failures / 1 unchanged incomplete-body pass | 1 |
| Same command after implementation | 7 passed | 0 |
| Same command after adding the 64-KiB newline-heavy boundary case | 8 passed; full totals, final differing line reachable, DOM remains bounded | 0 |
| Same focused command after the review-requested revision-number-only reset case | 9 passed | 0 |
| `vitest run src/prompt --reporter=verbose` before adding the boundary case | 103 passed, 15 files | 0 |
| `vitest run src/modelcenter src/prompt src/ui/AppShell.test.tsx src/ui/AppShell.projectNoun.test.tsx --reporter=verbose` on final stage code | 242 passed, 19 files | 0 |
| `tsc -b && vite build && node ../scripts/check_ui_design_tokens.mjs` | Pass; existing large-chunk warning unchanged | 0 |
| Repo-root `git diff --check` plus local inspection of new CSS token names against `tokens.css` and absence of new raw colors/pixel sizes | Pass | 0 |

The earlier adjacent preference-CAS failure remains open and is not covered by the 242-test
selection. Browser launch remains **BLOCKED** by the stage-1 platform socket failure and was not
retried; geometry/screenshots, backend, real models/GPU/Windows and whole-product acceptance
are **NOT_RUN** for this frontend stage.

Independent read-only review found no new defect. It ran the then-eight project tests plus six
isolated synthetic cases (14 passed, a separate overlapping run), checking sparse filtered
pagination, revision-number-only changes, exact spaces/tabs/CR/Unicode, incomplete transitions,
empty/newline differences and a high-change 64-KiB body. The revision-number-only case was then
added to the project suite; production code did not change after review.

### Stage 2 publication

Remote `253964fe48b54f22bf4c8c0aa7b13dc6d25a0b1b`, tree
`90c3a0c15682492f0a5299cbb0ddbfcf9ed176df`, exactly matches local tested checkpoint
`41a660a59422e2dfc2e91a4eb2506bb54bdc695b`. `git ls-remote` and fetched tree verification
passed. PR #48 remains Draft. The exact-SHA PR-run query reports terminal failures for
Cloud CI `38790478163`, Shared R123 `38790478159`, and Local Interop `38790478199`;
no hosted acceptance is claimed, and these runs were not retried.

## Stage 3 — find and select existing Prompt history records

### Verified gap and implementation

The existing authorized version rows already contain `changeReason`, but the old history list
only displayed `changeNote`. It also had no record search or in-row comparison selection, so a
user had to translate a meaningful history record back into a revision number in a separate
picker. No additional historical body or metadata endpoint is needed for this improvement.

- Display the existing optional authored reason, without synthesizing absent reasons.
- Search loaded records by revision number, note or reason; explicitly report the loaded scope
  and result count, and distinguish no loaded history from no matching search result.
- Select the old/new comparison side directly from a record. Selection only changes the existing
  pickers; the existing explicit comparison button remains responsible for reading bodies.
- Preserve incomplete-history warnings and record availability/redaction labels. No backend,
  read admission, masking, save, adoption, transport or storage behavior changes.
- Clear search returns keyboard focus to the input. Selected sides remain visible through
  `已选旧版` / `已选新版` text and `aria-pressed` even after focus moves elsewhere.

Files: new `frontend/src/prompt/PromptVersionHistory.tsx` and `.test.tsx`, plus the existing
`PromptWorkspace.tsx`, `PromptWorkspace.test.tsx` and token-only `promptWorkspace.css`.

### Verification and review

Commands are from `frontend/`; counts overlap and are not a total of unique tests.

| Command / checkpoint | Actual result | Exit |
| --- | --- | --- |
| Focused new `Prompt history finder` tests in `PromptWorkspace.test.tsx`, before implementation | 3 new failures / 11 deselected | 1 |
| Full `PromptWorkspace.test.tsx` after implementation | 14 passed | 0 |
| `vitest run src/prompt --reporter=verbose` while adding history unit coverage | 112 passed / 1 new-test failure from an unsupported Vitest matcher | 1 |
| Type check at that intermediate checkpoint | New test's unsupported matcher rejected; assertion was rewritten with equivalent supported matchers | 1 |
| Unbounded combined Model Center/Prompt/AppShell run overlapping a build | 248 passed / 2 existing scoping-test failures (one timeout); failed logs retained | 1 |
| `vitest run src/prompt/PromptWorkspace.scoping.test.tsx --reporter=verbose` without build overlap | All 3 unchanged cases passed | 0 |
| `vitest run src/prompt/PromptVersionHistory.test.tsx -t 'returns keyboard\|keeps selected' --reporter=verbose` before review corrections | 2 new failures / 5 deselected | 1 |
| `vitest run src/modelcenter src/prompt src/ui/AppShell.test.tsx src/ui/AppShell.projectNoun.test.tsx --maxWorkers=4 --minWorkers=1 --reporter=verbose` on final stage code, no build overlap | 252 passed, 20 files | 0 |
| `tsc -b && vite build && node ../scripts/check_ui_design_tokens.mjs` | Pass; existing large-chunk warning unchanged | 0 |
| `git diff --check` | Pass | 0 |

The two failed combined-run cases were not hidden, skipped or relaxed. Their isolated and
bounded-worker reruns pass; concurrent resource contention is a possible explanation, not a
proven root cause. The unrelated preference-CAS baseline failure remains open outside this scope.

Read-only review reproduced clear-search focus loss and identified invisible selected-state
feedback. Both now have dedicated regressions and UI-only corrections. Browser launch was not
retried: browser/geometry remains **BLOCKED / NOT_RUN**. The full frontend suite, backend,
Windows/GPU/live models and whole-product acceptance remain **NOT_RUN** for this stage.

## Current handoff

Three independent usability slices are implemented with preserved evidence and Draft-only
publication. Stage 3 publication SHA/tree will be recorded at the next checkpoint. No merge,
release or deployment is implied. The blocked lifecycle work remains separate and unchanged.

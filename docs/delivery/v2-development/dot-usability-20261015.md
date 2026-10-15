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

### Stage 3 publication

Remote `8128b6c7d4ec87868a75eb1f3aeba81e86e79cbd`, tree
`1a27ad4ffaf0d5354a898eb5801692d6f93e2ca6`, exactly matches local tested checkpoint
`f2be68e8ae1de304224049d32e62e8839dca427a`. `git ls-remote` and fetched tree verification
passed; PR #48 remains Draft. Exact-SHA PR workflows are terminal failures: Cloud CI
`38791985318`, Local Interop `38791985536`, Shared R123 `38791985542`. No hosted pass or
rerun is claimed.

## Stage 4 — recoverable, task-specific export download feedback

### Verified gap and implementation

The original novel export center requested a browser download but left no visible handoff
receipt or guidance for finding the file. A failed download from task A remained visible after
selecting task B, and a thrown browser handoff exception escaped without cleaning its temporary
anchor/blob URL. These are UI feedback/resource-cleanup issues in the existing download flow.

- Report that the browser was asked to download the named file, and direct users to its download
  list to confirm the actual save and location. Never claim a verified disk save.
- Associate download errors and handoff feedback with the originating task. When another file is
  pending, explain the existing wait instead of labelling the newly selected file as downloading.
- A fresh attempt clears an old handoff receipt. URL/anchor handoff failure gives a recoverable
  alert and cleans up the temporary anchor and any created URL.
- Keep existing download route, returned bytes/filename, context, active-view guard and
  single-download disabling unchanged. No new endpoint, credential, model call or backend change.

Code files: `frontend/src/novel/ExportPanel.tsx` and new
`frontend/src/novel/ExportPanel.downloadFeedback.test.tsx`. Existing UI classes/primitives are
reused; there is no CSS or protected-shell change.

### Verification and review

Commands are from `frontend/`; counts overlap.

| Command / checkpoint | Actual result | Exit |
| --- | --- | --- |
| `vitest run src/novel/ExportPanel.downloadFeedback.test.tsx --maxWorkers=2 --minWorkers=1 --reporter=verbose` on stage-3 source | 5 new failures and 1 uncaught simulated handoff error | 1 |
| Four export test files after implementation | 33 passed / 1 new-test expectation failure: generic Error message was incorrectly expected to use the API fallback | 1 |
| `vitest run src/novel/ExportPanel.downloadFeedback.test.tsx src/novel/ExportPanel.test.tsx src/novel/ExportPanel.recovery.test.tsx src/novel/ExportPanel.scope.test.tsx --maxWorkers=4 --minWorkers=1 --reporter=verbose` after correcting the new fixture and adding URL-creation coverage | 35 passed, 4 files | 0 |
| Same four files plus `src/modelcenter src/prompt src/ui/AppShell.test.tsx src/ui/AppShell.projectNoun.test.tsx`, same worker/reporter options | 287 passed, 24 files | 0 |
| `tsc -b && vite build && node ../scripts/check_ui_design_tokens.mjs` | Pass; existing large-chunk warning unchanged | 0 |
| `git diff --check` | Pass | 0 |

Independent read-only review checked the final source and six-test file, verified their hashes
and diff hygiene, and found no actionable issue. It did not independently rerun the unit suite
or validate a real browser download. No existing assertions, snapshots or test timeouts changed.

Real browser/geometry/download-to-disk verification remains **BLOCKED / NOT_RUN** from the
previously recorded cloud launch restriction; no browser retry was attempted. Full frontend,
backend, live model/GPU/Windows and whole-product acceptance remain **NOT_RUN**. The earlier
preference-CAS baseline failure and hosted workflow failures remain open.

### Stage 4 publication

Remote `497abbd9c2b4af012ae9843a594b92c59e966962`, tree
`da354668517c4236afaf214e70461630349aa7ab`, exactly matches reviewed/tested local
`2984b61fa149579c2bfad668046e8ce7f29bb5b3`. `git ls-remote` and fetched tree verification
passed. The PR metadata update first paused at an authorization check; after the exact original
Draft-PR authorization was supplied, the single retry succeeded. PR #48 remains Draft.
Exact-SHA PR workflows are terminal failures: Cloud CI `38795027442`, Local Interop
`38795027410`, Shared R123 `38795027347`. No hosted pass or rerun is claimed.

The stage-3 reviewer also closed both display findings against the actual published `8128b6c7`
source and its dedicated tests, without another test or browser run.

## Stage 5 — Prompt size guidance and accessible error correction

### Verified gap and implementation

The existing editor showed a static 64-KiB text limit but no current UTF-8 usage, making the limit
hard to judge for Chinese text and emoji. Seed/JSON errors were not linked to their controls, and
an invalid advanced JSON draft became hidden after switching to novice mode: saving explained
the error without exposing the field needed to fix it.

- Show current UTF-8 bytes, remaining bytes or exact overage against the existing
  `PROMPT_BOUNDS.textBytes`. Preserve every character; no trimming, clipping, new request or new
  save gate is introduced. Existing validation remains responsible for submission decisions.
- Associate current field-error text via `aria-describedby`, mark the affected control, and
  focus that control when an editable validation error is presented.
- Reveal erroneous parameters in novice mode and keep the correction field visible while the
  user types. Normal novice editing still hides advanced parameters; input remains unchanged
  until edited, and saving still requires the existing explicit button.
- Reuse the existing status/control presentation. On successful family selection, clear the
  previous draft's view-level field error so it cannot mark or focus a different draft. No CSS,
  primitive, draft state machine, API, persistence or backend changes.

Code files: `frontend/src/prompt/PromptEditorPanel.tsx`, new
`PromptEditorPanel.usability.test.tsx`, and an appended integration case in
`PromptWorkspace.test.tsx`; `usePromptWorkspace.ts` changes only the successful-selection
field-error reset.

### Verification

Commands are from `frontend/`; counts overlap.

| Command / checkpoint | Actual result | Exit |
| --- | --- | --- |
| `vitest run src/prompt/PromptEditorPanel.usability.test.tsx --maxWorkers=2 --minWorkers=1 --reporter=verbose` before implementation | 6 new failures / 1 unchanged pass | 1 |
| Same focused command after implementation | 7 passed | 0 |
| Stage-4 combined command after initial editor implementation | 294 passed, 25 files | 0 |
| Same combined command after adding professional-to-novice correction and explicit-save integration coverage | 295 passed, 25 files | 0 |
| Focused family-switch regression before review correction | 1 failed / 15 deselected | 1 |
| Same combined command after clearing the prior draft's field error on successful selection | 296 passed, 25 files | 0 |
| `tsc -b && vite build && node ../scripts/check_ui_design_tokens.mjs` | Pass; existing large-chunk warning unchanged | 0 |
| `git diff --check` | Pass | 0 |

The final combined command is `vitest run src/modelcenter src/prompt
src/novel/ExportPanel.downloadFeedback.test.tsx src/novel/ExportPanel.test.tsx
src/novel/ExportPanel.recovery.test.tsx src/novel/ExportPanel.scope.test.tsx
src/ui/AppShell.test.tsx src/ui/AppShell.projectNoun.test.tsx
--maxWorkers=4 --minWorkers=1 --reporter=verbose` (one shell command).

Read-only review found a stale cross-family validation error: selecting valid family B after
invalid family A could expose and focus B's valid parameters. A dedicated regression reproduced
this; the correction clears only the UI field error when successful selection replaces the draft.
The reviewer verified the final four source/test hashes and reran four isolated suites including
its original reproduction: **29 passed**, a separate overlapping review run. No remaining finding
in that scoped review.

Real browser/screen-reader/geometry checks remain **BLOCKED / NOT_RUN**; focus assertions here
are jsdom contracts, not assistive-technology acceptance. Full frontend, backend, live models,
GPU/Windows and whole-product acceptance remain **NOT_RUN**. The earlier baseline and hosted
workflow failures remain open.

### Stage 5 publication

Remote `04147ab4fcfdde2dc7f3ee2cc8656fbc290fa83f`, tree
`8a7cf10daf21f486a9c7b15a08b70aa63ffa0ecc`, exactly matches reviewed/tested local
`6850bb1e7210150341c8b81ca00aa8f6e7610f7f`. `git ls-remote` and fetched tree verification
passed, and PR #48 remains Draft. Exact-SHA PR workflows are terminal failures: Cloud CI
`38796237363`, Local Interop `38796237258`, Shared R123 `38796237291`. No hosted pass or
workflow rerun is claimed.

## Stage 6 — accurate receipt read state and loaded-history scope

### Verified gap and implementation

`ReceiptRecoveryPanel` originally described an absent page as a successful empty service result
even during IDLE, LOADING and FAILED states. It did not warn that `next_offset` meant only part of
the history was loaded. A completed task lacking a filename also displayed the unfinished-task
wording, despite the separate completed badge.

- Distinguish not-yet-read, loading, failed and successfully empty states. Loading is exposed
  with `aria-busy`; failed reads retain an explicit path to the existing manual read control.
- Mark retained rows as previously loaded facts while refresh is incomplete or failed.
- Label counts as loaded records and explain a supplied next-page marker, including offset zero.
  Users are directed to the original export center for pagination; no new reads are started.
- Distinguish a completed task's missing filename from an unfinished task and direct the user
  to the original export center to check the file.
- Changes are presentation-only. Recovery callbacks, controller, client, endpoints, gates,
  dispatch/cancel behavior, CSS and shared primitives are unchanged.

Code files: `frontend/src/delivery/ReceiptRecoveryPanel.tsx`, new
`ReceiptRecoveryPanel.test.tsx`, the outer empty-page labels in `DeliveryCenterPanel.tsx`,
and appended integration tests in `DeliveryCenterPanel.test.tsx`.

### Verification

Commands are from `frontend/`; counts overlap.

| Command / checkpoint | Actual result | Exit |
| --- | --- | --- |
| `vitest run src/delivery/ReceiptRecoveryPanel.test.tsx --maxWorkers=2 --minWorkers=1 --reporter=verbose` before implementation | 8 new failures / 1 unchanged empty-state pass | 1 |
| `vitest run src/delivery --maxWorkers=4 --minWorkers=1 --reporter=verbose` before the two extra integration cases | 64 passed, 5 files | 0 |
| Stage-5 final combined command plus `src/delivery`, after adding loading-to-empty and failure-to-explicit-read integration cases | 362 passed, 30 files | 0 |
| Focused empty-page/non-null-cursor integration before review correction | 2 failed / 13 deselected | 1 |
| Same combined command after aligning outer EMPTY badge/heading/detail with page-limited evidence | 364 passed, 30 files | 0 |
| `tsc -b && vite build && node ../scripts/check_ui_design_tokens.mjs` | Pass; existing large-chunk warning unchanged | 0 |
| `git diff --check` | Pass | 0 |

Read-only review found that an empty page with a remaining cursor could still trigger the outer
project-wide empty-history statement. Offset-zero and offset-50 regressions reproduced this;
the outer EMPTY badge, heading and detail now describe only the empty page in that case.

No original assertions, timeouts, or snapshots changed. The loading/recovery tests use controlled
synthetic reads; they do not prove live backend service recovery. Browser/geometry remains
**BLOCKED / NOT_RUN**, and full frontend, backend, live models, GPU/Windows and whole-product
acceptance remain **NOT_RUN**. Original baseline and hosted workflow failures remain open.

### Stage 6 publication

Remote `b863f99b4ff37eb62eedf6aadb9301c90a7902db`, tree
`8ced8bf5a721f36089f2355e85fd00d45044810f`, exactly matches reviewed/tested local
`b31017094c77a3e380727ae8c4f7611122edf215`. `git ls-remote` and fetched tree verification
passed; the combined command was rerun on that exact published SHA: **364 passed**, 30 files,
exit 0. Independent review reran 13 scoped display tests and closed the partial-history issue.
PR #48 remains Draft. Exact-SHA hosted workflows are terminal failures: Cloud CI `38797755972`,
Local Interop `38797756438`, Shared R123 `38797755786`; no hosted acceptance or rerun is claimed.

## Stage 7 — recoverable object-format inspection

### Verified gap and implementation

`ItemExportPanel` retained the previous successful format verdict when the user changed the
format, even though it cleared the previous refusal. Changing the kind filter could also hide
the checked object while leaving its verdict visible. A filter with no matching loaded objects
showed an unexplained empty list.

- Clear check feedback on explicit format or kind changes. A fresh verdict still requires the
  existing explicit check button; changing a selector does not claim fresh success.
- Explain an empty kind filter separately from an empty catalog, with scope limited to loaded
  objects. The shared-button action restores all kinds through the existing filter callback.
- Return focus to the kind selector when the recovery button disappears. Preserve the existing
  handover selection; no selection or dispatch callback is invoked by checking/filtering.
- No operation, capability, backend, controller, client, shared primitive or CSS changes.

Code files: `frontend/src/delivery/ItemExportPanel.tsx` and new `ItemExportPanel.test.tsx`.

### Verification

Commands run from `frontend/`; counts overlap.

| Command / checkpoint | Actual result | Exit |
| --- | --- | --- |
| `vitest run src/delivery/ItemExportPanel.test.tsx --maxWorkers=2 --minWorkers=1 --reporter=verbose` before implementation | 3 new failures / 2 unchanged passes | 1 |
| Same focused command after implementation | 5 passed | 0 |
| Stage-6 combined command, including the new delivery test file | 369 passed, 31 files | 0 |
| `tsc -b && vite build && node ../scripts/check_ui_design_tokens.mjs` | Pass; existing large-chunk warning unchanged | 0 |
| `git diff --check` | Pass | 0 |

Independent read-only review found no in-scope defect and passed 7 isolated tests: the 5 added
cases plus 2 extra cases covering repeated recovery, preserved format/selection, and no automatic
explicit-format check. This review count overlaps the project suite.

No original assertions, timeouts or snapshots changed. These are synthetic React/jsdom checks;
real browser/geometry/focus-device acceptance remains **BLOCKED / NOT_RUN**. Existing baseline
and hosted failures remain open. Full frontend, backend, models, GPU/Windows and whole-product
acceptance are not claimed.

## Current handoff

Seven independent usability slices are implemented with preserved evidence and Draft-only
publication. Stage 7 publication SHA/tree will be recorded at the next checkpoint. No merge,
release or deployment is implied. The blocked lifecycle work remains separate and unchanged.

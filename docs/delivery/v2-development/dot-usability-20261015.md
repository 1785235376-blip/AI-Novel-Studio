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

### Stage 7 publication

Remote `4f9f1e1fc20577e6db86dbceb78a51ba171a67a4`, tree
`2f135185f093228819dfd3a081703ce35a2e718e`, exactly matches reviewed/tested local
`b337a3c9798fe0f8f0bf4036c71ed51c4a87633b`. `git ls-remote` and fetched tree verification
passed. An initial post-publication combined run had **367 passed / 2 failed**, exit 1, both
initial download-button queries in the export-feedback suite. That suite then passed unchanged
in isolation (**6 passed**, exit 0), and the unchanged combined command, explicitly checking
published HEAD first, passed **369 tests**, 31 files, exit 0. The first run overlapped completion
of the identical-tree fetch/switch; no code changed, and the failure's root cause is not proven.
Failure logs remain retained; assertions and timeouts were not weakened.

PR #48 remains Draft and records this nuance. Exact-SHA hosted workflows are terminal failures:
Cloud CI `38798788469`, Local Interop `38798788145`, Shared R123 `38798788108`.

## Stage 8 — keyboard access to task-center queues

### Verified gap and implementation

The existing Task Center used `tablist` / `tab` roles without arrow-key navigation, a single
active tab stop, or tab-to-panel links. This is a concrete keyboard navigation gap under the
project design-system rules and the [WAI tabs pattern](https://www.w3.org/WAI/ARIA/apg/patterns/tabs/).

- Left/Right arrows wrap focus between queue tabs; Home/End focus the first/last tab.
- Navigation is manual activation: focus movement does not select another queue or read it.
  Native button activation retains the existing `setQueue` callback. Vertical arrows, Tab,
  and Alt/Ctrl/Meta shortcuts are left to the browser.
- Instance-unique tab/panel IDs provide `aria-controls` and `aria-labelledby`; only the selected
  tab is in the page tab sequence. Inactive panels are empty hidden placeholders, so their
  original queue contents remain unmounted.
- Existing queue controllers, reads, task actions, review decisions, source navigation, CSS
  and shared primitives are unchanged. Visible instructions explain manual activation.

Code files: `frontend/src/taskcenter/TaskCenter.tsx`, root panel attributes in `TaskList.tsx`
and `ReviewInbox.tsx`, and new `TaskCenter.navigation.test.tsx`.

### Verification

Commands run from `frontend/`; counts overlap.

| Command / checkpoint | Actual result | Exit |
| --- | --- | --- |
| `vitest run src/taskcenter/TaskCenter.navigation.test.tsx --maxWorkers=2 --minWorkers=1 --reporter=verbose` before implementation | 4 new failures / 1 unchanged pass | 1 |
| Same focused command after implementation | 5 passed | 0 |
| Stage-7 combined command plus `src/taskcenter` | 418 passed, 36 files | 0 |
| `tsc -b && vite build && node ../scripts/check_ui_design_tokens.mjs` after the final wording correction | Pass; existing large-chunk warning unchanged | 0 |
| `git diff --check` | Pass | 0 |

Independent read-only review found no scoped defect and passed 8 overlapping isolated tests:
the 5 candidate cases plus hidden-content unmounting, cached-return, native-key pass-through,
and separate-root ID/focus checks.

The wording correction removed an implication that every activation reads: cached queues retain
their existing on-demand behavior. Tests cover focus, attributes and explicit click activation in
jsdom; they do not emulate browser-native Enter/Space clicks or prove screen-reader behavior.
Real browser/geometry/assistive-technology acceptance remains **BLOCKED / NOT_RUN**. No original
assertions, timeouts or snapshots changed. Prior baseline and hosted failures remain open.

### Stage 8 publication

Remote `f411decb5b431658f4ae378be310fd607eb645f2`, tree
`e79403c2c34e72fd1779d16482ab774bbafa42e1`, exactly matches reviewed/tested local
`46c7c688656ead32af9df32f9868e3ff16bb4bb6`. Remote SHA and fetched tree verified; the combined
command at the exact published SHA passed **418 tests**, 36 files, exit 0. PR #48 remains Draft.
Exact-SHA hosted workflows are terminal failures: Cloud CI `38800005696`, Local Interop
`38800005724`, Shared R123 `38800005867`. No hosted acceptance or workflow rerun is claimed.

## Stage 9 — explicit visible Prompt body rescue and reuse

### Verified gap and implementation

Prompt draft bodies intentionally stay in memory and cannot be recovered after a reload. The
editor lacked an explicit copy action, although the existing conflict dialog already offered
clipboard/manual-copy recovery. This slice adds a user-controlled way to retain or reuse the
current visible body before leaving, without changing draft persistence.

- Explicit “复制当前正文” copies only the exact current body, preserving whitespace, CR/LF,
  Unicode and emoji. It does not copy parameters, identifiers or metadata, save a revision,
  invoke models, or create durable backup/import behavior.
- Success appears only after clipboard completion. Within one mounted editor, only one request
  can be pending at a time; no
  automatic write or retry is performed. Empty/locked editor behavior remains locked.
- Unsupported, rejected or throwing clipboard access offers an explicit “选中正文手动复制”
  action and Ctrl+C/Command+C guidance. It does not request permissions repeatedly or use
  an alternate hidden copying route.
- Receipt attribution includes the UI project/branch/actor scope, draft identity and exact
  body. Changing scope/draft/text or unmounting invalidates late feedback; editing away and
  back also invalidates it. Rendering checks the source before displaying feedback.
- A copy already requested from the browser cannot be cancelled here. Leaving ASSETS or
  changing the host key unmounts the editor. Reopening resets its local in-flight guard and
  permits a second **explicit** write while the first is unresolved. The old receipt never
  updates the reopened UI, but cross-mount clipboard completion order is not guaranteed.
  This is not global/reopen single-flight. Visible guidance asks the user to paste and check
  the result and says leaving does not cancel the request. Actual clipboard/device behavior
  is not verified by jsdom.

Code files: `frontend/src/prompt/PromptEditorPanel.tsx`, new
`PromptEditorPanel.copy.test.tsx`, one receipt-scope prop in `PromptWorkspace.tsx`, and one
appended copy/no-POST/no-body-persistence integration in `PromptWorkspace.test.tsx`.

### Verification

Commands run from `frontend/`; counts overlap.

| Command / checkpoint | Actual result | Exit |
| --- | --- | --- |
| `vitest run src/prompt/PromptEditorPanel.copy.test.tsx --maxWorkers=2 --minWorkers=1 --reporter=verbose` before implementation | 12 new failures (no copy control) | 1 |
| Same focused command after initial implementation | 10 passed / 2 failed (stale pending-source wording) | 1 |
| Same focused command after state-driven pending-source correction | 12 passed | 0 |
| Stage-8 combined command plus the new copy test file | 430 passed, 37 files | 0 |
| Same combined command with the workspace integration and final render-time source matching | 431 passed, 37 files | 0 |
| Same combined command after adding the remount/second-click boundary regression | 432 passed, 37 files | 0 |
| `tsc -b && vite build && node ../scripts/check_ui_design_tokens.mjs` | Pass; existing large-chunk warning unchanged | 0 |
| `git diff --check` | Pass | 0 |

Independent read-only review passed 29 overlapping existing scoped tests and 5 extra synthetic
cases. It confirmed the per-mounted-editor boundary above; a remount-and-second-click regression
is included, without adding a shared clipboard subsystem. This is accepted as a documented
limitation, not evidence of global serialization or durable backup. Final static recheck verified
the source/test hashes and truthful guidance after that regression was added; no new finding.

No original assertions, timeouts or snapshots changed. All clipboard outcomes are synthetic.
Browser/clipboard-device/assistive-technology/geometry acceptance remains **BLOCKED / NOT_RUN**.
Original baseline and hosted workflow failures remain open.

## Remaining original goals and handoff boundary (Stage 9 snapshot)

The WorldPanel candidate identified here is implemented in Stage 10 below. Other limitations
remain open; this section retains the prior checkpoint context.

These nine independently tested UX slices are not completion of the original advanced roadmap.
The bounded follow-on audit distinguishes external blockers from work outside this UI assignment:

- Pinned Prompt → production adoption is absent, but the existing gap report specifies a new
  closed-admission write route, source-version verification and File/PG acceptance. That work
  is outside this non-security UI worker and cannot be inferred from metadata placeholders.
- A concrete next authoring capability is **outside this worker's narrow assignment, not
  inherently platform-blocked**: `frontend/src/experimental/WorldPanel.tsx` offers only the
  eight old `examples` kinds in its type selector. It omits `CHARACTER_VISUAL` and `SCENE_VISUAL`,
  although `app/experimental/world.py` already defines/registers both typed models (lines
  130–168). The existing WorldPanel save/edit/history path uses the original `/world/records`
  owner and expected version; the Bible projection is deliberately read-only and consumes
  these records. A next owner-based task can expose those existing kinds with guided fields,
  then verify create → edit → reopen → Bible projection, retaining existing review/CAS behavior.
  Existing test entry points are `tests/test_round2_bible.py` (visual-kind registration/schema),
  `frontend/src/experimental/WorldPanel.test.tsx` and Bible projection tests. First confirm the
  existing route is usable within current gates; do not enable endpoints or change auth, and
  do not proceed if the path depends on the separately blocked lifecycle work.
- Novel import already has bounded file selection, parsing preview, explicit confirmation and
  candidate-review persistence. No missing independent import capability was established by
  this bounded audit; it was not reimplemented or accepted end-to-end here.
- Video/audio/NLE/model execution and the complete production chain still need their original
  runtime and actual-artifact acceptance. Historical CPU media evidence remains historical
  evidence and is not downgraded; it is not reused as this run's acceptance.
- Browser launch has the recorded cloud socket blocker; real UI/clipboard/geometry checks,
  Windows/GPU/installation and real-model acceptance remain unavailable or unverified here.
- The separately blocked lifecycle candidate remains unchanged and externally blocked. No
  policy/NSFW, authorization, endpoint-enabling or backend-lifecycle work was attempted here.

Stage 9 is reviewed and tested; its publication SHA/tree receipt is maintained on the Draft PR
linked below. The concrete WorldPanel candidate above is handed to the parent for broader owner-based
continuation; it has not been implemented or tested in this slice. Public publication
receipts are maintained on [Draft PR #48](https://github.com/1785235376-blip/AI-Novel-Studio/pull/48).
No merge, release, deployment or whole-product completion is implied.


## Stage 10 — guided character and scene visual authoring

### Existing owner, newly usable fields

The WorldPanel selector previously offered only eight JSON-based world record kinds, despite
`WorldService` already registering `CHARACTER_VISUAL` and `SCENE_VISUAL`. Both visual kinds are
now selectable and expose labeled subject IDs and authored visual fields through existing
`Field`, `Form`, `Button` and status primitives. The old eight examples and JSON editor remain.
No backend production code, schema, service, route, admission, flag, middleware, protected shell,
shared primitive or stylesheet changed. Bible remains the original read-only projection.

- Character: existing character ID, appearance, clothing, distinguishing marks and declared
  reference asset IDs. Scene: existing location ID, architecture, material, lighting, weather,
  mood, time of day and declared reference asset IDs.
- Required title and subject, Unicode code-point counts/limits matching the existing schema,
  field-linked over-limit feedback, nonnegative integer event order, optional chapter,
  and an explicitly editable reference list capped at 50. Subject/reference IDs are sent as
  entered without trimming, splitting commas, lowercasing or inventing IDs.
- Saves retain the original POST/PUT owner paths and exact `expected_version`. Editing hydrates
  all visual fields. The shared action guard prevents duplicate in-flight submits; a failed
  edit preserves entered values and version for explicit retry. Visual controls are disabled
  during an in-flight action. Cancel retains the pre-existing local form behavior without
  issuing a mutation. Review/reopen/history keep their original paths and row versions.
- Approved visual rows have a disabled edit button. If the active visual edit is approved,
  its unsaved input and original expected version are preserved while editing/save are locked.
  A successful own approval also locks the draft when the subsequent reload fails.
  Visible guidance says approved profiles
  are immutable, creating a profile does not automatically replace Canon, and Bible selects
  the first approved match or otherwise the first match, not the latest profile.
- Blank visual dimensions stay UNKNOWN. Distinguishing marks remain stored/editable/history
  data, not an extra Bible dimension. References are declarations, never proof of asset bytes.
  Scene reference IDs remain stored/projected metadata, outside the seven scene dimensions.

### Synthetic verification

Counts overlap. New functional tests use only synthetic records and fixture-owned File stores;
no model inference, real assets, PostgreSQL, GPU or external paid API is involved.

| Check | Actual result | Exit |
| --- | --- | --- |
| New WorldPanel visual test file, baseline before implementation | 12 failed: missing entry/controls | 1 |
| Focused WorldPanel tests after implementation | 12 passed / 1 new 50-row setup timed out | 1 |
| Same focused tests after hydrating 49 references, then exercising add-50/remove/save (no timeout increase) | 13 passed, 2 files | 0 |
| Previous nine-stage combined frontend command plus both WorldPanel files | 445 passed, 39 files | 0 |
| Original isolated runner, Bible functional selection and new two-kind owner roundtrip, initial | 31 passed / 2 failed: new test expected a nonexistent projection ID field | 1 |
| Same Python selection after aligning that new assertion to existing record-status/value fields | 33 passed / 3 deselected | 0 |

Python command: `python scripts/run_v2_checks.py dot-usability-visual-roundtrip -- python -m pytest tests/test_round2_bible.py -q -k 'not requires_authority and not only_the_declared_methods and not get_only'`.
The installed Python interpreter was reused without changes; imports were verified to resolve
this clean worktree. Its historical location is not used as a source checkout. The three existing
route authority/method assertions were excluded from this functional slice. Full machine receipts
and synthetic logs are retained locally rather than published as raw environment dumps.

The new owner roundtrip creates one profile per subject in REVIEW, edits at v1 → v2, reloads a
fresh original service/store against the same temporary File persistence, rejects at v2 → v3,
reopens at v3 → v4, checks exact values and prior-history versions, then reads the existing Bible
route. REVIEW stays non-authoritative and Canon stays empty; unknown dimensions and unresolved
references remain explicit. The fixture's stub authority and opt-in test flags establish only
functional projection behavior, not live authorization, security isolation or production gate
acceptance. No new authorization fixture or security probe was added.

Final reviewed verification (overlapping counts):

- WorldPanel focused tests: **15 passed** across 2 files, including code-point boundary and
  approve-while-editing regressions. Independent scoped reviewer also ran these 15 successfully
  and reported the final diff clean. The earlier visual-focused baseline had 12 missing-entry
  failures; no original assertion, timeout or snapshot was weakened.
- Prior nine-stage frontend scope plus both WorldPanel files: **447 passed**, 39 files, exit 0.
  Command from `frontend/`: `node_modules/.bin/vitest run src/modelcenter src/prompt src/delivery src/taskcenter src/novel/ExportPanel.downloadFeedback.test.tsx src/novel/ExportPanel.test.tsx src/novel/ExportPanel.recovery.test.tsx src/novel/ExportPanel.scope.test.tsx src/ui/AppShell.test.tsx src/ui/AppShell.projectNoun.test.tsx src/experimental/WorldPanel.test.tsx src/experimental/WorldPanel.visual.test.tsx --maxWorkers=4 --minWorkers=1 --reporter=verbose`.
- Final isolated Python selection after adding the schema Unicode regression: **34 passed**,
  3 existing route authority/method tests deselected, exit 0. Runner label
  `dot-usability-visual-roundtrip-reviewed`; sources unchanged during the check. The original
  `httpx`/Starlette deprecation warning remains; no dependency changes.
- Final reviewed `tsc -b && vite build && node ../scripts/check_ui_design_tokens.mjs`: **PASS**,
  exit 0; existing >500 kB chunk warning unchanged. Build ran after tests, not concurrently.
- `git diff --check`: **PASS**.
- The approval-while-editing issue was identified by independent review and corrected locally;
  the existing owner already refused edits to approved records. This is an immutable-UI fix,
  with no lifecycle, authorization or security-acceptance claim.

Publication receipts are maintained on Draft PR #48 and the final handoff checkpoint.
Browser launch/real geometry and assistive-technology verification remain BLOCKED / NOT_RUN;
there was no browser launch retry. Earlier baseline and hosted failures remain open. The separate
blocked lifecycle candidate was not inspected, modified, tested or included. This authoring slice
does not complete V2, replace runtime acceptance, or imply merge, release or deployment readiness.


## Stage 11 — existing Director genre and shot-time authoring

### Original owners, completed authoring controls

The existing `DirectorVisualTarget.genre` and `ShotContinuity.time` fields were already typed
and consumed by the Director/continuity projections, but absent from the original frontend
editors. This slice exposes both through the existing visual-target and shot editor. It does
not add a backend model, service, endpoint, write owner or gate. The read-only DirectorWorkspace
stays read-only. No protected shell, shared primitive, stylesheet or dependency changed.

- The document-level genre control writes `visual_target.genre`, distinct from the project's
  inherited genre. It appears in the original document editor and its already-shared Director
  proposal preparation/review editor. Existing explicit preparation/review paths remain intact;
  no model is invoked automatically.
- Shot time writes `continuity.time`. Guidance explains that scene time does not populate it,
  and both adjacent shots need authored values before comparison. An empty side remains unknown.
- Ordinary shot lighting continues to supply lighting continuity. Stored `continuity.lighting`
  overrides remain preserved, without a second ambiguous lighting control.
- Merely viewing or editing unrelated fields leaves absent optional fields absent. An explicitly
  cleared control stores an empty string while retaining its sibling fields. Whole-target and
  whole-continuity removal still use their original explicit controls. IDs, scene data, shot
  links, director bindings and other shot/target fields remain unchanged. Frontend pass-through
  tests also retain unrecognized nested data; this does not expand the strict backend schema.
- Genre's 2,000 and time's 4,000 limits count Unicode code points to match the existing owner.
  Over-limit text is retained with field-linked feedback and cannot be saved until corrected.
  The document summary identifies over-limit time on unselected shots. The original busy and
  read-only fieldset applies to the new controls. No trimming or truncation is performed on save.
- Persistence stays on full-document POST/PUT, with the original `expected_version`, history,
  explicit restore and conflict reconciliation. Local conflicting input survives until the
  user explicitly chooses the checked server version. Restore creates a new current version.

### Verification

All results are synthetic and counts overlap. No new authorization fixture, security probe,
PostgreSQL, browser, model, GPU, external paid API or media service was used.

| Check | Actual result | Exit |
| --- | --- | --- |
| New `CreativeAuthoringFields.test.tsx`, before implementation | 12 failed: missing controls | 1 |
| New field tests plus original shot-continuity tests | 16 passed, 2 files | 0 |
| Focused authoring, original Director proposal/canvas and read-only Director projection suites | 60 passed, 7 files | 0 |
| Prior ten-stage frontend scope plus this stage's relevant workspace/client/Director and static design-contract tests | 561 passed, 50 files | 0 |
| Original isolated runner, Director projection/owner selection including new File roundtrip and Unicode limits | 39 passed, 2 existing route-authority/method tests deselected | 0 |

Python command from the repository root:
`PYTHONPATH="$PWD" /workspace/scratch/20a0022d2b33/studio-overnight/.venv/bin/python scripts/run_v2_checks.py dot-usability-director-authoring -- python -m pytest tests/test_v2_director_workspace.py -q -k 'not requires_authority and not only_the_declared_methods'`.
Only the installed interpreter/dependencies were reused; application imports resolve this clean
worktree. No sibling candidate source, environment modification or service was involved. Raw
receipts/logs are retained locally, not published as environment dumps. Existing `httpx`/Starlette
deprecation warning remains.

The new functional File test creates legacy-shaped v1, authors genre/time at v2, rereads through
an independently constructed original File store/service and verifies complete history, clears
one time and genre at v3, then restores v1 content as v4. The existing projection reports the
saved document-authored genre, changed-time warning and ordinary shot-lighting differences.
After one time is cleared, comparison is unknown rather than a false match or a break. A separate
original Director-owner test creates genre without shots. Fixture route authority/flags establish
functional behavior only, not live authorization, security isolation or production admission.
Frontend integration checks create, full-payload update, in-flight duplicate-save prevention,
reopen, history restore and explicit conflict replacement. Real browser and assistive-technology
acceptance remains **BLOCKED / NOT_RUN**. Static token/geometry contracts are not pixel geometry
or screenshot acceptance. Earlier baseline and hosted failures remain open.

### Append-only correction to the Stage 9 audit

Current source already contains Prompt-adoption implementation and a mounted read-only disclosure
panel. Stage 9's “adoption absent” wording refers to an unavailable accepted write workflow, not
absent source code. The write switch remains closed and acceptance unfinished. This stage neither
rebuilds nor enables adoption, and does not supersede the earlier historical evidence.

Publication and independent-review receipts are recorded on Draft PR #48. Eleven authoring/UX
stages are not V2 completion, merge, release, deployment or full production-chain acceptance.

Stage 11 build note: the first typecheck found five possibly-undefined `RequestInit` accesses
in the new test assertions/helpers. These were corrected using the existing optional-access
pattern, without changing assertions or production behavior. The subsequent
`tsc -b && vite build && node ../scripts/check_ui_design_tokens.mjs` passed, exit 0; the existing
>500 kB chunk warning remains. No test timeout or snapshot was weakened.

Independent read-only review found no in-scope defect and independently ran **27 passed / 3 files**,
exit 0: `CreativeAuthoringFields.test.tsx`, `CreativeStoryboardContinuity.phase4.test.tsx` and
`AIDirectorPanel.test.tsx` with `--maxWorkers=4 --minWorkers=1 --reporter=verbose`.

Combined frontend command from `frontend/`:
`node_modules/.bin/vitest run src/modelcenter src/prompt src/delivery src/taskcenter src/novel/ExportPanel.downloadFeedback.test.tsx src/novel/ExportPanel.test.tsx src/novel/ExportPanel.recovery.test.tsx src/novel/ExportPanel.scope.test.tsx src/ui/AppShell.test.tsx src/ui/AppShell.projectNoun.test.tsx src/experimental/WorldPanel.test.tsx src/experimental/WorldPanel.visual.test.tsx src/creative/CreativeAuthoringFields.test.tsx src/creative/CreativeStoryboardContinuity.phase4.test.tsx src/creative/AIDirectorPanel.test.tsx src/creative/AIDirectorFastReceipt.test.tsx src/creative/CreativeProductionCanvas.test.tsx src/creative/CreativeWorkspace.test.tsx src/creative/client.test.ts src/creative/graphCanvasGeometry.test.ts src/director tests/uiContracts.test.ts --maxWorkers=4 --minWorkers=1 --reporter=verbose`.

After all source/test edits, the reviewed combined frontend command was repeated successfully:
**561 passed / 50 files**, exit 0. The isolated Python selection was also repeated under label
`dot-usability-director-authoring-reviewed`: **39 passed / 2 deselected**, exit 0, with source
hashes unchanged during the check. The same code passed type/build/token checks above.

### Stage 11 publication status — blocked before remote mutation

The reviewed code is committed locally. Publication of the updated existing feature matrix was
rejected by an external approval requirement; the single evidence-backed identical retry was
also rejected. The matrix change was checked to contain only 24 appended sanitized Stage 11
lines, with no removals or credential/environment payload added. No alternative publication
route or partial upload was attempted. No Stage 11 blob, remote commit, ref update or PR update
succeeded. Draft PR #48 therefore still points to Stage 10 at
`61b1f0390077b403b62cc57cbd50048d2324ae40`; the preceding publication-receipt sentence is an
intended destination, not evidence that Stage 11 reached it. Publication now awaits explicit
approval for the committed Stage 11 source/tests and sanitized documentation payload. The
exact-published-SHA rerun and new hosted CI are **NOT_RUN** because no new published SHA exists.

## Stage 12 — bounded standalone MP3 export (local only)

### Current handoff index and actual scope

This append supersedes the initial report's frontend-only scope for this stage: the original
standalone audio trim/export owner now supports explicit MP3 in addition to omitted/default WAV
and explicit FLAC. Requirement: current-source gap in `AUDIO-12` (§14.3) and the user's approved
old/new advanced-capability continuation. Stage 11 and all earlier checkpoints remain intact.
The starting local commit is `e4cb8f571fea0137f08c40ea510da823589b1d27`; this stage remains on
`work/dot-usability-handoff11-20261015`. No new queue, registry, provider, asset owner or review
owner was created. No voice/model generation or normalization capability is implied.

The sibling lifecycle/security candidate stays **BLOCKED**, with its known defect and unfinished
acceptance unchanged. No lifecycle/security implementation, PostgreSQL, permission/gate, release,
main, tag, dependency, protected shell or user-device change was made here. All Stage 11/later
publication is still **BLOCKED pending explicit user resolution**. No new upload, push, ref or PR
mutation was attempted. Draft PR #48 remains the last verified Stage 10 head `61b1f039`; no new
hosted CI or exact-published acceptance exists.

### New behavior and bounded codec contract

- The existing Audio Inspector selects MP3 explicitly; leaving the format blank still omits the
  control and preserves legacy WAV request/recipe identities. Changing format invalidates the
  existing preview confirmation. Preview, queue, execute and review remain separate actions.
- Only local `libmp3lame` is used, with explicit CBR 128 kb/s at 32000/44100/48000 Hz and 64 kb/s
  at 8000/11025/12000/16000/22050/24000 Hz. Mono/stereo and existing reviewed gain are preserved.
  Unsupported requested rates are rejected in DTO, owner and client; no silent substitute rate,
  encoder or format is selected. Missing encoder/ffprobe produces `STUDIO_AUDIO_MP3_TOOL_UNAVAILABLE`.
- MP3 clips are 10 ms–120 s. The new minimum follows observed native behavior: one-millisecond
  LAME files at lower rates decode to 47 samples instead of the requested 8–44 samples. Independent
  tiny-file probes verified 10 ms at every supported rate. WAV/FLAC minimums are unchanged.
- Actual output is checked as an MP3 stream with the requested sample rate, channels and bitrate,
  then decoded through the original cancellable process owner to a size-capped private S16 file.
  Output and decoded-PCM SHA256, sample count, decoded bytes and measured duration are persisted.
  `audio/mpeg` is bound to the existing original receipt and candidate. A `.mp3` filename alone
  cannot satisfy proof. S16 describes decoded PCM; MP3 has no lossless/S16 bit-depth claim.
- Gapless decoded duration must match within one sample. Container duration separately permits
  at most three MPEG frames plus 2 ms rounding, and no more than 1 ms below decoded duration.
  The original 25 MiB encoded/decoded budget and process limits remain. Container delay/padding
  is displayed separately, rather than passed off as requested duration.
- Original private-candidate, explicit review, version checks, source bindings, cancellation,
  failure and unknown-publication/no-automatic-replay behavior remain. Recovery consumes the
  existing persisted proof without reencoding. Encoder failure and cancellation clean owned
  temporary files; the source waveform remains byte-identical.

### Actual functional evidence and files

A self-created 440 Hz WAV passes original File preview → idempotent queue → real native encode
→ private candidate → fresh service/store reopen → explicit review → approved asset → reopen.
Independent ffprobe and ffmpeg decoding verify MP3/22050 Hz/mono/64 kb/s/700 ms and 15,435 decoded
samples (30,870 S16 bytes). The gain test compares interior RMS to the expected half-amplitude
sine with a documented 10% lossy tolerance; it does not assert lossless sample equality or human
perceived quality. Stereo exports cover all nine rates at 713 ms; mono covers all nine rates
at the 10 ms boundary. Mounted original Host API tests verify real bytes, `audio/mpeg`, exact
candidate digest, private-before-review and approved/reopened receipt. This is functional File
and mounted-fixture evidence, not live authorization/isolation acceptance.

Production changes: `app/creative/production_execution_models.py`,
`app/services/studio_audio_execution.py`, new `app/services/studio_audio_mp3_profile.py`,
`StudioMediaExecutionPanel.tsx`, `useStudioMediaExecution.ts`, `studioProductionClient.ts`.
Tests: new `test_v2_audio_mp3.py`, `test_v2_audio_mp3_api.py`, `studioAudioMp3Contract.test.tsx`
and synthetic `fixtures/audio-mp3.capture.json`; existing FLAC exclusion examples now reject
lowercase `mp3` while uppercase MP3 is explicitly tested as supported. Existing WAV display
assertion follows the format-neutral empty-measurement copy. No assertions were removed.

### Separately identified test-selector correction

The expanded frontend run found two existing tests assuming a single global `alert`:
`IndependentStudioWorkspace.test.tsx` preference-CAS and `IndependentStudioRelationships.test.tsx`
relationship-CAS. Both were reproduced in an isolated, unchanged `e4cb8f5` frontend archive:
**2 failed / 11 passed**, exit 1. Existing mocked unrelated reads also expose network alerts,
so a global single-alert wait is ambiguous despite the correct conflict alert being present.
Only those two waits now require the exact version-conflict message and assert `role="alert"`.
Every later draft, source/version, module and no-dispatch assertion is retained. No timeout,
skip, fixture coverage, route behavior or security expectation was weakened. This corrects
those two previously recorded baseline test failures; their historical failed evidence remains.

### Verification receipts and limits

Counts below overlap and must not be added. Raw failure/success logs, exact commands, source-hash
receipts and synthetic media are retained locally; environment/source-hash dumps are not committed.

- Before implementation, new Python contracts: **5 failed**, plus 10 File fixture setup errors
  from an omitted owned `--basetemp` and 10 unrun PostgreSQL cases. New UI selection test: **1 failed**
  because MP3 was absent. The fixture command was corrected without changing fixture assertions.
- Initial native proof exposed the `audio/mp3` MIME assumption; it was corrected to `audio/mpeg`.
  Subsequent new-test accessor/actor errors and the 1 ms native timing failures are preserved.
- New backend/actual mounted API selection: **39 passed / 31 PostgreSQL cases deselected**, exit 0.
- Final original WAV/FLAC plus MP3 codec/owner/mounted functional selection: **116 passed /
  76 deselected**, exit 0; source snapshot unchanged during the run. Deselection covers PostgreSQL
  parameterizations and the existing FLAC revocation probe, not a suppressed codec failure.
- New/existing audio frontend selection: **155 passed / 4 files**, exit 0.
- Expanded prior-stage plus all creative frontend before the selector correction: **2072 passed /
  2 failed / 131 files**, exit 1. The two failures above were verified against unchanged baseline.
- Typecheck, Vite build and token guard **PASS**, exit 0; existing large-chunk warning remains.
  Initial typecheck rejected a new test's raw-JSON cast (`needs_reconciliation: null`); the test
  now obtains the typed job through the existing checked client decoder. No contract was relaxed.
- Independent read-only review found no in-scope production defect. It separately passed **45/45**
  real encode/probe/decode boundary combinations: 8k/44.1k/96k source rates into five MP3 rates,
  stereo, 10 ms at source start/middle/end. Captured MP3 bytes were independently re-probed and
  re-decoded with every measured field matching; exact legacy WAV hashes were retained.

Backend command from repository root, using the installed Python interpreter/dependencies only:
`PYTHONPATH="$PWD" python scripts/run_v2_checks.py dot-usability-mp3-regression -- python -m pytest tests/test_v2_audio_mp3.py tests/test_v2_audio_mp3_api.py tests/test_v2_audio_wav_controls.py tests/test_v2_audio_flac.py tests/test_v2_audio_wav_controls_api.py::test_mounted_real_pcm_proof_private_candidate_explicit_review_and_fixture tests/test_v2_audio_wav_controls_api.py::test_pcm_capacity_and_unknown_controls_are_structured_errors tests/test_v2_audio_flac_api.py::test_mounted_flac_proof_private_candidate_review_and_safe_capture -q -m 'not postgres_backend_only' -k 'not revoke_during_flac' --basetemp=.runtime/v2-checks/dot-usability-mp3-regression/pytest`.
The installed sibling interpreter was used without inspecting/importing sibling candidate source,
changing its environment, or starting a database/service.

Expanded frontend command is the Stage 11 combined command recorded above with `src/creative`
added after `vitest run`; Vitest deduplicates overlapping paths. Workers stay at `--maxWorkers=4
--minWorkers=1 --reporter=verbose`. Build is sequential `tsc -b && vite build && node
../scripts/check_ui_design_tokens.mjs`. All UI evidence is jsdom/static; browser/socket restriction
was not retried. Real browser pixels, assistive technology, native audio-player, Windows/GPU/model,
full V2, authorization/security and release acceptance remain **NOT_RUN / BLOCKED / LOCAL_REQUIRED**
as previously applicable. MP3 improves one original audio delivery path; it is not a new audio
editor or completion claim for all Audio Studio requirements.

Final expanded frontend rerun after the two selector-only corrections: **2074 passed / 131 files**,
exit 0. No skip or timeout change. Final `tsc -b` after those test edits also passes, exit 0.
The separate successful Vite/token build above uses identical production code.

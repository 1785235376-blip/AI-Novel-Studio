# Draft acceptance integrity and Workflow scope isolation

Date: 2026-10-05 UTC. Synthetic local data and recording/mocked APIs only. No real manuscript, credential, model inference, commit, push, merge or deployment was used for this work.

## Fixed findings

- **R2-IA-04:** Local Accept now uses the generation's captured chapter version as its CAS precondition. Supplying the newer current version cannot rebase an older draft. A known stale draft raises `VersionConflict` before writing or claiming acceptance. Legacy replacement drafts without a generation base fail closed; legacy continuation compatibility is retained because that operation creates a new chapter.
- **R2-IA-05:** Acceptance is serialized by the existing process-plus-OS-file mutation coordinator using a persisted-job namespace. Every attempt re-reads durable job state under the lock. `ACCEPTING` is persisted before the first side effect; `ACCEPTED` is persisted only after chapter/summary/proposal writes. An interrupted attempt remains blocked and requires review, with `ACCEPTANCE_UNCERTAIN` / `ACCEPTANCE_REVIEW_REQUIRED` recorded when the process can report failure. This is a single-host guarantee, not a distributed PostgreSQL transaction claim. PendingCanon IDs are deterministic per generation; stale rejection cannot erase the claim. Cancellation cannot change a live acceptance claim into a retryable generation state.
- **R2-IA-07:** WorkflowPanel and AgentQueuePanel remount their data observers on novel, actor, session, workspace, project, storyline and branch identity changes. Async work uses a mount epoch, captured collaboration request context, latest-request fencing, and duplicate-mutation guards. Late old-scope success/error/finally work cannot repopulate the new scope or initiate a follow-on refresh there. Workflow run loads also fence out-of-order selection changes. Task summaries are cleared on unmount. No visual shell, tokens, geometry or styling were changed.

The integration lead owns the coordinating `app/api.py` local expected-version forwarding and `frontend/src/api.ts` captured-context helper forwarding, full module remount key, and recovery-state display. The worker did not overwrite those files.

## Verified

- Focused backend regression: **35 passed**, one pre-existing FastAPI/Starlette deprecation warning. Includes **17 new acceptance tests**, real two-process single-host acceptance contention, two-manager contention, restart claims, a proposal-persisted-then-failed path, cancellation during acceptance, stale request-version injection, missing replacement base, local HTTP 409, generation variants, collaboration HTTP boundaries, and memory-enqueue failure tolerance.
  - `evidence/acceptance-integrity.txt`
  - `evidence/acceptance-integrity.xml`
- Exact original independent acceptance invariants: **3 passed, 7 deselected**. Executed the unchanged audit file outside this checkout.
  - `evidence/acceptance-independent.txt`
  - `evidence/acceptance-independent.xml`
- Frontend focused regression: **30 passed in 5 files**. Includes 20 new scope/race tests, the byte-identical archived independent stale-project assertion, four existing panel tests and five design-system contract tests.
  - `evidence/workflow-scope.txt`
  - `evidence/workflow-scope.xml`
- TypeScript: PASS (`evidence/workflow-scope-typecheck.txt`).
- Design-token lint: PASS (`evidence/workflow-scope-token-lint.txt`).
- Scoped `git diff --check`: PASS.

Counts overlap where indicated; these are focused verification, not a claim of a full-suite release pass.

## Blocked / not verified here

Actual browser visuals and geometry: **NOT_RUN (environment blocked before assertions)**. The configured bundled Chromium executable is absent. The existing system Chromium alternative also terminates before opening the synthetic fixture because Unix `socket()` returns `Operation not permitted`, including the permitted escalated retry. No screenshot baseline was updated. Hosted browser CI remains required.

Real PostgreSQL concurrency, multiple application hosts, native Windows execution and crash/power-loss recovery were not run. Ambiguous acceptance deliberately requires manual manuscript/Canon review instead of automatically replaying potentially completed writes.

An earlier broader regression run found two memory-agent extraction tests whose old router-only fixture no longer matches another concurrent worker's verified-local-provider contract. That fixture issue was reported to the integration lead; the acceptance-specific memory-enqueue test passes. This document does not claim those unrelated failures are resolved.

## Owned implementation and tests

- `app/jobs.py`: acceptance methods, claim-protecting rejection, acceptance statuses in the terminal set. The integration lead separately edits outbound dispatch logic in this file.
- `frontend/src/novel/WorkflowPanel.tsx`
- `frontend/src/novel/AgentQueuePanel.tsx`
- `tests/test_r2_acceptance_integrity.py`
- `frontend/src/novel/WorkflowScopeGuards.test.tsx`
- `frontend/src/novel/WorkflowPanel.independent-audit.test.tsx` (unchanged copy of the frozen audit assertion; original archive untouched)

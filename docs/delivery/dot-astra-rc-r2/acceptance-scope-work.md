# Draft acceptance integrity and Workflow scope isolation

Date: 2026-10-05 UTC. Synthetic local data and recording/mocked APIs only. No real manuscript, credential, model inference, commit, push, merge or deployment was used for this work.

## Fixed findings

- **R2-IA-04:** Local Accept now uses the generation's captured chapter version as its CAS precondition. Supplying the newer current version cannot rebase an older draft. A known stale draft raises `VersionConflict` before writing or claiming acceptance. Legacy replacement drafts without a generation base fail closed; legacy continuation compatibility is retained because that operation creates a new chapter.
- **R2-IA-05:** Acceptance is serialized by the existing process-plus-OS-file mutation coordinator using a persisted-job namespace. Every attempt re-reads durable job state under the lock. `ACCEPTING` is persisted before the first side effect; `ACCEPTED` is persisted only after chapter/summary/proposal writes. An interrupted attempt remains blocked and requires review, with `ACCEPTANCE_UNCERTAIN` / `ACCEPTANCE_REVIEW_REQUIRED` recorded when the process can report failure. This is a single-host guarantee, not a distributed PostgreSQL transaction claim. PendingCanon IDs are deterministic per generation; stale rejection cannot erase the claim. Cancellation cannot change a live acceptance claim into a retryable generation state.
- **R2-IA-07:** WorkflowPanel and AgentQueuePanel remount their data observers on novel, actor, session, workspace, project, storyline and branch identity changes. Async work uses a mount epoch, captured collaboration request context, latest-request fencing, and duplicate-mutation guards. Late old-scope success/error/finally work cannot repopulate the new scope or initiate a follow-on refresh there. Workflow run loads also fence out-of-order selection changes. Task summaries are cleared on unmount. No visual shell, tokens, geometry or styling were changed.

The integration lead owns the coordinating `app/api.py` local expected-version forwarding and `frontend/src/api.ts` captured-context helper forwarding, full module remount key, and recovery-state display. The worker did not overwrite those files.

## Backend-isolation correction after hosted PostgreSQL CI

The File acceptance harness originally passed only `data_root` to the repository factory. That argument does not override the configured backend; under the PostgreSQL matrix it incorrectly selected PostgreSQL and collided on fixed synthetic IDs. The same fixture-selection issue affected the dispatch Agent fixture and the reusable memory-agent File runner.

The three helpers now pass `Settings(storage_backend="file", database_url="")` explicitly. The spawned acceptance worker also receives a temporary `STORAGE_BACKEND=file` environment because a fresh interpreter imports application dependencies before calling the helper. These are still File/single-host tests when run in the PostgreSQL matrix; their passes must not be counted as PostgreSQL integration evidence. No whole-suite skip or weakened safety assertion was added. Three fixture-selection regressions deliberately set the process default to PostgreSQL and verify the helpers still create actual File repositories without contacting a database.

Separate `tests/test_r2_acceptance_postgres.py` provides eight true PostgreSQL cases using real repositories, independent connection pools and spawned OS processes. The original six cases are retained unchanged:

- Stale generation-base conflict with omitted, original and newer-current request versions (three cases)
- Concurrent two-manager continuation acceptance: independently read `ACCEPTING` before chapter creation, one accepted result, one blocked result, one added chapter and one PendingCanon
- A committed proposal followed by an injected failure remains non-replayable after reopening managers
- A persisted interrupted `ACCEPTING` claim survives reopening and cannot be replayed
- Two spawned OS processes, each importing the application in PostgreSQL mode, compete to accept the same PG-backed job while sharing the host lock root. Independent parent SQL-repository reads prove the committed `ACCEPTING` claim before writes; results must be one success, one rejection, one new chapter and one proposal
- A newly spawned process reads an existing `ACCEPTING` row and rejects replay without creating a chapter or proposal

`tests/test_r2_dispatch_postgres.py` adds two actual PostgreSQL Agent dispatch cases. A synthetic character starts `CLOUD_ALLOWED`, appears in the reviewed cloud context, and is committed as `LOCAL_ONLY` through an independent connection during route preparation or normalized provider resolution. Direct `CharacterModel.privacy` reads prove the persisted transition; the actual `TextModelNode` and a recording-only adapter must observe zero prompts and a persisted `AGENT_SOURCE_CHANGED` failure. No real model or paid provider is called.

These cases require the explicit disposable `TEST_POSTGRES_DATABASE_URL`, use unique UUID project/job IDs per test, and clean up only their own projects. A configured but unreachable endpoint fails rather than silently falling back. Existing `tests/test_lore_postgres_contract.py` continues to provide separate actual PostgreSQL Lore/Memory coverage and was not altered.

Current affected File verification: **117 passed, 10 PostgreSQL cases skipped / NOT_RUN locally**, one FastAPI/Starlette deprecation warning. Latest receipt: `evidence/acceptance-pg-process-dispatch-local.txt` and `.xml`. The earlier six-case collection is retained in `evidence/acceptance-backend-isolation.txt` and `.xml`. This local result proves File fixture isolation and the affected regression suite only. All ten PostgreSQL cases require the integration lead's actual hosted PostgreSQL CI run before any PostgreSQL-pass claim.

## Verified (original File-mode repair receipts)

- Focused File-backend regression: **35 passed**, one pre-existing FastAPI/Starlette deprecation warning. Includes **17 new acceptance tests**, real two-process single-host acceptance contention, two-manager contention, restart claims, a proposal-persisted-then-failed path, cancellation during acceptance, stale request-version injection, missing replacement base, local HTTP 409, generation variants, collaboration HTTP boundaries, and memory-enqueue failure tolerance.
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
- `tests/test_r2_acceptance_integrity.py` (explicit File harness)
- `tests/test_r2_acceptance_postgres.py` (eight real PostgreSQL contracts, including spawned OS processes; not executed locally)
- `tests/test_r2_dispatch_postgres.py` (two real PostgreSQL policy-revocation/normalized-dispatch contracts; not executed locally)
- `tests/test_r2_fixture_backend_isolation.py` (three File fixture-selection regressions)
- `tests/test_r2_dispatch_revalidation.py` (explicit File configuration in Agent fixture only)
- `tests/test_memory_agent_contract.py` (explicit File configuration in reusable runner only)
- `frontend/src/novel/WorkflowScopeGuards.test.tsx`
- `frontend/src/novel/WorkflowPanel.independent-audit.test.tsx` (unchanged copy of the frozen audit assertion; original archive untouched)

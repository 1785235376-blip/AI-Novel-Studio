# Original Adaptation lifecycle and pipeline surface

Status: **PARTIAL / CONTRACT_VERIFIED**. Real model admission is **NOT_CONFIGURED**.
This document describes engineering behavior, not model quality or a formal surface freeze.

## Authority and scope

- `AdaptationService` remains the original owner. Proposal, blueprint, review,
  task and recovery state lives in `NovelRepository.adaptation_proposals`:
  `adaptations.json` in File and the existing locked novel metadata in PostgreSQL.
  There is no parallel task store, manuscript store or adaptation workspace.
- Mainline source chapters come from the original ChapterRepository. Explicit
  project-scoped requests on a shared project require PROJECT rights. A branch
  lead does not acquire mainline authority by omitting `branch_id`.
- Registered branch requests always require `branch_manuscript_v1` and the
  existing BranchManuscriptService. Feature OFF and an empty branch cannot fall
  back to mainline. The target of a team adaptation is a real independent target
  project/branch, created through the original audited collaboration service.
- A local adapted project uses the original Novel/Chapter owners. All copies
  preserve the complete rich document, marks, attributes and stable block IDs.
  Target chapter identity is distinct from the source identity. Immutable source
  snapshots are evidence; they are not a second editable manuscript authority.
- Every source proposal API checks original current capability and scope. Task
  generation, review, apply, exact-task opening and target reuse additionally
  require current target capabilities. Mutation checks run again at commit and
  immediately before target work. Unknown persistence is fail-closed.

## Version, source and human review contract

Every proposal write compares its captured `revision` with the original owner
under the File project lock or PostgreSQL row lock. History retains immutable
prior envelopes; it does not recursively embed its own history or source copies.
`blueprint_revision`/`blueprint_history` remain compatible original fields.

When `adaptation_lifecycle_v1` is ON, original mutation endpoints require the exact
integer `expected_revision` (428 if missing, 422 if invalid, 409 if stale).
Shared-owner two-writer CAS and reviewed-target protection also apply to legacy
calls while this additive feature is OFF.

Approval binds blueprint, instruction, target and source digest. A generated
preparation/draft binds source stable ID/version/digest and target stable
ID/version/digest. Human acceptance records the full draft hash plus proposal,
blueprint, source scope and target scope binding. Apply uses that reviewed target
version, never the latest version fetched after approval. Source or target
changes reject the operation before a new write. Unknown older acceptance
records lacking the target binding cannot be promoted by guessing a current
version; cancel/recover and review a newly prepared draft instead.

The local preparation draft is an exact rich-document preservation flow. It is
not claimed to perform an intelligent rewrite. A model draft must satisfy the
original adaptation JSON schema and retain source provenance.

## Durable intent, cancellation and restart

Before target creation the source proposal persists a unique operation ID and
reserved project/storyline/branch UUIDs. These IDs are internal coordinator
inputs, not fields in unrelated public project-creation requests. Reserved-ID
validation rejects path-like IDs and existing/cross-owner scope identities.
File replay cannot delete an existing target during rollback; concurrent File
creation is process-coordinated. PostgreSQL uniqueness is transactional.

Each target chapter follows `CHAPTER_WRITE_INTENT` →
`DOCUMENT_WRITE_INTENT` → `CHAPTER_COMMITTED`; the stable chapter ID and exact
saved version/digest are checkpointed. No continuation uses chapter count as an
idempotency token. Project and document receipts are persisted before the next
external mutation.

- A known clean checkpoint can be explicitly recovered and resumes only the
  remaining work, on the same reserved project and existing chapter identities.
- A lost project/chapter creation response preserves `RECOVERY_REQUIRED` and the
  exact write intent. It never silently creates another target. Creation intents
  without a provable committed receipt require operator reconciliation; there is
  deliberately no endpoint that guesses ownership from a title or a chapter
  count. This remains a **PARTIAL** recovery boundary.
- Apply records `APPLYING` and the expected target version/result digest before
  entering the original save. A lost response can be explicitly reconciled only
  when that exact result is present at expected version + 1. An unchanged or
  differently edited target does not authorize replay.
- Cancellation clears the proposal/task execution claim. A late synthetic result
  cannot become reviewable. Cancellation during an uncertain write reports
  `RECOVERY_REQUIRED`, not a promise that no write happened. Its existing receipt
  may be reconciled without a second write.
- Restart does not launch workers or dispatch models. Interrupted RUNNING/APPLYING
  records remain durable; Task Center marks recovery-required work as unknown.
  Explicit recover fences the old execution claim before a new preparation.

## Model/runtime boundary

The production model adapter returns `NOT_CONFIGURED` with
`ADAPTATION_MODEL_ADMISSION_NOT_CONFIGURED`. No real provider is invoked through
this synchronous endpoint, and no original JobManager/admission integration is
claimed. The future real adapter must enter the existing JobManager and broker
preview/reservation, permission, privacy/egress and terminal-accounting paths.

Only an explicitly host-owned `MockProvider`, with mock mode enabled and packaged
runtime disabled, can execute the existing synthetic contract path. The current
DeepSeek development stand-in is recognized from its actual registered mock
adapter, not from its provider name. Unknown/real providers remain closed.
Synthetic output is **MOCK_ONLY**, never model-quality verification. Claim,
permission and source checks surround synthetic execution and publication.

## Bounded storage and recovery reserve

All limits are returned by `/adaptations/catalog`. Capacity errors are explicit;
there is no silent history pruning or eviction.

| Limit | Bound |
|---|---:|
| Proposals per project across branches | 100 |
| Source chapters / execution tasks per proposal | 40 |
| Immutable source snapshot bytes | 8,000,000 |
| Proposal history entries | 400 |
| Entries reserved for cancellation/finalization | 32 |
| Serialized proposal bytes | 32,000,000 |
| Bytes reserved for cancellation/finalization | 4,000,000 |
| One history envelope excluding source snapshots/history | 2,000,000 |
| Combined manifest draft bytes | 1,000,000 |
| Generation attempts per task, including failed attempts | 10 |
| Title / instruction characters | 200 / 8,000 |

Normal commands stop before reserved history/byte capacity. Multi-step
materialization and draft/apply claims check conservative remaining capacity
before any target mutation or execution. Terminal outcomes and cancellation use
reserved space. Recover does not reset the attempt count or remove history.
At capacity, records remain readable and cancellation remains available within
its explicit reserve; further normal work requires a new bounded proposal or
operator-managed archival outside this API. No implicit archival is performed.

## API catalog

Base: `/api/novels/{nid}/adaptations`. Scope uses the existing `branch_id` query
and `X-Session-Token` header. Bodies use `expected_revision` where applicable.

| Method | Suffix | Purpose |
|---|---|---|
| GET | `/catalog` | Capabilities, exact owner, states, flags, limits, runtime boundary |
| GET / POST | empty | List current-scope proposals / create immutable source proposal |
| PUT | `/{proposal}/blueprint` | DRAFT-only CAS revision, stable source map preserved |
| POST | `/{proposal}/approve` | Source-bound blueprint approval |
| POST | `/{proposal}/materialize` | Durable target/receipt workflow, completed result reuse |
| POST | `/{proposal}/tasks/{task}/generate` | Local preparation or explicit synthetic adapter |
| POST | `/{proposal}/tasks/{task}/review` | Exact draft/source/target acceptance or rejection |
| POST | `/{proposal}/tasks/{task}/apply` | Reviewed-target CAS through original owner |
| GET | `/{proposal}/tasks/{task}` | Exact authorized task, proposal revision and stale result |
| GET | `/{proposal}/history` | Original immutable history/checkpoint read |
| POST | `/{proposal}/actions/{cancel,recover}` | Explicit proposal lifecycle command |
| POST | `/{proposal}/tasks/{task}/actions/{cancel,recover}` | Explicit task lifecycle/reconciliation |

New history, exact-task and lifecycle action routes require
`adaptation_lifecycle_v1`, registered OFF by default. Turning it off hides
lifecycle-created proposals and blocks their mutations. Existing safe legacy
proposal workflows remain available; registered branch data never bypasses its
separate branch flag. Capacity/uncertain outcome conflicts are 409. Missing
sources/records are 404, denied capabilities 403, missing/invalid sessions 401.
Conflict payloads contain IDs/version coordinates, not manuscript content.

## UI and navigation

The original `AdaptationPanel` is still under 制作与分析 → 智能改编. It now consumes
catalog capability states and exact proposal revisions. Loading, empty,
unauthorized, disabled, missing configuration, conflict, review, failed,
cancelled and recovery states are visible. A blueprint conflict retains entered
text; reading a new revision does not silently replace it. Discard/reload is
explicit. Draft content, source/target identities, versions and digests are
available before acceptance. Duplicate mutation clicks are suppressed.

Task Center and Unified Review are read-through projections of the original
execution manifest. They carry proposal ID, task ID, proposal/source/target
versions and an exact owner pointer. They have no generic approve, retry or
executor path. Current source/target permissions and stale bindings are checked.

`App.navigateWorkspace` reopens the original Adaptation surface only after
reading the exact original proposal/task, matching its revision and rejecting a
stale result. It respects the existing editor namespace, epoch, cancellation
signal and dirty/composition/save guards. It never switches the manuscript
chapter or generates/applies work merely by opening. Missing, stale or
unauthorized pointers do not fall back to another proposal/task. The panel
receives `requestedProposalId`, `requestedTaskId`, `requestedRevision`.

The original `ScreenplayPipelinePanel`/`PipelineStatusPanel` now shows its original
pipeline's loading/empty/error/permission/conflict/manual-review states and
fences late responses after selection changes. It retains existing screenplay
approval and CAS authority. No visual redesign or new top-level module is added.
Scoped CSS only contains long evidence IDs and fields; DS-v1 tokens/primitives
and the shared AppShell remain unchanged.

## Verification and preserved tests

- Original `test_phase7_adaptation.py`: all five tests/assertions unchanged.
- Original authorization module: all three original test bodies, assertions,
  node IDs and skips unchanged. A reviewed fixture-only adjustment
  enables the real branch flag locally and initializes a true branch through
  production fork preview/apply as the already-authorized admin. The branch-only
  lead's rights are unchanged. The temporary collaboration runtime flag is
  restored in `finally`; the feature environment uses a scoped monkeypatch.
  Exact before/after file hashes, test-body hashes and diff are in
  `ADAPTATION_FIXTURE_EXCEPTION.json` and `.patch`.
- New File/PostgreSQL-marked lifecycle/projection tests cover independent writers,
  immutable history/reopen, rich documents, source-gone/source-stale, reviewed
  target conflicts, cancel/late result, uncertain writes, no replay, clean-checkpoint
  restart, exact apply reconciliation, capacity and flag behavior.
- Mounted API tests cover explicit project/branch permissions, empty-branch
  non-fallback, different mainline/branch text, source and target revocation,
  flag-OFF non-fallback, strict revision contract, reserved-ID concurrency and
  exact task opening.
- New UI tests cover original-panel conflicts, pending/disabled/denied states,
  exact revisions, repeated clicks, stale/missing pointers, late responses,
  dirty/composition guards and no manuscript execution from navigation.
- Hosted Playwright spec `surface-freeze-adaptation.spec.ts` is collected by the
  existing surface configuration. It uses real File API/React, synthetic prose,
  actual 409s and source/target states, reload, recovery and 1366/1440/1920 geometry
  captures. Browser launch was **NOT_RUN** locally after the known socket denial;
  no alternate local browser route was attempted.
- Real PostgreSQL is **NOT_RUN locally**. Marked tests require the hosted
  disposable PostgreSQL service; they do not substitute SQLite.
- No model/GPU/download/paid-provider execution, merge, release, deploy, protocol
  37 changes, migrations 001–020 changes or final UI redesign are included.

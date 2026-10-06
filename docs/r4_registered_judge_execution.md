# A03 registered local Narrative Judge execution

## Scope and status

This extends the original Narrative Judge on the Experimental PR39 branch. It does not change frozen PR37/38, merge, deploy, install a runtime/model, or claim real-model literary quality.

- IMPLEMENTED / INTEGRATED: explicit registered local-model selection, exact evidence/request preview, reviewed dispatch through the existing AuthorPreparer, Model Broker and JobManager, bounded output admission into existing review_threads, original-job recovery and cancellation.
- CONTRACT_VERIFIED: production-mounted File routes and synthetic transport contracts, React controls and TypeScript checks, as reported by the task's exact test run. Marked PostgreSQL cases use the same mounted contracts; a hosted PostgreSQL receipt is required.
- SYNTHETIC_PROTOCOL_ONLY: the shipped mock provider returns visibly labeled evidence-derived JSON, only when it receives the explicit Judge contract. It is not a real literary assessment, an independent model, or an injected test-only service adapter.
- REAL_RUNTIME_VERIFIED / REAL_MODEL_VERIFIED / USER_ACCEPTED: NOT_RUN for this increment. Existing registered runtime evidence remains distinct from actual Judge inference and quality verification.
- Local Chromium: NOT_RUN because the executor's launch restriction was already established. `frontend/tests/e2e/r4-judge-model.spec.ts` is an authored real-control journey for the existing hosted R4 browser suite; test collection does not establish browser execution.

## Actual production composition

`app/experimental/narrative_judge_model.py` binds the existing `NarrativeJudgeService` to `author_preparer`, `model_broker_service`, and `legacy_api.jobs` in the production experimental router. It does not create a second executor, model registry, ledger or review database.

The legacy in-process `JudgeAdapter` seam is preserved for existing contracts, but this production path does not depend on an injected adapter. It resolves actual registered TEXT routes from the original broker. Runtime absence is a visible blocker; deterministic review remains available.

The existing `narrative_quality_judge_v2` flag keeps its original world/planning/inbox dependencies. Model endpoints additionally require `model_broker_v2`, `author_context_inspector_v2`, the trusted host session, current write permission, and the original run actor. Default-off and `V1_ACCEPTANCE_MODE=true` remain server-enforced. Generic generation acceptance is blocked for the trusted `narrative_judge_model` origin by `JUDGE_DRAFT_ONLY`.

## User path

1. Experimental workbench → 作品审稿. Select saved chapters and run the deterministic check.
2. In the selected check, choose “查看已注册本地审稿路线”. Opening the panel alone does not discover routes, launch a model, or run a Judge.
3. Select an available registered local TEXT model, then “准备准确模型审稿预览”.
4. Inspect the actual adapter-facing request, full selected chapter evidence, source versions/digests, actor/scope, versioned rubric, exact provider/model/registered identity, price source/currency/applicability, project budget snapshot/version, excluded sources and bounds. The built-in mock route is explicitly labeled synthetic.
5. Check the reviewed-receipt checkbox and choose “明确发送此次本地模型审稿”. Preview alone does not reserve budget or authorize execution.
6. Use “查询原任务并核对模型证据” to reconcile the original job and admit only valid model opinions. The underlying job uses the original persistence and budget ledger. Reloads never launch a replacement job.
7. Review/ignore/reopen individual opinions through the original review authority and give a reason. Optional revision linkage records evidence only. No action applies text or promotes Canon.

## Exact scope and bounds

- The source is the deterministic run's exact saved chapter selection, not the currently open editor buffer. Every selected source's content/version/privacy/branch/metadata is captured, and existing reviewed world/planning freshness is retained conservatively.
- Only selected chapter IDs, versions and complete content enter the bounded Judge instruction. The original AuthorPreparer is used with `source_mode=NONE` and automatic context, style and planning disabled so manuscript tails or derived context cannot reenter the request.
- The source strategy is explicitly `EXACT_SELECTED_CHAPTER_EVIDENCE`; using `NONE` refers only to automatic author-source injection. The preview displays the entire final request with the selected evidence present.
- Source JSON plus versioned instructions must fit 18,000 characters. Excess input is rejected, never silently truncated. The original deterministic selection limit remains 20 chapters / 100,000 characters; model review has the stricter limit.
- Execution supports only `LOCAL_ONLY` and a known zero-microusd reservation on the explicitly selected route. A local endpoint does not establish free usage. Missing or nonzero price, unavailable model, expired price, changed budget, or revoked registration fails closed. There is no cloud fallback.
- One original job per run, no automatic replay, up to 32,768 UTF-8 output bytes and a 120-second job deadline. The original JobManager enforces output and deadline bounds.
- Exact rubric `narrative-model-evidence-v1`, version 1; maximum 20 model opinions, 1–5 references each, quote maximum 2,000 characters. Each opinion has category, explanation, suggestion, and uncertainty boundary. No numerical literary score is emitted.
- Parsing accepts only the exact JSON object with `opinions`; duplicate keys, nonfinite values, markdown fences, unknown fields, coercions and oversized input are rejected. All opinions are validated before any is published. Chapter/version, single-paragraph location, Unicode offsets and exact quotation must all match selected sources.
- An empty opinions list is abstention. Invalid output becomes a failed model assessment while all deterministic findings remain intact.

## Recovery and safety

A durable admission record precedes broker reservation and JobManager start. It stores the original job ID, reservation, preview digest, bounds, and receipt state. Simultaneous duplicate sends can produce only one admission. A lost response/start uncertainty preserves the same original IDs and `UNKNOWN_NO_AUTOMATIC_REPLAY`; absence of a job does not prove no upstream dispatch and does not release an uncertain hold.

Restarted persisted jobs lack the live author authorization closure. Their output is not admitted as model findings; users can inspect the original job/accounting receipt, but the coordinator will not replay it or create an independent replacement. Repeated unchanged refreshes do not add findings or history versions.

Cancellation first marks the run's model execution cancelled, fencing later send and output publication, then cancels the original job. It remains available when selected sources have changed. Already sent information cannot be recalled and ambiguous upstream reservations are not automatically released. Shared JobManager cancellation is also available if a feature is disabled.

Current session/actor/branch/source/route/price/budget and exact request checks occur before preparation, reservation, executor admission and final adapter send. The coordinator rechecks current authority after ledger persistence. Model opinions remain separate from deterministic findings, and generic generation Accept is rejected. Stale reads hide old prompt/evidence/opinions. Conflict payloads contain only record identity/version/status, not stored prompt/history.

Model identity is recorded, while independence remains UNVERIFIED. The same model with a different prompt is not described as independent; multiple agreeing models still do not prove correctness.

## Verification files

- `tests/test_r4_judge_model.py`: File / marked real-PG, both `/api` and `/api/v1`; shipped registered path, captured exact transport, original job/ledger/review persistence, no replay, cancellation/restart, source and permission fences, last-send revocation, route/budget change, strict parser and output bounds.
- Existing `tests/test_r4_style_judge.py` and `tests/test_r4_style_judge_mounted.py`: deterministic and original review compatibility.
- `frontend/src/experimental/NarrativeJudgeModelPanel.test.tsx`: deliberate selection/preview/dispatch, reviewed digest, duplicate-click suppression, hidden stale previews, unknown original-job recovery and late callback suppression.
- Existing `frontend/src/experimental/StyleReviewPanels.test.tsx`: preserved deterministic rule and STYLE flows.
- `frontend/tests/e2e/r4-judge-model.spec.ts`: actual React controls and production File API using existing trusted broker fixture on ports 8022/5182. Includes full exact preview, 1366/1440/1920 viewport evidence, original-job settlement, advisory review, reload persistence, manuscript nonmutation and stale redaction. No mocked HTTP business responses.

Real user runtime compatibility, true model inference quality, independent-model comparison, Windows acceptance and hosted PostgreSQL/browser execution require their own verified receipts. This implementation alone does not establish them.

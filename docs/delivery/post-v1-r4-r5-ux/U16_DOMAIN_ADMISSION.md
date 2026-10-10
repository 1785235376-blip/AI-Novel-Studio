# U16 original domain admission and durable batch receipts

## Requirement reconciliation

This extends the original U16 scope. The initial implementation already provided proof/export, serial preflight/confirm/dispatch/stop, failed-only retry, snapshot fences and the exact synthetic image executor. Those operations were reused, not reimplemented.

Closed deterministic gaps:

- Preserve per-attempt status, original task and reservation IDs, original approval version, snapshot digest, known/unknown cost state and subsequent reconciliation. Failed-only retries retain earlier attempts and approvals. A known completed media task interrupted before the batch result commit can be adopted from its original receipt without another generation or registration.
- Skip identical satisfied proof/export and approved current media outputs. Original assets must still be authorized and readable. A mere generated candidate is not a satisfied result. Already-approved original voice results can also be skipped; locked or unreviewed voice segments cannot be sent.
- Reuse B01's existing local catalog, independent project copy, version, diff/update/history/revert for the `safe_batch` template type. Its strict payload contains only proof, export format and skip-satisfied parameters. It cannot carry source IDs, credentials, budget, runtime permissions or execution approval. The exact project-copy version is included in each batch snapshot.
- Admit registered local IMAGE adapters through the existing broker's exact preview/route/fingerprint/price/source/configuration receipt, then original `reserve`, `guard_dispatch`, `finalize` and `reconcile`. Original `MediaService` remains the executor and media/asset review authority. A storyboard additionally requires the original approved shot plan. No new provider router or workflow executor was created.
- Add original TTS resolver metadata to the same broker route catalog. Original provider IDs are resolved explicitly without health checks or network calls; `auto` is never resolved during catalog reads. Endpoint and credential identities are hashed/opaque, not exposed. Prices remain unknown until the existing broker price authority provides a current estimate. Localhost is not evidence of a free request.
- Batch selected jobs already reviewed and queued by B03. A shared `DirectedAudiobookService.execute_local_job` serves the standalone and batch routes through the original `AudiobookService`, original durable audio queue, original decoder and original asset writer. Batch source/privacy/actor/approval/configuration/budget guards run at the actual send boundary and before result acceptance. No repeat of an entire chapter or locked segment is introduced.
- A batch-adopted voice job and its generated-record projection are hidden from legacy and standalone controls outside the server-only batch context. Audio assets retain both their original voice and batch feature fences. Listening and accepting are separate, snapshot/version-bound actions.

## Safety and recovery contract

- Existing flags remain default OFF and V1-forceOFF. No new execution flag or startup job is introduced. Optional template, voice, media and broker authorities must be enabled for the corresponding operation.
- Maximum concurrency is one per batch; maximum batch size is 20. The broker additionally enforces original project reservation concurrency. Each explicit request runs one stage. No automatic startup, restart, fallback, scheduler, download loop or GPU-control claim exists.
- The admitted estimate must be exactly zero USD, bound to the original broker receipt with `LOCAL_ONLY` and zero task limit. Unknown/nonzero estimates, remote routes, missing workflow registration, changed credentials/configuration, expired prices, changed sources or revoked authority are rejected before send.
- A zero estimate is not an invoice. A non-attested upstream invoice stays `UNKNOWN_UPSTREAM` even after a usable output arrives; the batch becomes UNKNOWN and cannot continue or accept that candidate. The original broker's explicit reconciliation is required first. A positive reconciled bill does not expand the original zero budget and remains blocked for batch continuation.
- Original receipts are queried explicitly. No caller-supplied claim of success or “not charged” substitutes for an executor/ledger terminal record. Running/ambiguous tasks are never automatically replayed. Failed-only retry makes a fresh reservation under a fresh explicit confirmation while retaining prior approval and attempt records.
- Stop prevents subsequent effects and discards late output through original guards; it cannot retract an already sent request. Unknown cost holds remain retained. Cancellation never deletes original source, history, trash, assets or cost records.
- Source changes conceal obsolete content/configuration while retaining authorized sanitized approval/attempt/cost receipts. Hidden/deleted/foreign dependencies conceal the batch. Old preflights whose expanded contract no longer matches require a fresh preview; no migration silently reauthorizes them.
- Experimental metadata remains in original File/PostgreSQL scope transactions. Audio execution stays in the original actor/branch-scoped audio sidecar store; this extension does not claim that sidecar became a PostgreSQL queue. Content writers and asset identities are unchanged.

## Actual UI flow

1. In B01 copy the built-in proof/export preset or a validated imported preset into this project. Use existing compare/update/revert controls if needed.
2. For real registered media, use Model routing's IMAGE capability; for original queued B03 jobs, use AUDIO. Select the exact saved source, a local route and a zero limit. Configure a dated zero estimate through the original price controls when supported and justified. Unknown cost is displayed as unknown.
3. In Safe batches select chapters/ranges, optional preset, current media brief and exact broker preview, or matching reviewed/queued voice segments. The preview lists versions, parameters, resource limitations and cost state. No request is sent.
4. Confirm the exact snapshot and zero budget. Dispatch one stage at a time. Current authority is checked again at each boundary. Stop remains a separate available control.
5. Inspect retained attempts and original cost receipts. Query the original terminal receipt after any required broker reconciliation. Preview/listen to the decoded candidate, then explicitly accept it through the original asset authority.
6. Repeat the same satisfied selection to verify SKIPPED outputs and no second reservation, acceptance or asset registration.

DS-v1.0 primitives/tokens and the existing workbench/shell are retained. No shared geometry, theme or CSS change was needed. Controls clear their context through existing scope remounts. The onScopeChange addition to ModelBrokerPanel's existing author preview preserves the parent's exact source-item receipt flow.

## Verification

Authored/executed synthetic tests use `../r2-run.sh`, the pinned pnpm install and the existing isolated venv. No real credentials, manuscripts, paid calls, GPU process, runtime configuration change, remote push, merge or deployment was performed by this worker.

- `tests/test_r4_batch_admission.py`: File and opt-in actual PostgreSQL parameters; original registered-media reservation/finalization, zero estimate vs unknown bill, explicit reconciliation, interruption adoption, positive-bill blocking, satisfied assets, retained failed attempts/original approvals, B01 version fences, real HttpAudioProvider with in-process synthetic transport, original B03 queue/decoder/assets, generic-route concealment, hidden source, provider drift and cancellation during send.
- `tests/test_r4_batch_admission_mounted.py`: actual production app composition at both `/api` and `/api/v1`, trusted host/session authority, B01 instance fence, broker feature revocation, original registered-media review/skip and full original voice/broker/decoder/reconciliation/acceptance journey. Only audio HTTP transport is synthetic in the AUDIO case.
- Impacted suites include prior portable/batch, broker, voice/subtitle, original audiobook, audio provider/configuration, declarative templates and production/media contracts. Exact totals and tested tree/commit are in the parent checkpoint; skipped PostgreSQL parameters are not passes.
- `SafeBatchesPanel.test.tsx`, `ModelBrokerPanel.test.tsx`, existing `DeclarativeTemplatePanels.test.tsx`: real fetch-bound request/state tests for exact B01/IMAGE/AUDIO inputs, explicit approvals, no auto-start, source/context invalidation, retained receipts, unknown no-replay and separate voice preview/acceptance.
- `frontend/tests/e2e/r4-batch-admission.spec.ts`: real File/API/React journey for B01 copy, original broker synthetic-image receipt, three explicit stages, separate acceptance and all-satisfied skip with a single ledger reservation. The test is collected by the existing R4 wildcard profile. Local Chromium was not retried after the established EPERM blocker; actual hosted execution belongs to the parent's CI checkpoint.

## Remaining real-runtime boundaries

Production AUDIO dispatch is wired to the shipped original resolver and executor, not a test-only injected cost hook. Actual TTS still requires a configured, reachable original local endpoint, valid model/voice configuration, separately approved text/voice use and current original broker pricing. Registered IMAGE execution requires a host-registered runnable adapter/workflow plus its original broker route. This worker verified protocol/decoder/storage behavior using synthetic providers/transports, not real synthesis quality, runtime availability, GPU capacity or performance.

Remote media/TTS egress is still rejected. Original brief-media execution returns image candidates; a VIDEO batch executor cannot be asserted from static modality declarations. No controlled GPU scheduler/free-VRAM authority exists in this scope, so external GPU occupancy is reported unknown. Windows/native media/editor software, real PostgreSQL endpoint and real Chromium execution remain separately tracked by the parent.

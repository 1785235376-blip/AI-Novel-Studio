# M4 AI Execution Layer: bounded local-text graph execution

The user's 2026-10-10 instruction names the next milestone **M4 AI Execution
Layer**. That current scope supersedes the earlier roadmap's M4
Text/Screenplay/Agents label. This document describes its first bounded execution
slice, not an Image/Video studio, real-model benchmark or completed GPU scheduler.

## Six requested modules and their existing owners

| Module | Implementation and owner reuse | API/UI boundary |
|---|---|---|
| Model Provider Adapter | `app/model_execution.py` consumes the original `TextProvider`, registries and `TextModelNode`; it does not register providers. | Graph model-capabilities and the graph's local-model selector show supported current routes and explicit blockers. |
| Model Router | `app/creative/ai_execution.py::ModelRouter` delegates candidate facts, exact-route selection, price, license, admission and settlement to `ModelBrokerService`. | A user selects one route and previews it. No fallback or independent ranking registry is introduced. |
| Creative Graph Node Runtime | `CreativeGraphNodeRuntime` composes original WorkflowRun claim/completion/review with original JobManager preparation and asynchronous execution. | Explicit prepare → preview → confirm → dispatch → refresh → review actions on one saved graph run. |
| Local model invocation | A transient, exact `PreparedTextInvocation` uses one original enabled external Ollama/llama.cpp adapter, or an explicitly consented built-in synthetic adapter. | No endpoint, credential, executable, model path or provider result can be submitted to graph APIs. |
| API Provider | A nonexecuting reserved interface; existing native/API provider implementations remain unchanged. | `RESERVED / API_PROVIDER_EXECUTION_NOT_ENABLED`; there is no cloud dispatch button or local-to-cloud fallback. |
| Capability matching / scheduling | Original TEXT/generate/stream capability checks, current model/adapter identity, locality, license and known-zero price. Original broker admission enforces its project concurrency limit; WorkflowRun orders dependencies and JobManager owns workers. | Shows eligibility and the original task receipt. No claim of VRAM fit, GPU allocation, model unload, global fairness or literary quality. |

Provider Runtime 2.1D remains a separate **read-only diagnostic service**. Its
current Model Center snapshot has no positive execution authority. Neither its
decision shape nor discovery advertisements can authorize this execution path.
The legacy `app/router.py::ModelRouter` and its older fallback semantics remain
unchanged; the new namespaced facade does not use them for graph execution.

## Activation and schema compatibility

All four explicit server flags are required:

```
ai_execution_v2,narrative_production_v2,model_broker_v2,author_context_inspector_v2
```

They default off. `V1_ACCEPTANCE_MODE` overrides them off. Adding this surface
does not change the published forty-feature opt-in tuple or enable an old model.

The original seven-definition `GraphInput` schema 1 and its catalog remain
unchanged. A user explicitly adding `text_generate` promotes that graph to
schema 2. Schema 2 requires the new gate even if it contains only local nodes.
Its finite text node has a required TEXT input, optional DIRECTOR_NOTES input,
an instruction of at most 4,000 characters, a 1–2,048 output-token limit and one
DRAFT output. Model-produced drafts have distinct `MODEL_PROPOSAL` provenance.
Old manual/local ports cannot forge that provenance.

At most one model node is admitted per selected run. Its selected output path
must include an explicit human-review node. Disconnected local-only selections
retain their original semantics; selecting a model without its review gate is
not executable. Model output is never reused by the local-rule cache.

## HTTP and interaction contract

Routes exist under `/api` and `/api/v1`, using the existing Studio project and
branch authority, private no-store responses and current host authority:

| Method and suffix after `/projects/{project}/studio` | Purpose |
|---|---|
| GET `/graphs/model-capabilities` | Read current local-route eligibility and reserved API-provider state. No inference, install or dispatch; existing bounded metadata/evidence checks may run. |
| POST `/graph-runs/{run}/model/preview` | `{expected_version, route_id, allow_synthetic}`. Persist an original broker preview and a source-bound review receipt. |
| POST `/graph-runs/{run}/model/dispatch` | `{expected_version, reviewed_preview_digest}`. Admit the exact reviewed local request once. |
| POST `/graph-runs/{run}/model/refresh` | `{expected_version}`. Reconcile the original worker/accounting receipt; never replay or replace it. |

Original run execute/approve/reject/cancel routes remain their state owners.
Execute advances only the local dependencies, stopping at the model boundary.
Preview, load, save, reload and refresh do not run a model. Dispatch requires a
separate checkbox acknowledging the exact prompt, source, route and limits.
Synthetic routes additionally need explicit synthetic consent.

Model runs add an explicitly versioned `model_runtime` envelope with contract
`creative-graph-model/1`. The original no-model run shape is retained. A stored
`model_called: false` while a job is admitted/unknown means its last stored
receipt has not observed dispatch; it is not proof that an uncertain call never
ran. The UI asks the user to reconcile the receipt. `external_calls: 0` denotes
no remote/cloud invocation in this local-only path; synthetic versus real local
protocol execution is shown separately. `quality_verification` remains NOT_RUN.

The existing graph workspace, primitives, design tokens and shell slots host
these controls. No AppShell, ModuleSwitcher, Model Center or protected visual
system is replaced. Losing scope, host identity, permission or a feature clears
private model previews and suppresses late UI responses.

## Execution and authority fences

1. Existing project incarnation, exact scope/actor, graph version/digest, typed
   upstream output and node parameters bind the preview. The original broker
   binds route implementation, model/runtime evidence, budget and price.
2. Host authority captures the current registry/bootstrap instance and token
   binding generation, not merely a token string. Re-registering the same token
   does not revive old consent or a running job. Forwarded headers and a remote
   collaboration-only session cannot impersonate the local host.
3. A short original WorkflowRun transaction records the model claim and one
   job ID before broker reservation or worker start. Model I/O never holds the
   graph scope transaction. The original scope→project lock order is retained.
4. The original JobManager receives a host-prepared, chapter-independent request.
   No dummy chapter, manuscript context, canon lookup or duplicate job queue is
   created. The prepared invocation and live guards are transient; restart does
   not reconstruct them from persisted JSON.
5. Current flags, origin, host, project incarnation, graph/source/route identity,
   cancellation and limits are checked during preparation, at the actual
   adapter-facing hop, at emitted events and before publication. External local
   adapters have a preparation guard inside their original execution lock,
   before any managed-runtime launch path. Managed adapters are unavailable to
   this slice; no model process is automatically started or stopped.
6. Bounds are 32,000 UTF-8 prompt bytes, 32,000 generated bytes, 8,000 reviewed
   characters and at most 180 seconds per model invocation, additionally limited
   by the original run deadline. Cancellation is cooperative; a blocked external
   server might finish later, but its late output cannot become an accepted draft.
7. Broker scope mutations keep the actual project-owner lease through commit.
   Job persistence also respects its graph incarnation, so late settlement or
   status writes cannot attach an old task to a same-slug replacement project.
8. A successful provider response alone is insufficient. The exact job must be
   completed with a durable terminal hook and original ledger SETTLED at zero
   cost before output reaches graph review. Unknown upstream/accounting retains
   its hold and never permits replay. A known pre-dispatch release can be a
   recorded receipt without being a successful output.
9. Refreshing an unchanged receipt does not consume history. Preview/admission
   limits preserve room for terminal cancellation/review. Missing or ambiguous
   admission is retained as UNKNOWN_NO_AUTOMATIC_REPLAY.
10. Human review uses the original domain.review permission, current source
    and exact output digest. Review does not apply text to manuscript, canon,
    assets or a model catalog. Generic generation URLs cannot disclose, cancel,
    retry or apply these graph jobs; the existing broker recovery view exposes
    accounting/status only, not graph text.

## Verification and remaining acceptance

Focused tests use actual original JobManager worker threads, original File and
PostgreSQL owners, exact built-in MockProvider and mocked external local transport.
They distinguish protocol execution from real model inference. Original local
graph/author/provider regressions remain intact. The final milestone report
binds actual commands, source hashes, counts, retained development failures and
fresh PostgreSQL lifecycle receipts; intermediate source-drift runs are not final
acceptance.

The isolated browser fixture is test-only and never imported by the product.
Its current host identity and synthetic call counter support real HTTP/UI tests;
collection and fixture self-checks do not prove that Chromium launched. Browser
launch/geometry evidence and exact-commit hosted CI are reported separately.

Real local model inference/quality, user Windows/GPU acceptance, memory-aware GPU
scheduling, paid/API provider activation, tool use and larger Image/Video graph
execution remain **NOT_RUN / outside this bounded slice**. API provider support
is a reserved contract, not a hidden cloud implementation. There is no new
migration, credential flow, download, model install or launch permission here.

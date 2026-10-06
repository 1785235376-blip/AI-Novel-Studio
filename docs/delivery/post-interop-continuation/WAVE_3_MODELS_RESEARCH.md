# Wave 3 — existing models, evidence, research and vectors

Date: 2026-10-06. Original starting baseline: PR #42, `e58c72b04182cd374af092314386b90f8250a173`. Recovery base: verified published `4d736c0d14bdcd12d0ad3cc7146553971654620b`, tree `6b8269fb95e695178ce4c587c9fc729275d0e848`.

## Recovery evidence boundary

The executor was replaced at approximately 15:42 UTC and uncommitted Wave 3 files became unavailable. The owned changes were reconstructed from the implementation's tool-call context using required baseline anchors. All anchors matched the verified published recovery base. Nine owned Python implementation files and three restored Python test modules pass AST parsing; the owned diff check passes. Fresh post-recovery focused backend execution passed: 276 passed, 97 unchanged profile skips, one warning across the 14 listed files (18.11 seconds), using the restored approved Python environment. Recovered frontend/runtime/type checks remain NOT_RUN because Node dependency setup is blocked; hosted CI is required.

The previous local results, 276 backend passes with 97 unchanged profile skips and 31 frontend passes, are HISTORICAL_PRE_RESET_SOURCE_ONLY. They are not verification of recovered bytes. Prior TypeScript/token checks and real loopback transport results have the same boundary. The new focused backend receipt verifies the recovered backend scope only. Hosted CI and recovered frontend receipts remain required for aggregate product acceptance. No historical PR evidence or blocked independent audit was changed or restarted.

## Original-scope traceability

| Original scope | Reconstructed concrete continuation | Current boundary |
| --- | --- | --- |
| A06 Explainable model broker | Privacy First, Balanced and policy aliases; Local First places legal local routes ahead of preferred cloud routes. Explicit `allow_cloud_fallback` is needed for cloud proposals under Local First. Optional license-confirmation admission uses original Model Center facts and is fenced at dispatch. Cost/context/availability/hardware/source-privacy checks continue through the original broker and executor. | PARTIAL. Reconstructed implementation: focused backend CONTRACT_VERIFIED; frontend recheck NOT_RUN. Real model quality and paid billing NOT_RUN. |
| A07 Benchmark/capability evidence | Read-only capability profiles separately label catalog claims, detection, contract testing, local benchmarks and explicit review of exact completed/current saved outputs. User verification binds exact evidence version and loses currency after set/runtime/evidence changes. It never grants a global quality score or routing weight. | PARTIAL. Recovered focused backend CONTRACT_VERIFIED; frontend recheck NOT_RUN. Real hardware/model quality LOCAL_REQUIRED; throughput/memory/cold-start values stay unknown when unmeasured. |
| A10 Research Library | Original-file replacement, full bounded history, owner-only revision export, archived-source inspection, restore into a new PRIVATE revision. Versioned note edit/delete/history and citation repair for the author's own active sources. Image width/height/format metadata without OCR claims. | PARTIAL. Recovered File workflows REAL_VERIFIED by the focused tests; real PostgreSQL remains locally NOT_RUN. Real public-web compatibility, Windows containment and OCR/vision remain unverified. Research is separate from Canon. |
| Existing `visual_embeddings`; R3-GAP-06, associated A06/A07/A10 | Real local Ollama `/api/embed` transport guarded by existing discovery validation/registration/license/locality/enablement. Scoped Character/Scene/Asset/Research picker, per-index original-registration selection, dimension constraint, edit/rebuild/cancel/invalidate/remove/query. Research changes atomically clear vectors and fence in-flight callbacks. | PARTIAL. Adapter contract and real loopback transport recheck PASS on recovered bytes with synthetic vectors. Earlier transport test used a real loopback server returning synthetic vectors, never a real model. Actual Ollama inference and semantic quality LOCAL_REQUIRED / NOT_RUN. Image embeddings require another configured host provider. |
| R3-GAP-05 Provider profiles | Existing credential-free profile contracts retained. | BLOCKED on verified OS-vault host integration. No new credential endpoint or model registry. |

## Authorities, privacy and cancellation

- Reuse the original ExperimentalStore scope-atomic File/PG document, Model Center, Research, asset and screenplay services. No second manuscript, model or task authority.
- Parent composition: `embedding_service.research = research_library_service`; `embedding_service.discovery_bridge = local_ai_discovery.route_bridge`. These shared composition edits are not owned by the Wave 3 reconstruction scripts.
- Embedding-only discovery recognition is gated by `visual_embeddings`; default OFF and V1 acceptance preserve legacy rejection. Registration remains disabled after restart until explicit revalidation/enablement. No startup inference.
- Positive locality evidence is mandatory. Hosted/remote Ollama declarations, revoked registration/license, changed model evidence, malformed dimensions, nonfinite or zero vectors and wrong response identity fail closed. Metadata validation is followed by final source/authority checks before dispatch. No pull, install, launch or paid call was performed.
- Research indexes and indexes that reference owner-private assets are owner-private. Query checks current sources/model/index version before and after inference; a stale badge is not the only protection.
- Source replacement, metadata edits, revocation and deletion clear derived Research vectors atomically and remove build tokens. Late responses cannot republish invalidated work.
- Cancel invalidates the build token. Already dispatched synchronous transport can take until its bounded timeout to end. Restart does not automatically replay.
- Research restore creates a new version and defaults to PRIVATE; old citations stay stale. Revoked or newly private third-party citations cannot expose old note history. Own-source citation repair preserves the author's writing but requires explicit current citation selection.
- Source retention is bounded to 20 prior revisions and 32 MiB stored source JSON. Revocation/deletion are not blocked by quota and can retain one additional bounded archival snapshot. Owner-only original-version export remains available.
- R1/R2/R3 permission, revocation, terminal/error and unknown-cost semantics must pass the parent aggregate regression. Interop 1.0 wire/consent/authority fields are untouched.

## API changes

Under the original `/novels/{nid}/experimental` scope and feature gates:

- Broker preview policies: `PRIVACY_FIRST`, `BALANCED`, conventional aliases, `allow_cloud_fallback`, `require_confirmed_license`, policy explanation and license evidence.
- `GET model-benchmarks/profiles`; `POST model-benchmarks/evidence/{id}/review`.
- `GET research-library/sources-archive`; `GET sources/{id}/history`; `GET sources/{id}/history/{version}/original`; `PUT sources/{id}/file`; `POST sources/{id}/restore`.
- `PUT research-library/notes/{id}`; `POST notes/{id}/delete`; `GET notes/{id}/history`; `GET note-repairs`.
- `GET embeddings/providers`; `GET embeddings/sources`; `PUT embeddings/indexes/{id}`; explicit `cancel` action. Existing endpoints gain current actor/privacy/source guards and no-store responses.

## Data compatibility

No SQL migration or historical migration edit. The existing generic scope document stores optional index selection/privacy fields, retained source histories and the additive `benchmark_evidence_reviews_v2` collection. No real user database or V1 data was opened or migrated. Legacy sources remain live projections; existing native sources and default-provider indexes continue to load. Missing old history is not invented. New Research vector definitions cannot execute on an older application and should remain disabled during downgrade. Existing backups remain the rollback route.

## Verification inventory

The adjacent JSON records the reconstructed owned-file hashes, commands and current statuses.

- Current recovered verification: AST parse and owned diff-check PASS; fresh focused backend 276 passed, 97 unchanged profile skips, one warning across 14 files. Recovered frontend/TypeScript checks NOT_RUN because Node dependency setup is blocked, pending hosted CI.
- Historical pre-reset focused backend (separate earlier source): 276 passed, 97 unchanged profile skips, one warning across 14 files. The real PostgreSQL availability gate was unchanged; no local PostgreSQL endpoint was configured.
- Historical pre-reset frontend: 31 passed across six panel files, including eight new interaction tests. Historical TypeScript and token guard PASS.
- Restored hosted browser journey: `frontend/tests/e2e/r4-wave3-continuation.spec.ts`, selected by existing R4 glob. Real File API/React flow covers import, file replacement, cited-note editing, repair, private restore, source picker, NOT_CONFIGURED index persistence, reload and 1366/1440/1920 geometry/screenshots.
- Local Chromium remains BLOCKED by the previously established platform restriction. It was not retried/rerouted. Browser journey remains NOT_RUN pending hosted execution.
- Actual model inference, semantic retrieval quality, real GPU/Windows, image embeddings and paid/cloud billing remain NOT_RUN / LOCAL_REQUIRED.

Protocol reference: [Ollama Generate embeddings](https://docs.ollama.com/api/embed), checked in the pre-reset implementation on 2026-10-06. The adapter uses `truncate=false`: over-context text fails explicitly. Large references can require splitting; automatic semantic chunking/reranking is not claimed.

## Opus handoff

Keep the existing AppShell, Panel, Button, Badge, Field, StatusMessage and design tokens. No protected design-system redesign was made.

- Broker: added policy and explicit fallback/license controls. Changed selection invalidates old approval. Unknown metrics remain visibly unknown.
- Benchmark: evidence profile and exact-output human-review form. Catalog/imported/synthetic evidence never implies real-model quality.
- Research: preserve input on conflicts; distinguish metadata edit from file replacement; explain private new-version restore. History export, archived-source review and citation repair are explicit. Revoked citation evidence must stay hidden.
- Embedding: original scoped-source picker is primary; raw IDs stay advanced. Explain text-only Ollama vs IMAGE sources. BUILDING is a phase without a fabricated percentage; cancellation is available separately from pending work. Missing default provider remains NOT_CONFIGURED even if an original registration can be selected for an individual index.

Final art direction remains for the requested Opus pass. Historical acceptance status and evidence are frozen.

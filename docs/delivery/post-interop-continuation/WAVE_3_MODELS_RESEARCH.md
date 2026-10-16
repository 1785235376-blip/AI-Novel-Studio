# Wave 3 — existing models, evidence, research and vectors

Date: 2026-10-06. Original starting baseline: PR #42, `e58c72b04182cd374af092314386b90f8250a173`. Recovery base: verified published `4d736c0d14bdcd12d0ad3cc7146553971654620b`, tree `6b8269fb95e695178ce4c587c9fc729275d0e848`.

## Current verification and recovery boundary

The recovered Wave3 implementation was published in `dd34bf213020da488ae76ee07a43d416496a52c7`. Its exact staged code tree `8a0f4952e61f40c2f52cb6f156f607a9d6c9298d` passed the complete frontend unit suite (1175 passed, 8 inherited opt-in skips) and TypeScript. The temporary Node dependency blocker was resolved; it is not the current frontend status. The [Wave3 staged receipt](WAVE_3_STAGED_VERIFICATION.json) also records 29 new backend passes with 22 PostgreSQL variants deselected for hosted execution.

A later P2 correction was published in `d18e874e20117bce6cce15366b64d2c1c129b1bc`: disabling Research now hides only its dependent indexes, while independent Character indexes remain usable. Its focused checks passed 71 backend cases with 64 unchanged profile skips and 5 frontend cases, plus TypeScript and diff checks. Separate verification of this correction also passed. The subsequent exact core staged tree `04c0cd285757fb04d8917d95828421ad7a76c963`, which includes the correction, passed the complete frontend suite (1222 passed, 8 inherited opt-in skips), TypeScript and 214 focused backend cases; 198 PostgreSQL variants were deselected. See the [core staged receipt](WAVE_2_STAGED_VERIFICATION.json).

These are source-specific local receipts, not final-source acceptance. Complete final-source hosted File, PostgreSQL, browser and Windows CI remains pending. Real model inference and semantic quality remain NOT_RUN. Focused and complete-suite counts overlap and must not be summed.

The workspace replacement at approximately 15:42 UTC interrupted earlier uncommitted work. Recovery used the verified published baseline, followed by fresh checks. The pre-reset 276 backend/31 frontend results remain explicitly historical and are not reused as evidence for recovered bytes. The later recovered 276-pass focused backend receipt is a distinct, source-labelled checkpoint. No immutable historical PR evidence or previously blocked independent audit was changed or restarted.

## Original-scope traceability

| Original scope | Implemented continuation | Current boundary |
| --- | --- | --- |
| A06 Explainable model broker | Privacy First, Balanced and policy aliases; Local First places legal local routes ahead of preferred cloud routes. Explicit `allow_cloud_fallback` is needed for cloud proposals under Local First. Optional license-confirmation admission uses original Model Center facts and is fenced at dispatch. Cost/context/availability/hardware/source-privacy checks continue through the original broker and executor. | PARTIAL. Source-specific backend, frontend and TypeScript checks passed; final-source hosted CI pending. Real model quality and paid billing NOT_RUN. |
| A07 Benchmark/capability evidence | Read-only capability profiles separately label catalog claims, detection, contract testing, local benchmarks and explicit review of exact completed/current saved outputs. User verification binds exact evidence version and loses currency after set/runtime/evidence changes. It never grants a global quality score or routing weight. | PARTIAL. Source-specific backend, frontend and TypeScript checks passed; final-source hosted CI pending. Real hardware/model quality LOCAL_REQUIRED; throughput/memory/cold-start values stay unknown when unmeasured. |
| A10 Research Library | Original-file replacement, full bounded history, owner-only revision export, archived-source inspection, restore into a new PRIVATE revision. Versioned note edit/delete/history and citation repair for the author's own active sources. Image width/height/format metadata without OCR claims. | PARTIAL. Recovered File workflows REAL_VERIFIED by the focused tests; real PostgreSQL remains locally NOT_RUN. Real public-web compatibility, Windows containment and OCR/vision remain unverified. Research is separate from Canon. |
| Existing `visual_embeddings`; R3-GAP-06, associated A06/A07/A10 | Real local Ollama `/api/embed` transport guarded by existing discovery validation/registration/license/locality/enablement. Scoped Character/Scene/Asset/Research picker, per-index original-registration selection, dimension constraint, edit/rebuild/cancel/invalidate/remove/query. Research changes atomically clear vectors and fence in-flight callbacks. | PARTIAL. Adapter contract and real loopback transport recheck PASS on recovered bytes with synthetic vectors. Earlier transport test used a real loopback server returning synthetic vectors, never a real model. Actual Ollama inference and semantic quality LOCAL_REQUIRED / NOT_RUN. Image embeddings require another configured host provider. |
| R3-GAP-05 Provider profiles | Existing credential-free profile contracts retained. | BLOCKED on verified OS-vault host integration. No new credential endpoint or model registry. |

## Authorities, privacy and cancellation

- Reuse the original ExperimentalStore scope-atomic File/PG document, Model Center, Research, asset and screenplay services. No second manuscript, model or task authority.
- Application composition binds `embedding_service.research = research_library_service` and `embedding_service.discovery_bridge = local_ai_discovery.route_bridge`, preserving the original authorities.
- Embedding-only discovery recognition is gated by `visual_embeddings`; default OFF and V1 acceptance preserve legacy rejection. Registration remains disabled after restart until explicit revalidation/enablement. No startup inference.
- Positive locality evidence is mandatory. Hosted/remote Ollama declarations, revoked registration/license, changed model evidence, malformed dimensions, nonfinite or zero vectors and wrong response identity fail closed. Metadata validation is followed by final source/authority checks before dispatch. No pull, install, launch or paid call was performed.
- P2 feature isolation: the index list omits only Research-dependent rows on the typed `research_library_v2` disabled response, including mid-read toggles. Direct reads/actions and all global project/session denials remain fail-closed.
- Research indexes and indexes that reference owner-private assets are owner-private. Query checks current sources/model/index version before and after inference; a stale badge is not the only protection.
- Source replacement, metadata edits, revocation and deletion clear derived Research vectors atomically and remove build tokens. Late responses cannot republish invalidated work.
- Cancel invalidates the build token. Already dispatched synchronous transport can take until its bounded timeout to end. Restart does not automatically replay.
- Research restore creates a new version and defaults to PRIVATE; old citations stay stale. Revoked or newly private third-party citations cannot expose old note history. Own-source citation repair preserves the author's writing but requires explicit current citation selection.
- Source retention is bounded to 20 prior revisions and 32 MiB stored source JSON. Revocation/deletion are not blocked by quota and can retain one additional bounded archival snapshot. Owner-only original-version export remains available.
- R1/R2/R3 permission, revocation, terminal/error and unknown-cost semantics remain subject to the final-source aggregate regression. Interop 1.0 wire/consent/authority fields are untouched.

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

The adjacent JSON preserves the original Wave3 checkpoint hash inventory separately from the corrected inventory and records exact source scopes:

- Original recovered checkpoint, before P2: 276 focused backend passes, 97 unchanged profile skips, one warning across 14 files. These are real post-recovery results, separate from the identically counted pre-reset run.
- Wave3 staged code tree `8a0f4952e61f40c2f52cb6f156f607a9d6c9298d`: complete frontend 1175 passed / 8 inherited opt-in skips; TypeScript PASS; three new backend suites 29 passed / 22 PostgreSQL variants deselected.
- P2 corrected file hashes: focused backend 71 passed / 64 unchanged profile skips / one warning; EmbeddingPanel regressions 5 passed; TypeScript and diff checks PASS. Separate correction verification PASS.
- Later core staged code tree `04c0cd285757fb04d8917d95828421ad7a76c963`, including P2: complete frontend 1222 passed / 8 inherited opt-in skips; TypeScript PASS; focused backend 214 passed / 198 PostgreSQL variants deselected.
- Pre-reset source only: 276 backend passes / 97 skips and 31 frontend passes, plus then-current TypeScript/token checks. These are retained as historical receipts and do not verify later bytes.
- Hosted browser journey: `frontend/tests/e2e/r4-wave3-continuation.spec.ts`, selected by the existing R4 glob. It covers real File API/React import, replacement, cited-note editing, repair, private restore, source selection, NOT_CONFIGURED index persistence, reload and 1366/1440/1920 geometry/screenshots. Execution remains pending hosted CI; local Chromium was not retried after its established platform restriction.
- Actual model inference, semantic retrieval quality, real GPU/Windows, image embeddings and paid/cloud billing remain NOT_RUN / LOCAL_REQUIRED. Synthetic-vector loopback transport tests establish the adapter contract, not model quality.

### P2 source-hash correction

The correction is included in commit `d18e874e20117bce6cce15366b64d2c1c129b1bc`:

| File | Corrected SHA-256 |
| --- | --- |
| `app/experimental/embeddings.py` | `49db3d91b3c6497a1a816be22251e5d5b64eb548c53450e894b0a2ddba308452` |
| `frontend/src/experimental/EmbeddingPanel.continuation.test.tsx` | `78ecc583484548408eaa40bea2f4c9766ec5ea977454392398b7378a30679061` |
| `tests/test_post_interop_embedding_feature_isolation.py` | `77c8910f57acef2a608436f8c1bd0f8e8233ea1f193b2fa4b238869a34c724aa` |

The JSON retains the earlier hashes with their original checkpoint label; it does not retroactively attach new test results to old source bytes.

Protocol reference: [Ollama Generate embeddings](https://docs.ollama.com/api/embed), checked on 2026-10-06. The adapter uses `truncate=false`: over-context text fails explicitly. Large references can require splitting; automatic semantic chunking/reranking is not claimed.

## Opus handoff

Keep the existing AppShell, Panel, Button, Badge, Field, StatusMessage and design tokens. No protected design-system redesign was made.

- Broker: added policy and explicit fallback/license controls. Changed selection invalidates old approval. Unknown metrics remain visibly unknown.
- Benchmark: evidence profile and exact-output human-review form. Catalog/imported/synthetic evidence never implies real-model quality.
- Research: preserve input on conflicts; distinguish metadata edit from file replacement; explain private new-version restore. History export, archived-source review and citation repair are explicit. Revoked citation evidence must stay hidden.
- Embedding: original scoped-source picker is primary; raw IDs stay advanced. Explain text-only Ollama vs IMAGE sources. BUILDING is a phase without a fabricated percentage; cancellation is available separately from pending work. Missing default provider remains NOT_CONFIGURED even if an original registration can be selected for an individual index.

Final art direction remains for the requested Opus pass. Historical acceptance status and evidence are frozen.

# Search, visual identity and Research functional surfaces

## Owner and scope

This completion extends the existing `EmbeddingService`, `ResearchLibraryService`, approved `V1CapabilityService.visual_memory`, and `AssetLibraryService`. It adds no first-level module, second profile owner, competing model queue, or executable plugin. Machine-readable surface contract: `contracts/functional-surfaces/search-visual-research.v1.json`.

Local STORY indexes read the original ChapterService. Collaboration STORY indexes require the bound branch manuscript authority and never substitute mainline prose. All persistent indexes/receipts use the original ExperimentalStore project/workspace/storyline/branch key. Research-bearing indexes and analysis/comparison receipts are creator-private. Asset access still uses its original feature/actor/scope/integrity authority. API `/api` and `/api/v1` share original mounted authorization.

## Hybrid retrieval

The existing EmbeddingProvider contract and real local Model Center Ollama registration path remain authoritative. The new VectorIndex interface has a bounded exact-cosine implementation over existing persisted vectors; it creates no duplicate vector store. Hybrid mode uses weighted reciprocal-rank fusion of actual cosine-ranked vectors and live lexical term scores. Both component scores/ranks are returned. Defaults: lexical weight 0.35; RRF constant 60. Query weight must be strictly between 0 and 1.

Character, STORY chapter, Research, image Asset and existing Scene entities share provider/model revision, source version/digest, index version and vector integrity fences. Results include exact original-owner navigation and Research paragraph citations. Caller can pin expected index version. Missing provider returns `EMBEDDING_NOT_CONFIGURED`, never keyword results under a semantic label. Synthetic providers remain `MOCK_ONLY`; no model/semantic quality claim is made.

Existing create/edit/rebuild/invalidate/remove/cancel persists version/history. Rebuild publishes atomically only while its execution token, sources, flags, provider and authorization remain current. Restart never automatically runs a model; a leftover BUILDING index must be explicitly cancelled/invalidated and rebuilt. UI adds a mode selector and STORY source kind to the existing EmbeddingPanel, preserving its conflict input and scope epoch behavior.

## Visual identity

`GET .../embeddings/visual-identity/profiles` projects current approved CHARACTER visual-memory records. `appearance_version` is the original visual record version. Hair/body/accessories remain inside the existing `appearance` object; clothing remains the original `clothing` object. The original visual-reference create/update/approve API is the only editing authority. Updating appearance returns it to DRAFT. Asset digest/version and original approval provenance must still match.

A comparison request selects 1–12 approved references and a pinned candidate asset, with IMAGE or VIDEO target and explicit cosine drift threshold. It persists a creator-private review receipt, not a new appearance profile. Synthetic image vectors produce inspectable similarity and drift warnings. Versioned review is required before the selection endpoint releases pinned source lineage. A changed/unapproved/deleted reference or candidate blocks selection. Selection dispatches no production task.

## OCR/Vision Research contracts

Existing TXT, Markdown, DOCX, text PDF, explicit Web Capture, Notes, and image-metadata imports remain unchanged. OCR, scanned PDF Vision, image understanding, chart understanding and table understanding now have typed input/capability/result/provider interfaces plus durable review receipts. Each source is pinned by ID/version/original-byte digest; output blocks have page and optional normalized bounding box, structured table cells and derived citation digest. Original bytes are never replaced by output, and reviewed results never automatically become source paragraphs, manuscript or Canon.

Original replacement, restore, revoke and delete invalidate analysis execution tokens/results atomically with source changes. Read paths revalidate current source visibility/version and hide stale output. Jobs are creator-private even when the underlying source has project access.

## Adapter execution and honest limits

The small `ReviewAdapterJobs` helper stores domain review receipts only. It is not a JobManager, scheduler, model worker, task runtime, plugin host or automatic recovery engine. Requests run synchronously in process only with a trusted explicit `MOCK_ONLY`, local synthetic provider. Real image/OCR/Vision adapters fail with `ADAPTER_MODEL_ADMISSION_NOT_CONFIGURED`; enabling them requires integration with the existing JobManager/admission authority, not bypassing it. Transport/GPU/model quality remains `NOT_RUN`; production configuration remains `NOT_CONFIGURED`.

Receipts persist DRAFT/NOT_CONFIGURED → RUNNING → REVIEW_REQUIRED → REVIEWED. Cancel/invalidate clear the token and current result. Interrupted RUNNING is surfaced as `recovery_required`; explicit recover clears the orphaned lease, and a separate explicit run starts fresh. Late model callbacks cannot restore cancelled/invalidated receipts. Errors persist sanitized codes, never stack traces/provider payloads. Limits: 200 receipts per scope per domain, 100 revisions per receipt, 512 KiB result JSON, source import 4 MiB, 1,000 derived blocks, 100 table rows × 50 cells with 1,000 chars/cell. These are bounded synchronous adapter contracts, not proof of durable worker execution.

## Surface/API ownership

All exact routes, actions, states, scopes, permissions, flag dependencies and protected engineering behavior are enumerated in the JSON surface contract. Visual identity and OCR/Vision have formal functional UI contracts for existing Assets/Research inspectors; only hybrid controls are added to visible UI in this pass. No final aesthetic redesign is included.

Both flags default off, require explicit allowlisting, and are disabled by V1 acceptance mode. Collaboration's existing outer middleware may return its established `501 COLLABORATION_ROUTE_NOT_ENABLED` when no experimental feature is enabled; local disabled feature routes return 404. Current session/role/feature checks occur before and after expensive dispatch and immediately before publication.

## Verification

New mounted tests are parameterized over File and real PostgreSQL and both API prefixes. They cover lexical+vector contributions, four entity kinds/citations, source/provider/index versions, unconfigured and feature-disabled behavior, cross-branch/actor access, permission revoke while executing, source replacement invalidation, explicit recovery/restart, and actual cross-thread cancel/publish races. Synthetic fixtures are plainly labelled MOCK_ONLY. No existing tests/assertions/skips or migrations 001–020 were changed.

Local and hosted test receipts should be read with the final delivery report. Real model quality, durable model-worker restart, and live image/OCR inference are NOT_RUN. No private manuscript, paid API, model download, credential, merge, release or deploy is used.

### Local check receipt (2026-10-07)

- Combined File focused suite: 98 passed; 90 real-PostgreSQL cases deselected for the local profile. Suites: new `test_surface_search_visual_research.py`, existing embedding contracts, Research service/mounted tests, feature isolation and wave3 embedding adapter. Real PostgreSQL execution is pending hosted verification, not simulated.
- Existing + new EmbeddingPanel/ExperimentalWorkbench UI tests: 21 passed. UI token guard and TypeScript build passed.
- Seven existing design-system snapshot/geometry cases were attempted locally and stopped at browser launch because Playwright `chromium_headless_shell-1234` is absent. Browser assertions did not execute; no snapshots were updated. New `surface-freeze-search-hybrid.spec.ts` is registered by the shared functional-surface config for hosted real File API/browser execution.
- Historical frozen evidence and original assertions/skips were not edited. These focused results are not the complete regression verdict.

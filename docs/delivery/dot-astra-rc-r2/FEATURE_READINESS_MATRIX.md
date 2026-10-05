# R2 feature readiness matrix

**Engineering in progress. Release blocked pending discovery review, final regression and verified GitHub delivery.**

- Fixed inspection snapshot: `547167e8abce15cad3495779f52e845310a0a1fe`; tree `528459b8c7d6b94dde8b70e37c1e52d12524fc81`.
- Baseline: `f8c141c39a543cc9dbea57647ac91185bc9aecd6`. Branch: `work/dot-astra-v1-rc-r2`; [Draft PR #37](https://github.com/1785235376-blip/AI-Novel-Studio/pull/37).
- Last remote head reported by lead: `90f4369b7367579b7aaeb00d4d25f21171353753`. Final remote SHA, exact test checkout and CI: **PENDING_LEAD**.
- Scope: all 143 original A–T codes, all D00–D18 packages, all 28 Local AI supplement sections. No completion percentage.
- Current source contains later uncommitted discovery fixes. This document does not declare them reviewed or delivered.
- Full explicit per-row API/storage/UI/evidence/version/dependency/revision fields are in [FEATURE_READINESS_MATRIX.json](FEATURE_READINESS_MATRIX.json).

## Evidence interpretation

- The 143 original codes are preserved exactly. Their historical rows are evidence of the old audit, never proof of current completion.
- The original audit does not contain full canonical feature definitions. Each feature records that limitation rather than inventing requirements.
- Feature D01-D07 and work-package D01-D07 are different namespaces; use features[].code and packages[].package_id.
- IMPLEMENTED describes the bounded stated implementation, not literary quality, every historical requirement, real model verification or final release readiness.
- CONNECTED requires a callable service/API and visible functional entry or documented Host/API entry. DISCONNECTED includes deliberately disabled execution.
- CONTRACT_VERIFIED may use real files, parsers and local codecs but does not prove a real AI model. MOCK_ONLY means model/provider behavior used controlled test doubles.
- No current REAL_VERIFIED model claim is made. Hosted Windows build/native contract results do not replace interactive Windows/WebView2 or user acceptance.
- User-visible states describe shipped capability semantics, not a percentage. AVAILABLE manual CRUD can coexist with NOT_CONFIGURED generation and incomplete higher-level package requirements.
- Worker logs are integration checkpoints from an uncommitted worktree. Final owner must replace pending revision/status using exact checkout SHA and retain distinctions between branch and PR merge checkout.
- Test paths without a cited passing result are inventory only. No old 96%, DONE status or historic passing count is inherited.
- The fixed snapshot 547167e8 is distinct from newer uncommitted discovery repair work. Open independent findings override older broad positive capability claims.
- The latest full backend checkpoint failed one test. A fixture repair or focused pass cannot replace a complete final-SHA rerun.
- The Local AI supplement is mapped separately as LAD-01–LAD-28; the original 143 A–T feature IDs are unchanged.
- A loopback runtime can proxy a remote model. Local routing authority requires verified runtime/model locality, current identity and current explicit enable authority.

## Current verification layers

| Layer | Evidence/state |
|---|---|
| original_independent_findings | At frozen eb165609: 9 failing Python assertions / 1 pass plus one failing UI assertion, grouped into 7 findings; preserved evidence/independent-before. |
| original_repair_recheck | 10/10 unchanged Python invariants now pass; exact unchanged UI scope assertion passes. New Local AI findings remain open separately. Current public exact-recheck artifact PENDING_LEAD. |
| latest_full_file_backend | FAILED checkpoint: 2032 passed / 35 skipped / 1 failed. Missing-policy-authority fixture expected a prior code; production fails closed with 403. Focused contract recheck now passes 143 tests; public focused receipt and complete final rerun remain PENDING_LEAD. |
| latest_frontend_unit | 548 passed across 108 files; integration-worktree checkpoint, not proof of later discovery edits or exact final SHA. Public current receipt PENDING_LEAD. |
| focused_discovery | 263 passed / 1 native-Windows skip in provider/hardware combined checkpoint; standalone lifecycle and metadata contracts only; independent fixed-snapshot discovery review found additional gaps. |
| final_file_suite | PENDING_LEAD |
| final_real_postgresql | NOT_RUN for this final candidate locally; final hosted result PENDING_LEAD |
| final_frontend_unit_typecheck_build | PENDING_LEAD for final committed code |
| browser_business_e2e | Local BLOCKED before launch by socket EPERM; hosted exact-final result PENDING_LEAD |
| hosted_windows_build_native_contract | No new-head result confirmed; PENDING_LEAD. Historical hosted checks do not validate this snapshot. |
| interactive_windows_webview2_install_upgrade_uninstall | NOT_RUN |
| real_provider_gpu_models | NOT_RUN |
| user_acceptance | NOT_RUN |

## New Local AI independent review blockers

| Finding | Fixed-snapshot issue | Required check |
|---|---|---|
| DISCOVERY-REVIEW-01 | Ollama remote_host/remote_model entries can be classified local at the fixed snapshot. A loopback Ollama service can proxy a cloud model; endpoint locality alone is insufficient. | Capture actual dispatch; remote/unknown locality must issue zero generation calls, including raw legacy Ollama and auto-memory paths. |
| DISCOVERY-REVIEW-02 | The fixed snapshot registers enabled local text models with streaming=False while the Writer route requires streaming. Discovery Enable therefore does not establish usable Writer selection. | Enabled discovered local model must execute through the actual Writer path. If output is buffered, label it buffered instead of claiming live token streaming. |
| DISCOVERY-REVIEW-03 | Rescan/model digest changes do not reliably revoke existing registration authority in the fixed snapshot. | Changed/vanished model identity after rescan must invalidate route and require current validation and explicit re-enable. |
| DISCOVERY-REVIEW-04 | A Disable during a blocking validation/enable callback can be overwritten by the late callback in the fixed snapshot. | Control epoch/CAS: Disable, removal or configuration changes win over older validate/enable results; no subsequent dispatch. |
| DISCOVERY-REVIEW-05 | External llama.cpp model alias association can be validated using a filename fallback but dispatched with the internal candidate identifier in the fixed snapshot. | Validate an external runtime advertised model alias and assert actual request.model matches the validated upstream identity. |

Original seven R2 findings now have passing focused unchanged invariant rechecks. Those results do not close the separate Local AI findings or replace final full regression.

## D00–D18 package summary

| Package | Priority/dependencies | Implementation / integration / verification | Delivered scope | Remaining gate |
|---|---|---|---|---|
| D00 Baseline and traceability | P0;  | PARTIAL/CONNECTED/CONTRACT_VERIFIED | Verified inherited PR36/main ancestry, branch and actual model; inventory all 143 original codes. | Final SHA, remote CI receipts and final deliverable inventory pending owner. |
| D01 Privacy and authorization | P0; D00 | IMPLEMENTED/CONNECTED/CONTRACT_VERIFIED | Original privacy serializer/migration fixes plus consistent raw-manuscript project/outline policies and normalized final-dispatch guards across author, adaptation, Agent, image/audio and motion paths; post-Accept memory is verified-local-only. | Original seven findings have passing focused independent rechecks, but Discovery introduces separate unresolved locality/identity/control findings. Final full File/real PostgreSQL/security receipt PENDING_LEAD. |
| D02 Export recovery and format fixes | P0; D01 | IMPLEMENTED/CONNECTED/CONTRACT_VERIFIED | Server-scoped history, reauthorization, same-snapshot rediscovery, frozen ZIP resources and Fountain structural fixes connected. | Complete fountain-js parser focused tests passed; real browser creation/reopen/download blocked locally and target screenplay app NOT_RUN. |
| D03 Core authoring and recovery | P0; D01 | IMPLEMENTED/CONNECTED/MOCK_ONLY | Core authoring retains Draft/Diff/Accept, source versions and recovery. Local Accept now binds captured generation base; per-job durable ACCEPTING claim serializes side effects across single-host processes, stale/reentrant attempts fail closed; original independent invariants pass. | Interrupted ambiguous acceptance requires review, never automatic replay. Full browser journey, IME/native crash behavior and final exact-SHA regression remain pending. |
| D04 Provider execution and vault | P0; D01 | PARTIAL/CONNECTED/FAILED | Guarded compatible/Claude/Gemini adapters and OS vault retained; integrated Local AI Discovery uses existing text/image/model registries with explicit lifecycle steps, bounded read-only probes and managed llama task-only launch design. | Five independent discovery issues need accepted fixes; real model/GPU/Windows behavior NOT_RUN. Named vault profiles and authoritative v2 broker remain absent. |
| D05 Advanced authoring and planning | P1; D03, D04 | PARTIAL/CONNECTED/CONTRACT_VERIFIED | Multi-variant review plus reusable STYLE/PLOT, compare/history/approval/restore and actual generation inputs; bounded selected-model exact-evidence structured suggestions and explicit-marker rule/plot drafts added. | Full outline/volume/chapter/scene hierarchy and semantic planning quality remain gaps; structured model path is MOCK_ONLY, with actual app registration inspected and final two-alias/full-suite gates pending. |
| D06 Import extraction and review | P1; D03, D04 | PARTIAL/CONNECTED/CONTRACT_VERIFIED | Evidence-located four-group extraction/review/journal plus separate explicit-marker rule/plot proposals and bounded selected-model planning drafts. | Latest full backend run has one failing missing-policy-authority fixture expectation. The reported fail-closed correction is covered by a 143-test focused green checkpoint; a full final rerun and published exact-revision receipt remain required. Semantic long-book extraction and global multi-entity atomicity remain incomplete. |
| D07 World characters continuity | P1; D05, D06 | PARTIAL/CONNECTED/CONTRACT_VERIFIED | Typed HISTORY/GEOGRAPHY/CIVILIZATION/ABILITY/PSYCHOLOGY records plus exact-evidence optional selected-model suggestions/local explicit rule extraction; existing rule/findings/graph retained. | New reviewed drafts do not constitute semantic engines or automatically join Canon/checker rules; real model quality unverified. |
| D08 Screenplay storyboard transitions | P1; D03, D04 | PARTIAL/CONNECTED/CONTRACT_VERIFIED | Branch-aware screenplay operations, approved revision fork preserving assets, shot/card/prompt fields and source-linked exports. | Specialized model-assisted shot/composition/camera/transition quality and complete independent scene/shot revision UX remain limited. |
| D09 Resource packages and documents | P1; D02, D08 | PARTIAL/CONNECTED/CONTRACT_VERIFIED | Three frozen resource ZIP formats connected to queue/API/UI; bounded owned bytes; licensed pinned CJK font and PDF embedding/render evidence. | Target Word/Final Draft/EPUB/NLE interoperability, typography and archive reimport remain independent gaps. |
| D10 Images references assets | P2; D04, D07 | PARTIAL/CONNECTED/MOCK_ONLY | Persistent image queue/review, real decoder checks, approved lexical reference index, digest-safe assets/lineage/trash/restore. | Real image/vision models, embeddings/semantic identity, cover/storyboard-specific generation and bulk governance/reimport remain gaps. Existing canvas zoom/pan/select/drag/align/group/layer/lock/undo is retained. |
| D11 Video tasks and timeline | P2; D08, D10 | PARTIAL/CONNECTED/MOCK_ONLY | Frame/prompt consent, fenced submit/cancel/callback, SSRF-safe actual download/decode, ordered trimmed silent review-cut output. Motion cloud review is now complete-request-bound and final dispatch reauthorizes all inputs; legacy remote asset workers are fail-closed rather than implicitly consented. | No real video model, bundled Windows codec distribution, soundtrack/final master/NLE conformance or vendor-specific asymmetric callbacks. |
| D12 Voices and audiobook | P2; D04, D07 | PARTIAL/CONNECTED/MOCK_ONLY | Durable voice/dictionary/provenance, immutable consent-checked sentence queues, verified audio, order-preserving PCM concatenate/export. | Real TTS/voices, expressive emotion, auto multi-character attribution, mixed-format mastering and phoneme-aligned subtitles absent/unrun. |
| D13 Agent and workflow execution | P2; D04, D05, D06, D08 | PARTIAL/CONNECTED/MOCK_ONLY | Bounded persistent authorized DAG with genuine Agent-job dispatch/completion and review; three tested local rule artifact recipes. Full-scope epoch/remount guards close original stale cross-project UI leak; automatic memory extraction is guarded-local-only and safe when no route is configured. | Recipes are not autonomous domain-apply loops; real-model role quality and transactional multi-worker/crash-gap scheduling incomplete. |
| D14 Comments and unified review | P1/P2; D03, D06 | PARTIAL/CONNECTED/CONTRACT_VERIFIED | Version/hash/quote-anchored persistent comments, trusted actor, stale markers, resolve/reopen/reply and history/UI. | Separate import/Canon/Agent/media queues are not one unified approval inbox; final browser permissions run pending. |
| D15 Plugin management and isolation | P2; D00, D01, D04 | PARTIAL/CONNECTED/CONTRACT_VERIFIED | Integrity-checked local declarative install/update/rollback/recoverable remove and grant reset; PR26 independently inspected. | Executable runtime DISCONNECTED/DENY_ALL; real Windows isolation/broker absent; packaged/collaboration lifecycle writes blocked without Host-admin authority. |
| D16 Migration backup and restore | P0/P1; D01 | IMPLEMENTED/CONNECTED/CONTRACT_VERIFIED | Stricter File/PG migration and non-destructive exclusive backup/new-target restore; exact inventory/digests and whole runtime sidecars included. | Final real PostgreSQL fresh-instance recovery and Windows ACL/locking/PowerShell checks pending; sidecars are not all migrated to SQL. |
| D17 Usability and Opus handoff | P0/P1; D00 | PARTIAL/CONNECTED/CONTRACT_VERIFIED | Existing shell/tokens kept; genuine forms/history/errors/review/recovery added with focused component/build/token checks. Local AI panel is mounted in Model Center. Latest integration UI checkpoint: 548 tests in 108 files pass, with later discovery corrections still requiring rerun. | Discovery disable/UI callback corrections remain under review. Local Chromium cannot launch; final hosted business/geometry and current real screenshots PENDING_LEAD; native IME/accessibility/user acceptance NOT_RUN. |
| D18 Build Windows delivery | P0/P1; D02, D03, D04, D09, D16, D17 | PARTIAL/CONNECTED/NOT_RUN | Pinned frontend toolchain, CI/native Host build/check work and licensed font build input advanced; Draft delivery only. | Fixed tree delivery verified at 90f4369b; final corrective source upload/readback/CI PENDING_LEAD; delivered remote 90f4369b has the same source tree as fixed snapshot 547167e8; newer corrective delivery/test head remains pending. Hosted new-head Windows result absent. No verified complete BaseApplication installer or interactive install/upgrade/uninstall acceptance. |

## Original A–T inventory

Original feature D01–D07 and work-package D01–D07 are separate namespaces. The historical audit does not contain complete original definitions; descriptive names below do not invent missing requirements. Test revision is recorded per evidence checkpoint in JSON; exact final revision remains PENDING_LEAD.

### A. Desktop runtime

#### A01 · Embedded desktop frontend

IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:45; full original definition unavailable.
- Before: WebView2 Host/static frontend already existed.
- After: Retained packaged Host/React bridge; UI extensions use the same shell.
- Source/UI: `app/packaging/packaged_desktop_host.py`, `app/packaging/static_frontend.py`, `frontend/src/packagedHost.ts`
- API: GET /health; GET /providers; GET /models
- Storage: Packaged runtime config; migration ledger; provider OS vault
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/BASELINE_RECEIPT.md; tests/test_packaged_desktop_composition_v070.py; tests/test_runtime_ownership_foundation_v070.py; tests/test_packaged_postgres_migrations_v070.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P0; D01, D02, D03, D04, D09, D16, D17; packages D04, D16, D18
- Remaining/next check: Interactive Windows/WebView2 lifecycle and screenshots still NOT_RUN.

#### A02 · Desktop launch and child lifecycle

IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:46; full original definition unavailable.
- Before: Packaged launcher and owned-process controls existed.
- After: Existing launcher retained; Windows build/provenance work is separate from an installable full runtime.
- Source/UI: `app/packaging/packaged_desktop_launcher.py`, `app/packaging/packaged_launcher.py`, `frontend/src/packagedHost.ts`
- API: GET /health; GET /providers; GET /models
- Storage: Packaged runtime config; migration ledger; provider OS vault
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/BASELINE_RECEIPT.md; tests/test_packaged_desktop_composition_v070.py; tests/test_runtime_ownership_foundation_v070.py; tests/test_packaged_postgres_migrations_v070.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P0; D01, D02, D03, D04, D09, D16, D17; packages D04, D16, D18
- Remaining/next check: Clean install, upgrades, uninstall data retention and actual window launch remain pending.

#### A03 · FastAPI application

IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:47; full original definition unavailable.
- Before: Versioned API and service composition existed.
- After: New authoring/media/workflow/plugin routers registered through existing app composition.
- Source/UI: `app/main.py`, `app/packaging/packaged_desktop_host.py`, `app/packaging/packaged_processes.py`, `app/packaging/runtime_lifecycle.py`, `app/model_runtime.py`, `frontend/src/packagedHost.ts`, `frontend/src/ui/ModelCenter.tsx`
- API: GET /health; GET /providers; GET /models
- Storage: Packaged runtime config; migration ledger; provider OS vault
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/BASELINE_RECEIPT.md; tests/test_packaged_desktop_composition_v070.py; tests/test_runtime_ownership_foundation_v070.py; tests/test_packaged_postgres_migrations_v070.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P0; D01, D02, D03, D04, D09, D16, D17; packages D04, D16, D18
- Remaining/next check: Final full-suite exact-SHA result pending.

#### A04 · Bundled PostgreSQL runtime

IMPLEMENTED / CONNECTED / NOT_RUN / EXPERIMENTAL
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:48; full original definition unavailable.
- Before: Packaged PostgreSQL bootstrap existed.
- After: Privacy migration registered; no replacement runtime architecture.
- Source/UI: `app/packaging/packaged_processes.py`, `app/packaging/database_bootstrap.py`, `frontend/src/packagedHost.ts`
- API: GET /health; GET /providers; GET /models
- Storage: Packaged runtime config; migration ledger; provider OS vault
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/BASELINE_RECEIPT.md; tests/test_packaged_desktop_composition_v070.py; tests/test_runtime_ownership_foundation_v070.py; tests/test_packaged_postgres_migrations_v070.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P0; D01, D02, D03, D04, D09, D16, D17; packages D04, D16, D18
- Remaining/next check: Clean Windows bundled runtime delivery and real final PostgreSQL run pending.

#### A05 · Database migration

IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:49; full original definition unavailable.
- Before: Migration ledger through inherited schema existed.
- After: Migration 018 persists/validates foreshadowing policy and preserves stricter imported policies.
- Source/UI: `app/packaging/postgres_migrations.py`, `database/migrations/018_context_privacy.sql`, `frontend/src/packagedHost.ts`
- API: GET /health; GET /providers; GET /models
- Storage: Packaged runtime config; migration ledger; provider OS vault
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/BASELINE_RECEIPT.md; tests/test_packaged_desktop_composition_v070.py; tests/test_runtime_ownership_foundation_v070.py; tests/test_packaged_postgres_migrations_v070.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P0; D01, D02, D03, D04, D09, D16, D17; packages D04, D16, D18
- Remaining/next check: Real PostgreSQL upgrade/restart/recovery gate pending exact final SHA.

#### A06 · Restart, shutdown and recovery

IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:50; full original definition unavailable.
- Before: Owned-process lifecycle and generation recovery existed.
- After: Non-destructive verified backup/restore added; interrupted Agent jobs fail for explicit retry.
- Source/UI: `app/packaging/runtime_lifecycle.py`, `app/backup_restore.py`, `frontend/src/packagedHost.ts`
- API: GET /health; GET /providers; GET /models
- Storage: Packaged runtime config; migration ledger; provider OS vault
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/BASELINE_RECEIPT.md; tests/test_packaged_desktop_composition_v070.py; tests/test_runtime_ownership_foundation_v070.py; tests/test_packaged_postgres_migrations_v070.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P0; D01, D02, D03, D04, D09, D16, D17; packages D04, D16, D18
- Remaining/next check: Windows process/ACL/power-loss checks remain unrun.

#### A07 · Desktop bridge

IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:51; full original definition unavailable.
- Before: Trusted Host bridge existed.
- After: Bridge preserved; new UI does not put provider secrets in browser storage.
- Source/UI: `app/packaging/desktop_bridge.py`, `app/packaging/host_uplink.py`, `frontend/src/packagedHost.ts`
- API: GET /health; GET /providers; GET /models
- Storage: Packaged runtime config; migration ledger; provider OS vault
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/BASELINE_RECEIPT.md; tests/test_packaged_desktop_composition_v070.py; tests/test_runtime_ownership_foundation_v070.py; tests/test_packaged_postgres_migrations_v070.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P0; D01, D02, D03, D04, D09, D16, D17; packages D04, D16, D18
- Remaining/next check: Real WebView2 interaction and Host authorization handoff pending.

#### A08 · Trusted session and credential boundary

IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:52; full original definition unavailable.
- Before: Opaque session and OS vault architecture already existed.
- After: Legacy supported provider dispatch resolves vault entries; packaged env-only key is insufficient.
- Source/UI: `app/credential_vault.py`, `app/trusted_sessions.py`, `frontend/src/novel/DeepSeekCredentialControl.tsx`
- API: GET /health; GET /providers; GET /models
- Storage: Packaged runtime config; migration ledger; provider OS vault
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/BASELINE_RECEIPT.md; tests/test_packaged_desktop_composition_v070.py; tests/test_runtime_ownership_foundation_v070.py; tests/test_packaged_postgres_migrations_v070.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P0; D01, D02, D03, D04, D09, D16, D17; packages D04, D16, D18
- Remaining/next check: Native Windows vault/Host end-to-end remains unrun.

#### A09 · Text provider execution

IMPLEMENTED / CONNECTED / MOCK_ONLY / NOT_CONFIGURED
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:53; full original definition unavailable.
- Before: Compatible adapter and old real-provider history existed; current source egress guard was incomplete.
- After: Last-send source/version/privacy checks, native Claude/Gemini protocols, cancellation/usage and explicit Mock disclosure.
- Source/UI: `app/providers.py`, `app/openai_compatible.py`, `app/native_text_providers.py`, `app/jobs.py`, `app/model_center/discovery_types.py`, `app/model_center/discovery_probes.py`, `app/model_center/discovery.py`, `app/model_center/discovery_api.py`, `app/model_center/discovery_bridge.py`, `app/model_center/domain.py`, `app/model_center/service.py`, `app/dependencies.py`, `app/main.py`, `frontend/src/ui/ModelCenter.tsx`, `frontend/src/novel/AiWritingPanel.tsx`, `frontend/src/ui/LocalAiDiscovery.tsx`, `frontend/src/localAiDiscoveryApi.ts`
- API: GET /health; GET /providers; GET /models
- Storage: Packaged runtime config; migration ledger; provider OS vault
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/BASELINE_RECEIPT.md; LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; tests/test_packaged_desktop_composition_v070.py; tests/test_runtime_ownership_foundation_v070.py; tests/test_packaged_postgres_migrations_v070.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Guarded selected text adapter: compatible/Ollama/Claude/Gemini as configured; transport tests/mock only, no current real model calls
- Priority/dependencies: P0; D01, D02, D03, D04, D09, D16, D17; packages D04, D16, D18
- Remaining/next check: No current real provider, credential, billing or quality verification; full v2 authoritative broker incomplete.
- Subpath Optional Local AI Discovery registration/route bridge: PARTIAL / CONNECTED / FAILED / EXPERIMENTAL. Standalone synthetic lifecycle passed; independent review of fixed 547167e8 reports five additional locality/identity/disable/Writer-route gaps. New dirty-tree fixes pending recheck.

#### A10 · Multi-provider/model routing

PARTIAL / CONNECTED / MOCK_ONLY / NOT_CONFIGURED
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:54; full original definition unavailable.
- Before: Catalog and explicit text/media adapters existed.
- After: Explicit compatible/native model routes are retained. Local AI Discovery is mounted on both API aliases and embedded in Model Center, with bounded probes, validation, disabled registration, separate explicit Enable and existing registry bridges. Independent review found five additional local-route safety/usability gaps; fixes are not yet accepted.
- Source/UI: `app/model_runtime.py`, `app/provider_runtime_v2_routing_service.py`, `app/providers.py`, `app/model_center/discovery_types.py`, `app/model_center/discovery_probes.py`, `app/model_center/discovery.py`, `app/model_center/discovery_api.py`, `app/model_center/discovery_bridge.py`, `app/model_center/domain.py`, `app/model_center/service.py`, `app/dependencies.py`, `app/main.py`, `frontend/src/ui/ModelCenter.tsx`, `frontend/src/ui/LocalAiDiscovery.tsx`, `frontend/src/localAiDiscoveryApi.ts`
- API: GET /health; GET /providers; GET /models
- Storage: Packaged runtime config; migration ledger; provider OS vault
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/BASELINE_RECEIPT.md; LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; tests/test_packaged_desktop_composition_v070.py; tests/test_runtime_ownership_foundation_v070.py; tests/test_packaged_postgres_migrations_v070.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Guarded selected text adapter: compatible/Ollama/Claude/Gemini as configured; transport tests/mock only, no current real model calls
- Priority/dependencies: P0; D01, D02, D03, D04, D09, D16, D17; packages D04, D16, D18
- Remaining/next check: Discovery review findings must close before real local routing acceptance; no real Windows/GPU/model evidence. Multiple named vault profiles and full authoritative v2 compatibility/budget broker remain incomplete.
- Subpath Optional Local AI Discovery registration/route bridge: PARTIAL / CONNECTED / FAILED / EXPERIMENTAL. Standalone synthetic lifecycle passed; independent review of fixed 547167e8 reports five additional locality/identity/disable/Writer-route gaps. New dirty-tree fixes pending recheck.

### B. Novel authoring

#### B01 · Novel/project creation

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:60; full original definition unavailable.
- Before: Novel creation and basic overview already existed.
- After: Core creation retained; persisted plans/comments/goal entries extend project workflow.
- Source/UI: `app/services/novel_service.py`, `app/services/chapter_service.py`, `app/services/generation_service.py`, `app/jobs.py`, `frontend/src/App.tsx`, `frontend/src/novel/AiWritingPanel.tsx`, `frontend/src/RevisionPanel.tsx`
- API: POST /novels; GET/POST /novels/{nid}/chapters; PUT /chapters/{id}; POST /generate/{operation}; POST /generation/{id}/accept; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: File/PostgreSQL novel/chapter/revision/generation repositories; generation snapshot/state
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/runtime-work.md; tests/test_core.py; tests/test_chapter_concurrency.py; tests/test_generation_idempotency_contracts.py; tests/test_generation_variants_phase3.py; tests/test_r2_generation_egress.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P0/P1; D01, D03, D04; packages D03, D05
- Remaining/next check: Final browser save/reopen journey pending; no claim of all historical overview requirements.

#### B02 · Workspace organization

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:61; full original definition unavailable.
- Before: Workspace/storyline/branch identity and basic navigation existed.
- After: Existing identity model reused by new routes; no parallel accounts.
- Source/UI: `app/services/novel_service.py`, `app/services/chapter_service.py`, `app/services/generation_service.py`, `app/jobs.py`, `frontend/src/App.tsx`, `frontend/src/novel/AiWritingPanel.tsx`, `frontend/src/RevisionPanel.tsx`
- API: POST /novels; GET/POST /novels/{nid}/chapters; PUT /chapters/{id}; POST /generate/{operation}; POST /generation/{id}/accept; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: File/PostgreSQL novel/chapter/revision/generation repositories; generation snapshot/state
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/runtime-work.md; tests/test_core.py; tests/test_chapter_concurrency.py; tests/test_generation_idempotency_contracts.py; tests/test_generation_variants_phase3.py; tests/test_r2_generation_egress.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P0/P1; D01, D03, D04; packages D03, D05
- Remaining/next check: Interactive multi-user desktop acceptance pending.

#### B03 · Chapter lifecycle

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:62; full original definition unavailable.
- Before: Create/archive/duplicate/move chapter operations existed.
- After: Existing atomic lifecycle reused by creation/import/audio references.
- Source/UI: `app/services/novel_service.py`, `app/services/chapter_service.py`, `app/services/generation_service.py`, `app/jobs.py`, `frontend/src/App.tsx`, `frontend/src/novel/AiWritingPanel.tsx`, `frontend/src/RevisionPanel.tsx`
- API: POST /novels; GET/POST /novels/{nid}/chapters; PUT /chapters/{id}; POST /generate/{operation}; POST /generation/{id}/accept; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: File/PostgreSQL novel/chapter/revision/generation repositories; generation snapshot/state
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/runtime-work.md; tests/test_core.py; tests/test_chapter_concurrency.py; tests/test_generation_idempotency_contracts.py; tests/test_generation_variants_phase3.py; tests/test_r2_generation_egress.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P0/P1; D01, D03, D04; packages D03, D05
- Remaining/next check: Final backend and browser lifecycle rerun pending.

#### B04 · Editor and saving

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:63; full original definition unavailable.
- Before: TipTap editor, versioned writes and unsaved conflict handling existed.
- After: Retained editor/save contract and generation acceptance boundary.
- Source/UI: `app/services/novel_service.py`, `app/services/chapter_service.py`, `app/services/generation_service.py`, `app/jobs.py`, `app/source_privacy.py`, `frontend/src/App.tsx`, `frontend/src/novel/AiWritingPanel.tsx`, `frontend/src/RevisionPanel.tsx`
- API: POST /novels; GET/POST /novels/{nid}/chapters; PUT /chapters/{id}; POST /generate/{operation}; POST /generation/{id}/accept; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: File/PostgreSQL novel/chapter/revision/generation repositories; generation snapshot/state
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/acceptance-scope-work.md; docs/delivery/dot-astra-rc-r2/evidence/acceptance-integrity.xml; docs/delivery/dot-astra-rc-r2/evidence/workflow-scope.xml; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; tests/test_core.py; tests/test_chapter_concurrency.py; tests/test_generation_idempotency_contracts.py; tests/test_generation_variants_phase3.py; tests/test_r2_generation_egress.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx; tests/test_r2_acceptance_integrity.py; tests/test_r2_outbound_dispatch_authority.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P0/P1; D01, D03, D04; packages D03, D05
- Remaining/next check: Crash/IME/undo/keyboard desktop acceptance and complete browser journey pending.

#### B05 · Chapter version history

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:64; full original definition unavailable.
- Before: Persistent chapter revisions existed.
- After: All new author plans/comments/media snapshots retain source versions; history remains authoritative.
- Source/UI: `app/services/novel_service.py`, `app/services/chapter_service.py`, `app/services/generation_service.py`, `app/jobs.py`, `app/source_privacy.py`, `frontend/src/App.tsx`, `frontend/src/novel/AiWritingPanel.tsx`, `frontend/src/RevisionPanel.tsx`
- API: POST /novels; GET/POST /novels/{nid}/chapters; PUT /chapters/{id}; POST /generate/{operation}; POST /generation/{id}/accept; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: File/PostgreSQL novel/chapter/revision/generation repositories; generation snapshot/state
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/acceptance-scope-work.md; docs/delivery/dot-astra-rc-r2/evidence/acceptance-integrity.xml; docs/delivery/dot-astra-rc-r2/evidence/workflow-scope.xml; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; tests/test_core.py; tests/test_chapter_concurrency.py; tests/test_generation_idempotency_contracts.py; tests/test_generation_variants_phase3.py; tests/test_r2_generation_egress.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx; tests/test_r2_acceptance_integrity.py; tests/test_r2_outbound_dispatch_authority.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P0/P1; D01, D03, D04; packages D03, D05
- Remaining/next check: Final history/reopen regression pending.

#### B06 · Version restore

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:65; full original definition unavailable.
- Before: Optimistic version restore existed.
- After: Restore remains explicit; plan restore creates a new reviewable draft rather than overwriting history.
- Source/UI: `app/services/novel_service.py`, `app/services/chapter_service.py`, `app/services/generation_service.py`, `app/jobs.py`, `app/source_privacy.py`, `frontend/src/App.tsx`, `frontend/src/novel/AiWritingPanel.tsx`, `frontend/src/RevisionPanel.tsx`
- API: POST /novels; GET/POST /novels/{nid}/chapters; PUT /chapters/{id}; POST /generate/{operation}; POST /generation/{id}/accept; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: File/PostgreSQL novel/chapter/revision/generation repositories; generation snapshot/state
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/acceptance-scope-work.md; docs/delivery/dot-astra-rc-r2/evidence/acceptance-integrity.xml; docs/delivery/dot-astra-rc-r2/evidence/workflow-scope.xml; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; tests/test_core.py; tests/test_chapter_concurrency.py; tests/test_generation_idempotency_contracts.py; tests/test_generation_variants_phase3.py; tests/test_r2_generation_egress.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx; tests/test_r2_acceptance_integrity.py; tests/test_r2_outbound_dispatch_authority.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P0/P1; D01, D03, D04; packages D03, D05
- Remaining/next check: Native unexpected-exit/unsaved-local-draft combinations require acceptance.

#### B07 · AI continuation

IMPLEMENTED / CONNECTED / MOCK_ONLY / NOT_CONFIGURED
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:66; full original definition unavailable.
- Before: Continue operation existed but old baseline could send raw restricted source.
- After: Version/hash/privacy-bound actual dispatch; returned content remains Draft until Accept.
- Source/UI: `app/services/novel_service.py`, `app/services/chapter_service.py`, `app/services/generation_service.py`, `app/jobs.py`, `app/source_privacy.py`, `frontend/src/App.tsx`, `frontend/src/novel/AiWritingPanel.tsx`, `frontend/src/RevisionPanel.tsx`
- API: POST /novels; GET/POST /novels/{nid}/chapters; PUT /chapters/{id}; POST /generate/{operation}; POST /generation/{id}/accept; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: File/PostgreSQL novel/chapter/revision/generation repositories; generation snapshot/state
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/acceptance-scope-work.md; docs/delivery/dot-astra-rc-r2/evidence/acceptance-integrity.xml; docs/delivery/dot-astra-rc-r2/evidence/workflow-scope.xml; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; tests/test_core.py; tests/test_chapter_concurrency.py; tests/test_generation_idempotency_contracts.py; tests/test_generation_variants_phase3.py; tests/test_r2_generation_egress.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx; tests/test_r2_acceptance_integrity.py; tests/test_r2_outbound_dispatch_authority.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Guarded selected text adapter: compatible/Ollama/Claude/Gemini as configured; transport tests/mock only, no current real model calls
- Priority/dependencies: P0/P1; D01, D03, D04; packages D03, D05
- Remaining/next check: Current real model and full browser Draft/Diff/Accept/recovery journey NOT_RUN.

#### B08 · AI rewrite

IMPLEMENTED / CONNECTED / MOCK_ONLY / NOT_CONFIGURED
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:67; full original definition unavailable.
- Before: Rewrite/selection and review path existed.
- After: Actual egress rechecks, selected-text membership, owner-scoped job access and repeat-safe accept enforced.
- Source/UI: `app/services/novel_service.py`, `app/services/chapter_service.py`, `app/services/generation_service.py`, `app/jobs.py`, `app/source_privacy.py`, `frontend/src/App.tsx`, `frontend/src/novel/AiWritingPanel.tsx`, `frontend/src/RevisionPanel.tsx`
- API: POST /novels; GET/POST /novels/{nid}/chapters; PUT /chapters/{id}; POST /generate/{operation}; POST /generation/{id}/accept; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: File/PostgreSQL novel/chapter/revision/generation repositories; generation snapshot/state
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/acceptance-scope-work.md; docs/delivery/dot-astra-rc-r2/evidence/acceptance-integrity.xml; docs/delivery/dot-astra-rc-r2/evidence/workflow-scope.xml; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; tests/test_core.py; tests/test_chapter_concurrency.py; tests/test_generation_idempotency_contracts.py; tests/test_generation_variants_phase3.py; tests/test_r2_generation_egress.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx; tests/test_r2_acceptance_integrity.py; tests/test_r2_outbound_dispatch_authority.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Guarded selected text adapter: compatible/Ollama/Claude/Gemini as configured; transport tests/mock only, no current real model calls
- Priority/dependencies: P0/P1; D01, D03, D04; packages D03, D05
- Remaining/next check: Real-provider output quality and interrupted live stream NOT_RUN.

#### B09 · AI polishing (inferred label)

IMPLEMENTED / CONNECTED / MOCK_ONLY / NOT_CONFIGURED
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:68; full original definition unavailable.
- Before: Generic operation dispatch existed; audit omitted precise historical name.
- After: Current polish operation shares guarded generation, Draft/Diff/Accept and failure handling.
- Source/UI: `app/services/novel_service.py`, `app/services/chapter_service.py`, `app/services/generation_service.py`, `app/jobs.py`, `app/source_privacy.py`, `frontend/src/App.tsx`, `frontend/src/novel/AiWritingPanel.tsx`, `frontend/src/RevisionPanel.tsx`
- API: POST /novels; GET/POST /novels/{nid}/chapters; PUT /chapters/{id}; POST /generate/{operation}; POST /generation/{id}/accept; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: File/PostgreSQL novel/chapter/revision/generation repositories; generation snapshot/state
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/acceptance-scope-work.md; docs/delivery/dot-astra-rc-r2/evidence/acceptance-integrity.xml; docs/delivery/dot-astra-rc-r2/evidence/workflow-scope.xml; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; tests/test_core.py; tests/test_chapter_concurrency.py; tests/test_generation_idempotency_contracts.py; tests/test_generation_variants_phase3.py; tests/test_r2_generation_egress.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx; tests/test_r2_acceptance_integrity.py; tests/test_r2_outbound_dispatch_authority.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Guarded selected text adapter: compatible/Ollama/Claude/Gemini as configured; transport tests/mock only, no current real model calls
- Priority/dependencies: P0/P1; D01, D03, D04; packages D03, D05
- Remaining/next check: Precise original definition unavailable; real model NOT_RUN.

#### B10 · AI brainstorming (inferred label)

IMPLEMENTED / CONNECTED / MOCK_ONLY / NOT_CONFIGURED
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:69; full original definition unavailable.
- Before: Generic operation dispatch existed; audit omitted precise historical name.
- After: Current brainstorm operation shares guarded generation and review.
- Source/UI: `app/services/novel_service.py`, `app/services/chapter_service.py`, `app/services/generation_service.py`, `app/jobs.py`, `app/source_privacy.py`, `frontend/src/App.tsx`, `frontend/src/novel/AiWritingPanel.tsx`, `frontend/src/RevisionPanel.tsx`
- API: POST /novels; GET/POST /novels/{nid}/chapters; PUT /chapters/{id}; POST /generate/{operation}; POST /generation/{id}/accept; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: File/PostgreSQL novel/chapter/revision/generation repositories; generation snapshot/state
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/acceptance-scope-work.md; docs/delivery/dot-astra-rc-r2/evidence/acceptance-integrity.xml; docs/delivery/dot-astra-rc-r2/evidence/workflow-scope.xml; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; tests/test_core.py; tests/test_chapter_concurrency.py; tests/test_generation_idempotency_contracts.py; tests/test_generation_variants_phase3.py; tests/test_r2_generation_egress.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx; tests/test_r2_acceptance_integrity.py; tests/test_r2_outbound_dispatch_authority.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Guarded selected text adapter: compatible/Ollama/Claude/Gemini as configured; transport tests/mock only, no current real model calls
- Priority/dependencies: P0/P1; D01, D03, D04; packages D03, D05
- Remaining/next check: Precise original definition unavailable; real model NOT_RUN.

#### B11 · Multiple writing candidates

PARTIAL / CONNECTED / MOCK_ONLY / NOT_CONFIGURED
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:70; full original definition unavailable.
- Before: Variant endpoint and comparison UI existed despite historical TODO.
- After: Multiple persisted candidates and Diff/explicit selection remain. Accept now uses the captured generation base and a durable serialized single-host acceptance claim; stale/current-version injection and concurrent duplicate side effects are rejected.
- Source/UI: `app/services/novel_service.py`, `app/services/chapter_service.py`, `app/services/generation_service.py`, `app/jobs.py`, `app/source_privacy.py`, `frontend/src/App.tsx`, `frontend/src/novel/AiWritingPanel.tsx`, `frontend/src/RevisionPanel.tsx`
- API: POST /novels; GET/POST /novels/{nid}/chapters; PUT /chapters/{id}; POST /generate/{operation}; POST /generation/{id}/accept; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: File/PostgreSQL novel/chapter/revision/generation repositories; generation snapshot/state
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/acceptance-scope-work.md; docs/delivery/dot-astra-rc-r2/evidence/acceptance-integrity.xml; docs/delivery/dot-astra-rc-r2/evidence/workflow-scope.xml; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; tests/test_core.py; tests/test_chapter_concurrency.py; tests/test_generation_idempotency_contracts.py; tests/test_generation_variants_phase3.py; tests/test_r2_generation_egress.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx; tests/test_r2_acceptance_integrity.py; tests/test_r2_outbound_dispatch_authority.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Guarded selected text adapter: compatible/Ollama/Claude/Gemini as configured; transport tests/mock only, no current real model calls
- Priority/dependencies: P0/P1; D01, D03, D04; packages D03, D05
- Remaining/next check: Candidate synthesis is not implemented. Ambiguous interrupted Accept remains review-required; multi-host PostgreSQL transactionality, real model quality and final browser recovery are unverified.

#### B12 · Reusable writing style

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:71; full original definition unavailable.
- Before: Only one-off style strings/presets existed.
- After: Typed versioned STYLE drafts, approval, history/restore and actual generation input with last-hop review recheck. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history.
- Source/UI: `app/services/creation_workbench_service.py`, `app/creation_workbench_api.py`, `app/api.py`, `app/jobs.py`, `app/services/ai_planning_service.py`, `app/ai_planning_api.py`, `app/planning_extraction.py`, `frontend/src/novel/CreationWorkbenchPanel.tsx`, `frontend/src/App.tsx`, `frontend/src/novel/AIPlanningPanel.tsx`
- API: POST /novels; GET/POST /novels/{nid}/chapters; PUT /chapters/{id}; POST /generate/{operation}; POST /generation/{id}/accept; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: File/PostgreSQL novel/chapter/revision/generation repositories; generation snapshot/state; planning_runs.json durable sidecar; explicit candidate save to versioned creation_records DRAFT
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.txt; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; tests/test_core.py; tests/test_chapter_concurrency.py; tests/test_generation_idempotency_contracts.py; tests/test_generation_variants_phase3.py; tests/test_r2_generation_egress.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Manual/local explicit extraction available; optional registered TextModelNode selected-provider suggestions are MOCK_ONLY verified / actual provider NOT_RUN.
- Priority/dependencies: P0/P1; D01, D03, D04; packages D03, D05
- Remaining/next check: Manual style authoring works; no learned style model; generation requires separately configured provider.
- Subpath Existing manual/domain operations: bounded existing implementation / CONNECTED / CONTRACT_VERIFIED / AVAILABLE.
- Subpath Selected-model structured planning suggestions: IMPLEMENTED / CONNECTED / MOCK_ONLY / NOT_CONFIGURED. At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes.
- Subpath Explicit marker rule/plot extraction: IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE. Only explicit bilingual rule lines or complete six-field three-act markers; incomplete/duplicate plot markers yield findings. Saves ABILITY/PLOT DRAFT only; not automatic extraction of unstated facts.

#### B13 · Writing goals and progress

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:72; full original definition unavailable.
- Before: Goal APIs and App goal display/editor already existed.
- After: Existing targets/deadline/current counts retained and chapter operations refresh progress.
- Source/UI: `app/services/novel_service.py`, `app/api.py`, `frontend/src/App.tsx`
- API: POST /novels; GET/POST /novels/{nid}/chapters; PUT /chapters/{id}; POST /generate/{operation}; POST /generation/{id}/accept; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: File/PostgreSQL novel/chapter/revision/generation repositories; generation snapshot/state
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/runtime-work.md; tests/test_core.py; tests/test_chapter_concurrency.py; tests/test_generation_idempotency_contracts.py; tests/test_generation_variants_phase3.py; tests/test_r2_generation_egress.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P0/P1; D01, D03, D04; packages D03, D05
- Remaining/next check: No new analytics claim; final UI goal persistence run pending.

### C. Import and knowledge review

#### C01 · TXT import

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:78; full original definition unavailable.
- Before: TXT parsing and chapter import existed.
- After: Existing parser reused with durable versioned knowledge review and safe application journal.
- Source/UI: `app/import_parsers.py`, `app/knowledge_extraction.py`, `app/services/import_review_service.py`, `app/services/import_apply_service.py`, `frontend/src/novel/NovelImportPanel.tsx`
- API: POST /novels/import; GET /novels/{nid}/import/knowledge-base/review; GET/PUT /novels/{nid}/import/knowledge-base/review/{review_id}; POST /novels/{nid}/import/knowledge-base/review; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: import_reviews.json; durable per-review apply journal; File/PostgreSQL target entities
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/import-apply-checkpoints.md; docs/delivery/dot-astra-rc-r2/evidence/synthetic-scale.json; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; tests/test_import_parsers.py; tests/test_import_ai_review.py; tests/test_r2_import_boundaries.py; tests/test_r2_import_apply_journal.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D01, D03, D04; packages D03, D06
- Remaining/next check: Measured 200-chapter/1,002,092-character synthetic File fixture exists (evidence/synthetic-scale.json); native picker and target-hardware performance acceptance pending.

#### C02 · Markdown import

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:79; full original definition unavailable.
- Before: Markdown parsing/import existed.
- After: Existing parser and source content retained; review can reopen.
- Source/UI: `app/import_parsers.py`, `app/knowledge_extraction.py`, `app/services/import_review_service.py`, `app/services/import_apply_service.py`, `frontend/src/novel/NovelImportPanel.tsx`
- API: POST /novels/import; GET /novels/{nid}/import/knowledge-base/review; GET/PUT /novels/{nid}/import/knowledge-base/review/{review_id}; POST /novels/{nid}/import/knowledge-base/review; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: import_reviews.json; durable per-review apply journal; File/PostgreSQL target entities
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/import-apply-checkpoints.md; docs/delivery/dot-astra-rc-r2/evidence/synthetic-scale.json; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; tests/test_import_parsers.py; tests/test_import_ai_review.py; tests/test_r2_import_boundaries.py; tests/test_r2_import_apply_journal.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D01, D03, D04; packages D03, D06
- Remaining/next check: A measured million-character synthetic File fixture exists; malformed mixed-layout document coverage remains limited.

#### C03 · DOCX import

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:80; full original definition unavailable.
- Before: DOCX parsing/import existed.
- After: Parser remains actual file reader; review journal prevents silent all-or-nothing false success.
- Source/UI: `app/import_parsers.py`, `app/knowledge_extraction.py`, `app/services/import_review_service.py`, `app/services/import_apply_service.py`, `frontend/src/novel/NovelImportPanel.tsx`
- API: POST /novels/import; GET /novels/{nid}/import/knowledge-base/review; GET/PUT /novels/{nid}/import/knowledge-base/review/{review_id}; POST /novels/{nid}/import/knowledge-base/review; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: import_reviews.json; durable per-review apply journal; File/PostgreSQL target entities
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/import-apply-checkpoints.md; docs/delivery/dot-astra-rc-r2/evidence/synthetic-scale.json; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; tests/test_import_parsers.py; tests/test_import_ai_review.py; tests/test_r2_import_boundaries.py; tests/test_r2_import_apply_journal.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D01, D03, D04; packages D03, D06
- Remaining/next check: Target Word layouts and edge-case embedded content require independent acceptance.

#### C04 · PDF import

PARTIAL / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:81; full original definition unavailable.
- Before: PDF text extraction/fallback existed.
- After: Existing text extraction retained; no OCR pipeline added.
- Source/UI: `app/import_parsers.py`, `app/knowledge_extraction.py`, `app/services/import_review_service.py`, `app/services/import_apply_service.py`, `frontend/src/novel/NovelImportPanel.tsx`
- API: POST /novels/import; GET /novels/{nid}/import/knowledge-base/review; GET/PUT /novels/{nid}/import/knowledge-base/review/{review_id}; POST /novels/{nid}/import/knowledge-base/review; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: import_reviews.json; durable per-review apply journal; File/PostgreSQL target entities
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/import-apply-checkpoints.md; docs/delivery/dot-astra-rc-r2/evidence/synthetic-scale.json; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; tests/test_import_parsers.py; tests/test_import_ai_review.py; tests/test_r2_import_boundaries.py; tests/test_r2_import_apply_journal.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D01, D03, D04; packages D03, D06
- Remaining/next check: Scanned/image-only PDFs and layout reconstruction not implemented as reliable import.

#### C05 · Import structure analysis

PARTIAL / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:82; full original definition unavailable.
- Before: Adaptation/review could hold structure proposals.
- After: Bounded local heuristics emit exact version/hash/offset evidence; optional AI review remains review-only. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history.
- Source/UI: `app/import_parsers.py`, `app/knowledge_extraction.py`, `app/services/import_review_service.py`, `app/services/import_apply_service.py`, `app/services/ai_planning_service.py`, `app/ai_planning_api.py`, `app/planning_extraction.py`, `frontend/src/novel/NovelImportPanel.tsx`, `frontend/src/novel/AIPlanningPanel.tsx`
- API: POST /novels/import; GET /novels/{nid}/import/knowledge-base/review; GET/PUT /novels/{nid}/import/knowledge-base/review/{review_id}; POST /novels/{nid}/import/knowledge-base/review; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: import_reviews.json; durable per-review apply journal; File/PostgreSQL target entities; planning_runs.json durable sidecar; explicit candidate save to versioned creation_records DRAFT
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/import-apply-checkpoints.md; docs/delivery/dot-astra-rc-r2/evidence/synthetic-scale.json; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; tests/test_import_parsers.py; tests/test_import_ai_review.py; tests/test_r2_import_boundaries.py; tests/test_r2_import_apply_journal.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Manual/local explicit extraction available; optional registered TextModelNode selected-provider suggestions are MOCK_ONLY verified / actual provider NOT_RUN.
- Priority/dependencies: P1; D01, D03, D04; packages D03, D06
- Remaining/next check: Explicit-marker rule/plot proposals now exist separately from four-group import review. Natural-language rule/structure quality, cross-chapter identity, interrupted large-book analysis and hierarchy generation remain incomplete.
- Subpath Existing manual/domain operations: bounded existing implementation / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL.
- Subpath Selected-model structured planning suggestions: IMPLEMENTED / CONNECTED / MOCK_ONLY / NOT_CONFIGURED. At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes.
- Subpath Explicit marker rule/plot extraction: IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE. Only explicit bilingual rule lines or complete six-field three-act markers; incomplete/duplicate plot markers yield findings. Saves ABILITY/PLOT DRAFT only; not automatic extraction of unstated facts.

#### C06 · Character extraction/review

PARTIAL / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:83; full original definition unavailable.
- Before: Review surface existed without deterministic extraction closure.
- After: Heuristic English/Chinese names, within-chapter dedupe, editable versioned review and journaled accepted upserts.
- Source/UI: `app/import_parsers.py`, `app/knowledge_extraction.py`, `app/services/import_review_service.py`, `app/services/import_apply_service.py`, `frontend/src/novel/NovelImportPanel.tsx`
- API: POST /novels/import; GET /novels/{nid}/import/knowledge-base/review; GET/PUT /novels/{nid}/import/knowledge-base/review/{review_id}; POST /novels/{nid}/import/knowledge-base/review; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: import_reviews.json; durable per-review apply journal; File/PostgreSQL target entities
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/import-apply-checkpoints.md; docs/delivery/dot-astra-rc-r2/evidence/synthetic-scale.json; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; tests/test_import_parsers.py; tests/test_import_ai_review.py; tests/test_r2_import_boundaries.py; tests/test_r2_import_apply_journal.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D01, D03, D04; packages D03, D06
- Remaining/next check: No cross-chapter identity resolution guarantee; homonym quality needs real corpus evaluation.

#### C07 · Location extraction/review

PARTIAL / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:84; full original definition unavailable.
- Before: Review model could store location candidates.
- After: Bounded place-name heuristics with source evidence and explicit accepted application.
- Source/UI: `app/import_parsers.py`, `app/knowledge_extraction.py`, `app/services/import_review_service.py`, `app/services/import_apply_service.py`, `frontend/src/novel/NovelImportPanel.tsx`
- API: POST /novels/import; GET /novels/{nid}/import/knowledge-base/review; GET/PUT /novels/{nid}/import/knowledge-base/review/{review_id}; POST /novels/{nid}/import/knowledge-base/review; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: import_reviews.json; durable per-review apply journal; File/PostgreSQL target entities
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/import-apply-checkpoints.md; docs/delivery/dot-astra-rc-r2/evidence/synthetic-scale.json; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; tests/test_import_parsers.py; tests/test_import_ai_review.py; tests/test_r2_import_boundaries.py; tests/test_r2_import_apply_journal.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D01, D03, D04; packages D03, D06
- Remaining/next check: Heuristic false positives remain; geographic semantics and long-form quality unverified.

#### C08 · Import timeline candidates

PARTIAL / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:85; full original definition unavailable.
- Before: Timeline CRUD existed; import linkage incomplete.
- After: Chapter-derived timeline candidates carry source locations and manual review/application.
- Source/UI: `app/import_parsers.py`, `app/knowledge_extraction.py`, `app/services/import_review_service.py`, `app/services/import_apply_service.py`, `frontend/src/novel/NovelImportPanel.tsx`
- API: POST /novels/import; GET /novels/{nid}/import/knowledge-base/review; GET/PUT /novels/{nid}/import/knowledge-base/review/{review_id}; POST /novels/{nid}/import/knowledge-base/review; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: import_reviews.json; durable per-review apply journal; File/PostgreSQL target entities
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/import-apply-checkpoints.md; docs/delivery/dot-astra-rc-r2/evidence/synthetic-scale.json; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; tests/test_import_parsers.py; tests/test_import_ai_review.py; tests/test_r2_import_boundaries.py; tests/test_r2_import_apply_journal.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D01, D03, D04; packages D03, D06
- Remaining/next check: A chapter summary is not temporal reasoning; precise event chronology extraction remains incomplete.

#### C09 · Import foreshadowing candidates

PARTIAL / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:86; full original definition unavailable.
- Before: Foreshadowing/canon review existed.
- After: Cue-based candidate extraction, privacy, selection and checkpointed application connected.
- Source/UI: `app/import_parsers.py`, `app/knowledge_extraction.py`, `app/services/import_review_service.py`, `app/services/import_apply_service.py`, `frontend/src/novel/NovelImportPanel.tsx`
- API: POST /novels/import; GET /novels/{nid}/import/knowledge-base/review; GET/PUT /novels/{nid}/import/knowledge-base/review/{review_id}; POST /novels/{nid}/import/knowledge-base/review; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: import_reviews.json; durable per-review apply journal; File/PostgreSQL target entities
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/import-apply-checkpoints.md; docs/delivery/dot-astra-rc-r2/evidence/synthetic-scale.json; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; tests/test_import_parsers.py; tests/test_import_ai_review.py; tests/test_r2_import_boundaries.py; tests/test_r2_import_apply_journal.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D01, D03, D04; packages D03, D06
- Remaining/next check: Semantic setup/payoff matching and rule extraction remain incomplete.

#### C10 · Adapt unfinished novel

PARTIAL / CONNECTED / MOCK_ONLY / NOT_CONFIGURED
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:87; full original definition unavailable.
- Before: Adaptation service and reviewable generation workflow existed.
- After: Independent R2 audit found unreviewed adaptation-source cloud dispatch in eb165609. Current repair adds source/hash/version/project-policy/branch reauthorization immediately before normalized dispatch; historical snapshots without current consent remain local-only. Output stays reviewable Draft.
- Source/UI: `app/import_parsers.py`, `app/knowledge_extraction.py`, `app/services/import_review_service.py`, `app/services/import_apply_service.py`, `app/services/adaptation_service.py`, `app/source_privacy.py`, `frontend/src/novel/NovelImportPanel.tsx`
- API: POST /novels/import; GET /novels/{nid}/import/knowledge-base/review; GET/PUT /novels/{nid}/import/knowledge-base/review/{review_id}; POST /novels/{nid}/import/knowledge-base/review; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: import_reviews.json; durable per-review apply journal; File/PostgreSQL target entities
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/import-apply-checkpoints.md; docs/delivery/dot-astra-rc-r2/evidence/synthetic-scale.json; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; tests/test_import_parsers.py; tests/test_import_ai_review.py; tests/test_r2_import_boundaries.py; tests/test_r2_import_apply_journal.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx; tests/test_r2_dispatch_revalidation.py; tests/test_r2_outbound_dispatch_authority.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D01, D03, D04; packages D03, D06
- Remaining/next check: Contract repair passes the original recording-transport invariant; real model quality and long-book adaptation remain NOT_RUN. Final full-suite and actual provider acceptance are required.

### D. World knowledge

#### D01 · Lore/world knowledge base

PARTIAL / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:93; full original definition unavailable.
- Before: Lore evidence/proposals/memory existed.
- After: Stricter privacy filtering and reviewed manual typed structures reuse existing project identity. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history.
- Source/UI: `app/services/lore_service.py`, `app/lore/continuity_engine.py`, `app/services/creation_workbench_service.py`, `app/services/novel_service.py`, `app/creation_workbench_api.py`, `app/services/ai_planning_service.py`, `app/ai_planning_api.py`, `app/planning_extraction.py`, `frontend/src/novel/StoryDatabase.tsx`, `frontend/src/novel/CreationWorkbenchPanel.tsx`, `frontend/src/novel/WorldBuildingDashboard.tsx`, `frontend/src/novel/AIPlanningPanel.tsx`
- API: GET/POST /novels/{nid}/world-rules; GET/POST /novels/{nid}/creation-records; POST /novels/{nid}/creation-records/{rid}/{action}; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: File/PostgreSQL Lore and domain records; versioned creation_records sidecar for new typed manual structures; planning_runs.json durable sidecar; explicit candidate save to versioned creation_records DRAFT
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/privacy-recovery-focused.txt; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; tests/test_lore_contract.py; tests/test_world_rule_payload.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Manual/local explicit extraction available; optional registered TextModelNode selected-provider suggestions are MOCK_ONLY verified / actual provider NOT_RUN.
- Priority/dependencies: P1; D03, D04, D05, D06; packages D06, D07
- Remaining/next check: Full semantic world model and evidence-quality acceptance incomplete.
- Subpath Existing manual/domain operations: bounded existing implementation / CONNECTED / CONTRACT_VERIFIED / AVAILABLE.
- Subpath Selected-model structured planning suggestions: IMPLEMENTED / CONNECTED / MOCK_ONLY / NOT_CONFIGURED. At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes.
- Subpath Explicit marker rule/plot extraction: IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE. Only explicit bilingual rule lines or complete six-field three-act markers; incomplete/duplicate plot markers yield findings. Saves ABILITY/PLOT DRAFT only; not automatic extraction of unstated facts.

#### D02 · World rules

PARTIAL / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:94; full original definition unavailable.
- Before: Approved rule registry and forbidden-term checks existed.
- After: Conservative privacy persistence and manual structure references retained. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history.
- Source/UI: `app/services/lore_service.py`, `app/lore/continuity_engine.py`, `app/services/creation_workbench_service.py`, `app/services/novel_service.py`, `app/creation_workbench_api.py`, `app/services/ai_planning_service.py`, `app/ai_planning_api.py`, `app/planning_extraction.py`, `frontend/src/novel/StoryDatabase.tsx`, `frontend/src/novel/CreationWorkbenchPanel.tsx`, `frontend/src/novel/WorldBuildingDashboard.tsx`, `frontend/src/novel/AIPlanningPanel.tsx`
- API: GET/POST /novels/{nid}/world-rules; GET/POST /novels/{nid}/creation-records; POST /novels/{nid}/creation-records/{rid}/{action}; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: File/PostgreSQL Lore and domain records; versioned creation_records sidecar for new typed manual structures; planning_runs.json durable sidecar; explicit candidate save to versioned creation_records DRAFT
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/privacy-recovery-focused.txt; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; tests/test_lore_contract.py; tests/test_world_rule_payload.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Manual/local explicit extraction available; optional registered TextModelNode selected-provider suggestions are MOCK_ONLY verified / actual provider NOT_RUN.
- Priority/dependencies: P1; D03, D04, D05, D06; packages D06, D07
- Remaining/next check: Model/local explicit proposals become ABILITY drafts and require separate review; they do not automatically enter the approved world-rule registry or semantic checker.
- Subpath Existing manual/domain operations: bounded existing implementation / CONNECTED / CONTRACT_VERIFIED / AVAILABLE.
- Subpath Selected-model structured planning suggestions: IMPLEMENTED / CONNECTED / MOCK_ONLY / NOT_CONFIGURED. At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes.
- Subpath Explicit marker rule/plot extraction: IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE. Only explicit bilingual rule lines or complete six-field three-act markers; incomplete/duplicate plot markers yield findings. Saves ABILITY/PLOT DRAFT only; not automatic extraction of unstated facts.

#### D03 · Historical event records

PARTIAL / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:95; full original definition unavailable.
- Before: No dedicated historical-event structure found in baseline audit.
- After: HISTORY record kind has schema, versions, API, approval/restore and UI. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history.
- Source/UI: `app/services/lore_service.py`, `app/lore/continuity_engine.py`, `app/services/creation_workbench_service.py`, `app/services/novel_service.py`, `app/creation_workbench_api.py`, `app/services/ai_planning_service.py`, `app/ai_planning_api.py`, `app/planning_extraction.py`, `frontend/src/novel/StoryDatabase.tsx`, `frontend/src/novel/CreationWorkbenchPanel.tsx`, `frontend/src/novel/WorldBuildingDashboard.tsx`, `frontend/src/novel/AIPlanningPanel.tsx`
- API: GET/POST /novels/{nid}/world-rules; GET/POST /novels/{nid}/creation-records; POST /novels/{nid}/creation-records/{rid}/{action}; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: File/PostgreSQL Lore and domain records; versioned creation_records sidecar for new typed manual structures; planning_runs.json durable sidecar; explicit candidate save to versioned creation_records DRAFT
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.txt; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; tests/test_lore_contract.py; tests/test_world_rule_payload.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Manual/local explicit extraction available; optional registered TextModelNode selected-provider suggestions are MOCK_ONLY verified / actual provider NOT_RUN.
- Priority/dependencies: P1; D03, D04, D05, D06; packages D06, D07
- Remaining/next check: Manual and model-proposed source-evidenced records now exist; historical chronology inference and automatic Canon/checker integration remain absent.
- Subpath Existing manual/domain operations: bounded existing implementation / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL.
- Subpath Selected-model structured planning suggestions: IMPLEMENTED / CONNECTED / MOCK_ONLY / NOT_CONFIGURED. At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes.
- Subpath Explicit marker rule/plot extraction: IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE. Only explicit bilingual rule lines or complete six-field three-act markers; incomplete/duplicate plot markers yield findings. Saves ABILITY/PLOT DRAFT only; not automatic extraction of unstated facts.

#### D04 · Geography structures

PARTIAL / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:96; full original definition unavailable.
- Before: Location CRUD was not a geography system.
- After: GEOGRAPHY records support referenced locations, rules and versioned review. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history.
- Source/UI: `app/services/lore_service.py`, `app/lore/continuity_engine.py`, `app/services/creation_workbench_service.py`, `app/services/novel_service.py`, `app/creation_workbench_api.py`, `app/services/ai_planning_service.py`, `app/ai_planning_api.py`, `app/planning_extraction.py`, `frontend/src/novel/StoryDatabase.tsx`, `frontend/src/novel/CreationWorkbenchPanel.tsx`, `frontend/src/novel/WorldBuildingDashboard.tsx`, `frontend/src/novel/AIPlanningPanel.tsx`
- API: GET/POST /novels/{nid}/world-rules; GET/POST /novels/{nid}/creation-records; POST /novels/{nid}/creation-records/{rid}/{action}; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: File/PostgreSQL Lore and domain records; versioned creation_records sidecar for new typed manual structures; planning_runs.json durable sidecar; explicit candidate save to versioned creation_records DRAFT
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.txt; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; tests/test_lore_contract.py; tests/test_world_rule_payload.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Manual/local explicit extraction available; optional registered TextModelNode selected-provider suggestions are MOCK_ONLY verified / actual provider NOT_RUN.
- Priority/dependencies: P1; D03, D04, D05, D06; packages D06, D07
- Remaining/next check: Geography drafts can be model-proposed with evidence; no map/topology/path or geographic consistency engine.
- Subpath Existing manual/domain operations: bounded existing implementation / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL.
- Subpath Selected-model structured planning suggestions: IMPLEMENTED / CONNECTED / MOCK_ONLY / NOT_CONFIGURED. At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes.
- Subpath Explicit marker rule/plot extraction: IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE. Only explicit bilingual rule lines or complete six-field three-act markers; incomplete/duplicate plot markers yield findings. Saves ABILITY/PLOT DRAFT only; not automatic extraction of unstated facts.

#### D05 · Civilization/organization structures

PARTIAL / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:97; full original definition unavailable.
- Before: No dedicated civilization product found.
- After: CIVILIZATION record kind persisted with constraints, references, version/review UI. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history.
- Source/UI: `app/services/lore_service.py`, `app/lore/continuity_engine.py`, `app/services/creation_workbench_service.py`, `app/services/novel_service.py`, `app/creation_workbench_api.py`, `app/services/ai_planning_service.py`, `app/ai_planning_api.py`, `app/planning_extraction.py`, `frontend/src/novel/StoryDatabase.tsx`, `frontend/src/novel/CreationWorkbenchPanel.tsx`, `frontend/src/novel/WorldBuildingDashboard.tsx`, `frontend/src/novel/AIPlanningPanel.tsx`
- API: GET/POST /novels/{nid}/world-rules; GET/POST /novels/{nid}/creation-records; POST /novels/{nid}/creation-records/{rid}/{action}; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: File/PostgreSQL Lore and domain records; versioned creation_records sidecar for new typed manual structures; planning_runs.json durable sidecar; explicit candidate save to versioned creation_records DRAFT
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.txt; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; tests/test_lore_contract.py; tests/test_world_rule_payload.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Manual/local explicit extraction available; optional registered TextModelNode selected-provider suggestions are MOCK_ONLY verified / actual provider NOT_RUN.
- Priority/dependencies: P1; D03, D04, D05, D06; packages D06, D07
- Remaining/next check: Civilization drafts can be model-proposed with evidence; simulation/hierarchy reasoning and automatic Canon integration absent.
- Subpath Existing manual/domain operations: bounded existing implementation / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL.
- Subpath Selected-model structured planning suggestions: IMPLEMENTED / CONNECTED / MOCK_ONLY / NOT_CONFIGURED. At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes.
- Subpath Explicit marker rule/plot extraction: IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE. Only explicit bilingual rule lines or complete six-field three-act markers; incomplete/duplicate plot markers yield findings. Saves ABILITY/PLOT DRAFT only; not automatic extraction of unstated facts.

#### D06 · Ability/power structures

PARTIAL / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:98; full original definition unavailable.
- Before: No dedicated ability product found.
- After: ABILITY records retain rules, references, history and explicit approval. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history.
- Source/UI: `app/services/lore_service.py`, `app/lore/continuity_engine.py`, `app/services/creation_workbench_service.py`, `app/services/novel_service.py`, `app/creation_workbench_api.py`, `app/services/ai_planning_service.py`, `app/ai_planning_api.py`, `app/planning_extraction.py`, `frontend/src/novel/StoryDatabase.tsx`, `frontend/src/novel/CreationWorkbenchPanel.tsx`, `frontend/src/novel/WorldBuildingDashboard.tsx`, `frontend/src/novel/AIPlanningPanel.tsx`
- API: GET/POST /novels/{nid}/world-rules; GET/POST /novels/{nid}/creation-records; POST /novels/{nid}/creation-records/{rid}/{action}; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: File/PostgreSQL Lore and domain records; versioned creation_records sidecar for new typed manual structures; planning_runs.json durable sidecar; explicit candidate save to versioned creation_records DRAFT
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.txt; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; tests/test_lore_contract.py; tests/test_world_rule_payload.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Manual/local explicit extraction available; optional registered TextModelNode selected-provider suggestions are MOCK_ONLY verified / actual provider NOT_RUN.
- Priority/dependencies: P1; D03, D04, D05, D06; packages D06, D07
- Remaining/next check: Explicit-marked or model-proposed rules can become reviewed drafts; no power-system solver or automatic formal rule installation.
- Subpath Existing manual/domain operations: bounded existing implementation / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL.
- Subpath Selected-model structured planning suggestions: IMPLEMENTED / CONNECTED / MOCK_ONLY / NOT_CONFIGURED. At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes.
- Subpath Explicit marker rule/plot extraction: IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE. Only explicit bilingual rule lines or complete six-field three-act markers; incomplete/duplicate plot markers yield findings. Saves ABILITY/PLOT DRAFT only; not automatic extraction of unstated facts.

#### D07 · World consistency checks

PARTIAL / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:99; full original definition unavailable.
- Before: Deterministic continuity/rule service existed.
- After: Existing findings retained with stricter policy/source boundaries.
- Source/UI: `app/services/lore_service.py`, `app/lore/continuity_engine.py`, `app/services/creation_workbench_service.py`, `app/services/novel_service.py`, `app/creation_workbench_api.py`, `frontend/src/novel/StoryDatabase.tsx`, `frontend/src/novel/CreationWorkbenchPanel.tsx`, `frontend/src/novel/WorldBuildingDashboard.tsx`
- API: GET/POST /novels/{nid}/world-rules; GET/POST /novels/{nid}/creation-records; POST /novels/{nid}/creation-records/{rid}/{action}; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: File/PostgreSQL Lore and domain records; versioned creation_records sidecar for new typed manual structures
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/privacy-recovery-focused.txt; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; tests/test_lore_contract.py; tests/test_world_rule_payload.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D03, D04, D05, D06; packages D06, D07
- Remaining/next check: Full semantic aggregate consistency and new manual-record-to-rule engine integration incomplete.

### E. Characters

#### E01 · Character records

IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:105; full original definition unavailable.
- Before: Character CRUD and editor existed.
- After: Existing persistent character records retained and usable by reference validation.
- Source/UI: `app/services/novel_service.py`, `app/services/v1_capability_service.py`, `app/services/creation_workbench_service.py`, `app/review.py`, `app/creation_workbench_api.py`, `frontend/src/novel/StoryDatabase.tsx`, `frontend/src/novel/WorldRelationshipGraph.tsx`, `frontend/src/novel/CreationWorkbenchPanel.tsx`
- API: PUT /novels/{nid}/characters/{id}; GET/POST /novels/{nid}/characters/{id}/evolution; POST /novels/{nid}/characters/consistency-check; GET/POST /novels/{nid}/creation-records; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: File/PostgreSQL character/relationship rows; capability evolution and creation_records sidecars
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; tests/test_phase4_characters.py; tests/test_phase4_relationships.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D05, D06; packages D07
- Remaining/next check: Final cross-branch character/UI acceptance pending.

#### E02 · Character attributes

PARTIAL / CONNECTED / NOT_RUN / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:106; full original definition unavailable.
- Before: Flexible character metadata existed.
- After: Existing attributes plus referenced versioned manual psychology records available.
- Source/UI: `app/services/novel_service.py`, `app/services/v1_capability_service.py`, `app/services/creation_workbench_service.py`, `app/review.py`, `app/creation_workbench_api.py`, `frontend/src/novel/StoryDatabase.tsx`, `frontend/src/novel/WorldRelationshipGraph.tsx`, `frontend/src/novel/CreationWorkbenchPanel.tsx`
- API: PUT /novels/{nid}/characters/{id}; GET/POST /novels/{nid}/characters/{id}/evolution; POST /novels/{nid}/characters/consistency-check; GET/POST /novels/{nid}/creation-records; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: File/PostgreSQL character/relationship rows; capability evolution and creation_records sidecars
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; tests/test_phase4_characters.py; tests/test_phase4_relationships.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D05, D06; packages D07
- Remaining/next check: No comprehensive typed/versioned character attribute schema migration delivered.

#### E03 · Character relationships/graph

IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:107; full original definition unavailable.
- Before: Relationship CRUD and graph/filter view already existed.
- After: Actual relationship graph retained; new plans can reference entities.
- Source/UI: `app/services/novel_service.py`, `app/services/v1_capability_service.py`, `app/services/creation_workbench_service.py`, `app/review.py`, `app/creation_workbench_api.py`, `frontend/src/novel/StoryDatabase.tsx`, `frontend/src/novel/WorldRelationshipGraph.tsx`, `frontend/src/novel/CreationWorkbenchPanel.tsx`
- API: PUT /novels/{nid}/characters/{id}; GET/POST /novels/{nid}/characters/{id}/evolution; POST /novels/{nid}/characters/consistency-check; GET/POST /novels/{nid}/creation-records; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: File/PostgreSQL character/relationship rows; capability evolution and creation_records sidecars
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; tests/test_phase4_characters.py; tests/test_phase4_relationships.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D05, D06; packages D07
- Remaining/next check: No automatic inferred relationship acceptance or causal reasoning claim.

#### E04 · Character growth records

PARTIAL / CONNECTED / NOT_RUN / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:108; full original definition unavailable.
- Before: Evolution records/editor already existed.
- After: Existing evidence/version-linked evolution records retained.
- Source/UI: `app/services/novel_service.py`, `app/services/v1_capability_service.py`, `app/services/creation_workbench_service.py`, `app/review.py`, `app/creation_workbench_api.py`, `frontend/src/novel/StoryDatabase.tsx`, `frontend/src/novel/WorldRelationshipGraph.tsx`, `frontend/src/novel/CreationWorkbenchPanel.tsx`
- API: PUT /novels/{nid}/characters/{id}; GET/POST /novels/{nid}/characters/{id}/evolution; POST /novels/{nid}/characters/consistency-check; GET/POST /novels/{nid}/creation-records; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: File/PostgreSQL character/relationship rows; capability evolution and creation_records sidecars
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; tests/test_phase4_characters.py; tests/test_phase4_relationships.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D05, D06; packages D07
- Remaining/next check: Dedicated growth planner/route visualization and integration with all new records incomplete.

#### E05 · Psychological records/engine

PARTIAL / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:109; full original definition unavailable.
- Before: No psychological-state engine found.
- After: PSYCHOLOGY record kind adds manual schema, references, approval/version/restore/UI. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history.
- Source/UI: `app/services/novel_service.py`, `app/services/v1_capability_service.py`, `app/services/creation_workbench_service.py`, `app/review.py`, `app/creation_workbench_api.py`, `app/services/ai_planning_service.py`, `app/ai_planning_api.py`, `app/planning_extraction.py`, `frontend/src/novel/StoryDatabase.tsx`, `frontend/src/novel/WorldRelationshipGraph.tsx`, `frontend/src/novel/CreationWorkbenchPanel.tsx`, `frontend/src/novel/AIPlanningPanel.tsx`
- API: PUT /novels/{nid}/characters/{id}; GET/POST /novels/{nid}/characters/{id}/evolution; POST /novels/{nid}/characters/consistency-check; GET/POST /novels/{nid}/creation-records; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: File/PostgreSQL character/relationship rows; capability evolution and creation_records sidecars; planning_runs.json durable sidecar; explicit candidate save to versioned creation_records DRAFT
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.txt; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; tests/test_phase4_characters.py; tests/test_phase4_relationships.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Manual/local explicit extraction available; optional registered TextModelNode selected-provider suggestions are MOCK_ONLY verified / actual provider NOT_RUN.
- Priority/dependencies: P1; D05, D06; packages D07
- Remaining/next check: Evidence-bound psychology suggestions can become reviewed drafts; no psychological-state inference/simulation engine or validated character-quality benchmark.
- Subpath Existing manual/domain operations: bounded existing implementation / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL.
- Subpath Selected-model structured planning suggestions: IMPLEMENTED / CONNECTED / MOCK_ONLY / NOT_CONFIGURED. At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes.
- Subpath Explicit marker rule/plot extraction: IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE. Only explicit bilingual rule lines or complete six-field three-act markers; incomplete/duplicate plot markers yield findings. Saves ABILITY/PLOT DRAFT only; not automatic extraction of unstated facts.

#### E06 · Character consistency

PARTIAL / CONNECTED / NOT_RUN / EXPERIMENTAL
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:110; full original definition unavailable.
- Before: Deterministic check endpoint/editor action existed.
- After: Current rule checks and evidence findings retained.
- Source/UI: `app/services/novel_service.py`, `app/services/v1_capability_service.py`, `app/services/creation_workbench_service.py`, `app/review.py`, `app/creation_workbench_api.py`, `frontend/src/novel/StoryDatabase.tsx`, `frontend/src/novel/WorldRelationshipGraph.tsx`, `frontend/src/novel/CreationWorkbenchPanel.tsx`
- API: PUT /novels/{nid}/characters/{id}; GET/POST /novels/{nid}/characters/{id}/evolution; POST /novels/{nid}/characters/consistency-check; GET/POST /novels/{nid}/creation-records; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: File/PostgreSQL character/relationship rows; capability evolution and creation_records sidecars
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; tests/test_phase4_characters.py; tests/test_phase4_relationships.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D05, D06; packages D07
- Remaining/next check: Complete persistent semantic consistency workflow/quality catalog incomplete.

### F. Plot planning

#### F01 · AI outline generation

PARTIAL / CONNECTED / NOT_RUN / EXPERIMENTAL
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:116; full original definition unavailable.
- Before: Manual outline editor existed, no dedicated outline generator.
- After: Approved PLOT instructions feed existing text generation; selected-model Agent can propose text. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history.
- Source/UI: `app/services/novel_service.py`, `app/services/creation_workbench_service.py`, `app/narrative.py`, `app/creation_workbench_api.py`, `app/services/ai_planning_service.py`, `app/ai_planning_api.py`, `app/planning_extraction.py`, `frontend/src/novel/StoryDatabase.tsx`, `frontend/src/novel/CreationWorkbenchPanel.tsx`, `frontend/src/novel/AIPlanningPanel.tsx`
- API: GET/PUT /novels/{nid}/outline; GET/POST /novels/{nid}/creation-records; PUT /novels/{nid}/volumes/{volume_id}; PUT /novels/{nid}/scenes/{scene_id}; GET /novels/{nid}/story-routes; PUT /novels/{nid}/story-routes/{route_id}; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: File/PostgreSQL outline/volume/scene/route records; creation_records versioned sidecar; planning_runs.json durable sidecar; explicit candidate save to versioned creation_records DRAFT
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; tests/test_phase5_outline.py; tests/test_phase5_volumes.py; tests/test_phase5_scenes.py; tests/test_phase5_story_routes.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Manual/local explicit extraction available; optional registered TextModelNode selected-provider suggestions are MOCK_ONLY verified / actual provider NOT_RUN.
- Priority/dependencies: P1; D03, D04, D05, D06; packages D05, D07
- Remaining/next check: Structured PLOT candidates feed approved generation input, but full outline→volume→chapter→scene decomposition/review/apply hierarchy remains incomplete.
- Subpath Existing manual/domain operations: bounded existing implementation / CONNECTED / NOT_RUN / EXPERIMENTAL.
- Subpath Selected-model structured planning suggestions: IMPLEMENTED / CONNECTED / MOCK_ONLY / NOT_CONFIGURED. At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes.
- Subpath Explicit marker rule/plot extraction: IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE. Only explicit bilingual rule lines or complete six-field three-act markers; incomplete/duplicate plot markers yield findings. Saves ABILITY/PLOT DRAFT only; not automatic extraction of unstated facts.

#### F02 · Three-act planning

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:117; full original definition unavailable.
- Before: No typed three-act domain record found.
- After: PLOT requires three acts/conflict/climax/ending; versions, compare, approval and generation input connected. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history.
- Source/UI: `app/services/novel_service.py`, `app/services/creation_workbench_service.py`, `app/narrative.py`, `app/creation_workbench_api.py`, `app/services/ai_planning_service.py`, `app/ai_planning_api.py`, `app/planning_extraction.py`, `frontend/src/novel/StoryDatabase.tsx`, `frontend/src/novel/CreationWorkbenchPanel.tsx`, `frontend/src/novel/AIPlanningPanel.tsx`
- API: GET/PUT /novels/{nid}/outline; GET/POST /novels/{nid}/creation-records; PUT /novels/{nid}/volumes/{volume_id}; PUT /novels/{nid}/scenes/{scene_id}; GET /novels/{nid}/story-routes; PUT /novels/{nid}/story-routes/{route_id}; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: File/PostgreSQL outline/volume/scene/route records; creation_records versioned sidecar; planning_runs.json durable sidecar; explicit candidate save to versioned creation_records DRAFT
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.txt; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; tests/test_phase5_outline.py; tests/test_phase5_volumes.py; tests/test_phase5_scenes.py; tests/test_phase5_story_routes.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Manual/local explicit extraction available; optional registered TextModelNode selected-provider suggestions are MOCK_ONLY verified / actual provider NOT_RUN.
- Priority/dependencies: P1; D03, D04, D05, D06; packages D05, D07
- Remaining/next check: Manual three-act record closure and bounded structured proposals exist; real-provider/plot-quality acceptance NOT_RUN.
- Subpath Existing manual/domain operations: bounded existing implementation / CONNECTED / CONTRACT_VERIFIED / AVAILABLE.
- Subpath Selected-model structured planning suggestions: IMPLEMENTED / CONNECTED / MOCK_ONLY / NOT_CONFIGURED. At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes.
- Subpath Explicit marker rule/plot extraction: IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE. Only explicit bilingual rule lines or complete six-field three-act markers; incomplete/duplicate plot markers yield findings. Saves ABILITY/PLOT DRAFT only; not automatic extraction of unstated facts.

#### F03 · Volume planning

IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:118; full original definition unavailable.
- Before: Volume APIs and editor existed.
- After: Existing persisted manual volume planning retained.
- Source/UI: `app/services/novel_service.py`, `app/services/creation_workbench_service.py`, `app/narrative.py`, `app/creation_workbench_api.py`, `frontend/src/novel/StoryDatabase.tsx`, `frontend/src/novel/CreationWorkbenchPanel.tsx`
- API: GET/PUT /novels/{nid}/outline; GET/POST /novels/{nid}/creation-records; PUT /novels/{nid}/volumes/{volume_id}; PUT /novels/{nid}/scenes/{scene_id}; GET /novels/{nid}/story-routes; PUT /novels/{nid}/story-routes/{route_id}; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: File/PostgreSQL outline/volume/scene/route records; creation_records versioned sidecar
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; tests/test_phase5_outline.py; tests/test_phase5_volumes.py; tests/test_phase5_scenes.py; tests/test_phase5_story_routes.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D03, D04, D05, D06; packages D05, D07
- Remaining/next check: No automatic AI decomposition/acceptance claim; final API/UI rerun pending.

#### F04 · Chapter outline planning

IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:119; full original definition unavailable.
- Before: Outline APIs and editor existed.
- After: Existing persisted outline retained and privacy-filtered in outbound contexts.
- Source/UI: `app/services/novel_service.py`, `app/services/creation_workbench_service.py`, `app/narrative.py`, `app/creation_workbench_api.py`, `frontend/src/novel/StoryDatabase.tsx`, `frontend/src/novel/CreationWorkbenchPanel.tsx`
- API: GET/PUT /novels/{nid}/outline; GET/POST /novels/{nid}/creation-records; PUT /novels/{nid}/volumes/{volume_id}; PUT /novels/{nid}/scenes/{scene_id}; GET /novels/{nid}/story-routes; PUT /novels/{nid}/story-routes/{route_id}; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: File/PostgreSQL outline/volume/scene/route records; creation_records versioned sidecar
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; tests/test_phase5_outline.py; tests/test_phase5_volumes.py; tests/test_phase5_scenes.py; tests/test_phase5_story_routes.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D03, D04, D05, D06; packages D05, D07
- Remaining/next check: Dedicated AI outline generation is separate F01 gap.

#### F05 · Scene planning

IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:120; full original definition unavailable.
- Before: Scene APIs/editor existed.
- After: Existing scene planning reused by screenplay/media references.
- Source/UI: `app/services/novel_service.py`, `app/services/creation_workbench_service.py`, `app/narrative.py`, `app/creation_workbench_api.py`, `frontend/src/novel/StoryDatabase.tsx`, `frontend/src/novel/CreationWorkbenchPanel.tsx`
- API: GET/PUT /novels/{nid}/outline; GET/POST /novels/{nid}/creation-records; PUT /novels/{nid}/volumes/{volume_id}; PUT /novels/{nid}/scenes/{scene_id}; GET /novels/{nid}/story-routes; PUT /novels/{nid}/story-routes/{route_id}; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: File/PostgreSQL outline/volume/scene/route records; creation_records versioned sidecar
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; tests/test_phase5_outline.py; tests/test_phase5_volumes.py; tests/test_phase5_scenes.py; tests/test_phase5_story_routes.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D03, D04, D05, D06; packages D05, D07
- Remaining/next check: No automatic semantic scene design guarantee.

#### F06 · Main story routes

IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:121; full original definition unavailable.
- Before: Story route/thread CRUD existed.
- After: Existing routes remain referencable from versioned PLOT records.
- Source/UI: `app/services/novel_service.py`, `app/services/creation_workbench_service.py`, `app/narrative.py`, `app/creation_workbench_api.py`, `frontend/src/novel/StoryDatabase.tsx`, `frontend/src/novel/CreationWorkbenchPanel.tsx`
- API: GET/PUT /novels/{nid}/outline; GET/POST /novels/{nid}/creation-records; PUT /novels/{nid}/volumes/{volume_id}; PUT /novels/{nid}/scenes/{scene_id}; GET /novels/{nid}/story-routes; PUT /novels/{nid}/story-routes/{route_id}; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: File/PostgreSQL outline/volume/scene/route records; creation_records versioned sidecar
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; tests/test_phase5_outline.py; tests/test_phase5_volumes.py; tests/test_phase5_scenes.py; tests/test_phase5_story_routes.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D03, D04, D05, D06; packages D05, D07
- Remaining/next check: Full graphical route-to-manuscript planning remains a limited manual workflow.

#### F07 · Subplot routes

IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:122; full original definition unavailable.
- Before: Route type/branch metadata and editor existed.
- After: Existing subplot records retained without inventing analytics.
- Source/UI: `app/services/novel_service.py`, `app/services/creation_workbench_service.py`, `app/narrative.py`, `app/creation_workbench_api.py`, `frontend/src/novel/StoryDatabase.tsx`, `frontend/src/novel/CreationWorkbenchPanel.tsx`
- API: GET/PUT /novels/{nid}/outline; GET/POST /novels/{nid}/creation-records; PUT /novels/{nid}/volumes/{volume_id}; PUT /novels/{nid}/scenes/{scene_id}; GET /novels/{nid}/story-routes; PUT /novels/{nid}/story-routes/{route_id}; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: File/PostgreSQL outline/volume/scene/route records; creation_records versioned sidecar
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; tests/test_phase5_outline.py; tests/test_phase5_volumes.py; tests/test_phase5_scenes.py; tests/test_phase5_story_routes.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D03, D04, D05, D06; packages D05, D07
- Remaining/next check: Dedicated subplot balance/causal analytics absent.

#### F08 · Conflict design

PARTIAL / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:123; full original definition unavailable.
- Before: Continuity finding proposals existed without design assistant.
- After: Typed required PLOT conflict, comparison and approved generation input added. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history.
- Source/UI: `app/services/novel_service.py`, `app/services/creation_workbench_service.py`, `app/narrative.py`, `app/creation_workbench_api.py`, `app/services/ai_planning_service.py`, `app/ai_planning_api.py`, `app/planning_extraction.py`, `frontend/src/novel/StoryDatabase.tsx`, `frontend/src/novel/CreationWorkbenchPanel.tsx`, `frontend/src/novel/AIPlanningPanel.tsx`
- API: GET/PUT /novels/{nid}/outline; GET/POST /novels/{nid}/creation-records; PUT /novels/{nid}/volumes/{volume_id}; PUT /novels/{nid}/scenes/{scene_id}; GET /novels/{nid}/story-routes; PUT /novels/{nid}/story-routes/{route_id}; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: File/PostgreSQL outline/volume/scene/route records; creation_records versioned sidecar; planning_runs.json durable sidecar; explicit candidate save to versioned creation_records DRAFT
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.txt; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; tests/test_phase5_outline.py; tests/test_phase5_volumes.py; tests/test_phase5_scenes.py; tests/test_phase5_story_routes.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Manual/local explicit extraction available; optional registered TextModelNode selected-provider suggestions are MOCK_ONLY verified / actual provider NOT_RUN.
- Priority/dependencies: P1; D03, D04, D05, D06; packages D05, D07
- Remaining/next check: Structured conflict proposals require exact source evidence and explicit review; no broader semantic conflict-quality engine.
- Subpath Existing manual/domain operations: bounded existing implementation / CONNECTED / CONTRACT_VERIFIED / AVAILABLE.
- Subpath Selected-model structured planning suggestions: IMPLEMENTED / CONNECTED / MOCK_ONLY / NOT_CONFIGURED. At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes.
- Subpath Explicit marker rule/plot extraction: IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE. Only explicit bilingual rule lines or complete six-field three-act markers; incomplete/duplicate plot markers yield findings. Saves ABILITY/PLOT DRAFT only; not automatic extraction of unstated facts.

#### F09 · Climax planning

PARTIAL / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:124; full original definition unavailable.
- Before: No dedicated climax planning model found.
- After: Required PLOT climax, versions, source linkage and generation input added. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history.
- Source/UI: `app/services/novel_service.py`, `app/services/creation_workbench_service.py`, `app/narrative.py`, `app/creation_workbench_api.py`, `app/services/ai_planning_service.py`, `app/ai_planning_api.py`, `app/planning_extraction.py`, `frontend/src/novel/StoryDatabase.tsx`, `frontend/src/novel/CreationWorkbenchPanel.tsx`, `frontend/src/novel/AIPlanningPanel.tsx`
- API: GET/PUT /novels/{nid}/outline; GET/POST /novels/{nid}/creation-records; PUT /novels/{nid}/volumes/{volume_id}; PUT /novels/{nid}/scenes/{scene_id}; GET /novels/{nid}/story-routes; PUT /novels/{nid}/story-routes/{route_id}; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: File/PostgreSQL outline/volume/scene/route records; creation_records versioned sidecar; planning_runs.json durable sidecar; explicit candidate save to versioned creation_records DRAFT
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.txt; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; tests/test_phase5_outline.py; tests/test_phase5_volumes.py; tests/test_phase5_scenes.py; tests/test_phase5_story_routes.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Manual/local explicit extraction available; optional registered TextModelNode selected-provider suggestions are MOCK_ONLY verified / actual provider NOT_RUN.
- Priority/dependencies: P1; D03, D04, D05, D06; packages D05, D07
- Remaining/next check: Structured climax proposals require exact source evidence and explicit review; no automated tension/pacing measurement.
- Subpath Existing manual/domain operations: bounded existing implementation / CONNECTED / CONTRACT_VERIFIED / AVAILABLE.
- Subpath Selected-model structured planning suggestions: IMPLEMENTED / CONNECTED / MOCK_ONLY / NOT_CONFIGURED. At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes.
- Subpath Explicit marker rule/plot extraction: IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE. Only explicit bilingual rule lines or complete six-field three-act markers; incomplete/duplicate plot markers yield findings. Saves ABILITY/PLOT DRAFT only; not automatic extraction of unstated facts.

#### F10 · Multiple ending planning

PARTIAL / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:125; full original definition unavailable.
- Before: Collaboration branches were not ending plans.
- After: Multiple separately versioned PLOT endings can compare and be selected for generation. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history.
- Source/UI: `app/services/novel_service.py`, `app/services/creation_workbench_service.py`, `app/narrative.py`, `app/creation_workbench_api.py`, `app/services/ai_planning_service.py`, `app/ai_planning_api.py`, `app/planning_extraction.py`, `frontend/src/novel/StoryDatabase.tsx`, `frontend/src/novel/CreationWorkbenchPanel.tsx`, `frontend/src/novel/AIPlanningPanel.tsx`
- API: GET/PUT /novels/{nid}/outline; GET/POST /novels/{nid}/creation-records; PUT /novels/{nid}/volumes/{volume_id}; PUT /novels/{nid}/scenes/{scene_id}; GET /novels/{nid}/story-routes; PUT /novels/{nid}/story-routes/{route_id}; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft; GET/POST /novels/{nid}/planning-runs; GET /novels/{nid}/planning-runs/{rid}; POST /novels/{nid}/planning-runs/{rid}/cancel; POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft
- Storage: File/PostgreSQL outline/volume/scene/route records; creation_records versioned sidecar; planning_runs.json durable sidecar; explicit candidate save to versioned creation_records DRAFT
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.txt; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; tests/test_phase5_outline.py; tests/test_phase5_volumes.py; tests/test_phase5_scenes.py; tests/test_phase5_story_routes.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Manual/local explicit extraction available; optional registered TextModelNode selected-provider suggestions are MOCK_ONLY verified / actual provider NOT_RUN.
- Priority/dependencies: P1; D03, D04, D05, D06; packages D05, D07
- Remaining/next check: Multiple source-bound structured endings can be proposed/compared; no graph of consequence propagation or automatic branch-to-manuscript synthesis.
- Subpath Existing manual/domain operations: bounded existing implementation / CONNECTED / CONTRACT_VERIFIED / AVAILABLE.
- Subpath Selected-model structured planning suggestions: IMPLEMENTED / CONNECTED / MOCK_ONLY / NOT_CONFIGURED. At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes.
- Subpath Explicit marker rule/plot extraction: IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE. Only explicit bilingual rule lines or complete six-field three-act markers; incomplete/duplicate plot markers yield findings. Saves ABILITY/PLOT DRAFT only; not automatic extraction of unstated facts.

### G. Foreshadowing and continuity

#### G01 · Foreshadowing records

IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:131; full original definition unavailable.
- Before: Foreshadowing CRUD and PendingCanon existed.
- After: Persisted strict privacy fixes plus reviewable extracted candidates integrated.
- Source/UI: `app/services/narrative_finding_service.py`, `app/services/continuity_finding_service.py`, `app/lore/continuity_engine.py`, `app/review.py`, `frontend/src/novel/StoryDatabase.tsx`, `frontend/src/novel/ContinuityCheckPanel.tsx`, `frontend/src/novel/WorldBuildingDashboard.tsx`
- API: GET /novels/{nid}/foreshadowing/reminders; POST /projects/{id}/continuity/checks; GET/POST narrative finding routes in app/api.py
- Storage: File/PostgreSQL timeline/foreshadowing/Canon/findings; conservative persisted privacy
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/privacy-recovery-focused.txt; tests/test_phase4_foreshadowing.py; tests/test_narrative_detection.py; tests/test_continuity_lifecycle.py; tests/test_r2_privacy_persistence.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D00, D05, D06; packages D01, D07
- Remaining/next check: Final real PostgreSQL/restart check pending.

#### G02 · Foreshadowing payoff tracking

PARTIAL / CONNECTED / NOT_RUN / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:132; full original definition unavailable.
- Before: Tracker/lifecycle metadata existed.
- After: Existing status/reminder display retained with durable privacy.
- Source/UI: `app/services/narrative_finding_service.py`, `app/services/continuity_finding_service.py`, `app/lore/continuity_engine.py`, `app/review.py`, `frontend/src/novel/StoryDatabase.tsx`, `frontend/src/novel/ContinuityCheckPanel.tsx`, `frontend/src/novel/WorldBuildingDashboard.tsx`
- API: GET /novels/{nid}/foreshadowing/reminders; POST /projects/{id}/continuity/checks; GET/POST narrative finding routes in app/api.py
- Storage: File/PostgreSQL timeline/foreshadowing/Canon/findings; conservative persisted privacy
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/privacy-recovery-focused.txt; tests/test_phase4_foreshadowing.py; tests/test_narrative_detection.py; tests/test_continuity_lifecycle.py; tests/test_r2_privacy_persistence.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D00, D05, D06; packages D01, D07
- Remaining/next check: Comprehensive payoff linkage and semantic lifecycle audit incomplete.

#### G03 · Overdue reminders

PARTIAL / CONNECTED / NOT_RUN / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:133; full original definition unavailable.
- Before: Chapter-aware reminder query/UI existed.
- After: Existing deterministic reminders retained.
- Source/UI: `app/services/narrative_finding_service.py`, `app/services/continuity_finding_service.py`, `app/lore/continuity_engine.py`, `app/review.py`, `frontend/src/novel/StoryDatabase.tsx`, `frontend/src/novel/ContinuityCheckPanel.tsx`, `frontend/src/novel/WorldBuildingDashboard.tsx`
- API: GET /novels/{nid}/foreshadowing/reminders; POST /projects/{id}/continuity/checks; GET/POST narrative finding routes in app/api.py
- Storage: File/PostgreSQL timeline/foreshadowing/Canon/findings; conservative persisted privacy
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/privacy-recovery-focused.txt; tests/test_phase4_foreshadowing.py; tests/test_narrative_detection.py; tests/test_continuity_lifecycle.py; tests/test_r2_privacy_persistence.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D00, D05, D06; packages D01, D07
- Remaining/next check: No scheduled/background notification delivery; query is not a notification service.

#### G04 · Timeline conflict checks

IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:134; full original definition unavailable.
- Before: Deterministic continuity timeline conflict rules existed.
- After: Rules retained; stricter timeline serialization prevents cloud leakage.
- Source/UI: `app/services/narrative_finding_service.py`, `app/services/continuity_finding_service.py`, `app/lore/continuity_engine.py`, `app/review.py`, `frontend/src/novel/StoryDatabase.tsx`, `frontend/src/novel/ContinuityCheckPanel.tsx`, `frontend/src/novel/WorldBuildingDashboard.tsx`
- API: GET /novels/{nid}/foreshadowing/reminders; POST /projects/{id}/continuity/checks; GET/POST narrative finding routes in app/api.py
- Storage: File/PostgreSQL timeline/foreshadowing/Canon/findings; conservative persisted privacy
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/privacy-recovery-focused.txt; tests/test_phase4_foreshadowing.py; tests/test_narrative_detection.py; tests/test_continuity_lifecycle.py; tests/test_r2_privacy_persistence.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D00, D05, D06; packages D01, D07
- Remaining/next check: Coverage limited to implemented rules; full story temporal reasoning not claimed.

#### G05 · Behavior consistency

PARTIAL / CONNECTED / NOT_RUN / EXPERIMENTAL
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:135; full original definition unavailable.
- Before: Deterministic character behavior rules existed.
- After: Existing checks retained with source-aware runtime filtering.
- Source/UI: `app/services/narrative_finding_service.py`, `app/services/continuity_finding_service.py`, `app/lore/continuity_engine.py`, `app/review.py`, `frontend/src/novel/StoryDatabase.tsx`, `frontend/src/novel/ContinuityCheckPanel.tsx`, `frontend/src/novel/WorldBuildingDashboard.tsx`
- API: GET /novels/{nid}/foreshadowing/reminders; POST /projects/{id}/continuity/checks; GET/POST narrative finding routes in app/api.py
- Storage: File/PostgreSQL timeline/foreshadowing/Canon/findings; conservative persisted privacy
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/privacy-recovery-focused.txt; tests/test_phase4_foreshadowing.py; tests/test_narrative_detection.py; tests/test_continuity_lifecycle.py; tests/test_r2_privacy_persistence.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D00, D05, D06; packages D01, D07
- Remaining/next check: Semantic behavior model and broad evidence-based rule catalog incomplete.

#### G06 · World-rule violation checks

PARTIAL / CONNECTED / NOT_RUN / EXPERIMENTAL
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:136; full original definition unavailable.
- Before: Approved rules/forbidden-term check existed.
- After: Conservative policy preserves approved source restrictions.
- Source/UI: `app/services/narrative_finding_service.py`, `app/services/continuity_finding_service.py`, `app/lore/continuity_engine.py`, `app/review.py`, `frontend/src/novel/StoryDatabase.tsx`, `frontend/src/novel/ContinuityCheckPanel.tsx`, `frontend/src/novel/WorldBuildingDashboard.tsx`
- API: GET /novels/{nid}/foreshadowing/reminders; POST /projects/{id}/continuity/checks; GET/POST narrative finding routes in app/api.py
- Storage: File/PostgreSQL timeline/foreshadowing/Canon/findings; conservative persisted privacy
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/privacy-recovery-focused.txt; tests/test_phase4_foreshadowing.py; tests/test_narrative_detection.py; tests/test_continuity_lifecycle.py; tests/test_r2_privacy_persistence.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D00, D05, D06; packages D01, D07
- Remaining/next check: Semantic interpretation of arbitrary world/ability rules incomplete.

#### G07 · Plot findings and resolution

IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:137; full original definition unavailable.
- Before: Findings/check/resolve APIs and UI existed.
- After: Existing workflow retained; human resolution remains explicit. Automatic post-Accept memory extraction only uses explicitly enabled guarded local TextModelNode registrations or labeled non-packaged test Mock; no safe local route records NOT_CONFIGURED without undoing accepted text. It never falls back to cloud.
- Source/UI: `app/services/narrative_finding_service.py`, `app/services/continuity_finding_service.py`, `app/lore/continuity_engine.py`, `app/review.py`, `frontend/src/novel/StoryDatabase.tsx`, `frontend/src/novel/ContinuityCheckPanel.tsx`, `frontend/src/novel/WorldBuildingDashboard.tsx`
- API: GET /novels/{nid}/foreshadowing/reminders; POST /projects/{id}/continuity/checks; GET/POST narrative finding routes in app/api.py
- Storage: File/PostgreSQL timeline/foreshadowing/Canon/findings; conservative persisted privacy
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/privacy-recovery-focused.txt; tests/test_phase4_foreshadowing.py; tests/test_narrative_detection.py; tests/test_continuity_lifecycle.py; tests/test_r2_privacy_persistence.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D00, D05, D06; packages D01, D07
- Remaining/next check: No assertion all narrative plot holes can be detected.

### H. Agent team

#### H01 · Planning Agent

PARTIAL / CONNECTED / MOCK_ONLY / NOT_CONFIGURED
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:143; full original definition unavailable.
- Before: Agent catalog/job primitives existed.
- After: Guarded selected-model executor connected; local planning recipe explicitly uses user-supplied input.
- Source/UI: `app/agent_catalog.py`, `app/services/agent_job_service.py`, `app/services/agent_context_service.py`, `app/workflow_api.py`, `app/model_runtime.py`, `frontend/src/novel/AgentTeamPanel.tsx`, `frontend/src/novel/AgentQueuePanel.tsx`, `frontend/src/novel/AgentResultReview.tsx`
- API: GET /agents; POST /agent-jobs; GET /agent-jobs/{id}; Agent review/apply routes; Workflow Agent execute/synchronize routes
- Storage: Persisted Agent jobs; existing review/apply state; scope-bound workflow sidecars
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; tests/test_phase6_agent_jobs.py; tests/test_r2_provider_execution.py; tests/test_r2_workflow_execution.py; tests/test_r2_outbound_dispatch_authority.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Selected text adapter; actual model NOT_RUN
- Priority/dependencies: P2; D01, D04, D05, D06, D08; packages D04, D13
- Remaining/next check: Specialized structured planning outputs/domain application and real model quality incomplete.

#### H02 · Writing Agent

IMPLEMENTED / CONNECTED / MOCK_ONLY / NOT_CONFIGURED
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:144; full original definition unavailable.
- Before: Generation/Agent review/apply existed.
- After: Actual selected-model job execution, source/usage provenance and restart failure recovery connected.
- Source/UI: `app/agent_catalog.py`, `app/services/agent_job_service.py`, `app/services/agent_context_service.py`, `app/workflow_api.py`, `app/model_runtime.py`, `frontend/src/novel/AgentTeamPanel.tsx`, `frontend/src/novel/AgentQueuePanel.tsx`, `frontend/src/novel/AgentResultReview.tsx`
- API: GET /agents; POST /agent-jobs; GET /agent-jobs/{id}; Agent review/apply routes; Workflow Agent execute/synchronize routes
- Storage: Persisted Agent jobs; existing review/apply state; scope-bound workflow sidecars
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; tests/test_phase6_agent_jobs.py; tests/test_r2_provider_execution.py; tests/test_r2_workflow_execution.py; tests/test_r2_outbound_dispatch_authority.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Selected text adapter; actual model NOT_RUN
- Priority/dependencies: P2; D01, D04, D05, D06, D08; packages D04, D13
- Remaining/next check: Real provider NOT_RUN; generated work still needs explicit review/apply.

#### H03 · Editing Agent

PARTIAL / CONNECTED / MOCK_ONLY / NOT_CONFIGURED
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:145; full original definition unavailable.
- Before: Generic review/apply roles existed.
- After: Guarded executor shared; result approval remains explicit.
- Source/UI: `app/agent_catalog.py`, `app/services/agent_job_service.py`, `app/services/agent_context_service.py`, `app/workflow_api.py`, `app/model_runtime.py`, `frontend/src/novel/AgentTeamPanel.tsx`, `frontend/src/novel/AgentQueuePanel.tsx`, `frontend/src/novel/AgentResultReview.tsx`
- API: GET /agents; POST /agent-jobs; GET /agent-jobs/{id}; Agent review/apply routes; Workflow Agent execute/synchronize routes
- Storage: Persisted Agent jobs; existing review/apply state; scope-bound workflow sidecars
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; tests/test_phase6_agent_jobs.py; tests/test_r2_provider_execution.py; tests/test_r2_workflow_execution.py; tests/test_r2_outbound_dispatch_authority.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Selected text adapter; actual model NOT_RUN
- Priority/dependencies: P2; D01, D04, D05, D06, D08; packages D04, D13
- Remaining/next check: Dedicated editorial policy/quality engine not delivered.

#### H04 · Continuity Agent

PARTIAL / CONNECTED / MOCK_ONLY / NOT_CONFIGURED
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:146; full original definition unavailable.
- Before: Continuity service existed, orchestration incomplete.
- After: Agent nodes wait for real jobs; deterministic continuity remains separate. Automatic post-Accept memory extraction only uses explicitly enabled guarded local TextModelNode registrations or labeled non-packaged test Mock; no safe local route records NOT_CONFIGURED without undoing accepted text. It never falls back to cloud.
- Source/UI: `app/agent_catalog.py`, `app/services/agent_job_service.py`, `app/services/agent_context_service.py`, `app/workflow_api.py`, `app/model_runtime.py`, `frontend/src/novel/AgentTeamPanel.tsx`, `frontend/src/novel/AgentQueuePanel.tsx`, `frontend/src/novel/AgentResultReview.tsx`
- API: GET /agents; POST /agent-jobs; GET /agent-jobs/{id}; Agent review/apply routes; Workflow Agent execute/synchronize routes
- Storage: Persisted Agent jobs; existing review/apply state; scope-bound workflow sidecars
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; tests/test_phase6_agent_jobs.py; tests/test_r2_provider_execution.py; tests/test_r2_workflow_execution.py; tests/test_r2_outbound_dispatch_authority.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Selected text adapter; actual model NOT_RUN
- Priority/dependencies: P2; D01, D04, D05, D06, D08; packages D04, D13
- Remaining/next check: Specialized automated continuity-to-finding-to-review recipe not complete.

#### H05 · Director Agent

PARTIAL / CONNECTED / MOCK_ONLY / NOT_CONFIGURED
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:147; full original definition unavailable.
- Before: Adaptation/screenplay services existed.
- After: Generic selected-model execution and local shot-proposal review recipe available.
- Source/UI: `app/agent_catalog.py`, `app/services/agent_job_service.py`, `app/services/agent_context_service.py`, `app/workflow_api.py`, `app/model_runtime.py`, `frontend/src/novel/AgentTeamPanel.tsx`, `frontend/src/novel/AgentQueuePanel.tsx`, `frontend/src/novel/AgentResultReview.tsx`
- API: GET /agents; POST /agent-jobs; GET /agent-jobs/{id}; Agent review/apply routes; Workflow Agent execute/synchronize routes
- Storage: Persisted Agent jobs; existing review/apply state; scope-bound workflow sidecars
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; tests/test_phase6_agent_jobs.py; tests/test_r2_provider_execution.py; tests/test_r2_workflow_execution.py; tests/test_r2_outbound_dispatch_authority.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Selected text adapter; actual model NOT_RUN
- Priority/dependencies: P2; D01, D04, D05, D06, D08; packages D04, D13
- Remaining/next check: Dedicated model-backed director scene/shot contract and apply closure incomplete.

#### H06 · Art Agent

PARTIAL / CONNECTED / MOCK_ONLY / NOT_CONFIGURED
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:148; full original definition unavailable.
- Before: Generic asset tasks existed; no autonomous art agent.
- After: Image review queue and Agent executor exist as distinct controlled paths.
- Source/UI: `app/agent_catalog.py`, `app/services/agent_job_service.py`, `app/services/agent_context_service.py`, `app/workflow_api.py`, `app/model_runtime.py`, `frontend/src/novel/AgentTeamPanel.tsx`, `frontend/src/novel/AgentQueuePanel.tsx`, `frontend/src/novel/AgentResultReview.tsx`
- API: GET /agents; POST /agent-jobs; GET /agent-jobs/{id}; Agent review/apply routes; Workflow Agent execute/synchronize routes
- Storage: Persisted Agent jobs; existing review/apply state; scope-bound workflow sidecars
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; tests/test_phase6_agent_jobs.py; tests/test_r2_provider_execution.py; tests/test_r2_workflow_execution.py; tests/test_r2_outbound_dispatch_authority.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Selected text adapter; actual model NOT_RUN
- Priority/dependencies: P2; D01, D04, D05, D06, D08; packages D04, D13
- Remaining/next check: No dedicated art-agent executor-to-image review workflow; generic components not full art agent.

#### H07 · Multi-Agent coordination

PARTIAL / CONNECTED / MOCK_ONLY / EXPERIMENTAL
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:149; full original definition unavailable.
- Before: Generic workflow lacked actual Agent completion gating.
- After: Bounded DAG dispatches selected-model Agent jobs, waits for real state and retains approval/failure/cancel.
- Source/UI: `app/agent_catalog.py`, `app/services/agent_job_service.py`, `app/services/agent_context_service.py`, `app/workflow_api.py`, `app/model_runtime.py`, `frontend/src/novel/AgentTeamPanel.tsx`, `frontend/src/novel/AgentQueuePanel.tsx`, `frontend/src/novel/AgentResultReview.tsx`
- API: GET /agents; POST /agent-jobs; GET /agent-jobs/{id}; Agent review/apply routes; Workflow Agent execute/synchronize routes
- Storage: Persisted Agent jobs; existing review/apply state; scope-bound workflow sidecars
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; tests/test_phase6_agent_jobs.py; tests/test_r2_provider_execution.py; tests/test_r2_workflow_execution.py; tests/test_r2_outbound_dispatch_authority.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Selected text adapter; actual model NOT_RUN
- Priority/dependencies: P2; D01, D04, D05, D06, D08; packages D04, D13
- Remaining/next check: No fully autonomous three-recipe domain closure; cross-process transactional scheduler not claimed.

### I. Screenplay

#### I01 · Novel-to-screenplay conversion

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:155; full original definition unavailable.
- Before: Screenplay service/create/export existed.
- After: Source-traceable branch-safe screenplay and approved revision fork strengthened; current per-edit CAS/history changes require their final test receipt.
- Source/UI: `app/services/screenplay_service.py`, `app/industry_export_formats.py`, `frontend/src/novel/ScreenplayPanel.tsx`
- API: GET/POST /novels/{nid}/screenplays; Screenplay scene/shot edit and revision endpoints in app/api.py
- Storage: Persisted screenplay records; branch scope; approved version fork and source provenance
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; tests/test_phase8_screenplay.py; tests/test_phase8_shots.py; tests/test_screenplay_branch_revision.py; tests/test_industry_export_queue.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D02, D03, D04, D08; packages D08, D09
- Remaining/next check: Deterministic structural conversion is not model-quality certification.

#### I02 · Industry screenplay formats

PARTIAL / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:156; full original definition unavailable.
- Before: Fountain/Markdown/DOCX exporters existed with semantic Fountain defects.
- After: Forced character/action handling, frozen resource packages and font/build improvements added.
- Source/UI: `app/services/screenplay_service.py`, `app/industry_export_formats.py`, `frontend/src/novel/ScreenplayPanel.tsx`
- API: GET/POST /novels/{nid}/screenplays; Screenplay scene/shot edit and revision endpoints in app/api.py
- Storage: Persisted screenplay records; branch scope; approved version fork and source provenance
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; tests/test_phase8_screenplay.py; tests/test_phase8_shots.py; tests/test_screenplay_branch_revision.py; tests/test_industry_export_queue.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D02, D03, D04, D08; packages D08, D09
- Remaining/next check: Target Final Draft/Word pagination/industry-layout acceptance still NOT_RUN.

#### I03 · Screenplay scenes

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:157; full original definition unavailable.
- Before: Scene model/update existed.
- After: Branch-aware authorization and version-safe approved screenplay fork added.
- Source/UI: `app/services/screenplay_service.py`, `app/industry_export_formats.py`, `frontend/src/novel/ScreenplayPanel.tsx`
- API: GET/POST /novels/{nid}/screenplays; Screenplay scene/shot edit and revision endpoints in app/api.py
- Storage: Persisted screenplay records; branch scope; approved version fork and source provenance
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; tests/test_phase8_screenplay.py; tests/test_phase8_shots.py; tests/test_screenplay_branch_revision.py; tests/test_industry_export_queue.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D02, D03, D04, D08; packages D08, D09
- Remaining/next check: Full interactive reorder/edit acceptance pending.

#### I04 · Shot records

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:158; full original definition unavailable.
- Before: Shot model/routes existed.
- After: Structured shot data preserved across guarded screenplay revision/export.
- Source/UI: `app/services/screenplay_service.py`, `app/industry_export_formats.py`, `frontend/src/novel/ScreenplayPanel.tsx`
- API: GET/POST /novels/{nid}/screenplays; Screenplay scene/shot edit and revision endpoints in app/api.py
- Storage: Persisted screenplay records; branch scope; approved version fork and source provenance
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; tests/test_phase8_screenplay.py; tests/test_phase8_shots.py; tests/test_screenplay_branch_revision.py; tests/test_industry_export_queue.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D02, D03, D04, D08; packages D08, D09
- Remaining/next check: Final UI source/order acceptance pending.

#### I05 · Shot numbering

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:159; full original definition unavailable.
- Before: Deterministic numbering existed.
- After: Numbering remains the source for storyboard/export/task provenance.
- Source/UI: `app/services/screenplay_service.py`, `app/industry_export_formats.py`, `frontend/src/novel/ScreenplayPanel.tsx`
- API: GET/POST /novels/{nid}/screenplays; Screenplay scene/shot edit and revision endpoints in app/api.py
- Storage: Persisted screenplay records; branch scope; approved version fork and source provenance
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; tests/test_phase8_screenplay.py; tests/test_phase8_shots.py; tests/test_screenplay_branch_revision.py; tests/test_industry_export_queue.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D02, D03, D04, D08; packages D08, D09
- Remaining/next check: Complex interactive reorder acceptance pending.

#### I06 · Framing/shot design

PARTIAL / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:160; full original definition unavailable.
- Before: Shot metadata carried framing.
- After: Existing editable shot fields retained; manual design flows into assets/export.
- Source/UI: `app/services/screenplay_service.py`, `app/industry_export_formats.py`, `frontend/src/novel/ScreenplayPanel.tsx`
- API: GET/POST /novels/{nid}/screenplays; Screenplay scene/shot edit and revision endpoints in app/api.py
- Storage: Persisted screenplay records; branch scope; approved version fork and source provenance
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; tests/test_phase8_screenplay.py; tests/test_phase8_shots.py; tests/test_screenplay_branch_revision.py; tests/test_industry_export_queue.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D02, D03, D04, D08; packages D08, D09
- Remaining/next check: No complete model-assisted shot-design engine.

#### I07 · Camera movement

PARTIAL / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:161; full original definition unavailable.
- Before: Camera metadata fields existed.
- After: Existing manual motion fields feed prompt/task records.
- Source/UI: `app/services/screenplay_service.py`, `app/industry_export_formats.py`, `frontend/src/novel/ScreenplayPanel.tsx`
- API: GET/POST /novels/{nid}/screenplays; Screenplay scene/shot edit and revision endpoints in app/api.py
- Storage: Persisted screenplay records; branch scope; approved version fork and source provenance
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; tests/test_phase8_screenplay.py; tests/test_phase8_shots.py; tests/test_screenplay_branch_revision.py; tests/test_industry_export_queue.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D02, D03, D04, D08; packages D08, D09
- Remaining/next check: No camera-planning/physical feasibility engine.

#### I08 · Screenplay dialogue conversion

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:162; full original definition unavailable.
- Before: Dialogue conversion/export existed.
- After: Fountain character and multiline dialogue semantics corrected.
- Source/UI: `app/services/screenplay_service.py`, `app/industry_export_formats.py`, `frontend/src/novel/ScreenplayPanel.tsx`
- API: GET/POST /novels/{nid}/screenplays; Screenplay scene/shot edit and revision endpoints in app/api.py
- Storage: Persisted screenplay records; branch scope; approved version fork and source provenance
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; tests/test_phase8_screenplay.py; tests/test_phase8_shots.py; tests/test_screenplay_branch_revision.py; tests/test_industry_export_queue.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D02, D03, D04, D08; packages D08, D09
- Remaining/next check: Target screenplay application import still NOT_RUN.

#### I09 · Action descriptions

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:163; full original definition unavailable.
- Before: Scene/shot/storyboard action text existed.
- After: Forced Fountain actions preserve text that resembles syntax/character lines.
- Source/UI: `app/services/screenplay_service.py`, `app/industry_export_formats.py`, `frontend/src/novel/ScreenplayPanel.tsx`
- API: GET/POST /novels/{nid}/screenplays; Screenplay scene/shot edit and revision endpoints in app/api.py
- Storage: Persisted screenplay records; branch scope; approved version fork and source provenance
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; tests/test_phase8_screenplay.py; tests/test_phase8_shots.py; tests/test_screenplay_branch_revision.py; tests/test_industry_export_queue.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D02, D03, D04, D08; packages D08, D09
- Remaining/next check: Industry rendered layout acceptance remains separate.

### J. Storyboard

#### J01 · Storyboard cards/review

IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:164; full original definition unavailable.
- Before: Create/edit/approve storyboard existed.
- After: Branch-safe screenplay revision leaves approved asset references unchanged.
- Source/UI: `app/services/screenplay_service.py`, `app/industry_export_formats.py`, `frontend/src/novel/ScreenplayPanel.tsx`
- API: Storyboard create/approve/update routes under /novels/{nid}/screenplays/{id}
- Storage: Persisted storyboard cards, approval and source scene/shot references
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; tests/test_phase8_storyboard.py; tests/test_screenplay_branch_revision.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D03, D04, D07; packages D08, D10
- Remaining/next check: No generated storyboard image implication.

#### J02 · Composition planning

PARTIAL / CONNECTED / NOT_RUN / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:165; full original definition unavailable.
- Before: Composition fields existed.
- After: Manual composition records remain connected to storyboard/export.
- Source/UI: `app/services/screenplay_service.py`, `app/industry_export_formats.py`, `frontend/src/novel/ScreenplayPanel.tsx`
- API: Storyboard create/approve/update routes under /novels/{nid}/screenplays/{id}
- Storage: Persisted storyboard cards, approval and source scene/shot references
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; tests/test_phase8_storyboard.py; tests/test_screenplay_branch_revision.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D03, D04, D07; packages D08, D10
- Remaining/next check: No automatic composition engine or generated image quality verification.

#### J03 · Visual descriptions

IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:166; full original definition unavailable.
- Before: Descriptions and HTML/storyboard exports existed.
- After: Descriptions retained with immutable resource snapshot export path.
- Source/UI: `app/services/screenplay_service.py`, `app/industry_export_formats.py`, `frontend/src/novel/ScreenplayPanel.tsx`
- API: Storyboard create/approve/update routes under /novels/{nid}/screenplays/{id}
- Storage: Persisted storyboard cards, approval and source scene/shot references
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; tests/test_phase8_storyboard.py; tests/test_screenplay_branch_revision.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D03, D04, D07; packages D08, D10
- Remaining/next check: Description text is not a rendered/generated visual.

#### J04 · Visual continuity

PARTIAL / CONNECTED / NOT_RUN / EXPERIMENTAL
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:167; full original definition unavailable.
- Before: Continuity fields/transition metadata existed.
- After: Approved references can be looked up lexically with provenance.
- Source/UI: `app/services/screenplay_service.py`, `app/industry_export_formats.py`, `frontend/src/novel/ScreenplayPanel.tsx`
- API: Storyboard create/approve/update routes under /novels/{nid}/screenplays/{id}
- Storage: Persisted storyboard cards, approval and source scene/shot references
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; tests/test_phase8_storyboard.py; tests/test_screenplay_branch_revision.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D03, D04, D07; packages D08, D10
- Remaining/next check: No trained visual-consistency validator; embedding/semantic inference absent.

### K. Transitions

#### K01 · Transition suggestions

PARTIAL / CONNECTED / NOT_RUN / EXPERIMENTAL
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:168; full original definition unavailable.
- Before: Deterministic suggestion/prompt service existed.
- After: Existing rule-based suggestion retained with durable screenplay state.
- Source/UI: `app/services/screenplay_service.py`, `frontend/src/novel/ScreenplayPanel.tsx`, `frontend/src/novel/ScreenplayPipelinePanel.tsx`
- API: Transition create/edit/suggest routes; POST .../transitions/{id}/prompt
- Storage: Screenplay transition records, prompt history and freeze state
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/media-work.md; tests/test_phase8_transitions.py; tests/test_phase1_video_runtime.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1/P2; D03, D04, D08, D10; packages D08, D11
- Remaining/next check: No integrated real-model transition reasoning acceptance.

#### K02 · Scene transitions

IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:169; full original definition unavailable.
- Before: Scene transition records existed.
- After: Existing editable transitions flow into source-linked exports/tasks.
- Source/UI: `app/services/screenplay_service.py`, `frontend/src/novel/ScreenplayPanel.tsx`, `frontend/src/novel/ScreenplayPipelinePanel.tsx`
- API: Transition create/edit/suggest routes; POST .../transitions/{id}/prompt
- Storage: Screenplay transition records, prompt history and freeze state
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/media-work.md; tests/test_phase8_transitions.py; tests/test_phase1_video_runtime.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1/P2; D03, D04, D08, D10; packages D08, D11
- Remaining/next check: Manual transition records only; no cinematic quality guarantee.

#### K03 · Shot transitions

IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:170; full original definition unavailable.
- Before: Shot transition records existed.
- After: Existing transition/task linkage retained.
- Source/UI: `app/services/screenplay_service.py`, `frontend/src/novel/ScreenplayPanel.tsx`, `frontend/src/novel/ScreenplayPipelinePanel.tsx`
- API: Transition create/edit/suggest routes; POST .../transitions/{id}/prompt
- Storage: Screenplay transition records, prompt history and freeze state
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/media-work.md; tests/test_phase8_transitions.py; tests/test_phase1_video_runtime.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1/P2; D03, D04, D08, D10; packages D08, D11
- Remaining/next check: Final interactive shot-transition acceptance pending.

#### K04 · Temporal transitions

PARTIAL / CONNECTED / NOT_RUN / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:171; full original definition unavailable.
- Before: Temporal transition type existed.
- After: Current manual temporal type/prompt remains available.
- Source/UI: `app/services/screenplay_service.py`, `frontend/src/novel/ScreenplayPanel.tsx`, `frontend/src/novel/ScreenplayPipelinePanel.tsx`
- API: Transition create/edit/suggest routes; POST .../transitions/{id}/prompt
- Storage: Screenplay transition records, prompt history and freeze state
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/media-work.md; tests/test_phase8_transitions.py; tests/test_phase1_video_runtime.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1/P2; D03, D04, D08, D10; packages D08, D11
- Remaining/next check: No temporal reasoning engine.

#### K05 · Spatial transitions

PARTIAL / CONNECTED / NOT_RUN / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:172; full original definition unavailable.
- Before: Spatial transition type existed.
- After: Current manual spatial type/prompt remains available.
- Source/UI: `app/services/screenplay_service.py`, `frontend/src/novel/ScreenplayPanel.tsx`, `frontend/src/novel/ScreenplayPipelinePanel.tsx`
- API: Transition create/edit/suggest routes; POST .../transitions/{id}/prompt
- Storage: Screenplay transition records, prompt history and freeze state
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/media-work.md; tests/test_phase8_transitions.py; tests/test_phase1_video_runtime.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1/P2; D03, D04, D08, D10; packages D08, D11
- Remaining/next check: No spatial planner or geometry-aware validation.

#### K06 · Emotional transitions

PARTIAL / CONNECTED / NOT_RUN / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:173; full original definition unavailable.
- Before: Emotional type/reason fields existed.
- After: Current manual rationale and prompt remain available.
- Source/UI: `app/services/screenplay_service.py`, `frontend/src/novel/ScreenplayPanel.tsx`, `frontend/src/novel/ScreenplayPipelinePanel.tsx`
- API: Transition create/edit/suggest routes; POST .../transitions/{id}/prompt
- Storage: Screenplay transition records, prompt history and freeze state
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/media-work.md; tests/test_phase8_transitions.py; tests/test_phase1_video_runtime.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1/P2; D03, D04, D08, D10; packages D08, D11
- Remaining/next check: No emotion model or quality-certified cinematic transition engine.

#### K07 · Action match cuts

PARTIAL / CONNECTED / NOT_RUN / EXPERIMENTAL
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:174; full original definition unavailable.
- Before: Keyword action matching/suggestion existed.
- After: Current deterministic matcher retained.
- Source/UI: `app/services/screenplay_service.py`, `frontend/src/novel/ScreenplayPanel.tsx`, `frontend/src/novel/ScreenplayPipelinePanel.tsx`
- API: Transition create/edit/suggest routes; POST .../transitions/{id}/prompt
- Storage: Screenplay transition records, prompt history and freeze state
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/media-work.md; tests/test_phase8_transitions.py; tests/test_phase1_video_runtime.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1/P2; D03, D04, D08, D10; packages D08, D11
- Remaining/next check: Model-assisted motion/action alignment unimplemented.

#### K08 · Transition prompt workflow

PARTIAL / CONNECTED / NOT_RUN / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:175; full original definition unavailable.
- Before: Prompt history/freeze existed.
- After: Durable prompts remain linked to scene/shot state and guarded motion submission.
- Source/UI: `app/services/screenplay_service.py`, `frontend/src/novel/ScreenplayPanel.tsx`, `frontend/src/novel/ScreenplayPipelinePanel.tsx`
- API: Transition create/edit/suggest routes; POST .../transitions/{id}/prompt
- Storage: Screenplay transition records, prompt history and freeze state
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/media-work.md; tests/test_phase8_transitions.py; tests/test_phase1_video_runtime.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1/P2; D03, D04, D08, D10; packages D08, D11
- Remaining/next check: Real transition model adapter/quality not verified; template generation is not model execution.

### L. Images and visual memory

#### L01 · Vision adapter

PARTIAL / CONNECTED / MOCK_ONLY / NOT_CONFIGURED
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:181; full original definition unavailable.
- Before: Compatible Vision adapter existed.
- After: Current adapter and analysis entry retained; no real model run.
- Source/UI: `app/asset_providers.py`, `app/services/image_job_service.py`, `app/services/visual_memory_index.py`, `app/asset_lifecycle_api.py`, `frontend/src/novel/ImageGenerationPanel.tsx`, `frontend/src/novel/ImageQueuePanel.tsx`, `frontend/src/novel/VisionAnalysisPanel.tsx`, `frontend/src/novel/VisualReferencePanel.tsx`
- API: POST /vision/analyze; POST /images/generate; GET/POST /novels/{nid}/image-jobs; POST .../image-jobs/{id}/execute|cancel|retry|accept; GET/POST .../visual-references; GET .../visual-reference-search
- Storage: Image production queue scoped by project/actor/branch; approved assets and version-bound visual-reference index
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; docs/delivery/dot-astra-rc-r2/assets-tests.xml; tests/test_asset_provider_adapter.py; tests/test_r2_media_api.py; tests/test_r2_media_lifecycle.py; tests/test_asset_lifecycle_r2.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; OpenAI-compatible Vision/image; configured Automatic1111/ComfyUI; real provider NOT_RUN
- Priority/dependencies: P2; D04, D07; packages D10
- Remaining/next check: Authorized configured vision model and output-quality/security acceptance required.

#### L02 · Image understanding

PARTIAL / CONNECTED / MOCK_ONLY / NOT_CONFIGURED
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:182; full original definition unavailable.
- Before: Image-URL analysis panel existed.
- After: Existing actual request path retained; results can inform reviewed references.
- Source/UI: `app/asset_providers.py`, `app/services/image_job_service.py`, `app/services/visual_memory_index.py`, `app/asset_lifecycle_api.py`, `frontend/src/novel/ImageGenerationPanel.tsx`, `frontend/src/novel/ImageQueuePanel.tsx`, `frontend/src/novel/VisionAnalysisPanel.tsx`, `frontend/src/novel/VisualReferencePanel.tsx`
- API: POST /vision/analyze; POST /images/generate; GET/POST /novels/{nid}/image-jobs; POST .../image-jobs/{id}/execute|cancel|retry|accept; GET/POST .../visual-references; GET .../visual-reference-search
- Storage: Image production queue scoped by project/actor/branch; approved assets and version-bound visual-reference index
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; docs/delivery/dot-astra-rc-r2/assets-tests.xml; tests/test_asset_provider_adapter.py; tests/test_r2_media_api.py; tests/test_r2_media_lifecycle.py; tests/test_asset_lifecycle_r2.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; OpenAI-compatible Vision/image; configured Automatic1111/ComfyUI; real provider NOT_RUN
- Priority/dependencies: P2; D04, D07; packages D10
- Remaining/next check: Real image-understanding quality and supported URL/vendor formats NOT_RUN.

#### L03 · Character visual understanding

PARTIAL / CONNECTED / MOCK_ONLY / NOT_CONFIGURED
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:183; full original definition unavailable.
- Before: Character-linked analysis/memory existed.
- After: Reviewed CHARACTER reference metadata has exact asset provenance and lexical lookup.
- Source/UI: `app/asset_providers.py`, `app/services/image_job_service.py`, `app/services/visual_memory_index.py`, `app/asset_lifecycle_api.py`, `frontend/src/novel/ImageGenerationPanel.tsx`, `frontend/src/novel/ImageQueuePanel.tsx`, `frontend/src/novel/VisionAnalysisPanel.tsx`, `frontend/src/novel/VisualReferencePanel.tsx`
- API: POST /vision/analyze; POST /images/generate; GET/POST /novels/{nid}/image-jobs; POST .../image-jobs/{id}/execute|cancel|retry|accept; GET/POST .../visual-references; GET .../visual-reference-search
- Storage: Image production queue scoped by project/actor/branch; approved assets and version-bound visual-reference index
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; docs/delivery/dot-astra-rc-r2/assets-tests.xml; tests/test_asset_provider_adapter.py; tests/test_r2_media_api.py; tests/test_r2_media_lifecycle.py; tests/test_asset_lifecycle_r2.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; OpenAI-compatible Vision/image; configured Automatic1111/ComfyUI; real provider NOT_RUN
- Priority/dependencies: P2; D04, D07; packages D10
- Remaining/next check: No trained identity-consistency/embedding engine; real vision quality NOT_RUN.

#### L04 · Scene visual understanding

PARTIAL / CONNECTED / MOCK_ONLY / NOT_CONFIGURED
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:184; full original definition unavailable.
- Before: Scene-linked analysis/memory existed.
- After: SCENE/LOCATION references can be approved and retrieved lexically.
- Source/UI: `app/asset_providers.py`, `app/services/image_job_service.py`, `app/services/visual_memory_index.py`, `app/asset_lifecycle_api.py`, `frontend/src/novel/ImageGenerationPanel.tsx`, `frontend/src/novel/ImageQueuePanel.tsx`, `frontend/src/novel/VisionAnalysisPanel.tsx`, `frontend/src/novel/VisualReferencePanel.tsx`
- API: POST /vision/analyze; POST /images/generate; GET/POST /novels/{nid}/image-jobs; POST .../image-jobs/{id}/execute|cancel|retry|accept; GET/POST .../visual-references; GET .../visual-reference-search
- Storage: Image production queue scoped by project/actor/branch; approved assets and version-bound visual-reference index
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; docs/delivery/dot-astra-rc-r2/assets-tests.xml; tests/test_asset_provider_adapter.py; tests/test_r2_media_api.py; tests/test_r2_media_lifecycle.py; tests/test_asset_lifecycle_r2.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; OpenAI-compatible Vision/image; configured Automatic1111/ComfyUI; real provider NOT_RUN
- Priority/dependencies: P2; D04, D07; packages D10
- Remaining/next check: No scene-semantic similarity or geometry reasoning engine.

#### L05 · Image generation/review

IMPLEMENTED / CONNECTED / MOCK_ONLY / NOT_CONFIGURED
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:185; full original definition unavailable.
- Before: Direct request/history could lose inline image bytes and status.
- After: Persistent image queue, real parameter mapping, decoder validation and explicit accept-to-library remain. Image execution now rechecks the durable attempt, cancellation, ownership and current authorization after provider resolution and before dispatch; late results cannot revive cancelled attempts.
- Source/UI: `app/asset_providers.py`, `app/services/image_job_service.py`, `app/services/visual_memory_index.py`, `app/asset_lifecycle_api.py`, `app/model_center/discovery_types.py`, `app/model_center/discovery_probes.py`, `app/model_center/discovery.py`, `app/model_center/discovery_api.py`, `app/model_center/discovery_bridge.py`, `app/model_center/domain.py`, `app/model_center/service.py`, `app/dependencies.py`, `app/main.py`, `frontend/src/novel/ImageGenerationPanel.tsx`, `frontend/src/novel/ImageQueuePanel.tsx`, `frontend/src/novel/VisionAnalysisPanel.tsx`, `frontend/src/novel/VisualReferencePanel.tsx`, `frontend/src/ui/ModelCenter.tsx`, `frontend/src/ui/LocalAiDiscovery.tsx`, `frontend/src/localAiDiscoveryApi.ts`
- API: POST /vision/analyze; POST /images/generate; GET/POST /novels/{nid}/image-jobs; POST .../image-jobs/{id}/execute|cancel|retry|accept; GET/POST .../visual-references; GET .../visual-reference-search
- Storage: Image production queue scoped by project/actor/branch; approved assets and version-bound visual-reference index
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; docs/delivery/dot-astra-rc-r2/assets-tests.xml; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; tests/test_asset_provider_adapter.py; tests/test_r2_media_api.py; tests/test_r2_media_lifecycle.py; tests/test_asset_lifecycle_r2.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; OpenAI-compatible Vision/image; configured Automatic1111/ComfyUI; real provider NOT_RUN
- Priority/dependencies: P2; D04, D07; packages D10
- Remaining/next check: Real model execution is NOT_RUN. Discovery-backed local model routes additionally depend on the open Local AI review fixes. Local cancellation cannot recall a request already sent.
- Subpath Optional Local AI Discovery registration/route bridge: PARTIAL / CONNECTED / FAILED / EXPERIMENTAL. Standalone synthetic lifecycle passed; independent review of fixed 547167e8 reports five additional locality/identity/disable/Writer-route gaps. New dirty-tree fixes pending recheck.

#### L06 · Character image generation

PARTIAL / CONNECTED / MOCK_ONLY / NOT_CONFIGURED
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:186; full original definition unavailable.
- Before: Generic character-linked generation existed.
- After: Generic image queue and reviewed character reference assets available.
- Source/UI: `app/asset_providers.py`, `app/services/image_job_service.py`, `app/services/visual_memory_index.py`, `app/asset_lifecycle_api.py`, `frontend/src/novel/ImageGenerationPanel.tsx`, `frontend/src/novel/ImageQueuePanel.tsx`, `frontend/src/novel/VisionAnalysisPanel.tsx`, `frontend/src/novel/VisualReferencePanel.tsx`
- API: POST /vision/analyze; POST /images/generate; GET/POST /novels/{nid}/image-jobs; POST .../image-jobs/{id}/execute|cancel|retry|accept; GET/POST .../visual-references; GET .../visual-reference-search
- Storage: Image production queue scoped by project/actor/branch; approved assets and version-bound visual-reference index
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; docs/delivery/dot-astra-rc-r2/assets-tests.xml; tests/test_asset_provider_adapter.py; tests/test_r2_media_api.py; tests/test_r2_media_lifecycle.py; tests/test_asset_lifecycle_r2.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; OpenAI-compatible Vision/image; configured Automatic1111/ComfyUI; real provider NOT_RUN
- Priority/dependencies: P2; D04, D07; packages D10
- Remaining/next check: Dedicated character templates/consistency control and real-model validation incomplete.

#### L07 · Scene image generation

PARTIAL / CONNECTED / MOCK_ONLY / NOT_CONFIGURED
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:187; full original definition unavailable.
- Before: Generic scene-linked generation existed.
- After: Generic parameterized queue and approved scene references available.
- Source/UI: `app/asset_providers.py`, `app/services/image_job_service.py`, `app/services/visual_memory_index.py`, `app/asset_lifecycle_api.py`, `frontend/src/novel/ImageGenerationPanel.tsx`, `frontend/src/novel/ImageQueuePanel.tsx`, `frontend/src/novel/VisionAnalysisPanel.tsx`, `frontend/src/novel/VisualReferencePanel.tsx`
- API: POST /vision/analyze; POST /images/generate; GET/POST /novels/{nid}/image-jobs; POST .../image-jobs/{id}/execute|cancel|retry|accept; GET/POST .../visual-references; GET .../visual-reference-search
- Storage: Image production queue scoped by project/actor/branch; approved assets and version-bound visual-reference index
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; docs/delivery/dot-astra-rc-r2/assets-tests.xml; tests/test_asset_provider_adapter.py; tests/test_r2_media_api.py; tests/test_r2_media_lifecycle.py; tests/test_asset_lifecycle_r2.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; OpenAI-compatible Vision/image; configured Automatic1111/ComfyUI; real provider NOT_RUN
- Priority/dependencies: P2; D04, D07; packages D10
- Remaining/next check: Dedicated scene-generation/continuity workflow incomplete.

#### L08 · Cover creation workflow

MISSING / DISCONNECTED / NOT_RUN / UNAVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:188; full original definition unavailable.
- Before: No dedicated cover workflow found.
- After: Generic image prompts can request a cover but no dedicated cover product was added.
- Source/UI: `app/asset_providers.py`, `app/services/image_job_service.py`, `app/services/visual_memory_index.py`, `app/asset_lifecycle_api.py`, `No dedicated implemented workflow`
- API: No dedicated callable product workflow
- Storage: Image production queue scoped by project/actor/branch; approved assets and version-bound visual-reference index
- Evidence/test inventory:
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; OpenAI-compatible Vision/image; configured Automatic1111/ComfyUI; real provider NOT_RUN
- Priority/dependencies: P2; D04, D07; packages D10
- Remaining/next check: Need composition/title-safe-area/typography/review/export workflow; generic prompt is not completion.

#### L09 · Storyboard image generation

MISSING / DISCONNECTED / NOT_RUN / UNAVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:189; full original definition unavailable.
- Before: Storyboard visual cards lacked image generation.
- After: Image queue exists independently; storyboard assets may be manually linked.
- Source/UI: `app/asset_providers.py`, `app/services/image_job_service.py`, `app/services/visual_memory_index.py`, `app/asset_lifecycle_api.py`, `No dedicated implemented workflow`
- API: No dedicated callable product workflow
- Storage: Image production queue scoped by project/actor/branch; approved assets and version-bound visual-reference index
- Evidence/test inventory:
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; OpenAI-compatible Vision/image; configured Automatic1111/ComfyUI; real provider NOT_RUN
- Priority/dependencies: P2; D04, D07; packages D10
- Remaining/next check: Need storyboard-specific image generation and versioned card acceptance/association.

#### L10 · Visual memory retrieval

PARTIAL / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:190; full original definition unavailable.
- Before: Visual memory records lacked a real index.
- After: Approved version/digest-bound Unicode lexical/metadata index rebuilds safely and returns provenance.
- Source/UI: `app/asset_providers.py`, `app/services/image_job_service.py`, `app/services/visual_memory_index.py`, `app/asset_lifecycle_api.py`, `frontend/src/novel/ImageGenerationPanel.tsx`, `frontend/src/novel/ImageQueuePanel.tsx`, `frontend/src/novel/VisionAnalysisPanel.tsx`, `frontend/src/novel/VisualReferencePanel.tsx`
- API: POST /vision/analyze; POST /images/generate; GET/POST /novels/{nid}/image-jobs; POST .../image-jobs/{id}/execute|cancel|retry|accept; GET/POST .../visual-references; GET .../visual-reference-search
- Storage: Image production queue scoped by project/actor/branch; approved assets and version-bound visual-reference index
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; docs/delivery/dot-astra-rc-r2/assets-tests.xml; tests/test_asset_provider_adapter.py; tests/test_r2_media_api.py; tests/test_r2_media_lifecycle.py; tests/test_asset_lifecycle_r2.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Deterministic LEXICAL_METADATA; embeddings_available=false; inference_performed=false
- Priority/dependencies: P2; D04, D07; packages D10
- Remaining/next check: No embeddings, visual semantic search or inference; full-scale performance not benchmarked.

### M. Asset library

#### M01 · Asset library

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:191; full original definition unavailable.
- Before: Asset service/API/UI existed.
- After: Digest/size/id/path checks, atomic publication, restore/recycle bin and permission-aware reads strengthened.
- Source/UI: `app/services/asset_library_service.py`, `app/asset_lifecycle_api.py`, `app/services/export_resource_snapshot.py`, `frontend/src/novel/AssetLibraryPanel.tsx`, `frontend/src/novel/AssetInspector.tsx`
- API: GET/POST /novels/{nid}/assets; GET/DELETE /assets/{asset_id} (owned project/branch query required in collaboration); GET .../asset-trash; POST .../assets/{id}/restore; GET .../assets/{id}/references
- Storage: Verified owned binary assets plus atomic metadata; recoverable tombstones; derivative lineage; frozen export resources
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/assets-tests.xml; docs/delivery/dot-astra-rc-r2/assets-work.md; tests/test_asset_lifecycle_r2.py; tests/test_asset_safety.py; tests/test_export_resource_packages.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1/P2; D02, D04, D07, D08, D10; packages D09, D10, D11, D12
- Remaining/next check: Whole-product reference scanning and archive reimport incomplete.

#### M02 · Image asset storage

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:192; full original definition unavailable.
- Before: Generic storage accepted image MIME.
- After: Accepted generated images must decode; generic upload preserves opaque-byte contract and honest preview errors.
- Source/UI: `app/services/asset_library_service.py`, `app/asset_lifecycle_api.py`, `app/services/export_resource_snapshot.py`, `frontend/src/novel/AssetLibraryPanel.tsx`, `frontend/src/novel/AssetInspector.tsx`
- API: GET/POST /novels/{nid}/assets; GET/DELETE /assets/{asset_id} (owned project/branch query required in collaboration); GET .../asset-trash; POST .../assets/{id}/restore; GET .../assets/{id}/references
- Storage: Verified owned binary assets plus atomic metadata; recoverable tombstones; derivative lineage; frozen export resources
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/assets-tests.xml; docs/delivery/dot-astra-rc-r2/assets-work.md; tests/test_asset_lifecycle_r2.py; tests/test_asset_safety.py; tests/test_export_resource_packages.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1/P2; D02, D04, D07, D08, D10; packages D09, D10, D11, D12
- Remaining/next check: Declared MIME on generic upload alone does not prove decoding. Existing ImageInfiniteCanvas retains zoom/pan/select/drag/align/group/layer/lock/undo; no raster editing or semantic inference claim.

#### M03 · Audio asset storage

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:193; full original definition unavailable.
- Before: Generic audio MIME storage existed.
- After: TTS ingress now validates real audio bytes/duration before creating owned asset.
- Source/UI: `app/services/asset_library_service.py`, `app/asset_lifecycle_api.py`, `app/services/export_resource_snapshot.py`, `frontend/src/novel/AssetLibraryPanel.tsx`, `frontend/src/novel/AssetInspector.tsx`
- API: GET/POST /novels/{nid}/assets; GET/DELETE /assets/{asset_id} (owned project/branch query required in collaboration); GET .../asset-trash; POST .../assets/{id}/restore; GET .../assets/{id}/references
- Storage: Verified owned binary assets plus atomic metadata; recoverable tombstones; derivative lineage; frozen export resources
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/assets-tests.xml; docs/delivery/dot-astra-rc-r2/assets-work.md; tests/test_asset_lifecycle_r2.py; tests/test_asset_safety.py; tests/test_export_resource_packages.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1/P2; D02, D04, D07, D08, D10; packages D09, D10, D11, D12
- Remaining/next check: Opaque manual-upload semantics differ; provider playback on target Windows still unrun.

#### M04 · Video asset storage

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:194; full original definition unavailable.
- Before: Generic video MIME storage existed.
- After: Generated download ingress uses pinned-network policy plus ffprobe/ffmpeg decode.
- Source/UI: `app/services/asset_library_service.py`, `app/asset_lifecycle_api.py`, `app/services/export_resource_snapshot.py`, `frontend/src/novel/AssetLibraryPanel.tsx`, `frontend/src/novel/AssetInspector.tsx`
- API: GET/POST /novels/{nid}/assets; GET/DELETE /assets/{asset_id} (owned project/branch query required in collaboration); GET .../asset-trash; POST .../assets/{id}/restore; GET .../assets/{id}/references
- Storage: Verified owned binary assets plus atomic metadata; recoverable tombstones; derivative lineage; frozen export resources
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/assets-tests.xml; docs/delivery/dot-astra-rc-r2/assets-work.md; tests/test_asset_lifecycle_r2.py; tests/test_asset_safety.py; tests/test_export_resource_packages.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1/P2; D02, D04, D07, D08, D10; packages D09, D10, D11, D12
- Remaining/next check: ffmpeg licensing/bundling and native playback pending; generic uploads retain opaque contract.

#### M05 · Project ownership

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:195; full original definition unavailable.
- Before: Novel ownership existed.
- After: Project/branch provenance, ID validation and current membership checks guard new asset paths.
- Source/UI: `app/services/asset_library_service.py`, `app/asset_lifecycle_api.py`, `app/services/export_resource_snapshot.py`, `frontend/src/novel/AssetLibraryPanel.tsx`, `frontend/src/novel/AssetInspector.tsx`
- API: GET/POST /novels/{nid}/assets; GET/DELETE /assets/{asset_id} (owned project/branch query required in collaboration); GET .../asset-trash; POST .../assets/{id}/restore; GET .../assets/{id}/references
- Storage: Verified owned binary assets plus atomic metadata; recoverable tombstones; derivative lineage; frozen export resources
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/assets-tests.xml; docs/delivery/dot-astra-rc-r2/assets-work.md; tests/test_asset_lifecycle_r2.py; tests/test_asset_safety.py; tests/test_export_resource_packages.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1/P2; D02, D04, D07, D08, D10; packages D09, D10, D11, D12
- Remaining/next check: Legacy unbound records are not auto-adopted into a branch; final cross-user UI acceptance pending.

#### M06 · Character associations

PARTIAL / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:196; full original definition unavailable.
- Before: Association metadata could reference characters.
- After: Reviewed CHARACTER references and guarded lineage metadata are persisted and searchable.
- Source/UI: `app/services/asset_library_service.py`, `app/asset_lifecycle_api.py`, `app/services/export_resource_snapshot.py`, `frontend/src/novel/AssetLibraryPanel.tsx`, `frontend/src/novel/AssetInspector.tsx`
- API: GET/POST /novels/{nid}/assets; GET/DELETE /assets/{asset_id} (owned project/branch query required in collaboration); GET .../asset-trash; POST .../assets/{id}/restore; GET .../assets/{id}/references
- Storage: Verified owned binary assets plus atomic metadata; recoverable tombstones; derivative lineage; frozen export resources
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/assets-tests.xml; docs/delivery/dot-astra-rc-r2/assets-work.md; tests/test_asset_lifecycle_r2.py; tests/test_asset_safety.py; tests/test_export_resource_packages.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1/P2; D02, D04, D07, D08, D10; packages D09, D10, D11, D12
- Remaining/next check: Manual entity-ID entry; universal typed foreign keys/bulk relation UI incomplete.

#### M07 · Scene associations

PARTIAL / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:197; full original definition unavailable.
- Before: Scene/screenplay asset tasks existed.
- After: Source tasks, scene/shot references, digest/version lineage and video assembly provenance retained.
- Source/UI: `app/services/asset_library_service.py`, `app/asset_lifecycle_api.py`, `app/services/export_resource_snapshot.py`, `frontend/src/novel/AssetLibraryPanel.tsx`, `frontend/src/novel/AssetInspector.tsx`
- API: GET/POST /novels/{nid}/assets; GET/DELETE /assets/{asset_id} (owned project/branch query required in collaboration); GET .../asset-trash; POST .../assets/{id}/restore; GET .../assets/{id}/references
- Storage: Verified owned binary assets plus atomic metadata; recoverable tombstones; derivative lineage; frozen export resources
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/assets-tests.xml; docs/delivery/dot-astra-rc-r2/assets-work.md; tests/test_asset_lifecycle_r2.py; tests/test_asset_safety.py; tests/test_export_resource_packages.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1/P2; D02, D04, D07, D08, D10; packages D09, D10, D11, D12
- Remaining/next check: Universal scene relation constraints and full dependency/reimport handling incomplete.

### N. Video production

#### N01 · Shot-to-asset task pipeline

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:198; full original definition unavailable.
- Before: Screenplay shot/asset tasks existed.
- After: Owned shot/asset tasks retain file validation and result fencing. Legacy asset-task cloud dispatch now fails closed because no complete exact-prompt review exists; individual authorized local dispatch remains supported. Bulk workers require per-task authority callbacks.
- Source/UI: `app/services/screenplay_service.py`, `app/services/video_assembly_service.py`, `app/media_files.py`, `app/media_frames.py`, `app/video_assembly_api.py`, `frontend/src/novel/VideoTaskInspector.tsx`, `frontend/src/novel/MotionPrivacyPanel.tsx`, `frontend/src/novel/VideoAssemblyPanel.tsx`
- API: Motion Task submit/poll/cancel/retry/frame/privacy routes; GET/POST /novels/{nid}/screenplays/{id}/video-assemblies
- Storage: Branch-shared screenplay/motion state; verified assets; persisted clip/source/digest manifests
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; tests/test_phase1_video_runtime.py; tests/test_r2_media_lifecycle.py; tests/test_r2_media_api.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Configured HTTP video adapter; ffmpeg/ffprobe for local validation/assembly; model NOT_RUN
- Priority/dependencies: P2; D08, D10; packages D11
- Remaining/next check: Remote legacy asset execution is UNAVAILABLE pending a proper consent workflow; this safe restriction is not feature completion. Real video generation and multi-host workers remain unverified.

#### N02 · Storyboard-to-video assembly

PARTIAL / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:199; full original definition unavailable.
- Before: Storyboard approval could produce tasks but no finished cut.
- After: Author orders/trims owned clips; real bounded silent 640x360/24fps MP4 review rendition plus manifest.
- Source/UI: `app/services/screenplay_service.py`, `app/services/video_assembly_service.py`, `app/media_files.py`, `app/media_frames.py`, `app/video_assembly_api.py`, `frontend/src/novel/VideoTaskInspector.tsx`, `frontend/src/novel/MotionPrivacyPanel.tsx`, `frontend/src/novel/VideoAssemblyPanel.tsx`
- API: Motion Task submit/poll/cancel/retry/frame/privacy routes; GET/POST /novels/{nid}/screenplays/{id}/video-assemblies
- Storage: Branch-shared screenplay/motion state; verified assets; persisted clip/source/digest manifests
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; tests/test_phase1_video_runtime.py; tests/test_r2_media_lifecycle.py; tests/test_r2_media_api.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Configured HTTP video adapter; ffmpeg/ffprobe for local validation/assembly; model NOT_RUN
- Priority/dependencies: P2; D08, D10; packages D11
- Remaining/next check: Not final-master production; no soundtrack/compositor/automatic storyboard rendering.

#### N03 · Motion prompt/task handoff

PARTIAL / CONNECTED / MOCK_ONLY / NOT_CONFIGURED
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:200; full original definition unavailable.
- Before: Motion prompt and task endpoints existed.
- After: Motion submit/poll/cancel/retry retains actual file validation. Cloud review now binds complete request_sha256: prompt, both frame references, constraints, provider/model/endpoint and owner scope. Final current authorization/state/attempt/source-policy/frame checks run after preparation; stale prompt-only consent cannot authorize dispatch.
- Source/UI: `app/services/screenplay_service.py`, `app/services/video_assembly_service.py`, `app/media_files.py`, `app/media_frames.py`, `app/video_assembly_api.py`, `frontend/src/novel/VideoTaskInspector.tsx`, `frontend/src/novel/MotionPrivacyPanel.tsx`, `frontend/src/novel/VideoAssemblyPanel.tsx`
- API: Motion Task submit/poll/cancel/retry/frame/privacy routes; GET/POST /novels/{nid}/screenplays/{id}/video-assemblies
- Storage: Branch-shared screenplay/motion state; verified assets; persisted clip/source/digest manifests
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; tests/test_phase1_video_runtime.py; tests/test_r2_media_lifecycle.py; tests/test_r2_media_api.py; tests/test_r2_legacy_egress_guards.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Configured HTTP video adapter; ffmpeg/ffprobe for local validation/assembly; model NOT_RUN
- Priority/dependencies: P2; D08, D10; packages D11
- Remaining/next check: Remote provider NOT_RUN; review must be repeated for legacy prompt-only approvals. Callback is shared-secret rather than all-vendor asymmetric verification. Windows codec distribution remains pending.

#### N04 · Start-frame handling

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:201; full original definition unavailable.
- Before: Start-frame storage/history existed.
- After: Local frame resolves owned current asset/shot/storyboard bytes with image decode and digest/version.
- Source/UI: `app/services/screenplay_service.py`, `app/services/video_assembly_service.py`, `app/media_files.py`, `app/media_frames.py`, `app/video_assembly_api.py`, `frontend/src/novel/VideoTaskInspector.tsx`, `frontend/src/novel/MotionPrivacyPanel.tsx`, `frontend/src/novel/VideoAssemblyPanel.tsx`
- API: Motion Task submit/poll/cancel/retry/frame/privacy routes; GET/POST /novels/{nid}/screenplays/{id}/video-assemblies
- Storage: Branch-shared screenplay/motion state; verified assets; persisted clip/source/digest manifests
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; tests/test_phase1_video_runtime.py; tests/test_r2_media_lifecycle.py; tests/test_r2_media_api.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Configured HTTP video adapter; ffmpeg/ffprobe for local validation/assembly; model NOT_RUN
- Priority/dependencies: P2; D08, D10; packages D11
- Remaining/next check: Opaque external frame URLs have content_verified=false; real provider use NOT_RUN.

#### N05 · End-frame handling

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:202; full original definition unavailable.
- Before: End-frame storage/history existed.
- After: Same actual frame validation/privacy and active-task freeze as start frame.
- Source/UI: `app/services/screenplay_service.py`, `app/services/video_assembly_service.py`, `app/media_files.py`, `app/media_frames.py`, `app/video_assembly_api.py`, `frontend/src/novel/VideoTaskInspector.tsx`, `frontend/src/novel/MotionPrivacyPanel.tsx`, `frontend/src/novel/VideoAssemblyPanel.tsx`
- API: Motion Task submit/poll/cancel/retry/frame/privacy routes; GET/POST /novels/{nid}/screenplays/{id}/video-assemblies
- Storage: Branch-shared screenplay/motion state; verified assets; persisted clip/source/digest manifests
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; tests/test_phase1_video_runtime.py; tests/test_r2_media_lifecycle.py; tests/test_r2_media_api.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Configured HTTP video adapter; ffmpeg/ffprobe for local validation/assembly; model NOT_RUN
- Priority/dependencies: P2; D08, D10; packages D11
- Remaining/next check: External URL/frame interpretation and target model support unverified.

#### N06 · Video provider execution

PARTIAL / CONNECTED / MOCK_ONLY / NOT_CONFIGURED
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:203; full original definition unavailable.
- Before: HTTP submit/poll/callback path existed.
- After: Motion submit/poll/cancel/retry retains actual file validation. Cloud review now binds complete request_sha256: prompt, both frame references, constraints, provider/model/endpoint and owner scope. Final current authorization/state/attempt/source-policy/frame checks run after preparation; stale prompt-only consent cannot authorize dispatch.
- Source/UI: `app/services/screenplay_service.py`, `app/services/video_assembly_service.py`, `app/media_files.py`, `app/media_frames.py`, `app/video_assembly_api.py`, `app/model_center/discovery_types.py`, `app/model_center/discovery_probes.py`, `app/model_center/discovery.py`, `app/model_center/discovery_api.py`, `app/model_center/discovery_bridge.py`, `app/model_center/domain.py`, `app/model_center/service.py`, `app/dependencies.py`, `app/main.py`, `frontend/src/novel/VideoTaskInspector.tsx`, `frontend/src/novel/MotionPrivacyPanel.tsx`, `frontend/src/novel/VideoAssemblyPanel.tsx`, `frontend/src/ui/ModelCenter.tsx`, `frontend/src/ui/LocalAiDiscovery.tsx`, `frontend/src/localAiDiscoveryApi.ts`
- API: Motion Task submit/poll/cancel/retry/frame/privacy routes; GET/POST /novels/{nid}/screenplays/{id}/video-assemblies
- Storage: Branch-shared screenplay/motion state; verified assets; persisted clip/source/digest manifests
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; tests/test_phase1_video_runtime.py; tests/test_r2_media_lifecycle.py; tests/test_r2_media_api.py; tests/test_r2_legacy_egress_guards.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Configured HTTP video adapter; ffmpeg/ffprobe for local validation/assembly; model NOT_RUN
- Priority/dependencies: P2; D08, D10; packages D11
- Remaining/next check: Remote provider NOT_RUN; review must be repeated for legacy prompt-only approvals. Callback is shared-secret rather than all-vendor asymmetric verification. Windows codec distribution remains pending.
- Subpath Optional Local AI Discovery registration/route bridge: PARTIAL / CONNECTED / FAILED / EXPERIMENTAL. Standalone synthetic lifecycle passed; independent review of fixed 547167e8 reports five additional locality/identity/disable/Writer-route gaps. New dirty-tree fixes pending recheck.

### O. Speech and audiobook

#### O01 · TTS execution

IMPLEMENTED / CONNECTED / MOCK_ONLY / NOT_CONFIGURED
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:204; full original definition unavailable.
- Before: Compatible speech API existed but success could depend on URL-only response.
- After: Real binary/URL audio validation, usage/error/cancel fencing, verified owned audio asset and preview. Current attempt/cancellation/source privacy/project authority are rechecked after provider resolution and immediately before synthesis; original cancellation/revocation recording-provider regressions now pass.
- Source/UI: `app/audio_providers.py`, `app/audio_production_store.py`, `app/services/audiobook_service.py`, `app/media_files.py`, `frontend/src/novel/AudioGenerationPanel.tsx`, `frontend/src/novel/AudioTaskInspector.tsx`, `frontend/src/novel/AudiobookManifestPanel.tsx`
- API: POST /speech/synthesize; GET /novels/{nid}/audiobook/jobs; POST .../audiobook/chapters/{id}/queue; POST .../audiobook/jobs/{id}/execute|cancel|retry; POST .../audiobook/chapters/{id}/queue-segments; POST .../audiobook/chapters/{id}/export
- Storage: Actor/branch-bound voice bindings, pronunciation dictionary, immutable text snapshots, jobs and audio assets
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; tests/test_audio_providers.py; tests/test_r2_media_lifecycle.py; tests/test_r2_media_api.py; tests/test_r2_outbound_dispatch_authority.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; OpenAI-compatible TTS; real provider NOT_RUN; PCM WAV local assembly
- Priority/dependencies: P2; D04, D07; packages D12
- Remaining/next check: No real TTS/model quality; async-only providers without poll adapter unavailable.

#### O02 · Character voice profiles

IMPLEMENTED / CONNECTED / MOCK_ONLY / NOT_CONFIGURED
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:205; full original definition unavailable.
- Before: Voice bindings/history already existed.
- After: Durable bindings, pronunciation and authorization notes captured into jobs/manifests.
- Source/UI: `app/audio_providers.py`, `app/audio_production_store.py`, `app/services/audiobook_service.py`, `app/media_files.py`, `frontend/src/novel/AudioGenerationPanel.tsx`, `frontend/src/novel/AudioTaskInspector.tsx`, `frontend/src/novel/AudiobookManifestPanel.tsx`
- API: POST /speech/synthesize; GET /novels/{nid}/audiobook/jobs; POST .../audiobook/chapters/{id}/queue; POST .../audiobook/jobs/{id}/execute|cancel|retry; POST .../audiobook/chapters/{id}/queue-segments; POST .../audiobook/chapters/{id}/export
- Storage: Actor/branch-bound voice bindings, pronunciation dictionary, immutable text snapshots, jobs and audio assets
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; tests/test_audio_providers.py; tests/test_r2_media_lifecycle.py; tests/test_r2_media_api.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; OpenAI-compatible TTS; real provider NOT_RUN; PCM WAV local assembly
- Priority/dependencies: P2; D04, D07; packages D12
- Remaining/next check: No multi-speaker automatic dialogue detection; actual authorized voice verification required.

#### O03 · Audiobook chapters

PARTIAL / CONNECTED / MOCK_ONLY / NOT_CONFIGURED
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:206; full original definition unavailable.
- Before: Chapter manifests/queues existed in later baseline, despite historical TODO.
- After: Immutable reviewed text, ordered sentence queues, retry/recovery, verified audio and PCM WAV concatenate/export. Current attempt/cancellation/source privacy/project authority are rechecked after provider resolution and immediately before synthesis; original cancellation/revocation recording-provider regressions now pass.
- Source/UI: `app/audio_providers.py`, `app/audio_production_store.py`, `app/services/audiobook_service.py`, `app/media_files.py`, `frontend/src/novel/AudioGenerationPanel.tsx`, `frontend/src/novel/AudioTaskInspector.tsx`, `frontend/src/novel/AudiobookManifestPanel.tsx`
- API: POST /speech/synthesize; GET /novels/{nid}/audiobook/jobs; POST .../audiobook/chapters/{id}/queue; POST .../audiobook/jobs/{id}/execute|cancel|retry; POST .../audiobook/chapters/{id}/queue-segments; POST .../audiobook/chapters/{id}/export
- Storage: Actor/branch-bound voice bindings, pronunciation dictionary, immutable text snapshots, jobs and audio assets
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; tests/test_audio_providers.py; tests/test_r2_media_lifecycle.py; tests/test_r2_media_api.py; tests/test_r2_outbound_dispatch_authority.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; OpenAI-compatible TTS; real provider NOT_RUN; PCM WAV local assembly
- Priority/dependencies: P2; D04, D07; packages D12
- Remaining/next check: Mixed codec/sample-rate mastering, automatic multi-character detection and aligned subtitles incomplete.

#### O04 · Emotion narration

PARTIAL / CONNECTED / CONTRACT_VERIFIED / UNAVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:207; full original definition unavailable.
- Before: No complete emotion narration engine found.
- After: Neutral supported contract and explicit rejection of unsupported emotions replace fake spoken emotion tags.
- Source/UI: `app/audio_providers.py`, `app/audio_production_store.py`, `app/services/audiobook_service.py`, `app/media_files.py`, `frontend/src/novel/AudioGenerationPanel.tsx`, `frontend/src/novel/AudioTaskInspector.tsx`, `frontend/src/novel/AudiobookManifestPanel.tsx`
- API: POST /speech/synthesize; GET /novels/{nid}/audiobook/jobs; POST .../audiobook/chapters/{id}/queue; POST .../audiobook/jobs/{id}/execute|cancel|retry; POST .../audiobook/chapters/{id}/queue-segments; POST .../audiobook/chapters/{id}/export
- Storage: Actor/branch-bound voice bindings, pronunciation dictionary, immutable text snapshots, jobs and audio assets
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; tests/test_audio_providers.py; tests/test_r2_media_lifecycle.py; tests/test_r2_media_api.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; OpenAI-compatible TTS; real provider NOT_RUN; PCM WAV local assembly
- Priority/dependencies: P2; D04, D07; packages D12
- Remaining/next check: No supported expressive/emotion provider mapping verified; rejecting unsupported input is not emotion synthesis.

### P. Plugins

#### P01 · Plugin execution/runtime

PARTIAL / DISCONNECTED / NOT_RUN / UNAVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:213; full original definition unavailable.
- Before: Manifest surface existed; PR26 was an unverified sandbox prototype.
- After: Declarative packages manageable; executable runtime remains execution_supported=false, DENY_ALL.
- Source/UI: `app/plugin_contracts.py`, `app/plugin_package_manager.py`, `app/plugin_management_api.py`, `app/plugin_runtime_contracts.py`, `frontend/src/novel/PluginManagerPanel.tsx`, `frontend/src/novel/PluginInspector.tsx`
- API: GET /plugins; GET /plugins/runtime-status; Plugin package install/update/rollback/remove routes
- Storage: Host-local declarative JSON packages; validated resource checksums; previous-version/recoverable archives; reviewed permissions
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/runtime-work.md; tests/test_r2_plugin_packages.py; tests/test_plugin_contract_v1.py; tests/test_plugin_discovery_security.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Third-party execution DENY_ALL; PR #26 prototype separately assessed
- Priority/dependencies: P2; D00, D01, D04; packages D15
- Remaining/next check: Trusted broker/OS vault mediation/native AppContainer denial and cleanup not implemented/verified as full execution.

#### P02 · Plugin manifest

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:214; full original definition unavailable.
- Before: Manifest validation already existed.
- After: Bundle integrity, strict manifest/resource allowlists and size/path/symlink checks added.
- Source/UI: `app/plugin_contracts.py`, `app/plugin_package_manager.py`, `app/plugin_management_api.py`, `app/plugin_runtime_contracts.py`, `frontend/src/novel/PluginManagerPanel.tsx`, `frontend/src/novel/PluginInspector.tsx`
- API: GET /plugins; GET /plugins/runtime-status; Plugin package install/update/rollback/remove routes
- Storage: Host-local declarative JSON packages; validated resource checksums; previous-version/recoverable archives; reviewed permissions
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/runtime-work.md; tests/test_r2_plugin_packages.py; tests/test_plugin_contract_v1.py; tests/test_plugin_discovery_security.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P2; D00, D01, D04; packages D15
- Remaining/next check: Manifest validity does not authorize code execution or package trust.

#### P03 · Plugin API surface

PARTIAL / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:215; full original definition unavailable.
- Before: Catalog/permission endpoints existed.
- After: Declarative resource lifecycle is exposed with local authority checks.
- Source/UI: `app/plugin_contracts.py`, `app/plugin_package_manager.py`, `app/plugin_management_api.py`, `app/plugin_runtime_contracts.py`, `frontend/src/novel/PluginManagerPanel.tsx`, `frontend/src/novel/PluginInspector.tsx`
- API: GET /plugins; GET /plugins/runtime-status; Plugin package install/update/rollback/remove routes
- Storage: Host-local declarative JSON packages; validated resource checksums; previous-version/recoverable archives; reviewed permissions
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/runtime-work.md; tests/test_r2_plugin_packages.py; tests/test_plugin_contract_v1.py; tests/test_plugin_discovery_security.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P2; D00, D01, D04; packages D15
- Remaining/next check: No broad executable extension SDK/broker; packaged/collaboration package writes blocked without Host-admin authority.

#### P04 · Plugin permissions

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:216; full original definition unavailable.
- Before: Permission/authorization service existed.
- After: Package changes reset grants; rollback cannot restore implicit trust; current actor checks retained.
- Source/UI: `app/plugin_contracts.py`, `app/plugin_package_manager.py`, `app/plugin_management_api.py`, `app/plugin_runtime_contracts.py`, `frontend/src/novel/PluginManagerPanel.tsx`, `frontend/src/novel/PluginInspector.tsx`
- API: GET /plugins; GET /plugins/runtime-status; Plugin package install/update/rollback/remove routes
- Storage: Host-local declarative JSON packages; validated resource checksums; previous-version/recoverable archives; reviewed permissions
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/runtime-work.md; tests/test_r2_plugin_packages.py; tests/test_plugin_contract_v1.py; tests/test_plugin_discovery_security.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P2; D00, D01, D04; packages D15
- Remaining/next check: Executable permission enforcement cannot be claimed while runtime disabled.

#### P05 · Plugin lifecycle management

PARTIAL / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:217; full original definition unavailable.
- Before: Enable/disable/list existed without full lifecycle UI.
- After: Host-local declarative install/update/rollback/recoverable remove with integrity checks and UI.
- Source/UI: `app/plugin_contracts.py`, `app/plugin_package_manager.py`, `app/plugin_management_api.py`, `app/plugin_runtime_contracts.py`, `frontend/src/novel/PluginManagerPanel.tsx`, `frontend/src/novel/PluginInspector.tsx`
- API: GET /plugins; GET /plugins/runtime-status; Plugin package install/update/rollback/remove routes
- Storage: Host-local declarative JSON packages; validated resource checksums; previous-version/recoverable archives; reviewed permissions
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/runtime-work.md; tests/test_r2_plugin_packages.py; tests/test_plugin_contract_v1.py; tests/test_plugin_discovery_security.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P2; D00, D01, D04; packages D15
- Remaining/next check: No marketplace, signed executable distribution or packaged Host-admin write authority.

### Q. Workflow

#### Q01 · Workflow engine

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:218; full original definition unavailable.
- Before: Workflow/DAG definitions and runs existed.
- After: Bounded durable snapshots, cycle rejection, actual Agent completion gating, cancellation/rejection and scope guards. Workflow/queue observers now remount and epoch-fence full actor/session/workspace/project/storyline/branch changes; old-scope callbacks cannot repopulate the next scope.
- Source/UI: `app/workflow.py`, `app/workflow_api.py`, `app/workflow_recipes.py`, `app/services/v1_capability_service.py`, `frontend/src/novel/WorkflowPanel.tsx`, `frontend/src/novel/AgentQueuePanel.tsx`, `frontend/src/novel/WorkflowPanel.tsx`, `frontend/src/novel/WorkflowInspector.tsx`, `frontend/src/novel/AgentQueuePanel.tsx`
- API: GET/POST /workflows; POST /workflows/{workflow_id}/runs; Run approval/reject/pause/resume/cancel/retry and Agent dispatch routes
- Storage: Scoped durable definitions/run snapshots/outputs/reviews; bounded DAG and persisted Agent jobs
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/acceptance-scope-work.md; docs/delivery/dot-astra-rc-r2/evidence/acceptance-integrity.xml; docs/delivery/dot-astra-rc-r2/evidence/workflow-scope.xml; tests/test_workflow.py; tests/test_r2_workflow_execution.py; frontend/src/novel/WorkflowScopeGuards.test.tsx; frontend/src/novel/WorkflowPanel.independent-audit.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Local rule recipes; explicit selected-model Agent executor; no real provider test
- Priority/dependencies: P2; D04, D05, D06, D08; packages D13
- Remaining/next check: Single Host process; distributed leases/multi-process transactional scheduling not claimed.

#### Q02 · Novel-to-film recipe

PARTIAL / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:219; full original definition unavailable.
- Before: Release-gate/workflow primitives existed.
- After: Three bounded local transformations save reviewed candidates, supplied draft and shot/task proposals.
- Source/UI: `app/workflow.py`, `app/workflow_api.py`, `app/workflow_recipes.py`, `app/services/v1_capability_service.py`, `frontend/src/novel/WorkflowPanel.tsx`, `frontend/src/novel/WorkflowInspector.tsx`, `frontend/src/novel/AgentQueuePanel.tsx`
- API: GET/POST /workflows; POST /workflows/{workflow_id}/runs; Run approval/reject/pause/resume/cancel/retry and Agent dispatch routes
- Storage: Scoped durable definitions/run snapshots/outputs/reviews; bounded DAG and persisted Agent jobs
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/runtime-work.md; tests/test_workflow.py; tests/test_r2_workflow_execution.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Local rule recipes; explicit selected-model Agent executor; no real provider test
- Priority/dependencies: P2; D04, D05, D06, D08; packages D13
- Remaining/next check: No end-to-end novel-to-film production/apply pipeline; proposals do not start media generation.

#### Q03 · Custom workflows

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:220; full original definition unavailable.
- Before: Definition/create/run APIs and UI existed.
- After: Persisted input/results, human approval/reject, pause/resume/cancel/retry available. Workflow/queue observers now remount and epoch-fence full actor/session/workspace/project/storyline/branch changes; old-scope callbacks cannot repopulate the next scope.
- Source/UI: `app/workflow.py`, `app/workflow_api.py`, `app/workflow_recipes.py`, `app/services/v1_capability_service.py`, `frontend/src/novel/WorkflowPanel.tsx`, `frontend/src/novel/AgentQueuePanel.tsx`, `frontend/src/novel/WorkflowPanel.tsx`, `frontend/src/novel/WorkflowInspector.tsx`, `frontend/src/novel/AgentQueuePanel.tsx`
- API: GET/POST /workflows; POST /workflows/{workflow_id}/runs; Run approval/reject/pause/resume/cancel/retry and Agent dispatch routes
- Storage: Scoped durable definitions/run snapshots/outputs/reviews; bounded DAG and persisted Agent jobs
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/acceptance-scope-work.md; docs/delivery/dot-astra-rc-r2/evidence/acceptance-integrity.xml; docs/delivery/dot-astra-rc-r2/evidence/workflow-scope.xml; tests/test_workflow.py; tests/test_r2_workflow_execution.py; frontend/src/novel/WorkflowScopeGuards.test.tsx; frontend/src/novel/WorkflowPanel.independent-audit.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Local rule recipes; explicit selected-model Agent executor; no real provider test
- Priority/dependencies: P2; D04, D05, D06, D08; packages D13
- Remaining/next check: Core local DAG contracts verified; full desktop long-running recovery pending.

#### Q04 · Agent workflow nodes

PARTIAL / CONNECTED / CONTRACT_VERIFIED / NOT_CONFIGURED
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:221; full original definition unavailable.
- Before: Agent nodes could be marked successful before actual work.
- After: Selected-model dispatch persists real Agent jobs and synchronizes actual completion with approval. Workflow/queue observers now remount and epoch-fence full actor/session/workspace/project/storyline/branch changes; old-scope callbacks cannot repopulate the next scope.
- Source/UI: `app/workflow.py`, `app/workflow_api.py`, `app/workflow_recipes.py`, `app/services/v1_capability_service.py`, `frontend/src/novel/WorkflowPanel.tsx`, `frontend/src/novel/AgentQueuePanel.tsx`, `frontend/src/novel/WorkflowPanel.tsx`, `frontend/src/novel/WorkflowInspector.tsx`, `frontend/src/novel/AgentQueuePanel.tsx`
- API: GET/POST /workflows; POST /workflows/{workflow_id}/runs; Run approval/reject/pause/resume/cancel/retry and Agent dispatch routes
- Storage: Scoped durable definitions/run snapshots/outputs/reviews; bounded DAG and persisted Agent jobs
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/acceptance-scope-work.md; docs/delivery/dot-astra-rc-r2/evidence/acceptance-integrity.xml; docs/delivery/dot-astra-rc-r2/evidence/workflow-scope.xml; tests/test_workflow.py; tests/test_r2_workflow_execution.py; frontend/src/novel/WorkflowScopeGuards.test.tsx; frontend/src/novel/WorkflowPanel.independent-audit.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Local rule recipes; explicit selected-model Agent executor; no real provider test
- Priority/dependencies: P2; D04, D05, D06, D08; packages D13
- Remaining/next check: Model calls MOCK_ONLY; domain-specific multi-agent recipes and atomic crash-gap recovery incomplete.

### R. Credentials and provider selection

#### R01 · Session credentials

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:222; full original definition unavailable.
- Before: Trusted sessions/vault already existed.
- After: Existing Host boundary retained; no persistent browser secret storage added.
- Source/UI: `app/credential_vault.py`, `app/trusted_sessions.py`, `app/providers.py`, `app/native_text_providers.py`, `frontend/src/novel/DeepSeekCredentialControl.tsx`, `frontend/src/ui/ModelCenter.tsx`
- API: Credential status/test/clear through trusted Host; GET /providers; GET /models
- Storage: One credential entry per provider in Windows Credential Manager/keyring; opaque trusted sessions
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/runtime-work.md; tests/test_credential_vault.py; tests/test_credential_provider_lifecycle.py; tests/test_r2_native_text_providers.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Windows Credential Manager/keyring; memory backend only for isolated tests
- Priority/dependencies: P0; D01; packages D04
- Remaining/next check: Real Host handoff/native session lifecycle still NOT_RUN.

#### R02 · Persistent provider secrets

IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:223; full original definition unavailable.
- Before: Historical audit said TODO, but inspected baseline already has WindowsBackend/keyring persistence.
- After: Existing durable OS vault reused; production avoids environment-only configured claims.
- Source/UI: `app/credential_vault.py`, `app/trusted_sessions.py`, `app/providers.py`, `app/native_text_providers.py`, `frontend/src/novel/DeepSeekCredentialControl.tsx`, `frontend/src/ui/ModelCenter.tsx`
- API: Credential status/test/clear through trusted Host; GET /providers; GET /models
- Storage: One credential entry per provider in Windows Credential Manager/keyring; opaque trusted sessions
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/runtime-work.md; tests/test_credential_vault.py; tests/test_credential_provider_lifecycle.py; tests/test_r2_native_text_providers.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Windows Credential Manager/keyring; memory backend only for isolated tests
- Priority/dependencies: P0; D01; packages D04
- Remaining/next check: No current OS-store integration run; memory test backend is not durable proof.

#### R03 · Windows Credential Manager

IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:224; full original definition unavailable.
- Before: Actual CredWriteW/CredReadW/CredDeleteW implementation already present.
- After: Reuse actual OS integration instead of replacing with a new secret store.
- Source/UI: `app/credential_vault.py`, `app/trusted_sessions.py`, `app/providers.py`, `app/native_text_providers.py`, `frontend/src/novel/DeepSeekCredentialControl.tsx`, `frontend/src/ui/ModelCenter.tsx`
- API: Credential status/test/clear through trusted Host; GET /providers; GET /models
- Storage: One credential entry per provider in Windows Credential Manager/keyring; opaque trusted sessions
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/runtime-work.md; tests/test_credential_vault.py; tests/test_credential_provider_lifecycle.py; tests/test_r2_native_text_providers.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Windows Credential Manager/keyring; memory backend only for isolated tests
- Priority/dependencies: P0; D01; packages D04
- Remaining/next check: Native Windows credential persistence/revocation and desktop UI end-to-end NOT_RUN.

#### R04 · Multiple key/profile management

MISSING / DISCONNECTED / NOT_RUN / UNAVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:225; full original definition unavailable.
- Before: One vault slot per provider; no multi-profile model found.
- After: Still one provider-key identity; no named profile CRUD/selection implemented.
- Source/UI: `app/credential_vault.py`, `app/trusted_sessions.py`, `app/providers.py`, `app/native_text_providers.py`, `No dedicated implemented workflow`
- API: No dedicated callable product workflow
- Storage: One credential entry per provider in Windows Credential Manager/keyring; opaque trusted sessions
- Evidence/test inventory:
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Windows Credential Manager/keyring; memory backend only for isolated tests
- Priority/dependencies: P0; D01; packages D04
- Remaining/next check: Need bounded profile identity/scope/revocation/masked UI and authoritative runtime selection.

#### R05 · Provider/model switching

PARTIAL / CONNECTED / CONTRACT_VERIFIED / NOT_CONFIGURED
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:226; full original definition unavailable.
- Before: Provider catalog and credential routes existed.
- After: Explicit compatible/Claude/Gemini selection feeds current adapters; no guessed model IDs.
- Source/UI: `app/credential_vault.py`, `app/trusted_sessions.py`, `app/providers.py`, `app/native_text_providers.py`, `app/model_center/discovery_types.py`, `app/model_center/discovery_probes.py`, `app/model_center/discovery.py`, `app/model_center/discovery_api.py`, `app/model_center/discovery_bridge.py`, `app/model_center/domain.py`, `app/model_center/service.py`, `app/dependencies.py`, `app/main.py`, `frontend/src/novel/DeepSeekCredentialControl.tsx`, `frontend/src/ui/ModelCenter.tsx`, `frontend/src/ui/LocalAiDiscovery.tsx`, `frontend/src/localAiDiscoveryApi.ts`
- API: Credential status/test/clear through trusted Host; GET /providers; GET /models
- Storage: One credential entry per provider in Windows Credential Manager/keyring; opaque trusted sessions
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/runtime-work.md; LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; tests/test_credential_vault.py; tests/test_credential_provider_lifecycle.py; tests/test_r2_native_text_providers.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; Windows Credential Manager/keyring; memory backend only for isolated tests
- Priority/dependencies: P0; D01; packages D04
- Remaining/next check: Discovery lifecycle is integrated but under active independent correction; optional local route availability is not yet accepted. Real switching, multi-key profiles and full v2 execution broker remain unverified/incomplete.
- Subpath Optional Local AI Discovery registration/route bridge: PARTIAL / CONNECTED / FAILED / EXPERIMENTAL. Standalone synthetic lifecycle passed; independent review of fixed 547167e8 reports five additional locality/identity/disable/Writer-route gaps. New dirty-tree fixes pending recheck.

### S. Collaboration and review

#### S01 · Workspaces/storylines/branches

IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:227; full original definition unavailable.
- Before: Collaboration scope already existed.
- After: New records/tasks reuse existing identity/scope with reauthorization and remount protection.
- Source/UI: `app/collaboration_api.py`, `app/services/membership_authorization_service.py`, `app/creation_workbench_api.py`, `app/services/creation_workbench_service.py`, `frontend/src/novel/WorkflowPanel.tsx`, `frontend/src/novel/AgentQueuePanel.tsx`, `frontend/src/WorkspaceManagement.tsx`, `frontend/src/novel/CreationWorkbenchPanel.tsx`
- API: Workspace/membership/storyline/branch routes; GET/POST /novels/{nid}/review-threads; POST .../review-threads/{id}/{reply|resolve|reopen}
- Storage: Existing workspace/user/branch identity repositories; chapter-version-anchored review_threads sidecar
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/acceptance-scope-work.md; docs/delivery/dot-astra-rc-r2/evidence/acceptance-integrity.xml; docs/delivery/dot-astra-rc-r2/evidence/workflow-scope.xml; tests/test_r2_creation_workbench.py; tests/test_collaboration_scope.py; frontend/src/novel/WorkflowScopeGuards.test.tsx; frontend/src/novel/WorkflowPanel.independent-audit.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D01, D03, D06; packages D03, D14
- Remaining/next check: Different domain sharing semantics documented; final multi-user/browser acceptance pending.

#### S02 · Membership and permissions

IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:228; full original definition unavailable.
- Before: Server-side identity/membership authorization existed.
- After: New workflow, plans, comments, media and export paths use trusted actor/current membership.
- Source/UI: `app/collaboration_api.py`, `app/services/membership_authorization_service.py`, `app/creation_workbench_api.py`, `app/services/creation_workbench_service.py`, `frontend/src/novel/WorkflowPanel.tsx`, `frontend/src/novel/AgentQueuePanel.tsx`, `frontend/src/WorkspaceManagement.tsx`, `frontend/src/novel/CreationWorkbenchPanel.tsx`
- API: Workspace/membership/storyline/branch routes; GET/POST /novels/{nid}/review-threads; POST .../review-threads/{id}/{reply|resolve|reopen}
- Storage: Existing workspace/user/branch identity repositories; chapter-version-anchored review_threads sidecar
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/acceptance-scope-work.md; docs/delivery/dot-astra-rc-r2/evidence/acceptance-integrity.xml; docs/delivery/dot-astra-rc-r2/evidence/workflow-scope.xml; tests/test_r2_creation_workbench.py; tests/test_collaboration_scope.py; frontend/src/novel/WorkflowScopeGuards.test.tsx; frontend/src/novel/WorkflowPanel.independent-audit.test.tsx
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D01, D03, D06; packages D03, D14
- Remaining/next check: Final permission-revocation end-to-end tests/Windows interaction pending.

#### S03 · Comment/review threads

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:229; full original definition unavailable.
- Before: No comments/review threads found in audit.
- After: Persistent chapter-version/quote/hash anchor; trusted actor, reply/resolve/reopen/history and stale-anchor UI.
- Source/UI: `app/collaboration_api.py`, `app/services/membership_authorization_service.py`, `app/creation_workbench_api.py`, `app/services/creation_workbench_service.py`, `frontend/src/WorkspaceManagement.tsx`, `frontend/src/novel/CreationWorkbenchPanel.tsx`
- API: Workspace/membership/storyline/branch routes; GET/POST /novels/{nid}/review-threads; POST .../review-threads/{id}/{reply|resolve|reopen}
- Storage: Existing workspace/user/branch identity repositories; chapter-version-anchored review_threads sidecar
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.txt; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; tests/test_r2_creation_workbench.py; tests/test_collaboration_scope.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D01, D03, D06; packages D03, D14
- Remaining/next check: Anchors flag changed/missing source rather than automatically remapping; final browser gate pending.

#### S04 · Unified approvals

PARTIAL / CONNECTED / NOT_RUN / EXPERIMENTAL
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:230; full original definition unavailable.
- Before: Import/Agent/release approvals were separate.
- After: Comments/review panel adds durable audit; creation approval and import journals preserve explicit review.
- Source/UI: `app/collaboration_api.py`, `app/services/membership_authorization_service.py`, `app/creation_workbench_api.py`, `app/services/creation_workbench_service.py`, `frontend/src/WorkspaceManagement.tsx`, `frontend/src/novel/CreationWorkbenchPanel.tsx`
- API: Workspace/membership/storyline/branch routes; GET/POST /novels/{nid}/review-threads; POST .../review-threads/{id}/{reply|resolve|reopen}
- Storage: Existing workspace/user/branch identity repositories; chapter-version-anchored review_threads sidecar
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; tests/test_r2_creation_workbench.py; tests/test_collaboration_scope.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P1; D01, D03, D06; packages D03, D14
- Remaining/next check: No unified inbox aggregating import/Agent/Canon/media approvals; separate domain queues remain.

### T. Exports

#### T01 · TXT export

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:231; full original definition unavailable.
- Before: TXT exporter/queue existed; history UI could not rediscover jobs.
- After: Scope-bound server history/filter/reopen plus immutable snapshot/download/retry.
- Source/UI: `app/export_formats.py`, `app/pdf_export.py`, `app/industry_export_formats.py`, `app/services/export_job_service.py`, `app/services/export_resource_snapshot.py`, `frontend/src/novel/ExportPanel.tsx`
- API: GET/POST /exports; GET /exports/{id}; GET /exports/{id}/download; POST /exports/{id}/retry|cancel
- Storage: export_jobs.json; immutable content/source/resource snapshots; owned result artifacts; context-bound reauthorization
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/pdf-fonts.txt; docs/delivery/dot-astra-rc-r2/evidence/font-manifest.json; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; tests/test_export_jobs.py; tests/test_export_history_recovery.py; tests/test_export_resource_packages.py; tests/test_docx_export.py; tests/test_pdf_export.py; tests/test_r2_pdf_font.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P0/P1; D01, D02, D08; packages D02, D09
- Remaining/next check: Final business browser recovery and target Windows download acceptance pending.

#### T02 · Markdown export

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:232; full original definition unavailable.
- Before: Markdown exporter existed.
- After: Same durable scoped history/snapshot/reauthorization as TXT.
- Source/UI: `app/export_formats.py`, `app/pdf_export.py`, `app/industry_export_formats.py`, `app/services/export_job_service.py`, `app/services/export_resource_snapshot.py`, `frontend/src/novel/ExportPanel.tsx`
- API: GET/POST /exports; GET /exports/{id}; GET /exports/{id}/download; POST /exports/{id}/retry|cancel
- Storage: export_jobs.json; immutable content/source/resource snapshots; owned result artifacts; context-bound reauthorization
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/pdf-fonts.txt; docs/delivery/dot-astra-rc-r2/evidence/font-manifest.json; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; tests/test_export_jobs.py; tests/test_export_history_recovery.py; tests/test_export_resource_packages.py; tests/test_docx_export.py; tests/test_pdf_export.py; tests/test_r2_pdf_font.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P0/P1; D01, D02, D08; packages D02, D09
- Remaining/next check: Final exact-SHA format and browser regression pending.

#### T03 · DOCX export

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:233; full original definition unavailable.
- Before: DOCX output and structure tests existed.
- After: Retained DOCX and added frozen screenplay-resource packaging.
- Source/UI: `app/export_formats.py`, `app/pdf_export.py`, `app/industry_export_formats.py`, `app/services/export_job_service.py`, `app/services/export_resource_snapshot.py`, `frontend/src/novel/ExportPanel.tsx`
- API: GET/POST /exports; GET /exports/{id}; GET /exports/{id}/download; POST /exports/{id}/retry|cancel
- Storage: export_jobs.json; immutable content/source/resource snapshots; owned result artifacts; context-bound reauthorization
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/pdf-fonts.txt; docs/delivery/dot-astra-rc-r2/evidence/font-manifest.json; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; tests/test_export_jobs.py; tests/test_export_history_recovery.py; tests/test_export_resource_packages.py; tests/test_docx_export.py; tests/test_pdf_export.py; tests/test_r2_pdf_font.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P0/P1; D01, D02, D08; packages D02, D09
- Remaining/next check: Word/LibreOffice rendered pagination and target font behavior remain unrun.

#### T04 · PDF export

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:234; full original definition unavailable.
- Before: PDF export existed; strict CJK embedding gate incomplete.
- After: Pinned OFL Noto CJK preparation, licensed manifest and actual embedded PDF validation/render evidence.
- Source/UI: `app/export_formats.py`, `app/pdf_export.py`, `app/industry_export_formats.py`, `app/services/export_job_service.py`, `app/services/export_resource_snapshot.py`, `frontend/src/novel/ExportPanel.tsx`
- API: GET/POST /exports; GET /exports/{id}; GET /exports/{id}/download; POST /exports/{id}/retry|cancel
- Storage: export_jobs.json; immutable content/source/resource snapshots; owned result artifacts; context-bound reauthorization
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/pdf-fonts.txt; docs/delivery/dot-astra-rc-r2/evidence/font-manifest.json; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; tests/test_export_jobs.py; tests/test_export_history_recovery.py; tests/test_export_resource_packages.py; tests/test_docx_export.py; tests/test_pdf_export.py; tests/test_r2_pdf_font.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P0/P1; D01, D02, D08; packages D02, D09
- Remaining/next check: Font download/build gate required; Windows font/runtime acceptance and broad typography still NOT_RUN.

#### T05 · EPUB export

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:235; full original definition unavailable.
- Before: EPUB exporter existed.
- After: Retained immutable export snapshots and discoverable job history.
- Source/UI: `app/export_formats.py`, `app/pdf_export.py`, `app/industry_export_formats.py`, `app/services/export_job_service.py`, `app/services/export_resource_snapshot.py`, `frontend/src/novel/ExportPanel.tsx`
- API: GET/POST /exports; GET /exports/{id}; GET /exports/{id}/download; POST /exports/{id}/retry|cancel
- Storage: export_jobs.json; immutable content/source/resource snapshots; owned result artifacts; context-bound reauthorization
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/pdf-fonts.txt; docs/delivery/dot-astra-rc-r2/evidence/font-manifest.json; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; tests/test_export_jobs.py; tests/test_export_history_recovery.py; tests/test_export_resource_packages.py; tests/test_docx_export.py; tests/test_pdf_export.py; tests/test_r2_pdf_font.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P0/P1; D01, D02, D08; packages D02, D09
- Remaining/next check: External EPUB validator/reader compatibility and accessibility audit not newly claimed.

#### T06 · Screenplay export

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:236; full original definition unavailable.
- Before: Fountain/Markdown/DOCX existed with mixed-name/action/multiline defects.
- After: Structural Fountain fixes; screenplay ZIP with immutable resource bytes enters queue/API/UI.
- Source/UI: `app/export_formats.py`, `app/pdf_export.py`, `app/industry_export_formats.py`, `app/services/export_job_service.py`, `app/services/export_resource_snapshot.py`, `frontend/src/novel/ExportPanel.tsx`
- API: GET/POST /exports; GET /exports/{id}; GET /exports/{id}/download; POST /exports/{id}/retry|cancel
- Storage: export_jobs.json; immutable content/source/resource snapshots; owned result artifacts; context-bound reauthorization
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/pdf-fonts.txt; docs/delivery/dot-astra-rc-r2/evidence/font-manifest.json; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; tests/test_export_jobs.py; tests/test_export_history_recovery.py; tests/test_export_resource_packages.py; tests/test_docx_export.py; tests/test_pdf_export.py; tests/test_r2_pdf_font.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P0/P1; D01, D02, D08; packages D02, D09
- Remaining/next check: Complete fountain-js 1.2.4 parser tests passed at the focused checkpoint; target Final Draft/industry layout and final exact-SHA rerun remain separate.

#### T07 · Shot/storyboard exports

IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE
- Requirement: AI-Novel-Studio-V1.0-Feature-Audit.md:237; full original definition unavailable.
- Before: CSV/storyboard/HTML output existed.
- After: Shot/storyboard resource ZIPs, source versions, exact byte digests and history/recovery connected.
- Source/UI: `app/export_formats.py`, `app/pdf_export.py`, `app/industry_export_formats.py`, `app/services/export_job_service.py`, `app/services/export_resource_snapshot.py`, `frontend/src/novel/ExportPanel.tsx`
- API: GET/POST /exports; GET /exports/{id}; GET /exports/{id}/download; POST /exports/{id}/retry|cancel
- Storage: export_jobs.json; immutable content/source/resource snapshots; owned result artifacts; context-bound reauthorization
- Evidence/test inventory: docs/delivery/dot-astra-rc-r2/evidence/pdf-fonts.txt; docs/delivery/dot-astra-rc-r2/evidence/font-manifest.json; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; tests/test_export_jobs.py; tests/test_export_history_recovery.py; tests/test_export_resource_packages.py; tests/test_docx_export.py; tests/test_pdf_export.py; tests/test_r2_pdf_font.py
- Platform/provider: Isolated Linux/synthetic fixtures; current hosted Windows result PENDING_LEAD; interactive Windows, real GPU/model and user acceptance NOT_RUN; None; deterministic local application
- Priority/dependencies: P0/P1; D01, D02, D08; packages D02, D09
- Remaining/next check: Archive reimport not added; target NLE/industry interoperability NOT_RUN.

## 28-section Local AI supplement coverage

Shared actual entry: Settings → Model Center → Local AI, `frontend/src/ui/LocalAiDiscovery.tsx`, with `localAiDiscoveryApi.ts`. Actual composition is in `app/dependencies.py`, both API aliases in `app/main.py`, and media registry publication in `app/api.py`. Earlier worker handoff text saying integration was pending is historical.

Shared persistence: host-local `model-center/local-discovery.json`, existing Model Center stable identities and registries. No weight-file deletion. All new reads and writes require trusted Host authority.

| Section | Implementation / integration / verification | Bounded implementation | PARTIAL / acceptance |
|---|---|---|---|
| LAD-01 Goal and Model Center integration | PARTIAL / CONNECTED / FAILED | Settings→Model Center→Local AI is a real mounted surface reusing existing registries. | Writer-route review gaps and real Windows usability remain unresolved; not release-complete. |
| LAD-02 Detect→Validate→Register→Enable→Launch | PARTIAL / CONNECTED / FAILED | Distinct backend operations; registration disabled, Enable explicitly confirmed, task-only managed launch. | Digest-rescan invalidation and Disable-versus-callback races require accepted fixes. |
| LAD-03 Windows hardware inventory | PARTIAL / CONNECTED / NOT_RUN | Host inventory reused for architecture, CPU/RAM and GPU vendor/name/VRAM display; missing facts remain unknown. | Real Windows hardware collection and matched compatibility NOT_RUN; Linux/mock metadata does not certify hardware. |
| LAD-04 Ollama text discovery | PARTIAL / CONNECTED / FAILED | Existing OllamaProvider.list_models used for tags/details; metadata show/version and explicit completion capability; registry bridge exists. | remote_host locality, Writer stream eligibility and digest-revocation findings remain under review. No real Ollama inference. |
| LAD-05 llama.cpp/GGUF | PARTIAL / CONNECTED / FAILED | Configured bounded GGUF roots/header/metadata, executable hints, context/GPU-layer/thread/batch settings, managed task-only lifecycle and external association. | External advertised-alias dispatch finding pending; no actual executable/GGUF generation/CUDA validation. Passive version data is not a runnable version check. |
| LAD-06 Flexible Qwen text families | PARTIAL / CONNECTED / FAILED | Version-flexible family recognition and user-installed Ollama/GGUF identity; fixed old profile is not the only catalog entry. | Names are declarations only; source locality, external alias and real compatibility remain separately gated. |
| LAD-07 ComfyUI runtime discovery | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED | Default/saved loopback probes read system_stats and object_info, retain partial outcomes and separate runtime/node/model evidence. | Actual ComfyUI node/workflow execution NOT_RUN; metadata alone is not generation proof. |
| LAD-08 ComfyUI model families | PARTIAL / CONNECTED / CONTRACT_VERIFIED | IMAGE Qwen-Image/FLUX/Z-Image, VIDEO H3/Wan/LTX, RESTORATION SeedVR2 and INTERPOLATION RIFE are classified with UNKNOWN fallback. | Family/loader declarations do not supply missing reviewed workflow adapters; arbitrary custom nodes remain unsupported. |
| LAD-09 Qwen-Image | PARTIAL / CONNECTED / CONTRACT_VERIFIED | Discovered candidates and disabled registration retain distinct model/file/node/workflow/inference evidence. | No verified Qwen-Image workflow adapter or real generation; file/loader presence cannot be READY. |
| LAD-10 MiniMax H3 identity correction | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED | minimax-h3-video is a distinct ComfyUI VIDEO identity; legacy minimax-h3 AUDIO identity remains disabled solely for old history. | Does not validate user's actual model/license/workflow; no UUID/history reinterpretation or executable-video completion. |
| LAD-11 Local video model/adapters | PARTIAL / CONNECTED / CONTRACT_VERIFIED | H3/Wan/LTX family discovery separates runtime identity, model registration and workflow_adapter_id. | T2V/I2V/start-end/continuation adapters are extension contracts, not implemented runnable workflows for every family. |
| LAD-12 SeedVR2/RIFE utility modalities | PARTIAL / CONNECTED / CONTRACT_VERIFIED | RESTORATION/INTERPOLATION labels stay separate and LOCAL_VIDEO_PIPELINE_V1 architecture is retained. | Actual restoration/interpolation adapters, model output and complete video pipeline NOT_RUN/unavailable where adapter missing. |
| LAD-13 Automatic1111 | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED | Default/saved loopback discovery enumerates sd-models; missing service is NOT_FOUND; explicit IMAGE route uses existing adapter without credentials. | Real checkpoint inference not run; existing supported request contract is not universal A1111 version certification. |
| LAD-14 Custom local runtime editor | PARTIAL / CONNECTED / FAILED | Name/type/endpoint/model/modality/health/credential requirement/lifecycle settings persist; loopback-only validation; managed lifecycle limited to llama. | Unknown generic HTTP and OpenAI-compatible models lists do not authorize inference; credential binding is unsupported; external llama alias review pending. |
| LAD-15 Declared versus verified capability | PARTIAL / CONNECTED / FAILED | Separate declared_capabilities, metadata/workflow verified_capabilities and actual inference verified=false; standard modalities preserved. | Ollama proxy locality must be verified separately; capability metadata alone cannot authorize a local-private route. |
| LAD-16 Hardware compatibility display | PARTIAL / CONNECTED / NOT_RUN | Unknown/possibly compatible/unsupported statuses and offload/context warnings do not delete small-VRAM models. | No actual matched-GPU benchmark; COMPATIBLE cannot be asserted from filename or static recommendation. |
| LAD-17 Validation states | PARTIAL / CONNECTED / FAILED | DISCOVERED/NOT_FOUND/NOT_INSTALLED/VALIDATION_REQUIRED/LICENSE_REQUIRED/DISABLED/DEGRADED and conservative compatibility shown. | Identity-change and Disable callback findings affect current authority; revalidation fixes require independent pass before enabling trustworthy final state. |
| LAD-18 License and usage policy | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED | License acknowledgment is separate from validation and explicit Enable; unknown/restricted model use is not assumed commercially permitted. | Application acknowledgment is not a granted license; actual user license and purpose need user review. |
| LAD-19 Model lifecycle | PARTIAL / CONNECTED / FAILED | No startup inference; managed llama launches only for task and releases afterward; other runtimes remain EXTERNAL_RUNTIME; restart disables registrations. | Disable/rescan/alias/Writer gate regressions pending; real process/GPU cleanup NOT_RUN; external runtime is not terminated. |
| LAD-20 Functional Local AI UI | PARTIAL / CONNECTED / FAILED | Scan/rescan/cancel, categories/evidence, Validate/Register/Configure/explicit Enable/Disable/Remove-registration are wired to actual API. | Current callback/control-state repairs need recheck; latest full UI pass predates later edits; hosted viewport/keyboard/browser evidence pending. |
| LAD-21 Skippable first-use experience | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED | Panel supports Skip, no scan on startup; explicit Scan and explicit registration/Enable are separate. | Actual first clean Windows install NOT_RUN; no startup scan/launch should be inferred from opening Model Center. |
| LAD-22 Privacy and safety | PARTIAL / CONNECTED / FAILED | Every discovery read/write requires trusted Host session; bounded configured paths, loopback transports, no proxy/redirect/cloud classification or manuscript scan. | Ollama remote proxy and stale lifecycle authority findings are safety blockers pending accepted repairs. Local endpoint alone is not proof of local processing. |
| LAD-23 Performance and partial results | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED | Background bounded scan, per-probe timeout/size/read budget, partial outcomes and cancellation between probes/directory entries. | Cancellation cannot preempt an in-progress blocking call; real desktop startup/large directory latency not benchmarked. Existing synthetic novel benchmark is not discovery performance. |
| LAD-24 Test requirements | PARTIAL / CONNECTED / CONTRACT_VERIFIED | Synthetic probe/header/capability/lifecycle/identity tests, mounted API wiring, UI tests and browser cases exist; dedicated earlier combined 263 passed/1 skipped. | Independent discovery review disproves a blanket pass; final regression/real Windows/GPU/inference NOT_RUN or PENDING_LEAD. |
| LAD-25 Documentation and Opus handoff | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED | Root LOCAL_AI_DISCOVERY.md, LOCAL_AI_WINDOWS_ACCEPTANCE.md and OPUS_UI_HANDOFF.md sections exist; source/status/limits documented. | Earlier worker pending-integration paragraph is historical; final hashes/CI and corrected discovery behavior must be reconciled by lead. |
| LAD-26 No fake completion | PARTIAL / CONNECTED / FAILED | Real state machine and runtime probes replace static-only dropdowns; no actual inference verified flag from filename/metadata. | Known locality, enabled-Writer and revocation gaps must close; synthetic lifecycle pass cannot conceal them or certify all model families. |
| LAD-27 Priority within R2 | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED | Original privacy/data/Accept/export/recovery work retained; supplement reuses same project rather than replacing P0 fixes. | Discovery safety findings now join existing final gates; do not bypass original full File/PG/browser/Windows checks for supplementary counts. |
| LAD-28 GitHub direct delivery | PARTIAL / CONNECTED / NOT_RUN | Same working branch and Draft PR retained; local fixed snapshot includes integrated supplement and documentation. | Fixed integration tree is verified delivered at 90f4369b (same tree as local 547167e8). Newer correction commit/upload, final CI and final tested identity are PENDING_LEAD. |

Detailed per-section paths, routes, tests, dependencies, evidence and affected original IDs are retained in JSON. FAILED denotes a known independent fixed-snapshot issue whose later author fix has not yet been accepted.

## Final owner update requirements

1. Freeze and commit the discovery fixes; repeat independent locality/control/identity/Writer probes and original invariants.
2. Publish the failed full-suite receipt and its focused correction, then run full File/real PostgreSQL/frontend/build/tokens/browser/hosted Windows checks at the exact final checkout.
3. Publish the newer correction commit after the already delivered 90f4369b tree; read back final remote branch/PR head and record branch-head versus PR merge checkout separately.
4. Keep interactive Windows, real model/GPU, complete installer and user acceptance NOT_RUN until actual evidence exists.
5. Do not merge main, publish a formal Release or deploy production.

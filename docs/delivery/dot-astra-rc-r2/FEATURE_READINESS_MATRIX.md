# R2 feature readiness matrix

Status: ENGINEERING CANDIDATE, not release accepted. Final SHA and final gate receipts are pending integration-owner updates.

- Repository: https://github.com/1785235376-blip/AI-Novel-Studio
- Branch: `work/dot-astra-v1-rc-r2`; Draft PR: https://github.com/1785235376-blip/AI-Novel-Studio/pull/37
- Starting SHA: `f8c141c39a543cc9dbea57647ac91185bc9aecd6`; inventory HEAD: `e73ab085407bcc63c4a7e380f685dba92f8b4cf5` plus integrating worktree changes.
- Coverage: all 143 original A–T codes; all 19 R2 work packages. No completion percentage.
- Machine-readable companion: [FEATURE_READINESS_MATRIX.json](FEATURE_READINESS_MATRIX.json). It contains per-feature source/API/storage/UI/evidence/version/revision/dependency fields.

## Interpretation and evidence limits

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

## Verification layers

| Layer | Current evidence |
|---|---|
| source_inventory | COMPLETED on listed current worktree |
| independent_readiness_focus | Initial 18 passed plus later expanded 47 passed (overlapping, not additive); File/synthetic/model-double contracts; evidence/readiness-focused.xml and evidence/readiness-planning-focused.xml |
| worker_focused_contracts | See cited per-feature worker reports; overlapping tests not summed |
| final_file_suite | PENDING_OWNER_RESULT |
| final_real_postgresql | PENDING_OWNER_RESULT |
| final_frontend_unit_typecheck_build | PENDING_OWNER_RESULT |
| browser_business_e2e | Local BLOCKED before assertions; hosted result PENDING_OWNER_RESULT |
| hosted_windows_build_native_contract | PENDING_OWNER_RESULT |
| interactive_windows_webview2_install_upgrade_uninstall | NOT_RUN |
| real_provider_gpu_models | NOT_RUN; no authorized credentials/budget supplied to this inventory |
| user_acceptance | NOT_RUN |

## D00–D18 work packages

Feature-code D01 and work-package D01 are different namespaces. A package stays partial when any material requested capability is missing, even if several lower-level services pass.

| Package | Priority / dependencies | Implementation / integration / verification | Delivered bounded behavior | Remaining acceptance/gap | Evidence |
|---|---|---|---|---|---|
| D00 Baseline and traceability | P0;  | PARTIAL / CONNECTED / CONTRACT_VERIFIED | Verified inherited PR36/main ancestry, branch and actual model; inventory all 143 original codes. | Final SHA, remote CI receipts and final deliverable inventory pending owner. | docs/delivery/dot-astra-rc-r2/BASELINE_RECEIPT.md |
| D01 Privacy and authorization | P0; D00 | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED | Timeline/foreshadowing/Canon persistence, conservative merge, migration 018, File parity and actual transport canaries strengthened. | Final real PostgreSQL save/read/fresh-process/migration and full permission-revocation run pending. | docs/delivery/dot-astra-rc-r2/privacy-recovery-work.md; docs/delivery/dot-astra-rc-r2/runtime-work.md |
| D02 Export recovery and format fixes | P0; D01 | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED | Server-scoped history, reauthorization, same-snapshot rediscovery, frozen ZIP resources and Fountain structural fixes connected. | Complete fountain-js parser focused tests passed; real browser creation/reopen/download blocked locally and target screenplay app NOT_RUN. | docs/delivery/dot-astra-rc-r2/evidence/fountain-before.json; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt |
| D03 Core authoring and recovery | P0; D01 | IMPLEMENTED / CONNECTED / MOCK_ONLY | Existing author/edit/save/revision chain preserved; generation identity/idempotency/late privacy checks hardened. | Single complete UI create/import/edit/generate/Diff/Accept/restore/reopen journey and native crash/IME acceptance still pending. | docs/delivery/dot-astra-rc-r2/runtime-work.md |
| D04 Provider execution and vault | P0; D01 | PARTIAL / CONNECTED / MOCK_ONLY | Compatible plus explicit native Claude/Gemini adapters, guarded execution, real usage or UNKNOWN, cancel/no unsafe replay and OS vault reuse. | No actual provider calls, multi-key profiles, full authoritative v2 broker or native OS-vault acceptance. | docs/delivery/dot-astra-rc-r2/runtime-work.md |
| D05 Advanced authoring and planning | P1; D03, D04 | PARTIAL / CONNECTED / CONTRACT_VERIFIED | Multi-variant review plus reusable STYLE/PLOT, compare/history/approval/restore and actual generation inputs; bounded selected-model exact-evidence structured suggestions and explicit-marker rule/plot drafts added. | Full outline/volume/chapter/scene hierarchy and semantic planning quality remain gaps; structured model path is MOCK_ONLY, with actual app registration inspected and final two-alias/full-suite gates pending. | docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/runtime-work.md |
| D06 Import extraction and review | P1; D03, D04 | PARTIAL / CONNECTED / CONTRACT_VERIFIED | Evidence-located four-group extraction/review/journal plus separate explicit-marker rule/plot proposals and bounded selected-model planning drafts. | No reliable inference of unstated world/plot facts, cross-chapter identity resolution, long-book semantic quality or atomic multi-entity transaction; journals expose partial progress. | docs/delivery/dot-astra-rc-r2/import-apply-checkpoints.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml |
| D07 World characters continuity | P1; D05, D06 | PARTIAL / CONNECTED / CONTRACT_VERIFIED | Typed HISTORY/GEOGRAPHY/CIVILIZATION/ABILITY/PSYCHOLOGY records plus exact-evidence optional selected-model suggestions/local explicit rule extraction; existing rule/findings/graph retained. | New reviewed drafts do not constitute semantic engines or automatically join Canon/checker rules; real model quality unverified. | docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/privacy-recovery-work.md |
| D08 Screenplay storyboard transitions | P1; D03, D04 | PARTIAL / CONNECTED / CONTRACT_VERIFIED | Branch-aware screenplay operations, approved revision fork preserving assets, shot/card/prompt fields and source-linked exports. | Specialized model-assisted shot/composition/camera/transition quality and complete independent scene/shot revision UX remain limited. | docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml |
| D09 Resource packages and documents | P1; D02, D08 | PARTIAL / CONNECTED / CONTRACT_VERIFIED | Three frozen resource ZIP formats connected to queue/API/UI; bounded owned bytes; licensed pinned CJK font and PDF embedding/render evidence. | Target Word/Final Draft/EPUB/NLE interoperability, typography and archive reimport remain independent gaps. | docs/delivery/dot-astra-rc-r2/evidence/font-manifest.json; docs/delivery/dot-astra-rc-r2/evidence/pdf-fonts.txt |
| D10 Images references assets | P2; D04, D07 | PARTIAL / CONNECTED / MOCK_ONLY | Persistent image queue/review, real decoder checks, approved lexical reference index, digest-safe assets/lineage/trash/restore. | Real image/vision models, embeddings/semantic identity, cover/storyboard-specific generation and bulk governance/reimport remain gaps. Existing canvas zoom/pan/select/drag/align/group/layer/lock/undo is retained. | docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/assets-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml |
| D11 Video tasks and timeline | P2; D08, D10 | PARTIAL / CONNECTED / MOCK_ONLY | Frame/prompt consent, fenced submit/cancel/callback, SSRF-safe actual download/decode, ordered trimmed silent review-cut output. | No real video model, bundled Windows codec distribution, soundtrack/final master/NLE conformance or vendor-specific asymmetric callbacks. | docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml |
| D12 Voices and audiobook | P2; D04, D07 | PARTIAL / CONNECTED / MOCK_ONLY | Durable voice/dictionary/provenance, immutable consent-checked sentence queues, verified audio, order-preserving PCM concatenate/export. | Real TTS/voices, expressive emotion, auto multi-character attribution, mixed-format mastering and phoneme-aligned subtitles absent/unrun. | docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml |
| D13 Agent and workflow execution | P2; D04, D05, D06, D08 | PARTIAL / CONNECTED / MOCK_ONLY | Bounded persistent authorized DAG with genuine Agent-job dispatch/completion and review; three tested local rule artifact recipes. | Recipes are not autonomous domain-apply loops; real-model role quality and transactional multi-worker/crash-gap scheduling incomplete. | docs/delivery/dot-astra-rc-r2/runtime-work.md |
| D14 Comments and unified review | P1/P2; D03, D06 | PARTIAL / CONNECTED / CONTRACT_VERIFIED | Version/hash/quote-anchored persistent comments, trusted actor, stale markers, resolve/reopen/reply and history/UI. | Separate import/Canon/Agent/media queues are not one unified approval inbox; final browser permissions run pending. | docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml |
| D15 Plugin management and isolation | P2; D00, D01, D04 | PARTIAL / CONNECTED / CONTRACT_VERIFIED | Integrity-checked local declarative install/update/rollback/recoverable remove and grant reset; PR26 independently inspected. | Executable runtime DISCONNECTED/DENY_ALL; real Windows isolation/broker absent; packaged/collaboration lifecycle writes blocked without Host-admin authority. | docs/delivery/dot-astra-rc-r2/runtime-work.md |
| D16 Migration backup and restore | P0/P1; D01 | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED | Stricter File/PG migration and non-destructive exclusive backup/new-target restore; exact inventory/digests and whole runtime sidecars included. | Final real PostgreSQL fresh-instance recovery and Windows ACL/locking/PowerShell checks pending; sidecars are not all migrated to SQL. | docs/delivery/dot-astra-rc-r2/privacy-recovery-work.md; docs/delivery/dot-astra-rc-r2/privacy-recovery-focused.txt |
| D17 Usability and Opus handoff | P0/P1; D00 | PARTIAL / CONNECTED / CONTRACT_VERIFIED | Existing shell/tokens kept; genuine forms/history/errors/review/recovery added with focused component/build/token checks. | Local browser blocked before assertions; exact final CI browser business/geometry/screenshots and complete handoff pending owner; native IME/focus/user acceptance unrun. | docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/assets-work.md |
| D18 Build Windows delivery | P0/P1; D02, D03, D04, D09, D16, D17 | PARTIAL / CONNECTED / NOT_RUN | Pinned frontend toolchain, CI/native Host build/check work and licensed font build input advanced; Draft delivery only. | Hosted Windows job pending receipt; no claim of full base-runtime installer, interactive Windows install/upgrade/uninstall or user acceptance; final SHA/CI/hashes pending. | docs/delivery/dot-astra-rc-r2/BASELINE_RECEIPT.md |

## Full original-code inventory

For every row below, test revision is UNCOMMITTED_INTEGRATION_CHECKPOINT at inventory HEAD; exact final tested SHA is pending. Platform defaults to isolated Linux, product 0.7.0, Python 3.12.14, Node 24.19.0 and pnpm 10.6.5. Current real providers, interactive Windows and user acceptance are NOT_RUN. The API/storage/UI/evidence header for each area applies to its rows unless the row states otherwise; complete explicit per-row values are in JSON.

### A. Desktop runtime

- Requirement source: `AI-Novel-Studio-V1.0-Feature-Audit.md`, original code rows. Original full definitions unavailable; names below are descriptive reconstructions.
- Source: `app/main.py`, `app/packaging/packaged_desktop_host.py`, `app/packaging/packaged_processes.py`, `app/packaging/runtime_lifecycle.py`, `app/model_runtime.py`
- API: `GET /health`; `GET /providers`; `GET /models`
- Persistence: Packaged runtime config; migration ledger; provider OS vault
- UI/entry: `frontend/src/packagedHost.ts`, `frontend/src/ui/ModelCenter.tsx`
- Test inventory: `tests/test_packaged_desktop_composition_v070.py`, `tests/test_runtime_ownership_foundation_v070.py`, `tests/test_packaged_postgres_migrations_v070.py`
- Evidence: docs/delivery/dot-astra-rc-r2/BASELINE_RECEIPT.md
- Provider: None; deterministic local application
- Priority/dependencies: P0; D04, D16, D18
- Next check for each row: run listed tests at final SHA, then resolve the row-specific limitation.

| Code / bounded feature | Before → after | Implementation / integration / verification / visible state | Row-specific limitation / next acceptance |
|---|---|---|---|
| A01 Embedded desktop frontend | WebView2 Host/static frontend already existed. → Retained packaged Host/React bridge; UI extensions use the same shell. | IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE | Interactive Windows/WebView2 lifecycle and screenshots still NOT_RUN. Source: app/packaging/packaged_desktop_host.py, app/packaging/static_frontend.py Entry: frontend/src/packagedHost.ts |
| A02 Desktop launch and child lifecycle | Packaged launcher and owned-process controls existed. → Existing launcher retained; Windows build/provenance work is separate from an installable full runtime. | IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE | Clean install, upgrades, uninstall data retention and actual window launch remain pending. Source: app/packaging/packaged_desktop_launcher.py, app/packaging/packaged_launcher.py Entry: frontend/src/packagedHost.ts |
| A03 FastAPI application | Versioned API and service composition existed. → New authoring/media/workflow/plugin routers registered through existing app composition. | IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE | Final full-suite exact-SHA result pending. |
| A04 Bundled PostgreSQL runtime | Packaged PostgreSQL bootstrap existed. → Privacy migration registered; no replacement runtime architecture. | IMPLEMENTED / CONNECTED / NOT_RUN / EXPERIMENTAL | Clean Windows bundled runtime delivery and real final PostgreSQL run pending. Source: app/packaging/packaged_processes.py, app/packaging/database_bootstrap.py Entry: frontend/src/packagedHost.ts |
| A05 Database migration | Migration ledger through inherited schema existed. → Migration 018 persists/validates foreshadowing policy and preserves stricter imported policies. | IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE | Real PostgreSQL upgrade/restart/recovery gate pending exact final SHA. Source: app/packaging/postgres_migrations.py, database/migrations/018_context_privacy.sql Entry: frontend/src/packagedHost.ts |
| A06 Restart, shutdown and recovery | Owned-process lifecycle and generation recovery existed. → Non-destructive verified backup/restore added; interrupted Agent jobs fail for explicit retry. | IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE | Windows process/ACL/power-loss checks remain unrun. Source: app/packaging/runtime_lifecycle.py, app/backup_restore.py Entry: frontend/src/packagedHost.ts |
| A07 Desktop bridge | Trusted Host bridge existed. → Bridge preserved; new UI does not put provider secrets in browser storage. | IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE | Real WebView2 interaction and Host authorization handoff pending. Source: app/packaging/desktop_bridge.py, app/packaging/host_uplink.py Entry: frontend/src/packagedHost.ts |
| A08 Trusted session and credential boundary | Opaque session and OS vault architecture already existed. → Legacy supported provider dispatch resolves vault entries; packaged env-only key is insufficient. | IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE | Native Windows vault/Host end-to-end remains unrun. Source: app/credential_vault.py, app/trusted_sessions.py Entry: frontend/src/novel/DeepSeekCredentialControl.tsx |
| A09 Text provider execution | Compatible adapter and old real-provider history existed; current source egress guard was incomplete. → Last-send source/version/privacy checks, native Claude/Gemini protocols, cancellation/usage and explicit Mock disclosure. | IMPLEMENTED / CONNECTED / MOCK_ONLY / NOT_CONFIGURED | No current real provider, credential, billing or quality verification; full v2 authoritative broker incomplete. Source: app/providers.py, app/openai_compatible.py, app/native_text_providers.py, app/jobs.py Entry: frontend/src/ui/ModelCenter.tsx, frontend/src/novel/AiWritingPanel.tsx Provider: Guarded selected text adapter: compatible/Ollama/Claude/Gemini as configured; transport tests/mock only, no current real model calls |
| A10 Multi-provider/model routing | Catalog and explicit text/media adapters existed. → Explicit native/compatible model selection and trusted adapters wired; v2 diagnostic ALLOW never authorizes execution. | PARTIAL / CONNECTED / MOCK_ONLY / NOT_CONFIGURED | Multiple named profiles, authoritative compatibility/budget/permission broker and all-vendor coverage absent. Source: app/model_runtime.py, app/provider_runtime_v2_routing_service.py, app/providers.py Entry: frontend/src/ui/ModelCenter.tsx Provider: Guarded selected text adapter: compatible/Ollama/Claude/Gemini as configured; transport tests/mock only, no current real model calls |

### B. Novel authoring

- Requirement source: `AI-Novel-Studio-V1.0-Feature-Audit.md`, original code rows. Original full definitions unavailable; names below are descriptive reconstructions.
- Source: `app/services/novel_service.py`, `app/services/chapter_service.py`, `app/services/generation_service.py`, `app/jobs.py`
- API: `POST /novels`; `GET/POST /novels/{nid}/chapters`; `PUT /chapters/{id}`; `POST /generate/{operation}`; `POST /generation/{id}/accept`; `GET/POST /novels/{nid}/planning-runs`; `GET /novels/{nid}/planning-runs/{rid}`; `POST /novels/{nid}/planning-runs/{rid}/cancel`; `POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft`
- Persistence: File/PostgreSQL novel/chapter/revision/generation repositories; generation snapshot/state
- UI/entry: `frontend/src/App.tsx`, `frontend/src/novel/AiWritingPanel.tsx`, `frontend/src/RevisionPanel.tsx`
- Test inventory: `tests/test_core.py`, `tests/test_chapter_concurrency.py`, `tests/test_generation_idempotency_contracts.py`, `tests/test_generation_variants_phase3.py`, `tests/test_r2_generation_egress.py`, `tests/test_r2_ai_planning.py`, `frontend/src/novel/AIPlanningPanel.test.tsx`
- Evidence: docs/delivery/dot-astra-rc-r2/runtime-work.md
- Provider: None; deterministic local application
- Priority/dependencies: P0/P1; D03, D05
- Next check for each row: run listed tests at final SHA, then resolve the row-specific limitation.

| Code / bounded feature | Before → after | Implementation / integration / verification / visible state | Row-specific limitation / next acceptance |
|---|---|---|---|
| B01 Novel/project creation | Novel creation and basic overview already existed. → Core creation retained; persisted plans/comments/goal entries extend project workflow. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Final browser save/reopen journey pending; no claim of all historical overview requirements. |
| B02 Workspace organization | Workspace/storyline/branch identity and basic navigation existed. → Existing identity model reused by new routes; no parallel accounts. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Interactive multi-user desktop acceptance pending. |
| B03 Chapter lifecycle | Create/archive/duplicate/move chapter operations existed. → Existing atomic lifecycle reused by creation/import/audio references. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Final backend and browser lifecycle rerun pending. |
| B04 Editor and saving | TipTap editor, versioned writes and unsaved conflict handling existed. → Retained editor/save contract and generation acceptance boundary. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Crash/IME/undo/keyboard desktop acceptance and complete browser journey pending. |
| B05 Chapter version history | Persistent chapter revisions existed. → All new author plans/comments/media snapshots retain source versions; history remains authoritative. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Final history/reopen regression pending. |
| B06 Version restore | Optimistic version restore existed. → Restore remains explicit; plan restore creates a new reviewable draft rather than overwriting history. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Native unexpected-exit/unsaved-local-draft combinations require acceptance. |
| B07 AI continuation | Continue operation existed but old baseline could send raw restricted source. → Version/hash/privacy-bound actual dispatch; returned content remains Draft until Accept. | IMPLEMENTED / CONNECTED / MOCK_ONLY / NOT_CONFIGURED | Current real model and full browser Draft/Diff/Accept/recovery journey NOT_RUN. Provider: Guarded selected text adapter: compatible/Ollama/Claude/Gemini as configured; transport tests/mock only, no current real model calls |
| B08 AI rewrite | Rewrite/selection and review path existed. → Actual egress rechecks, selected-text membership, owner-scoped job access and repeat-safe accept enforced. | IMPLEMENTED / CONNECTED / MOCK_ONLY / NOT_CONFIGURED | Real-provider output quality and interrupted live stream NOT_RUN. Provider: Guarded selected text adapter: compatible/Ollama/Claude/Gemini as configured; transport tests/mock only, no current real model calls |
| B09 AI polishing (inferred label) | Generic operation dispatch existed; audit omitted precise historical name. → Current polish operation shares guarded generation, Draft/Diff/Accept and failure handling. | IMPLEMENTED / CONNECTED / MOCK_ONLY / NOT_CONFIGURED | Precise original definition unavailable; real model NOT_RUN. Provider: Guarded selected text adapter: compatible/Ollama/Claude/Gemini as configured; transport tests/mock only, no current real model calls |
| B10 AI brainstorming (inferred label) | Generic operation dispatch existed; audit omitted precise historical name. → Current brainstorm operation shares guarded generation and review. | IMPLEMENTED / CONNECTED / MOCK_ONLY / NOT_CONFIGURED | Precise original definition unavailable; real model NOT_RUN. Provider: Guarded selected text adapter: compatible/Ollama/Claude/Gemini as configured; transport tests/mock only, no current real model calls |
| B11 Multiple writing candidates | Variant endpoint and comparison UI existed despite historical TODO. → Variant ownership, scoped idempotency and explicit single acceptance are reinforced; persistent jobs rediscoverable. | PARTIAL / CONNECTED / MOCK_ONLY / NOT_CONFIGURED | Not a candidate-synthesis engine; full browser multi-candidate recovery and real quality NOT_RUN. Provider: Guarded selected text adapter: compatible/Ollama/Claude/Gemini as configured; transport tests/mock only, no current real model calls |
| B12 Reusable writing style | Only one-off style strings/presets existed. → Typed versioned STYLE drafts, approval, history/restore and actual generation input with last-hop review recheck. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Manual style authoring works; no learned style model; generation requires separately configured provider. Structured-model subpath: CONNECTED / MOCK_ONLY / NOT_CONFIGURED; local explicit extraction CONTRACT_VERIFIED. Source: app/services/creation_workbench_service.py, app/creation_workbench_api.py, app/api.py, app/jobs.py, app/services/ai_planning_service.py, app/ai_planning_api.py, app/planning_extraction.py Entry: frontend/src/novel/CreationWorkbenchPanel.tsx, frontend/src/App.tsx, frontend/src/novel/AIPlanningPanel.tsx Evidence: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.txt; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md Provider: Manual/local explicit extraction available; optional registered TextModelNode selected-provider suggestions are MOCK_ONLY verified / actual provider NOT_RUN. Manual persistence and explicit markers are CONTRACT_VERIFIED; the optional structured model path is MOCK_ONLY. At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes. |
| B13 Writing goals and progress | Goal APIs and App goal display/editor already existed. → Existing targets/deadline/current counts retained and chapter operations refresh progress. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | No new analytics claim; final UI goal persistence run pending. Source: app/services/novel_service.py, app/api.py Entry: frontend/src/App.tsx |

### C. Import and knowledge review

- Requirement source: `AI-Novel-Studio-V1.0-Feature-Audit.md`, original code rows. Original full definitions unavailable; names below are descriptive reconstructions.
- Source: `app/import_parsers.py`, `app/knowledge_extraction.py`, `app/services/import_review_service.py`, `app/services/import_apply_service.py`
- API: `POST /novels/import`; `GET /novels/{nid}/import/knowledge-base/review`; `GET/PUT /novels/{nid}/import/knowledge-base/review/{review_id}`; `POST /novels/{nid}/import/knowledge-base/review`; `GET/POST /novels/{nid}/planning-runs`; `GET /novels/{nid}/planning-runs/{rid}`; `POST /novels/{nid}/planning-runs/{rid}/cancel`; `POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft`
- Persistence: import_reviews.json; durable per-review apply journal; File/PostgreSQL target entities
- UI/entry: `frontend/src/novel/NovelImportPanel.tsx`
- Test inventory: `tests/test_import_parsers.py`, `tests/test_import_ai_review.py`, `tests/test_r2_import_boundaries.py`, `tests/test_r2_import_apply_journal.py`, `tests/test_r2_ai_planning.py`, `frontend/src/novel/AIPlanningPanel.test.tsx`
- Evidence: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/import-apply-checkpoints.md; docs/delivery/dot-astra-rc-r2/evidence/synthetic-scale.json; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/synthetic-scale.json; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/synthetic-scale.json; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/synthetic-scale.json; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/synthetic-scale.json; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/synthetic-scale.json; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/synthetic-scale.json; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md
- Provider: None; deterministic local application
- Priority/dependencies: P1; D03, D06
- Next check for each row: run listed tests at final SHA, then resolve the row-specific limitation.

| Code / bounded feature | Before → after | Implementation / integration / verification / visible state | Row-specific limitation / next acceptance |
|---|---|---|---|
| C01 TXT import | TXT parsing and chapter import existed. → Existing parser reused with durable versioned knowledge review and safe application journal. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Measured 200-chapter/1,002,092-character synthetic File fixture exists (evidence/synthetic-scale.json); native picker and target-hardware performance acceptance pending. |
| C02 Markdown import | Markdown parsing/import existed. → Existing parser and source content retained; review can reopen. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | A measured million-character synthetic File fixture exists; malformed mixed-layout document coverage remains limited. |
| C03 DOCX import | DOCX parsing/import existed. → Parser remains actual file reader; review journal prevents silent all-or-nothing false success. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Target Word layouts and edge-case embedded content require independent acceptance. |
| C04 PDF import | PDF text extraction/fallback existed. → Existing text extraction retained; no OCR pipeline added. | PARTIAL / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Scanned/image-only PDFs and layout reconstruction not implemented as reliable import. |
| C05 Import structure analysis | Adaptation/review could hold structure proposals. → Bounded local heuristics emit exact version/hash/offset evidence; optional AI review remains review-only. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history. | PARTIAL / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL | Explicit-marker rule/plot proposals now exist separately from four-group import review. Natural-language rule/structure quality, cross-chapter identity, interrupted large-book analysis and hierarchy generation remain incomplete. Structured-model subpath: CONNECTED / MOCK_ONLY / NOT_CONFIGURED; local explicit extraction CONTRACT_VERIFIED. Source: app/import_parsers.py, app/knowledge_extraction.py, app/services/import_review_service.py, app/services/import_apply_service.py, app/services/ai_planning_service.py, app/ai_planning_api.py, app/planning_extraction.py Entry: frontend/src/novel/NovelImportPanel.tsx, frontend/src/novel/AIPlanningPanel.tsx Provider: Manual/local explicit extraction available; optional registered TextModelNode selected-provider suggestions are MOCK_ONLY verified / actual provider NOT_RUN. Manual persistence and explicit markers are CONTRACT_VERIFIED; the optional structured model path is MOCK_ONLY. At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes. |
| C06 Character extraction/review | Review surface existed without deterministic extraction closure. → Heuristic English/Chinese names, within-chapter dedupe, editable versioned review and journaled accepted upserts. | PARTIAL / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL | No cross-chapter identity resolution guarantee; homonym quality needs real corpus evaluation. |
| C07 Location extraction/review | Review model could store location candidates. → Bounded place-name heuristics with source evidence and explicit accepted application. | PARTIAL / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL | Heuristic false positives remain; geographic semantics and long-form quality unverified. |
| C08 Import timeline candidates | Timeline CRUD existed; import linkage incomplete. → Chapter-derived timeline candidates carry source locations and manual review/application. | PARTIAL / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL | A chapter summary is not temporal reasoning; precise event chronology extraction remains incomplete. |
| C09 Import foreshadowing candidates | Foreshadowing/canon review existed. → Cue-based candidate extraction, privacy, selection and checkpointed application connected. | PARTIAL / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL | Semantic setup/payoff matching and rule extraction remain incomplete. |
| C10 Adapt unfinished novel | Adaptation service and reviewable generation workflow existed. → Existing adaptation retained under shared runtime/privacy boundaries. | PARTIAL / CONNECTED / CONTRACT_VERIFIED / NOT_CONFIGURED | Real-model literary quality, long-book continuity and desktop acceptance NOT_RUN. |

### D. World knowledge

- Requirement source: `AI-Novel-Studio-V1.0-Feature-Audit.md`, original code rows. Original full definitions unavailable; names below are descriptive reconstructions.
- Source: `app/services/lore_service.py`, `app/lore/continuity_engine.py`, `app/services/creation_workbench_service.py`, `app/services/novel_service.py`, `app/services/creation_workbench_service.py`, `app/creation_workbench_api.py`, `app/services/creation_workbench_service.py`, `app/creation_workbench_api.py`, `app/services/creation_workbench_service.py`, `app/creation_workbench_api.py`, `app/services/creation_workbench_service.py`, `app/creation_workbench_api.py`
- API: `GET/POST /novels/{nid}/world-rules`; `GET/POST /novels/{nid}/creation-records`; `POST /novels/{nid}/creation-records/{rid}/{action}`; `GET/POST /novels/{nid}/planning-runs`; `GET /novels/{nid}/planning-runs/{rid}`; `POST /novels/{nid}/planning-runs/{rid}/cancel`; `POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft`; `GET/POST /novels/{nid}/planning-runs`; `GET /novels/{nid}/planning-runs/{rid}`; `POST /novels/{nid}/planning-runs/{rid}/cancel`; `POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft`; `GET/POST /novels/{nid}/planning-runs`; `GET /novels/{nid}/planning-runs/{rid}`; `POST /novels/{nid}/planning-runs/{rid}/cancel`; `POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft`; `GET/POST /novels/{nid}/planning-runs`; `GET /novels/{nid}/planning-runs/{rid}`; `POST /novels/{nid}/planning-runs/{rid}/cancel`; `POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft`; `GET/POST /novels/{nid}/planning-runs`; `GET /novels/{nid}/planning-runs/{rid}`; `POST /novels/{nid}/planning-runs/{rid}/cancel`; `POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft`; `GET/POST /novels/{nid}/planning-runs`; `GET /novels/{nid}/planning-runs/{rid}`; `POST /novels/{nid}/planning-runs/{rid}/cancel`; `POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft`
- Persistence: File/PostgreSQL Lore and domain records; versioned creation_records sidecar for new typed manual structures
- UI/entry: `frontend/src/novel/StoryDatabase.tsx`, `frontend/src/novel/CreationWorkbenchPanel.tsx`, `frontend/src/novel/WorldBuildingDashboard.tsx`
- Test inventory: `tests/test_lore_contract.py`, `tests/test_world_rule_payload.py`, `tests/test_r2_creation_workbench.py`, `tests/test_r2_ai_planning.py`, `frontend/src/novel/AIPlanningPanel.test.tsx`, `tests/test_r2_ai_planning.py`, `frontend/src/novel/AIPlanningPanel.test.tsx`, `tests/test_r2_ai_planning.py`, `frontend/src/novel/AIPlanningPanel.test.tsx`, `tests/test_r2_ai_planning.py`, `frontend/src/novel/AIPlanningPanel.test.tsx`, `tests/test_r2_ai_planning.py`, `frontend/src/novel/AIPlanningPanel.test.tsx`, `tests/test_r2_ai_planning.py`, `frontend/src/novel/AIPlanningPanel.test.tsx`
- Evidence: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/privacy-recovery-focused.txt; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md
- Provider: None; deterministic local application
- Priority/dependencies: P1; D06, D07
- Next check for each row: run listed tests at final SHA, then resolve the row-specific limitation.

| Code / bounded feature | Before → after | Implementation / integration / verification / visible state | Row-specific limitation / next acceptance |
|---|---|---|---|
| D01 Lore/world knowledge base | Lore evidence/proposals/memory existed. → Stricter privacy filtering and reviewed manual typed structures reuse existing project identity. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history. | PARTIAL / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Full semantic world model and evidence-quality acceptance incomplete. Structured-model subpath: CONNECTED / MOCK_ONLY / NOT_CONFIGURED; local explicit extraction CONTRACT_VERIFIED. Source: app/services/lore_service.py, app/lore/continuity_engine.py, app/services/creation_workbench_service.py, app/services/novel_service.py, app/creation_workbench_api.py, app/services/ai_planning_service.py, app/ai_planning_api.py, app/planning_extraction.py Entry: frontend/src/novel/StoryDatabase.tsx, frontend/src/novel/CreationWorkbenchPanel.tsx, frontend/src/novel/WorldBuildingDashboard.tsx, frontend/src/novel/AIPlanningPanel.tsx Provider: Manual/local explicit extraction available; optional registered TextModelNode selected-provider suggestions are MOCK_ONLY verified / actual provider NOT_RUN. Manual persistence and explicit markers are CONTRACT_VERIFIED; the optional structured model path is MOCK_ONLY. At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes. |
| D02 World rules | Approved rule registry and forbidden-term checks existed. → Conservative privacy persistence and manual structure references retained. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history. | PARTIAL / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Model/local explicit proposals become ABILITY drafts and require separate review; they do not automatically enter the approved world-rule registry or semantic checker. Structured-model subpath: CONNECTED / MOCK_ONLY / NOT_CONFIGURED; local explicit extraction CONTRACT_VERIFIED. Source: app/services/lore_service.py, app/lore/continuity_engine.py, app/services/creation_workbench_service.py, app/services/novel_service.py, app/creation_workbench_api.py, app/services/ai_planning_service.py, app/ai_planning_api.py, app/planning_extraction.py Entry: frontend/src/novel/StoryDatabase.tsx, frontend/src/novel/CreationWorkbenchPanel.tsx, frontend/src/novel/WorldBuildingDashboard.tsx, frontend/src/novel/AIPlanningPanel.tsx Provider: Manual/local explicit extraction available; optional registered TextModelNode selected-provider suggestions are MOCK_ONLY verified / actual provider NOT_RUN. Manual persistence and explicit markers are CONTRACT_VERIFIED; the optional structured model path is MOCK_ONLY. At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes. |
| D03 Historical event records | No dedicated historical-event structure found in baseline audit. → HISTORY record kind has schema, versions, API, approval/restore and UI. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history. | PARTIAL / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL | Manual and model-proposed source-evidenced records now exist; historical chronology inference and automatic Canon/checker integration remain absent. Structured-model subpath: CONNECTED / MOCK_ONLY / NOT_CONFIGURED; local explicit extraction CONTRACT_VERIFIED. Source: app/services/lore_service.py, app/lore/continuity_engine.py, app/services/creation_workbench_service.py, app/services/novel_service.py, app/creation_workbench_api.py, app/services/ai_planning_service.py, app/ai_planning_api.py, app/planning_extraction.py Entry: frontend/src/novel/StoryDatabase.tsx, frontend/src/novel/CreationWorkbenchPanel.tsx, frontend/src/novel/WorldBuildingDashboard.tsx, frontend/src/novel/AIPlanningPanel.tsx Evidence: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.txt; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md Provider: Manual/local explicit extraction available; optional registered TextModelNode selected-provider suggestions are MOCK_ONLY verified / actual provider NOT_RUN. Manual persistence and explicit markers are CONTRACT_VERIFIED; the optional structured model path is MOCK_ONLY. At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes. |
| D04 Geography structures | Location CRUD was not a geography system. → GEOGRAPHY records support referenced locations, rules and versioned review. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history. | PARTIAL / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL | Geography drafts can be model-proposed with evidence; no map/topology/path or geographic consistency engine. Structured-model subpath: CONNECTED / MOCK_ONLY / NOT_CONFIGURED; local explicit extraction CONTRACT_VERIFIED. Source: app/services/lore_service.py, app/lore/continuity_engine.py, app/services/creation_workbench_service.py, app/services/novel_service.py, app/creation_workbench_api.py, app/services/ai_planning_service.py, app/ai_planning_api.py, app/planning_extraction.py Entry: frontend/src/novel/StoryDatabase.tsx, frontend/src/novel/CreationWorkbenchPanel.tsx, frontend/src/novel/WorldBuildingDashboard.tsx, frontend/src/novel/AIPlanningPanel.tsx Evidence: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.txt; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md Provider: Manual/local explicit extraction available; optional registered TextModelNode selected-provider suggestions are MOCK_ONLY verified / actual provider NOT_RUN. Manual persistence and explicit markers are CONTRACT_VERIFIED; the optional structured model path is MOCK_ONLY. At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes. |
| D05 Civilization/organization structures | No dedicated civilization product found. → CIVILIZATION record kind persisted with constraints, references, version/review UI. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history. | PARTIAL / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL | Civilization drafts can be model-proposed with evidence; simulation/hierarchy reasoning and automatic Canon integration absent. Structured-model subpath: CONNECTED / MOCK_ONLY / NOT_CONFIGURED; local explicit extraction CONTRACT_VERIFIED. Source: app/services/lore_service.py, app/lore/continuity_engine.py, app/services/creation_workbench_service.py, app/services/novel_service.py, app/creation_workbench_api.py, app/services/ai_planning_service.py, app/ai_planning_api.py, app/planning_extraction.py Entry: frontend/src/novel/StoryDatabase.tsx, frontend/src/novel/CreationWorkbenchPanel.tsx, frontend/src/novel/WorldBuildingDashboard.tsx, frontend/src/novel/AIPlanningPanel.tsx Evidence: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.txt; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md Provider: Manual/local explicit extraction available; optional registered TextModelNode selected-provider suggestions are MOCK_ONLY verified / actual provider NOT_RUN. Manual persistence and explicit markers are CONTRACT_VERIFIED; the optional structured model path is MOCK_ONLY. At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes. |
| D06 Ability/power structures | No dedicated ability product found. → ABILITY records retain rules, references, history and explicit approval. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history. | PARTIAL / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL | Explicit-marked or model-proposed rules can become reviewed drafts; no power-system solver or automatic formal rule installation. Structured-model subpath: CONNECTED / MOCK_ONLY / NOT_CONFIGURED; local explicit extraction CONTRACT_VERIFIED. Source: app/services/lore_service.py, app/lore/continuity_engine.py, app/services/creation_workbench_service.py, app/services/novel_service.py, app/creation_workbench_api.py, app/services/ai_planning_service.py, app/ai_planning_api.py, app/planning_extraction.py Entry: frontend/src/novel/StoryDatabase.tsx, frontend/src/novel/CreationWorkbenchPanel.tsx, frontend/src/novel/WorldBuildingDashboard.tsx, frontend/src/novel/AIPlanningPanel.tsx Evidence: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.txt; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md Provider: Manual/local explicit extraction available; optional registered TextModelNode selected-provider suggestions are MOCK_ONLY verified / actual provider NOT_RUN. Manual persistence and explicit markers are CONTRACT_VERIFIED; the optional structured model path is MOCK_ONLY. At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes. |
| D07 World consistency checks | Deterministic continuity/rule service existed. → Existing findings retained with stricter policy/source boundaries. | PARTIAL / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL | Full semantic aggregate consistency and new manual-record-to-rule engine integration incomplete. |

### E. Characters

- Requirement source: `AI-Novel-Studio-V1.0-Feature-Audit.md`, original code rows. Original full definitions unavailable; names below are descriptive reconstructions.
- Source: `app/services/novel_service.py`, `app/services/v1_capability_service.py`, `app/services/creation_workbench_service.py`, `app/review.py`, `app/services/creation_workbench_service.py`, `app/creation_workbench_api.py`
- API: `PUT /novels/{nid}/characters/{id}`; `GET/POST /novels/{nid}/characters/{id}/evolution`; `POST /novels/{nid}/characters/consistency-check`; `GET/POST /novels/{nid}/creation-records`; `GET/POST /novels/{nid}/planning-runs`; `GET /novels/{nid}/planning-runs/{rid}`; `POST /novels/{nid}/planning-runs/{rid}/cancel`; `POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft`
- Persistence: File/PostgreSQL character/relationship rows; capability evolution and creation_records sidecars
- UI/entry: `frontend/src/novel/StoryDatabase.tsx`, `frontend/src/novel/WorldRelationshipGraph.tsx`, `frontend/src/novel/CreationWorkbenchPanel.tsx`
- Test inventory: `tests/test_phase4_characters.py`, `tests/test_phase4_relationships.py`, `tests/test_r2_creation_workbench.py`, `tests/test_r2_ai_planning.py`, `frontend/src/novel/AIPlanningPanel.test.tsx`
- Evidence: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml
- Provider: None; deterministic local application
- Priority/dependencies: P1; D07
- Next check for each row: run listed tests at final SHA, then resolve the row-specific limitation.

| Code / bounded feature | Before → after | Implementation / integration / verification / visible state | Row-specific limitation / next acceptance |
|---|---|---|---|
| E01 Character records | Character CRUD and editor existed. → Existing persistent character records retained and usable by reference validation. | IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE | Final cross-branch character/UI acceptance pending. |
| E02 Character attributes | Flexible character metadata existed. → Existing attributes plus referenced versioned manual psychology records available. | PARTIAL / CONNECTED / NOT_RUN / AVAILABLE | No comprehensive typed/versioned character attribute schema migration delivered. |
| E03 Character relationships/graph | Relationship CRUD and graph/filter view already existed. → Actual relationship graph retained; new plans can reference entities. | IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE | No automatic inferred relationship acceptance or causal reasoning claim. |
| E04 Character growth records | Evolution records/editor already existed. → Existing evidence/version-linked evolution records retained. | PARTIAL / CONNECTED / NOT_RUN / AVAILABLE | Dedicated growth planner/route visualization and integration with all new records incomplete. |
| E05 Psychological records/engine | No psychological-state engine found. → PSYCHOLOGY record kind adds manual schema, references, approval/version/restore/UI. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history. | PARTIAL / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL | Evidence-bound psychology suggestions can become reviewed drafts; no psychological-state inference/simulation engine or validated character-quality benchmark. Structured-model subpath: CONNECTED / MOCK_ONLY / NOT_CONFIGURED; local explicit extraction CONTRACT_VERIFIED. Source: app/services/novel_service.py, app/services/v1_capability_service.py, app/services/creation_workbench_service.py, app/review.py, app/creation_workbench_api.py, app/services/ai_planning_service.py, app/ai_planning_api.py, app/planning_extraction.py Entry: frontend/src/novel/StoryDatabase.tsx, frontend/src/novel/WorldRelationshipGraph.tsx, frontend/src/novel/CreationWorkbenchPanel.tsx, frontend/src/novel/AIPlanningPanel.tsx Evidence: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.txt; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md Provider: Manual/local explicit extraction available; optional registered TextModelNode selected-provider suggestions are MOCK_ONLY verified / actual provider NOT_RUN. Manual persistence and explicit markers are CONTRACT_VERIFIED; the optional structured model path is MOCK_ONLY. At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes. |
| E06 Character consistency | Deterministic check endpoint/editor action existed. → Current rule checks and evidence findings retained. | PARTIAL / CONNECTED / NOT_RUN / EXPERIMENTAL | Complete persistent semantic consistency workflow/quality catalog incomplete. |

### F. Plot planning

- Requirement source: `AI-Novel-Studio-V1.0-Feature-Audit.md`, original code rows. Original full definitions unavailable; names below are descriptive reconstructions.
- Source: `app/services/novel_service.py`, `app/services/creation_workbench_service.py`, `app/narrative.py`, `app/services/creation_workbench_service.py`, `app/creation_workbench_api.py`, `app/services/creation_workbench_service.py`, `app/creation_workbench_api.py`, `app/services/creation_workbench_service.py`, `app/creation_workbench_api.py`, `app/services/creation_workbench_service.py`, `app/creation_workbench_api.py`
- API: `GET/PUT /novels/{nid}/outline`; `GET/POST /novels/{nid}/creation-records`; `PUT /novels/{nid}/volumes/{volume_id}`; `PUT /novels/{nid}/scenes/{scene_id}`; `GET /novels/{nid}/story-routes`; `PUT /novels/{nid}/story-routes/{route_id}`; `GET/POST /novels/{nid}/planning-runs`; `GET /novels/{nid}/planning-runs/{rid}`; `POST /novels/{nid}/planning-runs/{rid}/cancel`; `POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft`; `GET/POST /novels/{nid}/planning-runs`; `GET /novels/{nid}/planning-runs/{rid}`; `POST /novels/{nid}/planning-runs/{rid}/cancel`; `POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft`; `GET/POST /novels/{nid}/planning-runs`; `GET /novels/{nid}/planning-runs/{rid}`; `POST /novels/{nid}/planning-runs/{rid}/cancel`; `POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft`; `GET/POST /novels/{nid}/planning-runs`; `GET /novels/{nid}/planning-runs/{rid}`; `POST /novels/{nid}/planning-runs/{rid}/cancel`; `POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft`; `GET/POST /novels/{nid}/planning-runs`; `GET /novels/{nid}/planning-runs/{rid}`; `POST /novels/{nid}/planning-runs/{rid}/cancel`; `POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft`
- Persistence: File/PostgreSQL outline/volume/scene/route records; creation_records versioned sidecar
- UI/entry: `frontend/src/novel/StoryDatabase.tsx`, `frontend/src/novel/CreationWorkbenchPanel.tsx`
- Test inventory: `tests/test_phase5_outline.py`, `tests/test_phase5_volumes.py`, `tests/test_phase5_scenes.py`, `tests/test_phase5_story_routes.py`, `tests/test_r2_creation_workbench.py`, `tests/test_r2_ai_planning.py`, `frontend/src/novel/AIPlanningPanel.test.tsx`, `tests/test_r2_ai_planning.py`, `frontend/src/novel/AIPlanningPanel.test.tsx`, `tests/test_r2_ai_planning.py`, `frontend/src/novel/AIPlanningPanel.test.tsx`, `tests/test_r2_ai_planning.py`, `frontend/src/novel/AIPlanningPanel.test.tsx`, `tests/test_r2_ai_planning.py`, `frontend/src/novel/AIPlanningPanel.test.tsx`
- Evidence: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md
- Provider: None; deterministic local application
- Priority/dependencies: P1; D05, D07
- Next check for each row: run listed tests at final SHA, then resolve the row-specific limitation.

| Code / bounded feature | Before → after | Implementation / integration / verification / visible state | Row-specific limitation / next acceptance |
|---|---|---|---|
| F01 AI outline generation | Manual outline editor existed, no dedicated outline generator. → Approved PLOT instructions feed existing text generation; selected-model Agent can propose text. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history. | PARTIAL / CONNECTED / NOT_RUN / EXPERIMENTAL | Structured PLOT candidates feed approved generation input, but full outline→volume→chapter→scene decomposition/review/apply hierarchy remains incomplete. Structured-model subpath: CONNECTED / MOCK_ONLY / NOT_CONFIGURED; local explicit extraction CONTRACT_VERIFIED. Source: app/services/novel_service.py, app/services/creation_workbench_service.py, app/narrative.py, app/creation_workbench_api.py, app/services/ai_planning_service.py, app/ai_planning_api.py, app/planning_extraction.py Entry: frontend/src/novel/StoryDatabase.tsx, frontend/src/novel/CreationWorkbenchPanel.tsx, frontend/src/novel/AIPlanningPanel.tsx Provider: Manual/local explicit extraction available; optional registered TextModelNode selected-provider suggestions are MOCK_ONLY verified / actual provider NOT_RUN. Manual persistence and explicit markers are CONTRACT_VERIFIED; the optional structured model path is MOCK_ONLY. At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes. |
| F02 Three-act planning | No typed three-act domain record found. → PLOT requires three acts/conflict/climax/ending; versions, compare, approval and generation input connected. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Manual three-act record closure and bounded structured proposals exist; real-provider/plot-quality acceptance NOT_RUN. Structured-model subpath: CONNECTED / MOCK_ONLY / NOT_CONFIGURED; local explicit extraction CONTRACT_VERIFIED. Source: app/services/novel_service.py, app/services/creation_workbench_service.py, app/narrative.py, app/creation_workbench_api.py, app/services/ai_planning_service.py, app/ai_planning_api.py, app/planning_extraction.py Entry: frontend/src/novel/StoryDatabase.tsx, frontend/src/novel/CreationWorkbenchPanel.tsx, frontend/src/novel/AIPlanningPanel.tsx Evidence: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.txt; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md Provider: Manual/local explicit extraction available; optional registered TextModelNode selected-provider suggestions are MOCK_ONLY verified / actual provider NOT_RUN. Manual persistence and explicit markers are CONTRACT_VERIFIED; the optional structured model path is MOCK_ONLY. At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes. |
| F03 Volume planning | Volume APIs and editor existed. → Existing persisted manual volume planning retained. | IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE | No automatic AI decomposition/acceptance claim; final API/UI rerun pending. |
| F04 Chapter outline planning | Outline APIs and editor existed. → Existing persisted outline retained and privacy-filtered in outbound contexts. | IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE | Dedicated AI outline generation is separate F01 gap. |
| F05 Scene planning | Scene APIs/editor existed. → Existing scene planning reused by screenplay/media references. | IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE | No automatic semantic scene design guarantee. |
| F06 Main story routes | Story route/thread CRUD existed. → Existing routes remain referencable from versioned PLOT records. | IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE | Full graphical route-to-manuscript planning remains a limited manual workflow. |
| F07 Subplot routes | Route type/branch metadata and editor existed. → Existing subplot records retained without inventing analytics. | IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE | Dedicated subplot balance/causal analytics absent. |
| F08 Conflict design | Continuity finding proposals existed without design assistant. → Typed required PLOT conflict, comparison and approved generation input added. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history. | PARTIAL / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Structured conflict proposals require exact source evidence and explicit review; no broader semantic conflict-quality engine. Structured-model subpath: CONNECTED / MOCK_ONLY / NOT_CONFIGURED; local explicit extraction CONTRACT_VERIFIED. Source: app/services/novel_service.py, app/services/creation_workbench_service.py, app/narrative.py, app/creation_workbench_api.py, app/services/ai_planning_service.py, app/ai_planning_api.py, app/planning_extraction.py Entry: frontend/src/novel/StoryDatabase.tsx, frontend/src/novel/CreationWorkbenchPanel.tsx, frontend/src/novel/AIPlanningPanel.tsx Evidence: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.txt; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md Provider: Manual/local explicit extraction available; optional registered TextModelNode selected-provider suggestions are MOCK_ONLY verified / actual provider NOT_RUN. Manual persistence and explicit markers are CONTRACT_VERIFIED; the optional structured model path is MOCK_ONLY. At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes. |
| F09 Climax planning | No dedicated climax planning model found. → Required PLOT climax, versions, source linkage and generation input added. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history. | PARTIAL / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Structured climax proposals require exact source evidence and explicit review; no automated tension/pacing measurement. Structured-model subpath: CONNECTED / MOCK_ONLY / NOT_CONFIGURED; local explicit extraction CONTRACT_VERIFIED. Source: app/services/novel_service.py, app/services/creation_workbench_service.py, app/narrative.py, app/creation_workbench_api.py, app/services/ai_planning_service.py, app/ai_planning_api.py, app/planning_extraction.py Entry: frontend/src/novel/StoryDatabase.tsx, frontend/src/novel/CreationWorkbenchPanel.tsx, frontend/src/novel/AIPlanningPanel.tsx Evidence: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.txt; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md Provider: Manual/local explicit extraction available; optional registered TextModelNode selected-provider suggestions are MOCK_ONLY verified / actual provider NOT_RUN. Manual persistence and explicit markers are CONTRACT_VERIFIED; the optional structured model path is MOCK_ONLY. At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes. |
| F10 Multiple ending planning | Collaboration branches were not ending plans. → Multiple separately versioned PLOT endings can compare and be selected for generation. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history. | PARTIAL / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Multiple source-bound structured endings can be proposed/compared; no graph of consequence propagation or automatic branch-to-manuscript synthesis. Structured-model subpath: CONNECTED / MOCK_ONLY / NOT_CONFIGURED; local explicit extraction CONTRACT_VERIFIED. Source: app/services/novel_service.py, app/services/creation_workbench_service.py, app/narrative.py, app/creation_workbench_api.py, app/services/ai_planning_service.py, app/ai_planning_api.py, app/planning_extraction.py Entry: frontend/src/novel/StoryDatabase.tsx, frontend/src/novel/CreationWorkbenchPanel.tsx, frontend/src/novel/AIPlanningPanel.tsx Evidence: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.txt; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md Provider: Manual/local explicit extraction available; optional registered TextModelNode selected-provider suggestions are MOCK_ONLY verified / actual provider NOT_RUN. Manual persistence and explicit markers are CONTRACT_VERIFIED; the optional structured model path is MOCK_ONLY. At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes. |

### G. Foreshadowing and continuity

- Requirement source: `AI-Novel-Studio-V1.0-Feature-Audit.md`, original code rows. Original full definitions unavailable; names below are descriptive reconstructions.
- Source: `app/services/narrative_finding_service.py`, `app/services/continuity_finding_service.py`, `app/lore/continuity_engine.py`, `app/review.py`
- API: `GET /novels/{nid}/foreshadowing/reminders`; `POST /projects/{id}/continuity/checks`; `GET/POST narrative finding routes in app/api.py`
- Persistence: File/PostgreSQL timeline/foreshadowing/Canon/findings; conservative persisted privacy
- UI/entry: `frontend/src/novel/StoryDatabase.tsx`, `frontend/src/novel/ContinuityCheckPanel.tsx`, `frontend/src/novel/WorldBuildingDashboard.tsx`
- Test inventory: `tests/test_phase4_foreshadowing.py`, `tests/test_narrative_detection.py`, `tests/test_continuity_lifecycle.py`, `tests/test_r2_privacy_persistence.py`
- Evidence: docs/delivery/dot-astra-rc-r2/privacy-recovery-focused.txt
- Provider: None; deterministic local application
- Priority/dependencies: P1; D01, D07
- Next check for each row: run listed tests at final SHA, then resolve the row-specific limitation.

| Code / bounded feature | Before → after | Implementation / integration / verification / visible state | Row-specific limitation / next acceptance |
|---|---|---|---|
| G01 Foreshadowing records | Foreshadowing CRUD and PendingCanon existed. → Persisted strict privacy fixes plus reviewable extracted candidates integrated. | IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE | Final real PostgreSQL/restart check pending. |
| G02 Foreshadowing payoff tracking | Tracker/lifecycle metadata existed. → Existing status/reminder display retained with durable privacy. | PARTIAL / CONNECTED / NOT_RUN / AVAILABLE | Comprehensive payoff linkage and semantic lifecycle audit incomplete. |
| G03 Overdue reminders | Chapter-aware reminder query/UI existed. → Existing deterministic reminders retained. | PARTIAL / CONNECTED / NOT_RUN / AVAILABLE | No scheduled/background notification delivery; query is not a notification service. |
| G04 Timeline conflict checks | Deterministic continuity timeline conflict rules existed. → Rules retained; stricter timeline serialization prevents cloud leakage. | IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE | Coverage limited to implemented rules; full story temporal reasoning not claimed. |
| G05 Behavior consistency | Deterministic character behavior rules existed. → Existing checks retained with source-aware runtime filtering. | PARTIAL / CONNECTED / NOT_RUN / EXPERIMENTAL | Semantic behavior model and broad evidence-based rule catalog incomplete. |
| G06 World-rule violation checks | Approved rules/forbidden-term check existed. → Conservative policy preserves approved source restrictions. | PARTIAL / CONNECTED / NOT_RUN / EXPERIMENTAL | Semantic interpretation of arbitrary world/ability rules incomplete. |
| G07 Plot findings and resolution | Findings/check/resolve APIs and UI existed. → Existing workflow retained; human resolution remains explicit. | IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE | No assertion all narrative plot holes can be detected. |

### H. Agent team

- Requirement source: `AI-Novel-Studio-V1.0-Feature-Audit.md`, original code rows. Original full definitions unavailable; names below are descriptive reconstructions.
- Source: `app/agent_catalog.py`, `app/services/agent_job_service.py`, `app/services/agent_context_service.py`, `app/workflow_api.py`
- API: `GET /agents`; `POST /agent-jobs`; `GET /agent-jobs/{id}`; `Agent review/apply routes`; `Workflow Agent execute/synchronize routes`
- Persistence: Persisted Agent jobs; existing review/apply state; scope-bound workflow sidecars
- UI/entry: `frontend/src/novel/AgentTeamPanel.tsx`, `frontend/src/novel/AgentQueuePanel.tsx`, `frontend/src/novel/AgentResultReview.tsx`
- Test inventory: `tests/test_phase6_agent_jobs.py`, `tests/test_r2_provider_execution.py`, `tests/test_r2_workflow_execution.py`
- Evidence: docs/delivery/dot-astra-rc-r2/runtime-work.md
- Provider: Selected text adapter; actual model NOT_RUN
- Priority/dependencies: P2; D04, D13
- Next check for each row: run listed tests at final SHA, then resolve the row-specific limitation.

| Code / bounded feature | Before → after | Implementation / integration / verification / visible state | Row-specific limitation / next acceptance |
|---|---|---|---|
| H01 Planning Agent | Agent catalog/job primitives existed. → Guarded selected-model executor connected; local planning recipe explicitly uses user-supplied input. | PARTIAL / CONNECTED / MOCK_ONLY / NOT_CONFIGURED | Specialized structured planning outputs/domain application and real model quality incomplete. |
| H02 Writing Agent | Generation/Agent review/apply existed. → Actual selected-model job execution, source/usage provenance and restart failure recovery connected. | IMPLEMENTED / CONNECTED / MOCK_ONLY / NOT_CONFIGURED | Real provider NOT_RUN; generated work still needs explicit review/apply. |
| H03 Editing Agent | Generic review/apply roles existed. → Guarded executor shared; result approval remains explicit. | PARTIAL / CONNECTED / MOCK_ONLY / NOT_CONFIGURED | Dedicated editorial policy/quality engine not delivered. |
| H04 Continuity Agent | Continuity service existed, orchestration incomplete. → Agent nodes wait for real jobs; deterministic continuity remains separate. | PARTIAL / CONNECTED / MOCK_ONLY / NOT_CONFIGURED | Specialized automated continuity-to-finding-to-review recipe not complete. |
| H05 Director Agent | Adaptation/screenplay services existed. → Generic selected-model execution and local shot-proposal review recipe available. | PARTIAL / CONNECTED / MOCK_ONLY / NOT_CONFIGURED | Dedicated model-backed director scene/shot contract and apply closure incomplete. |
| H06 Art Agent | Generic asset tasks existed; no autonomous art agent. → Image review queue and Agent executor exist as distinct controlled paths. | PARTIAL / CONNECTED / MOCK_ONLY / NOT_CONFIGURED | No dedicated art-agent executor-to-image review workflow; generic components not full art agent. |
| H07 Multi-Agent coordination | Generic workflow lacked actual Agent completion gating. → Bounded DAG dispatches selected-model Agent jobs, waits for real state and retains approval/failure/cancel. | PARTIAL / CONNECTED / MOCK_ONLY / EXPERIMENTAL | No fully autonomous three-recipe domain closure; cross-process transactional scheduler not claimed. |

### I. Screenplay

- Requirement source: `AI-Novel-Studio-V1.0-Feature-Audit.md`, original code rows. Original full definitions unavailable; names below are descriptive reconstructions.
- Source: `app/services/screenplay_service.py`, `app/industry_export_formats.py`
- API: `GET/POST /novels/{nid}/screenplays`; `Screenplay scene/shot edit and revision endpoints in app/api.py`
- Persistence: Persisted screenplay records; branch scope; approved version fork and source provenance
- UI/entry: `frontend/src/novel/ScreenplayPanel.tsx`
- Test inventory: `tests/test_phase8_screenplay.py`, `tests/test_phase8_shots.py`, `tests/test_screenplay_branch_revision.py`, `tests/test_industry_export_queue.py`
- Evidence: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json
- Provider: None; deterministic local application
- Priority/dependencies: P1; D08, D09
- Next check for each row: run listed tests at final SHA, then resolve the row-specific limitation.

| Code / bounded feature | Before → after | Implementation / integration / verification / visible state | Row-specific limitation / next acceptance |
|---|---|---|---|
| I01 Novel-to-screenplay conversion | Screenplay service/create/export existed. → Source-traceable branch-safe screenplay and approved revision fork strengthened; current per-edit CAS/history changes require their final test receipt. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Deterministic structural conversion is not model-quality certification. |
| I02 Industry screenplay formats | Fountain/Markdown/DOCX exporters existed with semantic Fountain defects. → Forced character/action handling, frozen resource packages and font/build improvements added. | PARTIAL / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Target Final Draft/Word pagination/industry-layout acceptance still NOT_RUN. |
| I03 Screenplay scenes | Scene model/update existed. → Branch-aware authorization and version-safe approved screenplay fork added. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Full interactive reorder/edit acceptance pending. |
| I04 Shot records | Shot model/routes existed. → Structured shot data preserved across guarded screenplay revision/export. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Final UI source/order acceptance pending. |
| I05 Shot numbering | Deterministic numbering existed. → Numbering remains the source for storyboard/export/task provenance. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Complex interactive reorder acceptance pending. |
| I06 Framing/shot design | Shot metadata carried framing. → Existing editable shot fields retained; manual design flows into assets/export. | PARTIAL / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | No complete model-assisted shot-design engine. |
| I07 Camera movement | Camera metadata fields existed. → Existing manual motion fields feed prompt/task records. | PARTIAL / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | No camera-planning/physical feasibility engine. |
| I08 Screenplay dialogue conversion | Dialogue conversion/export existed. → Fountain character and multiline dialogue semantics corrected. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Target screenplay application import still NOT_RUN. |
| I09 Action descriptions | Scene/shot/storyboard action text existed. → Forced Fountain actions preserve text that resembles syntax/character lines. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Industry rendered layout acceptance remains separate. |

### J. Storyboard

- Requirement source: `AI-Novel-Studio-V1.0-Feature-Audit.md`, original code rows. Original full definitions unavailable; names below are descriptive reconstructions.
- Source: `app/services/screenplay_service.py`, `app/industry_export_formats.py`
- API: `Storyboard create/approve/update routes under /novels/{nid}/screenplays/{id}`
- Persistence: Persisted storyboard cards, approval and source scene/shot references
- UI/entry: `frontend/src/novel/ScreenplayPanel.tsx`
- Test inventory: `tests/test_phase8_storyboard.py`, `tests/test_screenplay_branch_revision.py`
- Evidence: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml
- Provider: None; deterministic local application
- Priority/dependencies: P1; D08, D10
- Next check for each row: run listed tests at final SHA, then resolve the row-specific limitation.

| Code / bounded feature | Before → after | Implementation / integration / verification / visible state | Row-specific limitation / next acceptance |
|---|---|---|---|
| J01 Storyboard cards/review | Create/edit/approve storyboard existed. → Branch-safe screenplay revision leaves approved asset references unchanged. | IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE | No generated storyboard image implication. |
| J02 Composition planning | Composition fields existed. → Manual composition records remain connected to storyboard/export. | PARTIAL / CONNECTED / NOT_RUN / AVAILABLE | No automatic composition engine or generated image quality verification. |
| J03 Visual descriptions | Descriptions and HTML/storyboard exports existed. → Descriptions retained with immutable resource snapshot export path. | IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE | Description text is not a rendered/generated visual. |
| J04 Visual continuity | Continuity fields/transition metadata existed. → Approved references can be looked up lexically with provenance. | PARTIAL / CONNECTED / NOT_RUN / EXPERIMENTAL | No trained visual-consistency validator; embedding/semantic inference absent. |

### K. Transitions

- Requirement source: `AI-Novel-Studio-V1.0-Feature-Audit.md`, original code rows. Original full definitions unavailable; names below are descriptive reconstructions.
- Source: `app/services/screenplay_service.py`
- API: `Transition create/edit/suggest routes`; `POST .../transitions/{id}/prompt`
- Persistence: Screenplay transition records, prompt history and freeze state
- UI/entry: `frontend/src/novel/ScreenplayPanel.tsx`, `frontend/src/novel/ScreenplayPipelinePanel.tsx`
- Test inventory: `tests/test_phase8_transitions.py`, `tests/test_phase1_video_runtime.py`
- Evidence: docs/delivery/dot-astra-rc-r2/media-work.md
- Provider: None; deterministic local application
- Priority/dependencies: P1/P2; D08, D11
- Next check for each row: run listed tests at final SHA, then resolve the row-specific limitation.

| Code / bounded feature | Before → after | Implementation / integration / verification / visible state | Row-specific limitation / next acceptance |
|---|---|---|---|
| K01 Transition suggestions | Deterministic suggestion/prompt service existed. → Existing rule-based suggestion retained with durable screenplay state. | PARTIAL / CONNECTED / NOT_RUN / EXPERIMENTAL | No integrated real-model transition reasoning acceptance. |
| K02 Scene transitions | Scene transition records existed. → Existing editable transitions flow into source-linked exports/tasks. | IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE | Manual transition records only; no cinematic quality guarantee. |
| K03 Shot transitions | Shot transition records existed. → Existing transition/task linkage retained. | IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE | Final interactive shot-transition acceptance pending. |
| K04 Temporal transitions | Temporal transition type existed. → Current manual temporal type/prompt remains available. | PARTIAL / CONNECTED / NOT_RUN / AVAILABLE | No temporal reasoning engine. |
| K05 Spatial transitions | Spatial transition type existed. → Current manual spatial type/prompt remains available. | PARTIAL / CONNECTED / NOT_RUN / AVAILABLE | No spatial planner or geometry-aware validation. |
| K06 Emotional transitions | Emotional type/reason fields existed. → Current manual rationale and prompt remain available. | PARTIAL / CONNECTED / NOT_RUN / AVAILABLE | No emotion model or quality-certified cinematic transition engine. |
| K07 Action match cuts | Keyword action matching/suggestion existed. → Current deterministic matcher retained. | PARTIAL / CONNECTED / NOT_RUN / EXPERIMENTAL | Model-assisted motion/action alignment unimplemented. |
| K08 Transition prompt workflow | Prompt history/freeze existed. → Durable prompts remain linked to scene/shot state and guarded motion submission. | PARTIAL / CONNECTED / NOT_RUN / AVAILABLE | Real transition model adapter/quality not verified; template generation is not model execution. |

### L. Images and visual memory

- Requirement source: `AI-Novel-Studio-V1.0-Feature-Audit.md`, original code rows. Original full definitions unavailable; names below are descriptive reconstructions.
- Source: `app/asset_providers.py`, `app/services/image_job_service.py`, `app/services/visual_memory_index.py`, `app/asset_lifecycle_api.py`
- API: `POST /vision/analyze`; `POST /images/generate`; `GET/POST /novels/{nid}/image-jobs`; `POST .../image-jobs/{id}/execute|cancel|retry|accept`; `GET/POST .../visual-references`; `GET .../visual-reference-search`
- Persistence: Image production queue scoped by project/actor/branch; approved assets and version-bound visual-reference index
- UI/entry: `frontend/src/novel/ImageGenerationPanel.tsx`, `frontend/src/novel/ImageQueuePanel.tsx`, `frontend/src/novel/VisionAnalysisPanel.tsx`, `frontend/src/novel/VisualReferencePanel.tsx`
- Test inventory: `tests/test_asset_provider_adapter.py`, `tests/test_r2_media_api.py`, `tests/test_r2_media_lifecycle.py`, `tests/test_asset_lifecycle_r2.py`
- Evidence: docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; docs/delivery/dot-astra-rc-r2/assets-tests.xml
- Provider: OpenAI-compatible Vision/image; configured Automatic1111/ComfyUI; real provider NOT_RUN
- Priority/dependencies: P2; D10
- Next check for each row: run listed tests at final SHA, then resolve the row-specific limitation.

| Code / bounded feature | Before → after | Implementation / integration / verification / visible state | Row-specific limitation / next acceptance |
|---|---|---|---|
| L01 Vision adapter | Compatible Vision adapter existed. → Current adapter and analysis entry retained; no real model run. | PARTIAL / CONNECTED / MOCK_ONLY / NOT_CONFIGURED | Authorized configured vision model and output-quality/security acceptance required. |
| L02 Image understanding | Image-URL analysis panel existed. → Existing actual request path retained; results can inform reviewed references. | PARTIAL / CONNECTED / MOCK_ONLY / NOT_CONFIGURED | Real image-understanding quality and supported URL/vendor formats NOT_RUN. |
| L03 Character visual understanding | Character-linked analysis/memory existed. → Reviewed CHARACTER reference metadata has exact asset provenance and lexical lookup. | PARTIAL / CONNECTED / MOCK_ONLY / NOT_CONFIGURED | No trained identity-consistency/embedding engine; real vision quality NOT_RUN. |
| L04 Scene visual understanding | Scene-linked analysis/memory existed. → SCENE/LOCATION references can be approved and retrieved lexically. | PARTIAL / CONNECTED / MOCK_ONLY / NOT_CONFIGURED | No scene-semantic similarity or geometry reasoning engine. |
| L05 Image generation/review | Direct request/history could lose inline image bytes and status. → Durable parameterized queue, cancel/retry/recover, comparison, decoded image verification and explicit accept-to-library. | IMPLEMENTED / CONNECTED / MOCK_ONLY / NOT_CONFIGURED | Real providers NOT_RUN; local cancel discards late results without guaranteeing upstream cancellation. |
| L06 Character image generation | Generic character-linked generation existed. → Generic image queue and reviewed character reference assets available. | PARTIAL / CONNECTED / MOCK_ONLY / NOT_CONFIGURED | Dedicated character templates/consistency control and real-model validation incomplete. |
| L07 Scene image generation | Generic scene-linked generation existed. → Generic parameterized queue and approved scene references available. | PARTIAL / CONNECTED / MOCK_ONLY / NOT_CONFIGURED | Dedicated scene-generation/continuity workflow incomplete. |
| L08 Cover creation workflow | No dedicated cover workflow found. → Generic image prompts can request a cover but no dedicated cover product was added. | MISSING / DISCONNECTED / NOT_RUN / UNAVAILABLE | Need composition/title-safe-area/typography/review/export workflow; generic prompt is not completion. Entry: No dedicated implemented workflow API: No dedicated callable product workflow Evidence:  |
| L09 Storyboard image generation | Storyboard visual cards lacked image generation. → Image queue exists independently; storyboard assets may be manually linked. | MISSING / DISCONNECTED / NOT_RUN / UNAVAILABLE | Need storyboard-specific image generation and versioned card acceptance/association. Entry: No dedicated implemented workflow API: No dedicated callable product workflow Evidence:  |
| L10 Visual memory retrieval | Visual memory records lacked a real index. → Approved version/digest-bound Unicode lexical/metadata index rebuilds safely and returns provenance. | PARTIAL / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL | No embeddings, visual semantic search or inference; full-scale performance not benchmarked. Provider: Deterministic LEXICAL_METADATA; embeddings_available=false; inference_performed=false |

### M. Asset library

- Requirement source: `AI-Novel-Studio-V1.0-Feature-Audit.md`, original code rows. Original full definitions unavailable; names below are descriptive reconstructions.
- Source: `app/services/asset_library_service.py`, `app/asset_lifecycle_api.py`, `app/services/export_resource_snapshot.py`
- API: `GET/POST /novels/{nid}/assets`; `GET/DELETE /assets/{asset_id} (owned project/branch query required in collaboration)`; `GET .../asset-trash`; `POST .../assets/{id}/restore`; `GET .../assets/{id}/references`
- Persistence: Verified owned binary assets plus atomic metadata; recoverable tombstones; derivative lineage; frozen export resources
- UI/entry: `frontend/src/novel/AssetLibraryPanel.tsx`, `frontend/src/novel/AssetInspector.tsx`
- Test inventory: `tests/test_asset_lifecycle_r2.py`, `tests/test_asset_safety.py`, `tests/test_export_resource_packages.py`
- Evidence: docs/delivery/dot-astra-rc-r2/assets-tests.xml; docs/delivery/dot-astra-rc-r2/assets-work.md
- Provider: None; deterministic local application
- Priority/dependencies: P1/P2; D09, D10, D11, D12
- Next check for each row: run listed tests at final SHA, then resolve the row-specific limitation.

| Code / bounded feature | Before → after | Implementation / integration / verification / visible state | Row-specific limitation / next acceptance |
|---|---|---|---|
| M01 Asset library | Asset service/API/UI existed. → Digest/size/id/path checks, atomic publication, restore/recycle bin and permission-aware reads strengthened. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Whole-product reference scanning and archive reimport incomplete. |
| M02 Image asset storage | Generic storage accepted image MIME. → Accepted generated images must decode; generic upload preserves opaque-byte contract and honest preview errors. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Declared MIME on generic upload alone does not prove decoding. Existing ImageInfiniteCanvas retains zoom/pan/select/drag/align/group/layer/lock/undo; no raster editing or semantic inference claim. |
| M03 Audio asset storage | Generic audio MIME storage existed. → TTS ingress now validates real audio bytes/duration before creating owned asset. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Opaque manual-upload semantics differ; provider playback on target Windows still unrun. |
| M04 Video asset storage | Generic video MIME storage existed. → Generated download ingress uses pinned-network policy plus ffprobe/ffmpeg decode. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | ffmpeg licensing/bundling and native playback pending; generic uploads retain opaque contract. |
| M05 Project ownership | Novel ownership existed. → Project/branch provenance, ID validation and current membership checks guard new asset paths. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Legacy unbound records are not auto-adopted into a branch; final cross-user UI acceptance pending. |
| M06 Character associations | Association metadata could reference characters. → Reviewed CHARACTER references and guarded lineage metadata are persisted and searchable. | PARTIAL / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Manual entity-ID entry; universal typed foreign keys/bulk relation UI incomplete. |
| M07 Scene associations | Scene/screenplay asset tasks existed. → Source tasks, scene/shot references, digest/version lineage and video assembly provenance retained. | PARTIAL / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Universal scene relation constraints and full dependency/reimport handling incomplete. |

### N. Video production

- Requirement source: `AI-Novel-Studio-V1.0-Feature-Audit.md`, original code rows. Original full definitions unavailable; names below are descriptive reconstructions.
- Source: `app/services/screenplay_service.py`, `app/services/video_assembly_service.py`, `app/media_files.py`, `app/media_frames.py`, `app/video_assembly_api.py`
- API: `Motion Task submit/poll/cancel/retry/frame/privacy routes`; `GET/POST /novels/{nid}/screenplays/{id}/video-assemblies`
- Persistence: Branch-shared screenplay/motion state; verified assets; persisted clip/source/digest manifests
- UI/entry: `frontend/src/novel/VideoTaskInspector.tsx`, `frontend/src/novel/MotionPrivacyPanel.tsx`, `frontend/src/novel/VideoAssemblyPanel.tsx`
- Test inventory: `tests/test_phase1_video_runtime.py`, `tests/test_r2_media_lifecycle.py`, `tests/test_r2_media_api.py`
- Evidence: docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml
- Provider: Configured HTTP video adapter; ffmpeg/ffprobe for local validation/assembly; model NOT_RUN
- Priority/dependencies: P2; D11
- Next check for each row: run listed tests at final SHA, then resolve the row-specific limitation.

| Code / bounded feature | Before → after | Implementation / integration / verification / visible state | Row-specific limitation / next acceptance |
|---|---|---|---|
| N01 Shot-to-asset task pipeline | Screenplay shot/asset tasks existed. → Late-result fencing, actual owned frame validation and decoded file import strengthen pipeline. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Real generated-video quality/provider integration remains N06 gap. |
| N02 Storyboard-to-video assembly | Storyboard approval could produce tasks but no finished cut. → Author orders/trims owned clips; real bounded silent 640x360/24fps MP4 review rendition plus manifest. | PARTIAL / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL | Not final-master production; no soundtrack/compositor/automatic storyboard rendering. |
| N03 Motion prompt/task handoff | Motion prompt and task endpoints existed. → Exact prompt/provider/model-bound privacy review plus guarded task submission. | PARTIAL / CONNECTED / MOCK_ONLY / NOT_CONFIGURED | Real generation NOT_RUN; deterministic prompt is not proof of video model quality. |
| N04 Start-frame handling | Start-frame storage/history existed. → Local frame resolves owned current asset/shot/storyboard bytes with image decode and digest/version. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Opaque external frame URLs have content_verified=false; real provider use NOT_RUN. |
| N05 End-frame handling | End-frame storage/history existed. → Same actual frame validation/privacy and active-task freeze as start frame. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | External URL/frame interpretation and target model support unverified. |
| N06 Video provider execution | HTTP submit/poll/callback path existed. → Submission fencing, shared-secret callback task/key/replay checks, strict downloads, real decode and asset import. | PARTIAL / CONNECTED / MOCK_ONLY / NOT_CONFIGURED | Real provider NOT_RUN; shared-secret is not per-vendor asymmetric signature; codecs not bundled Windows. |

### O. Speech and audiobook

- Requirement source: `AI-Novel-Studio-V1.0-Feature-Audit.md`, original code rows. Original full definitions unavailable; names below are descriptive reconstructions.
- Source: `app/audio_providers.py`, `app/audio_production_store.py`, `app/services/audiobook_service.py`, `app/media_files.py`
- API: `POST /speech/synthesize`; `GET /novels/{nid}/audiobook/jobs`; `POST .../audiobook/chapters/{id}/queue`; `POST .../audiobook/jobs/{id}/execute|cancel|retry`; `POST .../audiobook/chapters/{id}/queue-segments`; `POST .../audiobook/chapters/{id}/export`
- Persistence: Actor/branch-bound voice bindings, pronunciation dictionary, immutable text snapshots, jobs and audio assets
- UI/entry: `frontend/src/novel/AudioGenerationPanel.tsx`, `frontend/src/novel/AudioTaskInspector.tsx`, `frontend/src/novel/AudiobookManifestPanel.tsx`
- Test inventory: `tests/test_audio_providers.py`, `tests/test_r2_media_lifecycle.py`, `tests/test_r2_media_api.py`
- Evidence: docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml
- Provider: OpenAI-compatible TTS; real provider NOT_RUN; PCM WAV local assembly
- Priority/dependencies: P2; D12
- Next check for each row: run listed tests at final SHA, then resolve the row-specific limitation.

| Code / bounded feature | Before → after | Implementation / integration / verification / visible state | Row-specific limitation / next acceptance |
|---|---|---|---|
| O01 TTS execution | Compatible speech API existed but success could depend on URL-only response. → Real binary/URL audio validation, usage/error/cancel fencing, verified owned audio asset and preview. | IMPLEMENTED / CONNECTED / MOCK_ONLY / NOT_CONFIGURED | No real TTS/model quality; async-only providers without poll adapter unavailable. |
| O02 Character voice profiles | Voice bindings/history already existed. → Durable bindings, pronunciation and authorization notes captured into jobs/manifests. | IMPLEMENTED / CONNECTED / MOCK_ONLY / NOT_CONFIGURED | No multi-speaker automatic dialogue detection; actual authorized voice verification required. |
| O03 Audiobook chapters | Chapter manifests/queues existed in later baseline, despite historical TODO. → Immutable reviewed text, ordered sentence queues, retry/recovery, verified audio and PCM WAV concatenate/export. | PARTIAL / CONNECTED / MOCK_ONLY / NOT_CONFIGURED | Mixed codec/sample-rate mastering, automatic multi-character detection and aligned subtitles incomplete. |
| O04 Emotion narration | No complete emotion narration engine found. → Neutral supported contract and explicit rejection of unsupported emotions replace fake spoken emotion tags. | PARTIAL / CONNECTED / CONTRACT_VERIFIED / UNAVAILABLE | No supported expressive/emotion provider mapping verified; rejecting unsupported input is not emotion synthesis. Only unsupported-emotion rejection and neutral mapping are contract verified; expressive narration itself NOT_RUN/unavailable. |

### P. Plugins

- Requirement source: `AI-Novel-Studio-V1.0-Feature-Audit.md`, original code rows. Original full definitions unavailable; names below are descriptive reconstructions.
- Source: `app/plugin_contracts.py`, `app/plugin_package_manager.py`, `app/plugin_management_api.py`, `app/plugin_runtime_contracts.py`
- API: `GET /plugins`; `GET /plugins/runtime-status`; `Plugin package install/update/rollback/remove routes`
- Persistence: Host-local declarative JSON packages; validated resource checksums; previous-version/recoverable archives; reviewed permissions
- UI/entry: `frontend/src/novel/PluginManagerPanel.tsx`, `frontend/src/novel/PluginInspector.tsx`
- Test inventory: `tests/test_r2_plugin_packages.py`, `tests/test_plugin_contract_v1.py`, `tests/test_plugin_discovery_security.py`
- Evidence: docs/delivery/dot-astra-rc-r2/runtime-work.md
- Provider: None; deterministic local application
- Priority/dependencies: P2; D15
- Next check for each row: run listed tests at final SHA, then resolve the row-specific limitation.

| Code / bounded feature | Before → after | Implementation / integration / verification / visible state | Row-specific limitation / next acceptance |
|---|---|---|---|
| P01 Plugin execution/runtime | Manifest surface existed; PR26 was an unverified sandbox prototype. → Declarative packages manageable; executable runtime remains execution_supported=false, DENY_ALL. | PARTIAL / DISCONNECTED / NOT_RUN / UNAVAILABLE | Trusted broker/OS vault mediation/native AppContainer denial and cleanup not implemented/verified as full execution. Provider: Third-party execution DENY_ALL; PR #26 prototype separately assessed |
| P02 Plugin manifest | Manifest validation already existed. → Bundle integrity, strict manifest/resource allowlists and size/path/symlink checks added. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Manifest validity does not authorize code execution or package trust. |
| P03 Plugin API surface | Catalog/permission endpoints existed. → Declarative resource lifecycle is exposed with local authority checks. | PARTIAL / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL | No broad executable extension SDK/broker; packaged/collaboration package writes blocked without Host-admin authority. |
| P04 Plugin permissions | Permission/authorization service existed. → Package changes reset grants; rollback cannot restore implicit trust; current actor checks retained. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Executable permission enforcement cannot be claimed while runtime disabled. |
| P05 Plugin lifecycle management | Enable/disable/list existed without full lifecycle UI. → Host-local declarative install/update/rollback/recoverable remove with integrity checks and UI. | PARTIAL / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL | No marketplace, signed executable distribution or packaged Host-admin write authority. |

### Q. Workflow

- Requirement source: `AI-Novel-Studio-V1.0-Feature-Audit.md`, original code rows. Original full definitions unavailable; names below are descriptive reconstructions.
- Source: `app/workflow.py`, `app/workflow_api.py`, `app/workflow_recipes.py`, `app/services/v1_capability_service.py`
- API: `GET/POST /workflows`; `POST /workflows/{workflow_id}/runs`; `Run approval/reject/pause/resume/cancel/retry and Agent dispatch routes`
- Persistence: Scoped durable definitions/run snapshots/outputs/reviews; bounded DAG and persisted Agent jobs
- UI/entry: `frontend/src/novel/WorkflowPanel.tsx`, `frontend/src/novel/WorkflowInspector.tsx`, `frontend/src/novel/AgentQueuePanel.tsx`
- Test inventory: `tests/test_workflow.py`, `tests/test_r2_workflow_execution.py`
- Evidence: docs/delivery/dot-astra-rc-r2/runtime-work.md
- Provider: Local rule recipes; explicit selected-model Agent executor; no real provider test
- Priority/dependencies: P2; D13
- Next check for each row: run listed tests at final SHA, then resolve the row-specific limitation.

| Code / bounded feature | Before → after | Implementation / integration / verification / visible state | Row-specific limitation / next acceptance |
|---|---|---|---|
| Q01 Workflow engine | Workflow/DAG definitions and runs existed. → Bounded durable snapshots, cycle rejection, actual Agent completion gating, cancellation/rejection and scope guards. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Single Host process; distributed leases/multi-process transactional scheduling not claimed. |
| Q02 Novel-to-film recipe | Release-gate/workflow primitives existed. → Three bounded local transformations save reviewed candidates, supplied draft and shot/task proposals. | PARTIAL / CONNECTED / CONTRACT_VERIFIED / EXPERIMENTAL | No end-to-end novel-to-film production/apply pipeline; proposals do not start media generation. |
| Q03 Custom workflows | Definition/create/run APIs and UI existed. → Persisted input/results, human approval/reject, pause/resume/cancel/retry available. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Core local DAG contracts verified; full desktop long-running recovery pending. |
| Q04 Agent workflow nodes | Agent nodes could be marked successful before actual work. → Selected-model dispatch persists real Agent jobs and synchronizes actual completion with approval. | PARTIAL / CONNECTED / CONTRACT_VERIFIED / NOT_CONFIGURED | Model calls MOCK_ONLY; domain-specific multi-agent recipes and atomic crash-gap recovery incomplete. |

### R. Credentials and provider selection

- Requirement source: `AI-Novel-Studio-V1.0-Feature-Audit.md`, original code rows. Original full definitions unavailable; names below are descriptive reconstructions.
- Source: `app/credential_vault.py`, `app/trusted_sessions.py`, `app/providers.py`, `app/native_text_providers.py`
- API: `Credential status/test/clear through trusted Host`; `GET /providers`; `GET /models`
- Persistence: One credential entry per provider in Windows Credential Manager/keyring; opaque trusted sessions
- UI/entry: `frontend/src/novel/DeepSeekCredentialControl.tsx`, `frontend/src/ui/ModelCenter.tsx`
- Test inventory: `tests/test_credential_vault.py`, `tests/test_credential_provider_lifecycle.py`, `tests/test_r2_native_text_providers.py`
- Evidence: docs/delivery/dot-astra-rc-r2/runtime-work.md
- Provider: Windows Credential Manager/keyring; memory backend only for isolated tests
- Priority/dependencies: P0; D04
- Next check for each row: run listed tests at final SHA, then resolve the row-specific limitation.

| Code / bounded feature | Before → after | Implementation / integration / verification / visible state | Row-specific limitation / next acceptance |
|---|---|---|---|
| R01 Session credentials | Trusted sessions/vault already existed. → Existing Host boundary retained; no persistent browser secret storage added. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Real Host handoff/native session lifecycle still NOT_RUN. |
| R02 Persistent provider secrets | Historical audit said TODO, but inspected baseline already has WindowsBackend/keyring persistence. → Existing durable OS vault reused; production avoids environment-only configured claims. | IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE | No current OS-store integration run; memory test backend is not durable proof. Actual OS vault code inspected; native Windows persistence/desktop integration not run by this inventory. Contract test path is not native verification. |
| R03 Windows Credential Manager | Actual CredWriteW/CredReadW/CredDeleteW implementation already present. → Reuse actual OS integration instead of replacing with a new secret store. | IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE | Native Windows credential persistence/revocation and desktop UI end-to-end NOT_RUN. Actual OS vault code inspected; native Windows persistence/desktop integration not run by this inventory. Contract test path is not native verification. |
| R04 Multiple key/profile management | One vault slot per provider; no multi-profile model found. → Still one provider-key identity; no named profile CRUD/selection implemented. | MISSING / DISCONNECTED / NOT_RUN / UNAVAILABLE | Need bounded profile identity/scope/revocation/masked UI and authoritative runtime selection. Entry: No dedicated implemented workflow API: No dedicated callable product workflow Evidence:  |
| R05 Provider/model switching | Provider catalog and credential routes existed. → Explicit compatible/Claude/Gemini selection feeds current adapters; no guessed model IDs. | PARTIAL / CONNECTED / CONTRACT_VERIFIED / NOT_CONFIGURED | Automatic v2 compatibility/budget broker and multi-profile routing incomplete; real service switching NOT_RUN. |

### S. Collaboration and review

- Requirement source: `AI-Novel-Studio-V1.0-Feature-Audit.md`, original code rows. Original full definitions unavailable; names below are descriptive reconstructions.
- Source: `app/collaboration_api.py`, `app/services/membership_authorization_service.py`, `app/creation_workbench_api.py`, `app/services/creation_workbench_service.py`, `app/services/creation_workbench_service.py`, `app/creation_workbench_api.py`
- API: `Workspace/membership/storyline/branch routes`; `GET/POST /novels/{nid}/review-threads`; `POST .../review-threads/{id}/{reply|resolve|reopen}`
- Persistence: Existing workspace/user/branch identity repositories; chapter-version-anchored review_threads sidecar
- UI/entry: `frontend/src/WorkspaceManagement.tsx`, `frontend/src/novel/CreationWorkbenchPanel.tsx`
- Test inventory: `tests/test_r2_creation_workbench.py`, `tests/test_collaboration_scope.py`
- Evidence: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml
- Provider: None; deterministic local application
- Priority/dependencies: P1; D03, D14
- Next check for each row: run listed tests at final SHA, then resolve the row-specific limitation.

| Code / bounded feature | Before → after | Implementation / integration / verification / visible state | Row-specific limitation / next acceptance |
|---|---|---|---|
| S01 Workspaces/storylines/branches | Collaboration scope already existed. → New records/tasks reuse existing identity/scope with reauthorization and remount protection. | IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE | Different domain sharing semantics documented; final multi-user/browser acceptance pending. |
| S02 Membership and permissions | Server-side identity/membership authorization existed. → New workflow, plans, comments, media and export paths use trusted actor/current membership. | IMPLEMENTED / CONNECTED / NOT_RUN / AVAILABLE | Final permission-revocation end-to-end tests/Windows interaction pending. |
| S03 Comment/review threads | No comments/review threads found in audit. → Persistent chapter-version/quote/hash anchor; trusted actor, reply/resolve/reopen/history and stale-anchor UI. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Anchors flag changed/missing source rather than automatically remapping; final browser gate pending. Evidence: docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.txt; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md |
| S04 Unified approvals | Import/Agent/release approvals were separate. → Comments/review panel adds durable audit; creation approval and import journals preserve explicit review. | PARTIAL / CONNECTED / NOT_RUN / EXPERIMENTAL | No unified inbox aggregating import/Agent/Canon/media approvals; separate domain queues remain. |

### T. Exports

- Requirement source: `AI-Novel-Studio-V1.0-Feature-Audit.md`, original code rows. Original full definitions unavailable; names below are descriptive reconstructions.
- Source: `app/export_formats.py`, `app/pdf_export.py`, `app/industry_export_formats.py`, `app/services/export_job_service.py`, `app/services/export_resource_snapshot.py`
- API: `GET/POST /exports`; `GET /exports/{id}`; `GET /exports/{id}/download`; `POST /exports/{id}/retry|cancel`
- Persistence: export_jobs.json; immutable content/source/resource snapshots; owned result artifacts; context-bound reauthorization
- UI/entry: `frontend/src/novel/ExportPanel.tsx`
- Test inventory: `tests/test_export_jobs.py`, `tests/test_export_history_recovery.py`, `tests/test_export_resource_packages.py`, `tests/test_docx_export.py`, `tests/test_pdf_export.py`, `tests/test_r2_pdf_font.py`
- Evidence: docs/delivery/dot-astra-rc-r2/evidence/pdf-fonts.txt; docs/delivery/dot-astra-rc-r2/evidence/font-manifest.json; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json
- Provider: None; deterministic local application
- Priority/dependencies: P0/P1; D02, D09
- Next check for each row: run listed tests at final SHA, then resolve the row-specific limitation.

| Code / bounded feature | Before → after | Implementation / integration / verification / visible state | Row-specific limitation / next acceptance |
|---|---|---|---|
| T01 TXT export | TXT exporter/queue existed; history UI could not rediscover jobs. → Scope-bound server history/filter/reopen plus immutable snapshot/download/retry. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Final business browser recovery and target Windows download acceptance pending. |
| T02 Markdown export | Markdown exporter existed. → Same durable scoped history/snapshot/reauthorization as TXT. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Final exact-SHA format and browser regression pending. |
| T03 DOCX export | DOCX output and structure tests existed. → Retained DOCX and added frozen screenplay-resource packaging. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Word/LibreOffice rendered pagination and target font behavior remain unrun. |
| T04 PDF export | PDF export existed; strict CJK embedding gate incomplete. → Pinned OFL Noto CJK preparation, licensed manifest and actual embedded PDF validation/render evidence. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Font download/build gate required; Windows font/runtime acceptance and broad typography still NOT_RUN. Actual pinned-font PDF binary/embed/render evidence; not target Windows print/layout or real provider verification. |
| T05 EPUB export | EPUB exporter existed. → Retained immutable export snapshots and discoverable job history. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | External EPUB validator/reader compatibility and accessibility audit not newly claimed. |
| T06 Screenplay export | Fountain/Markdown/DOCX existed with mixed-name/action/multiline defects. → Structural Fountain fixes; screenplay ZIP with immutable resource bytes enters queue/API/UI. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Complete fountain-js 1.2.4 parser tests passed at the focused checkpoint; target Final Draft/industry layout and final exact-SHA rerun remain separate. |
| T07 Shot/storyboard exports | CSV/storyboard/HTML output existed. → Shot/storyboard resource ZIPs, source versions, exact byte digests and history/recovery connected. | IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED / AVAILABLE | Archive reimport not added; target NLE/industry interoperability NOT_RUN. |

## Concrete remaining engineering gaps

### GAP-01 (D04)

- Location: `app/credential_vault.py CredentialVault/provider key identity`
- Gap: One key slot per provider; multiple profile selection/rotation and authoritative v2 execution broker remain absent.
- Next: Define profile scope and masked UI/host policy; test revocation and route selection without broadening cloud authority.

### GAP-02 (D05, D07)

- Location: `app/services/creation_workbench_service.py WorkbenchRecordIn/generation_inputs`
- Gap: Manual and bounded selected-model proposals are useful; approved STYLE/PLOT feed author generation. Reviewed other kinds still do not become semantic Canon/checker engines.
- Next: Add narrow reviewed adapters to existing domain registries and structured AI outline acceptance before claiming intelligence.

### GAP-03 (D06)

- Location: `app/knowledge_extraction.py extract_knowledge_candidates`
- Gap: Four-group heuristics plus separate explicit-marker rule/plot drafts now exist. No proven natural-language fact extraction/long-book identity resolution; complete six markers are required for local plot extraction.
- Next: Evaluate bounded model proposals on controlled quality fixtures; decide explicit reviewed adapters to existing world-rule/Canon registries without broadening permissions.

### GAP-04 (D10)

- Location: `app/services/visual_memory_index.py; app/services/image_job_service.py`
- Gap: Lexical metadata index only; dedicated cover/storyboard generation and semantic consistency incomplete. Existing canvas manipulation is retained, not missing.
- Next: Implement per-card/cover source-version review workflows first; add optional embeddings only with a real installed/authorized model.

### GAP-05 (D10, D09)

- Location: `app/services/asset_library_service.py references; app/services/export_resource_snapshot.py`
- Gap: References scan is not universal; no archive reimport/full bulk association manager.
- Next: Define safe reviewed reimport IDs/ownership and extend per-module reference adapters; never silently cascade-delete.

### GAP-06 (D11, D18)

- Location: `app/services/video_assembly_service.py; scripts/build_windows_application.ps1`
- Gap: Output is silent low-resolution review cut; codec binaries/license distribution and final master/audio mixing unavailable.
- Next: Make supported Windows codec installation/package provenance explicit; separately build bounded audio mux/master profiles if authorized scope requires.

### GAP-07 (D12)

- Location: `app/services/audiobook_service.py; app/audio_providers.py`
- Gap: No expressive emotion mapping, automated speaker attribution, cross-codec mix or phoneme-aligned timing.
- Next: Expose each supported provider capability accurately and add actual model/codec fixtures; keep estimated subtitle labels.

### GAP-08 (D13)

- Location: `app/workflow_recipes.py execute_local_recipe_node; app/workflow_api.py`
- Gap: Real Agent dispatch exists, but local recipes stop at reviewed artifacts; no autonomous domain apply or transactional distributed scheduler.
- Next: Connect one bounded reviewed artifact to existing Draft/Canon/media approval APIs with explicit approval and restart-safe idempotency.

### GAP-09 (D14)

- Location: `frontend/src/novel/CreationWorkbenchPanel.tsx; app/creation_workbench_api.py`
- Gap: Comments are complete bounded feature; approvals remain split across domains.
- Next: Add read-only aggregation of existing authorized pending queues before adding cross-domain action controls.

### GAP-10 (D15)

- Location: `app/plugin_runtime_contracts.py; app/plugin_management_api.py`
- Gap: Executable plugins deliberately unavailable; local declarative lifecycle does not close sandbox/broker/Host-admin authority.
- Next: Keep DENY_ALL until real Windows identity, filesystem/network/process denial, cleanup, trust and credential-broker evidence exists.

### GAP-11 (D17, D18)

- Location: `frontend/tests/e2e/r2-business.spec.ts; .github/workflows/cloud-ci.yml`
- Gap: Local Chromium cannot launch; expanded full browser Draft/Diff/Accept/restore/conflict script now exists but hosted execution remains pending. IME and interactive Windows installer evidence are still missing.
- Next: Run the expanded hosted browser business test at exact final SHA; verify real UI Draft/Diff/Accept/restore/conflict, then manually run remaining IME/native installation checks in an authorized desktop session.

## Final owner update checklist

1. Freeze integration, run final tests, record exact branch-head and any PR merge checkout separately. Replace pending test-revision fields without claiming worker checkpoints ran at that later SHA.
2. Attach final File/real-PostgreSQL/frontend/browser/hosted-Windows receipts and upgrade only the capability/layer each result actually proves.
3. Keep real Provider, local GPU, interactive Windows/WebView2/installer and user acceptance NOT_RUN until each has its own authorized actual evidence.
4. Recheck concrete gaps against final source. Do not turn local CRUD, rule recipes, callback secrets or synthetic media into semantic AI, autonomous production, vendor signatures or native deployment claims.
5. Keep Draft PR; no automatic merge, public release or production deployment.

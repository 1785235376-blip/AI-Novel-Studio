# Frozen capability continuation ledger — 2026-10-16

This is a current-source dependency ledger, not full product acceptance. Baseline source is local `69162fdc75328291f5b944de172bd8b69be29a4f`, tree `124ec1705e064732eab969f60d4387c6d8309454`, identical to published PR48 `58bbaad11360330d51f49fc2bb78a955a26469f0`. PR47 remains Draft at `045b865e5a003cac3333462d055f22099f6368d6`; main remains untouched. Read-only GitHub verification: 2026-10-16.

The frozen user anchor is [archived verbatim](frozen-product-anchor-20261016.txt), SHA256 `ebabfe5314d9ed4535814baaca295ec6db0f17e5541d4dc35a6ed16805c129f4`. It specifies goals, not completion. The original referenced 904-line Master Roadmap was not located/read; this ledger uses its existing versioned matrix trace and does not claim exhaustive original-roadmap reconciliation.

Status axes: IMPLEMENTED = bounded source exists; PARTIAL = broader feature remains incomplete; MISSING = named inspected seam absent; BLOCKED = explicit gate; LOCAL_REQUIRED = target machine/model acceptance; NOT_RUN = not exercised here. Historical tests below are source references, not rerun claims. P0 lifecycle repair/reproduction is platform-BLOCKED and untouched; release remains HOLD. No paid API, GPU, hosted CI, push, merge, tag or release was performed.

## Current slice delta (not a rewrite of the baseline rows)

- A01 now has a bounded [exact simulator → original planning review handoff](simulator-planning-handoff-20261016.md): persistently saved route IDs reopen the exact original proposal, original CAS review/history is reused, and explicit return reads saved run constraints/source digests. Missing/denied/stale/ABA cases preserve original boundaries; no new store/API/model execution. A05 original character-context writing binding was audited and retained. Post-approval target changes may make original run evidence STALE; historical replay and real model/literary quality remain open. P0 BLOCKED, R3-GATE HOLD, Prompt Adoption disabled; no push/hosted CI.

- Independent asset → TIMELINE now has a bounded [exact-reference handoff](asset-timeline-handoff-20261016.md): actual AssetBrowser callback, original dirty navigation, explicit metadata preview and re-read, compatible unlocked-track acceptance through original timeline history/save/reopen. Stale/identity/target-generation/UNKNOWN/budget guards remain; no automatic save/render/download. IMAGE/VIDEO/STORYBOARD handoffs remain open. Unified DeliveryCenter items/entitlements wiring is BLOCKED by the absence of an authoritative grant producer; manual_export capability is not substituted for permission. Original raw asset download and delivery default-deny behavior are unchanged.

- CONSOLE-02/05 and U06 now include a bounded [Director source-impact preview](director-source-impact-20261016.md): explicit original export/history/list reads, per-historical-snapshot canonical digest receipts, exact pinned/current field differences or metadata-only fallback, loaded-graph structural downstream pins and currently readable storyboard references. Stale derived documents remain gated/excluded; the UI states that zero readable references is not zero impact. No rebind/overwrite/model/write action was added. 274 targeted mocked UI/geometry, four nonsecurity File and 30 PUBLIC checks pass; full impact inventory and browser/model acceptance remain open.

- CONSOLE-01/03, CORE-06: `GraphDirectorConsole.tsx` is now mounted through the original graph workspace. It edits/saves original Creative Director documents with existing `CreativeCanvas` fields, opens exact version/digest source receipts from selected Director nodes, and uses existing graph persistence/typed ports.
- CONSOLE-02/05 remain PARTIAL: the [director→storyboard handoff](director-storyboard-handoff-20261016.md) now explicitly previews a saved version/digest, calls the existing DIRECTOR_NOTES derivation owner to create a separate Shot draft, and reopens original document status. It does not approve proposals/assets, dispatch models or tasks, or rebind graphs. Multi-target model-proposal/approval/task-status coordination remains open.
- Source updates preserve graph pins and display changed-source impact; original backend preflight remains authoritative. UNKNOWN saves lock writes and support directory-based read reconciliation or explicitly acknowledged local abandonment. Unsaved text is session-local, with existing unload/navigation warnings; crash-proof draft recovery is not claimed.
- GRAPH-10 now has a bounded display-only viewport-culling slice: derived geometry projection, retained interaction anchors and synthetic 1000/10000-display-object measurement. See [current culling report](canvas-display-culling-20261016.md). Full LOD/virtualization, persistent visual grouping and browser performance acceptance remain open; execution-budget/coordinate/zoom bounds are unchanged.
- GRAPH-06/08 correction: saved viewport and positions already belonged to original Graph CAS definitions. The new [layout-apply slice](canvas-layout-apply-20261016.md) wires explicit preview → live-draft apply → original undo/save/reopen, preserving pins and camera; no second store or new persistence contract. Unsaved crash recovery and independent grouping presentation remain open.
- GRAPH-06/07 now includes a mounted bounded [MiniMap navigation slice](canvas-minimap-navigation-20261016.md): all display-card bounds, current viewport and selection, click/keyboard camera navigation through original history/save, and transient hide control. Read-only/busy camera restrictions and execution/zoom/coordinate bounds are unchanged. Browser visual/accessibility/performance acceptance remains NOT_RUN.
- GRAPH-08 now includes [selected alignment preview/apply](canvas-selected-alignment-20261016.md): left, horizontal-center, top and horizontal equal-spacing distribution through original history/save, with stale-selection/owner guards and unchanged camera/pins/edges. At that slice snap/grid and grouping remained open; 194 mocked UI/geometry tests are bounded evidence, not browser acceptance.
- GRAPH-02/06/07 now includes [world-grid and group snapping](canvas-grid-snapping-20261016.md): explicit transient grid/snap/step controls, grabbed-anchor snapping with offset-preserving bounded group movement, original one-step undo/save/reopen and unchanged keyboard nudge contract. Settings are session-only because existing preferences have no grid fields; persisted settings/grouping remain open. 203 targeted mocked UI/geometry tests, 1 File owner test and 30 PUBLIC contracts pass; browser/native input acceptance remains NOT_RUN.
- GRAPH-08 now includes a bounded [graph-level annotation](canvas-annotation-20261016.md): optional original-owner presentation.comment, strict backwards-compatible serialization and transport, mounted edit/remove → original undo/save/reopen. Legacy definition digests and execution projection remain unchanged when absent. Named grouping/collapse/nested subgraphs and spatial/per-node comments remain MISSING; this is not group completion. 268 selected UI/transport/geometry, 11 pure backend, 4 File and 30 PUBLIC tests pass; browser/target-platform acceptance remains NOT_RUN.
- GRAPH-06/08 now includes a bounded [persisted visual group panel](canvas-visual-groups-20261016.md): create from selected nodes, rename/remove without node deletion, select members and existing group drag, strict disjoint original-owner presentation.groups with undo/save/reopen and deletion cleanup. Comment-only/legacy canonical digests and execution budgets remain unchanged. Spatial outlines, collapse/nesting and browser acceptance remain open. 294 targeted UI, 32 pure backend, 3 File and 30 PUBLIC tests pass.
- GRAPH-06/08 now includes [world-space visual group outlines](canvas-group-outlines-20261016.md), derived from existing member card geometry with explicit label selection, viewport culling/focus retention and original drag/alignment previews. No new persistence/schema/execution owner; MiniMap stays node-based. 301 targeted UI tests, 32 pure backend, 3 File and 30 PUBLIC tests pass; 1000/10000-node offline display benchmark includes 24 bounded groups. Collapse/nesting and browser acceptance remain open.
- GRAPH-06/08 now includes [session-only group collapse](canvas-group-collapse-20261016.md): explicit compact cards, member/internal/external-edge counts and original endpoint details, hidden incident curves with expand-required real ports, protected interaction anchors and owner reset. No schema/save/dispatch/budget changes. 311 targeted UI/geometry and 65 schema/File/PUBLIC checks pass; browser acceptance remains NOT_RUN. Persistent folding, nested subcanvases and boundary-routing previews remain open.
- GRAPH-04/06 now includes [bounded graph-instance navigation](canvas-node-search-20261016.md): replaces the flat selector with label/type/ID search, 20-result pages, explicit keyboard selection/centering, IME cancellation/focus restoration and folded-member reveal through original history/save. Existing catalog creation search and global command palette remain separate original owners. 316 selected UI/geometry, one File and 30 PUBLIC tests pass; 1200-display-instance mocked DOM fixture is not browser performance acceptance. Full context-menu/global canvas commands remain open.
- Exact selected test/build results and boundaries are in [the slice report](canvas-director-integration-20261016.md). All full-product rows below remain PARTIAL unless their narrower state says otherwise.

## A/B/U source and dependency rows

### A01 — Bounded story simulation

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `app/experimental/story_simulator.py`; `app/experimental/story_simulator_model.py`; `frontend/src/experimental/StorySimulatorPanel.tsx`

- **API owner files:** `app/experimental/story_simulator_api.py`

- **Static mounted call sites:** `frontend/src/experimental/ExperimentalWorkbench.tsx:80`

- **Gap / next acceptance:** Deterministic kernel outcomes are not factual future probabilities. Real local model/GPU/literary quality NOT_RUN; exact model-task reopening has focused contract verification; final browser acceptance is pending. No automatic manuscript or Canon write.

### A02 — Style metrics and drift

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `app/experimental/style_analysis.py`; `app/experimental/style_analysis_model.py`; `frontend/src/experimental/StyleAnalysisPanel.tsx`; `frontend/src/experimental/StyleAnalysisModelPanel.tsx`

- **API owner files:** `app/experimental/style_analysis_api.py`

- **Static mounted call sites:** `frontend/src/experimental/ExperimentalWorkbench.tsx:77`; `frontend/src/experimental/StyleAnalysisPanel.tsx:111`

- **Gap / next acceptance:** Description/sensory semantic ratios and narrative distance/tone/rhythm/humor/imagery are not calibrated deterministic facts. Lexical POV cues are not full POV classification; actual model judgments/quality NOT_RUN.

### A03 — Evidence-based narrative judge

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `app/experimental/narrative_judge.py`; `app/experimental/narrative_judge_model.py`; `app/experimental/writer_room.py`; `frontend/src/experimental/NarrativeJudgePanel.tsx`; `frontend/src/experimental/NarrativeJudgeRevisionTaskPanel.tsx`

- **API owner files:** `app/experimental/narrative_judge_api.py`

- **Static mounted call sites:** `frontend/src/experimental/ExperimentalWorkbench.tsx:78`; `frontend/src/experimental/NarrativeJudgePanel.tsx:115`; `frontend/src/experimental/NarrativeJudgePanel.tsx:70`

- **Gap / next acceptance:** Model-derived advice remains separately labelled; model independence and literary quality are NOT_RUN. Task-center exact model-opinion reopening has focused contract verification; domain approval never automatically applies prose/Canon.

### A04 — Temporal semantic story graph

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `app/experimental/world.py`; `app/experimental/story_graph.py`; `app/experimental/story_graph_api.py`; `frontend/src/experimental/StoryGraphPanel.tsx`

- **API owner files:** `app/experimental/story_graph_api.py`; `app/experimental/world_api.py`

- **Static mounted call sites:** `frontend/src/experimental/ExperimentalWorkbench.tsx:74`

- **Gap / next acceptance:** Reviewed deterministic relations are not universal semantic inference. Uncertain/future/cross-parent scene states are excluded; absent branch manuscript authority remains unavailable.

### A05 — Character knowledge and mind state

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `app/experimental/story_graph.py`; `app/experimental/character_author_context.py`; `app/experimental/author_context_api.py`; `frontend/src/experimental/StoryGraphPanel.tsx`; `frontend/src/novel/AiWritingPanel.tsx`

- **API owner files:** `app/experimental/story_graph_api.py`

- **Static mounted call sites:** `frontend/src/experimental/ExperimentalWorkbench.tsx:74`; `frontend/src/App.tsx:1665`

- **Gap / next acceptance:** Only the supported original character-author operations are available; unrestricted character-selection rewriting and real literary/POV quality are not verified. Author-only research/graph additions cannot enter character-only mode.

### A06 — Explainable model broker

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `app/experimental/model_broker.py`; `app/experimental/model_broker_api.py`; `app/experimental/provider_profiles.py`; `app/model_center/service.py`; `frontend/src/experimental/ModelBrokerPanel.tsx`

- **API owner files:** `app/experimental/model_broker_api.py`

- **Static mounted call sites:** `frontend/src/experimental/ExperimentalWorkbench.tsx:75`

- **Gap / next acceptance:** Unknown quality is not ranked as measured quality; unknown cost/hardware stays unknown. Local-only feature coordinators do not become paid-cloud execution merely because broker candidate policy exists. Real billing/model performance NOT_RUN.

### A07 — Model benchmark and capability evidence

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `app/experimental/model_benchmark.py`; `app/experimental/model_benchmark_api.py`; `app/model_center/discovery.py`; `frontend/src/experimental/ModelBenchmarkPanel.tsx`

- **API owner files:** `app/experimental/model_benchmark_api.py`

- **Static mounted call sites:** `frontend/src/experimental/ModelBrokerPanel.tsx:137`

- **Gap / next acceptance:** Human review never manufactures quality scores, throughput, VRAM, memory or failure-rate measurements. Real GPU/quality benchmarks and unsupported video workflow admission remain NOT_RUN/adapter-bound.

### A08 — Camera grammar and scene direction

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `app/experimental/director.py`; `app/services/screenplay_service.py`; `frontend/src/experimental/DirectorPanel.tsx`; `frontend/src/novel/DirectorShotCard.tsx`

- **API owner files:** `app/experimental/director_api.py`

- **Static mounted call sites:** `frontend/src/experimental/ExperimentalWorkbench.tsx:95`; `frontend/src/novel/DirectorShotList.tsx:460`; `frontend/src/novel/MultimodalDirectorWorkspace.tsx:477`; `frontend/src/App.tsx:1891`

- **Gap / next acceptance:** Grammar checks use declared metadata, not visual proof of cinematic quality or the 180-degree rule. Manual review remains required; real generated motion/video/model quality NOT_RUN.

### A09 — Asset lineage and derived relationships

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `app/services/asset_library_service.py`; `app/experimental/production_lineage.py`; `app/experimental/media.py`; `frontend/src/experimental/ProductionLineagePanel.tsx`

- **API owner files:** `app/experimental/production_lineage_api.py`; `app/experimental/media_api.py`

- **Static mounted call sites:** `frontend/src/experimental/ExperimentalWorkbench.tsx:76`; `frontend/src/creative/IndependentStudioWorkspace.tsx:492`

- **Gap / next acceptance:** Only actually recorded dependency edges/hashes/licenses are known; missing historical provenance and legal judgments are not invented. Real visual embedding/provider quality remains separate.

### A10 — Layered research library

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `app/experimental/research_library.py`; `app/experimental/research_extract.py`; `app/experimental/embeddings.py`; `app/experimental/research_library_api.py`; `frontend/src/experimental/ResearchLibraryPanel.tsx`; `frontend/src/experimental/EmbeddingPanel.tsx`

- **API owner files:** `app/experimental/research_library_api.py`

- **Static mounted call sites:** `frontend/src/experimental/ExperimentalWorkbench.tsx:81`; `frontend/src/experimental/ExperimentalWorkbench.tsx:108`; `frontend/src/App.tsx:1897`

- **Gap / next acceptance:** Research remains LOCAL_ONLY and never automatically becomes Canon or character context. OCR/vision/image embedding are NOT_CONFIGURED; no keyword-as-vector fallback. Actual Ollama inference/semantic quality and broad public-web compatibility NOT_RUN; loopback transport tests use synthetic vectors.

### A11 — Revision intelligence and partial changes

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `app/experimental/revision_intelligence.py`; `app/experimental/revision_intelligence_model.py`; `app/experimental/revision_intelligence_api.py`; `frontend/src/experimental/RevisionIntelligencePanel.tsx`; `frontend/src/experimental/RevisionComparisonModelPanel.tsx`

- **API owner files:** `app/experimental/revision_intelligence_api.py`

- **Static mounted call sites:** `frontend/src/experimental/ExperimentalWorkbench.tsx:97`; `frontend/src/experimental/RevisionIntelligencePanel.tsx:218`

- **Gap / next acceptance:** Semantic interpretations are evidence-backed opinions, not automatic factual proof or edits. No branch-manuscript fallback. Real model quality NOT_RUN; original local partial-write authority only.

### A12 — OTIO and NLE exchange

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `app/experimental/timeline_exchange.py`; `app/industry_export_formats.py`; `frontend/src/experimental/TimelineExchangePanel.tsx`

- **API owner files:** `app/experimental/timeline_exchange_api.py`

- **Static mounted call sites:** `frontend/src/experimental/ExperimentalWorkbench.tsx:96`; `frontend/src/novel/DirectorShotList.tsx:347`

- **Gap / next acceptance:** Actual Resolve/Premiere/other NLE import/export acceptance remains NOT_RUN. Supported OTIO syntax is not universal target compatibility; media availability and unsupported metadata remain explicit.

### A13 — Production manifest and controlled replay

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `app/experimental/production_lineage.py`; `app/experimental/media.py`; `frontend/src/experimental/ProductionLineagePanel.tsx`

- **API owner files:** `app/experimental/production_lineage_api.py`; `app/experimental/media_api.py`

- **Static mounted call sites:** `frontend/src/experimental/ExperimentalWorkbench.tsx:76`

- **Gap / next acceptance:** Missing model hashes/environment/usage remain unknown; a seed never guarantees GPU byte identity. Cloud replay coordinator, real model reproducibility and hardware acceptance remain unimplemented/unverified.

### B01 — Declarative template library

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `app/experimental/template_library.py`; `app/experimental/declarative_agents.py`; `frontend/src/experimental/TemplateLibraryPanel.tsx`

- **API owner files:** `app/experimental/template_library_api.py`

- **Static mounted call sites:** `frontend/src/experimental/ExperimentalWorkbench.tsx:90`

- **Gap / next acceptance:** Most creative brief types are editable declarations rather than automatic manuscript/Canon construction. Marketplace, remote catalog sync and executable installation remain absent.

### B02 — Custom agents and workflow SDK

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `app/experimental/declarative_agents.py`; `app/experimental/declarative_model.py`; `app/experimental/declarative_adapter_sdk.py`; `frontend/src/experimental/DeclarativeAgentsPanel.tsx`

- **API owner files:** `app/experimental/declarative_agents_api.py`

- **Static mounted call sites:** `frontend/src/experimental/ExperimentalWorkbench.tsx:91`; `frontend/src/App.tsx:1882`; `frontend/src/ui/ModuleWorkspaceRoutes.tsx:67`

- **Gap / next acceptance:** Executable third-party plugins remain DENY_ALL. Local known-zero configured route only; real model quality NOT_RUN. Exact task-center model-run reopening has focused contract verification; final browser acceptance is pending.

### B03 — Voice direction and speaker attribution

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `app/experimental/audiobook.py`; `app/experimental/voice_direction.py`; `app/audio_production_store.py`; `frontend/src/experimental/AudiobookPanel.tsx`; `frontend/src/experimental/VoiceDirectionPanel.tsx`

- **API owner files:** `app/experimental/audiobook_api.py`; `app/experimental/voice_direction_api.py`

- **Static mounted call sites:** `frontend/src/experimental/ExperimentalWorkbench.tsx:111`; `frontend/src/experimental/ExperimentalWorkbench.tsx:109`; `frontend/src/App.tsx:1884`; `frontend/src/App.tsx:2103`; `frontend/src/novel/DirectorShotList.tsx:348`

- **Gap / next acceptance:** Measured fixture audio is not real voice quality. ASR/forced word/phoneme alignment, precise lip sync and reference-voice consent/execution remain NOT_CONFIGURED/NOT_RUN. Synchronous bounded mix is not a fabricated durable task.

### B04 — Subtitle editing and timeline

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `app/experimental/subtitle_timeline.py`; `app/experimental/voice_direction.py`; `frontend/src/experimental/SubtitleTimelinePanel.tsx`

- **API owner files:** `app/experimental/subtitle_timeline_api.py`

- **Static mounted call sites:** `frontend/src/experimental/ExperimentalWorkbench.tsx:110`

- **Gap / next acceptance:** No ASR/word alignment model means exact speech-word timestamps are not claimed. Burn-in, subtitle applications and professional typography remain unimplemented/unverified.

### B05 — Multilingual revisions and terminology

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `app/experimental/multilingual_editions.py`; `app/experimental/multilingual_translation.py`; `frontend/src/experimental/MultilingualEditionsPanel.tsx`; `frontend/src/experimental/TranslationMemoryPanel.tsx`

- **API owner files:** `app/experimental/multilingual_editions_api.py`

- **Static mounted call sites:** `frontend/src/experimental/ExperimentalWorkbench.tsx:92`; `frontend/src/experimental/MultilingualEditionsPanel.tsx:131`; `frontend/src/experimental/MultilingualEditionsPanel.tsx:71`

- **Gap / next acceptance:** Literal missing/term checks are not semantic translation-quality/omission proof. No automatic retranslation or silent replay. Real language/RTL/font acceptance NOT_RUN; exact translation-job reopening has focused contract verification; final browser acceptance is pending.

### B06 — Comic and Webtoon layouts

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `app/experimental/comic_layouts.py`; `app/services/asset_library_service.py`; `frontend/src/experimental/ComicLayoutsPanel.tsx`

- **API owner files:** `app/experimental/comic_layouts_api.py`

- **Static mounted call sites:** `frontend/src/experimental/ExperimentalWorkbench.tsx:88`

- **Gap / next acceptance:** Synthetic approved PNG/CJK raster contracts do not verify model art quality, arbitrary scripts/fonts or professional print/Webtoon production acceptance. No automatic generation from a brief.

### B07 — Interactive narrative export

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `app/experimental/interactive_story.py`; `app/experimental/planning.py`; `frontend/src/experimental/InteractiveStoryPanel.tsx`; `frontend/src/experimental/InteractiveStoryHistory.tsx`

- **API owner files:** `app/experimental/interactive_story_api.py`

- **Static mounted call sites:** `frontend/src/experimental/ExperimentalWorkbench.tsx:89`; `frontend/src/experimental/InteractiveStoryPanel.tsx:46`; `frontend/src/experimental/InteractiveStoryPanel.tsx:47`

- **Gap / next acceptance:** Bounded analysis is not an unbounded graph proof. RenPy text/menu and engine-neutral JSON export do not execute/deploy engines or media. Actual RenPy/Godot runtime NOT_RUN.

### B08 — Writer room and team review

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `app/experimental/writer_room.py`; `app/services/creation_workbench_service.py`; `app/experimental/inbox.py`; `frontend/src/experimental/WriterRoomPanel.tsx`

- **API owner files:** `app/experimental/writer_room_api.py`

- **Static mounted call sites:** `frontend/src/experimental/ExperimentalWorkbench.tsx:87`

- **Gap / next acceptance:** No realtime co-editing, presence transport, invitation or permission grant. Finishing a room task cannot approve/apply original manuscript/Canon/assets; branch manuscript source remains unavailable.

### B09 — Project fork and merge

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `app/experimental/project_forks.py`; `app/experimental/structured_forks.py`; `app/experimental/world.py`; `frontend/src/experimental/ProjectForksPanel.tsx`; `frontend/src/experimental/SharedUniversePanel.tsx`

- **API owner files:** `app/experimental/project_forks_api.py`

- **Static mounted call sites:** `frontend/src/experimental/ExperimentalWorkbench.tsx:85`; `frontend/src/experimental/ProjectForksPanel.tsx:51`; `frontend/src/experimental/ProjectForksPanel.tsx:49`

- **Gap / next acceptance:** Snapshots never mutate another work or become a second Canon; source edits do not repin. Current source/target deletion/archive/privacy/permission loss withholds old content. Local owner sharing only; bounded incoming scan; no implicit model-context injection or branch-manuscript fallback.

### B10 — Offline synchronization foundation

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `app/experimental/offline_sync.py`; `app/experimental/portable_projects.py`; `frontend/src/experimental/OfflineSyncPanel.tsx`

- **API owner files:** `app/experimental/offline_sync_api.py`

- **Static mounted call sites:** `frontend/src/experimental/ExperimentalWorkbench.tsx:86`

- **Gap / next acceptance:** No automatic cloud transport, production realtime synchronization or missing collaboration-branch manuscript authority. Manual local exchange is not a second task/model/manuscript system.

### U01 — Resume the previous workspace

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `app/experimental/ux.py`; `frontend/src/store.ts`; `frontend/src/App.tsx`; `frontend/src/experimental/WorkspaceToolsPanel.tsx`

- **API owner files:** `app/experimental/ux_api.py`

- **Static mounted call sites:** `frontend/src/experimental/ExperimentalWorkbench.tsx:100`

- **Gap / next acceptance:** Missing/cleared browser storage requires explicit project selection; unavailable branch-manuscript sources fail closed. Exact reopen has focused contract verification; final browser acceptance is pending.

### U02 — Loss-resistant editing and visible save state

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `frontend/src/drafts.ts`; `frontend/src/App.tsx`; `frontend/src/ui/SaveControls.tsx`; `app/autosave/durable.py`

- **API owner files:** `app/api.py`

- **Static mounted call sites:** `frontend/src/App.tsx:1590`; `frontend/src/creative/useStudioManualMask.ts:49`; `frontend/src/App.tsx:1762`; `frontend/src/App.tsx:2231`

- **Gap / next acceptance:** Browser storage clearing, inaccessible storage, never-persisted keystrokes and real power-loss/native Windows acceptance remain outside the verified contract.

### U03 — Search, commands and recents

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `app/experimental/ux.py`; `app/experimental/search_sources.py`; `frontend/src/experimental/WorkspaceSearch.tsx`; `frontend/src/App.tsx`; `frontend/src/ui/FeatureLauncher.tsx`

- **API owner files:** `app/experimental/ux_api.py`

- **Static mounted call sites:** `frontend/src/experimental/WorkspaceToolsPanel.tsx:130`; `frontend/src/App.tsx:1349`

- **Gap / next acceptance:** Literal search is not semantic retrieval. Result/cache/page limits and current permissions apply. Collaboration IDs cannot substitute for absent branch-manuscript storage; final browser journey pending.

### U04 — Focus, reference split and inspiration

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `app/experimental/writing_focus.py`; `frontend/src/experimental/WritingFocusPanel.tsx`; `frontend/src/Editor.tsx`; `frontend/src/App.tsx`

- **API owner files:** `app/experimental/writing_focus_api.py`

- **Static mounted call sites:** `frontend/src/experimental/ExperimentalWorkbench.tsx:98`; `frontend/src/creative/useStudioManualMask.ts:49`

- **Gap / next acceptance:** No separate new focus engine. Native input and absent branch-manuscript adapters remain separate acceptance boundaries.

### U05 — Selection assistant and partial accept

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `app/experimental/revision_intelligence.py`; `app/services/generation_service.py`; `frontend/src/Editor.tsx`; `frontend/src/novel/AiWritingPanel.tsx`

- **API owner files:** `app/experimental/revision_intelligence_api.py`; `app/api.py`

- **Static mounted call sites:** `frontend/src/creative/useStudioManualMask.ts:49`; `frontend/src/App.tsx:1665`; `frontend/src/experimental/ExperimentalWorkbench.tsx:97`

- **Gap / next acceptance:** Real output quality/native selection/IME acceptance NOT_RUN. Branch source adapters remain unavailable; no generic whole-manuscript adoption for feature-owned model jobs.

### U06 — Change impact and selective refresh

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `app/experimental/media.py`; `app/experimental/media_api.py`; `app/experimental/change_impact.py`; `frontend/src/experimental/MediaPanel.tsx`; `frontend/src/experimental/ChangeImpactPanel.tsx`

- **API owner files:** `app/experimental/change_impact_api.py`; `app/experimental/media_api.py`

- **Static mounted call sites:** `frontend/src/experimental/ExperimentalWorkbench.tsx:107`; `frontend/src/experimental/ExperimentalWorkbench.tsx:79`

- **Gap / next acceptance:** Stale queue/approval remains denied; unknown config/permission errors propagate. Removed character references require restoring the source or a new brief. Image refresh is not a generic audio/video executor; real art quality and unknown upstream monetary settlement remain separate.

### U07 — Unified task center and honest progress

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `app/experimental/ux.py`; `app/experimental/author_task_projection.py`; `app/experimental/workspace_task_owners.py`; `frontend/src/experimental/WorkspaceToolsPanel.tsx`; `frontend/src/experimental/ExperimentalWorkbench.tsx`

- **API owner files:** `app/experimental/ux_api.py`

- **Static mounted call sites:** `frontend/src/experimental/ExperimentalWorkbench.tsx:100`; `frontend/src/App.tsx:1639`

- **Gap / next acceptance:** Retry/resume is never a generic replay. Exact style/revision model links are verified; simulator/Judge/translation/declarative exact subrecord reopen now has focused contract verification, with final browser acceptance pending. Synchronous operations are not fabricated background jobs.

### U08 — Context and privacy inspector

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `app/author_context_sources.py`; `app/author_request.py`; `app/experimental/author_context_api.py`; `app/jobs.py`; `frontend/src/novel/AuthorSourceItems.tsx`; `frontend/src/novel/AuthorRequestPreviewPanel.tsx`

- **API owner files:** `app/api.py`

- **Static mounted call sites:** `frontend/src/novel/AuthorRequestPreviewPanel.tsx:71`; `frontend/src/experimental/ModelBrokerPanel.tsx:121`; `frontend/src/novel/AiWritingPanel.tsx:519`; `frontend/src/experimental/ModelBrokerPanel.tsx:120`; `frontend/src/App.tsx:1660`

- **Gap / next acceptance:** Research is LOCAL_ONLY. Character-only author mode rejects author-only additions. Anonymous derived bundles use conservative whole-bundle exclusion; duplicated prose is not semantic DLP. Unsupported branch sources and cloud/budgeted variant groups remain unavailable.

### U09 — Local AI diagnostic and setup guidance

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `app/model_center/discovery.py`; `app/model_center/discovery_probes.py`; `app/experimental/local_ai_inspection.py`; `frontend/src/ui/LocalAiDiscovery.tsx`; `frontend/src/experimental/WorkflowInspectionPanel.tsx`

- **API owner files:** `app/experimental/local_ai_inspection_api.py`; `app/model_center/discovery_api.py`

- **Static mounted call sites:** `frontend/src/ui/ModelCenter.tsx:84`; `frontend/src/experimental/ExperimentalWorkbench.tsx:99`; `frontend/src/App.tsx:1887`

- **Gap / next acceptance:** Actual hardware/runtime/model validation remains LOCAL_REQUIRED/NOT_RUN. No automatic ComfyUI/Torch/CUDA/driver upgrade or unknown-node installation; unsupported families retain ADAPTER_REQUIRED.

### U10 — Scenario onboarding and progressive disclosure

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `app/experimental/first_use.py`; `frontend/src/novel/EntryExperience.tsx`; `frontend/src/ui/FeatureLauncher.tsx`

- **API owner files:** `app/experimental/first_use_api.py`

- **Static mounted call sites:** `frontend/src/App.tsx:1219`; `frontend/src/App.tsx:1349`; `frontend/src/novel/EntryExperience.tsx:529`; `frontend/src/App.tsx:1658`

- **Gap / next acceptance:** No new isolated first-use File/API acceptance is claimed by this continuation slice. Original create-without-receipt stays UNKNOWN and is not replayed; native first-run/installer acceptance remains NOT_RUN.

### U11 — Reading, proofreading and publishing checks

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `app/experimental/reader_preflight.py`; `app/services/export_job_service.py`; `frontend/src/experimental/ReaderPreflightPanel.tsx`; `frontend/src/novel/ExportPanel.tsx`

- **API owner files:** `app/experimental/reader_preflight_api.py`

- **Static mounted call sites:** `frontend/src/experimental/ExperimentalWorkbench.tsx:82`; `frontend/src/App.tsx:1894`

- **Gap / next acceptance:** No new isolated full reader/typography acceptance is claimed. Native readers, layout, accessibility and target publishing quality require actual target evidence; final full regression pending.

### U12 — Actionable errors and private diagnostic export

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `app/experimental/ux.py`; `app/experimental/ux_api.py`; `app/runtime_diagnostics.py`; `frontend/src/novel/RuntimeDiagnostics.tsx`; `frontend/src/experimental/WorkspaceToolsPanel.tsx`

- **API owner files:** `app/experimental/ux_api.py`

- **Static mounted call sites:** `frontend/src/App.tsx:1887`; `frontend/src/experimental/ExperimentalWorkbench.tsx:100`

- **Gap / next acceptance:** The allowlist is not complete telemetry; no automatic upload or unbounded raw-log exposure.

### U13 — Chinese input, accessibility and scale

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `frontend/src/Editor.tsx`; `frontend/src/ui/AppShell.tsx`; `frontend/src/ui/tokens.css`; `frontend/tests/visual`; `docs/ui/design_system.md`

- **API owner files:** No separate API file enumerated by the inspected registry; verify the original owner route before extending this row.

- **Static mounted call sites:** `frontend/src/creative/useStudioManualMask.ts:49`; `frontend/src/App.tsx:1738`; `frontend/src/experimental/WorkspaceToolsPanel.tsx:93`

- **Gap / next acceptance:** React/jsdom and token checks do not verify physical input latency, native Windows IME, screen readers, multi-monitor or OS zoom. Historical Chromium scale/geometry receipts remain source-specific; final hosted screenshots pending.

### U14 — Portable project, relink and safe cleanup

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `app/experimental/portable_projects.py`; `app/backup_restore.py`; `app/services/asset_library_service.py`; `frontend/src/experimental/PortableProjectsPanel.tsx`

- **API owner files:** `app/experimental/portable_projects_api.py`

- **Static mounted call sites:** `frontend/src/experimental/ExperimentalWorkbench.tsx:93`

- **Gap / next acceptance:** Selected portable bundles are not full-history/Canon backups. Collaboration restore, large real archives, native packaging and user upgrade/uninstall retention remain separate gates.

### U15 — Writing goals and controlled notices

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `app/experimental/writing_sessions.py`; `frontend/src/experimental/WritingSessionPanel.tsx`; `frontend/src/novel/NovelOverviewPanel.tsx`

- **API owner files:** `app/experimental/writing_sessions_api.py`

- **Static mounted call sites:** `frontend/src/experimental/ExperimentalWorkbench.tsx:83`; `frontend/src/App.tsx:1885`

- **Gap / next acceptance:** No Wave5-specific U15 closure claim. Notices are in-app only while the supported surface is active; no OS/background/external notification service. Final full regression pending.

### U16 — Safe batch preflight

**State:** PARTIAL; bounded source IMPLEMENTED; current execution NOT_RUN.

- **Original owners:** `app/experimental/safe_batches.py`; `app/experimental/safe_batch_contracts.py`; `frontend/src/experimental/SafeBatchesPanel.tsx`

- **API owner files:** `app/experimental/safe_batches_api.py`

- **Static mounted call sites:** `frontend/src/experimental/ExperimentalWorkbench.tsx:94`

- **Gap / next acceptance:** Paid/unknown-price routes are held or unavailable; unknown cost stays unreconciled. Real cloud/model/GPU/voice quality and arbitrary adapter families are not verified.

## Graph-01–22 and Console-01–06

| ID / exact traced requirement | State | Current original owner / implementation | Remaining dependency and acceptance |
|---|---|---|---|
| GRAPH-01 Shared Image/Video/Audio/3D/Research DAG and ordinary/pro UI | PARTIAL; NOT_RUN acceptance | Typed schema1–5 GraphService and original Workflow/Production owners; mounted IndependentStudioWorkspace graph view. | Full media/3D/research parity and professional unified acceptance remain incomplete. |
| GRAPH-02 Pan/zoom, marquee/multiselect and draggable visual objects | PARTIAL; NOT_RUN acceptance | GraphCanvas pointer drag, pan, anchored wheel zoom, marquee and multi-node movement are implemented. | Spatial view remains limited to execution graph geometry; broad workspace/camera and target-browser acceptance missing. |
| GRAPH-03 Drag-connect, typed-port highlighting, invalid-edge explanation/conversion | PARTIAL; NOT_RUN acceptance | graphDraft.connectionIssue plus selected port buttons, ConnectionAdvisorPanel and strict server TypedEdge validation. | Pointer drag-to-connect, broader conversions and complete visual highlight/error-focus acceptance incomplete. |
| GRAPH-04 Context-menu and keyboard command search | PARTIAL; NOT_RUN acceptance | NodePalettePanel consumes catalog fields with search; existing workspace command surfaces. | Complete canvas context menu/keyboard command insertion and focus acceptance incomplete. |
| GRAPH-05 Undo/redo and copy/paste | PARTIAL; NOT_RUN acceptance | useStudioGraphEditorController maintains past/future and explicit undo/redo. | Cross-canvas/project safe copy/paste and durable undo history not found in inspected graph seam. |
| GRAPH-06 Node grouping, annotations, collapse, MiniMap and alignment | PARTIAL; NOT_RUN acceptance | CanvasOps local helpers plus deterministic layout preview/apply and mounted MiniMap navigation through original undo/save/reopen exist; see current layout and MiniMap reports. | Actual GraphCanvas collapse/group rendering, grouping persistence and nested subcanvases missing. |
| GRAPH-07 Keyboard node/port navigation and error location | PARTIAL; NOT_RUN acceptance | GraphCanvas keyboard movement/node list/port buttons and editable-target guard exist. | Full keyboard path, IME, error focus and screen-reader/real-device acceptance NOT_RUN. |
| GRAPH-08 Graph version, visible autosaved drafts and reload/disconnect recovery | PARTIAL; NOT_RUN acceptance | GraphService CAS persists viewport/positions with dirty/conflict/navigation guards; graph location remembered. Targeted File and mocked UI reopen/conflict tests pass. | Unsaved text autosave/disconnect/restart recovery and independently persisted grouping/annotation presentation missing. |
| GRAPH-09 Import/export graph templates; disconnect/delete consequence preview | PARTIAL; NOT_RUN acceptance | Bounded remove preserves original assets; change-impact classifier and declarative template subsystem exist. | General typed graph import/export/cross-canvas templates and reviewed disconnect consequence preview incomplete. |
| GRAPH-10 Large-graph virtualization/LOD benchmark | PARTIAL; bounded culling IMPLEMENTED; browser acceptance NOT_RUN | GraphCanvas uses disposable presentation bounds/index and viewport culling with interaction retention; 1000/10000 display-only geometry benchmark measured. See current culling report. | No browser FPS/memory acceptance, full LOD/spatial index or persistent large-display workspace; accessibility directory and connection descriptions still scale with all objects. Execution budgets unchanged. |
| GRAPH-11 Input nodes: Text/Image/Video/Audio/3D/AssetRef/reference/Depth/external file | PARTIAL; NOT_RUN acceptance | Text/reference/Asset inputs plus exact saved Director/Storyboard documents exist. | Full 3D/pose/depth/external-file semantics and independent adapters incomplete. |
| GRAPH-12 Processing nodes: Agent/image/edit/upscale/video/interpolate/TTS/ASR/convert/quality | PARTIAL; NOT_RUN acceptance | Local text model, image generation/style/upscale, media/video and timeline processing registered in finite schemas. | Full interpolate/ASR/quality/conversion node portfolio and real provider quality incomplete. |
| GRAPH-13 Control nodes: Director/style/character/camera/motion/budget/review/conditions | PARTIAL; NOT_RUN acceptance | director note/director_plan, image_style, human/media review nodes and admission budgets exist. | General camera/motion/budget/condition control nodes and editable Console incomplete. |
| GRAPH-14 Output nodes: Asset Save/Preview/Export/Timeline Handoff/Package | PARTIAL; NOT_RUN acceptance | Reviewed media formal Asset and timeline_export adapters plus output preview/review routes exist. | Unified explicit asset-save/package/export node portfolio and whole-chain acceptance incomplete. |
| GRAPH-15 Text/Image/Video/Audio/Model/Scene/Camera/Pose/Depth/Style/AssetRef/Timeline ports | PARTIAL; NOT_RUN acceptance | Strict typed ports include TEXT/DRAFT/ASSET_REF and media/planning-specific output contracts. | Not every requested model/scene/camera/pose/depth/style/timeline type has a live adapter. |
| GRAPH-16 Single-node or graph execution with no Director node | PARTIAL; NOT_RUN acceptance | Selected dependency closure and graph with optional/no Director; independent media entry remains. | All node families independent live execution and UX acceptance NOT_RUN. |
| GRAPH-17 Preview inputs/outputs/models/permissions/privacy/resources/cost/overwrite | PARTIAL; NOT_RUN acceptance | Preflight plus explicit model/media preview and per-request input/provider/cost/privacy consent. | One complete cross-module Graph/Console impact/overwrite/cost preview remains incomplete. |
| GRAPH-18 Dependency execution and bounded concurrency | PARTIAL; NOT_RUN acceptance | Original bounded Workflow host and topological closure execution. | General multimodal parallel scheduling not established. |
| GRAPH-19 VRAM conflict queue, staged unload and resource release | PARTIAL; NOT_RUN acceptance | Original Model Center/runtime lifecycle and bounded production execution retained. | Graph-wide VRAM conflict queue/staged unload/resource release acceptance not established. |
| GRAPH-20 Cache binds input version/model/parameters/definition/permission; descendant invalidation | PARTIAL; NOT_RUN acceptance | GraphExecutionService._cached uses same-version owned reviewed-ancestor outputs and keyed receipts. | Cross-version descendant invalidation, binary/provider cache and cleanup/reservation incomplete. |
| GRAPH-21 Node/local rerun, queue pause, explicit retry, cancel requested versus acknowledged | PARTIAL; NOT_RUN acceptance | Original pause/resume/cancel/review/execute actions with UNKNOWN no-replay and media receipt reconciliation. | General partial rerun/retry across every provider and acknowledged cancellation acceptance incomplete. |
| GRAPH-22 Truthful node progress/time/resource/missing-capability/error navigation | PARTIAL; NOT_RUN acceptance | GraphRunPanel projects run/node states; original outputs/review/status retained. | Whole-node timing/resource accounting, error navigation and truthful real provider telemetry incomplete. |
| CONSOLE-01 Optional Director Console carries vision/duration/audience/story/style/performance/sound/review | PARTIAL; NOT_RUN acceptance | DirectorIntent/ShotCard and read-only DirectorWorkspace; AIDirectorPanel with editable original proposals and optional model controls. | Optional fused writable Console carrying full requested design/resource fields remains incomplete. |
| CONSOLE-02 Versioned suggestions/parameters to multiple targets without elevated authority | PARTIAL; NOT_RUN acceptance | director_plan/storyboard_plan read exact Creative document versions/digests; source ancestry checked. | Reviewed multi-target suggestions→formal owner writes/tasks/status loop not complete. |
| CONSOLE-03 Collapsible card, expanded Console, dependency/progress preview | PARTIAL; NOT_RUN acceptance | Typed Director reference card and separate read-only expanded DirectorWorkspace exist. | No fused editable/collapsible Console with persisted presentation and dependency/progress UX. |
| CONSOLE-04 Multiple independent Director nodes, duplicate as sub-console | PARTIAL; NOT_RUN acceptance | Multiple ordinary director_plan instances can reference distinct documents within node budgets. | No explicit console responsibility/sub-console duplication semantics or acceptance; do not equate generic instances with full feature. |
| CONSOLE-05 Preview/review graph/Shot List proposals before replacing/rerunning/sending | PARTIAL; NOT_RUN acceptance | Original Director proposals distinguish deterministic versus model provenance; explicit review/apply exists. | Complete graph proposal diff/adoption/replacement/rerun/send approval integration remains incomplete. |
| CONSOLE-06 Disconnect/delete Director without breaking unrelated valid nodes/assets | PARTIAL; NOT_RUN acceptance | removeGraphNodes and editor removal only remove graph nodes/edges, not original assets; Director is optional. | Specialized fused Console disconnect/delete dependency/independent-module acceptance is NOT_RUN. |


## All additional FS / CORE surface IDs from the versioned catalog

These are key cross-cutting product surfaces, not an invented new numbering scheme. PARTIAL means implementation exists but complete frozen acceptance is open. Formal-only inspector descriptions are explicitly kept separate from mounted UI. Catalog scope text is historical; files are checked against the pinned current tree.

| ID / requirement | State and owner/API | UI evidence | Concrete remaining boundary / dependencies |
|---|---|---|---|
| CORE_MANUSCRIPT — Project / Chapter tree / Authoritative manuscript | PARTIAL; [`app/services/novel_service.py`](../../app/services/novel_service.py); [`app/services/chapter_service.py`](../../app/services/chapter_service.py); [`app/chapter_identity.py`](../../app/chapter_identity.py); [`app/document.py`](../../app/document.py); API [`app/api.py`](../../app/api.py); [`app/collaboration_api.py`](../../app/collaboration_api.py) | [`frontend/src/novel/ChapterTree.tsx`](../../frontend/src/novel/ChapterTree.tsx); [`frontend/src/Editor.tsx`](../../frontend/src/Editor.tsx); [`frontend/src/App.tsx`](../../frontend/src/App.tsx); `frontend/src/App.tsx:1258`; `frontend/src/creative/useStudioManualMask.ts:49` | FINAL_SOURCE_CI; current execution NOT_RUN; original scope/version/review required. |
| CORE_GENERATION — AI writing / Draft-Diff-Accept / Recovery | PARTIAL; [`app/services/generation_service.py`](../../app/services/generation_service.py); [`app/jobs.py`](../../app/jobs.py); [`app/generation_stream.py`](../../app/generation_stream.py); [`app/api.py`](../../app/api.py); API [`app/api.py`](../../app/api.py); [`app/experimental/author_context_api.py`](../../app/experimental/author_context_api.py) | [`frontend/src/novel/AiWritingPanel.tsx`](../../frontend/src/novel/AiWritingPanel.tsx); [`frontend/src/novel/GenerationRecoveryPicker.tsx`](../../frontend/src/novel/GenerationRecoveryPicker.tsx); [`frontend/src/novel/GenerationWorkflowTimeline.tsx`](../../frontend/src/novel/GenerationWorkflowTimeline.tsx); `frontend/src/App.tsx:1665`; `frontend/src/App.tsx:1661` | FINAL_SOURCE_CI; current execution NOT_RUN; original scope/version/review required. |
| CORE_CREATION — Creation workbench / Structured plans / Review threads | PARTIAL; [`app/services/creation_workbench_service.py`](../../app/services/creation_workbench_service.py); [`app/creation_workbench_api.py`](../../app/creation_workbench_api.py); API [`app/creation_workbench_api.py`](../../app/creation_workbench_api.py) | [`frontend/src/novel/CreationWorkbenchPanel.tsx`](../../frontend/src/novel/CreationWorkbenchPanel.tsx); [`frontend/src/novel/AIPlanningPanel.tsx`](../../frontend/src/novel/AIPlanningPanel.tsx); `frontend/src/App.tsx:1896`; `frontend/src/novel/CreationWorkbenchPanel.tsx:49` | FINAL_SOURCE_CI; current execution NOT_RUN; original scope/version/review required. |
| FS_PLANNING — Layered planning / Proposals / Templates | PARTIAL; [`app/experimental/planning.py`](../../app/experimental/planning.py); [`app/services/ai_planning_service.py`](../../app/services/ai_planning_service.py); [`app/experimental/planning_api.py`](../../app/experimental/planning_api.py); [`app/ai_planning_api.py`](../../app/ai_planning_api.py); API [`app/experimental/planning_api.py`](../../app/experimental/planning_api.py); [`app/ai_planning_api.py`](../../app/ai_planning_api.py) | [`frontend/src/experimental/PlanningPanel.tsx`](../../frontend/src/experimental/PlanningPanel.tsx); [`frontend/src/novel/StoryPlanningWorkspace.tsx`](../../frontend/src/novel/StoryPlanningWorkspace.tsx); [`frontend/src/experimental/PromotionRecovery.tsx`](../../frontend/src/experimental/PromotionRecovery.tsx); `frontend/src/experimental/ExperimentalWorkbench.tsx:101`; `frontend/src/App.tsx:2065` | FINAL_SOURCE_CI; current execution NOT_RUN; original scope/version/review required. |
| FS_CANON — Canon / Evidence / Pending decisions | PARTIAL; [`app/experimental/finding_review_composition.py`](../../app/experimental/finding_review_composition.py); [`app/services/canon_service.py`](../../app/services/canon_service.py); [`app/services/pending_canon_review_service.py`](../../app/services/pending_canon_review_service.py); [`app/services/lore_service.py`](../../app/services/lore_service.py); API [`app/api.py`](../../app/api.py); [`app/pending_canon_review_api.py`](../../app/pending_canon_review_api.py) | [`frontend/src/novel/StoryDatabase.tsx`](../../frontend/src/novel/StoryDatabase.tsx); [`frontend/src/experimental/WorldPanel.tsx`](../../frontend/src/experimental/WorldPanel.tsx); [`frontend/src/experimental/InboxPanel.tsx`](../../frontend/src/experimental/InboxPanel.tsx); `frontend/src/App.tsx:1873`; `frontend/src/experimental/ExperimentalWorkbench.tsx:103` | FINAL_SOURCE_CI; current execution NOT_RUN; original scope/version/review required. |
| FS_CONTINUITY — Continuity / Evidence / Author feedback | PARTIAL; [`app/experimental/finding_review_composition.py`](../../app/experimental/finding_review_composition.py); [`app/services/continuity_finding_service.py`](../../app/services/continuity_finding_service.py); [`app/services/finding_review_service.py`](../../app/services/finding_review_service.py); [`app/lore/continuity.py`](../../app/lore/continuity.py); API [`app/api.py`](../../app/api.py); [`app/finding_review_api.py`](../../app/finding_review_api.py) | [`frontend/src/novel/ContinuityCheckPanel.tsx`](../../frontend/src/novel/ContinuityCheckPanel.tsx); [`frontend/src/novel/FindingReviewPanel.tsx`](../../frontend/src/novel/FindingReviewPanel.tsx); [`frontend/src/novel/findingReviewClient.ts`](../../frontend/src/novel/findingReviewClient.ts); `frontend/src/App.tsx:1886`; `frontend/src/novel/ContinuityCheckPanel.tsx:125` | FINAL_SOURCE_CI; current execution NOT_RUN; original scope/version/review required. |
| FS_FORESHADOWING — Foreshadowing / Narrative progress | PARTIAL; [`app/experimental/finding_review_composition.py`](../../app/experimental/finding_review_composition.py); [`app/services/novel_service.py`](../../app/services/novel_service.py); [`app/services/narrative_state_service.py`](../../app/services/narrative_state_service.py); [`app/services/narrative_finding_service.py`](../../app/services/narrative_finding_service.py); API [`app/api.py`](../../app/api.py); [`app/story_record_api.py`](../../app/story_record_api.py) | [`frontend/src/novel/StoryDatabase.tsx`](../../frontend/src/novel/StoryDatabase.tsx); [`frontend/src/novel/StoryRecordVersionEditor.tsx`](../../frontend/src/novel/StoryRecordVersionEditor.tsx); [`frontend/src/novel/StoryPlanningWorkspace.tsx`](../../frontend/src/novel/StoryPlanningWorkspace.tsx); `frontend/src/App.tsx:1873`; `frontend/src/novel/StoryDatabase.tsx:60` | LEGACY_STRUCTURED_CAS_COMPATIBILITY; FINAL_SOURCE_CI; current execution NOT_RUN; original scope/version/review required. |
| FS_TIMELINE — Story timeline / World chronology | PARTIAL; [`app/services/novel_service.py`](../../app/services/novel_service.py); [`app/experimental/world.py`](../../app/experimental/world.py); [`app/narrative.py`](../../app/narrative.py); [`app/lore/continuity.py`](../../app/lore/continuity.py); API [`app/api.py`](../../app/api.py); [`app/story_record_api.py`](../../app/story_record_api.py) | [`frontend/src/novel/StoryDatabase.tsx`](../../frontend/src/novel/StoryDatabase.tsx); [`frontend/src/novel/StoryRecordVersionEditor.tsx`](../../frontend/src/novel/StoryRecordVersionEditor.tsx); [`frontend/src/novel/WorldTimelineView.tsx`](../../frontend/src/novel/WorldTimelineView.tsx); `frontend/src/App.tsx:1873`; `frontend/src/novel/StoryDatabase.tsx:60` | LEGACY_STRUCTURED_CAS_COMPATIBILITY; FINAL_SOURCE_CI; current execution NOT_RUN; original scope/version/review required. |
| FS_STORY_DATABASE — Characters / Locations / Relationships / World rules | PARTIAL; [`app/services/novel_service.py`](../../app/services/novel_service.py); [`app/services/lore_service.py`](../../app/services/lore_service.py); [`app/repositories/structured_cas.py`](../../app/repositories/structured_cas.py); [`app/repositories/story_record_versions.py`](../../app/repositories/story_record_versions.py); API [`app/api.py`](../../app/api.py); [`app/story_record_api.py`](../../app/story_record_api.py) | [`frontend/src/novel/StoryDatabase.tsx`](../../frontend/src/novel/StoryDatabase.tsx); [`frontend/src/novel/StoryRecordVersionEditor.tsx`](../../frontend/src/novel/StoryRecordVersionEditor.tsx); [`frontend/src/novel/WorldBuildingDashboard.tsx`](../../frontend/src/novel/WorldBuildingDashboard.tsx); `frontend/src/App.tsx:1873`; `frontend/src/novel/StoryDatabase.tsx:60` | LEGACY_STRUCTURED_CAS_COMPATIBILITY; FINAL_SOURCE_CI; current execution NOT_RUN; original scope/version/review required. |
| FS_IMPORT — Manuscript import / Import health / Extraction | PARTIAL; [`app/services/import_review_service.py`](../../app/services/import_review_service.py); [`app/services/import_apply_service.py`](../../app/services/import_apply_service.py); [`app/import_parsers.py`](../../app/import_parsers.py); [`app/experimental/imports.py`](../../app/experimental/imports.py); API [`app/api.py`](../../app/api.py); [`app/experimental/imports_api.py`](../../app/experimental/imports_api.py) | [`frontend/src/novel/NovelImportPanel.tsx`](../../frontend/src/novel/NovelImportPanel.tsx); [`frontend/src/experimental/ImportPanel.tsx`](../../frontend/src/experimental/ImportPanel.tsx); `frontend/src/App.tsx:1895`; `frontend/src/experimental/ExperimentalWorkbench.tsx:102` | FINAL_SOURCE_CI; current execution NOT_RUN; original scope/version/review required. |
| FS_REVIEW — Unified review inbox | PARTIAL; [`app/experimental/inbox.py`](../../app/experimental/inbox.py); [`app/experimental/legacy_inbox.py`](../../app/experimental/legacy_inbox.py); [`app/experimental/finding_review_composition.py`](../../app/experimental/finding_review_composition.py); [`app/experimental/adaptation_projection.py`](../../app/experimental/adaptation_projection.py); API [`app/experimental/inbox_api.py`](../../app/experimental/inbox_api.py) | [`frontend/src/experimental/InboxPanel.tsx`](../../frontend/src/experimental/InboxPanel.tsx); [`frontend/src/novel/AgentResultReview.tsx`](../../frontend/src/novel/AgentResultReview.tsx); [`frontend/src/RevisionPanel.tsx`](../../frontend/src/RevisionPanel.tsx); `frontend/src/experimental/ExperimentalWorkbench.tsx:104`; `frontend/src/novel/AgentTeamPanel.tsx:523` | FINAL_SOURCE_CI; current execution NOT_RUN; original scope/version/review required. |
| CORE_IMAGES — Image / Cover / Storyboard / Character reference / Edit / Multi-reference | PARTIAL; [`app/services/image_job_service.py`](../../app/services/image_job_service.py); [`app/asset_providers.py`](../../app/asset_providers.py); [`app/experimental/media.py`](../../app/experimental/media.py); [`app/api.py`](../../app/api.py); API [`app/api.py`](../../app/api.py); [`app/experimental/media_api.py`](../../app/experimental/media_api.py) | [`frontend/src/novel/ImageGenerationPanel.tsx`](../../frontend/src/novel/ImageGenerationPanel.tsx); [`frontend/src/novel/ImageQueuePanel.tsx`](../../frontend/src/novel/ImageQueuePanel.tsx); [`frontend/src/novel/ImageInfiniteCanvas.tsx`](../../frontend/src/novel/ImageInfiniteCanvas.tsx); `frontend/src/ui/ModuleWorkspaceRoutes.tsx:62`; `frontend/src/App.tsx:1892` | EXTERNAL_REAL_MODELS; FINAL_SOURCE_CI; current execution NOT_RUN; original scope/version/review required. Real model/GPU/quality LOCAL_REQUIRED. |
| CORE_SCREENPLAY — Screenplay / Scene / Shot authoring | PARTIAL; [`app/services/screenplay_service.py`](../../app/services/screenplay_service.py); [`app/repositories/screenplay_versions.py`](../../app/repositories/screenplay_versions.py); [`app/api.py`](../../app/api.py); API [`app/api.py`](../../app/api.py) | [`frontend/src/novel/ScreenplayPanel.tsx`](../../frontend/src/novel/ScreenplayPanel.tsx); [`frontend/src/novel/MultimodalDirectorWorkspace.tsx`](../../frontend/src/novel/MultimodalDirectorWorkspace.tsx); [`frontend/src/novel/BindingManifestPanel.tsx`](../../frontend/src/novel/BindingManifestPanel.tsx); `frontend/src/App.tsx:1891`; `frontend/src/ui/ModuleWorkspaceRoutes.tsx:62` | FINAL_SOURCE_CI; current execution NOT_RUN; original scope/version/review required. |
| CORE_VIDEO — Video / Motion / Assembly / Post | PARTIAL; [`app/services/video_assembly_service.py`](../../app/services/video_assembly_service.py); [`app/asset_providers.py`](../../app/asset_providers.py); [`app/media_frames.py`](../../app/media_frames.py); [`app/experimental/media.py`](../../app/experimental/media.py); API [`app/api.py`](../../app/api.py); [`app/experimental/media_api.py`](../../app/experimental/media_api.py) | [`frontend/src/novel/MotionTaskWorkspace.tsx`](../../frontend/src/novel/MotionTaskWorkspace.tsx); [`frontend/src/novel/MotionPrivacyPanel.tsx`](../../frontend/src/novel/MotionPrivacyPanel.tsx); [`frontend/src/novel/VideoAssemblyPanel.tsx`](../../frontend/src/novel/VideoAssemblyPanel.tsx); `frontend/src/App.tsx:1890`; `frontend/src/novel/VideoTaskInspector.tsx:22` | EXTERNAL_REAL_MODELS; FINAL_SOURCE_CI; current execution NOT_RUN; original scope/version/review required. Real model/GPU/quality LOCAL_REQUIRED. |
| CORE_AUDIO — Audio / TTS / BGM / Ambience / SFX | PARTIAL; [`app/services/audiobook_service.py`](../../app/services/audiobook_service.py); [`app/audio_production_store.py`](../../app/audio_production_store.py); [`app/audio_providers.py`](../../app/audio_providers.py); [`app/api.py`](../../app/api.py); API [`app/api.py`](../../app/api.py) | [`frontend/src/novel/AudioGenerationPanel.tsx`](../../frontend/src/novel/AudioGenerationPanel.tsx); [`frontend/src/novel/AudioTaskInspector.tsx`](../../frontend/src/novel/AudioTaskInspector.tsx); [`frontend/src/novel/SpeechSynthesisPanel.tsx`](../../frontend/src/novel/SpeechSynthesisPanel.tsx); `frontend/src/ui/ModuleWorkspaceRoutes.tsx:64`; `frontend/src/ui/ModuleWorkspaceRoutes.tsx:70` | EXTERNAL_REAL_MODELS; FINAL_SOURCE_CI; current execution NOT_RUN; original scope/version/review required. Real model/GPU/quality LOCAL_REQUIRED. |
| CORE_ASSETS — Asset library / References / Integrity | PARTIAL; [`app/services/asset_library_service.py`](../../app/services/asset_library_service.py); [`app/asset_lifecycle_api.py`](../../app/asset_lifecycle_api.py); [`app/media_files.py`](../../app/media_files.py); [`app/services/v1_capability_service.py`](../../app/services/v1_capability_service.py); API [`app/asset_lifecycle_api.py`](../../app/asset_lifecycle_api.py); [`app/api.py`](../../app/api.py) | [`frontend/src/novel/AssetLibraryPanel.tsx`](../../frontend/src/novel/AssetLibraryPanel.tsx); [`frontend/src/novel/AssetInspector.tsx`](../../frontend/src/novel/AssetInspector.tsx); [`frontend/src/novel/VisualReferencePanel.tsx`](../../frontend/src/novel/VisualReferencePanel.tsx); `frontend/src/App.tsx:1893`; `frontend/src/creative/IndependentStudioWorkspace.tsx:492` | FINAL_SOURCE_CI; current execution NOT_RUN; original scope/version/review required. |
| CORE_MODELS — Model Center / Provider configuration | PARTIAL; [`app/model_center/service.py`](../../app/model_center/service.py); [`app/model_center/domain.py`](../../app/model_center/domain.py); [`app/model_center/discovery.py`](../../app/model_center/discovery.py); [`app/model_center/runtime_profiles.py`](../../app/model_center/runtime_profiles.py); API [`app/model_center/api.py`](../../app/model_center/api.py); [`app/model_center/discovery_api.py`](../../app/model_center/discovery_api.py) | [`frontend/src/ui/ModelCenter.tsx`](../../frontend/src/ui/ModelCenter.tsx); [`frontend/src/ui/AiControlCenter.tsx`](../../frontend/src/ui/AiControlCenter.tsx); [`frontend/src/ui/MediaProviderSettings.tsx`](../../frontend/src/ui/MediaProviderSettings.tsx); `frontend/src/ui/ModuleWorkspaceRoutes.tsx:51`; `frontend/src/App.tsx:1898` | FINAL_SOURCE_CI; current execution NOT_RUN; original scope/version/review required. |
| CORE_EXPORT — Export / History / Snapshot preflight | PARTIAL; [`app/services/export_job_service.py`](../../app/services/export_job_service.py); [`app/services/export_snapshot_authority.py`](../../app/services/export_snapshot_authority.py); [`app/manuscript_sources.py`](../../app/manuscript_sources.py); [`app/export_formats.py`](../../app/export_formats.py); API [`app/api.py`](../../app/api.py) | [`frontend/src/novel/ExportPanel.tsx`](../../frontend/src/novel/ExportPanel.tsx); `frontend/src/App.tsx:1894` | FINAL_SOURCE_CI; current execution NOT_RUN; original scope/version/review required. Actual target application/native export LOCAL_REQUIRED. |
| CORE_COLLAB — Workspace / Membership / Permissions | PARTIAL; [`app/services/collaboration_scope_service.py`](../../app/services/collaboration_scope_service.py); [`app/services/authorization_service.py`](../../app/services/authorization_service.py); [`app/collaboration_admin.py`](../../app/collaboration_admin.py); [`app/application/collaboration_service.py`](../../app/application/collaboration_service.py); API [`app/collaboration_api.py`](../../app/collaboration_api.py); [`app/api.py`](../../app/api.py) | [`frontend/src/WorkspaceManagement.tsx`](../../frontend/src/WorkspaceManagement.tsx); [`frontend/src/PermissionManagement.tsx`](../../frontend/src/PermissionManagement.tsx); [`frontend/src/CollaborationPanels.tsx`](../../frontend/src/CollaborationPanels.tsx); `frontend/src/CollaborationPanels.tsx:8`; `frontend/src/CollaborationPanels.tsx:10` | BLOCKED release gate: frozen known incarnation authorization defect; no security candidate inspected or tested. FINAL_SOURCE_CI; current execution NOT_RUN; original scope/version/review required. |
| FS_BRANCH — Branch manuscript / Fork / Compare / Human merge | PARTIAL; [`app/services/branch_manuscript_service.py`](../../app/services/branch_manuscript_service.py); [`app/repositories/branch_manuscript.py`](../../app/repositories/branch_manuscript.py); [`app/experimental/branch_manuscript_composition.py`](../../app/experimental/branch_manuscript_composition.py); [`app/manuscript_sources.py`](../../app/manuscript_sources.py); API [`app/experimental/branch_manuscript_api.py`](../../app/experimental/branch_manuscript_api.py) | [`frontend/src/experimental/BranchManuscriptPanel.tsx`](../../frontend/src/experimental/BranchManuscriptPanel.tsx); [`frontend/src/experimental/ProjectForksPanel.tsx`](../../frontend/src/experimental/ProjectForksPanel.tsx); `frontend/src/experimental/ExperimentalWorkbench.tsx:84`; `frontend/src/experimental/ExperimentalWorkbench.tsx:85` | FINAL_SOURCE_CI; current execution NOT_RUN; original scope/version/review required. |
| FS_REALTIME — Realtime protocol / Presence / Co-edit inspector | PARTIAL; [`app/experimental/writer_room_realtime.py`](../../app/experimental/writer_room_realtime.py); [`app/experimental/writer_room.py`](../../app/experimental/writer_room.py); [`app/experimental/writer_room_api.py`](../../app/experimental/writer_room_api.py); API [`app/experimental/writer_room_api.py`](../../app/experimental/writer_room_api.py) | [`frontend/src/experimental/WriterRoomPanel.tsx`](../../frontend/src/experimental/WriterRoomPanel.tsx); `frontend/src/experimental/ExperimentalWorkbench.tsx:87` | FORMAL_NEW_INSPECTORS; EXTERNAL_PRODUCTION_TRANSPORT; FINAL_SOURCE_CI; current execution NOT_RUN; original scope/version/review required. |
| FS_SEMANTIC — Semantic / Hybrid retrieval and indexes | PARTIAL; [`app/experimental/embeddings.py`](../../app/experimental/embeddings.py); [`app/experimental/vector_index.py`](../../app/experimental/vector_index.py); [`app/experimental/embeddings_api.py`](../../app/experimental/embeddings_api.py); API [`app/experimental/embeddings_api.py`](../../app/experimental/embeddings_api.py) | [`frontend/src/experimental/EmbeddingPanel.tsx`](../../frontend/src/experimental/EmbeddingPanel.tsx); `frontend/src/experimental/ExperimentalWorkbench.tsx:108` | EXTERNAL_REAL_MODELS; FINAL_SOURCE_CI; current execution NOT_RUN; original scope/version/review required. Real model/GPU/quality LOCAL_REQUIRED. |
| FS_VISUAL — Visual Identity / Similarity / Drift | PARTIAL; [`app/experimental/visual_identity.py`](../../app/experimental/visual_identity.py); [`app/experimental/embeddings.py`](../../app/experimental/embeddings.py); [`app/experimental/review_adapter_jobs.py`](../../app/experimental/review_adapter_jobs.py); [`app/experimental/review_adapter_projection.py`](../../app/experimental/review_adapter_projection.py); API [`app/experimental/embeddings_api.py`](../../app/experimental/embeddings_api.py); [`app/api.py`](../../app/api.py) | [`frontend/src/novel/VisualReferencePanel.tsx`](../../frontend/src/novel/VisualReferencePanel.tsx); [`frontend/src/novel/VisualContextPanel.tsx`](../../frontend/src/novel/VisualContextPanel.tsx); `frontend/src/novel/AssetInspector.tsx:65`; `frontend/src/ui/ModuleWorkspaceRoutes.tsx:62` | FORMAL_NEW_INSPECTORS; EXTERNAL_REAL_MODELS; FINAL_SOURCE_CI; current execution NOT_RUN; original scope/version/review required. Real model/GPU/quality LOCAL_REQUIRED. |
| FS_SYNC — Production sync / Manifest / Device / Checkpoint | PARTIAL; [`app/experimental/offline_sync_production.py`](../../app/experimental/offline_sync_production.py); [`app/experimental/offline_sync.py`](../../app/experimental/offline_sync.py); [`app/experimental/offline_sync_api.py`](../../app/experimental/offline_sync_api.py); API [`app/experimental/offline_sync_api.py`](../../app/experimental/offline_sync_api.py) | [`frontend/src/experimental/OfflineSyncPanel.tsx`](../../frontend/src/experimental/OfflineSyncPanel.tsx); `frontend/src/experimental/ExperimentalWorkbench.tsx:86` | FORMAL_NEW_INSPECTORS; EXTERNAL_PRODUCTION_TRANSPORT; FINAL_SOURCE_CI; current execution NOT_RUN; original scope/version/review required. |
| FS_RESEARCH_VISION — OCR / Scanned PDF / Image / Chart / Table | PARTIAL; [`app/experimental/research_vision.py`](../../app/experimental/research_vision.py); [`app/experimental/review_adapter_jobs.py`](../../app/experimental/review_adapter_jobs.py); [`app/experimental/review_adapter_projection.py`](../../app/experimental/review_adapter_projection.py); [`app/experimental/research_library.py`](../../app/experimental/research_library.py); API [`app/experimental/research_library_api.py`](../../app/experimental/research_library_api.py) | [`frontend/src/experimental/ResearchLibraryPanel.tsx`](../../frontend/src/experimental/ResearchLibraryPanel.tsx); `frontend/src/experimental/ExperimentalWorkbench.tsx:81` | FORMAL_NEW_INSPECTORS; EXTERNAL_REAL_MODELS; FINAL_SOURCE_CI; current execution NOT_RUN; original scope/version/review required. Real model/GPU/quality LOCAL_REQUIRED. |
| FS_PROCESSING — ASR / Forced alignment / Burn-in adapters | PARTIAL; [`app/experimental/subtitle_processing.py`](../../app/experimental/subtitle_processing.py); [`app/experimental/subtitle_timeline.py`](../../app/experimental/subtitle_timeline.py); [`app/experimental/subtitle_timeline_api.py`](../../app/experimental/subtitle_timeline_api.py); API [`app/experimental/subtitle_timeline_api.py`](../../app/experimental/subtitle_timeline_api.py) | [`frontend/src/experimental/SubtitleTimelinePanel.tsx`](../../frontend/src/experimental/SubtitleTimelinePanel.tsx); `frontend/src/experimental/ExperimentalWorkbench.tsx:110` | FORMAL_NEW_INSPECTORS; EXTERNAL_REAL_MODELS; FINAL_SOURCE_CI; current execution NOT_RUN; original scope/version/review required. Real model/GPU/quality LOCAL_REQUIRED. |
| FS_ENGINES — Godot / Ren'Py export adapters | PARTIAL; [`app/experimental/interactive_story.py`](../../app/experimental/interactive_story.py); [`app/experimental/interactive_story_api.py`](../../app/experimental/interactive_story_api.py); API [`app/experimental/interactive_story_api.py`](../../app/experimental/interactive_story_api.py) | [`frontend/src/experimental/InteractiveStoryPanel.tsx`](../../frontend/src/experimental/InteractiveStoryPanel.tsx); `frontend/src/experimental/ExperimentalWorkbench.tsx:89` | EXTERNAL_TARGETS; FINAL_SOURCE_CI; current execution NOT_RUN; original scope/version/review required. Actual target application/native export LOCAL_REQUIRED. |
| FS_SDK — Model / Import / Export Adapter SDK | PARTIAL; [`app/experimental/declarative_adapter_sdk.py`](../../app/experimental/declarative_adapter_sdk.py); [`app/experimental/declarative_agents.py`](../../app/experimental/declarative_agents.py); [`app/experimental/media.py`](../../app/experimental/media.py); [`app/experimental/imports.py`](../../app/experimental/imports.py); API [`app/experimental/declarative_agents_api.py`](../../app/experimental/declarative_agents_api.py); [`app/experimental/media_api.py`](../../app/experimental/media_api.py) | [`frontend/src/novel/PluginManagerPanel.tsx`](../../frontend/src/novel/PluginManagerPanel.tsx); [`frontend/src/novel/PluginInspector.tsx`](../../frontend/src/novel/PluginInspector.tsx); [`frontend/src/experimental/DeclarativeAgentsPanel.tsx`](../../frontend/src/experimental/DeclarativeAgentsPanel.tsx); `frontend/src/ui/ModuleWorkspaceRoutes.tsx:66`; `frontend/src/ui/ModuleWorkspaceRoutes.tsx:70` | FINAL_SOURCE_CI; current execution NOT_RUN; original scope/version/review required. |
| FS_UNIVERSE — Shared Universe / Selected snapshots | PARTIAL; [`app/experimental/project_forks.py`](../../app/experimental/project_forks.py); [`app/experimental/structured_forks.py`](../../app/experimental/structured_forks.py); [`app/experimental/project_forks_api.py`](../../app/experimental/project_forks_api.py); API [`app/experimental/project_forks_api.py`](../../app/experimental/project_forks_api.py) | [`frontend/src/experimental/SharedUniversePanel.tsx`](../../frontend/src/experimental/SharedUniversePanel.tsx); `frontend/src/experimental/ProjectForksPanel.tsx:51` | FINAL_SOURCE_CI; current execution NOT_RUN; original scope/version/review required. |
| FS_INTERACTION — Command Palette / Keyboard / Accessibility preferences | PARTIAL; [`app/experimental/workspace_interaction.py`](../../app/experimental/workspace_interaction.py); [`app/experimental/ux.py`](../../app/experimental/ux.py); [`app/experimental/ux_api.py`](../../app/experimental/ux_api.py); API [`app/experimental/ux_api.py`](../../app/experimental/ux_api.py) | [`frontend/src/experimental/WorkspaceInteractionPanel.tsx`](../../frontend/src/experimental/WorkspaceInteractionPanel.tsx); [`frontend/src/experimental/WorkspaceToolsPanel.tsx`](../../frontend/src/experimental/WorkspaceToolsPanel.tsx); `frontend/src/experimental/WorkspaceToolsPanel.tsx:93`; `frontend/src/experimental/ExperimentalWorkbench.tsx:100` | FINAL_SOURCE_CI; current execution NOT_RUN; original scope/version/review required. |
| CORE_INTEROP — Frozen PoemSeed Local Interop 1.0 | PARTIAL; [`app/local_interop/api.py`](../../app/local_interop/api.py); [`app/local_interop/transport.py`](../../app/local_interop/transport.py); [`app/local_interop/host.py`](../../app/local_interop/host.py); [`app/local_interop/desktop.py`](../../app/local_interop/desktop.py); API [`app/local_interop/api.py`](../../app/local_interop/api.py) | [`frontend/src/interop/entry.tsx`](../../frontend/src/interop/entry.tsx); [`frontend/src/interop/DesktopIntegrationDetails.tsx`](../../frontend/src/interop/DesktopIntegrationDetails.tsx); [`frontend/src/interop/LocalTutorIntegration.tsx`](../../frontend/src/interop/LocalTutorIntegration.tsx); `frontend/src/interop/LocalTutorIntegration.tsx:441` | Frozen protocol retained; QingJian work explicitly paused/out of scope. FINAL_SOURCE_CI; current execution NOT_RUN; original scope/version/review required. |
| CORE_AUTOMATION — Original Agent / Workflow execution | PARTIAL; [`app/services/agent_job_service.py`](../../app/services/agent_job_service.py); [`app/workflow_api.py`](../../app/workflow_api.py); [`app/workflow.py`](../../app/workflow.py); [`app/api.py`](../../app/api.py); API [`app/api.py`](../../app/api.py); [`app/workflow_api.py`](../../app/workflow_api.py) | [`frontend/src/novel/AgentActivityCenter.tsx`](../../frontend/src/novel/AgentActivityCenter.tsx); [`frontend/src/novel/AgentJobDetail.tsx`](../../frontend/src/novel/AgentJobDetail.tsx); [`frontend/src/novel/AgentTeamPanel.tsx`](../../frontend/src/novel/AgentTeamPanel.tsx); `frontend/src/App.tsx:1888`; `frontend/src/novel/AgentTeamPanel.tsx:299` | FINAL_SOURCE_CI; current execution NOT_RUN; original scope/version/review required. |
| CORE_ADAPTATION — Adaptation / Blueprint / Screenplay draft | PARTIAL; [`app/services/adaptation_service.py`](../../app/services/adaptation_service.py); [`app/services/screenplay_service.py`](../../app/services/screenplay_service.py); [`app/experimental/adaptation_projection.py`](../../app/experimental/adaptation_projection.py); [`app/repositories/adaptation_versions.py`](../../app/repositories/adaptation_versions.py); API [`app/api.py`](../../app/api.py); [`app/adaptation_api.py`](../../app/adaptation_api.py) | [`frontend/src/novel/AdaptationPanel.tsx`](../../frontend/src/novel/AdaptationPanel.tsx); [`frontend/src/novel/ScreenplayPipelinePanel.tsx`](../../frontend/src/novel/ScreenplayPipelinePanel.tsx); [`frontend/src/novel/PipelineStatusPanel.tsx`](../../frontend/src/novel/PipelineStatusPanel.tsx); `frontend/src/App.tsx:1889`; `frontend/src/novel/ScreenplayPanel.tsx:123` | ADAPTATION_UNKNOWN_CREATION_RECOVERY; EXTERNAL_REAL_MODELS; FINAL_SOURCE_CI; current execution NOT_RUN; original scope/version/review required. |


## Next dependency sequence

1. Independently review the mounted Director source/Graph integration and preserve exact test receipts.
2. Extend grouping/collapse rendering and presentation contracts through an existing owner; viewport/position persistence already exists and explicit auto-layout apply is now wired. Preserve original conflict recovery and execution budgets.
3. Build on the bounded culling and MiniMap slices for LOD and real-browser measurement; existing 1000/10000 display-object geometry timings are not browser interaction/memory acceptance.
4. Extend explicit reviewed suggestions to original Shot/Prompt/task/timeline owners, preserving versions, cost/privacy previews, cancellation and UNKNOWN semantics.
5. Resume other A/B/U and FS/CORE gaps by dependency; preserve P0 HOLD, PUBLIC physical exclusion and final Windows/GPU/browser/model gates.

### 2026-10-16 increment: same-graph selection copy preview

P1 canvas remains PARTIAL. Added explicit exact-draft/owner-bound copy preview and atomic same-graph paste through original Graph history/save/CAS; new IDs/internal edges, excluded-boundary warning, exact source pins and original limits retained. 226 targeted mocked UI/contract/geometry checks, two nonsecurity File and 30 PUBLIC checks pass; build/token/487-file closure pass. Cross-canvas/project clipboard, nested subgraphs and browser acceptance remain open. See [report](canvas-selection-copy-20261016.md) and [evidence](canvas-selection-copy-20261016.json). No backend, security, execution or budget changes; P0 BLOCKED / R3-GATE HOLD unchanged. Local commit only; no cost-unknown hosted CI/push.

### 2026-10-16 increment: same-project cross-graph selection copy

P1 / GRAPH-05 remains PARTIAL. Explicit clean-saved source capture now survives guarded switches between saved graphs within the same owner/client/project/scope. Target preview checks equal schema, existing catalog kinds/typed connections, exact pins and original budgets, then explicit atomic paste uses one original history/save/CAS step. No OS clipboard, cross-project/user/scope transport, backend/security/store/budget expansion or execution. 254 targeted mocked UI/pure/geometry checks, three nonsecurity File and 30 PUBLIC checks pass; build/discovery/token/487-file closure pass. [Report](canvas-cross-graph-copy-20261016.md) and [evidence](canvas-cross-graph-copy-20261016.json). Cross-schema/project interchange, durable recovery and real browser acceptance remain open. P0 BLOCKED / R3-GATE HOLD and no cost-unknown push/hosted CI unchanged.

### 2026-10-16 increment: explicit graph view preferences

P1 canvas remains PARTIAL. Optional bounded grid/snap/8–32-step/MiniMap metadata now uses original Graph presentation owner, explicit draft add/remove, one undo step and original save/CAS/reopen. Temporary controls remain clean; exact owner/loaded-record refresh and undo restore saved settings/defaults. Collapse stays session-only. Legacy omission/canonical digests and execution projection/budgets unchanged. 210 selected mocked UI/transport/geometry and 81 Python (50 pure, one File, 30 PUBLIC) checks pass; build/discovery/token/487-file closure pass. [Report](canvas-view-preferences-20261016.md), [evidence](canvas-view-preferences-20261016.json). Real browser/visual/performance and full RC remain NOT_RUN; P0 BLOCKED / R3-GATE HOLD unchanged. Local only, no cost-unknown hosted CI/push.

### 2026-10-16 increment: exact asset-to-image draft handoff

Independent IMAGE asset use remains PARTIAL overall. AssetBrowser IMAGE now opens the original guarded production workspace, requires explicit existing I2I operation, reviews exact metadata and rereads before original-owner source insertion. Modern empty base slot or original bounded legacy references, source/client/draft/config/busy ABA, UNKNOWN and original preview/cloud-consent invalidation preserved. No generation, new runtime/backend, automatic configuration or second authoritative draft. 111 mocked UI/contract and 30 PUBLIC tests pass; type/build/token/discovery/487-file closure pass. [Report](asset-image-handoff-20261016.md), [evidence](asset-image-handoff-20261016.json). VIDEO/STORYBOARD and durable draft recovery remain open; Unified DeliveryCenter entitlement producer BLOCKED. P0 BLOCKED / R3-GATE HOLD unchanged; no cost-unknown push or hosted CI, browser/GPU/provider/user-machine/full RC not run.

### 2026-10-16 increment: exact asset-to-video draft handoff

Independent VIDEO remains PARTIAL overall. Existing session-only media handoff now accepts explicit VIDEO targets through original dirty navigation; user-selected I2V/image or V2V/video exact metadata is reread before filling an empty original source slot. No operation/provider change, replacement, latest-version substitution, preview/queue/dispatch or new owner. Local V2V remains unsupported; original configured provider capability gates remain intact. Shared synchronous loading and original ABA/UNKNOWN fences preserve IMAGE/TIMELINE behavior. 242 mocked UI/contract and 30 PUBLIC checks pass; type/build/discovery/token/diff/487-file closure pass. [Report](asset-video-handoff-20261016.md), [evidence](asset-video-handoff-20261016.json). STORYBOARD/durable drafts and DeliveryCenter entitlement producer remain open/BLOCKED. P0 BLOCKED / R3-GATE HOLD unchanged; no cost-unknown push/CI or browser/GPU/user-machine/full RC.

### 2026-10-16 increment: original media task/candidate navigation and Storyboard audit

U07 task navigation remains PARTIAL. Explicit TaskCenter locate now reads exact recognized experimental MediaService task/candidate records through original GETs; candidate ID/version/source must match. Unsupported owners report unavailable without unrelated production/asset navigation. Original dirty/identity/read guards, duplicate suppression and late/ABA fences remain; no new queue, backend, mutation or authority. [Report](task-owner-navigation-20261016.md), [evidence](task-owner-navigation-20261016.json).

STORYBOARD asset reference draft handoff is BLOCKED: CreativeShot has no reference-draft field and its workspace is read-only. Existing image-binding POST is an immediate versioned owner write that removes approval, not the requested unsaved edit; it remains unchanged. No fake draft attachment or replacement grant. P0 BLOCKED / R3-GATE HOLD; no cost-unknown push/hosted CI or browser/GPU/user-machine/full RC.

### 2026-10-16 increment: Judge evidence to original paragraph revision

A03/A11 remain PARTIAL. Same-saved-chapter explicit evidence handoff now reuses the original A11 panel, source/selection reads, manually authored candidate, diff, human accept/reject, original CAS and history. Exact run/finding/evidence versions and raw Markdown Unicode quote/paragraph locations are checked; authors select original PM paragraphs explicitly, including duplicate text. No offset guessing, semantic-truth claim, model invocation, automatic finding approval, backend/schema/security change or new owner. Source references are editable existing goal notes, not a second lineage authority. Client/content/dirty/feature ABA and failed rereads invalidate old context while preserving blocked typed candidates. [Report](judge-revision-handoff-20261016.md), [evidence](judge-revision-handoff-20261016.json). 105 mocked UI/pure, six nonsecurity File, five Python Unicode and 30 PUBLIC checks pass; forced type/build/token/discovery/487-file closure pass. Browser/HTTP integration/real model/Windows/GPU/full RC NOT_RUN; P0 BLOCKED, R3-GATE HOLD, Prompt Adoption disabled. No cost-unknown push or hosted CI.

## B04 bounded subtitle file handoff preflight — 2026-10-16

**PARTIAL:** existing caption save/SRT/VTT and original Timeline import already work through their respective owners. Added actionable local preflight in the original subtitle editor: exact rational milliseconds, source/dirty state, Unicode/speaker-inclusive target limits, overlap/range issues, focus-to-cue and explicit metadata-loss disclosure. No duplicate export or direct cross-owner source binding. Original preview/confirmation/CAS/UNKNOWN stays authoritative. Report/evidence: `subtitle-transfer-preflight-20261016.md` / `.json`. Direct track/version provenance, mapping into trimmed/speed-adjusted Timeline media, cross-owner rollback, caption durable unsaved recovery and UNKNOWN/history UI remain open. Model alignment quality and target software/browser/Windows/GPU acceptance NOT_RUN; P0 BLOCKED and all prior gates unchanged.

## B05 saved terminology issue navigation — 2026-10-16

**PARTIAL:** original multilingual save/source/glossary/review/translation/memory contracts already exist. Closed the count-only review gap with bounded exact-segment navigation, whole-editor focus and original rule/version/lock evidence; edits and acceptance remain explicit through the original owner. No guessed Unicode positions, automatic replacement or second consistency engine. 41 mock UI checks, three original nonsecurity File cases, one Unicode case and 30 PUBLIC checks pass; type/build/discovery/token/487-file closure are indexed in `terminology-issue-navigation-20261016.json`, report beside it. Browser/real model/language quality/Windows/GPU/full RC NOT_RUN; P0 BLOCKED and previous gates unchanged. Local commit only, no cost-unknown push/hosted CI.

## B06 content-preserving manual arrangement — 2026-10-16

**PARTIAL:** audited existing comic page/panel/text owner, approved source snapshots, raster preflight, approval/export and history. Added explicit bounded vertical coordinate preview → one original local edit → undo/save/reopen. Existing sizes, text, exact asset pins and source references stay intact; bubbles translate with panels. Invalid order/IDs/numbers, bubble inset or page-fit failures block application without destructive preset reset. No second owner, raster/export engine, provider or authority change. 37 mock/pure checks, four nonsecurity File and 30 PUBLIC checks; final type/build/token/discovery/487-file closure indexed in `comic-arrangement-20261016.json`, report beside it. Browser/native/real model/art quality/Windows/GPU/full RC NOT_RUN; P0 BLOCKED and prior gates preserved. Local commit only; parent independent review before next feature, no cost-unknown push or CI.

## B07 saved interactive-story issue navigation — 2026-10-16

**PARTIAL:** original finite replay, typed conditions, source pins, versioned history, review and standalone Ren'Py/neutral/Godot-data exports already exist. Closed the plain-text analysis gap with twenty-row saved-version issues and exact original node/choice editor focus, preserving dirty text and explicit save. Missing/ambiguous/malformed/wrong-parent/replaced identities, active IME, busy/archive and identity/revision changes remain guarded. No second engine, parser, backend, permission, autosave or automatic approval/export. 24 mocked UI, four nonsecurity File-fixture cases, one pure bounded-state case and 30 PUBLIC checks pass; final type/build/token/discovery/487-file closure indexed in `interactive-issue-navigation-20261016.json`, report beside it. Target engines/browser/native IME/HTTP/Windows/GPU/full RC NOT_RUN. P0 BLOCKED and previous gates unchanged; local only, no cost-unknown push/CI.

## A09 exact saved-reference inspection — 2026-10-16

**PARTIAL:** existing asset relationship persistence and project graph were reused. Saved kind/ID/version/digest can now be explicitly compared against the original current directory; exact asset opening requires the original dirty navigation guard and a second original-owner GET. Mismatches never upgrade pins; unavailable/ambiguous/failed reads and identity/target/busy ABA cannot reuse inspection. Chapter/screenplay metadata-only and missing original lineage history stay explicit. The existing graph filters direct incoming recorded relationships with incomplete-coverage disclosure; full Shot/Prompt/Timeline impact remains open. 62 mocked UI, four original nonsecurity File-owner and 30 PUBLIC checks pass; forced type/build/token/discovery/487-file closure indexed in `asset-lineage-reference-navigation-20261016.json`, report beside it. Actual full-chain quality/browser/native/HTTP/Windows/GPU/provider/full RC NOT_RUN. No backend/lifecycle/authority/adoption write or new store/queue. P0 BLOCKED, R3-GATE HOLD and no cost-unknown push/CI unchanged.

Independent review correction: exact relationship selection temporarily closes current asset browsers until explicit return; source-selection epoch plus original form revision invalidates batched A→B→A inspection. No frozen browser mount contract changed.

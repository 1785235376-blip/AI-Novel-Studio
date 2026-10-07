# Final Product Surface Map

Status: **SOURCE_MAP_REVIEW_PENDING**. This map describes the active Feature Completion worktree, not a verified final release. Starting SHA: `6dc09ffc71ba47b6730df491186bfce429f0721a`. Observed checkpoint: `d9d2df3a0a831a5bba6249793fd21946c17ce7d4`. Branch: `work/feature-completion-surface-freeze`. Draft [PR #45](https://github.com/1785235376-blip/AI-Novel-Studio/pull/45). Exact final SHA and hosted results are **PENDING**.

No functional-freeze candidate or formal freeze is declared here. Implemented original-owner closures and remaining integration/environment boundaries are distinguished below. Only the user can decide to enter the final Opus UI phase after reviewing the completed evidence.

## Read this map correctly

- Exactly ten final product areas: **Write, Story, Review, Research, Production, Assets, Collaboration, Models, Tasks, Settings**. No eleventh top-level module is planned.
- These are logical product areas for the eventual information architecture. Current `moduleRegistry.tsx` still renders its existing NOVEL/IMAGE/VIDEO/ASSETS/AUDIO/CONTROL/PLUGIN/WORKFLOW entries through one AppShell. This pass does not redesign that protected shell or pretend ten new tabs already exist.
- 73 named functional surfaces map the original forty packages plus existing core authorities and additive completion seams. A surface is a page/subpage/inspector/contract, **not another package or data store**.
- Actual mounted routes: [API_CATALOG.json](API_CATALOG.json), [API_CATALOG.md](API_CATALOG.md), [API_CATALOG_DETAIL.json.gz](API_CATALOG_DETAIL.json.gz) and [API_OPENAPI.json.gz](API_OPENAPI.json.gz). Source hashes and tests/test_surface_api_catalog.py check inventory consistency; an API inventory is not a runtime verification verdict.
- Full machine-readable pages, components, exact source routes, schema fields, actions, permissions, flags/dependencies, lifecycle, states, tests and requirement links: [`UI_SURFACE_CATALOG.json`](UI_SURFACE_CATALOG.json). Readable route inventory: [`UI_SURFACE_CATALOG.md`](UI_SURFACE_CATALOG.md). Current status matrix: [`FUNCTIONAL_SURFACE_MATRIX.md`](FUNCTIONAL_SURFACE_MATRIX.md) and [`FUNCTIONAL_SURFACE_MATRIX.json`](FUNCTIONAL_SURFACE_MATRIX.json).
- All 406 original nonempty requirement lines retain their exact text and source-line identity in the delivery requirements register. The 24 UX requirements and 12 creative domains are expanded below; no heading or repeated requirement was silently dropped.
- `PARTIAL` is implementation scope. `CONTRACT_VERIFIED`, `MOCK_ONLY`, `REAL_VERIFIED`, `LOCAL_REQUIRED`, `NOT_RUN`, `BLOCKED` describe different evidence boundaries. A file existing, an endpoint registered or a test collected is not a passing test.
- Every exact-final-head gate remains PENDING here. Read the lead's final delivery/test receipts for actual executed results. Real models/GPU, paid providers, production cloud/realtime and native/target-engine acceptance are not inferred from synthetic fixtures.
- Discovery schema v2 keeps legacy `features` stable and publishes complete `runtime_features` / `surface_features`; the actual runtime registry is `RUNTIME_FLAGS`, not historical `FLAGS`. Every new flag and dependency needs explicit opt-in.
- Original test bodies/assertions/node IDs/skips remain preserved. Reviewed fixture-only changes initialize genuine branches in the adaptation authorization test module and the isolated Interop browser-host script. Their whole-file hashes changed; original test bodies/assertions/node IDs/skips and original Interop HTTP/browser assertions remain unchanged. See `ADAPTATION_FIXTURE_EXCEPTION.json` / `.patch` and [Local Interop branch integration](docs/LOCAL_INTEROP_BRANCH_OWNER_INTEGRATION.md). Do not describe every historical fixture source as byte-identical. All other original tests and migrations 001–020 remain frozen; exact protected-file hashes are in [SOURCE_PRESERVATION.json](docs/delivery/functional-surface-freeze/SOURCE_PRESERVATION.json).
- Earlier d9d2 push/PR Frontend failures remain visible in [BROWSER_INTEGRATION_CORRECTIONS.md](docs/delivery/functional-surface-freeze/BROWSER_INTEGRATION_CORRECTIONS.md). New-browser route matching, active Story label, project-authorized mainline proof and explicit viewport fixes retain business/geometry assertions; corrected-head execution is PENDING.
- Local Chromium/socket execution was denied and real PostgreSQL is unavailable here. Hosted surface and separate branch-browser configurations are required; no local browser/PG PASS is claimed.
- Historical `POST_INTEROP_FEATURE_MATRIX.*`, F00 + 39 PARTIAL package accounting, frozen PR37 and PoemSeed Local Interop 1.0 evidence stay unchanged. Historical independent review stays **BLOCKED** and is not retried or relabelled by functional work.

## Product areas and existing navigation

| Final area | Existing hosts | Pages and subpages |
|---|---|---|
| Write | NOVEL editor, writing inspector, existing experimental workbench | U02: Manuscript / Save and recovery; U01: Continue Working / Workspace resume; U03: Global search / Recents; U08: Context inspector / Cost and privacy preview; U04: Focus / Reference split / Inspiration; U05: Selection assistant / Partial accept; U15: Writing goals / Session / Notices; B05: Translation / Memory / Terminology; CORE_MANUSCRIPT: Project / Chapter tree / Authoritative manuscript; CORE_GENERATION: AI writing / Draft-Diff-Accept / Recovery; FS_BRANCH: Branch manuscript / Fork / Compare / Human merge |
| Story | NOVEL StoryDatabase/world/planning and existing workbench | A04: Semantic Story Graph; A05: Character Mind / Viewpoint; A01: Story Simulator; CORE_CREATION: Creation workbench / Structured plans / Review threads; FS_PLANNING: Layered planning / Proposals / Templates; FS_CANON: Canon / Evidence / Pending decisions; FS_FORESHADOWING: Foreshadowing / Narrative progress; FS_TIMELINE: Story timeline / World chronology; FS_STORY_DATABASE: Characters / Locations / Relationships / World rules; FS_UNIVERSE: Shared Universe / Selected snapshots; CORE_ADAPTATION: Adaptation / Blueprint / Screenplay draft |
| Review | Original history/Draft-Diff-Accept, Continuity, existing unified inbox | U06: Change Impact / Selective refresh; A02: Style DNA / Drift / Opinions; A03: Narrative Judge / Finding review; A11: Revision Intelligence / Comparison; U11: Reader / Proofreading / Export preflight; FS_CONTINUITY: Continuity / Evidence / Author feedback; FS_REVIEW: Unified review inbox |
| Research | Original import/research and existing library/embedding workbench | A10: Library / Source / Notes / Citations; FS_IMPORT: Manuscript import / Import health / Extraction; FS_SEMANTIC: Semantic / Hybrid retrieval and indexes; FS_RESEARCH_VISION: OCR / Scanned PDF / Image / Chart / Table |
| Production | Existing IMAGE/VIDEO/AUDIO/script and production workbench | A13: Production manifest / Controlled replay; A08: Screenplay / Director / Shots; A12: Timeline / OTIO exchange; B03: Voice direction / Attribution / Audiobook; B04: Subtitles / Caption timeline; B06: Comics / Webtoon; B07: Interactive Story / Visual Novel; CORE_IMAGES: Image / Cover / Storyboard / Character reference / Edit / Multi-reference; CORE_SCREENPLAY: Screenplay / Scene / Shot authoring; CORE_VIDEO: Video / Motion / Assembly / Post; CORE_AUDIO: Audio / TTS / BGM / Ambience / SFX; CORE_EXPORT: Export / History / Snapshot preflight; FS_PROCESSING: ASR / Forced alignment / Burn-in adapters; FS_ENGINES: Godot / Ren'Py export adapters |
| Assets | Original AssetLibrary/reference inspector and portable recovery | A09: Lineage / Provenance; U14: Portable projects / Storage health / Relink; CORE_ASSETS: Asset library / References / Integrity; FS_VISUAL: Visual Identity / Similarity / Drift |
| Collaboration | Existing workspace/permission/WriterRoom/fork/offline surfaces | B08: Writer Room / Assignments / Comments; B09: Project Fork / Human Merge / Shared Universe; B10: Offline exchange / Reconciliation; CORE_COLLAB: Workspace / Membership / Permissions; FS_REALTIME: Realtime protocol / Presence / Co-edit inspector; FS_SYNC: Production sync / Manifest / Device / Checkpoint |
| Models | Original CONTROL/ModelCenter/discovery and model workbench | U09: Local AI diagnostics / Workflow inspection; A06: Model routing / Preflight / Cost preview; A07: Benchmarks / Capability evidence; CORE_MODELS: Model Center / Provider configuration |
| Tasks | Original Agent/Workflow and existing workspace task center | U07: Unified task center; U16: Safe batch / Cost preflight; B02: Agent SDK / Workflow SDK; CORE_AUTOMATION: Original Agent / Workflow execution |
| Settings | Existing entry/configuration/plugin/capability/local-interop/preferences surfaces | F00: Capabilities and feature dependencies; U12: Diagnostic preview / Export; U10: First Run / Onboarding / Practice project; U13: Accessibility / Input / Scale; B01: Template Library; FS_SDK: Model / Import / Export Adapter SDK; FS_INTERACTION: Command Palette / Keyboard / Accessibility preferences; CORE_INTEROP: Frozen PoemSeed Local Interop 1.0 |

## Unique authorities and navigation rules

1. Mainline prose stays in original ChapterService/ChapterRepository. Branch prose belongs to BranchManuscriptService and its scoped branch repository. Shared chapter readers select the owner from captured scope; absent branch authority never falls back to mainline.
2. ExperimentalStore is existing transactional metadata storage, not another manuscript/Canon/asset/job authority. File scope replacement and PostgreSQL scope row-lock transactions preserve existing ownership. Source receipts keep original IDs, versions and digests.
3. AssetLibrary, original Generation/Agent/Workflow/Image/Video/Audio/Export queues, Model Center/vault and original import/apply services remain unique. Tasks and Review are read-through projections with original-owner commands. New analysis/processing receipts are bounded owner metadata, not a generic worker service.
4. Actual user navigation binds current actor/project/workspace/storyline/branch, feature and source revision. Exact IDs include chapter/version/anchor; run/job; finding/opinion; source/paragraph/citation; index; asset; Scene/Shot; edition/segment; and fork/inbox record as applicable. Never replace an exact record link with a generic tab or use a stale response after a newer navigation.
5. On task/review navigation, resolve the original owner and render its original review/diff/recovery. Cancelling a lookup does not cancel the task. Hidden controls, a client role or knowledge of a record ID never grants access.
6. Privacy/source versions are rechecked at actual dispatch/publication. A preview must match the real request; already-sent bytes cannot be recalled. Research remains LOCAL_ONLY and cannot automatically become Canon. Character-only context cannot acquire author-only facts through a convenience panel.
7. Local Draft deliberately uses the browser Storage API and original chapter save/recovery service. No server copy of the local buffer is implied. Workspace preferences/resume are scoped metadata and contain no credential or manuscript copy.
8. `/api[/v1]` below means existing aliases, not a literal path. The separately generated mounted API catalog is authoritative for all concrete routes, including generated routes. Per-surface source lists allow exact navigation into the implementation.

## Shared state and lifecycle contract

These are minimum product rendering contracts. The JSON catalog gives every surface the state list and its owner-specific behavior; formal-only controls remain marked as such. They are not proof all UI/browser cases executed.

| State | Required behavior |
|---|---|
| Loading | Show loading and current captured scope; prevent duplicate mutation; do not erase recoverable draft. |
| Empty | Distinguish no authorized/current rows from no project, disabled owner and missing provider. Provide original create/import/select entry only when allowed. |
| Error | Show bounded original error code; preserve local intent; expose only applicable explicit retry/recovery. Never label a failed or unknown attempt successful. |
| Unauthorized | Render current-authority failure, stop in-flight navigation and suppress withdrawn source/result details. Browser roles are advisory. |
| NOT_CONFIGURED | Display missing provider/model/transport/adapter/configuration honestly; no implicit synthetic, lexical or mainline fallback. |
| Disabled | Explain server-owned flag/dependency/V1/permission or unsupported operation; UI cannot enable access by itself. |
| Conflict | Keep unsaved intent, show original expected/current revision or stale-source explanation; no silent overwrite/rebase/replay. |
| Review | Display exact original-owner source/result/version/evidence; require explicit allowed action. Review, approval and application remain separate. |
| Recovery | Show interrupted/corrupt/uncertain state and original history/journal; explicit recovery is not automatic retry. |
| PARTIAL | Keep capability and verification limitation next to the operation; local/contract/mock evidence never implies real model or target-platform acceptance. |
| Cancelled | Stop future publication through original attempt/token fences when supported; cancel a read only discards response, not a domain job. |
| Stale | Mark changed source/provider/index/record version and withhold affected adoption; retain permissible original history without leaking revoked content. |

Synchronous pure/transactional operations do not become fake asynchronous tasks to satisfy a checklist. Their Cancel means abort/discard before publication, their Restart means reread original durable state and revalidate, and their Resume is a fresh explicit original-owner action. Genuine jobs retain claim/attempt IDs, cancellation publication fences, interrupted/UNKNOWN state and explicit recovery. Resume never means automatically replay a non-idempotent or paid operation.

## All 24 UX functional requirements

| Requirement | Original surfaces / API kind | Actual behavior and boundary |
|---|---|---|
| FSR-268 Continue Working | U01, U02; original server/client API | Resolve saved project/chapter/anchor plus pending original tasks; do not auto-dispatch. |
| FSR-269 Workspace Resume | U01, U04; original server/client API | Restore versioned layout/reference pointers after current authority and dirty/IME guards. |
| FSR-270 Search | U03, FS_SEMANTIC; original server/client API | Literal search and semantic/hybrid query are labelled separately; resolve exact source revision before navigation. |
| FSR-271 Command Palette | FS_INTERACTION, U03; original server/client API | Finite workspace command catalog and revision-bound resolve; scoped keyboard navigation only, never a generic execution engine. |
| FSR-272 Unified Task Center | U07, FS_RESEARCH_VISION, FS_VISUAL; original server/client API | Project original owner IDs/status and cancel through current write/CAS authority; no second queue. Exact opening exists only where implemented; Research/visual receipt navigation remains formal-only without a generic open/retry/approve action. |
| FSR-273 Unified Review Inbox | FS_REVIEW, FS_RESEARCH_VISION, FS_VISUAL; original server/client API | Original domain review bindings retain source/creator permissions and distinct pending/approved/applied states. Adapter receipts have no generic or batch approval and no rendered exact-open control; formal targets remain labelled. |
| FSR-274 Context Inspector | U08; original server/client API | Actual request payload/context/source digest/omissions and current privacy/route, not an independent summary. |
| FSR-275 Save/Recovery | U02, CORE_MANUSCRIPT, FS_BRANCH, FS_STORY_DATABASE; original server/client API | Original document CAS and visible durable save state; current five-kind Story editors additionally use their original structured digest/version/history/restore owner. Uncertain outcomes are reread rather than replayed. |
| FSR-276 Local Draft | U02, FS_STORY_DATABASE, FS_TIMELINE, FS_FORESHADOWING; browser Storage API | Manuscript drafts retain original chapter/version owner; structured candidates use actor/workspace/project/branch/kind/record namespace. Access is rechecked before explicit recovery, secrets are excluded and no backend save is implied. |
| FSR-277 Conflict | U02, FS_BRANCH, A11, FS_STORY_DATABASE; original server/client API | Preserve local intent under original 409/428/version/source conflict. Five-kind Story forms retain structured candidates and require explicit latest-baseline/source refresh; prose compare/rebase/human merge stay with original owners. |
| FSR-278 Local AI Diagnostics | U09, CORE_MODELS; original server/client API | Detect/validate/register/enable/launch separated; missing model/runtime/adapter/license shown honestly. |
| FSR-279 Preflight | U08, A06, U16; original server/client API | Source, actual route, permission, capability and budget gates before execution; fresh recheck on dispatch. |
| FSR-280 Cost Preview | A06, U16, U08; original server/client API | Known quoted/measured costs only; unknown remains unknown and paid/uncertain routes are held. |
| FSR-281 Privacy Preview | U08, CORE_IMAGES, CORE_VIDEO; original server/client API | Exact source versions and destination/context exclusions; current revocation rechecked before egress. |
| FSR-282 Import Health | FS_IMPORT, A10, U14; original server/client API | Parser/format/truncation/source/citation/resource integrity checks and recoverable partial apply journal. |
| FSR-283 Export Preflight | U11, CORE_EXPORT, FS_ENGINES; original server/client API | Current review/source/resource/permission snapshot; target-engine acceptance remains distinct. |
| FSR-284 Diagnostic Export | U12; original server/client API | Bounded allowlisted preview-digest export; no raw logs, manuscript or credentials. |
| FSR-285 Asset Relink | U14, CORE_ASSETS; original server/client API | Original missing reference plus decoded replacement digest preflight; explicit owner mutation. |
| FSR-286 Missing Asset Repair | U14, CORE_ASSETS; original server/client API | Storage health distinguishes missing/corrupt/stale; exact validated recovery and retained journal. |
| FSR-287 First Run | U10; original server/client API | Original-authority isolated synthetic practice creation with durable pre-create receipts; interrupted unknown is not replayed. |
| FSR-288 Onboarding | U10, CORE_MODELS; original server/client API | Skip/reopen sample guide and progressive capabilities; manual writing remains available with models absent. |
| FSR-289 Accessibility States | U13, FS_INTERACTION; original server/client API | Labels/focus/live states/IME and versioned announcement/reduced-motion settings; native screen-reader NOT_RUN. |
| FSR-290 Keyboard Shortcuts | FS_INTERACTION, U13; original server/client API | Allowlisted unique Mod+Shift bindings, text-input/IME/repeat guards, scoped handler, persistent CAS/history. |
| FSR-291 Workspace Layout Persistence | U01, U04, FS_INTERACTION; original server/client API | Layout/search/task/reference/focus pointers are persisted and recovered through original owners. |

The Command Palette implementation is intentionally a finite, version-bound workspace-section command catalog; its shortcut listener is local to the active tools area and excludes text input/IME/repeats. It is not an app-wide arbitrary command runner. Accessibility preferences currently apply to their declared scope; actual Windows screen readers, physical IME and OS zoom remain LOCAL_REQUIRED/NOT_RUN.

## All 12 creative-intelligence lifecycle maps

Each domain below resolves the requested source version, provenance, history, review, recovery, cancel, task linkage, exact navigation, evidence, user feedback, intentional suppression, stale state and cross-module integration. An explicit non-job/non-detector boundary is not represented as an implemented generic task or suppression engine.

### Story Simulator (A01)

- **source version:** Chapter versions/digests, Scene, node version and context_digest
- **provenance:** Captured world/Canon/mind/knowledge/constraints plus actual route/job identity
- **history:** Versioned simulation row/history and route/step states
- **review:** Explicit candidate selection and planning proposal save; no manuscript/Canon auto-write
- **recovery:** Read persisted run, fresh context; UNKNOWN original model job reconciled by owner
- **cancel:** Versioned run cancel and original model cancel/late-publication fence
- **task linkage:** Original simulator model job projected by workspace owner; deterministic steps are synchronous
- **exact navigation:** Exact run ID/model record and original planning node
- **evidence:** Per-step assumptions, requirements, deltas, consequence/risk and source evidence
- **user feedback:** Explicit selected candidate/route and reviewed planning proposal
- **intentional suppression:** Not a repeating-finding detector; reject/unselect proposals rather than invent cross-run issue suppression
- **stale state:** Current source/context/node validation before step/save/select
- **cross module integration:** Story Graph + Character Mind + Canon + Planning + original Tasks/Review
- Evidence: [`app/experimental/story_simulator.py`](app/experimental/story_simulator.py), [`app/experimental/story_simulator_model.py`](app/experimental/story_simulator_model.py), [`frontend/src/experimental/StorySimulatorPanel.tsx`](frontend/src/experimental/StorySimulatorPanel.tsx), [`app/experimental/story_simulator_api.py`](app/experimental/story_simulator_api.py). Exact-final-head tests PENDING.

### Character Mind (A05)

- **source version:** World/graph record version, chapter order, Scene parent/position and source digest
- **provenance:** Original knowledge event + relation version; author evidence quotes not leaked into character projection
- **history:** WorldService record snapshots including previously approved forget tombstones
- **review:** Approve/reject/reopen/archive events through original domain.review
- **recovery:** Reopen/edit current event; persistent history, no automatic resurrection
- **cancel:** Abort read; synchronous event mutation has no fabricated background job
- **task linkage:** Character-only source context bound to original generation job; pure projection is not a task
- **exact navigation:** Original character/chapter/Scene/knowledge record identity
- **evidence:** Source record ID/version and evidence status; false belief distinct from author truth
- **user feedback:** Author edits/reviews explicit belief/secret/goal/intent events
- **intentional suppression:** Explicit FORGET/archived-event tombstones prevent old knowledge reappearing; not finding dedup
- **stale state:** Changed sources and uncertain/future/cross-parent events excluded
- **cross module integration:** Story Graph/Simulator/actual author-request preview and generation
- Evidence: [`app/experimental/story_graph.py`](app/experimental/story_graph.py), [`app/experimental/character_author_context.py`](app/experimental/character_author_context.py), [`app/experimental/author_context_api.py`](app/experimental/author_context_api.py), [`frontend/src/experimental/StoryGraphPanel.tsx`](frontend/src/experimental/StoryGraphPanel.tsx), [`frontend/src/novel/AiWritingPanel.tsx`](frontend/src/novel/AiWritingPanel.tsx). Exact-final-head tests PENDING.

### Semantic Story Graph (A04)

- **source version:** Original entity IDs plus chapter/Scene/version/digest and semantic dependencies
- **provenance:** Typed relation layer, author/character perspective and captured evidence
- **history:** Original WorldService history and graph-index versions
- **review:** Original approve/reject/reopen/archive per record
- **recovery:** Explicit edit/reopen/recompute; persisted records/index, no auto inference
- **cancel:** Abort query/recompute response; synchronous finite transaction has no fake task
- **task linkage:** Read projection for actual author context and Simulator; no graph worker invented
- **exact navigation:** Typed source record/entity/chapter/Scene IDs via exact search resolve
- **evidence:** Reviewed relation evidence, chapter quote/range, original source record versions
- **user feedback:** Explicit relation edits and review transitions
- **intentional suppression:** Archive/reject relations and retain knowledge tombstones; no recurring issue detector here
- **stale state:** Atomic affected-index invalidation/recompute and source-current projections
- **cross module integration:** Character Mind/Canon/Planning/Research citations/Change Impact/Search
- Evidence: [`app/experimental/world.py`](app/experimental/world.py), [`app/experimental/story_graph.py`](app/experimental/story_graph.py), [`app/experimental/story_graph_api.py`](app/experimental/story_graph_api.py), [`frontend/src/experimental/StoryGraphPanel.tsx`](frontend/src/experimental/StoryGraphPanel.tsx), [`app/experimental/world_api.py`](app/experimental/world_api.py). Exact-final-head tests PENDING.

### Style DNA (A02)

- **source version:** STYLE version/digest plus exact chapter/sample range versions
- **provenance:** Deterministic method version separate from model identity/rubric/job receipt
- **history:** Original creation STYLE history and analysis/model assessment review_history
- **review:** Opinion review/ignore/reopen with reason and CAS; raw metrics remain measurements
- **recovery:** Persisted analysis; refresh/reconcile original model job, no auto dispatch
- **cancel:** Original model cancel; synchronous deterministic analysis can only discard response
- **task linkage:** Exact style model job in original task center
- **exact navigation:** Analysis ID, opinion ID, STYLE ID and chapter/sample range
- **evidence:** Bounded exact quote/range and metric method; no literary percentage fabrication
- **user feedback:** Opinion reason/review history and STYLE instructions editing
- **intentional suppression:** Ignore/reopen is scoped to original opinion; no cross-source cross-run suppression claim
- **stale state:** Profile or sample change makes analysis unavailable for current use
- **cross module integration:** Original STYLE generation context + Tasks + Revision comparison
- Evidence: [`app/experimental/style_analysis.py`](app/experimental/style_analysis.py), [`app/experimental/style_analysis_model.py`](app/experimental/style_analysis_model.py), [`frontend/src/experimental/StyleAnalysisPanel.tsx`](frontend/src/experimental/StyleAnalysisPanel.tsx), [`frontend/src/experimental/StyleAnalysisModelPanel.tsx`](frontend/src/experimental/StyleAnalysisModelPanel.tsx), [`app/experimental/style_analysis_api.py`](app/experimental/style_analysis_api.py). Exact-final-head tests PENDING.

### Narrative Judge (A03)

- **source version:** Exact selected chapter versions and context fingerprint
- **provenance:** Finding issue_key plus deterministic/model origin, rubric and job
- **history:** Finding decision/review history and persisted run/model receipts
- **review:** Accept/ignore/intentional/reopen and exact result review
- **recovery:** Reopen decision or reconcile original model job; no auto-apply
- **cancel:** Original model cancel and source-current result fence
- **task linkage:** Original model run plus WriterRoom revision assignment ID
- **exact navigation:** Finding/run/job ID and exact WriterRoom revision target
- **evidence:** Quote/start/end/paragraph/source version validated against current chapter
- **user feedback:** Reason and explicit intentional/ignore/reopen decisions
- **intentional suppression:** Same unchanged evidence issue_key inherits intentional decision; changed evidence is reviewed afresh
- **stale state:** Stale source/context finding cannot be accepted as current
- **cross module integration:** Planning/World/Unified Review/WriterRoom/Tasks/Revision
- Evidence: [`app/experimental/narrative_judge.py`](app/experimental/narrative_judge.py), [`app/experimental/narrative_judge_model.py`](app/experimental/narrative_judge_model.py), [`app/experimental/writer_room.py`](app/experimental/writer_room.py), [`frontend/src/experimental/NarrativeJudgePanel.tsx`](frontend/src/experimental/NarrativeJudgePanel.tsx), [`frontend/src/experimental/NarrativeJudgeRevisionTaskPanel.tsx`](frontend/src/experimental/NarrativeJudgeRevisionTaskPanel.tsx). Exact-final-head tests PENDING.

### Revision Intelligence (A11)

- **source version:** Original before/after/current chapter versions plus rich-document selection digest
- **provenance:** Deterministic diff separate from declared/model-derived semantic interpretations and original job
- **history:** Original chapter revisions, comparison/proposal snapshots and milestones
- **review:** Comparison/opinion review; preview-bound segmented accept/reject
- **recovery:** Explicit current-source rebase or original version restore; never overwrite newer prose
- **cancel:** Model original-job cancel; dismiss selection preserves manuscript
- **task linkage:** Exact comparison model job and generation-backed partial proposal
- **exact navigation:** Original chapter/version/anchor plus comparison/proposal/job ID
- **evidence:** Exact before/after quote/offset and protected paragraph identity
- **user feedback:** Per-opinion or segment decision and explicit review
- **intentional suppression:** Rejected/ignored proposal/opinion stays its original decision; no generic future-source suppression
- **stale state:** Source/version/selection/lock changes block adoption until explicit rebase
- **cross module integration:** Write/History/Selection Assistant/Tasks/Unified Review/Change Impact
- Evidence: [`app/experimental/revision_intelligence.py`](app/experimental/revision_intelligence.py), [`app/experimental/revision_intelligence_model.py`](app/experimental/revision_intelligence_model.py), [`app/experimental/revision_intelligence_api.py`](app/experimental/revision_intelligence_api.py), [`frontend/src/experimental/RevisionIntelligencePanel.tsx`](frontend/src/experimental/RevisionIntelligencePanel.tsx), [`frontend/src/experimental/RevisionComparisonModelPanel.tsx`](frontend/src/experimental/RevisionComparisonModelPanel.tsx). Exact-final-head tests PENDING.

### Change Impact (U06)

- **source version:** Source IDs/current versions, dependency node/lock versions and preflight digest
- **provenance:** Original asset lineage/brief/manifest edges and selected refresh plan
- **history:** Persistent versioned preflight/refresh/lock rows
- **review:** Explicit selected preflight/prepare and original output review
- **recovery:** Original owner receipts, retained refresh plan; no generic replay
- **cancel:** Versioned refresh cancellation delegates actual task and fences late output
- **task linkage:** Original media refresh task IDs, not separate generic worker
- **exact navigation:** Source node, original brief/manifest and refresh task ID
- **evidence:** Recorded dependency hashes and known source changes; unknown lineage not invented
- **user feedback:** Selection and persistent exclusion locks
- **intentional suppression:** User lock prevents selected dependency refresh; not a narrative-finding suppression state
- **stale state:** Changed source/brief/configuration/preflight prevents execute/approve
- **cross module integration:** Graph + Asset lineage + original Cover/Storyboard and production manifest
- Evidence: [`app/experimental/media.py`](app/experimental/media.py), [`app/experimental/media_api.py`](app/experimental/media_api.py), [`app/experimental/change_impact.py`](app/experimental/change_impact.py), [`frontend/src/experimental/MediaPanel.tsx`](frontend/src/experimental/MediaPanel.tsx), [`frontend/src/experimental/ChangeImpactPanel.tsx`](frontend/src/experimental/ChangeImpactPanel.tsx). Exact-final-head tests PENDING.

### Planning (FS_PLANNING)

- **source version:** Graph/node/proposal versions plus ancestor, entity and chapter source digests
- **provenance:** Proposal rationale, template, adapter execution mode and optional simulation origin
- **history:** Immutable proposal/node history and explicit restore to fresh review
- **review:** Approve/reject/reopen original planning proposal
- **recovery:** History/restore and retained draft; synchronous bounded generate is not a job
- **cancel:** Cancel UI request; no durable generation promise for synchronous adapter
- **task linkage:** Links simulation origin and original reviewed planning owner; no fabricated background task
- **exact navigation:** Graph/node/proposal IDs and linked original chapter/Scene/character
- **evidence:** Source and ancestor fingerprints, rationale and comparison
- **user feedback:** Explicit edit/reject/approve and selected alternate proposals
- **intentional suppression:** Rejected proposal persists; no auto-recurring detector needing issue suppression
- **stale state:** Source/ancestor/template version changes invalidate proposal review
- **cross module integration:** Simulator/World/Story Graph/Canon/Interactive adaptation/Unified Review
- Evidence: [`app/experimental/planning.py`](app/experimental/planning.py), [`app/services/ai_planning_service.py`](app/services/ai_planning_service.py), [`app/experimental/planning_api.py`](app/experimental/planning_api.py), [`app/ai_planning_api.py`](app/ai_planning_api.py). Exact-final-head tests PENDING.

### Canon (FS_CANON)

- **source version:** Original pending candidate version/digest + selected immutable chapter version/content digest; legacy missing generation provenance stays explicit
- **provenance:** Original pending proposals and preview source lineage; current human review never invents an unrecorded historical source version
- **history:** Original-row retained versioned review, actor/reason/operation history and terminal receipts
- **review:** Project domain.review, explicit human confirmation, expected version + preview digest + reason + operation ID; no branch-only grant
- **recovery:** File prepared journal reconciles deterministic committed fact identities without duplicate append; precommit cancel is separate; PostgreSQL transaction rollback needs no File recovery
- **cancel:** Close unsubmitted review without write; cancel prepared File operation only before facts commit; after commit require recover
- **task linkage:** Original generation/import candidate identity; Canon review remains original-owner decision, not a new background queue
- **exact navigation:** Exact pending candidate ID and reviewed original chapter snapshot; terminal source identity survives later editor navigation
- **evidence:** Preview binds candidate digest and verified source content digest; missing/deleted source bytes withheld while history remains
- **user feedback:** Explicit approve/reject reason and retained history; opposite terminal decision conflicts
- **intentional suppression:** Canon rejection is a terminal candidate decision, not recurring-finding suppression; identical accepted operation is idempotent
- **stale state:** Changed candidate/source/version invalidates preview and approval; recover already committed facts without pretending stale source is current
- **cross module integration:** Original Canon/generation/context, existing Continuity review host and unified review; Research cannot auto-promote
- Evidence: [`app/experimental/finding_review_composition.py`](app/experimental/finding_review_composition.py), [`app/services/canon_service.py`](app/services/canon_service.py), [`app/services/pending_canon_review_service.py`](app/services/pending_canon_review_service.py), [`app/services/lore_service.py`](app/services/lore_service.py), [`app/experimental/world.py`](app/experimental/world.py). Exact-final-head tests PENDING.

### Continuity (FS_CONTINUITY)

- **source version:** Captured original mainline or branch chapter identity/version/digest + facts digest + finding fingerprint
- **provenance:** Original deterministic rule/subject/evidence under exact scope; stored Timeline facts validate public project slug, actual FK, payload ID and source alias. Storage UUID is not a public identity or scope grant; no mainline fallback for branch checks
- **history:** Original finding review version and bounded actor/reason/action/source history, retained through evidence changes
- **review:** Resolve/intentional/reopen/feedback with expected version, source digest, finding fingerprint, operation ID, reason and human confirmation
- **recovery:** Reload durable original decisions after interruption; repeated same-source check keeps accepted decision, no duplicate finding
- **cancel:** Synchronous check abort before commit; cancel unsubmitted decision preserves durable record; no fictional persistent scan worker
- **task linkage:** Original source/check identity; deterministic checks are synchronous and do not manufacture a model task
- **exact navigation:** Exact original current or historical chapter snapshot verified against captured digest, with original scope authorization
- **evidence:** Original evidence IDs and verified historical text; stored Timeline fact reads reject foreign/ambiguous/inconsistent ownership without rewriting rows. Absent paragraph coordinates explicitly mean chapter-level evidence
- **user feedback:** Reasoned resolve/intentional/reopen/feedback and retained operation history
- **intentional suppression:** Unchanged source/finding fingerprint keeps INTENTIONAL; changed evidence/version reopens and cannot inherit old suppression
- **stale state:** Changed/missing chapter or stored facts yields REVIEW_REQUIRED; stale rows allow feedback/reopen but not resolve/intentional
- **cross module integration:** Original Continuity/Narrative repositories, branch manuscript, StoryDatabase/World facts, existing Review UI and exact source
- Evidence: [`app/experimental/finding_review_composition.py`](app/experimental/finding_review_composition.py), [`app/services/continuity_finding_service.py`](app/services/continuity_finding_service.py), [`app/services/finding_review_service.py`](app/services/finding_review_service.py), [`app/lore/continuity.py`](app/lore/continuity.py), [`app/lore/continuity_engine.py`](app/lore/continuity_engine.py). Exact-final-head tests PENDING.

### Foreshadowing (FS_FORESHADOWING)

- **source version:** Original row digest/version and retained chapter/event source versions; planted/target numeric chapters resolve to immutable IDs when present
- **provenance:** Original row private metadata + narrative plant/develop/payoff event and ChapterNarrativeLink identities
- **history:** Original row retains 20 prior version snapshots; legacy saves advance opted-in metadata; original narrative event history remains distinct
- **review:** Snapshot-bound author feedback/restore confirmation; narrative findings use original source-bound review service
- **recovery:** Explicit actor/project/kind/record local candidate recovery and original history restore to a new current version; stale historical source remains labelled
- **cancel:** Cancel local unsent edit/restore preview; dispatched writes cannot be cancelled by dismissal; navigation cancellation discards late reads
- **task linkage:** Original narrative proposal/source chapter identities; synchronous author record transaction is not a second task
- **exact navigation:** Immutable source chapter IDs with fresh authorization and existing dirty/IME/local-draft guards
- **evidence:** Row digest/source snapshots, original chapter narrative links and exact finding historical evidence
- **user feedback:** ACKNOWLEDGED/INTENTIONAL/NEEDS_REVIEW/DISMISSED with note/evidence/actor/source snapshot; original findings retain separate reason/history
- **intentional suppression:** Record feedback applies only to exact row/source snapshot; original narrative finding same-source fingerprint suppression is separate
- **stale state:** CURRENT/STALE/UNLINKED source projection; stale save needs explicit refresh_sources; finding changes invalidate suppression
- **cross module integration:** Planning/Canon/Continuity/StoryDatabase and original chapter context; project-global editor rejects branch-only authority
- Evidence: [`app/experimental/finding_review_composition.py`](app/experimental/finding_review_composition.py), [`app/services/novel_service.py`](app/services/novel_service.py), [`app/services/narrative_state_service.py`](app/services/narrative_state_service.py), [`app/services/narrative_finding_service.py`](app/services/narrative_finding_service.py), [`app/services/finding_review_service.py`](app/services/finding_review_service.py). Exact-final-head tests PENDING.

### Timeline (FS_TIMELINE)

- **source version:** Original Timeline public digest + record version + immutable linked chapter source versions; world HISTORY remains a distinct reviewed projection
- **provenance:** Original event metadata/source snapshots and public IDs preserved. Continuity evidence persistence retains valid UUID event keys, adapts opaque IDs to deterministic storage UUIDs and resolves project slugs to their actual FK owner; mismatches are not rebound
- **history:** 20 retained original row snapshots with private version/provenance metadata; restore adds a new current version
- **review:** Version/source-bound author feedback and explicit restore confirmation; no automatic Canon review approval
- **recovery:** Actor/project/kind/record local candidate plus original GET/history after restart; uncertain writes are read back and never auto-replayed
- **cancel:** Cancel unsent edit/restore preview and pending exact-source read; committed synchronous save is not rolled back by UI close
- **task linkage:** Original source chapter/context; synchronous timeline transaction creates no duplicate task
- **exact navigation:** Original event ID/chapter immutable ID and world record identity; newer navigation/identity changes discard old responses
- **evidence:** Exact row/source digest and explicit time/calendar/order; Continuity Timeline get/list/evidence checks payload, source alias, project slug and actual original owner. Source declarations are not proof of inferred chronology
- **user feedback:** Snapshot-bound ACKNOWLEDGED/INTENTIONAL/NEEDS_REVIEW/DISMISSED with note/evidence; terminal feedback cannot be rewritten unchanged
- **intentional suppression:** Record decision is snapshot scoped; recurring contradiction suppression belongs original findings review
- **stale state:** Current/stale/unlinked source state; changed sources require explicit refresh; legacy compatibility does not imply mandatory CAS on every old endpoint
- **cross module integration:** World graph/Character Mind/Continuity/StoryDatabase and current-source navigation; separate from Production media timeline
- Evidence: [`app/services/novel_service.py`](app/services/novel_service.py), [`app/experimental/world.py`](app/experimental/world.py), [`app/narrative.py`](app/narrative.py), [`app/lore/continuity.py`](app/lore/continuity.py), [`app/repositories/file/continuity.py`](app/repositories/file/continuity.py). Exact-final-head tests PENDING.

## Surface-by-surface engineering contracts

Each entry below is an existing-owner page/subpage. Full model fields, route signatures, state matrix and test list are in the JSON catalog; no second service is implied by a second consumer surface.

### Write

#### U02 · Loss-resistant editing and visible save state

- Page/subpage: Write → Manuscript / Save and recovery. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / existing Manuscript / Save and recovery.
- Components: [`frontend/src/Editor.tsx`](frontend/src/Editor.tsx), [`frontend/src/App.tsx`](frontend/src/App.tsx), [`frontend/src/ui/SaveControls.tsx`](frontend/src/ui/SaveControls.tsx), [`frontend/src/ConflictDialog.tsx`](frontend/src/ConflictDialog.tsx), [`frontend/src/RevisionPanel.tsx`](frontend/src/RevisionPanel.tsx)
- Authority/model/store/API source: [`frontend/src/drafts.ts`](frontend/src/drafts.ts), [`frontend/src/App.tsx`](frontend/src/App.tsx), [`frontend/src/ui/SaveControls.tsx`](frontend/src/ui/SaveControls.tsx), [`app/autosave/durable.py`](app/autosave/durable.py), [`app/api.py`](app/api.py)
- Behavior: Original ChapterService/current document is durable authority; local draft is a separate recoverable editing buffer. Save uses chapter version and conflict preserves local text.
- Version/conflict/cancel/recovery/restart: Abort pending navigation, preserve dirty/IME draft, export corrupted bytes, explicitly reopen recovery, restore creates a new revision. Browser storage removal and never-persisted keystrokes remain outside the recovery guarantee.
- Scope/permissions: Current project/actor/scope and chapter identity/version; unauthenticated local hint never substitutes for authenticated target authorization; Current owner APIs authorize navigation/restore; local UI preference does not grant access. Profile: `UI_INTERACTION`; explicit legacy gaps take precedence over common defaults.
- Flags: `writing_recovery_v2`. Dependencies remain server-owned: {"writing_recovery_v2": []}.
- Navigation: CORE_MANUSCRIPT, FS_BRANCH, U01, A11.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`frontend/src/AppDraftRecovery.test.tsx`](frontend/src/AppDraftRecovery.test.tsx), [`frontend/src/drafts.test.ts`](frontend/src/drafts.test.ts), [`tests/test_post_interop_workspace_ux.py`](tests/test_post_interop_workspace_ux.py), [`frontend/src/Editor.anchor.test.tsx`](frontend/src/Editor.anchor.test.tsx), [`frontend/src/Editor.recovery.test.tsx`](frontend/src/Editor.recovery.test.tsx), [`frontend/src/Editor.a43-rich.test.tsx`](frontend/src/Editor.a43-rich.test.tsx). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### U01 · Resume the previous workspace

- Page/subpage: Write → Continue Working / Workspace resume. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Continue Working / Workspace resume.
- Components: [`frontend/src/experimental/WorkspaceToolsPanel.tsx`](frontend/src/experimental/WorkspaceToolsPanel.tsx), [`frontend/src/App.tsx`](frontend/src/App.tsx)
- Authority/model/store/API source: [`app/experimental/ux.py`](app/experimental/ux.py), [`frontend/src/store.ts`](frontend/src/store.ts), [`frontend/src/App.tsx`](frontend/src/App.tsx), [`frontend/src/experimental/WorkspaceToolsPanel.tsx`](frontend/src/experimental/WorkspaceToolsPanel.tsx), [`app/experimental/ux_api.py`](app/experimental/ux_api.py), [`frontend/src/experimental/uxClient.ts`](frontend/src/experimental/uxClient.ts)
- Behavior: Actor/project/scope-bound resume row stores chapter/version/anchor, layout, reference pointers and original unfinished-task IDs. Resolve rechecks original target authority before navigation.
- Version/conflict/cancel/recovery/restart: CAS save/reset-layout; persisted history; explicit reopen or open-current; dirty/IME/target-draft guards. Restart reads existing pointers and never dispatches a model.
- Scope/permissions: Current project/actor/scope and chapter identity/version; unauthenticated local hint never substitutes for authenticated target authorization; Current owner APIs authorize navigation/restore; local UI preference does not grant access. Profile: `UI_INTERACTION`; explicit legacy gaps take precedence over common defaults.
- Flags: `workspace_tools_v2`. Dependencies remain server-owned: {"workspace_tools_v2": []}.
- Navigation: U02, U03, U04, U07, FS_REVIEW.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_r4_workspace_resume.py`](tests/test_r4_workspace_resume.py), [`tests/test_r4_workspace_resume_mounted.py`](tests/test_r4_workspace_resume_mounted.py), [`tests/test_post_interop_workspace_ux.py`](tests/test_post_interop_workspace_ux.py), [`tests/test_post_interop_task_reopen.py`](tests/test_post_interop_task_reopen.py), [`frontend/src/experimental/ModelTaskReopen.test.tsx`](frontend/src/experimental/ModelTaskReopen.test.tsx), [`frontend/tests/e2e/r4-model-task-reopen.spec.ts`](frontend/tests/e2e/r4-model-task-reopen.spec.ts). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### U03 · Search, commands and recents

- Page/subpage: Write → Global search / Recents. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Global search / Recents.
- Components: [`frontend/src/experimental/WorkspaceSearch.tsx`](frontend/src/experimental/WorkspaceSearch.tsx), [`frontend/src/ui/FeatureLauncher.tsx`](frontend/src/ui/FeatureLauncher.tsx), [`frontend/src/App.tsx`](frontend/src/App.tsx)
- Authority/model/store/API source: [`app/experimental/ux.py`](app/experimental/ux.py), [`app/experimental/search_sources.py`](app/experimental/search_sources.py), [`frontend/src/experimental/WorkspaceSearch.tsx`](frontend/src/experimental/WorkspaceSearch.tsx), [`frontend/src/App.tsx`](frontend/src/App.tsx), [`frontend/src/ui/FeatureLauncher.tsx`](frontend/src/ui/FeatureLauncher.tsx), [`app/experimental/ux_api.py`](app/experimental/ux_api.py)
- Behavior: Literal lexical search over original authorized identities; current-source revision is resolved before exact owner navigation. Search is distinct from vector/hybrid retrieval.
- Version/conflict/cancel/recovery/restart: Bounded paging, request cancellation and cache invalidation; cancel aborts lookup, not the source job; restart rebuilds/reads current authorized projections. Unknown or withdrawn targets are withheld.
- Scope/permissions: Current project/actor/scope and chapter identity/version; unauthenticated local hint never substitutes for authenticated target authorization; Current owner APIs authorize navigation/restore; local UI preference does not grant access. Profile: `UI_INTERACTION`; explicit legacy gaps take precedence over common defaults.
- Flags: `workspace_tools_v2`. Dependencies remain server-owned: {"workspace_tools_v2": []}.
- Navigation: FS_SEMANTIC, FS_INTERACTION, U07, A04, A10.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_post_interop_structured_search.py`](tests/test_post_interop_structured_search.py), [`tests/test_post_interop_workspace_ux.py`](tests/test_post_interop_workspace_ux.py), [`frontend/src/experimental/StructuredSearchNavigation.test.tsx`](frontend/src/experimental/StructuredSearchNavigation.test.tsx), [`frontend/tests/e2e/r4-structured-search.spec.ts`](frontend/tests/e2e/r4-structured-search.spec.ts), [`frontend/src/experimental/WorkspaceSearch.test.tsx`](frontend/src/experimental/WorkspaceSearch.test.tsx), [`frontend/src/ui/FeatureLauncher.test.tsx`](frontend/src/ui/FeatureLauncher.test.tsx). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### U08 · Context and privacy inspector

- Page/subpage: Write → Context inspector / Cost and privacy preview. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / existing Context inspector / Cost and privacy preview.
- Components: [`frontend/src/novel/AiContextPreviewPanel.tsx`](frontend/src/novel/AiContextPreviewPanel.tsx), [`frontend/src/novel/AuthorRequestPreviewPanel.tsx`](frontend/src/novel/AuthorRequestPreviewPanel.tsx), [`frontend/src/novel/AuthorRequestControls.tsx`](frontend/src/novel/AuthorRequestControls.tsx), [`frontend/src/novel/AuthorSourceItems.tsx`](frontend/src/novel/AuthorSourceItems.tsx), [`frontend/src/novel/SourcePrivacyControl.tsx`](frontend/src/novel/SourcePrivacyControl.tsx), [`frontend/src/useScopedRequestConsent.tsx`](frontend/src/useScopedRequestConsent.tsx)
- Authority/model/store/API source: [`app/author_context_sources.py`](app/author_context_sources.py), [`app/author_request.py`](app/author_request.py), [`app/experimental/author_context_api.py`](app/experimental/author_context_api.py), [`app/jobs.py`](app/jobs.py), [`frontend/src/novel/AuthorSourceItems.tsx`](frontend/src/novel/AuthorSourceItems.tsx), [`frontend/src/novel/AuthorRequestPreviewPanel.tsx`](frontend/src/novel/AuthorRequestPreviewPanel.tsx), [`app/api.py`](app/api.py)
- Behavior: The actual request builder and digest-bound source/version/privacy/route preflight own prompt preview; source pointers are resolved, never trusted inline payloads.
- Version/conflict/cancel/recovery/restart: Preview cancellation is read-only; dispatch repeats current source/permission checks; stale preview requires re-review. Restart requires fresh preflight; unknown usage/cost remains unknown.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `author_context_inspector_v2`. Dependencies remain server-owned: {"author_context_inspector_v2": []}.
- Navigation: CORE_GENERATION, A06, A05, A10, FS_CANON.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_post_interop_author_added_sources.py`](tests/test_post_interop_author_added_sources.py), [`frontend/src/novel/AuthorSourcePicker.test.tsx`](frontend/src/novel/AuthorSourcePicker.test.tsx), [`frontend/tests/e2e/r4-author-added-sources.spec.ts`](frontend/tests/e2e/r4-author-added-sources.spec.ts), [`frontend/src/novel/AiContextPreviewPanel.test.tsx`](frontend/src/novel/AiContextPreviewPanel.test.tsx), [`frontend/src/novel/AuthorRequestPreviewPanel.test.tsx`](frontend/src/novel/AuthorRequestPreviewPanel.test.tsx), [`frontend/src/novel/AuthorRequestControls.test.tsx`](frontend/src/novel/AuthorRequestControls.test.tsx). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### U04 · Focus, reference split and inspiration

- Page/subpage: Write → Focus / Reference split / Inspiration. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Focus / Reference split / Inspiration.
- Components: [`frontend/src/experimental/WritingFocusPanel.tsx`](frontend/src/experimental/WritingFocusPanel.tsx), [`frontend/src/Editor.tsx`](frontend/src/Editor.tsx), [`frontend/src/App.tsx`](frontend/src/App.tsx)
- Authority/model/store/API source: [`app/experimental/writing_focus.py`](app/experimental/writing_focus.py), [`frontend/src/experimental/WritingFocusPanel.tsx`](frontend/src/experimental/WritingFocusPanel.tsx), [`frontend/src/Editor.tsx`](frontend/src/Editor.tsx), [`frontend/src/App.tsx`](frontend/src/App.tsx), [`app/experimental/writing_focus_api.py`](app/experimental/writing_focus_api.py)
- Behavior: Existing editor remains single prose authority; focus preferences/reference pins are scoped metadata; inspiration is an independent private draft until explicit planning proposal creation.
- Version/conflict/cancel/recovery/restart: Preference/pin versions, history and current source checks; cancel retains unsaved editor; restart resolves original references. Paragraph emphasis is not an AI write lock.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `writing_focus_v2`. Dependencies remain server-owned: {"writing_focus_v2": []}.
- Navigation: U02, U01, FS_PLANNING, A11.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_r4_workspace_resume.py`](tests/test_r4_workspace_resume.py), [`frontend/src/experimental/WritingFocusPanel.test.tsx`](frontend/src/experimental/WritingFocusPanel.test.tsx), [`frontend/src/Editor.anchor.test.tsx`](frontend/src/Editor.anchor.test.tsx), [`frontend/src/Editor.recovery.test.tsx`](frontend/src/Editor.recovery.test.tsx), [`frontend/src/Editor.a43-rich.test.tsx`](frontend/src/Editor.a43-rich.test.tsx), [`frontend/src/Editor.typography.test.ts`](frontend/src/Editor.typography.test.ts). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### U05 · Selection assistant and partial accept

- Page/subpage: Write → Selection assistant / Partial accept. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Selection assistant / Partial accept.
- Components: [`frontend/src/Editor.tsx`](frontend/src/Editor.tsx), [`frontend/src/novel/AiWritingPanel.tsx`](frontend/src/novel/AiWritingPanel.tsx), [`frontend/src/experimental/RevisionIntelligencePanel.tsx`](frontend/src/experimental/RevisionIntelligencePanel.tsx)
- Authority/model/store/API source: [`app/experimental/revision_intelligence.py`](app/experimental/revision_intelligence.py), [`app/services/generation_service.py`](app/services/generation_service.py), [`frontend/src/Editor.tsx`](frontend/src/Editor.tsx), [`frontend/src/novel/AiWritingPanel.tsx`](frontend/src/novel/AiWritingPanel.tsx), [`app/experimental/revision_intelligence_api.py`](app/experimental/revision_intelligence_api.py), [`app/api.py`](app/api.py)
- Behavior: Same selection/proposal and original generation owners as A11; saved version, UTF-16 range and paragraph locks bind edits.
- Version/conflict/cancel/recovery/restart: Cancel preserves current text; explicit partial accept/reject, fresh preview and rebase. Restart recovers original job/proposal rather than applying a whole candidate.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `selection_assistant_v2`. Dependencies remain server-owned: {"selection_assistant_v2": ["revision_intelligence_v2", "author_context_inspector_v2"]}.
- Navigation: A11, CORE_GENERATION, U02.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_r4_revision_intelligence.py`](tests/test_r4_revision_intelligence.py), [`tests/test_post_interop_revision_compare.py`](tests/test_post_interop_revision_compare.py), [`frontend/src/experimental/RevisionIntelligencePanel.test.tsx`](frontend/src/experimental/RevisionIntelligencePanel.test.tsx), [`frontend/src/Editor.anchor.test.tsx`](frontend/src/Editor.anchor.test.tsx), [`frontend/src/Editor.recovery.test.tsx`](frontend/src/Editor.recovery.test.tsx), [`frontend/src/Editor.a43-rich.test.tsx`](frontend/src/Editor.a43-rich.test.tsx). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### U15 · Writing goals and controlled notices

- Page/subpage: Write → Writing goals / Session / Notices. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Writing goals / Session / Notices.
- Components: [`frontend/src/experimental/WritingSessionPanel.tsx`](frontend/src/experimental/WritingSessionPanel.tsx), [`frontend/src/novel/NovelOverviewPanel.tsx`](frontend/src/novel/NovelOverviewPanel.tsx)
- Authority/model/store/API source: [`app/experimental/writing_sessions.py`](app/experimental/writing_sessions.py), [`frontend/src/experimental/WritingSessionPanel.tsx`](frontend/src/experimental/WritingSessionPanel.tsx), [`frontend/src/novel/NovelOverviewPanel.tsx`](frontend/src/novel/NovelOverviewPanel.tsx), [`app/experimental/writing_sessions_api.py`](app/experimental/writing_sessions_api.py)
- Behavior: Original source/session goal counters and controlled in-app notices; no OS/background/external notification service.
- Version/conflict/cancel/recovery/restart: Explicit start/stop/review preferences; persistent session state and source measurements; no duplicate notice on reopening. Restart reads original session.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `writing_sessions_v2`. Dependencies remain server-owned: {"writing_sessions_v2": ["workspace_tools_v2"]}.
- Navigation: U01, U07, CORE_MANUSCRIPT.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`frontend/src/novel/NovelOverviewPanel.test.tsx`](frontend/src/novel/NovelOverviewPanel.test.tsx). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### B05 · Multilingual revisions and terminology

- Page/subpage: Write → Translation / Memory / Terminology. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Translation / Memory / Terminology.
- Components: [`frontend/src/experimental/MultilingualEditionsPanel.tsx`](frontend/src/experimental/MultilingualEditionsPanel.tsx), [`frontend/src/experimental/LanguageTranslationPanel.tsx`](frontend/src/experimental/LanguageTranslationPanel.tsx), [`frontend/src/experimental/TranslationMemoryPanel.tsx`](frontend/src/experimental/TranslationMemoryPanel.tsx)
- Authority/model/store/API source: [`app/experimental/multilingual_editions.py`](app/experimental/multilingual_editions.py), [`app/experimental/multilingual_translation.py`](app/experimental/multilingual_translation.py), [`frontend/src/experimental/MultilingualEditionsPanel.tsx`](frontend/src/experimental/MultilingualEditionsPanel.tsx), [`frontend/src/experimental/TranslationMemoryPanel.tsx`](frontend/src/experimental/TranslationMemoryPanel.tsx), [`app/experimental/multilingual_editions_api.py`](app/experimental/multilingual_editions_api.py)
- Behavior: Original edition/segment owner retains source version, language and reviewed translation-memory exact matches; terminology and locked preferred terms are explicit rules.
- Version/conflict/cancel/recovery/restart: Per-segment save/review/source refresh/history/restore and original translation job cancel; reuse creates DRAFT, never silent retranslation. Restart resolves exact edition/run.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `multilingual_editions_v2`. Dependencies remain server-owned: {"multilingual_editions_v2": []}.
- Navigation: U07, FS_REVIEW, CORE_EXPORT, FS_CANON.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_post_interop_translation_memory.py`](tests/test_post_interop_translation_memory.py), [`tests/test_post_interop_extended_mounted.py`](tests/test_post_interop_extended_mounted.py), [`tests/test_r5_multilingual_translation.py`](tests/test_r5_multilingual_translation.py), [`frontend/src/experimental/TranslationMemoryPanel.test.tsx`](frontend/src/experimental/TranslationMemoryPanel.test.tsx), [`tests/test_post_interop_task_reopen.py`](tests/test_post_interop_task_reopen.py), [`frontend/src/experimental/ModelTaskReopen.test.tsx`](frontend/src/experimental/ModelTaskReopen.test.tsx). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: EXTERNAL_REAL_MODELS, FINAL_SOURCE_CI.

#### CORE_MANUSCRIPT · Project / Chapter tree / Authoritative manuscript

- Page/subpage: Write → Project / Chapter tree / Authoritative manuscript. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / existing Project / Chapter tree / Authoritative manuscript.
- Components: [`frontend/src/novel/ChapterTree.tsx`](frontend/src/novel/ChapterTree.tsx), [`frontend/src/Editor.tsx`](frontend/src/Editor.tsx), [`frontend/src/App.tsx`](frontend/src/App.tsx), [`frontend/src/RevisionPanel.tsx`](frontend/src/RevisionPanel.tsx)
- Authority/model/store/API source: [`app/services/novel_service.py`](app/services/novel_service.py), [`app/services/chapter_service.py`](app/services/chapter_service.py), [`app/chapter_identity.py`](app/chapter_identity.py), [`app/document.py`](app/document.py), [`app/api.py`](app/api.py), [`app/collaboration_api.py`](app/collaboration_api.py)
- Behavior: Mainline ChapterRepository owns prose, chapter identity/order and revision history; branch authority is FS_BRANCH. Save and restore require original version; conflict retains draft; archive/delete/move use original recovery rules.
- Version/conflict/cancel/recovery/restart: Native Windows IME/power-loss acceptance is separate; no snapshot proves native behavior.
- Scope/permissions: Original project/chapter/asset/job and collaboration scope where supported; unavailable branch paths must reject, never substitute mainline; Original route/middleware trusted session, owner/current membership and operation-specific domain permission; no client role authority. Profile: `ORIGINAL_AUTHORITY`; explicit legacy gaps take precedence over common defaults.
- Flags: Original core runtime/capability gates; no new blanket opt-in. Dependencies remain server-owned: {}.
- Navigation: U02, U01, FS_BRANCH, CORE_GENERATION, FS_STORY_DATABASE.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_a43_known_document_nodes.py`](tests/test_a43_known_document_nodes.py), [`tests/test_a43_rich_document.py`](tests/test_a43_rich_document.py), [`tests/test_chapter_archive_lifecycle_v070.py`](tests/test_chapter_archive_lifecycle_v070.py), [`tests/test_chapter_concurrency.py`](tests/test_chapter_concurrency.py), [`tests/test_chapter_markdown_contract.py`](tests/test_chapter_markdown_contract.py), [`tests/test_phase7_novel_import.py`](tests/test_phase7_novel_import.py). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### CORE_GENERATION · AI writing / Draft-Diff-Accept / Recovery

- Page/subpage: Write → AI writing / Draft-Diff-Accept / Recovery. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / existing AI writing / Draft-Diff-Accept / Recovery.
- Components: [`frontend/src/novel/AiWritingPanel.tsx`](frontend/src/novel/AiWritingPanel.tsx), [`frontend/src/novel/GenerationRecoveryPicker.tsx`](frontend/src/novel/GenerationRecoveryPicker.tsx), [`frontend/src/novel/GenerationWorkflowTimeline.tsx`](frontend/src/novel/GenerationWorkflowTimeline.tsx), [`frontend/src/generationRecovery.ts`](frontend/src/generationRecovery.ts)
- Authority/model/store/API source: [`app/services/generation_service.py`](app/services/generation_service.py), [`app/jobs.py`](app/jobs.py), [`app/generation_stream.py`](app/generation_stream.py), [`app/api.py`](app/api.py), [`app/experimental/author_context_api.py`](app/experimental/author_context_api.py)
- Behavior: Original JobManager generation attempt, provider/model and captured source/branch remain authority. Preview/dispatch/stream/cancel/recover/review/apply are distinct; late output never applies. Accept uses original document CAS.
- Version/conflict/cancel/recovery/restart: Real model/quality/GPU NOT_RUN; unknown paid attempt is not retried automatically; review-owned model tasks cannot be accepted wholesale as prose.
- Scope/permissions: Original project/chapter/asset/job and collaboration scope where supported; unavailable branch paths must reject, never substitute mainline; Original route/middleware trusted session, owner/current membership and operation-specific domain permission; no client role authority. Profile: `ORIGINAL_AUTHORITY`; explicit legacy gaps take precedence over common defaults.
- Flags: Original core runtime/capability gates; no new blanket opt-in. Dependencies remain server-owned: {}.
- Navigation: U08, U07, FS_REVIEW, A11.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_a43_detached_generation_acceptance.py`](tests/test_a43_detached_generation_acceptance.py), [`tests/test_export_jobs.py`](tests/test_export_jobs.py), [`tests/test_generation_idempotency_contracts.py`](tests/test_generation_idempotency_contracts.py), [`tests/test_generation_restart_recovery.py`](tests/test_generation_restart_recovery.py), [`tests/test_generation_snapshot_runtime_v056.py`](tests/test_generation_snapshot_runtime_v056.py), [`tests/test_generation_variants_phase3.py`](tests/test_generation_variants_phase3.py). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### FS_BRANCH · Branch manuscript / Fork / Compare / Human merge

- Page/subpage: Write → Branch manuscript / Fork / Compare / Human merge. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Branch manuscript / Fork / Compare / Human merge.
- Components: [`frontend/src/experimental/BranchManuscriptPanel.tsx`](frontend/src/experimental/BranchManuscriptPanel.tsx), [`frontend/src/experimental/ProjectForksPanel.tsx`](frontend/src/experimental/ProjectForksPanel.tsx)
- Authority/model/store/API source: [`app/services/branch_manuscript_service.py`](app/services/branch_manuscript_service.py), [`app/repositories/branch_manuscript.py`](app/repositories/branch_manuscript.py), [`app/experimental/branch_manuscript_composition.py`](app/experimental/branch_manuscript_composition.py), [`app/manuscript_sources.py`](app/manuscript_sources.py), [`app/services/export_snapshot_authority.py`](app/services/export_snapshot_authority.py), [`app/application/collaboration_service.py`](app/application/collaboration_service.py), [`app/application/persistence.py`](app/application/persistence.py), [`app/repositories/postgres/generation.py`](app/repositories/postgres/generation.py), [`app/experimental/branch_manuscript_api.py`](app/experimental/branch_manuscript_api.py)
- Behavior: Original BranchManuscriptService scoped repository owns actual independent rich prose, immutable chapter identity/version/order/history and receipts. Mainline remains ChapterService. Registered generation/context/GET/SSE/export and Local Interop source readers re-resolve the real branch owner even for retained old IDs; no mainline fallback or marker-only inference. Interop uses frozen-compatible scope-bound wire labels and live exact-owner reverse lookup; only an authorized editor handoff returns native IDs.
- Version/conflict/cancel/recovery/restart: Create/save/restore/archive/tombstone/move; confirmed fork, rich-block three-way compare, human merge and original-owner recovery. Branch transaction/journal is atomic; mainline uncertain write requires exact receipt reconciliation. Durable capacity ceilings fail before commit without silently evicting histories. Shared branch inbox is read-only with exact original review route; counterpart access is rechecked and cancellation stays in the original CAS/read+review endpoint. Collaboration retry needs fresh author preview; restart never dispatches automatically.
- Scope/permissions: Original project/chapter/asset/job and collaboration scope where supported; unavailable branch paths must reject, never substitute mainline; Original route/middleware trusted session, owner/current membership and operation-specific domain permission; no client role authority. Profile: `ORIGINAL_AUTHORITY`; explicit legacy gaps take precedence over common defaults.
- Flags: `branch_manuscript_v1`. Dependencies remain server-owned: {"branch_manuscript_v1": []}.
- Navigation: CORE_MANUSCRIPT, CORE_GENERATION, B09, FS_REALTIME, FS_REVIEW, U07, CORE_ADAPTATION, CORE_INTEROP.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_a43_detached_generation_acceptance.py`](tests/test_a43_detached_generation_acceptance.py), [`tests/test_collaboration_application_service_v056.py`](tests/test_collaboration_application_service_v056.py), [`tests/test_collaboration_http_boundary_v056.py`](tests/test_collaboration_http_boundary_v056.py), [`tests/test_collaboration_scope.py`](tests/test_collaboration_scope.py), [`tests/test_collaboration_scope_api.py`](tests/test_collaboration_scope_api.py), [`tests/test_collaboration_text_models_route.py`](tests/test_collaboration_text_models_route.py). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Source-bound focused owner receipts (not final-head acceptance): [`docs/delivery/functional-surface-freeze/BRANCH_MANUSCRIPT_VERIFICATION.json`](docs/delivery/functional-surface-freeze/BRANCH_MANUSCRIPT_VERIFICATION.json).
- Formal contract: [`docs/delivery/functional-surface-freeze/BRANCH_MANUSCRIPT_AUTHORITY.md`](docs/delivery/functional-surface-freeze/BRANCH_MANUSCRIPT_AUTHORITY.md), [`docs/LOCAL_INTEROP_BRANCH_OWNER_INTEGRATION.md`](docs/LOCAL_INTEROP_BRANCH_OWNER_INTEGRATION.md).
- Remaining boundaries: FINAL_SOURCE_CI.

### Story

#### A04 · Temporal semantic story graph

- Page/subpage: Story → Semantic Story Graph. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Semantic Story Graph.
- Components: [`frontend/src/experimental/StoryGraphPanel.tsx`](frontend/src/experimental/StoryGraphPanel.tsx)
- Authority/model/store/API source: [`app/experimental/world.py`](app/experimental/world.py), [`app/experimental/story_graph.py`](app/experimental/story_graph.py), [`app/experimental/story_graph_api.py`](app/experimental/story_graph_api.py), [`frontend/src/experimental/StoryGraphPanel.tsx`](frontend/src/experimental/StoryGraphPanel.tsx), [`app/experimental/world_api.py`](app/experimental/world_api.py)
- Behavior: Typed original-ID concepts/relations/knowledge events share WorldService records and reviewed graph index; temporal Chapter/Scene boundaries, evidence and source digests control projection.
- Version/conflict/cancel/recovery/restart: Edit/review/archive/reopen/history and recompute are versioned; stale relations and forget tombstones suppress invalid knowledge. Pure query/recompute has no fictional background task; cancelled UI reads discard results.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `temporal_story_graph_v2`. Dependencies remain server-owned: {"temporal_story_graph_v2": ["world_character_engines_v2"]}.
- Navigation: A05, FS_PLANNING, FS_CANON, U03, U06, FS_STORY_DATABASE.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_post_interop_scene_mind.py`](tests/test_post_interop_scene_mind.py), [`tests/test_post_interop_creation_mounted.py`](tests/test_post_interop_creation_mounted.py), [`tests/test_post_interop_creation_upgrade.py`](tests/test_post_interop_creation_upgrade.py), [`frontend/src/experimental/StoryGraphPanel.test.tsx`](frontend/src/experimental/StoryGraphPanel.test.tsx), [`tests/test_r4_story_graph.py`](tests/test_r4_story_graph.py), [`tests/test_r4_story_graph_mounted.py`](tests/test_r4_story_graph_mounted.py). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### A05 · Character knowledge and mind state

- Page/subpage: Story → Character Mind / Viewpoint. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Character Mind / Viewpoint.
- Components: [`frontend/src/experimental/StoryGraphPanel.tsx`](frontend/src/experimental/StoryGraphPanel.tsx), [`frontend/src/novel/AiWritingPanel.tsx`](frontend/src/novel/AiWritingPanel.tsx)
- Authority/model/store/API source: [`app/experimental/story_graph.py`](app/experimental/story_graph.py), [`app/experimental/character_author_context.py`](app/experimental/character_author_context.py), [`app/experimental/author_context_api.py`](app/experimental/author_context_api.py), [`frontend/src/experimental/StoryGraphPanel.tsx`](frontend/src/experimental/StoryGraphPanel.tsx), [`frontend/src/novel/AiWritingPanel.tsx`](frontend/src/novel/AiWritingPanel.tsx), [`app/experimental/story_graph_api.py`](app/experimental/story_graph_api.py)
- Behavior: Same reviewed knowledge-event owner as Story Graph. Author facts, known facts, beliefs, false beliefs, secrets, goals, fears, values, emotion, intent and relationship state remain distinct.
- Version/conflict/cancel/recovery/restart: History/CAS/review and stale tombstones come from A04; query abort does not change knowledge. Restart resolves current temporal sources; character-only request rejects author-only additions.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `character_mind_v2`. Dependencies remain server-owned: {"character_mind_v2": ["temporal_story_graph_v2"]}.
- Navigation: A04, A01, U08, CORE_GENERATION, FS_STORY_DATABASE.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_post_interop_scene_mind.py`](tests/test_post_interop_scene_mind.py), [`tests/test_r4_character_author_context.py`](tests/test_r4_character_author_context.py), [`frontend/src/novel/CharacterAuthorPanel.test.tsx`](frontend/src/novel/CharacterAuthorPanel.test.tsx), [`frontend/src/experimental/StoryGraphPanel.test.tsx`](frontend/src/experimental/StoryGraphPanel.test.tsx), [`frontend/src/novel/AiWritingPanel.test.tsx`](frontend/src/novel/AiWritingPanel.test.tsx), [`tests/test_r4_story_graph.py`](tests/test_r4_story_graph.py). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### A01 · Bounded story simulation

- Page/subpage: Story → Story Simulator. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Story Simulator.
- Components: [`frontend/src/experimental/StorySimulatorPanel.tsx`](frontend/src/experimental/StorySimulatorPanel.tsx)
- Authority/model/store/API source: [`app/experimental/story_simulator.py`](app/experimental/story_simulator.py), [`app/experimental/story_simulator_model.py`](app/experimental/story_simulator_model.py), [`frontend/src/experimental/StorySimulatorPanel.tsx`](frontend/src/experimental/StorySimulatorPanel.tsx), [`app/experimental/story_simulator_api.py`](app/experimental/story_simulator_api.py)
- Behavior: Bounded hypothetical routes/step outcomes retain current Scene/character/world/Canon/knowledge/constraint fingerprints; model suggestions use original jobs.
- Version/conflict/cancel/recovery/restart: Explicit step/cancel/select/save; source/CAS and reviewed-candidate digest; history persists; restart reads state and never advances itself. Saved route becomes a planning proposal only.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `story_simulator_v2`. Dependencies remain server-owned: {"story_simulator_v2": ["advanced_planning_v2", "temporal_story_graph_v2", "character_mind_v2"]}.
- Navigation: A04, A05, FS_PLANNING, U07, FS_REVIEW.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_post_interop_scene_mind.py`](tests/test_post_interop_scene_mind.py), [`tests/test_post_interop_creation_mounted.py`](tests/test_post_interop_creation_mounted.py), [`tests/test_r4_story_simulator_model.py`](tests/test_r4_story_simulator_model.py), [`tests/test_post_interop_task_reopen.py`](tests/test_post_interop_task_reopen.py), [`frontend/src/experimental/ModelTaskReopen.test.tsx`](frontend/src/experimental/ModelTaskReopen.test.tsx), [`frontend/tests/e2e/r4-model-task-reopen.spec.ts`](frontend/tests/e2e/r4-model-task-reopen.spec.ts). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: EXTERNAL_REAL_MODELS, FINAL_SOURCE_CI.

#### CORE_CREATION · Creation workbench / Structured plans / Review threads

- Page/subpage: Story → Creation workbench / Structured plans / Review threads. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / existing Creation workbench / Structured plans / Review threads.
- Components: [`frontend/src/novel/CreationWorkbenchPanel.tsx`](frontend/src/novel/CreationWorkbenchPanel.tsx), [`frontend/src/novel/AIPlanningPanel.tsx`](frontend/src/novel/AIPlanningPanel.tsx)
- Authority/model/store/API source: [`app/services/creation_workbench_service.py`](app/services/creation_workbench_service.py), [`app/creation_workbench_api.py`](app/creation_workbench_api.py)
- Behavior: Original creation record, PLAN/STYLE source version/digests, immutable history and CAS; explicit DRAFT/APPROVED/ARCHIVED transitions. Review threads preserve current/stale/missing anchors and explicit reopen.
- Version/conflict/cancel/recovery/restart: A plan or STYLE approval does not itself alter Canon or prose; generative results remain reviewed proposals.
- Scope/permissions: Original project/chapter/asset/job and collaboration scope where supported; unavailable branch paths must reject, never substitute mainline; Original route/middleware trusted session, owner/current membership and operation-specific domain permission; no client role authority. Profile: `ORIGINAL_AUTHORITY`; explicit legacy gaps take precedence over common defaults.
- Flags: Original core runtime/capability gates; no new blanket opt-in. Dependencies remain server-owned: {}.
- Navigation: FS_PLANNING, A02, FS_REVIEW.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_r2_creation_workbench.py`](tests/test_r2_creation_workbench.py), [`frontend/src/novel/CreationWorkbenchPanel.test.tsx`](frontend/src/novel/CreationWorkbenchPanel.test.tsx), [`frontend/src/novel/AIPlanningPanel.test.tsx`](frontend/src/novel/AIPlanningPanel.test.tsx). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### FS_PLANNING · Layered planning / Proposals / Templates

- Page/subpage: Story → Layered planning / Proposals / Templates. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Layered planning / Proposals / Templates.
- Components: [`frontend/src/experimental/PlanningPanel.tsx`](frontend/src/experimental/PlanningPanel.tsx), [`frontend/src/novel/StoryPlanningWorkspace.tsx`](frontend/src/novel/StoryPlanningWorkspace.tsx), [`frontend/src/experimental/PromotionRecovery.tsx`](frontend/src/experimental/PromotionRecovery.tsx)
- Authority/model/store/API source: [`app/experimental/planning.py`](app/experimental/planning.py), [`app/services/ai_planning_service.py`](app/services/ai_planning_service.py), [`app/experimental/planning_api.py`](app/experimental/planning_api.py), [`app/ai_planning_api.py`](app/ai_planning_api.py)
- Behavior: Graph/node levels and links use original Chapter/Character/Scene identities, expected node/proposal version and source fingerprint. Generate candidates through explicit adapter; compare/review/history/restore are current-source fenced.
- Version/conflict/cancel/recovery/restart: Bounded synchronous planning generation has no invented persistent task; absent real planning adapter remains NOT_CONFIGURED/MOCK_ONLY as reported. Restore creates another review proposal.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `advanced_planning_v2`. Dependencies remain server-owned: {"advanced_planning_v2": []}.
- Navigation: A01, A04, CORE_CREATION, FS_REVIEW.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_r2_ai_planning.py`](tests/test_r2_ai_planning.py), [`tests/test_r2_planning_app_routes.py`](tests/test_r2_planning_app_routes.py), [`tests/test_r3_planning.py`](tests/test_r3_planning.py), [`tests/test_r4_planning_authority.py`](tests/test_r4_planning_authority.py), [`frontend/src/experimental/PlanningPanel.recovery.test.tsx`](frontend/src/experimental/PlanningPanel.recovery.test.tsx), [`frontend/src/novel/StoryPlanningWorkspace.test.tsx`](frontend/src/novel/StoryPlanningWorkspace.test.tsx). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### FS_CANON · Canon / Evidence / Pending decisions

- Page/subpage: Story → Canon / Evidence / Pending decisions. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Canon / Evidence / Pending decisions.
- Components: [`frontend/src/novel/StoryDatabase.tsx`](frontend/src/novel/StoryDatabase.tsx), [`frontend/src/experimental/WorldPanel.tsx`](frontend/src/experimental/WorldPanel.tsx), [`frontend/src/experimental/InboxPanel.tsx`](frontend/src/experimental/InboxPanel.tsx), [`frontend/src/novel/PendingCanonReviewPanel.tsx`](frontend/src/novel/PendingCanonReviewPanel.tsx), [`frontend/src/novel/pendingCanonReviewClient.ts`](frontend/src/novel/pendingCanonReviewClient.ts)
- Authority/model/store/API source: [`app/experimental/finding_review_composition.py`](app/experimental/finding_review_composition.py), [`app/services/canon_service.py`](app/services/canon_service.py), [`app/services/pending_canon_review_service.py`](app/services/pending_canon_review_service.py), [`app/services/lore_service.py`](app/services/lore_service.py), [`app/experimental/world.py`](app/experimental/world.py), [`app/repositories/file/canon.py`](app/repositories/file/canon.py), [`app/repositories/postgres/canon.py`](app/repositories/postgres/canon.py), [`app/api.py`](app/api.py), [`app/pending_canon_review_api.py`](app/pending_canon_review_api.py), [`app/experimental/world_api.py`](app/experimental/world_api.py)
- Behavior: Original pending-Canon and approved Canon repositories remain project/mainline authority. Current source snapshot and candidate digest bind explicit preview, reason, human confirmation, expected version and operation ID; branch-only authority never grants project Canon access. Research cannot auto-promote.
- Version/conflict/cancel/recovery/restart: Terminal approve/reject is idempotent and opposite transitions conflict. File prepared journal plus deterministic fact receipts supports explicit recover/cancel-before-commit; PostgreSQL facts and decision use one transaction. Missing legacy provenance is explicit; unknown source cannot be approved. History remains after source removal while source bytes are withheld. Exact-final-head tests pending.
- Scope/permissions: Original project/chapter/asset/job and collaboration scope where supported; unavailable branch paths must reject, never substitute mainline; Original route/middleware trusted session, owner/current membership and operation-specific domain permission; no client role authority. Profile: `ORIGINAL_AUTHORITY`; explicit legacy gaps take precedence over common defaults.
- Flags: `finding_review_v1`, `world_character_engines_v2`. Dependencies remain server-owned: {"finding_review_v1": [], "world_character_engines_v2": []}.
- Navigation: FS_REVIEW, A04, FS_CONTINUITY, A10.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_lore_context_contract.py`](tests/test_lore_context_contract.py), [`tests/test_lore_contract.py`](tests/test_lore_contract.py), [`tests/test_lore_postgres_contract.py`](tests/test_lore_postgres_contract.py), [`tests/test_lore_service.py`](tests/test_lore_service.py), [`tests/test_surface_findings_canon_inbox.py`](tests/test_surface_findings_canon_inbox.py), [`tests/test_surface_pending_canon_review.py`](tests/test_surface_pending_canon_review.py). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Source-bound focused owner receipts (not final-head acceptance): [`docs/delivery/functional-surface-freeze/FINDINGS_AND_CANON_VERIFICATION.json`](docs/delivery/functional-surface-freeze/FINDINGS_AND_CANON_VERIFICATION.json).
- Formal contract: [`contracts/functional-surfaces/findings-canon.v1.json`](contracts/functional-surfaces/findings-canon.v1.json), [`docs/delivery/functional-surface-freeze/FINDINGS_AND_CANON.md`](docs/delivery/functional-surface-freeze/FINDINGS_AND_CANON.md).
- Remaining boundaries: FINAL_SOURCE_CI.

#### FS_FORESHADOWING · Foreshadowing / Narrative progress

- Page/subpage: Story → Foreshadowing / Narrative progress. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / existing Foreshadowing / Narrative progress.
- Components: [`frontend/src/novel/StoryDatabase.tsx`](frontend/src/novel/StoryDatabase.tsx), [`frontend/src/novel/StoryRecordVersionEditor.tsx`](frontend/src/novel/StoryRecordVersionEditor.tsx), [`frontend/src/novel/StoryPlanningWorkspace.tsx`](frontend/src/novel/StoryPlanningWorkspace.tsx), [`frontend/src/novel/ContinuityCheckPanel.tsx`](frontend/src/novel/ContinuityCheckPanel.tsx), [`frontend/src/novel/FindingReviewPanel.tsx`](frontend/src/novel/FindingReviewPanel.tsx)
- Authority/model/store/API source: [`app/experimental/finding_review_composition.py`](app/experimental/finding_review_composition.py), [`app/services/novel_service.py`](app/services/novel_service.py), [`app/services/narrative_state_service.py`](app/services/narrative_state_service.py), [`app/services/narrative_finding_service.py`](app/services/narrative_finding_service.py), [`app/services/finding_review_service.py`](app/services/finding_review_service.py), [`app/services/narrative_proposal_service.py`](app/services/narrative_proposal_service.py), [`app/narrative.py`](app/narrative.py), [`app/narrative_detection.py`](app/narrative_detection.py), [`app/repositories/story_record_versions.py`](app/repositories/story_record_versions.py), [`app/repositories/file/novel.py`](app/repositories/file/novel.py), [`app/repositories/postgres/novel.py`](app/repositories/postgres/novel.py), [`app/api.py`](app/api.py), [`app/story_record_api.py`](app/story_record_api.py), [`app/finding_review_api.py`](app/finding_review_api.py)
- Behavior: Original foreshadowing row receives private version/source/provenance/history/feedback metadata; original narrative event/proposal identity stays distinct. Versioned editor save binds expected digest and version; narrative findings use source-bound original FindingReviewService, not a Judge substitute.
- Version/conflict/cancel/recovery/restart: Retained 20-version history, restore to new version, explicit stale-source refresh, snapshot-bound feedback and actor/project/record local draft recovery. Legacy saves advance opted-in version/history; flag OFF retains legacy editor. Branch headers cannot access project-global rows. Exact source navigation retains dirty/IME/new-navigation guards; synchronous cancel never rolls back a committed save.
- Scope/permissions: Original project/chapter/asset/job and collaboration scope where supported; unavailable branch paths must reject, never substitute mainline; Original route/middleware trusted session, owner/current membership and operation-specific domain permission; no client role authority. Profile: `ORIGINAL_AUTHORITY`; explicit legacy gaps take precedence over common defaults.
- Flags: `story_record_versions_v1`, `finding_review_v1`. Dependencies remain server-owned: {"story_record_versions_v1": [], "finding_review_v1": []}.
- Navigation: FS_CONTINUITY, FS_PLANNING, CORE_MANUSCRIPT.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_narrative_api.py`](tests/test_narrative_api.py), [`tests/test_narrative_context.py`](tests/test_narrative_context.py), [`tests/test_narrative_detection.py`](tests/test_narrative_detection.py), [`tests/test_narrative_finding_api.py`](tests/test_narrative_finding_api.py), [`tests/test_narrative_finding_service.py`](tests/test_narrative_finding_service.py), [`tests/test_narrative_phase2c_rules.py`](tests/test_narrative_phase2c_rules.py). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Source-bound focused owner receipts (not final-head acceptance): [`docs/delivery/functional-surface-freeze/FINDINGS_AND_CANON_VERIFICATION.json`](docs/delivery/functional-surface-freeze/FINDINGS_AND_CANON_VERIFICATION.json), [`docs/delivery/functional-surface-freeze/STORY_RECORD_VERSIONING.md`](docs/delivery/functional-surface-freeze/STORY_RECORD_VERSIONING.md).
- Formal contract: [`contracts/functional-surfaces/findings-canon.v1.json`](contracts/functional-surfaces/findings-canon.v1.json), [`docs/delivery/functional-surface-freeze/STORY_RECORD_VERSIONING.md`](docs/delivery/functional-surface-freeze/STORY_RECORD_VERSIONING.md).
- Remaining boundaries: LEGACY_STRUCTURED_CAS_COMPATIBILITY, FINAL_SOURCE_CI.

#### FS_TIMELINE · Story timeline / World chronology

- Page/subpage: Story → Story timeline / World chronology. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Story timeline / World chronology.
- Components: [`frontend/src/novel/StoryDatabase.tsx`](frontend/src/novel/StoryDatabase.tsx), [`frontend/src/novel/StoryRecordVersionEditor.tsx`](frontend/src/novel/StoryRecordVersionEditor.tsx), [`frontend/src/novel/WorldTimelineView.tsx`](frontend/src/novel/WorldTimelineView.tsx), [`frontend/src/experimental/WorldPanel.tsx`](frontend/src/experimental/WorldPanel.tsx)
- Authority/model/store/API source: [`app/services/novel_service.py`](app/services/novel_service.py), [`app/experimental/world.py`](app/experimental/world.py), [`app/narrative.py`](app/narrative.py), [`app/lore/continuity.py`](app/lore/continuity.py), [`app/repositories/file/continuity.py`](app/repositories/file/continuity.py), [`app/repositories/postgres/continuity.py`](app/repositories/postgres/continuity.py), [`app/repositories/story_record_versions.py`](app/repositories/story_record_versions.py), [`app/repositories/file/novel.py`](app/repositories/file/novel.py), [`app/repositories/postgres/novel.py`](app/repositories/postgres/novel.py), [`app/api.py`](app/api.py), [`app/story_record_api.py`](app/story_record_api.py), [`app/experimental/world_api.py`](app/experimental/world_api.py)
- Behavior: Original Timeline row identity/public serialization remains authority; private version/source/provenance/history metadata adds expected-digest + expected-version CAS. World HISTORY is a separate reviewed chronology projection, and story time is distinct from media rational time.
- Version/conflict/cancel/recovery/restart: File atomic original-row replacement and PostgreSQL project/source locks; 20-version history, restore to new current version, current/stale/unlinked sources, terminal snapshot-bound feedback. Legacy saves advance opted-in history. Explicit draft/conflict recovery and exact source navigation retain manuscript dirty/IME guards; project-only authorization rejects branch headers. Continuity Timeline evidence uses the same original table through a narrow public-ID/storage-ID adapter: UUID events retain keys, opaque IDs use deterministic UUIDv5, public project IDs resolve as slugs, and same-owner retries are append-only. Collision, ambiguity or inconsistent/foreign owner metadata is rejected without rewrite.
- Scope/permissions: Original project/chapter/asset/job and collaboration scope where supported; unavailable branch paths must reject, never substitute mainline; Original route/middleware trusted session, owner/current membership and operation-specific domain permission; no client role authority. Profile: `ORIGINAL_AUTHORITY`; explicit legacy gaps take precedence over common defaults.
- Flags: `story_record_versions_v1`, `world_character_engines_v2`. Dependencies remain server-owned: {"story_record_versions_v1": [], "world_character_engines_v2": []}.
- Navigation: FS_CONTINUITY, A04, CORE_MANUSCRIPT.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_continuity_api.py`](tests/test_continuity_api.py), [`tests/test_continuity_engine.py`](tests/test_continuity_engine.py), [`tests/test_continuity_foundations.py`](tests/test_continuity_foundations.py), [`tests/test_continuity_lifecycle.py`](tests/test_continuity_lifecycle.py), [`tests/test_continuity_rules.py`](tests/test_continuity_rules.py), [`tests/test_continuity_semantic_rules.py`](tests/test_continuity_semantic_rules.py). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Source-bound focused owner receipts (not final-head acceptance): [`docs/delivery/functional-surface-freeze/STORY_RECORD_VERSIONING.md`](docs/delivery/functional-surface-freeze/STORY_RECORD_VERSIONING.md), [`docs/SURFACE_CONTINUITY_TIMELINE_IDENTITY.md`](docs/SURFACE_CONTINUITY_TIMELINE_IDENTITY.md).
- Formal contract: [`docs/delivery/functional-surface-freeze/STORY_RECORD_VERSIONING.md`](docs/delivery/functional-surface-freeze/STORY_RECORD_VERSIONING.md), [`docs/SURFACE_CONTINUITY_TIMELINE_IDENTITY.md`](docs/SURFACE_CONTINUITY_TIMELINE_IDENTITY.md).
- Remaining boundaries: LEGACY_STRUCTURED_CAS_COMPATIBILITY, FINAL_SOURCE_CI.

#### FS_STORY_DATABASE · Characters / Locations / Relationships / World rules

- Page/subpage: Story → Characters / Locations / Relationships / World rules. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / existing Characters / Locations / Relationships / World rules.
- Components: [`frontend/src/novel/StoryDatabase.tsx`](frontend/src/novel/StoryDatabase.tsx), [`frontend/src/novel/StoryRecordVersionEditor.tsx`](frontend/src/novel/StoryRecordVersionEditor.tsx), [`frontend/src/novel/WorldBuildingDashboard.tsx`](frontend/src/novel/WorldBuildingDashboard.tsx), [`frontend/src/novel/WorldRelationshipGraph.tsx`](frontend/src/novel/WorldRelationshipGraph.tsx)
- Authority/model/store/API source: [`app/services/novel_service.py`](app/services/novel_service.py), [`app/services/lore_service.py`](app/services/lore_service.py), [`app/repositories/structured_cas.py`](app/repositories/structured_cas.py), [`app/repositories/story_record_versions.py`](app/repositories/story_record_versions.py), [`app/repositories/file/novel.py`](app/repositories/file/novel.py), [`app/repositories/postgres/novel.py`](app/repositories/postgres/novel.py), [`app/repositories/postgres/serialization.py`](app/repositories/postgres/serialization.py), [`app/api.py`](app/api.py), [`app/story_record_api.py`](app/story_record_api.py)
- Behavior: Original Character/Location/Relationship rows now share the existing five-kind StoryRecord version owner with Timeline/Foreshadowing. Flag-ON current project editors require exact digest and version; original IDs, sparse public shape, opaque imported fields and privacy survive guarded edits/history/restore. World-rule proposal review retains its original separate owner.
- Version/conflict/cancel/recovery/restart: Original File project lock/atomic replacement and PostgreSQL original-row transaction/CAS; 20 retained snapshots, restore to new current version, terminal source-bound feedback and explicit stale-source refresh. Relationships pin exact Character/Timeline identities; exact known Character location pins its digest, historical free text remains unlinked. Owner-keyed local draft/conflict recovery excludes secrets. Legacy OFF/component-only callbacks and historical direct clients remain compatible, advancing existing version metadata. Project Story authority rejects branch-only scope.
- Scope/permissions: Original project/chapter/asset/job and collaboration scope where supported; unavailable branch paths must reject, never substitute mainline; Original route/middleware trusted session, owner/current membership and operation-specific domain permission; no client role authority. Profile: `ORIGINAL_AUTHORITY`; explicit legacy gaps take precedence over common defaults.
- Flags: `story_record_versions_v1`. Dependencies remain server-owned: {"story_record_versions_v1": []}.
- Navigation: FS_TIMELINE, FS_FORESHADOWING, FS_CANON, A05, A04, U02.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_lore_context_contract.py`](tests/test_lore_context_contract.py), [`tests/test_lore_contract.py`](tests/test_lore_contract.py), [`tests/test_lore_postgres_contract.py`](tests/test_lore_postgres_contract.py), [`tests/test_lore_service.py`](tests/test_lore_service.py), [`tests/test_phase7_novel_import.py`](tests/test_phase7_novel_import.py), [`tests/test_postgres_context_serialization.py`](tests/test_postgres_context_serialization.py). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Operation permission boundaries: {"catalog_read": "Original PROJECT domain.read; no branch-authority promotion", "versioned_save_restore": "Original PROJECT domain.write plus mandatory expected digest/version, current source and flag when versioned entry is used", "feedback": "Original PROJECT domain.review plus snapshot CAS and terminal source-bound decision", "legacy_compatibility": "Flag-OFF/component-only and historical direct writers retain original behavior; prior opted-in metadata advances history"}.
- Source-bound focused owner receipts (not final-head acceptance): [`docs/CORE_STORY_RECORD_VERSION_CLOSURE.md`](docs/CORE_STORY_RECORD_VERSION_CLOSURE.md).
- Formal contract: [`docs/CORE_STORY_RECORD_VERSION_CLOSURE.md`](docs/CORE_STORY_RECORD_VERSION_CLOSURE.md).
- Remaining boundaries: LEGACY_STRUCTURED_CAS_COMPATIBILITY, FINAL_SOURCE_CI.

#### FS_UNIVERSE · Shared Universe / Selected snapshots

- Page/subpage: Story → Shared Universe / Selected snapshots. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Shared Universe / Selected snapshots.
- Components: [`frontend/src/experimental/SharedUniversePanel.tsx`](frontend/src/experimental/SharedUniversePanel.tsx)
- Authority/model/store/API source: [`app/experimental/project_forks.py`](app/experimental/project_forks.py), [`app/experimental/structured_forks.py`](app/experimental/structured_forks.py), [`app/experimental/project_forks_api.py`](app/experimental/project_forks_api.py)
- Behavior: Original fork service immutable selected Character/Location/Organization/Rule/Timeline snapshots and explicit Main/Sequel/Prequel/Side Story pins; source/target authority and privacy checked.
- Version/conflict/cancel/recovery/restart: CAS pin/update/release/history, readonly incoming references; source edits never auto-repin. Restore/reuse requires fresh original-source permission. No separate Canon or implicit author context.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `project_forks_v2`. Dependencies remain server-owned: {"project_forks_v2": ["revision_intelligence_v2", "asset_lineage_v2"]}.
- Navigation: B09, A04, FS_CANON.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_r5_project_forks.py`](tests/test_r5_project_forks.py), [`tests/test_r5_project_forks_mounted.py`](tests/test_r5_project_forks_mounted.py), [`tests/test_r5_structured_forks.py`](tests/test_r5_structured_forks.py), [`tests/test_r5_structured_forks_mounted.py`](tests/test_r5_structured_forks_mounted.py), [`frontend/src/experimental/SharedUniversePanel.test.tsx`](frontend/src/experimental/SharedUniversePanel.test.tsx). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### CORE_ADAPTATION · Adaptation / Blueprint / Screenplay draft

- Page/subpage: Story → Adaptation / Blueprint / Screenplay draft. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / existing Adaptation / Blueprint / Screenplay draft.
- Components: [`frontend/src/novel/AdaptationPanel.tsx`](frontend/src/novel/AdaptationPanel.tsx), [`frontend/src/novel/ScreenplayPipelinePanel.tsx`](frontend/src/novel/ScreenplayPipelinePanel.tsx), [`frontend/src/novel/PipelineStatusPanel.tsx`](frontend/src/novel/PipelineStatusPanel.tsx), [`frontend/src/novel/ConstraintImportPreview.tsx`](frontend/src/novel/ConstraintImportPreview.tsx), [`frontend/src/App.tsx`](frontend/src/App.tsx)
- Authority/model/store/API source: [`app/services/adaptation_service.py`](app/services/adaptation_service.py), [`app/services/screenplay_service.py`](app/services/screenplay_service.py), [`app/experimental/adaptation_projection.py`](app/experimental/adaptation_projection.py), [`app/repositories/adaptation_versions.py`](app/repositories/adaptation_versions.py), [`app/repositories/file/novel.py`](app/repositories/file/novel.py), [`app/repositories/postgres/novel.py`](app/repositories/postgres/novel.py), [`app/api.py`](app/api.py), [`app/adaptation_api.py`](app/adaptation_api.py)
- Behavior: Original NovelRepository adaptation_proposals owns revision/history and immutable source rich-document snapshots. Original endpoints delegate to the same adaptation router; explicit project versus branch authority never substitutes mainline. Source-bound drafts capture target version/digest and reviewed draft binding.
- Version/conflict/cancel/recovery/restart: Reserved target identities and durable write-intent/checkpoint before materialization; apply uses reviewed target version, including legacy flow. Cancel/recover are explicit flag-gated actions; uncertain writes require provable receipt reconciliation and are never replayed. Real model dispatch is NOT_CONFIGURED until original JobManager/broker admission. Original Task/Review projections carry exact proposal/task/source/target bindings and no generic mutations; App revalidates the exact task with namespace/epoch/abort/dirty guards before opening the existing panel. Capacity ceilings and terminal reserves are explicit; exact-head execution pending.
- Scope/permissions: Original project/chapter/asset/job and collaboration scope where supported; unavailable branch paths must reject, never substitute mainline; Original route/middleware trusted session, owner/current membership and operation-specific domain permission; no client role authority. Profile: `ORIGINAL_AUTHORITY`; explicit legacy gaps take precedence over common defaults.
- Flags: `adaptation_lifecycle_v1`. Dependencies remain server-owned: {"adaptation_lifecycle_v1": []}.
- Navigation: FS_BRANCH, CORE_MANUSCRIPT, FS_REVIEW, U07, CORE_SCREENPLAY.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_phase7_adaptation.py`](tests/test_phase7_adaptation.py), [`tests/test_phase7_adaptation_authorization.py`](tests/test_phase7_adaptation_authorization.py), [`tests/test_phase7_novel_import.py`](tests/test_phase7_novel_import.py), [`tests/test_phase8_screenplay.py`](tests/test_phase8_screenplay.py), [`tests/test_screenplay_branch_revision.py`](tests/test_screenplay_branch_revision.py), [`tests/test_screenplay_cas_history.py`](tests/test_screenplay_cas_history.py). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Source-bound focused owner receipts (not final-head acceptance): [`docs/delivery/functional-surface-freeze/ADAPTATION_LIFECYCLE_VERIFICATION.json`](docs/delivery/functional-surface-freeze/ADAPTATION_LIFECYCLE_VERIFICATION.json).
- Formal contract: [`docs/delivery/functional-surface-freeze/ADAPTATION_LIFECYCLE.md`](docs/delivery/functional-surface-freeze/ADAPTATION_LIFECYCLE.md), [`docs/delivery/functional-surface-freeze/ADAPTATION_FIXTURE_EXCEPTION.json`](docs/delivery/functional-surface-freeze/ADAPTATION_FIXTURE_EXCEPTION.json).
- Remaining boundaries: ADAPTATION_UNKNOWN_CREATION_RECOVERY, EXTERNAL_REAL_MODELS, FINAL_SOURCE_CI.

### Review

#### U06 · Change impact and selective refresh

- Page/subpage: Review → Change Impact / Selective refresh. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Change Impact / Selective refresh.
- Components: [`frontend/src/experimental/ChangeImpactPanel.tsx`](frontend/src/experimental/ChangeImpactPanel.tsx), [`frontend/src/experimental/MediaPanel.tsx`](frontend/src/experimental/MediaPanel.tsx)
- Authority/model/store/API source: [`app/experimental/media.py`](app/experimental/media.py), [`app/experimental/media_api.py`](app/experimental/media_api.py), [`app/experimental/change_impact.py`](app/experimental/change_impact.py), [`frontend/src/experimental/MediaPanel.tsx`](frontend/src/experimental/MediaPanel.tsx), [`frontend/src/experimental/ChangeImpactPanel.tsx`](frontend/src/experimental/ChangeImpactPanel.tsx), [`app/experimental/change_impact_api.py`](app/experimental/change_impact_api.py)
- Behavior: Original dependency graph and selected media brief/manifest owners; lock, source digest, preflight and expected version bind narrowly selected refresh.
- Version/conflict/cancel/recovery/restart: Prepare/execute/cancel per original task; token/late-result fence, persisted refresh records and explicit owner recovery. Image refresh is not a generic video/audio executor.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `change_impact_v2`. Dependencies remain server-owned: {"change_impact_v2": ["temporal_story_graph_v2", "asset_lineage_v2"]}.
- Navigation: A04, A09, A13, CORE_IMAGES, FS_PLANNING.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_post_interop_media_visibility.py`](tests/test_post_interop_media_visibility.py), [`tests/test_post_interop_media_continuation.py`](tests/test_post_interop_media_continuation.py), [`frontend/src/experimental/MediaPanel.continuation.test.tsx`](frontend/src/experimental/MediaPanel.continuation.test.tsx), [`frontend/src/experimental/ChangeImpactPanel.test.tsx`](frontend/src/experimental/ChangeImpactPanel.test.tsx), [`frontend/src/experimental/MediaPanel.recovery.test.tsx`](frontend/src/experimental/MediaPanel.recovery.test.tsx), [`tests/test_r4_change_impact.py`](tests/test_r4_change_impact.py). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### A02 · Style metrics and drift

- Page/subpage: Review → Style DNA / Drift / Opinions. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Style DNA / Drift / Opinions.
- Components: [`frontend/src/experimental/StyleAnalysisPanel.tsx`](frontend/src/experimental/StyleAnalysisPanel.tsx), [`frontend/src/experimental/StyleAnalysisModelPanel.tsx`](frontend/src/experimental/StyleAnalysisModelPanel.tsx)
- Authority/model/store/API source: [`app/experimental/style_analysis.py`](app/experimental/style_analysis.py), [`app/experimental/style_analysis_model.py`](app/experimental/style_analysis_model.py), [`frontend/src/experimental/StyleAnalysisPanel.tsx`](frontend/src/experimental/StyleAnalysisPanel.tsx), [`frontend/src/experimental/StyleAnalysisModelPanel.tsx`](frontend/src/experimental/StyleAnalysisModelPanel.tsx), [`app/experimental/style_analysis_api.py`](app/experimental/style_analysis_api.py)
- Behavior: Original STYLE creation record plus immutable analysis receipt, exact source ranges and deterministic metrics. Model opinions retain original jobs and reviewed evidence.
- Version/conflict/cancel/recovery/restart: CAS profile/opinion review, model cancel/refresh and stored history; source changes make analysis stale. Ignore/reopen is supported; it is not cross-run intentional dedup.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `style_dna_v2`. Dependencies remain server-owned: {"style_dna_v2": []}.
- Navigation: CORE_CREATION, U08, U07, A11.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_post_interop_style_judge.py`](tests/test_post_interop_style_judge.py), [`tests/test_post_interop_style_model.py`](tests/test_post_interop_style_model.py), [`frontend/src/experimental/StyleAnalysisModelPanel.test.tsx`](frontend/src/experimental/StyleAnalysisModelPanel.test.tsx). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: EXTERNAL_REAL_MODELS, FINAL_SOURCE_CI.

#### A03 · Evidence-based narrative judge

- Page/subpage: Review → Narrative Judge / Finding review. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Narrative Judge / Finding review.
- Components: [`frontend/src/experimental/NarrativeJudgePanel.tsx`](frontend/src/experimental/NarrativeJudgePanel.tsx), [`frontend/src/experimental/NarrativeJudgeModelPanel.tsx`](frontend/src/experimental/NarrativeJudgeModelPanel.tsx), [`frontend/src/experimental/NarrativeJudgeRevisionTaskPanel.tsx`](frontend/src/experimental/NarrativeJudgeRevisionTaskPanel.tsx)
- Authority/model/store/API source: [`app/experimental/narrative_judge.py`](app/experimental/narrative_judge.py), [`app/experimental/narrative_judge_model.py`](app/experimental/narrative_judge_model.py), [`app/experimental/writer_room.py`](app/experimental/writer_room.py), [`frontend/src/experimental/NarrativeJudgePanel.tsx`](frontend/src/experimental/NarrativeJudgePanel.tsx), [`frontend/src/experimental/NarrativeJudgeRevisionTaskPanel.tsx`](frontend/src/experimental/NarrativeJudgeRevisionTaskPanel.tsx), [`app/experimental/narrative_judge_api.py`](app/experimental/narrative_judge_api.py)
- Behavior: Evidence-bound deterministic findings and separate model advice; accept/ignore/intentional decisions use exact evidence keys and retain reason/review history.
- Version/conflict/cancel/recovery/restart: Same-evidence intentional suppression and explicit reopen; source version/CAS; model cancel/refresh; create original WriterRoom revision task. Approval never applies manuscript or Canon.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `narrative_quality_judge_v2`. Dependencies remain server-owned: {"narrative_quality_judge_v2": ["advanced_planning_v2", "world_character_engines_v2", "unified_review_inbox"]}.
- Navigation: B08, FS_REVIEW, U07, A11, FS_CONTINUITY.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_post_interop_style_judge_mounted.py`](tests/test_post_interop_style_judge_mounted.py), [`tests/test_post_interop_style_model.py`](tests/test_post_interop_style_model.py), [`frontend/src/experimental/NarrativeJudgeContinuationPanels.test.tsx`](frontend/src/experimental/NarrativeJudgeContinuationPanels.test.tsx), [`tests/test_post_interop_task_reopen.py`](tests/test_post_interop_task_reopen.py), [`frontend/src/experimental/ModelTaskReopen.test.tsx`](frontend/src/experimental/ModelTaskReopen.test.tsx), [`frontend/tests/e2e/r4-model-task-reopen.spec.ts`](frontend/tests/e2e/r4-model-task-reopen.spec.ts). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: EXTERNAL_REAL_MODELS, FINAL_SOURCE_CI.

#### A11 · Revision intelligence and partial changes

- Page/subpage: Review → Revision Intelligence / Comparison. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Revision Intelligence / Comparison.
- Components: [`frontend/src/experimental/RevisionIntelligencePanel.tsx`](frontend/src/experimental/RevisionIntelligencePanel.tsx), [`frontend/src/experimental/RevisionComparisonModelPanel.tsx`](frontend/src/experimental/RevisionComparisonModelPanel.tsx)
- Authority/model/store/API source: [`app/experimental/revision_intelligence.py`](app/experimental/revision_intelligence.py), [`app/experimental/revision_intelligence_model.py`](app/experimental/revision_intelligence_model.py), [`app/experimental/revision_intelligence_api.py`](app/experimental/revision_intelligence_api.py), [`frontend/src/experimental/RevisionIntelligencePanel.tsx`](frontend/src/experimental/RevisionIntelligencePanel.tsx), [`frontend/src/experimental/RevisionComparisonModelPanel.tsx`](frontend/src/experimental/RevisionComparisonModelPanel.tsx)
- Behavior: Original ChapterService history and rich-document version/range/digest own comparison; model opinions, partial proposals, locks and milestones reference those originals.
- Version/conflict/cancel/recovery/restart: Compare/review/rebase/partial apply uses original CAS and exact preview; stale acceptance denied. Cancel model through original job; restart keeps proposal/history and needs revalidation.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `revision_intelligence_v2`. Dependencies remain server-owned: {"revision_intelligence_v2": []}.
- Navigation: U05, CORE_MANUSCRIPT, U02, U07, FS_REVIEW.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_post_interop_revision_compare.py`](tests/test_post_interop_revision_compare.py), [`tests/test_post_interop_revision_model.py`](tests/test_post_interop_revision_model.py), [`tests/test_r4_revision_intelligence.py`](tests/test_r4_revision_intelligence.py), [`frontend/src/experimental/RevisionComparisonModelPanel.test.tsx`](frontend/src/experimental/RevisionComparisonModelPanel.test.tsx), [`frontend/src/experimental/RevisionIntelligencePanel.test.tsx`](frontend/src/experimental/RevisionIntelligencePanel.test.tsx), [`tests/test_r4_revision_intelligence_mounted.py`](tests/test_r4_revision_intelligence_mounted.py). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### U11 · Reading, proofreading and publishing checks

- Page/subpage: Review → Reader / Proofreading / Export preflight. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Reader / Proofreading / Export preflight.
- Components: [`frontend/src/experimental/ReaderPreflightPanel.tsx`](frontend/src/experimental/ReaderPreflightPanel.tsx), [`frontend/src/novel/ExportPanel.tsx`](frontend/src/novel/ExportPanel.tsx)
- Authority/model/store/API source: [`app/experimental/reader_preflight.py`](app/experimental/reader_preflight.py), [`app/services/export_job_service.py`](app/services/export_job_service.py), [`frontend/src/experimental/ReaderPreflightPanel.tsx`](frontend/src/experimental/ReaderPreflightPanel.tsx), [`frontend/src/novel/ExportPanel.tsx`](frontend/src/novel/ExportPanel.tsx), [`app/experimental/reader_preflight_api.py`](app/experimental/reader_preflight_api.py)
- Behavior: Read/proof/source snapshot and publish/export checks remain advisory until original export owner is explicitly invoked.
- Version/conflict/cancel/recovery/restart: Versioned preflight/history/current-source checks; cancel discards bounded read; restart regenerates current preflight. Native publishing/layout acceptance stays NOT_RUN.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `reader_preflight_v2`. Dependencies remain server-owned: {"reader_preflight_v2": []}.
- Navigation: CORE_EXPORT, A03, A11, U16.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`frontend/src/novel/ExportPanel.recovery.test.tsx`](frontend/src/novel/ExportPanel.recovery.test.tsx), [`frontend/src/novel/ExportPanel.scope.test.tsx`](frontend/src/novel/ExportPanel.scope.test.tsx), [`frontend/src/novel/ExportPanel.test.tsx`](frontend/src/novel/ExportPanel.test.tsx). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### FS_CONTINUITY · Continuity / Evidence / Author feedback

- Page/subpage: Review → Continuity / Evidence / Author feedback. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Continuity / Evidence / Author feedback.
- Components: [`frontend/src/novel/ContinuityCheckPanel.tsx`](frontend/src/novel/ContinuityCheckPanel.tsx), [`frontend/src/novel/FindingReviewPanel.tsx`](frontend/src/novel/FindingReviewPanel.tsx), [`frontend/src/novel/findingReviewClient.ts`](frontend/src/novel/findingReviewClient.ts), [`frontend/src/experimental/WorldPanel.tsx`](frontend/src/experimental/WorldPanel.tsx)
- Authority/model/store/API source: [`app/experimental/finding_review_composition.py`](app/experimental/finding_review_composition.py), [`app/services/continuity_finding_service.py`](app/services/continuity_finding_service.py), [`app/services/finding_review_service.py`](app/services/finding_review_service.py), [`app/lore/continuity.py`](app/lore/continuity.py), [`app/lore/continuity_engine.py`](app/lore/continuity_engine.py), [`app/lore/continuity_rules.py`](app/lore/continuity_rules.py), [`app/repositories/file/continuity.py`](app/repositories/file/continuity.py), [`app/repositories/postgres/continuity.py`](app/repositories/postgres/continuity.py), [`app/experimental/world.py`](app/experimental/world.py), [`app/api.py`](app/api.py), [`app/finding_review_api.py`](app/finding_review_api.py), [`app/experimental/world_api.py`](app/experimental/world_api.py)
- Behavior: Original continuity finding repository owns source-bound deterministic checks and OPEN/RESOLVED/INTENTIONAL decisions. Exact chapter owner/version/digest, facts digest and finding fingerprint bind feedback/reason/history; changed evidence becomes REVIEW_REQUIRED and identical source preserves intentional suppression. Stored Timeline facts retain opaque public IDs while the original persistence adapter resolves real project-slug ownership and UUID storage keys; no unrelated Story row or foreign payload is adopted.
- Version/conflict/cancel/recovery/restart: Expected review version, operation ID and human confirmation; exact historical evidence snapshot verified before navigation. Reopen/feedback remain available on stale rows; resolve/intentional require current evidence. File coordination and PostgreSQL locks; history bounded at 100. Synchronous check cancellation discards an uncommitted result, restart rereads original decisions. No Canon auto-write.
- Scope/permissions: Original project/chapter/asset/job and collaboration scope where supported; unavailable branch paths must reject, never substitute mainline; Original route/middleware trusted session, owner/current membership and operation-specific domain permission; no client role authority. Profile: `ORIGINAL_AUTHORITY`; explicit legacy gaps take precedence over common defaults.
- Flags: `ENABLE_CONTINUITY_RULES`, `finding_review_v1`, `world_character_engines_v2`. Dependencies remain server-owned: {"ENABLE_CONTINUITY_RULES": [], "finding_review_v1": [], "world_character_engines_v2": []}.
- Navigation: FS_FORESHADOWING, FS_TIMELINE, A03, CORE_MANUSCRIPT.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_continuity_api.py`](tests/test_continuity_api.py), [`tests/test_continuity_engine.py`](tests/test_continuity_engine.py), [`tests/test_continuity_foundations.py`](tests/test_continuity_foundations.py), [`tests/test_continuity_lifecycle.py`](tests/test_continuity_lifecycle.py), [`tests/test_continuity_rules.py`](tests/test_continuity_rules.py), [`tests/test_continuity_semantic_rules.py`](tests/test_continuity_semantic_rules.py). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Source-bound focused owner receipts (not final-head acceptance): [`docs/delivery/functional-surface-freeze/FINDINGS_AND_CANON_VERIFICATION.json`](docs/delivery/functional-surface-freeze/FINDINGS_AND_CANON_VERIFICATION.json), [`docs/SURFACE_CONTINUITY_TIMELINE_IDENTITY.md`](docs/SURFACE_CONTINUITY_TIMELINE_IDENTITY.md).
- Formal contract: [`contracts/functional-surfaces/findings-canon.v1.json`](contracts/functional-surfaces/findings-canon.v1.json), [`docs/delivery/functional-surface-freeze/FINDINGS_AND_CANON.md`](docs/delivery/functional-surface-freeze/FINDINGS_AND_CANON.md), [`docs/SURFACE_CONTINUITY_TIMELINE_IDENTITY.md`](docs/SURFACE_CONTINUITY_TIMELINE_IDENTITY.md).
- Remaining boundaries: FINAL_SOURCE_CI.

#### FS_REVIEW · Unified review inbox

- Page/subpage: Review → Unified review inbox. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Unified review inbox.
- Components: [`frontend/src/experimental/InboxPanel.tsx`](frontend/src/experimental/InboxPanel.tsx), [`frontend/src/novel/AgentResultReview.tsx`](frontend/src/novel/AgentResultReview.tsx), [`frontend/src/RevisionPanel.tsx`](frontend/src/RevisionPanel.tsx)
- Authority/model/store/API source: [`app/experimental/inbox.py`](app/experimental/inbox.py), [`app/experimental/legacy_inbox.py`](app/experimental/legacy_inbox.py), [`app/experimental/finding_review_composition.py`](app/experimental/finding_review_composition.py), [`app/experimental/adaptation_projection.py`](app/experimental/adaptation_projection.py), [`app/experimental/review_adapter_projection.py`](app/experimental/review_adapter_projection.py), [`app/experimental/inbox_api.py`](app/experimental/inbox_api.py), [`frontend/src/experimental/uxClient.ts`](frontend/src/experimental/uxClient.ts)
- Behavior: Read-through original-domain ReviewBinding with source, original ID, revision, permission, risk and allowed actions. Batch is explicitly restricted and does not invent missing selection/review consent.
- Version/conflict/cancel/recovery/restart: Unversioned legacy gates and shared branch-manuscript projections remain read-only exact-owner links; branch cancellation/review stays in the original scope/version/read+review endpoint and rechecks counterpart access. Finding/Canon generic Inbox navigation is FORMAL_TARGET_ONLY with manual original-panel route and no exact-open control. Adaptation Task/Review keeps exact original proposal/task/source/target pointers and no generic mutation; actual opening revalidates owner/source/target. Research/visual adapter receipt projections retain original creator/source permissions; navigation is FORMAL_SOURCE_ONLY with no rendered exact-open control or generic approval. Original detail must supply actual review evidence. Current forbidden/missing feature is unavailable, not an empty success. Restart rereads owners.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `unified_review_inbox`. Dependencies remain server-owned: {"unified_review_inbox": []}.
- Navigation: U07, A03, A11, FS_BRANCH, FS_PROCESSING, FS_CANON, FS_CONTINUITY, CORE_ADAPTATION, FS_RESEARCH_VISION, FS_VISUAL.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_r3_inbox.py`](tests/test_r3_inbox.py), [`tests/test_surface_adaptation_projection.py`](tests/test_surface_adaptation_projection.py), [`tests/test_surface_findings_canon_inbox.py`](tests/test_surface_findings_canon_inbox.py), [`frontend/src/experimental/InboxPanel.findings.test.tsx`](frontend/src/experimental/InboxPanel.findings.test.tsx), [`frontend/src/novel/AgentResultReview.test.tsx`](frontend/src/novel/AgentResultReview.test.tsx), [`frontend/src/RevisionPanel.test.tsx`](frontend/src/RevisionPanel.test.tsx). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

### Research

#### A10 · Layered research library

- Page/subpage: Research → Library / Source / Notes / Citations. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Library / Source / Notes / Citations.
- Components: [`frontend/src/experimental/ResearchLibraryPanel.tsx`](frontend/src/experimental/ResearchLibraryPanel.tsx), [`frontend/src/novel/ResearchPanel.tsx`](frontend/src/novel/ResearchPanel.tsx), [`frontend/src/experimental/EmbeddingPanel.tsx`](frontend/src/experimental/EmbeddingPanel.tsx)
- Authority/model/store/API source: [`app/experimental/research_library.py`](app/experimental/research_library.py), [`app/experimental/research_extract.py`](app/experimental/research_extract.py), [`app/experimental/embeddings.py`](app/experimental/embeddings.py), [`app/experimental/research_library_api.py`](app/experimental/research_library_api.py), [`frontend/src/experimental/ResearchLibraryPanel.tsx`](frontend/src/experimental/ResearchLibraryPanel.tsx), [`frontend/src/experimental/EmbeddingPanel.tsx`](frontend/src/experimental/EmbeddingPanel.tsx)
- Behavior: Original source bytes and source ID/version/digest own TXT/Markdown/DOCX/text PDF/web capture/image metadata; notes and citations link exact current paragraphs.
- Version/conflict/cancel/recovery/restart: Replace/restore/privacy/revoke/delete invalidates citations/indexes/analysis. Owner recovery can inspect only erased INVALIDATED vector receipts when the actor owns both original Research source and index in the exact current scope; former shared readers remain denied and queries stay blocked. Original source archive/history and authorized byte recovery retain their own permission checks. Research remains LOCAL_ONLY; setting drafts cannot auto-promote to Canon.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `research_library_v2`. Dependencies remain server-owned: {"research_library_v2": ["semantic_import_v2", "temporal_story_graph_v2"]}.
- Navigation: FS_SEMANTIC, FS_RESEARCH_VISION, FS_IMPORT, U08, FS_CANON.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_post_interop_wave3_research.py`](tests/test_post_interop_wave3_research.py), [`tests/test_post_interop_wave3_embedding_adapter.py`](tests/test_post_interop_wave3_embedding_adapter.py), [`tests/test_post_interop_embedding_feature_isolation.py`](tests/test_post_interop_embedding_feature_isolation.py), [`frontend/src/experimental/EmbeddingPanel.continuation.test.tsx`](frontend/src/experimental/EmbeddingPanel.continuation.test.tsx), [`frontend/src/experimental/ResearchLibraryPanel.continuation.test.tsx`](frontend/src/experimental/ResearchLibraryPanel.continuation.test.tsx), [`frontend/src/experimental/ResearchLibraryPanel.test.tsx`](frontend/src/experimental/ResearchLibraryPanel.test.tsx). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### FS_IMPORT · Manuscript import / Import health / Extraction

- Page/subpage: Research → Manuscript import / Import health / Extraction. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Manuscript import / Import health / Extraction.
- Components: [`frontend/src/novel/NovelImportPanel.tsx`](frontend/src/novel/NovelImportPanel.tsx), [`frontend/src/experimental/ImportPanel.tsx`](frontend/src/experimental/ImportPanel.tsx)
- Authority/model/store/API source: [`app/services/import_review_service.py`](app/services/import_review_service.py), [`app/services/import_apply_service.py`](app/services/import_apply_service.py), [`app/import_parsers.py`](app/import_parsers.py), [`app/experimental/imports.py`](app/experimental/imports.py), [`app/api.py`](app/api.py), [`app/experimental/imports_api.py`](app/experimental/imports_api.py)
- Behavior: Original parser/source digest and versioned knowledge review, chunk/import candidate records. Preview health reports unsupported/empty/bad input; selected apply uses original data owners and partial-apply journal.
- Version/conflict/cancel/recovery/restart: Cancel stops future work, not already committed selected candidates. Recover reads exact apply journal and never replays committed writes; real OCR/Vision goes through FS_RESEARCH_VISION.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `semantic_import_v2`. Dependencies remain server-owned: {"semantic_import_v2": []}.
- Navigation: A10, FS_REVIEW, CORE_MANUSCRIPT, U14.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_export_snapshot_and_import_review.py`](tests/test_export_snapshot_and_import_review.py), [`tests/test_import_parsers.py`](tests/test_import_parsers.py), [`tests/test_r2_import_apply_journal.py`](tests/test_r2_import_apply_journal.py), [`frontend/src/novel/NovelImportPanel.test.tsx`](frontend/src/novel/NovelImportPanel.test.tsx). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### FS_SEMANTIC · Semantic / Hybrid retrieval and indexes

- Page/subpage: Research → Semantic / Hybrid retrieval and indexes. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Semantic / Hybrid retrieval and indexes.
- Components: [`frontend/src/experimental/EmbeddingPanel.tsx`](frontend/src/experimental/EmbeddingPanel.tsx)
- Authority/model/store/API source: [`app/experimental/embeddings.py`](app/experimental/embeddings.py), [`app/experimental/vector_index.py`](app/experimental/vector_index.py), [`app/experimental/embeddings_api.py`](app/experimental/embeddings_api.py)
- Behavior: Existing EmbeddingProvider and persisted index/vector owner; bounded exact cosine and weighted reciprocal-rank fusion with live lexical scores. Query and hybrid-query require domain.read plus current index/source visibility, while mutations retain domain.write; read-only permission does not bypass source privacy or branch scope. Character/Story/Research/Asset source version/digest and index version are pinned.
- Version/conflict/cancel/recovery/restart: Create/edit/rebuild/invalidate/remove/cancel; atomic publication checks token/source/provider/permission. After Research delete/revoke, only an actor who owns both source and index may inspect retained INVALIDATED receipts in the exact scope, under current feature authority; every stored vector must be erased and is never returned. Former shared readers remain denied; invalidated query remains blocked. Interrupted BUILDING requires explicit cancel/invalidate/rebuild. Missing embedding provider stays NOT_CONFIGURED; synthetic vectors MOCK_ONLY.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `visual_embeddings`. Dependencies remain server-owned: {"visual_embeddings": []}.
- Navigation: U03, A10, FS_VISUAL, CORE_MODELS.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`frontend/src/experimental/EmbeddingPanel.continuation.test.tsx`](frontend/src/experimental/EmbeddingPanel.continuation.test.tsx), [`frontend/src/experimental/EmbeddingPanel.hybrid.test.tsx`](frontend/src/experimental/EmbeddingPanel.hybrid.test.tsx), [`tests/test_surface_hybrid_read_authority.py`](tests/test_surface_hybrid_read_authority.py), [`tests/test_surface_embedding_invalidation_receipts.py`](tests/test_surface_embedding_invalidation_receipts.py), [`tests/test_surface_search_visual_research.py`](tests/test_surface_search_visual_research.py), [`frontend/tests/e2e/surface-freeze-search-hybrid.spec.ts`](frontend/tests/e2e/surface-freeze-search-hybrid.spec.ts). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Operation permission boundaries: {"query_and_hybrid_query": "domain.read plus current original index/source visibility and scope; before/after feature and authority checks", "index_mutations": "domain.write plus original source/creator, expected version and publication guards"}.
- Source-bound focused owner receipts (not final-head acceptance): [`docs/SURFACE_ADAPTER_RECOVERY_COMPLETION.md`](docs/SURFACE_ADAPTER_RECOVERY_COMPLETION.md).
- Formal contract: [`contracts/functional-surfaces/search-visual-research.v1.json`](contracts/functional-surfaces/search-visual-research.v1.json), [`docs/SURFACE_ADAPTER_RECOVERY_COMPLETION.md`](docs/SURFACE_ADAPTER_RECOVERY_COMPLETION.md).
- Remaining boundaries: EXTERNAL_REAL_MODELS, FINAL_SOURCE_CI.

#### FS_RESEARCH_VISION · OCR / Scanned PDF / Image / Chart / Table

- Page/subpage: Research → OCR / Scanned PDF / Image / Chart / Table. Entry: **FORMAL_UI_SURFACE_CONTRACT**.
- Current host: Shared AppShell / NOVEL experimental workbench / OCR / Scanned PDF / Image / Chart / Table; adjacent existing component is an integration host, NOT proof new inspector controls are rendered.
- Components: [`frontend/src/experimental/ResearchLibraryPanel.tsx`](frontend/src/experimental/ResearchLibraryPanel.tsx)
- Authority/model/store/API source: [`app/experimental/research_vision.py`](app/experimental/research_vision.py), [`app/experimental/review_adapter_jobs.py`](app/experimental/review_adapter_jobs.py), [`app/experimental/review_adapter_projection.py`](app/experimental/review_adapter_projection.py), [`app/experimental/research_library.py`](app/experimental/research_library.py), [`app/experimental/research_library_api.py`](app/experimental/research_library_api.py)
- Behavior: Original Research source ID/version/original digest and typed page/bbox/table-block result; private durable analysis review receipt and derived citation digest. Original bytes remain intact.
- Version/conflict/cancel/recovery/restart: Create/run/cancel/invalidate/recover/review uses bounded original receipts with reserved terminal/recovery/invalidation capacity and token fences. Repeated terminal cancel/invalidate is idempotent; revoked-source responses omit request/lineage/results. Reads retain original Research domain.write plus source/creator visibility. Tasks/Review project original receipts; cancel delegates original owner write+CAS, no generic approval/retry. FORMAL_SOURCE_ONLY target, no rendered exact-open control. Real admission NOT_CONFIGURED/MOCK_ONLY; no durable worker or restart replay.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; domain.write plus original Research source/creator visibility; Current domain.write and original receipt CAS/state/capacity through original owner; recheck before and after original-owner reads. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `research_library_v2`. Dependencies remain server-owned: {"research_library_v2": ["semantic_import_v2", "temporal_story_graph_v2"]}.
- Navigation: A10, FS_SEMANTIC, U07, FS_REVIEW.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_r4_research_library.py`](tests/test_r4_research_library.py), [`tests/test_r4_research_library_mounted.py`](tests/test_r4_research_library_mounted.py), [`frontend/src/experimental/ResearchLibraryPanel.continuation.test.tsx`](frontend/src/experimental/ResearchLibraryPanel.continuation.test.tsx), [`frontend/src/experimental/ResearchLibraryPanel.test.tsx`](frontend/src/experimental/ResearchLibraryPanel.test.tsx), [`tests/test_surface_adapter_capacity.py`](tests/test_surface_adapter_capacity.py), [`tests/test_surface_adapter_projection.py`](tests/test_surface_adapter_projection.py). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Operation permission boundaries: {"read": "domain.write plus original Research source/creator visibility", "cancel": "Current domain.write and original receipt CAS/state/capacity through original owner", "generic_review": "No approve or batch approve; original inspector remains FORMAL_SOURCE_ONLY without rendered exact-open control"}.
- Receipt capacity/recovery contract: {"owner": "Existing ReviewAdapterJobs metadata of the original Research/Embedding service", "history_entries": 100, "receipt_bytes": 8388608, "current_snapshot_bytes": 786432, "result_bytes": 524288, "run_free_revision_slots_required": 6, "capacity_behavior": "Reserve claim/terminal/review/cancel/recover/source-invalidation tail before dispatch; no eviction/truncation. Explicit new receipt required after finite admission exhausted.", "terminal_behavior": "Repeated same-state cancel/invalidate is an idempotent no-op; source replacement/revocation uses bounded invalidation.", "revoked_payload_behavior": "Cancel/invalidate/stale responses withhold request/source snapshot/model/result digest; conflict only exposes ID/version/status. Projections contain receipt identity/version/status, no source lineage or result.", "restart_behavior": "RUNNING reports recovery required; explicit recover/cancel fences token; no automatic replay or durable-worker claim"}.
- Source-bound focused owner receipts (not final-head acceptance): [`docs/SURFACE_ADAPTER_RECOVERY_COMPLETION.md`](docs/SURFACE_ADAPTER_RECOVERY_COMPLETION.md).
- Formal contract: [`contracts/functional-surfaces/search-visual-research.v1.json`](contracts/functional-surfaces/search-visual-research.v1.json), [`docs/SURFACE_ADAPTER_RECOVERY_COMPLETION.md`](docs/SURFACE_ADAPTER_RECOVERY_COMPLETION.md).
- Remaining boundaries: FORMAL_NEW_INSPECTORS, EXTERNAL_REAL_MODELS, FINAL_SOURCE_CI.

### Production

#### A13 · Production manifest and controlled replay

- Page/subpage: Production → Production manifest / Controlled replay. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Production manifest / Controlled replay.
- Components: [`frontend/src/experimental/ProductionLineagePanel.tsx`](frontend/src/experimental/ProductionLineagePanel.tsx)
- Authority/model/store/API source: [`app/experimental/production_lineage.py`](app/experimental/production_lineage.py), [`app/experimental/media.py`](app/experimental/media.py), [`frontend/src/experimental/ProductionLineagePanel.tsx`](frontend/src/experimental/ProductionLineagePanel.tsx), [`app/experimental/production_lineage_api.py`](app/experimental/production_lineage_api.py), [`app/experimental/media_api.py`](app/experimental/media_api.py)
- Behavior: Same manifest and original media execution owners as A09; traceability, preflight replayability, approximate reproduction and measured byte equality are distinct.
- Version/conflict/cancel/recovery/restart: Explicit source/configuration/permission/version revalidation; cancel belongs to original replay task. Restart does not rerun; missing hashes/configuration require user action.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `production_manifest_v2`. Dependencies remain server-owned: {"production_manifest_v2": ["asset_lineage_v2", "cover_storyboard_generation", "media_adapter_registry"]}.
- Navigation: A09, CORE_IMAGES, U16, U07.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_post_interop_media_continuation.py`](tests/test_post_interop_media_continuation.py), [`tests/test_r4_production_mounted.py`](tests/test_r4_production_mounted.py), [`frontend/src/experimental/ProductionLineagePanel.continuation.test.tsx`](frontend/src/experimental/ProductionLineagePanel.continuation.test.tsx), [`frontend/src/experimental/ProductionLineagePanel.test.tsx`](frontend/src/experimental/ProductionLineagePanel.test.tsx), [`tests/test_r4_production_lineage.py`](tests/test_r4_production_lineage.py). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### A08 · Camera grammar and scene direction

- Page/subpage: Production → Screenplay / Director / Shots. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Screenplay / Director / Shots.
- Components: [`frontend/src/experimental/DirectorPanel.tsx`](frontend/src/experimental/DirectorPanel.tsx), [`frontend/src/novel/DirectorShotCard.tsx`](frontend/src/novel/DirectorShotCard.tsx), [`frontend/src/novel/DirectorShotList.tsx`](frontend/src/novel/DirectorShotList.tsx), [`frontend/src/novel/ScreenplayPanel.tsx`](frontend/src/novel/ScreenplayPanel.tsx)
- Authority/model/store/API source: [`app/experimental/director.py`](app/experimental/director.py), [`app/services/screenplay_service.py`](app/services/screenplay_service.py), [`frontend/src/experimental/DirectorPanel.tsx`](frontend/src/experimental/DirectorPanel.tsx), [`frontend/src/novel/DirectorShotCard.tsx`](frontend/src/novel/DirectorShotCard.tsx), [`app/experimental/director_api.py`](app/experimental/director_api.py)
- Behavior: Original screenplay/Scene/Shot authority and reviewed director proposals; camera grammar/rhythm are declared metadata checks, not cinematic quality proof.
- Version/conflict/cancel/recovery/restart: Versioned screenplay edit and proposal review, source-current history/restore; cancel preserves draft. Restart uses original proposals and never dispatches media automatically.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `ai_director_v2`. Dependencies remain server-owned: {"ai_director_v2": []}.
- Navigation: CORE_SCREENPLAY, CORE_IMAGES, CORE_VIDEO, A12, B06.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_post_interop_media_continuation.py`](tests/test_post_interop_media_continuation.py), [`tests/test_r4_director.py`](tests/test_r4_director.py), [`frontend/src/experimental/DirectorPanel.test.tsx`](frontend/src/experimental/DirectorPanel.test.tsx), [`frontend/src/novel/DirectorShotCard.test.tsx`](frontend/src/novel/DirectorShotCard.test.tsx), [`frontend/src/novel/DirectorShotList.test.tsx`](frontend/src/novel/DirectorShotList.test.tsx), [`frontend/src/novel/ScreenplayPanel.test.tsx`](frontend/src/novel/ScreenplayPanel.test.tsx). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### A12 · OTIO and NLE exchange

- Page/subpage: Production → Timeline / OTIO exchange. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Timeline / OTIO exchange.
- Components: [`frontend/src/experimental/TimelineExchangePanel.tsx`](frontend/src/experimental/TimelineExchangePanel.tsx), [`frontend/src/novel/VideoTimeline.tsx`](frontend/src/novel/VideoTimeline.tsx)
- Authority/model/store/API source: [`app/experimental/timeline_exchange.py`](app/experimental/timeline_exchange.py), [`app/industry_export_formats.py`](app/industry_export_formats.py), [`frontend/src/experimental/TimelineExchangePanel.tsx`](frontend/src/experimental/TimelineExchangePanel.tsx), [`app/experimental/timeline_exchange_api.py`](app/experimental/timeline_exchange_api.py)
- Behavior: Original OTIO timeline and exact rational media time; supported track/clip/transition schema and media identity are retained, unsupported fields reported.
- Version/conflict/cancel/recovery/restart: Explicit preview/import/export/review with source/version fences; cancel discards synchronous result; repeat from reviewed current snapshot. Real NLE import/export NOT_RUN.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `timeline_exchange_v2`. Dependencies remain server-owned: {"timeline_exchange_v2": ["asset_lineage_v2"]}.
- Navigation: CORE_VIDEO, CORE_ASSETS, B04, CORE_EXPORT.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_post_interop_media_continuation.py`](tests/test_post_interop_media_continuation.py), [`tests/test_r4_timeline_exchange.py`](tests/test_r4_timeline_exchange.py), [`tests/test_r4_director_exchange_mounted.py`](tests/test_r4_director_exchange_mounted.py), [`frontend/src/experimental/TimelineExchangePanel.test.tsx`](frontend/src/experimental/TimelineExchangePanel.test.tsx), [`frontend/src/novel/VideoTimeline.test.tsx`](frontend/src/novel/VideoTimeline.test.tsx). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: EXTERNAL_TARGETS, FINAL_SOURCE_CI.

#### B03 · Voice direction and speaker attribution

- Page/subpage: Production → Voice direction / Attribution / Audiobook. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Voice direction / Attribution / Audiobook.
- Components: [`frontend/src/experimental/AudiobookPanel.tsx`](frontend/src/experimental/AudiobookPanel.tsx), [`frontend/src/experimental/VoiceDirectionPanel.tsx`](frontend/src/experimental/VoiceDirectionPanel.tsx), [`frontend/src/novel/AudiobookManifestPanel.tsx`](frontend/src/novel/AudiobookManifestPanel.tsx), [`frontend/src/novel/SpeechSynthesisPanel.tsx`](frontend/src/novel/SpeechSynthesisPanel.tsx), [`frontend/src/novel/DirectorVoiceToolbar.tsx`](frontend/src/novel/DirectorVoiceToolbar.tsx)
- Authority/model/store/API source: [`app/experimental/audiobook.py`](app/experimental/audiobook.py), [`app/experimental/voice_direction.py`](app/experimental/voice_direction.py), [`app/audio_production_store.py`](app/audio_production_store.py), [`frontend/src/experimental/AudiobookPanel.tsx`](frontend/src/experimental/AudiobookPanel.tsx), [`frontend/src/experimental/VoiceDirectionPanel.tsx`](frontend/src/experimental/VoiceDirectionPanel.tsx), [`app/experimental/audiobook_api.py`](app/experimental/audiobook_api.py), [`app/experimental/voice_direction_api.py`](app/experimental/voice_direction_api.py)
- Behavior: Original voice mapping, character/scene/utterance/emotion and audio/TTS jobs; unknown speaker remains NEEDS_REVIEW. Measured WAV frames and original mix proposal own timing.
- Version/conflict/cancel/recovery/restart: Per-segment review/CAS/source versions, job cancel and explicit original-owner recovery. Bounded PCM mix is synchronous; restart does not generate or mix automatically.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `voice_direction_v2`. Dependencies remain server-owned: {"voice_direction_v2": ["audiobook_v2"]}.
- Navigation: CORE_AUDIO, FS_PROCESSING, B04, U07, FS_REVIEW.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_post_interop_media_continuation.py`](tests/test_post_interop_media_continuation.py), [`tests/test_r5_voice_subtitles.py`](tests/test_r5_voice_subtitles.py), [`frontend/src/experimental/VoiceDirectionPanel.continuation.test.tsx`](frontend/src/experimental/VoiceDirectionPanel.continuation.test.tsx), [`frontend/src/novel/AudiobookManifestPanel.test.tsx`](frontend/src/novel/AudiobookManifestPanel.test.tsx), [`frontend/src/novel/SpeechSynthesisPanel.test.tsx`](frontend/src/novel/SpeechSynthesisPanel.test.tsx), [`tests/test_r3_audiobook_preparation.py`](tests/test_r3_audiobook_preparation.py). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### B04 · Subtitle editing and timeline

- Page/subpage: Production → Subtitles / Caption timeline. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Subtitles / Caption timeline.
- Components: [`frontend/src/experimental/SubtitleTimelinePanel.tsx`](frontend/src/experimental/SubtitleTimelinePanel.tsx)
- Authority/model/store/API source: [`app/experimental/subtitle_timeline.py`](app/experimental/subtitle_timeline.py), [`app/experimental/voice_direction.py`](app/experimental/voice_direction.py), [`frontend/src/experimental/SubtitleTimelinePanel.tsx`](frontend/src/experimental/SubtitleTimelinePanel.tsx), [`app/experimental/subtitle_timeline_api.py`](app/experimental/subtitle_timeline_api.py)
- Behavior: Original caption cue rows, rational timebase and measured source audio/video duration own manual/measured timing and SRT/WebVTT exports.
- Version/conflict/cancel/recovery/restart: CAS/save/review/history and stale-source refusal; cancel discards synchronous edits/results, persisted caption reopened after restart. ASR/alignment/burn-in handled by FS_PROCESSING.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `subtitle_timeline_v2`. Dependencies remain server-owned: {"subtitle_timeline_v2": ["voice_direction_v2"]}.
- Navigation: FS_PROCESSING, B03, A12, CORE_VIDEO.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_r5_voice_subtitles.py`](tests/test_r5_voice_subtitles.py), [`tests/test_r5_voice_subtitles_mounted.py`](tests/test_r5_voice_subtitles_mounted.py), [`frontend/src/experimental/VoiceSubtitlePanels.test.tsx`](frontend/src/experimental/VoiceSubtitlePanels.test.tsx). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### B06 · Comic and Webtoon layouts

- Page/subpage: Production → Comics / Webtoon. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Comics / Webtoon.
- Components: [`frontend/src/experimental/ComicLayoutsPanel.tsx`](frontend/src/experimental/ComicLayoutsPanel.tsx)
- Authority/model/store/API source: [`app/experimental/comic_layouts.py`](app/experimental/comic_layouts.py), [`app/services/asset_library_service.py`](app/services/asset_library_service.py), [`frontend/src/experimental/ComicLayoutsPanel.tsx`](frontend/src/experimental/ComicLayoutsPanel.tsx), [`app/experimental/comic_layouts_api.py`](app/experimental/comic_layouts_api.py)
- Behavior: Same approved AssetLibrary/reference identity and original Scene/Shot links; panel order, bubbles, page/vertical exports and source digests are explicit.
- Version/conflict/cancel/recovery/restart: Versioned layout/edit/review/export/history with asset approval/hash fences; cancel synchronous render/discard, restart reopens persisted layout. Professional art/font/print quality NOT_RUN.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `comic_layouts_v2`. Dependencies remain server-owned: {"comic_layouts_v2": ["asset_lineage_v2", "ai_director_v2"]}.
- Navigation: CORE_ASSETS, FS_VISUAL, A08, CORE_EXPORT.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_post_interop_wave5_templates_sdk_comics.py`](tests/test_post_interop_wave5_templates_sdk_comics.py), [`tests/test_r5_comic_layouts.py`](tests/test_r5_comic_layouts.py), [`frontend/src/experimental/Wave5TemplatesSdkComics.test.tsx`](frontend/src/experimental/Wave5TemplatesSdkComics.test.tsx), [`frontend/src/experimental/ComicLayoutsPanel.test.tsx`](frontend/src/experimental/ComicLayoutsPanel.test.tsx). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: EXTERNAL_TARGETS, FINAL_SOURCE_CI.

#### B07 · Interactive narrative export

- Page/subpage: Production → Interactive Story / Visual Novel. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Interactive Story / Visual Novel.
- Components: [`frontend/src/experimental/InteractiveStoryPanel.tsx`](frontend/src/experimental/InteractiveStoryPanel.tsx), [`frontend/src/experimental/InteractiveStoryHistory.tsx`](frontend/src/experimental/InteractiveStoryHistory.tsx), [`frontend/src/experimental/InteractiveStoryPreview.tsx`](frontend/src/experimental/InteractiveStoryPreview.tsx)
- Authority/model/store/API source: [`app/experimental/interactive_story.py`](app/experimental/interactive_story.py), [`app/experimental/planning.py`](app/experimental/planning.py), [`frontend/src/experimental/InteractiveStoryPanel.tsx`](frontend/src/experimental/InteractiveStoryPanel.tsx), [`frontend/src/experimental/InteractiveStoryHistory.tsx`](frontend/src/experimental/InteractiveStoryHistory.tsx), [`app/experimental/interactive_story_api.py`](app/experimental/interactive_story_api.py)
- Behavior: Original planning-node adaptation rows, typed conditions/variables/routes/endings and bounded reachability own review/playback/export.
- Version/conflict/cancel/recovery/restart: Version/digest/source-current review, export preview, history/restore and stale refusal. Cancel pure bounded export discards response; no engine run or deploy on resume/restart.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `interactive_story_v2`. Dependencies remain server-owned: {"interactive_story_v2": ["advanced_planning_v2", "temporal_story_graph_v2"]}.
- Navigation: FS_ENGINES, FS_PLANNING, A04, CORE_EXPORT.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_post_interop_interactive_history.py`](tests/test_post_interop_interactive_history.py), [`tests/test_r5_interactive_story.py`](tests/test_r5_interactive_story.py), [`tests/test_post_interop_extended_mounted.py`](tests/test_post_interop_extended_mounted.py), [`frontend/src/experimental/InteractiveStoryPanel.test.tsx`](frontend/src/experimental/InteractiveStoryPanel.test.tsx), [`frontend/src/experimental/InteractiveStoryHistory.test.tsx`](frontend/src/experimental/InteractiveStoryHistory.test.tsx), [`tests/test_r5_interactive_story_mounted.py`](tests/test_r5_interactive_story_mounted.py). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### CORE_IMAGES · Image / Cover / Storyboard / Character reference / Edit / Multi-reference

- Page/subpage: Production → Image / Cover / Storyboard / Character reference / Edit / Multi-reference. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Image / Cover / Storyboard / Character reference / Edit / Multi-reference.
- Components: [`frontend/src/novel/ImageGenerationPanel.tsx`](frontend/src/novel/ImageGenerationPanel.tsx), [`frontend/src/novel/ImageQueuePanel.tsx`](frontend/src/novel/ImageQueuePanel.tsx), [`frontend/src/novel/ImageInfiniteCanvas.tsx`](frontend/src/novel/ImageInfiniteCanvas.tsx), [`frontend/src/novel/ImageTaskInspector.tsx`](frontend/src/novel/ImageTaskInspector.tsx), [`frontend/src/experimental/MediaPanel.tsx`](frontend/src/experimental/MediaPanel.tsx), [`frontend/src/novel/AssetTaskExecutionPanel.tsx`](frontend/src/novel/AssetTaskExecutionPanel.tsx), [`frontend/src/novel/VisionAnalysisPanel.tsx`](frontend/src/novel/VisionAnalysisPanel.tsx), [`frontend/src/novel/VisualTextWorkflow.tsx`](frontend/src/novel/VisualTextWorkflow.tsx)
- Authority/model/store/API source: [`app/services/image_job_service.py`](app/services/image_job_service.py), [`app/asset_providers.py`](app/asset_providers.py), [`app/experimental/media.py`](app/experimental/media.py), [`app/api.py`](app/api.py), [`app/experimental/media_api.py`](app/experimental/media_api.py)
- Behavior: Original image jobs, assets and versioned media briefs own actual provider dispatch, attempts, source references and human acceptance. Qwen-Image/FLUX/FLUX.2 schema availability is distinct from executable configuration.
- Version/conflict/cancel/recovery/restart: Single-image bridge rejects unsupported reference conditioning; edit/multi-reference schemas do not mean actual adapter support. Real image quality NOT_RUN; configured route/credential/license gates remain.
- Scope/permissions: Original project/chapter/asset/job and collaboration scope where supported; unavailable branch paths must reject, never substitute mainline; Original route/middleware trusted session, owner/current membership and operation-specific domain permission; no client role authority. Profile: `ORIGINAL_AUTHORITY`; explicit legacy gaps take precedence over common defaults.
- Flags: `media_adapter_registry`, `cover_storyboard_generation`. Dependencies remain server-owned: {"media_adapter_registry": [], "cover_storyboard_generation": []}.
- Navigation: CORE_ASSETS, FS_VISUAL, A09, U07, CORE_VIDEO.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_r2_media_api.py`](tests/test_r2_media_api.py), [`frontend/src/novel/ImageGenerationPanel.test.tsx`](frontend/src/novel/ImageGenerationPanel.test.tsx), [`frontend/src/novel/ImageQueuePanel.test.tsx`](frontend/src/novel/ImageQueuePanel.test.tsx), [`frontend/src/novel/ImageInfiniteCanvas.test.tsx`](frontend/src/novel/ImageInfiniteCanvas.test.tsx), [`frontend/src/novel/ImageTaskInspector.test.tsx`](frontend/src/novel/ImageTaskInspector.test.tsx), [`frontend/src/experimental/MediaPanel.recovery.test.tsx`](frontend/src/experimental/MediaPanel.recovery.test.tsx). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: EXTERNAL_REAL_MODELS, FINAL_SOURCE_CI.

#### CORE_SCREENPLAY · Screenplay / Scene / Shot authoring

- Page/subpage: Production → Screenplay / Scene / Shot authoring. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / existing Screenplay / Scene / Shot authoring.
- Components: [`frontend/src/novel/ScreenplayPanel.tsx`](frontend/src/novel/ScreenplayPanel.tsx), [`frontend/src/novel/MultimodalDirectorWorkspace.tsx`](frontend/src/novel/MultimodalDirectorWorkspace.tsx), [`frontend/src/novel/BindingManifestPanel.tsx`](frontend/src/novel/BindingManifestPanel.tsx)
- Authority/model/store/API source: [`app/services/screenplay_service.py`](app/services/screenplay_service.py), [`app/repositories/screenplay_versions.py`](app/repositories/screenplay_versions.py), [`app/api.py`](app/api.py)
- Behavior: Original branch-bound screenplay source, approval revision and independent edit_version CAS. Scene/shot/storyboard/transition changes preserve current source and immutable history.
- Version/conflict/cancel/recovery/restart: Explicit restore creates a new draft and re-review. Cancellation/navigation preserves unsaved intent; no automatic downstream image/video production.
- Scope/permissions: Original project/chapter/asset/job and collaboration scope where supported; unavailable branch paths must reject, never substitute mainline; Original route/middleware trusted session, owner/current membership and operation-specific domain permission; no client role authority. Profile: `ORIGINAL_AUTHORITY`; explicit legacy gaps take precedence over common defaults.
- Flags: Original core runtime/capability gates; no new blanket opt-in. Dependencies remain server-owned: {}.
- Navigation: A08, CORE_IMAGES, CORE_VIDEO.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_phase8_screenplay.py`](tests/test_phase8_screenplay.py), [`tests/test_screenplay_branch_revision.py`](tests/test_screenplay_branch_revision.py), [`tests/test_screenplay_cas_history.py`](tests/test_screenplay_cas_history.py), [`tests/test_screenplay_cas_postgres.py`](tests/test_screenplay_cas_postgres.py), [`frontend/src/novel/ScreenplayPanel.test.tsx`](frontend/src/novel/ScreenplayPanel.test.tsx), [`frontend/src/novel/ScreenplayPanel.motion-binding.test.ts`](frontend/src/novel/ScreenplayPanel.motion-binding.test.ts). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### CORE_VIDEO · Video / Motion / Assembly / Post

- Page/subpage: Production → Video / Motion / Assembly / Post. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / existing Video / Motion / Assembly / Post.
- Components: [`frontend/src/novel/MotionTaskWorkspace.tsx`](frontend/src/novel/MotionTaskWorkspace.tsx), [`frontend/src/novel/MotionPrivacyPanel.tsx`](frontend/src/novel/MotionPrivacyPanel.tsx), [`frontend/src/novel/VideoAssemblyPanel.tsx`](frontend/src/novel/VideoAssemblyPanel.tsx), [`frontend/src/novel/VideoTaskInspector.tsx`](frontend/src/novel/VideoTaskInspector.tsx), [`frontend/src/novel/MotionTaskBatchControls.tsx`](frontend/src/novel/MotionTaskBatchControls.tsx)
- Authority/model/store/API source: [`app/services/video_assembly_service.py`](app/services/video_assembly_service.py), [`app/asset_providers.py`](app/asset_providers.py), [`app/media_frames.py`](app/media_frames.py), [`app/experimental/media.py`](app/experimental/media.py), [`app/api.py`](app/api.py), [`app/experimental/media_api.py`](app/experimental/media_api.py)
- Behavior: Original motion/video task and source frame assets own T2V/I2V/start-end/continuation; MiniMax H3/Wan/LTX/SeedVR2/RIFE are explicit adapter family schemas, not automatic runtime detection.
- Version/conflict/cancel/recovery/restart: No production GPU/model quality evidence. Unsupported operation remains ADAPTER_REQUIRED/NOT_CONFIGURED. Bounded silent review assembly is not audio mastering; cancel/recovery uses original attempts.
- Scope/permissions: Original project/chapter/asset/job and collaboration scope where supported; unavailable branch paths must reject, never substitute mainline; Original route/middleware trusted session, owner/current membership and operation-specific domain permission; no client role authority. Profile: `ORIGINAL_AUTHORITY`; explicit legacy gaps take precedence over common defaults.
- Flags: `media_adapter_registry`. Dependencies remain server-owned: {"media_adapter_registry": []}.
- Navigation: CORE_SCREENPLAY, A12, CORE_AUDIO, FS_PROCESSING.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_r2_media_api.py`](tests/test_r2_media_api.py), [`frontend/src/novel/MotionTaskWorkspace.test.tsx`](frontend/src/novel/MotionTaskWorkspace.test.tsx), [`frontend/src/novel/MotionPrivacyPanel.test.tsx`](frontend/src/novel/MotionPrivacyPanel.test.tsx), [`frontend/src/novel/VideoAssemblyPanel.test.tsx`](frontend/src/novel/VideoAssemblyPanel.test.tsx), [`frontend/src/novel/VideoTaskInspector.test.tsx`](frontend/src/novel/VideoTaskInspector.test.tsx), [`frontend/src/novel/MotionTaskBatchControls.test.ts`](frontend/src/novel/MotionTaskBatchControls.test.ts). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: EXTERNAL_REAL_MODELS, FINAL_SOURCE_CI.

#### CORE_AUDIO · Audio / TTS / BGM / Ambience / SFX

- Page/subpage: Production → Audio / TTS / BGM / Ambience / SFX. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / existing Audio / TTS / BGM / Ambience / SFX.
- Components: [`frontend/src/novel/AudioGenerationPanel.tsx`](frontend/src/novel/AudioGenerationPanel.tsx), [`frontend/src/novel/AudioTaskInspector.tsx`](frontend/src/novel/AudioTaskInspector.tsx), [`frontend/src/novel/SpeechSynthesisPanel.tsx`](frontend/src/novel/SpeechSynthesisPanel.tsx), [`frontend/src/novel/AudiobookManifestPanel.tsx`](frontend/src/novel/AudiobookManifestPanel.tsx)
- Authority/model/store/API source: [`app/services/audiobook_service.py`](app/services/audiobook_service.py), [`app/audio_production_store.py`](app/audio_production_store.py), [`app/audio_providers.py`](app/audio_providers.py), [`app/api.py`](app/api.py)
- Behavior: Original source-linked audio/TTS attempts and verified binary media. Character voice, emotion/dialogue attribution remain B03; sound design is original audio track input, never a second provider queue.
- Version/conflict/cancel/recovery/restart: Real voice/music/ambience quality NOT_RUN; original privacy/reference-voice permission required. Unknown or stale attempts are explicit; no automatic resynthesis after restart.
- Scope/permissions: Original project/chapter/asset/job and collaboration scope where supported; unavailable branch paths must reject, never substitute mainline; Original route/middleware trusted session, owner/current membership and operation-specific domain permission; no client role authority. Profile: `ORIGINAL_AUTHORITY`; explicit legacy gaps take precedence over common defaults.
- Flags: Original core runtime/capability gates; no new blanket opt-in. Dependencies remain server-owned: {}.
- Navigation: B03, B04, FS_PROCESSING, CORE_ASSETS.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_audio_providers.py`](tests/test_audio_providers.py), [`tests/test_r3_audiobook_preparation.py`](tests/test_r3_audiobook_preparation.py), [`frontend/src/novel/AudioGenerationPanel.test.tsx`](frontend/src/novel/AudioGenerationPanel.test.tsx), [`frontend/src/novel/AudioTaskInspector.test.tsx`](frontend/src/novel/AudioTaskInspector.test.tsx), [`frontend/src/novel/SpeechSynthesisPanel.test.tsx`](frontend/src/novel/SpeechSynthesisPanel.test.tsx), [`frontend/src/novel/AudiobookManifestPanel.test.tsx`](frontend/src/novel/AudiobookManifestPanel.test.tsx). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: EXTERNAL_REAL_MODELS, FINAL_SOURCE_CI.

#### CORE_EXPORT · Export / History / Snapshot preflight

- Page/subpage: Production → Export / History / Snapshot preflight. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / existing Export / History / Snapshot preflight.
- Components: [`frontend/src/novel/ExportPanel.tsx`](frontend/src/novel/ExportPanel.tsx)
- Authority/model/store/API source: [`app/services/export_job_service.py`](app/services/export_job_service.py), [`app/services/export_snapshot_authority.py`](app/services/export_snapshot_authority.py), [`app/manuscript_sources.py`](app/manuscript_sources.py), [`app/export_formats.py`](app/export_formats.py), [`app/industry_export_formats.py`](app/industry_export_formats.py), [`app/api.py`](app/api.py)
- Behavior: Original immutable snapshot job/history and captured resources own exports. Branch snapshots include exact owner/scope/version/document digest and never project datasets/outline. Historical branch-labelled artifacts without valid branch evidence require independent PROJECT access and are filtered before pagination; artifact bytes are not rewritten.
- Version/conflict/cancel/recovery/restart: Explicit cancel/retry/recovery uses original job; export download is not proof a target app accepted it. Cancel cannot recall already downloaded bytes; restart never exports current mutable source under an old job.
- Scope/permissions: Original project/chapter/asset/job and collaboration scope where supported; unavailable branch paths must reject, never substitute mainline; Original route/middleware trusted session, owner/current membership and operation-specific domain permission; no client role authority. Profile: `ORIGINAL_AUTHORITY`; explicit legacy gaps take precedence over common defaults.
- Flags: Original core runtime/capability gates; no new blanket opt-in. Dependencies remain server-owned: {}.
- Navigation: U11, U14, A12, FS_ENGINES, B05.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_export_jobs.py`](tests/test_export_jobs.py), [`frontend/src/novel/ExportPanel.recovery.test.tsx`](frontend/src/novel/ExportPanel.recovery.test.tsx), [`frontend/src/novel/ExportPanel.scope.test.tsx`](frontend/src/novel/ExportPanel.scope.test.tsx), [`frontend/src/novel/ExportPanel.test.tsx`](frontend/src/novel/ExportPanel.test.tsx). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### FS_PROCESSING · ASR / Forced alignment / Burn-in adapters

- Page/subpage: Production → ASR / Forced alignment / Burn-in adapters. Entry: **FORMAL_UI_SURFACE_CONTRACT**.
- Current host: Shared AppShell / NOVEL experimental workbench / ASR / Forced alignment / Burn-in adapters; adjacent existing component is an integration host, NOT proof new inspector controls are rendered.
- Components: [`frontend/src/experimental/SubtitleTimelinePanel.tsx`](frontend/src/experimental/SubtitleTimelinePanel.tsx)
- Authority/model/store/API source: [`app/experimental/subtitle_processing.py`](app/experimental/subtitle_processing.py), [`app/experimental/subtitle_timeline.py`](app/experimental/subtitle_timeline.py), [`app/experimental/subtitle_timeline_api.py`](app/experimental/subtitle_timeline_api.py)
- Behavior: SubtitleTimelineService owns exact caption/media/source digest, rational timing and private processing attempt with claim/epoch/version/history; no second task queue.
- Version/conflict/cancel/recovery/restart: Queue/execute/cancel/recover/resume/approve/reject/reviewed download. Atomic cue update only after review; original task/review projections. Real ASR/alignment model admission NOT_CONFIGURED; burn-in trusted adapter/real rendering NOT_RUN. Formal UI contract.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `subtitle_timeline_v2`. Dependencies remain server-owned: {"subtitle_timeline_v2": ["voice_direction_v2"]}.
- Navigation: B04, B03, CORE_VIDEO, FS_REVIEW, U07.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): Original owner contract; no separate server endpoint.. Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Formal contract: [`docs/delivery/functional-surface-freeze/MEDIA_ENGINE_SURFACES.md`](docs/delivery/functional-surface-freeze/MEDIA_ENGINE_SURFACES.md).
- Remaining boundaries: FORMAL_NEW_INSPECTORS, EXTERNAL_REAL_MODELS, FINAL_SOURCE_CI.

#### FS_ENGINES · Godot / Ren'Py export adapters

- Page/subpage: Production → Godot / Ren'Py export adapters. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Godot / Ren'Py export adapters.
- Components: [`frontend/src/experimental/InteractiveStoryPanel.tsx`](frontend/src/experimental/InteractiveStoryPanel.tsx)
- Authority/model/store/API source: [`app/experimental/interactive_story.py`](app/experimental/interactive_story.py), [`app/experimental/interactive_story_api.py`](app/experimental/interactive_story_api.py)
- Behavior: Shipped EngineExportAdapter validators/file exporters stay under original reviewed InteractiveStoryService bundle. Godot data schema and Ren'Py bounded text/menu subset retain source IDs and deterministic checksums.
- Version/conflict/cancel/recovery/restart: Source/current review and expected version before export-preview/export. Bounded synchronous export cancellation discards response; explicit regeneration on restart. No engine launch/install. Actual Godot/Ren'Py acceptance NOT_RUN.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `interactive_story_v2`. Dependencies remain server-owned: {"interactive_story_v2": ["advanced_planning_v2", "temporal_story_graph_v2"]}.
- Navigation: B07, CORE_EXPORT.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_r5_interactive_story.py`](tests/test_r5_interactive_story.py), [`tests/test_r5_interactive_story_mounted.py`](tests/test_r5_interactive_story_mounted.py), [`frontend/src/experimental/InteractiveStoryPanel.test.tsx`](frontend/src/experimental/InteractiveStoryPanel.test.tsx). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Formal contract: [`docs/delivery/functional-surface-freeze/MEDIA_ENGINE_SURFACES.md`](docs/delivery/functional-surface-freeze/MEDIA_ENGINE_SURFACES.md).
- Remaining boundaries: EXTERNAL_TARGETS, FINAL_SOURCE_CI.

### Assets

#### A09 · Asset lineage and derived relationships

- Page/subpage: Assets → Lineage / Provenance. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Lineage / Provenance.
- Components: [`frontend/src/experimental/ProductionLineagePanel.tsx`](frontend/src/experimental/ProductionLineagePanel.tsx), [`frontend/src/novel/AssetInspector.tsx`](frontend/src/novel/AssetInspector.tsx)
- Authority/model/store/API source: [`app/services/asset_library_service.py`](app/services/asset_library_service.py), [`app/experimental/production_lineage.py`](app/experimental/production_lineage.py), [`app/experimental/media.py`](app/experimental/media.py), [`frontend/src/experimental/ProductionLineagePanel.tsx`](frontend/src/experimental/ProductionLineagePanel.tsx), [`app/experimental/production_lineage_api.py`](app/experimental/production_lineage_api.py), [`app/experimental/media_api.py`](app/experimental/media_api.py)
- Behavior: Original AssetLibraryService/DAG retains observed model/provider/workflow/input/parent hashes and source Scene/Shot/version evidence.
- Version/conflict/cancel/recovery/restart: Inspect and explicit lineage/replay preflight; request cancellation leaves original asset intact. Restart rereads current asset authority; unknown historical provenance remains unknown.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `asset_lineage_v2`. Dependencies remain server-owned: {"asset_lineage_v2": []}.
- Navigation: CORE_ASSETS, A13, FS_VISUAL, U06, B06.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_post_interop_media_continuation.py`](tests/test_post_interop_media_continuation.py), [`tests/test_r4_production_lineage.py`](tests/test_r4_production_lineage.py), [`tests/test_post_interop_wave5_templates_sdk_comics.py`](tests/test_post_interop_wave5_templates_sdk_comics.py), [`frontend/src/experimental/ProductionLineagePanel.continuation.test.tsx`](frontend/src/experimental/ProductionLineagePanel.continuation.test.tsx), [`frontend/src/experimental/ProductionLineagePanel.test.tsx`](frontend/src/experimental/ProductionLineagePanel.test.tsx), [`frontend/src/novel/AssetInspector.test.tsx`](frontend/src/novel/AssetInspector.test.tsx). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### U14 · Portable project, relink and safe cleanup

- Page/subpage: Assets → Portable projects / Storage health / Relink. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Portable projects / Storage health / Relink.
- Components: [`frontend/src/experimental/PortableProjectsPanel.tsx`](frontend/src/experimental/PortableProjectsPanel.tsx)
- Authority/model/store/API source: [`app/experimental/portable_projects.py`](app/experimental/portable_projects.py), [`app/backup_restore.py`](app/backup_restore.py), [`app/services/asset_library_service.py`](app/services/asset_library_service.py), [`frontend/src/experimental/PortableProjectsPanel.tsx`](frontend/src/experimental/PortableProjectsPanel.tsx), [`app/experimental/portable_projects_api.py`](app/experimental/portable_projects_api.py)
- Behavior: Original backup/import/apply and AssetLibrary owners; scoped portable manifests and journals are orchestration, not second project or asset authority.
- Version/conflict/cancel/recovery/restart: Preflight missing/corrupt resources, relink exact hashes, explicit repair/recover, CAS/current-reference checks and restart journals. Selected bundles are not complete Canon/history backups.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `portable_projects_v2`. Dependencies remain server-owned: {"portable_projects_v2": []}.
- Navigation: CORE_ASSETS, FS_IMPORT, CORE_EXPORT, B10.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_r4_portable_batches.py`](tests/test_r4_portable_batches.py), [`tests/test_r4_production_mounted.py`](tests/test_r4_production_mounted.py), [`frontend/src/experimental/PortableProjectsPanel.maintenance.test.tsx`](frontend/src/experimental/PortableProjectsPanel.maintenance.test.tsx), [`frontend/src/experimental/PortableProjectsPanel.test.tsx`](frontend/src/experimental/PortableProjectsPanel.test.tsx). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### CORE_ASSETS · Asset library / References / Integrity

- Page/subpage: Assets → Asset library / References / Integrity. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / existing Asset library / References / Integrity.
- Components: [`frontend/src/novel/AssetLibraryPanel.tsx`](frontend/src/novel/AssetLibraryPanel.tsx), [`frontend/src/novel/AssetInspector.tsx`](frontend/src/novel/AssetInspector.tsx), [`frontend/src/novel/VisualReferencePanel.tsx`](frontend/src/novel/VisualReferencePanel.tsx), [`frontend/src/novel/AuthenticatedMedia.tsx`](frontend/src/novel/AuthenticatedMedia.tsx), [`frontend/src/novel/EntityAssetPanel.tsx`](frontend/src/novel/EntityAssetPanel.tsx), [`frontend/src/ui/AssetWorkspaceRoute.tsx`](frontend/src/ui/AssetWorkspaceRoute.tsx)
- Authority/model/store/API source: [`app/services/asset_library_service.py`](app/services/asset_library_service.py), [`app/asset_lifecycle_api.py`](app/asset_lifecycle_api.py), [`app/media_files.py`](app/media_files.py), [`app/services/v1_capability_service.py`](app/services/v1_capability_service.py), [`app/api.py`](app/api.py)
- Behavior: Unique original AssetLibrary owner, authenticated media bytes, asset version/SHA-256, provenance, approval and recoverable lifecycle. Appearance profiles reuse original visual-memory records.
- Version/conflict/cancel/recovery/restart: Asset relink/repair goes through U14 current manifest and exact hashes; missing bytes are not approved from metadata. Original provider result/review states remain distinct.
- Scope/permissions: Original project/chapter/asset/job and collaboration scope where supported; unavailable branch paths must reject, never substitute mainline; Original route/middleware trusted session, owner/current membership and operation-specific domain permission; no client role authority. Profile: `ORIGINAL_AUTHORITY`; explicit legacy gaps take precedence over common defaults.
- Flags: Original core runtime/capability gates; no new blanket opt-in. Dependencies remain server-owned: {}.
- Navigation: U14, A09, FS_VISUAL, CORE_IMAGES, CORE_VIDEO.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_asset_library.py`](tests/test_asset_library.py), [`frontend/src/novel/AssetLibraryPanel.test.tsx`](frontend/src/novel/AssetLibraryPanel.test.tsx), [`frontend/src/novel/AssetInspector.test.tsx`](frontend/src/novel/AssetInspector.test.tsx), [`frontend/src/novel/VisualReferencePanel.test.tsx`](frontend/src/novel/VisualReferencePanel.test.tsx). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### FS_VISUAL · Visual Identity / Similarity / Drift

- Page/subpage: Assets → Visual Identity / Similarity / Drift. Entry: **FORMAL_UI_SURFACE_CONTRACT**.
- Current host: Shared AppShell / existing Visual Identity / Similarity / Drift; adjacent existing component is an integration host, NOT proof new inspector controls are rendered.
- Components: [`frontend/src/novel/VisualReferencePanel.tsx`](frontend/src/novel/VisualReferencePanel.tsx), [`frontend/src/novel/VisualContextPanel.tsx`](frontend/src/novel/VisualContextPanel.tsx)
- Authority/model/store/API source: [`app/experimental/visual_identity.py`](app/experimental/visual_identity.py), [`app/experimental/embeddings.py`](app/experimental/embeddings.py), [`app/experimental/review_adapter_jobs.py`](app/experimental/review_adapter_jobs.py), [`app/experimental/review_adapter_projection.py`](app/experimental/review_adapter_projection.py), [`app/services/v1_capability_service.py`](app/services/v1_capability_service.py), [`app/experimental/embeddings_api.py`](app/experimental/embeddings_api.py), [`app/api.py`](app/api.py)
- Behavior: Appearance profile projects original approved CHARACTER visual-memory reference, appearance_version, clothing/hair/body/accessories and asset digest. Comparison adds only review receipt, never another profile store.
- Version/conflict/cancel/recovery/restart: Pinned candidate plus approved current references, target IMAGE/VIDEO and explicit threshold require review before selection. Bounded receipt admission reserves terminal/recovery/invalidation capacity; restart never replays, cancel/recover fence tokens, source-revoked responses omit old request/lineage/results. Task/Review are original-owner read-through projections; creator/read visibility and write+CAS cancellation remain distinct. FORMAL_SOURCE_ONLY target, no rendered exact-open control. Real image embedding NOT_CONFIGURED/NOT_RUN.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; domain.read plus receipt creator and approved current reference/asset visibility; Current domain.write and original receipt CAS/state/capacity through original owner; recheck before and after original-owner reads. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `visual_embeddings`. Dependencies remain server-owned: {"visual_embeddings": []}.
- Navigation: CORE_ASSETS, CORE_IMAGES, CORE_VIDEO, B06, FS_SEMANTIC, U07, FS_REVIEW.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`frontend/src/novel/VisualReferencePanel.test.tsx`](frontend/src/novel/VisualReferencePanel.test.tsx), [`frontend/src/novel/VisualContextPanel.test.tsx`](frontend/src/novel/VisualContextPanel.test.tsx), [`tests/test_surface_adapter_capacity.py`](tests/test_surface_adapter_capacity.py), [`tests/test_surface_adapter_projection.py`](tests/test_surface_adapter_projection.py), [`frontend/src/experimental/AdapterReceiptProjection.test.tsx`](frontend/src/experimental/AdapterReceiptProjection.test.tsx). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Operation permission boundaries: {"read": "domain.read plus receipt creator and approved current reference/asset visibility", "cancel": "Current domain.write and original receipt CAS/state/capacity through original owner", "generic_review": "No approve or batch approve; original inspector remains FORMAL_SOURCE_ONLY without rendered exact-open control"}.
- Receipt capacity/recovery contract: {"owner": "Existing ReviewAdapterJobs metadata of the original Research/Embedding service", "history_entries": 100, "receipt_bytes": 8388608, "current_snapshot_bytes": 786432, "result_bytes": 524288, "run_free_revision_slots_required": 6, "capacity_behavior": "Reserve claim/terminal/review/cancel/recover/source-invalidation tail before dispatch; no eviction/truncation. Explicit new receipt required after finite admission exhausted.", "terminal_behavior": "Repeated same-state cancel/invalidate is an idempotent no-op; source replacement/revocation uses bounded invalidation.", "revoked_payload_behavior": "Cancel/invalidate/stale responses withhold request/source snapshot/model/result digest; conflict only exposes ID/version/status. Projections contain receipt identity/version/status, no source lineage or result.", "restart_behavior": "RUNNING reports recovery required; explicit recover/cancel fences token; no automatic replay or durable-worker claim"}.
- Source-bound focused owner receipts (not final-head acceptance): [`docs/SURFACE_ADAPTER_RECOVERY_COMPLETION.md`](docs/SURFACE_ADAPTER_RECOVERY_COMPLETION.md).
- Formal contract: [`contracts/functional-surfaces/search-visual-research.v1.json`](contracts/functional-surfaces/search-visual-research.v1.json), [`docs/SURFACE_ADAPTER_RECOVERY_COMPLETION.md`](docs/SURFACE_ADAPTER_RECOVERY_COMPLETION.md).
- Remaining boundaries: FORMAL_NEW_INSPECTORS, EXTERNAL_REAL_MODELS, FINAL_SOURCE_CI.

### Collaboration

#### B08 · Writer room and team review

- Page/subpage: Collaboration → Writer Room / Assignments / Comments. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Writer Room / Assignments / Comments.
- Components: [`frontend/src/experimental/WriterRoomPanel.tsx`](frontend/src/experimental/WriterRoomPanel.tsx), [`frontend/src/CollaborationPanels.tsx`](frontend/src/CollaborationPanels.tsx)
- Authority/model/store/API source: [`app/experimental/writer_room.py`](app/experimental/writer_room.py), [`app/services/creation_workbench_service.py`](app/services/creation_workbench_service.py), [`app/experimental/inbox.py`](app/experimental/inbox.py), [`frontend/src/experimental/WriterRoomPanel.tsx`](frontend/src/experimental/WriterRoomPanel.tsx), [`app/experimental/writer_room_api.py`](app/experimental/writer_room_api.py)
- Behavior: Original comments, revision assignments and review target identities; finishing an assignment does not approve or apply that target.
- Version/conflict/cancel/recovery/restart: CAS/edit/status/review/reopen; retained task and comment history, source-anchor stale state; async room snapshots are not realtime coediting.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `writer_room_v2`. Dependencies remain server-owned: {"writer_room_v2": ["unified_review_inbox"]}.
- Navigation: FS_REALTIME, FS_BRANCH, FS_REVIEW, A03, U07.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_r5_writer_room_mounted.py`](tests/test_r5_writer_room_mounted.py), [`tests/test_post_interop_extended_mounted.py`](tests/test_post_interop_extended_mounted.py), [`frontend/src/experimental/WriterRoomPanel.test.tsx`](frontend/src/experimental/WriterRoomPanel.test.tsx), [`tests/test_writer_room_comment_authority_seam.py`](tests/test_writer_room_comment_authority_seam.py). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### B09 · Project fork and merge

- Page/subpage: Collaboration → Project Fork / Human Merge / Shared Universe. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Project Fork / Human Merge / Shared Universe.
- Components: [`frontend/src/experimental/ProjectForksPanel.tsx`](frontend/src/experimental/ProjectForksPanel.tsx), [`frontend/src/experimental/StructuredForksPanel.tsx`](frontend/src/experimental/StructuredForksPanel.tsx), [`frontend/src/experimental/SharedUniversePanel.tsx`](frontend/src/experimental/SharedUniversePanel.tsx)
- Authority/model/store/API source: [`app/experimental/project_forks.py`](app/experimental/project_forks.py), [`app/experimental/structured_forks.py`](app/experimental/structured_forks.py), [`app/experimental/world.py`](app/experimental/world.py), [`frontend/src/experimental/ProjectForksPanel.tsx`](frontend/src/experimental/ProjectForksPanel.tsx), [`frontend/src/experimental/SharedUniversePanel.tsx`](frontend/src/experimental/SharedUniversePanel.tsx), [`app/experimental/project_forks_api.py`](app/experimental/project_forks_api.py)
- Behavior: Original selected project/structured source snapshots, target CAS and explicit per-work universe pins; immutable snapshots never become another Canon owner.
- Version/conflict/cancel/recovery/restart: Fork/compare/conflict/human merge, source/target authorization/deletion/privacy checks, history/release and explicit recovery. No auto-repin or implicit model-context injection.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `project_forks_v2`. Dependencies remain server-owned: {"project_forks_v2": ["revision_intelligence_v2", "asset_lineage_v2"]}.
- Navigation: FS_BRANCH, FS_UNIVERSE, CORE_MANUSCRIPT, FS_CANON, B10.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_post_interop_shared_universe.py`](tests/test_post_interop_shared_universe.py), [`tests/test_r5_project_forks.py`](tests/test_r5_project_forks.py), [`tests/test_r5_structured_forks.py`](tests/test_r5_structured_forks.py), [`frontend/src/experimental/SharedUniversePanel.test.tsx`](frontend/src/experimental/SharedUniversePanel.test.tsx), [`frontend/src/experimental/ProjectForksPanel.test.tsx`](frontend/src/experimental/ProjectForksPanel.test.tsx), [`frontend/src/experimental/StructuredForksPanel.test.tsx`](frontend/src/experimental/StructuredForksPanel.test.tsx). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### B10 · Offline synchronization foundation

- Page/subpage: Collaboration → Offline exchange / Reconciliation. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Offline exchange / Reconciliation.
- Components: [`frontend/src/experimental/OfflineSyncPanel.tsx`](frontend/src/experimental/OfflineSyncPanel.tsx)
- Authority/model/store/API source: [`app/experimental/offline_sync.py`](app/experimental/offline_sync.py), [`app/experimental/portable_projects.py`](app/experimental/portable_projects.py), [`frontend/src/experimental/OfflineSyncPanel.tsx`](frontend/src/experimental/OfflineSyncPanel.tsx), [`app/experimental/offline_sync_api.py`](app/experimental/offline_sync_api.py)
- Behavior: Original selected-source outbox/inbox/channel and diff3 review; manual local exchange is not production cloud or a second manuscript system.
- Version/conflict/cancel/recovery/restart: CAS/checkpoint/import/review/cancel/recover with ambiguous outcome reconciliation; restart keeps journal and requires explicit action.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `offline_sync_v2`. Dependencies remain server-owned: {"offline_sync_v2": ["project_forks_v2"]}.
- Navigation: FS_SYNC, B09, U14, FS_REVIEW.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_r5_offline_sync.py`](tests/test_r5_offline_sync.py), [`tests/test_r5_offline_sync_mounted.py`](tests/test_r5_offline_sync_mounted.py), [`frontend/src/experimental/OfflineSyncPanel.test.tsx`](frontend/src/experimental/OfflineSyncPanel.test.tsx), [`tests/test_r5_offline_sync_tcp.py`](tests/test_r5_offline_sync_tcp.py). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### CORE_COLLAB · Workspace / Membership / Permissions

- Page/subpage: Collaboration → Workspace / Membership / Permissions. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / existing Workspace / Membership / Permissions.
- Components: [`frontend/src/WorkspaceManagement.tsx`](frontend/src/WorkspaceManagement.tsx), [`frontend/src/PermissionManagement.tsx`](frontend/src/PermissionManagement.tsx), [`frontend/src/CollaborationPanels.tsx`](frontend/src/CollaborationPanels.tsx)
- Authority/model/store/API source: [`app/services/collaboration_scope_service.py`](app/services/collaboration_scope_service.py), [`app/services/authorization_service.py`](app/services/authorization_service.py), [`app/collaboration_admin.py`](app/collaboration_admin.py), [`app/application/collaboration_service.py`](app/application/collaboration_service.py), [`app/collaboration_api.py`](app/collaboration_api.py), [`app/api.py`](app/api.py)
- Behavior: Trusted session/current membership and workspace/project/storyline/branch scope remain authority; roles or hidden controls in browser are never grants. Original audit and revision-CAS boundaries retained.
- Version/conflict/cancel/recovery/restart: Missing branch document is unavailable, never mainline fallback. Revocation ends current access; reconnect reauthorizes. Administrative operations preserve their original confirmations/recovery semantics.
- Scope/permissions: Original project/chapter/asset/job and collaboration scope where supported; unavailable branch paths must reject, never substitute mainline; Original route/middleware trusted session, owner/current membership and operation-specific domain permission; no client role authority. Profile: `ORIGINAL_AUTHORITY`; explicit legacy gaps take precedence over common defaults.
- Flags: `ENABLE_COLLABORATION_RUNTIME`. Dependencies remain server-owned: {"ENABLE_COLLABORATION_RUNTIME": []}.
- Navigation: FS_BRANCH, FS_REALTIME, B08, FS_SYNC.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_authorization_foundation.py`](tests/test_authorization_foundation.py), [`tests/test_collaboration_application_service_v056.py`](tests/test_collaboration_application_service_v056.py), [`tests/test_collaboration_http_boundary_v056.py`](tests/test_collaboration_http_boundary_v056.py), [`tests/test_collaboration_scope.py`](tests/test_collaboration_scope.py), [`tests/test_collaboration_scope_api.py`](tests/test_collaboration_scope_api.py), [`tests/test_collaboration_text_models_route.py`](tests/test_collaboration_text_models_route.py). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### FS_REALTIME · Realtime protocol / Presence / Co-edit inspector

- Page/subpage: Collaboration → Realtime protocol / Presence / Co-edit inspector. Entry: **FORMAL_UI_SURFACE_CONTRACT**.
- Current host: Shared AppShell / NOVEL experimental workbench / Realtime protocol / Presence / Co-edit inspector; adjacent existing component is an integration host, NOT proof new inspector controls are rendered.
- Components: [`frontend/src/experimental/WriterRoomPanel.tsx`](frontend/src/experimental/WriterRoomPanel.tsx)
- Authority/model/store/API source: [`app/experimental/writer_room_realtime.py`](app/experimental/writer_room_realtime.py), [`app/experimental/writer_room.py`](app/experimental/writer_room.py), [`app/experimental/writer_room_api.py`](app/experimental/writer_room_api.py)
- Behavior: WriterRoomService.realtime participant lease/session, cursor-selection/document-version and strict-CAS edit operation. Actual synthetic callback push is distinct from snapshot HTTP list.
- Version/conflict/cancel/recovery/restart: Join/heartbeat/disconnect/reconnect/leave/revoke/prepare/apply/cancel/inspect-recovery/adopt/close-without-replay. Restart disconnects leases. Production transport NOT_CONFIGURED; no OT/CRDT or deployed coediting claim.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `realtime_collaboration_v1`. Dependencies remain server-owned: {"realtime_collaboration_v1": ["writer_room_v2", "branch_manuscript_v1"]}.
- Navigation: B08, FS_BRANCH, CORE_MANUSCRIPT.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_r5_writer_room_mounted.py`](tests/test_r5_writer_room_mounted.py), [`tests/test_writer_room_comment_authority_seam.py`](tests/test_writer_room_comment_authority_seam.py), [`frontend/src/experimental/WriterRoomPanel.test.tsx`](frontend/src/experimental/WriterRoomPanel.test.tsx). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Formal contract: [`contracts/functional-surfaces/realtime-sync.v1.json`](contracts/functional-surfaces/realtime-sync.v1.json), [`contracts/functional-surfaces/realtime-sync-models.v1.json`](contracts/functional-surfaces/realtime-sync-models.v1.json).
- Remaining boundaries: FORMAL_NEW_INSPECTORS, EXTERNAL_PRODUCTION_TRANSPORT, FINAL_SOURCE_CI.

#### FS_SYNC · Production sync / Manifest / Device / Checkpoint

- Page/subpage: Collaboration → Production sync / Manifest / Device / Checkpoint. Entry: **FORMAL_UI_SURFACE_CONTRACT**.
- Current host: Shared AppShell / NOVEL experimental workbench / Production sync / Manifest / Device / Checkpoint; adjacent existing component is an integration host, NOT proof new inspector controls are rendered.
- Components: [`frontend/src/experimental/OfflineSyncPanel.tsx`](frontend/src/experimental/OfflineSyncPanel.tsx)
- Authority/model/store/API source: [`app/experimental/offline_sync_production.py`](app/experimental/offline_sync_production.py), [`app/experimental/offline_sync.py`](app/experimental/offline_sync.py), [`app/experimental/offline_sync_api.py`](app/experimental/offline_sync_api.py)
- Behavior: Original OfflineSync outbox/inbox plus device epoch, manifest/change-set/rich delta/object metadata/transfer checkpoints. Only local/synthetic transport/encryption seam; no production cloud claims.
- Version/conflict/cancel/recovery/restart: Register/revoke/seal/prepare/dispatch/cancel/resume and original diff3 review. Explicit copy boundary, current permission/source/device checks. Branch sync NOT_CONFIGURED and denied instead of mainline fallback. Formal inspector contract.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `production_sync_v1`. Dependencies remain server-owned: {"production_sync_v1": ["offline_sync_v2"]}.
- Navigation: B10, U14, FS_REVIEW.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_r5_offline_sync.py`](tests/test_r5_offline_sync.py), [`tests/test_r5_offline_sync_mounted.py`](tests/test_r5_offline_sync_mounted.py), [`tests/test_r5_offline_sync_tcp.py`](tests/test_r5_offline_sync_tcp.py), [`frontend/src/experimental/OfflineSyncPanel.test.tsx`](frontend/src/experimental/OfflineSyncPanel.test.tsx). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Formal contract: [`contracts/functional-surfaces/realtime-sync.v1.json`](contracts/functional-surfaces/realtime-sync.v1.json), [`contracts/functional-surfaces/realtime-sync-models.v1.json`](contracts/functional-surfaces/realtime-sync-models.v1.json).
- Remaining boundaries: FORMAL_NEW_INSPECTORS, EXTERNAL_PRODUCTION_TRANSPORT, FINAL_SOURCE_CI.

### Models

#### U09 · Local AI diagnostic and setup guidance

- Page/subpage: Models → Local AI diagnostics / Workflow inspection. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Local AI diagnostics / Workflow inspection.
- Components: [`frontend/src/ui/LocalAiDiscovery.tsx`](frontend/src/ui/LocalAiDiscovery.tsx), [`frontend/src/experimental/WorkflowInspectionPanel.tsx`](frontend/src/experimental/WorkflowInspectionPanel.tsx), [`frontend/src/novel/RuntimeDiagnostics.tsx`](frontend/src/novel/RuntimeDiagnostics.tsx)
- Authority/model/store/API source: [`app/model_center/discovery.py`](app/model_center/discovery.py), [`app/model_center/discovery_probes.py`](app/model_center/discovery_probes.py), [`app/experimental/local_ai_inspection.py`](app/experimental/local_ai_inspection.py), [`frontend/src/ui/LocalAiDiscovery.tsx`](frontend/src/ui/LocalAiDiscovery.tsx), [`frontend/src/experimental/WorkflowInspectionPanel.tsx`](frontend/src/experimental/WorkflowInspectionPanel.tsx), [`app/experimental/local_ai_inspection_api.py`](app/experimental/local_ai_inspection_api.py), [`app/model_center/discovery_api.py`](app/model_center/discovery_api.py)
- Behavior: Original Model Center detect, validate, register, explicit enable and launch boundaries; passive Comfy workflow inspection does not execute imported code.
- Version/conflict/cancel/recovery/restart: Abort/late-result fences, explicit retry and redacted diagnostic export. Restart rereads configured local runtime; missing hardware, node, model, license and adapter remain explicit.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `local_ai_workflow_inspector_v2`. Dependencies remain server-owned: {"local_ai_workflow_inspector_v2": []}.
- Navigation: CORE_MODELS, A06, A07, U12, FS_SDK.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`frontend/src/ui/LocalAiDiscovery.test.tsx`](frontend/src/ui/LocalAiDiscovery.test.tsx), [`tests/test_local_ai_discovery.py`](tests/test_local_ai_discovery.py), [`tests/test_local_ai_discovery_egress.py`](tests/test_local_ai_discovery_egress.py), [`frontend/src/experimental/WorkflowInspectionPanel.test.tsx`](frontend/src/experimental/WorkflowInspectionPanel.test.tsx), [`frontend/src/novel/RuntimeDiagnostics.test.tsx`](frontend/src/novel/RuntimeDiagnostics.test.tsx), [`tests/test_r4_local_ai_inspection.py`](tests/test_r4_local_ai_inspection.py). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### A06 · Explainable model broker

- Page/subpage: Models → Model routing / Preflight / Cost preview. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Model routing / Preflight / Cost preview.
- Components: [`frontend/src/experimental/ModelBrokerPanel.tsx`](frontend/src/experimental/ModelBrokerPanel.tsx)
- Authority/model/store/API source: [`app/experimental/model_broker.py`](app/experimental/model_broker.py), [`app/experimental/model_broker_api.py`](app/experimental/model_broker_api.py), [`app/experimental/provider_profiles.py`](app/experimental/provider_profiles.py), [`app/model_center/service.py`](app/model_center/service.py), [`frontend/src/experimental/ModelBrokerPanel.tsx`](frontend/src/experimental/ModelBrokerPanel.tsx)
- Behavior: Original route, model identity, policy, budget/admission and explicit fallback approval own dispatch; unknown cost and quality are not inferred.
- Version/conflict/cancel/recovery/restart: Version/source/route preview digest; cancel and original job recovery; never retry an ambiguous paid attempt automatically. Restart requires current route and reviewed preflight.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `model_broker_v2`. Dependencies remain server-owned: {"model_broker_v2": ["author_context_inspector_v2"]}.
- Navigation: CORE_MODELS, A07, U08, U16, CORE_GENERATION.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_post_interop_wave3_broker.py`](tests/test_post_interop_wave3_broker.py), [`tests/test_r4_broker_cancel_dispatch.py`](tests/test_r4_broker_cancel_dispatch.py), [`frontend/src/experimental/ModelBrokerPanel.test.tsx`](frontend/src/experimental/ModelBrokerPanel.test.tsx), [`tests/test_r4_model_broker.py`](tests/test_r4_model_broker.py). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### A07 · Model benchmark and capability evidence

- Page/subpage: Models → Benchmarks / Capability evidence. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Benchmarks / Capability evidence.
- Components: [`frontend/src/experimental/ModelBenchmarkPanel.tsx`](frontend/src/experimental/ModelBenchmarkPanel.tsx)
- Authority/model/store/API source: [`app/experimental/model_benchmark.py`](app/experimental/model_benchmark.py), [`app/experimental/model_benchmark_api.py`](app/experimental/model_benchmark_api.py), [`app/model_center/discovery.py`](app/model_center/discovery.py), [`frontend/src/experimental/ModelBenchmarkPanel.tsx`](frontend/src/experimental/ModelBenchmarkPanel.tsx)
- Behavior: Catalog claims, detection, contract fixtures, measured benchmark records and human output review are separate evidence types tied to exact runtime/model/output identities.
- Version/conflict/cancel/recovery/restart: Explicit run/cancel/review with retained records; missing GPU/model configuration stays unavailable. Restart reads receipts, never manufactures throughput, VRAM or quality.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `model_benchmark_v2`. Dependencies remain server-owned: {"model_benchmark_v2": ["model_broker_v2"]}.
- Navigation: CORE_MODELS, A06, U09.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_post_interop_wave3_broker.py`](tests/test_post_interop_wave3_broker.py), [`frontend/src/experimental/ModelBenchmarkPanel.continuation.test.tsx`](frontend/src/experimental/ModelBenchmarkPanel.continuation.test.tsx). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: EXTERNAL_REAL_MODELS, FINAL_SOURCE_CI.

#### CORE_MODELS · Model Center / Provider configuration

- Page/subpage: Models → Model Center / Provider configuration. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / existing Model Center / Provider configuration.
- Components: [`frontend/src/ui/ModelCenter.tsx`](frontend/src/ui/ModelCenter.tsx), [`frontend/src/ui/AiControlCenter.tsx`](frontend/src/ui/AiControlCenter.tsx), [`frontend/src/ui/MediaProviderSettings.tsx`](frontend/src/ui/MediaProviderSettings.tsx), [`frontend/src/novel/DeepSeekCredentialControl.tsx`](frontend/src/novel/DeepSeekCredentialControl.tsx)
- Authority/model/store/API source: [`app/model_center/service.py`](app/model_center/service.py), [`app/model_center/domain.py`](app/model_center/domain.py), [`app/model_center/discovery.py`](app/model_center/discovery.py), [`app/model_center/runtime_profiles.py`](app/model_center/runtime_profiles.py), [`app/credential_vault.py`](app/credential_vault.py), [`app/model_center/api.py`](app/model_center/api.py), [`app/model_center/discovery_api.py`](app/model_center/discovery_api.py)
- Behavior: Original Model Center registration/selection, runtime/profile identity and host/OS credential vault. Detect, validate, register, enable, launch and configured capability remain separate actions.
- Version/conflict/cancel/recovery/restart: Runtime/GPU/license/provider quality requires LOCAL_REQUIRED/NOT_RUN evidence. UI must not store secrets or auto-install/unlock unsupported model families.
- Scope/permissions: Original project/chapter/asset/job and collaboration scope where supported; unavailable branch paths must reject, never substitute mainline; Original route/middleware trusted session, owner/current membership and operation-specific domain permission; no client role authority. Profile: `ORIGINAL_AUTHORITY`; explicit legacy gaps take precedence over common defaults.
- Flags: Original core runtime/capability gates; no new blanket opt-in. Dependencies remain server-owned: {}.
- Navigation: U09, A06, A07, FS_SEMANTIC.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_collaboration_application_service_v056.py`](tests/test_collaboration_application_service_v056.py), [`tests/test_continuity_service.py`](tests/test_continuity_service.py), [`tests/test_credential_vault.py`](tests/test_credential_vault.py), [`tests/test_harness_process_service.py`](tests/test_harness_process_service.py), [`tests/test_local_ai_discovery.py`](tests/test_local_ai_discovery.py), [`tests/test_local_ai_discovery_adversarial.py`](tests/test_local_ai_discovery_adversarial.py). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

### Tasks

#### U07 · Unified task center and honest progress

- Page/subpage: Tasks → Unified task center. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Unified task center.
- Components: [`frontend/src/experimental/WorkspaceToolsPanel.tsx`](frontend/src/experimental/WorkspaceToolsPanel.tsx), [`frontend/src/experimental/ExperimentalWorkbench.tsx`](frontend/src/experimental/ExperimentalWorkbench.tsx)
- Authority/model/store/API source: [`app/experimental/ux.py`](app/experimental/ux.py), [`app/experimental/author_task_projection.py`](app/experimental/author_task_projection.py), [`app/experimental/workspace_task_owners.py`](app/experimental/workspace_task_owners.py), [`frontend/src/experimental/WorkspaceToolsPanel.tsx`](frontend/src/experimental/WorkspaceToolsPanel.tsx), [`frontend/src/experimental/ExperimentalWorkbench.tsx`](frontend/src/experimental/ExperimentalWorkbench.tsx), [`app/experimental/adaptation_projection.py`](app/experimental/adaptation_projection.py), [`app/experimental/review_adapter_projection.py`](app/experimental/review_adapter_projection.py), [`app/experimental/ux_api.py`](app/experimental/ux_api.py), [`frontend/src/experimental/uxClient.ts`](frontend/src/experimental/uxClient.ts)
- Behavior: Read-through TaskReader projection retains original authority and task IDs. Cancel/retry/review are routed to the original owner, never another queue.
- Version/conflict/cancel/recovery/restart: Owner-specific cancel states and version/revision guard; cancelled lookups do not cancel jobs. Retry/resume requires original preflight/consent, unknown attempts are reconciled rather than replayed. Restart rereads owners.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `workspace_tools_v2`. Dependencies remain server-owned: {"workspace_tools_v2": []}.
- Navigation: CORE_GENERATION, FS_REVIEW, A01, A02, A03, A11, FS_BRANCH, FS_PROCESSING, CORE_ADAPTATION, FS_RESEARCH_VISION, FS_VISUAL.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_post_interop_workspace_ux.py`](tests/test_post_interop_workspace_ux.py), [`tests/test_post_interop_creation_tasks.py`](tests/test_post_interop_creation_tasks.py), [`frontend/src/experimental/TaskOwnerNavigation.continuation.test.tsx`](frontend/src/experimental/TaskOwnerNavigation.continuation.test.tsx), [`tests/test_post_interop_task_reopen.py`](tests/test_post_interop_task_reopen.py), [`frontend/src/experimental/ModelTaskReopen.test.tsx`](frontend/src/experimental/ModelTaskReopen.test.tsx), [`frontend/tests/e2e/r4-model-task-reopen.spec.ts`](frontend/tests/e2e/r4-model-task-reopen.spec.ts). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### U16 · Safe batch preflight

- Page/subpage: Tasks → Safe batch / Cost preflight. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Safe batch / Cost preflight.
- Components: [`frontend/src/experimental/SafeBatchesPanel.tsx`](frontend/src/experimental/SafeBatchesPanel.tsx)
- Authority/model/store/API source: [`app/experimental/safe_batches.py`](app/experimental/safe_batches.py), [`app/experimental/safe_batch_contracts.py`](app/experimental/safe_batch_contracts.py), [`frontend/src/experimental/SafeBatchesPanel.tsx`](frontend/src/experimental/SafeBatchesPanel.tsx), [`app/experimental/safe_batch_voice.py`](app/experimental/safe_batch_voice.py), [`app/experimental/safe_batches_api.py`](app/experimental/safe_batches_api.py)
- Behavior: Original owner-specific admission, source/config/budget/approval/settlement constraints; finite supported batch kinds only.
- Version/conflict/cancel/recovery/restart: Prepare/execute/cancel with per-item identity and receipts; explicit retry from original owner, no silent replay or route upgrades. Unknown paid cost holds execution.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `safe_batches_v2`. Dependencies remain server-owned: {"safe_batches_v2": ["reader_preflight_v2"]}.
- Navigation: A06, U07, CORE_IMAGES, B03, U11.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_r4_batch_admission.py`](tests/test_r4_batch_admission.py), [`tests/test_r4_portable_batches.py`](tests/test_r4_portable_batches.py), [`frontend/src/experimental/SafeBatchesPanel.test.tsx`](frontend/src/experimental/SafeBatchesPanel.test.tsx). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### B02 · Custom agents and workflow SDK

- Page/subpage: Tasks → Agent SDK / Workflow SDK. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Agent SDK / Workflow SDK.
- Components: [`frontend/src/experimental/DeclarativeAgentsPanel.tsx`](frontend/src/experimental/DeclarativeAgentsPanel.tsx), [`frontend/src/novel/WorkflowPanel.tsx`](frontend/src/novel/WorkflowPanel.tsx), [`frontend/src/novel/AgentQueuePanel.tsx`](frontend/src/novel/AgentQueuePanel.tsx)
- Authority/model/store/API source: [`app/experimental/declarative_agents.py`](app/experimental/declarative_agents.py), [`app/experimental/declarative_model.py`](app/experimental/declarative_model.py), [`app/experimental/declarative_adapter_sdk.py`](app/experimental/declarative_adapter_sdk.py), [`frontend/src/experimental/DeclarativeAgentsPanel.tsx`](frontend/src/experimental/DeclarativeAgentsPanel.tsx), [`app/experimental/declarative_agents_api.py`](app/experimental/declarative_agents_api.py)
- Behavior: Declarative role/prompt/input/output/capability/runtime/review schema and rooted workflow dependencies use original JobManager and trusted shipped adapters.
- Version/conflict/cancel/recovery/restart: Preflight/definition CAS/test/run/human gates/cancel/model refresh and bounded retry; no arbitrary executable plugins, persistent access grant or automatic replay.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `declarative_agents_v2`. Dependencies remain server-owned: {"declarative_agents_v2": ["model_broker_v2", "agent_team_recipes", "media_adapter_registry"]}.
- Navigation: FS_SDK, A06, U07, FS_REVIEW, B01.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_post_interop_wave5_templates_sdk_comics.py`](tests/test_post_interop_wave5_templates_sdk_comics.py), [`tests/test_r5_declarative_model.py`](tests/test_r5_declarative_model.py), [`tests/test_r5_declarative_job_bounds.py`](tests/test_r5_declarative_job_bounds.py), [`tests/test_post_interop_task_reopen.py`](tests/test_post_interop_task_reopen.py), [`frontend/src/experimental/ModelTaskReopen.test.tsx`](frontend/src/experimental/ModelTaskReopen.test.tsx), [`frontend/tests/e2e/r4-model-task-reopen.spec.ts`](frontend/tests/e2e/r4-model-task-reopen.spec.ts). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### CORE_AUTOMATION · Original Agent / Workflow execution

- Page/subpage: Tasks → Original Agent / Workflow execution. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Original Agent / Workflow execution.
- Components: [`frontend/src/novel/AgentActivityCenter.tsx`](frontend/src/novel/AgentActivityCenter.tsx), [`frontend/src/novel/AgentJobDetail.tsx`](frontend/src/novel/AgentJobDetail.tsx), [`frontend/src/novel/AgentTeamPanel.tsx`](frontend/src/novel/AgentTeamPanel.tsx), [`frontend/src/novel/AgentQueuePanel.tsx`](frontend/src/novel/AgentQueuePanel.tsx), [`frontend/src/novel/WorkflowPanel.tsx`](frontend/src/novel/WorkflowPanel.tsx), [`frontend/src/novel/WorkflowInspector.tsx`](frontend/src/novel/WorkflowInspector.tsx), [`frontend/src/experimental/TeamsPanel.tsx`](frontend/src/experimental/TeamsPanel.tsx), [`frontend/src/ui/WorkflowWorkspaceRoute.tsx`](frontend/src/ui/WorkflowWorkspaceRoute.tsx)
- Authority/model/store/API source: [`app/services/agent_job_service.py`](app/services/agent_job_service.py), [`app/workflow_api.py`](app/workflow_api.py), [`app/workflow.py`](app/workflow.py), [`app/api.py`](app/api.py)
- Behavior: Original persisted agent/job/Workflow definition and node states remain the execution authority; the declarative SDK and task/review centers are adapters over them.
- Version/conflict/cancel/recovery/restart: Queued/running/waiting-approval/paused/completed/failed/cancelled/review/apply stay distinct. Original cancel/resume/checkpoint/retry and authorization fences survive UI changes; no generic task-center replay.
- Scope/permissions: Original project/chapter/asset/job and collaboration scope where supported; unavailable branch paths must reject, never substitute mainline; Original route/middleware trusted session, owner/current membership and operation-specific domain permission; no client role authority. Profile: `ORIGINAL_AUTHORITY`; explicit legacy gaps take precedence over common defaults.
- Flags: `agent_team_recipes`. Dependencies remain server-owned: {"agent_team_recipes": []}.
- Navigation: Original owner routes and captured project/scope; see API catalog.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_declarative_workflow_host_seam.py`](tests/test_declarative_workflow_host_seam.py), [`tests/test_phase6_agent_jobs.py`](tests/test_phase6_agent_jobs.py), [`tests/test_r2_workflow_execution.py`](tests/test_r2_workflow_execution.py), [`tests/test_r3_media_workflows.py`](tests/test_r3_media_workflows.py), [`tests/test_r4_workflow_projection.py`](tests/test_r4_workflow_projection.py), [`tests/test_visual_text_workflow_contract_v070.py`](tests/test_visual_text_workflow_contract_v070.py). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

### Settings

#### F00 · Foundation, reuse and dependency registry

- Page/subpage: Settings → Capabilities and feature dependencies. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / existing Capabilities and feature dependencies.
- Components: [`frontend/src/ui/CapabilityStatusCenter.tsx`](frontend/src/ui/CapabilityStatusCenter.tsx), [`frontend/src/ui/CapabilityRoadmapPanel.tsx`](frontend/src/ui/CapabilityRoadmapPanel.tsx), [`frontend/src/experimental/DeferredExperimentalWorkbench.tsx`](frontend/src/experimental/DeferredExperimentalWorkbench.tsx), [`frontend/src/experimental/experimentalNavigation.tsx`](frontend/src/experimental/experimentalNavigation.tsx), [`frontend/src/experimental/shared.tsx`](frontend/src/experimental/shared.tsx), [`frontend/src/main.tsx`](frontend/src/main.tsx), [`frontend/src/ui/CapabilityPlaceholder.tsx`](frontend/src/ui/CapabilityPlaceholder.tsx), [`frontend/src/ui/DesignSystemFixture.tsx`](frontend/src/ui/DesignSystemFixture.tsx), [`frontend/src/ui/ModulePlaceholders.tsx`](frontend/src/ui/ModulePlaceholders.tsx), [`frontend/src/ui/ModuleWorkspaceRoutes.tsx`](frontend/src/ui/ModuleWorkspaceRoutes.tsx), [`frontend/src/ui/moduleRegistry.tsx`](frontend/src/ui/moduleRegistry.tsx)
- Authority/model/store/API source: [`app/experimental/flags.py`](app/experimental/flags.py), [`app/experimental/store.py`](app/experimental/store.py), [`app/experimental/api.py`](app/experimental/api.py), [`app/experimental/capabilities.py`](app/experimental/capabilities.py), [`frontend/src/experimental/api.ts`](frontend/src/experimental/api.ts)
- Behavior: Discovery schema v2 preserves legacy features and exposes all RUNTIME_FLAGS through runtime_features plus surface_features. New flags require explicit opt-in and dependencies; frontend normalizes runtime_features. Discovery does not imply provider availability; V1 acceptance mode disables opt-in.
- Version/conflict/cancel/recovery/restart: No external execution or mutation: cancel is request abort; restart rereads host configuration. Original forty-package inventory remains unchanged.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: Original core runtime/capability gates; no new blanket opt-in. Dependencies remain server-owned: {}.
- Navigation: Original owner routes and captured project/scope; see API catalog.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`frontend/src/ui/CapabilityStatusCenter.test.tsx`](frontend/src/ui/CapabilityStatusCenter.test.tsx), [`frontend/src/ui/CapabilityRoadmapPanel.test.tsx`](frontend/src/ui/CapabilityRoadmapPanel.test.tsx), [`tests/test_r4_capabilities.py`](tests/test_r4_capabilities.py), [`frontend/src/experimental/api.surface-flags.test.ts`](frontend/src/experimental/api.surface-flags.test.ts), [`tests/test_surface_api_catalog.py`](tests/test_surface_api_catalog.py), [`frontend/src/experimental/DeferredExperimentalWorkbench.test.tsx`](frontend/src/experimental/DeferredExperimentalWorkbench.test.tsx). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### U12 · Actionable errors and private diagnostic export

- Page/subpage: Settings → Diagnostic preview / Export. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Diagnostic preview / Export.
- Components: [`frontend/src/novel/RuntimeDiagnostics.tsx`](frontend/src/novel/RuntimeDiagnostics.tsx), [`frontend/src/experimental/WorkspaceToolsPanel.tsx`](frontend/src/experimental/WorkspaceToolsPanel.tsx), [`frontend/src/Health.tsx`](frontend/src/Health.tsx)
- Authority/model/store/API source: [`app/experimental/ux.py`](app/experimental/ux.py), [`app/experimental/ux_api.py`](app/experimental/ux_api.py), [`app/runtime_diagnostics.py`](app/runtime_diagnostics.py), [`frontend/src/novel/RuntimeDiagnostics.tsx`](frontend/src/novel/RuntimeDiagnostics.tsx), [`frontend/src/experimental/WorkspaceToolsPanel.tsx`](frontend/src/experimental/WorkspaceToolsPanel.tsx)
- Behavior: Allowlisted bounded diagnostics from original task/configuration authorities; preview digest binds export and excludes private source bytes, credentials and raw logs.
- Version/conflict/cancel/recovery/restart: Cancel discards download; regenerate a current preview after source/authority change. No automatic upload or replay. Restart requires fresh preview.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `workspace_tools_v2`. Dependencies remain server-owned: {"workspace_tools_v2": []}.
- Navigation: U07, U09.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_post_interop_workspace_ux.py`](tests/test_post_interop_workspace_ux.py), [`frontend/src/novel/RuntimeDiagnostics.test.tsx`](frontend/src/novel/RuntimeDiagnostics.test.tsx), [`frontend/src/experimental/WorkspaceToolsPanel.test.tsx`](frontend/src/experimental/WorkspaceToolsPanel.test.tsx). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### U10 · Scenario onboarding and progressive disclosure

- Page/subpage: Settings → First Run / Onboarding / Practice project. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / existing First Run / Onboarding / Practice project.
- Components: [`frontend/src/novel/EntryExperience.tsx`](frontend/src/novel/EntryExperience.tsx), [`frontend/src/novel/FirstUsePanel.tsx`](frontend/src/novel/FirstUsePanel.tsx), [`frontend/src/novel/SampleJourneyGuide.tsx`](frontend/src/novel/SampleJourneyGuide.tsx), [`frontend/src/ui/FeatureLauncher.tsx`](frontend/src/ui/FeatureLauncher.tsx)
- Authority/model/store/API source: [`app/experimental/first_use.py`](app/experimental/first_use.py), [`frontend/src/novel/EntryExperience.tsx`](frontend/src/novel/EntryExperience.tsx), [`frontend/src/ui/FeatureLauncher.tsx`](frontend/src/ui/FeatureLauncher.tsx), [`app/experimental/first_use_api.py`](app/experimental/first_use_api.py)
- Behavior: OriginalFirstUseAuthorities create through original local or workspace project/chapter owners. One actor/workspace receipt precedes each non-idempotent create.
- Version/conflict/cancel/recovery/restart: Skip/reopen and explicit recover; interrupted create stays UNKNOWN until evidence resolves it. No automatic duplicate sample, model call or consent. Native installer/first-run acceptance is LOCAL_REQUIRED.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `workspace_tools_v2`. Dependencies remain server-owned: {"workspace_tools_v2": []}.
- Navigation: CORE_MANUSCRIPT, U01, CORE_EXPORT, CORE_MODELS.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`frontend/src/novel/EntryExperience.test.tsx`](frontend/src/novel/EntryExperience.test.tsx), [`frontend/src/novel/FirstUsePanel.test.tsx`](frontend/src/novel/FirstUsePanel.test.tsx), [`frontend/src/ui/FeatureLauncher.test.tsx`](frontend/src/ui/FeatureLauncher.test.tsx), [`frontend/src/ui/FeatureLauncher.css.test.ts`](frontend/src/ui/FeatureLauncher.css.test.ts), [`tests/test_r4_first_use_mounted.py`](tests/test_r4_first_use_mounted.py). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: EXTERNAL_TARGETS, FINAL_SOURCE_CI.

#### U13 · Chinese input, accessibility and scale

- Page/subpage: Settings → Accessibility / Input / Scale. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Accessibility / Input / Scale.
- Components: [`frontend/src/Editor.tsx`](frontend/src/Editor.tsx), [`frontend/src/ui/AppShell.tsx`](frontend/src/ui/AppShell.tsx), [`frontend/src/ui/primitives.tsx`](frontend/src/ui/primitives.tsx), [`frontend/src/experimental/WorkspaceInteractionPanel.tsx`](frontend/src/experimental/WorkspaceInteractionPanel.tsx)
- Authority/model/store/API source: [`frontend/src/Editor.tsx`](frontend/src/Editor.tsx), [`frontend/src/ui/AppShell.tsx`](frontend/src/ui/AppShell.tsx)
- Behavior: Semantic controls, labelled fields, focus return, IME-safe editing and scoped interaction preferences; native screen-reader and physical-input performance are separate acceptance layers.
- Version/conflict/cancel/recovery/restart: Retain dirty/IME buffers and focus on cancel; persisted keyboard/reduced-motion/announcement preferences use FS_INTERACTION CAS/history. No global keyboard interception in text input.
- Scope/permissions: Current project/actor/scope and chapter identity/version; unauthenticated local hint never substitutes for authenticated target authorization; Current owner APIs authorize navigation/restore; local UI preference does not grant access. Profile: `UI_INTERACTION`; explicit legacy gaps take precedence over common defaults.
- Flags: `writing_recovery_v2`. Dependencies remain server-owned: {"writing_recovery_v2": []}.
- Navigation: FS_INTERACTION, U02, U01.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`frontend/src/Editor.anchor.test.tsx`](frontend/src/Editor.anchor.test.tsx), [`frontend/src/Editor.recovery.test.tsx`](frontend/src/Editor.recovery.test.tsx), [`frontend/src/Editor.a43-rich.test.tsx`](frontend/src/Editor.a43-rich.test.tsx), [`frontend/src/Editor.typography.test.ts`](frontend/src/Editor.typography.test.ts), [`frontend/src/ui/AppShell.test.tsx`](frontend/src/ui/AppShell.test.tsx), [`frontend/src/ui/primitives.test.tsx`](frontend/src/ui/primitives.test.tsx). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: EXTERNAL_TARGETS, FINAL_SOURCE_CI.

#### B01 · Declarative template library

- Page/subpage: Settings → Template Library. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Template Library.
- Components: [`frontend/src/experimental/TemplateLibraryPanel.tsx`](frontend/src/experimental/TemplateLibraryPanel.tsx)
- Authority/model/store/API source: [`app/experimental/template_library.py`](app/experimental/template_library.py), [`app/experimental/declarative_agents.py`](app/experimental/declarative_agents.py), [`frontend/src/experimental/TemplateLibraryPanel.tsx`](frontend/src/experimental/TemplateLibraryPanel.tsx), [`app/experimental/template_library_api.py`](app/experimental/template_library_api.py)
- Behavior: Local strict declarative packages and independent project instances; import/copy do not grant permissions or execute code.
- Version/conflict/cancel/recovery/restart: Version/compatibility checks, compare/update/revert/history, recoverable uninstall; cancel preview/import is explicit; restart reads persisted copies.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `template_library_v2`. Dependencies remain server-owned: {"template_library_v2": []}.
- Navigation: FS_PLANNING, B02, CORE_CREATION.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_post_interop_wave5_templates_sdk_comics.py`](tests/test_post_interop_wave5_templates_sdk_comics.py), [`frontend/src/experimental/Wave5TemplatesSdkComics.test.tsx`](frontend/src/experimental/Wave5TemplatesSdkComics.test.tsx). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### FS_SDK · Model / Import / Export Adapter SDK

- Page/subpage: Settings → Model / Import / Export Adapter SDK. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Model / Import / Export Adapter SDK.
- Components: [`frontend/src/novel/PluginManagerPanel.tsx`](frontend/src/novel/PluginManagerPanel.tsx), [`frontend/src/novel/PluginInspector.tsx`](frontend/src/novel/PluginInspector.tsx), [`frontend/src/experimental/DeclarativeAgentsPanel.tsx`](frontend/src/experimental/DeclarativeAgentsPanel.tsx)
- Authority/model/store/API source: [`app/experimental/declarative_adapter_sdk.py`](app/experimental/declarative_adapter_sdk.py), [`app/experimental/declarative_agents.py`](app/experimental/declarative_agents.py), [`app/experimental/media.py`](app/experimental/media.py), [`app/experimental/imports.py`](app/experimental/imports.py), [`app/experimental/interactive_story.py`](app/experimental/interactive_story.py), [`app/plugin_package_manager.py`](app/plugin_package_manager.py), [`app/plugin_contracts.py`](app/plugin_contracts.py), [`app/plugin_capability_policy.py`](app/plugin_capability_policy.py), [`app/experimental/declarative_agents_api.py`](app/experimental/declarative_agents_api.py), [`app/experimental/media_api.py`](app/experimental/media_api.py), [`app/experimental/imports_api.py`](app/experimental/imports_api.py), [`app/experimental/interactive_story_api.py`](app/experimental/interactive_story_api.py), [`app/plugin_management_api.py`](app/plugin_management_api.py)
- Behavior: Strict finite schemas and trusted shipped adapter seams: model generation, bounded import extraction, pure export; Agent/Workflow execution remains B02 original JobManager.
- Version/conflict/cancel/recovery/restart: Executable third-party plugin policy remains DENY_ALL. Sandbox/capability/file/network/runtime isolation/trust-signature are prerequisites, not implemented permissions. Cancel/recovery stays with actual owner; registry metadata never permits execution.
- Scope/permissions: novel_id + local mode OR workspace_id/project/novel_id/storyline_id/branch_id; actor-private projections as required by original owner; Mounted original _workbench_authorize/host-session/current membership; domain.read/write/review per route, with repeat authorization at declared dispatch/publication boundaries. Profile: `EXPERIMENTAL_SCOPED`; explicit legacy gaps take precedence over common defaults.
- Flags: `declarative_agents_v2`, `media_adapter_registry`. Dependencies remain server-owned: {"declarative_agents_v2": ["model_broker_v2", "agent_team_recipes", "media_adapter_registry"], "media_adapter_registry": []}.
- Navigation: B02, CORE_MODELS, FS_IMPORT, CORE_EXPORT.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_r2_media_api.py`](tests/test_r2_media_api.py), [`tests/test_r5_interactive_story.py`](tests/test_r5_interactive_story.py), [`tests/test_r5_interactive_story_mounted.py`](tests/test_r5_interactive_story_mounted.py), [`frontend/src/novel/PluginManagerPanel.test.tsx`](frontend/src/novel/PluginManagerPanel.test.tsx), [`frontend/src/novel/PluginInspector.test.tsx`](frontend/src/novel/PluginInspector.test.tsx). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Remaining boundaries: FINAL_SOURCE_CI.

#### FS_INTERACTION · Command Palette / Keyboard / Accessibility preferences

- Page/subpage: Settings → Command Palette / Keyboard / Accessibility preferences. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / NOVEL experimental workbench / Command Palette / Keyboard / Accessibility preferences.
- Components: [`frontend/src/experimental/WorkspaceInteractionPanel.tsx`](frontend/src/experimental/WorkspaceInteractionPanel.tsx), [`frontend/src/experimental/WorkspaceToolsPanel.tsx`](frontend/src/experimental/WorkspaceToolsPanel.tsx)
- Authority/model/store/API source: [`app/experimental/workspace_interaction.py`](app/experimental/workspace_interaction.py), [`app/experimental/ux.py`](app/experimental/ux.py), [`app/experimental/ux_api.py`](app/experimental/ux_api.py)
- Behavior: Actor/project/scope-bound preference row and command revision. Finite commands resolve original workspace sections with dirty guard and never dispatch tasks; keyboard bindings are tool-local.
- Version/conflict/cancel/recovery/restart: CAS save/history/restore/reset, corruption RECOVERY_REQUIRED disables keyboard; explicit reset. Read-only command resolve can be cancelled; restart rereads preferences; typing/IME/repeat do not invoke commands. Global app-wide customizable palette remains outside this bounded implementation.
- Scope/permissions: Current project/actor/scope and chapter identity/version; unauthenticated local hint never substitutes for authenticated target authorization; Current owner APIs authorize navigation/restore; local UI preference does not grant access. Profile: `UI_INTERACTION`; explicit legacy gaps take precedence over common defaults.
- Flags: `workspace_interaction_v1`. Dependencies remain server-owned: {"workspace_interaction_v1": ["workspace_tools_v2"]}.
- Navigation: U01, U03, U07, U12, U13.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_collaboration_ux_api_v057.py`](tests/test_collaboration_ux_api_v057.py), [`tests/test_surface_workspace_interaction.py`](tests/test_surface_workspace_interaction.py), [`frontend/src/experimental/WorkspaceInteractionPanel.test.tsx`](frontend/src/experimental/WorkspaceInteractionPanel.test.tsx), [`frontend/src/experimental/WorkspaceToolsPanel.test.tsx`](frontend/src/experimental/WorkspaceToolsPanel.test.tsx). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Formal contract: [`app/experimental/workspace_interaction.py`](app/experimental/workspace_interaction.py), [`frontend/src/experimental/WorkspaceInteractionPanel.tsx`](frontend/src/experimental/WorkspaceInteractionPanel.tsx).
- Remaining boundaries: FINAL_SOURCE_CI.

#### CORE_INTEROP · Frozen PoemSeed Local Interop 1.0

- Page/subpage: Settings → Frozen PoemSeed Local Interop 1.0. Entry: **ENGINEERING_UI**.
- Current host: Shared AppShell / existing Frozen PoemSeed Local Interop 1.0.
- Components: [`frontend/src/interop/entry.tsx`](frontend/src/interop/entry.tsx), [`frontend/src/interop/DesktopIntegrationDetails.tsx`](frontend/src/interop/DesktopIntegrationDetails.tsx), [`frontend/src/interop/LocalTutorIntegration.tsx`](frontend/src/interop/LocalTutorIntegration.tsx)
- Authority/model/store/API source: [`app/local_interop/api.py`](app/local_interop/api.py), [`app/local_interop/transport.py`](app/local_interop/transport.py), [`app/local_interop/host.py`](app/local_interop/host.py), [`app/local_interop/desktop.py`](app/local_interop/desktop.py), [`app/local_interop/provider.py`](app/local_interop/provider.py), [`app/local_interop/chapter_ids.py`](app/local_interop/chapter_ids.py), [`frontend/src/interop/client.ts`](frontend/src/interop/client.ts), [`frontend/src/interop/chapterIds.ts`](frontend/src/interop/chapterIds.ts)
- Behavior: Frozen PoemSeed 1.0 schemas/public fields/product IDs/opaque-ID alphabet remain compatible. Original InteropContextProvider resolves the registered branch manuscript via CollaborationReadService; empty/disabled/revoked branches never borrow mainline. One Host and original consent/session authorities remain. Native incompatible chapter IDs use full scope-bound SHA-256 wire labels, not a second editable store or authority.
- Version/conflict/cancel/recovery/restart: Reverse wire lookup enumerates live exact-scope owner rows and rejects missing/archive/tombstone/collision; only explicit authorized editor handoff returns validated native identity. Response-body context/source/selection/handoff and queued event frames recheck owner/consent. Host restart invalidates sessions; no alias registry or mainline fallback for registered production branches. Actual native Desktop LOCAL_REQUIRED, browser/real PostgreSQL hosted-pending; synthetic Tutor remains MOCK_ONLY. Frozen public protocol objects remain unchanged.
- Scope/permissions: Original project/chapter/asset/job and collaboration scope where supported; unavailable branch paths must reject, never substitute mainline; Original route/middleware trusted session, owner/current membership and operation-specific domain permission; no client role authority. Profile: `ORIGINAL_AUTHORITY`; explicit legacy gaps take precedence over common defaults.
- Flags: `local_tutor_interop_v1`. Dependencies remain server-owned: {"local_tutor_interop_v1": []}.
- Navigation: FS_BRANCH, CORE_MANUSCRIPT, U01, U07.
- States: Loading, Empty, Error, Unauthorized, NOT_CONFIGURED, Disabled, Conflict, Review, Recovery, PARTIAL, Cancelled, Stale; shared state contract plus owner-specific lifecycle above.
- Tests (source presence only): [`tests/test_asset_provider_adapter.py`](tests/test_asset_provider_adapter.py), [`tests/test_asset_provider_catalog_api.py`](tests/test_asset_provider_catalog_api.py), [`tests/test_asset_provider_config.py`](tests/test_asset_provider_config.py), [`tests/test_asset_provider_contract.py`](tests/test_asset_provider_contract.py), [`tests/test_audio_provider_config.py`](tests/test_audio_provider_config.py), [`tests/test_audio_providers.py`](tests/test_audio_providers.py). Complete list in JSON; all exact-final-head execution gates **PENDING**.
- Source-bound focused owner receipts (not final-head acceptance): [`docs/LOCAL_INTEROP_BRANCH_OWNER_INTEGRATION.md`](docs/LOCAL_INTEROP_BRANCH_OWNER_INTEGRATION.md), [`docs/delivery/functional-surface-freeze/INTEROP_FIXTURE_EXCEPTION.json`](docs/delivery/functional-surface-freeze/INTEROP_FIXTURE_EXCEPTION.json), [`docs/delivery/functional-surface-freeze/BROWSER_INTEGRATION_CORRECTIONS.md`](docs/delivery/functional-surface-freeze/BROWSER_INTEGRATION_CORRECTIONS.md).
- Formal contract: [`docs/LOCAL_INTEROP_BRANCH_OWNER_INTEGRATION.md`](docs/LOCAL_INTEROP_BRANCH_OWNER_INTEGRATION.md), [`docs/delivery/functional-surface-freeze/INTEROP_FIXTURE_EXCEPTION.json`](docs/delivery/functional-surface-freeze/INTEROP_FIXTURE_EXCEPTION.json), [`docs/delivery/functional-surface-freeze/INTEROP_FIXTURE_EXCEPTION.patch`](docs/delivery/functional-surface-freeze/INTEROP_FIXTURE_EXCEPTION.patch).
- Remaining boundaries: FINAL_SOURCE_CI.

## Implemented original-owner closures

These are source-inspected implementations with focused owner receipts, not final-head acceptance.

- **GAP_CONTINUITY_FEEDBACK** (FS_CONTINUITY, FS_FORESHADOWING): Original FindingReviewService and original File/PostgreSQL findings provide source/fingerprint-bound review CAS, retained reason/history, exact historical evidence, stale projection and unchanged-source intentional suppression. Existing Continuity UI hosts concrete findings controls. Exact-final-head verification remains PENDING.
- **GAP_CANON_LEGACY_CAS** (FS_CANON): Original pending Canon owner now has preview/version/reason/operation binding, terminal idempotence, project-only permissions, File prepared-journal recovery/cancel and transactional PostgreSQL promotion. Original legacy terminal writes cannot reopen or duplicate approved facts. Exact-final-head verification remains PENDING.
- **GAP_STORY_RECORD_CAS** (FS_TIMELINE, FS_FORESHADOWING, FS_STORY_DATABASE): All five original record kinds (Character, Location, Relationship, Timeline, Foreshadowing) now share mandatory digest/version CAS in their flag-ON current editors/versioned routes, source lineage, bounded history/restore, feedback and owner-keyed draft recovery. Original IDs, sparse shape and opaque imported fields survive. Legacy OFF/component-only/direct-client compatibility remains explicit; universal CAS on historical endpoints is not claimed. Exact-final-head verification remains PENDING.
- **GAP_ADAPTATION_LIFECYCLE** (CORE_ADAPTATION): Original adaptation owner now has File/PostgreSQL revision/history, immutable rich source snapshots, reserved target intent/checkpoints, reviewed-target CAS, cancel/recover, bounded capacity/reserves and original rendered lifecycle controls. Read-through Task/Review and actual exact-task navigation are integrated. Real model admission and unknown creation-write reconciliation remain explicit boundaries. Exact-final-head verification remains PENDING.

## Remaining product and environment boundaries

A synthetic or formal adapter boundary permitted by the request is distinguished from a genuine missing original-owner behavior. Neither is renamed “complete.”

### LEGACY_STRUCTURED_CAS_COMPATIBILITY · EXPLICIT_LEGACY_COMPATIBILITY_BOUNDARY

Surfaces: FS_STORY_DATABASE, FS_TIMELINE, FS_FORESHADOWING. All five current Story editor kinds require digest/version through the shared versioned surface when story_record_versions_v1 is ON. Flag-OFF/component-only callbacks and historical direct clients keep compatible behavior while existing version metadata advances history. This is retained legacy compatibility, not a missing version/history/recovery path in current Character/Location/Relationship forms.

Freeze consequence: Preserve the mandatory current-editor contract and explicit flag-OFF/old-client compatibility. Requiring CAS on every historical direct endpoint would be a separate backward-compatibility change; do not remove guarded current editors during visual work.

### ADAPTATION_UNKNOWN_CREATION_RECOVERY · PARTIAL_OPERATOR_RECONCILIATION_REQUIRED

Surfaces: CORE_ADAPTATION. Known clean checkpoints and exact committed apply receipts support explicit recovery. An uncertain project/chapter creation intent without provable committed receipt stays RECOVERY_REQUIRED and needs operator reconciliation. No endpoint guesses target ownership from title/chapter count, and no second target/write is automatically created.

Freeze consequence: Retain this concrete fail-closed recovery boundary and original receipt history; no automatic replay, fully automated crash recovery or real model admission claim.

### FORMAL_NEW_INSPECTORS · FORMAL_UI_CONTRACT_ALLOWED_BY_REQUEST

Surfaces: FS_REALTIME, FS_SYNC, FS_VISUAL, FS_RESEARCH_VISION, FS_PROCESSING. Mounted APIs/services and formal adjacent-owner inspectors exist. Full new controls are not rendered in all existing host panels; catalog component list marks host versus actual UI.

Freeze consequence: Formal contracts satisfy the allowed surface-entry alternative only if all states/actions/permissions/lifecycle are concrete and validated. No browser-rendered claim for absent controls.

### EXTERNAL_REAL_MODELS · NOT_CONFIGURED_OR_NOT_RUN

Surfaces: FS_SEMANTIC, FS_VISUAL, FS_RESEARCH_VISION, CORE_IMAGES, CORE_VIDEO, CORE_AUDIO, FS_PROCESSING, A01, A02, A03, A07, B05, CORE_ADAPTATION. Synthetic contracts and local finite adapters do not establish real embedding/OCR/Vision/ASR/alignment/GPU/perceptual or literary quality. Real model admission integration remains absent for new synthetic-only adapter seams and adaptation; these routes fail closed as NOT_CONFIGURED.

Freeze consequence: Retain NOT_CONFIGURED/NOT_RUN/MOCK_ONLY; user permits bounded adapters, never counterfeit REAL_VERIFIED.

### EXTERNAL_PRODUCTION_TRANSPORT · PARTIAL_NOT_CONFIGURED

Surfaces: FS_REALTIME, FS_SYNC. No deployed production realtime server, cloud sync or production encryption. Actual synthetic transport and strict-CAS protocol are not CRDT/OT; branch production-sync adapter is explicitly unavailable.

Freeze consequence: Allowed local/synthetic contract boundary; do not claim production cloud/coediting acceptance.

### EXTERNAL_TARGETS · LOCAL_REQUIRED_NOT_RUN

Surfaces: FS_ENGINES, A12, B06, U13, U10. Godot/Ren'Py/NLE/native Windows IME/accessibility/installer/real font/print acceptance remains separate from schema, generated file and synthetic browser evidence.

Freeze consequence: Require real target acceptance later; retain current evidence labels.

### FINAL_SOURCE_CI · PENDING_EXACT_FINAL_HEAD

Surfaces: F00, U02, U01, U03, U07, U08, U09, U12, U04, U10, U13, A04, A05, A06, A07, A09, A13, U06, A02, A03, A01, A10, A11, U05, U11, U15, A08, A12, B03, B04, U14, U16, B01, B02, B05, B06, B07, B08, B09, B10, CORE_MANUSCRIPT, CORE_GENERATION, CORE_CREATION, FS_PLANNING, FS_CANON, FS_CONTINUITY, FS_FORESHADOWING, FS_TIMELINE, FS_STORY_DATABASE, FS_IMPORT, FS_REVIEW, CORE_IMAGES, CORE_SCREENPLAY, CORE_VIDEO, CORE_AUDIO, CORE_ASSETS, CORE_MODELS, CORE_EXPORT, CORE_COLLAB, FS_BRANCH, FS_REALTIME, FS_SEMANTIC, FS_VISUAL, FS_SYNC, FS_RESEARCH_VISION, FS_PROCESSING, FS_ENGINES, FS_SDK, FS_UNIVERSE, FS_INTERACTION, CORE_INTEROP, CORE_AUTOMATION, CORE_ADAPTATION. Final source is not yet pinned to corrected hosted results. First hosted candidate 13b9 failed original flag-discovery compatibility assertions; f25 is the compatibility-repair checkpoint, not a final-source verification receipt. A subsequent 8,626-node File snapshot reported an original erased-vector receipt regression and remains failed evidence. EmbeddingService.records now permits only same-source-owner/same-index-owner erased INVALIDATED receipts under current scope/feature authority; focused corrected coverage reported 51 File passes with 50 backend-profile skips plus 3 API catalog passes. The subsequently published d9d2df3a checkpoint retains failed push/PR Frontend receipts, documented in BROWSER_INTEGRATION_CORRECTIONS.md; no earlier failed screenshot is acceptance evidence. Meanwhile the later five-kind Story editor, adapter-receipt and Local Interop branch-owner follow-on changes require a new source-bound immutable checkpoint. The d9 PostgreSQL stored-facts assertion also failed on opaque Timeline IDs/public-slug versus UUID storage/FK ownership; the original repository adapter is corrected without changing that assertion, and the new identity matrix is File-tested only locally. No result for the corrected checkpoint is inferred from previous focused or hosted checks. Local Chromium/socket launch denied; real PostgreSQL unavailable locally.

Freeze consequence: Lead must pin source and verify actual hosted File/PostgreSQL/API/browser/full-regression checks for that source. Historical independent review remains BLOCKED and was not retried.

## Opus visual freedom and protected engineering boundaries

Opus may, after separate user authorization, improve domain information hierarchy, labels, grouping, density, spacing, alignment, status presentation, focus treatment, responsive inspector content and discoverability using the existing tokens/primitives and one AppShell/ModuleWorkspace contract. All ten logical product areas must remain available; related secondary inspectors may be grouped without inventing a new data owner or an eleventh area.

Opus may not silently change:

- Mainline versus branch manuscript ownership, Chapter/Scene/Shot/entity identity, original store ownership or migrations.
- Trusted-session/membership/permission/scope checks, owner-private data, source-policy egress, credential vault, DENY_ALL executable plugin policy or Local Interop 1.0 compatibility.
- Version/CAS/edit-version/source-digest/index-version/preview-digest contracts, history, conflict preservation or partial-apply journals.
- Job claims, attempts, cancel/late-result fences, UNKNOWN/interrupted recovery, explicit retry/resume or paid/uncertain dispatch restrictions.
- Human Review, Draft/Diff/Accept, exact navigation, character-only knowledge fences or Research-versus-Canon boundaries.
- Loading/empty/unauthorized/missing-config/disabled/conflict/stale/review/recovery distinctions; NOT_RUN, MOCK_ONLY, PARTIAL, LOCAL_REQUIRED and real measured evidence labels.
- Existing source-specific assertions, test coverage/skips, frozen evidence or screenshot baselines merely to turn a gate green.

Protected shell, switcher, context/sidebar/inspector/status layout, tokens and global primitives require the repository Design System Change Request and owner approval before system-level changes. No final visual redesign is authorized by this map.

## Candidate gate and final delivery ownership

The ten-area vocabulary, owner relationships and formal seams are mapped. This does not itself establish that all implementation gaps or tests are complete. Before the lead can issue any candidate declaration, it must reconcile the genuine gaps, pin the final commit, verify current File/PostgreSQL/API/permission/version/conflict/cancel/recovery/flag and relevant browser/contract gates, and retain honest NOT_RUN/LOCAL_REQUIRED/BLOCKED boundaries. A candidate, if later justified, still requires user review and is not formal freeze or authorization to merge/release/deploy.

The lead's final GitHub report owns Starting SHA, Final SHA, branch, Draft PR, commit list, exact mounted API catalog, current matrix, remaining missing features and actual test results. This map is additive to historical delivery artifacts and preserves the independent-review BLOCKED boundary.

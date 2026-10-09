# V2 architecture and owner reuse map

## Audit identity and scope

This is the **M0 engineering inventory**, inspected on 2026-10-09 against commit
`4350a61fb9f61acccb845fef96b24b9b1275bbd3`, tree
`a05d33f75c5af6f26171d6370c0efeb13a68619d`. It distinguishes implemented owners
from proposed extension seams. It does not announce the entire V2 product complete.

The authoritative inputs were read in full from the user's supplied
`AI_NOVEL_STUDIO_V2_MASTER_ROADMAP(1).txt` (904 lines, 71,777 bytes) and
`DOT_V2_START_INSTRUCTIONS(1).txt` (28 lines, 2,945 bytes as supplied metadata;
the roadmap's section numbers are used below). The actual repository takes
precedence over the roadmap's guesses about existing implementation.

[PR 47](https://github.com/1785235376-blip/AI-Novel-Studio/pull/47) was read on
2026-10-09 at 11:44 UTC: open, Draft, unmerged, same branch HEAD. Its current CI
status is **PARTIAL_CI_CAPACITY**. The old **39 PARTIAL + F00 INTEGRATED** and
**independent review BLOCKED** classifications remain untouched.

Companions: [feature matrix](AI_NOVEL_STUDIO_V2_FEATURE_MATRIX.md),
[M0 report](MILESTONE_M0_REPORT.md), [V1 freeze](V1_SCOPE_FREEZE.md),
[existing rollback contract](docs/delivery/post-interop-continuation/COMPATIBILITY_AND_ROLLBACK.md).

## 1. Actual authority map

An owner below is a service/repository with write authority, not the screen that
happens to display it. A projection or adapter must not become a second owner.

| Domain | Existing authority | Existing adapters / consumers | Safe V2 extension seam |
|---|---|---|---|
| Project identity and lifecycle | `RepositoryBundle.novels`: [FileNovelRepository](app/repositories/file/novel.py) / [FileRepository](app/repository.py), or [PostgresNovelRepository](app/repositories/postgres/novel.py) | [NovelService](app/services/novel_service.py), [API](app/api.py), [collaboration path mutations](app/application/persistence.py), [first-use adapter](app/experimental/first_use.py) | Neutral project terminology and blank creation delegate to the same owner; do not create a second project database. No chapter is required by the neutral UX. |
| Workspace, membership, storyline, branch and permission | [RepositoryBundle](app/repositories/bundle.py), [CollaborationScopeService](app/services/collaboration_scope_service.py), [AuthorizationService](app/services/authorization_service.py), [trusted sessions](app/trusted_sessions.py) | [collaboration API](app/collaboration_api.py), [experimental API](app/experimental/api.py), [creative API](app/creative/api.py) | Resolve actor and exact scope server-side, recheck before commit and response; intent/preset never grants or removes access. |
| Novel content and revision | [ChapterService](app/services/chapter_service.py), File/PostgreSQL chapter repositories and branch manuscript owner | TipTap editor, generation Draft/Accept, revision UI | A V2 asset reference carries an existing chapter ID/version/digest. Never copy the authoritative prose into an asset registry or node. |
| V2 project incarnation | [CreativeProjectStore](app/creative/project_store.py) wraps [ExperimentalStore](app/experimental/store.py) | Creative documents/proposals | Reuse File `creative_project_v2.json` UUID and PostgreSQL current `novels.id`; never equate a reusable slug with an owner lifetime. This wrapper is not a project registry. |
| Creative structured documents | [CreativeService](app/creative/service.py), [strict models](app/creative/models.py) | [CreativeWorkspace](frontend/src/creative/CreativeWorkspace.tsx), Director suggestions and model coordinator | Existing SCREENPLAY / DIRECTOR / STORYBOARD / PRODUCTION revisions, source binding, archive, history, restore and JSON export. Extend these; do not fork four new document stores. |
| Binary asset bytes and mutable metadata revision | [AssetLibraryService](app/services/asset_library_service.py) | [asset API](app/api.py), [lifecycle router](app/asset_lifecycle_api.py), media, export, research/portable adapters | Keep one UUID, immutable stored bytes, measured SHA256/size and metadata version owner. Add server-owned V2 origin/incarnation constraints here so every access path enforces them. |
| Asset relationships and production evidence | `AssetLibraryService.source_asset_ids` / `annotate_lineage`; [ProductionLineageService](app/experimental/production_lineage.py) projects these | [production lineage API](app/experimental/production_lineage_api.py), [change impact](app/experimental/change_impact.py) | Versioned typed relationship extension on the same owner; exact parent version/digest, scope and rights declaration. Do not fork the asset DAG. |
| Scope-atomic extension metadata | [ExperimentalStore](app/experimental/store.py), migration [019](database/migrations/019_experimental_scope_documents.sql) | DomainService and scoped services | Add bounded versioned metadata collections using original File lock/atomic replace and PostgreSQL transaction/row lock. Preserve old collections and migration files. |
| Storage roots and physical writes | [settings](app/config.py), [WindowsPackagingPaths](app/packaging/paths.py), [atomic_write](app/storage.py), asset owner | Packaged launcher, backup/restore scripts | Project/model/cache/export categories remain separate. `atomic_write` is a primitive, not a general Storage Manager. |
| Existing storage accounting and cleanup | [PortableProjectsService.storage/cleanup](app/experimental/portable_projects.py) | Portable project UI/API | Reuse measured categories and digest-bound cleanup previews. Its cleanup only removes verified reproducible export archives, not models, accepted assets, history, trash or failed-recovery inputs. |
| Workflow DAG definition and execution state | [V1CapabilityService workflow methods](app/services/v1_capability_service.py), [workflow API](app/workflow_api.py) | [DeclarativeAgentsService](app/experimental/declarative_agents.py) via `_ScopedOriginalWorkflowHost`; [workflow recipes](app/workflow_recipes.py) | Typed Creative Graph contracts and UI extend this host. Retain original approval, pause, resume, retry, timeout and original job delegation. No parallel scheduler. |
| Author model jobs | [JobManager](app/jobs.py), [AgentJobService](app/services/agent_job_service.py) | [AuthorRequestPreparer](app/author_request.py), [creative generation](app/creative/generation.py), declarative model adapter | Original admission, cancellation, terminal accounting and review apply. A graph node references the job, not a duplicated job state machine. |
| Existing media execution | [AssetTaskWorker](app/services/asset_task_worker.py), [MediaService](app/experimental/media.py), existing image/audio/video services | [AssetProviderRegistry](app/asset_providers.py), audio provider adapters, media review | Adapt existing modality owners into graph tasks. The repository already has modality-specific execution owners; unify projection/orchestration without claiming they are already one queue. |
| Task center | [workspace_task_owners](app/experimental/workspace_task_owners.py), [UX service](app/experimental/ux.py) | Existing task-center UI | Read/action projections retain original task IDs and owner semantics. Never invent progress or replay an unknown task. |
| Model discovery and enablement | [LocalDiscoveryService](app/model_center/discovery.py), [ModelCenterService](app/model_center/service.py), [environment scanner](app/model_center/discovery_environment.py), [HardwareInventory](app/provider_runtime_v2_host_hardware_inventory.py) | [LocalDiscoveryBridge](app/model_center/discovery_bridge.py), Runtime/Provider registries, [ModelCenter UI](frontend/src/ui/ModelCenter.tsx) | Extend these registries and evidence levels. No new model inventory, unbounded scan, automatic download, enablement or launch. |
| Route, price, budget and reconciliation | [ModelBrokerService](app/experimental/model_broker.py), [provider profiles](app/experimental/provider_profiles.py), [credential vault](app/credential_vault.py) | Creative model preview/dispatch, media, declared agents | Preserve preview binding, explicit outbound authorization, admission idempotency and unknown upstream accounting; no implicit paid fallback. |
| Knowledge relationships | [WorldService](app/experimental/world.py), [StoryGraph](app/experimental/story_graph.py), [ResearchLibraryService](app/experimental/research_library.py) | World/character context, evidence search and research UI | Evidence/confidence-based knowledge references remain separate from asset provenance and executable edges. |
| Director and timeline-adjacent planning | [DirectorService](app/experimental/director.py), creative DIRECTOR/PRODUCTION documents, original screenplay/shot owners | [VideoTimeline](frontend/src/novel/VideoTimeline.tsx), [ProductionTimeline](frontend/src/creative/ProductionTimeline.tsx) | Preserve planning and its stable shot references. A future NLE timeline needs explicit edit semantics; planning cards are not tracks. |
| Existing media assembly / captions / exchange | [VideoAssemblyService](app/services/video_assembly_service.py), [SubtitleTimelineService](app/experimental/subtitle_timeline.py), [TimelineExchange](app/experimental/timeline_exchange.py) | Existing assembly/caption/OTIO UI | Reuse verified media decoding, rational time and exchange boundaries; bounded video-only 640×360/24fps assembly is not a full NLE. |
| Export and portable delivery | [ExportJobService](app/services/export_job_service.py), [NovelService exporters](app/services/novel_service.py), AssetLibrary download, [PortableProjectsService](app/experimental/portable_projects.py) | Export panel, creative JSON export, portable package UI | Independent asset export delegates to the byte owner; future full graph/timeline package extends versioned portable formats. Existing portable archives are chapter-selected and not full V2 packages. |
| Optional Tutor bridge | [Studio host/provider/API](app/local_interop), [protocol](LOCAL_INTEROP_PROTOCOL_V1.md), [security](LOCAL_INTEROP_SECURITY.md) | [LocalTutorIntegration](frontend/src/interop/LocalTutorIntegration.tsx), reference adapters | Read-only minimized project/asset/task/graph context through versioned capability negotiation. No new protocol or control authority. |
| UI shell | [AppShell](frontend/src/ui/AppShell.tsx), [design system](docs/ui/design_system.md), [protected surfaces](docs/ui/protected_ui_surfaces.md) | ModuleWorkspace, existing NOVEL / IMAGE / VIDEO consumers | New content consumes existing shell/tokens. Protected shell changes need the documented design change request and independent visual evidence. |

## 2. Three graphs, three meanings

1. **Asset Relationship Graph** is descriptive provenance. Existing parents are
   measured under the asset owner's lock. It has no dispatch authority and a
   reference never establishes copyright or redistribution permission.
2. **Creative Workflow Graph** is a user-authored execution dependency graph.
   The original workflow host already rejects cycles and unknown node IDs,
   snapshots definitions and owns review/state transitions. Current edges contain
   source/target IDs, not the full V2 typed media-port contract. Add that contract
   without replacing the host or duplicating JobManager.
3. **Knowledge Graph** is evidence-bearing fictional/research knowledge, including
   fact versus belief, temporal validity and hypotheses. It cannot double as a
   media dependency graph or imply that unreviewed AI output became canon.

The existing [ImageInfiniteCanvas](frontend/src/novel/ImageInfiniteCanvas.tsx)
is a reference-board interaction surface with pan/zoom, selection, groups and
undo/redo. It is reusable UI experience, not an executable typed graph.
[VisualTextWorkflowAdapter](app/visual_workflow.py) is read-only.
[NovelWorkflow](app/workflow.py) is a legacy synthetic fixture requiring explicit
`draft_override`; neither is a new production execution owner.

## 3. First safe M1 vertical slice (design, not implemented by M0)

Required user path: **blank project → external image import → independent asset
ID/version/provenance → save/reopen → independent export**, with no mandatory
Novel, Chapter, Screenplay, Director, model install or graph interaction.

### 3.1 Neutral project adapter

- Create an existing project owner with no chapter and return its server identity.
  Keeping the legacy storage field named `novel_id` is an internal compatibility
  detail; requiring a novel-writing user journey is not acceptable.
- Persist bounded `CreativeIntent[]` and `WorkspacePreset` metadata only.
  Skipping, changing or combining them cannot alter grants, delete assets, hide
  otherwise accessible modules or dispatch jobs.
- Use the original local/collaboration create authority. Packaged or scoped
  sessions cannot silently fall back to `local-author`.
- Record admission before a non-idempotent create; interruption with an unknown
  receipt requires reconciliation, not a title-based search-and-adopt/replay.

### 3.2 Asset owner extension, not duplicate asset index

- Import bytes through `AssetLibraryService.create` with a server-owned origin,
  required feature gate, exact project incarnation and exact branch. The server
  computes digest and size; the client cannot supply an authoritative version.
- Retain the same metadata version owner. A project view may index asset IDs or
  query them, but must not maintain a second independently mutable version,
  storage reference, provenance or relationship graph.
- Existing `ProductionLineageService` accepts `EXTERNAL_IMPORT` with empty
  `chapter_ids`. Reuse that declaration model and original `annotate_lineage`
  mutation, preserving the distinction between rights declaration and legal
  verification. Review format and actual image decoding separately from MIME.
- The generic asset contract accepts opaque bytes up to 25 MiB. A new image-only
  surface must not claim a valid PNG/JPEG/WebP from the filename alone. Reuse
  [media_files](app/media_files.py) validation where appropriate.
- Export reads verified original bytes through the same owner. A file extension
  change is not transcoding. Store only privacy-safe export evidence; no public
  absolute local paths, credentials or private user media.

### 3.3 Cross-entry fail-closed requirements

Filtering only a new Creative API is insufficient: legacy `/assets` downloads,
trash/restore, derivatives, embedded references, export and media consumers also
reach the same asset owner. New V2 origin constraints must be enforced centrally.

- `_in_scope` / `get` / `list` are the existing common visibility seam. New bound
  records must compare current server-owned incarnation and exact branch even
  when a legacy caller supplies `None`; old unbound records retain old semantics.
- Every mutation and content response rechecks current owner, flag and permission.
  Derived assets inherit restrictive origins rather than laundering a disabled
  V2 source into an unguarded V1 output.
- A deleted/recreated same-slug project cannot recover old V2 assets. Missing,
  malformed or mismatched binding fails closed. A newly created File marker is
  not retrospective proof that historical assets belong to it.
- Do not silently adopt old unbound V2 data. Existing pre-incarnation Creative
  rows remain preserved and inaccessible pending a separately evidenced repair.
- Review lock order before implementation: CreativeStore currently uses scope →
  project owner; AssetLibrary holds its lock across lineage guards. Adding an
  owner lookup while already holding the asset lock must not introduce an
  opposing owner → asset / asset → owner deadlock. PostgreSQL and File need the
  same externally observable delete/write isolation, not an invented distributed
  atomicity claim.

### 3.4 Minimum verification before calling M1 complete

Real File and PostgreSQL cases plus UI/API evidence must cover no-chapter create,
import, malformed file, exact download digest, reload/restart, CAS conflict,
idempotent retry, ambiguous write, duplicate titles, same-slug recreation,
read-only actor, branch mismatch, revoke during await, late response, feature-off,
V1 acceptance mode, indirect old endpoints, delete/restore and source integrity.
Intent switching must preserve assets and permission. No model or paid request
is needed. Existing V1/Interop contracts remain in the applicable regression set.

## 4. Storage plan and boundaries

| Category | Current owner / fact | Extension requirement |
|---|---|---|
| App / managed runtime | Packaged paths separate application and runtime from durable user data | Keep installers and uninstall roots separate from model directories. |
| Models | ModelCenter runtime config and discovery reference configured paths | Do not copy weights to claim registration; deduplicate observations, not files. |
| Project / assets | Existing repository + asset root + scoped metadata | Neutral project accounting may reference these; no second physical store. |
| Cache / proxy | Packaged cache and portable reproducible export archives | Add bounded proxy/thumbnail categories and quotas with accurate accounting. |
| Temp / tests | Service-owned temporary directories / owned test fixtures | Clean only owned paths after preserving evidence; interrupted recovery data is not disposable cache. |
| Export | Existing download/export owner and user-chosen destination | Explicit output selection; no blind overwrite, path traversal or model inclusion. |

Remaining general Storage Manager work includes free-space estimates, task
admission/pause on low disk, quota enforcement, per-project media accounting,
verified directory migration, reference remapping and interrupted-migration
recovery. Existing `PortableProjectsService.cleanup` must not be broadened into
filesystem deletion without reviewed invariants and exact tests.

## 5. Migration and rollback contract

1. **M0 has no migration.** Only these inventory documents are added. No schema,
   runtime config, database, user data, package or frozen manifest is rewritten.
2. Before M1 runtime changes, use an isolated experimental data profile and the
   existing backup/export authority. Do not point tests at user/V1 data.
3. Add optional metadata to new V2 records or bounded extension collections.
   Retain legacy missing-field semantics. If SQL is genuinely required, add a
   new migration; do not edit an already applied one.
4. Keep project UUID/incarnation and immutable source versions in provenance.
   Never infer historical ownership from a title or current scope hash. An
   ownership repair needs explicit evidence, preview, scoped authorization,
   audit receipt and rollback; no automatic rebind is supplied by M0.
5. Feature-off rollback preserves new records, suppresses new surfaces and
   indirect origin-constrained reads, and never replays a job. `V1_ACCEPTANCE_MODE`
   remains an absolute server override.
6. **Binary compatibility is not guaranteed by code rollback.** An old binary
   that predates a new asset-origin fence might ignore it. Never open a new V2
   profile in that binary merely because fields are additive. Use the separately
   preserved V1 profile, or a verified backup restored as an explicit operation.
7. New editable records remain read-only/hidden to versions that cannot preserve
   their fields. Export forward metadata before an authorized migration/removal.
   No rollback deletes files, tables or model weights automatically.
8. Test upgrade, disable/re-enable, interrupted write, corrupt marker, same-slug
   replacement, File/PostgreSQL parity and owner-level reads. Final Windows
   install/upgrade/uninstall and power-loss behavior remain `LOCAL_REQUIRED`.

## 6. Model, execution and Tutor contracts to retain

- Detection, metadata inspection, verified runtime, enablement, real generation
  and human quality assessment are separate evidence levels. A family name or
  service HTTP response is not proof of an executable workflow.
- Current discovery is bounded and host-local. Cloud hardware or localhost is
  never the user's Windows machine. Custom ports require trusted configuration,
  not unrestricted scanning.
- Existing Broker preview/admission and JobManager guards own dispatch.
  Cancellation requested is not proof a paid upstream call stopped; unknown
  results require receipt/accounting reconciliation and no automatic replay.
- White/gray-model screenshot, previs video and real 3D scene/camera are distinct
  inputs. Current providers cannot be advertised as supporting all three merely
  because a model family is listed.
- `poemseed.creative.studio` and `poemseed.tutor.desktop`, protocol
  `PoemSeed Local Interop` version `1.0`, stay stable. Observer/Advisor/Tutor has
  no control role. Connection, one-shot content consent and standing events are
  different grants. Restart, revoke, disable or scope change invalidates them.
- A future dockable/floating Tutor slot consumes the existing bridge; graph/asset
  context needs a versioned, minimized projection. The absence of QingJian never
  blocks editing. Real two-app identity/native integration is `LOCAL_REQUIRED`.

## 7. Frozen baseline and CI interpretation

The complete exact-source CI ledger, hashes, prohibited changes and next-stage
gates are in [MILESTONE_M0_REPORT.md](MILESTONE_M0_REPORT.md). PR success does not
replace push coverage: File hit its existing 20-minute cap and PostgreSQL shard
0 hit its 55-minute cap. Both push aggregates correctly rejected incomplete
execution; join/reconciliation were not reached. No rerun-to-green is evidence
that the capacity issue has been fixed.

The user's staged authorization permits a serialized, owner-preserving M1
implementation using the above seams. M0 does not approve merge, release, deployment, paid APIs,
Windows access, protocol expansion or protected shell redesign.

## 8. M1 as-built delta — 2026-10-09 13:00 UTC

**M1 PARTIAL.** Sections above remain the M0 inventory at `4350a61`; this is an
append-only description of the subsequent implementation. Its documentation
baseline is `0df2640c4c1a2d3052bb0a84d14445744d04046f`; M1 end commit/tree and
published [PR 47](https://github.com/1785235376-blip/AI-Novel-Studio/pull/47)
execution receipt are still pending. [M1 report](MILESTONE_M1_REPORT.md) §§9–10
bind the following contracts to actual local evidence and retain earlier failures.

| Implemented adapter / consumer | Original authority and current boundary |
| --- | --- |
| `app/creative/workspace_api.py`, `workspace_models.py`, `workspace.py` | Blank creation delegates to the original project owner; explicit `NEUTRAL_STUDIO` activation and bounded multi-intent/custom/preset preferences reuse original creative scope storage. Server actor/scope/incarnation and V2/V1 gates determine authority. Preferences grant no permissions, hide no modules and run no tasks. |
| `CreativeProjectStore.owner_lease` and `AssetLibraryService.project_scope` | New binary records bind to the original project incarnation and exact branch/scope. The original asset service owns UUID, bytes, SHA256, metadata versions, recoverable deletion and lineage. Legacy paths cannot bypass the bound scope; old unbound records are not silently adopted. No second asset registry or project database exists. |
| Manual image/video/audio import and download | Actual media decoding precedes persistence. Bounded limits: 25 MiB/asset, 1,000 assets and 512 MiB recorded bytes including trash per scope. Import and `EXTERNAL_IMPORT` declaration are separate writes with declaration-only retry. Download returns verified original bytes, not a format conversion. No chapter, model or relationship is required. Generated-job asset adoption is a later adapter. |
| `app/creative/workspace_relationships.py` | Seven optional declarations use reserved versioned original asset metadata; target ASSET/CHAPTER/SCREENPLAY uses original owners. Chapter/Screenplay bridge is typed, read-only and digest/version bound; it does not duplicate prose. CAS, review permission for `APPROVED_FOR`, redaction, stale/deleted states, tombstones and original-lineage constraints remain authoritative. Projection is explicitly nonexecutable, not a new knowledge graph or workflow scheduler. |
| `app/creative/storage_admission.py` | Measures the existing asset filesystem, subtracts a 64 MiB safety reserve and intersects project quota for import admission; low/unavailable capacity fails safely. Descriptive owner categories expose no client-controlled paths, model scan, automatic cleanup or migration. Existing packaging path and portable-cache owners remain unchanged. |
| `BlankProjectEntry`, `IndependentStudioWorkspace`, `AssetRelationshipsPanel`, Studio client and original asset components | One shared shell and original asset list/inspector/lineage forms. Explicit current server receipt selects the neutral noun; legacy/default rendering stays novel. Authority-scoped async readers, current selection/draft fences, reviewer-only state, admission states and saved-preference wording have unit coverage. Real browser/geometry/visual acceptance is pending. |

### 8.1 Verified evidence and remaining architecture work

Selected original-owner regressions pass separately: File **1,047 / 954 skips**;
real PostgreSQL 17.11 **1,011 / 987 skips**, with matching normal shutdown.
Corrected full frontend is **1,773 passed / 8 existing skips**; corrected
TypeScript/Vite/43-file token guard passes. Catalog consistency is **3 passed**;
current mounted surface is **2,077 operations**, **34 added / 0 removed** relative
to the M0 baseline. These are bounded, source-fingerprinted results, not full
hosted CI, browser evidence or full M1 completion. Collection inventory preserves
all 9,151 original nodes in order and historical skips; inventory is not execution.

The architectural gap remains a **full Storage Manager**: configurable separated
roots/default export path, complete occupancy, cache/proxy limits, general
preview-confirm cleanup, verified reference/copy relocation with journal/recovery,
and running-job low-space pause/resume are absent or partial. The admission
adapter must not be expanded into an unreviewed filesystem owner or used to claim
those guarantees. Existing portable-export-cache cleanup remains its narrow
bounded capability. Presets currently save metadata; applied layouts and editable
suggested graphs are still missing.

Safe nondependent M2/M3 work can extend original Workflow/Job/Model owners using
these bounded contracts. Operations requiring missing migration, cleanup,
reservation or running-job pause guarantees remain blocked on those contracts.
Independent image/video browser acceptance and final publication/CI still need
exact receipts. No mandatory novel pipeline, automatic graph execution, model
launch, paid fallback, Tutor control, real NLE or user-Windows authority follows
from this checkpoint. Historical classifications and M12 approval gate remain
unchanged.

## 9. Final M1 metadata-boundary update

The final V2 `IndependentWorkspaceService._row` now admits only actual positive
integer asset revisions (`type(version) is int`, at least 1). It rejects corrupt
or coerced counters with `CREATIVE_ASSET_VERSION_INVALID` without mutating the
original files or changing the permissive legacy asset owner. The seven-value,
both-profile regression is preserved as RED before the correction. See
[M1 report §11](MILESTONE_M1_REPORT.md#11-final-metadata-guard-delta-and-bounded-m1-closure).

Final focused File and real PostgreSQL 17.11 checks each pass **215 / 186
opposite-profile skips**, with identical unchanged-source maps and normal PG
shutdown. The earlier larger owner regressions, frontend and build results in §8
remain bound to their **pre-final-guard snapshots**; no current-tree full
regression verdict follows. Final catalog generation still has **2,077 operations,
+34/−0**, backend fingerprint
`a06abe220e300bad702981085001c7bd0259ba6d81a519bb3f855c1f8db56292`.
Final catalog check is **3 passed**, coverage infrastructure **174 passed**.
Actual final collection is **9,823 nodes, INVENTORY_ONLY**, with original 9,151
ordered nodes and historical skips retained. Written manifest SHA256:
`3e86bfabbdcb2c494968cf89d6efdd3ff2cc10edf921fa47f6a9669474dfce9f`.

M1 is **PARTIAL / bounded minimum-path closure**. Browser acceptance is **BLOCKED
locally / NOT_RUN on hosted current M1**, with no new visual PASS. Full migration,
cache cleanup/limits, global reservation/job pause and applied presets remain
missing or partial and block dependent behavior. Safe nondependent M2/M3 may
continue. Final publication SHA/tree remains unrecorded; M12 approval is unchanged.

The preserved prior local Chromium launch is blocked by `socket() Operation not
permitted` / `SIGABRT`; no new M1 browser attempt occurred. Exact M0 terminal
receipt is [recorded separately](docs/delivery/v2-development/m0-ci-terminal.json):
push Cloud **FAILURE**, PR Cloud **CANCELLED**, both PR strict aggregates failed
despite successful PG shard execution. Neither is current-M1 hosted evidence.

## 10. M2-A in-progress graph delta — 2026-10-09 13:50 UTC

**M2 PARTIAL.** Published M1 baseline is
`57986cb13d452731baf82bbc242bfc79f9cfd145`; M2 end SHA/tree is uncommitted and
unrecorded. Earlier M0/M1 sections remain historical. The
[M2 report](MILESTONE_M2_REPORT.md) records source contracts, development receipts,
full-roadmap gaps and the distinct M1 hosted compatibility correction.

- `graph_models.py` supplies seven closed versioned node definitions and four
  current port types, strict schemas/edge validation and original DAG ordering.
  Empty independent graphs can persist without chapter/Director/model.
- `graph.py` uses original `CreativeProjectStore` collections for actor-private,
  exact-scope/incarnation definitions/runs; CAS, request identity, digest validation
  and final authorization checks remain mandatory. It creates no project/asset DB.
- `graph_execution.py` drives `_ScopedOriginalWorkflowHost` trigger/claim/complete
  and review transitions through a trusted local adapter. Text/manual/rule outputs
  do not invoke JobManager/providers or models, publish assets or overwrite prose.
  Preflight admission and exact output review are separate explicit actions.
- Original WorkflowRun default **3,600-second admission deadline** is retained
  through queued execution/pause/resume/review; node budget is **5 seconds**.
  Application timeouts are unrelated to unchanged CI budgets. Frontend currently
  parses/displays timing fields; final integrated verification is pending.
- Bounds: **16 nodes / 40 edges / 96,000 definition bytes / 64,000 output bytes**,
  **25 graphs / 100 runs / 20 history entries**; bytes are decimal. No general
  Storage Manager or scalable graph resource scheduler is implied.
- Cache is same-graph-version, same actor/scope/incarnation, digest-verified local
  output from successful reviewed ancestors only. Approval is never cached;
  cross-version descendant-only invalidation and binary cache are absent.
- `asset_reference` is read-only metadata with original-owner current/stale/hidden
  projection. It is **not** an AssetLibrary parent/provenance/dependency edge;
  original delete/restore may make it unavailable. Saved references cannot yet
  detach/rebind; selected execution is blocked pending an atomic original-owner
  input adapter. M1 relationship deletion guards do not automatically cover it.
- Optional canvas/run/inspector consumers use the existing Studio shell. Real
  positioned nodes, pointer/keyboard movement, pan/zoom and form-based typed
  connections exist; persistent draft autosave, drag-connect, templates, MiniMap,
  professional Director/Tutor and large-graph acceptance remain missing/partial.

Development deadline suite is **257 passed / 44 PG variants deselected**;
first mounted API **16 passed / 16 skipped** predates later auth cases. Earlier
241-pass run explicitly recorded source drift. Final File/actual-PG/full frontend,
build and hosted/browser results remain pending; no M2 visual PASS or final SHA.
Full M2's image generation/material conversion/JobManager/model gate remains open.
M1 storage/preset gaps continue to block dependent work and M12 remains gated.

### 10.1 Later terminal checks, 13:55 UTC

Source-stable, agreeing 1,660-input receipts now establish full frontend **1,923
passed / 8 existing skips**, TypeScript/Vite/43-file token **PASS**, and complete
CI infrastructure/catalog **279 passed** (276 infrastructure, including original
102 TCP checks, plus 3 catalog). Catalog is **2,107 operations, M2 +30/−0**.
Independent collection is **10,178 nodes, INVENTORY_ONLY**, original 9,151 order
and historical skips retained; written manifest and integrated File/actual PG
remain pending. [M2 report §7](MILESTONE_M2_REPORT.md#7-integrated-checkpoint-receipts--2026-10-09-1355-utc)
retains exact source identity. No browser/visual, full M2 gate or published end SHA
is inferred from these checks.

### 10.2 Integrated File update, 13:59 UTC

[Original-owner File](docs/delivery/v2-development/stage-m2-integrated-owner-file.json)
finished **PASS: 1,490 passed / 1,098 skipped**, 299.01 seconds. It selects 33
original-owner/M1/M2/media-contract files; it is not the full backend manifest.
The stable 1,660-input map matches frontend/build/279-check evidence. Real PG
remains pending; no profile combination, browser PASS or full M2 completion is
inferred. Exact log/source binding is in [M2 report](MILESTONE_M2_REPORT.md).

### 10.3 Written inventory update, 14:01 UTC

[Manifest review](docs/delivery/v2-development/stage-m2-manifest-change-review.json)
and [independent recollection/write](docs/delivery/v2-development/stage-m2-manifest-written.json)
verify **10,178 nodes = M1 9,823 + 355**, preserved old order/skips/external gates,
and actual manifest SHA256
`acefe60873bd452ff663b254cb4c25a910c99dcb140732171105b7ba0b687d62`.
The frozen manifest remains unchanged. [Actual browser collection](docs/delivery/v2-development/m2-browser-inventory-review.json)
retains all prior 12 cases: **7 original + 8 independent (5 M1 + 3 M2)**, no overlap.
Both are **inventory only**; no browser launched or full backend execution inferred.
Real PG completion remains pending at this observation.

### 10.4 Final local M2-A checkpoint, 14:07 UTC

Actual PostgreSQL 17.11 is now **PASS: 1,457 passed / 1,131 skipped**, 830.19 s,
with matching normal shutdown. Its stable 1,660-input map agrees with File
**1,490/1,098**, frontend **1,923/8**, build/token and **279** infrastructure/catalog
checks. Earlier pending observations are historical; exact final evidence is in
[M2 report §7.5](MILESTONE_M2_REPORT.md#75-integrated-postgresql-and-final-local-checkpoint-1407-utc).
These are selected local checks, not full hosted backend/browser acceptance.
M2 remains PARTIAL; missing execution adapters, full canvas/Tutor and M1 storage
semantics remain explicit. Final published SHA will be bound through PR47 after
commit; no source-independent end SHA, Windows result or visual PASS is claimed.

## 11. Append-only M3-A host discovery/consent development delta

**2026-10-09 14:44 UTC; M3 PARTIAL, source not frozen.** Published parent is
`99c43b6892038233c390be2ae61acb669163d0b5`, tree
`69d69ffe71838263069d164a0a07b39b5f4a4333`. This supplements the preserved M0/M1/M2
architecture, not its historical source identity. [M3 report](MILESTONE_M3_REPORT.md)
records the detailed contract, exact bounds, receipt links and remaining gates.

- `main.py` mounts the existing discovery router with new, separate current Host
  authority on **every production discovery route and both API prefixes, even
  with V2 off**. Cached host paths remain private. Packaged bootstrap/live-session
  provenance or local-only direct-loopback/existing credential is required;
  ordinary nonpackaged collaboration roles and forwarded claims do not suffice.
  The legitimate shared Model Center collaboration helper is unchanged. This is
  an intentional security-tightening compatibility change, not preserved access
  for all former discovery callers.
- The original trusted-session registry supplies a binding generation to fence
  same-token reincarnation. Guards run before/after work/response and at original
  persistence/late-metadata-adoption checkpoints. No parallel credentials, Vault,
  persistent ACL or authorization grant comes from a scope digest.
- `discovery_scope.py` and `discovery_onboarding_types.py` define a closed V2
  preview/confirmation contract over `LocalDiscoveryService`: explicit common
  roots default false; 16 ephemeral receipts with 120-second TTL, bound to host
  principal, service instance, nonce and full effective plan. Confirmation uses
  the original worker, deadline and cancel/status owner. V2 legacy HTTP scan
  cannot bypass the new consent; original direct-service test/embedding seam is
  preserved separately.
- Planning discloses configured and registered GGUF headers, executable metadata
  and approved recursive roots, not just directory roots. Existing stale
  registration/route disabling and safety persistence are declared effects.
  There is no automatic register/enable/runtime launch/weight load/cloud call.
- Frozen scope/cancellation guards flow through bounded probe and metadata reads.
  Supported POSIX descriptor traversal is no-follow; Windows pathname/reparse
  checks are **not equivalent atomic ancestor protection**. Platform acceptance,
  inference and complete model-component validation remain unproved here.
- Captured frontend owner/client state protects V2 Model Center and environment
  summary reads, previews and asynchronous results. Existing ModelCenter,
  RuntimeRegistry/bridge, Broker/Vault and JobManager ownership remains intact.

Development logs retain the real first cache-leak and legacy cancellation
failures and later passing snapshots; source maps differ and tests overlap.
Final integrated File/real-PG/frontend/build/catalog/manifest evidence is pending.
No final M3 SHA, browser/visual approval, full M3 or user Windows PASS is asserted.

### 11.1 Planning hardening, 14:55 UTC

M3 scope planning/replanning now has a **5-second cooperative budget** exposed as
`limits.planning_budget_seconds`, checks between each runtime/root/registered-file
metadata operation, and existing-owner lock waits in **at most 50-ms** intervals.
Revocation/planning expiry stops before new preview issuance or scan admission;
`LOCAL_AI_SCOPE_BUDGET_REACHED` identifies budget exhaustion. In-flight OS calls
are not forcibly interrupted. The original 45-second scan budget and 120-second
TTL remain unchanged. [M3 report §8](MILESTONE_M3_REPORT.md#8-append-only-planning-hardening-update--2026-10-09-1455-utc)
records the **224-pass** development run and its explicit unrelated browser-fixture
source drift; final freeze/integration and browser execution remain pending.

### 11.2 Frozen-source local checkpoint, 15:05 UTC

Source frozen at 15:01 UTC has **1,676 inputs**, map fingerprint
`aefdbfd9884879ab2e17b42754c8ae7cbb6ecd54de4b8e192c9b158e6fe22259`.
Matching stable receipts now establish full frontend **1,981 PASS / 8 existing
skips**, TypeScript/Vite/45-file token **PASS**, and infrastructure/catalog **279
PASS**. Catalog is **2,111 operations, M3 +4/−0**, with current discovery-authority
annotations corrected without rewriting other owners; its regression is **3 PASS**.
The written **10,335-node** inventory preserves old order/test/gate/skip contracts;
actual browser collection is **7 original + 11 independent**, inventory only.
[M3 report §9](MILESTONE_M3_REPORT.md#9-source-freeze-and-terminal-local-checks--2026-10-09-1505-utc)
binds hashes, generation tree and receipt levels. Selected 52-file File/real-PG
integration is still pending; no published M3 SHA, browser or full M3 PASS follows.

### 11.3 Integrated File update, 15:08 UTC

[52-file original-owner File integration](docs/delivery/v2-development/stage-m3-integrated-owner-file.json)
is now **2,082 PASS / 1,099 skips**, 310.49 s, with the same stable 1,676-input map.
Skips preserve 1,098 opposite-profile cases plus one existing real-Windows native
acceptance case. This is selected owner integration, not the full 10,335-node
manifest or actual Windows proof. Real PG remains pending; exact log/source
binding is in [M3 report §9.5](MILESTONE_M3_REPORT.md#95-integrated-file-result-1508-utc).

### 11.4 First PG failure and published-M2 terminal record, 15:20 UTC

The first M3 real-PG owner selection finished **FAIL: 2 failed / 2,047 passed /
1,132 skipped**, 811.97 s, on the same stable 1,676-input map. Both unchanged
`test_r2_workflow_execution.py` API-owner tests encountered missing `id` after a
novel-create response; cause is not established by the log alone. Real PG 17.11 SQL
is verified; normal-stop evidence and diagnosis remain pending. The evidence-read
transport disconnect recovered on the same executor without restarting this run.
[M3 report §§10–11](MILESTONE_M3_REPORT.md#10-terminal-published-m2-hosted-record--2026-10-09-1520-utc)
also records all published-M2 workflows terminal: both Cloud events FAIL, File
cancelled/incomplete and PG execution successful but strict aggregates FAIL.
Neither historical hosted success subsets nor current File/UI passes erase the
failed M3 PG attempt. Full M3 remains PARTIAL.

### 11.5 Confirmed PG harness isolation issue, 15:24 UTC

The two first-PG failures are now traced to reused test data: SQL shows both
fixed-title rows created at 14:04:35 UTC during M2; the unchanged original API
correctly returns 409. The first diagnostic's unused-import failure is retained,
and the corrected diagnostic proves the conflict. Normal original-run shutdown
is verified at 15:15:57 UTC. [M3 report §11.1](MILESTONE_M3_REPORT.md#111-confirmed-reused-database-cause-and-normal-shutdown-1524-utc)
records hashes and exact evidence. A narrow runner-only fresh-database mode and
new isolation tests are being prepared, preserving existing data and original
assertions/titles. New source freeze and complete selected checks are required;
the first failed run and prior 1,676-input results remain historical, not rewritten.

### 11.6 Fresh-source File and local-check checkpoint, 15:42 UTC

After the runner-only fresh-database correction, current receipts bind **1,677
inputs**, map SHA256
`964ad4a0c317f43d65e2aa8793d6f87b5e6630b977ee269803c42c6248fd143f`.
The **complete selected 53-file File owner range** is **2,109 PASS / 1,099 skips**,
317.00 s; it is not all **10,362** product nodes. Freshly rerun frontend is
**1,981 PASS / 8 existing skips**, build/45-file token PASS, infrastructure/catalog
**279 PASS** and browser collection **7 original + 11 independent, inventory only**.
All these maps and logs were verified, rather than borrowing initial-source runs.

Fresh smoke reruns the original two failed tests unchanged: **2 PASS**, with
actual PG 17.11 database OID 31259, empty-before-migration proof, all 20 original
SQL files, normal stop and retained data. Runner/helper regressions are **32 PASS**;
the first integration failure remains preserved. New written inventory is
**10,362 = 10,335 + 27**, SHA256
`bc15318b92cae0ee7a3c581321de95f3577c684b0ced26daf9f7228ccda57715`,
with old tests/gates/order/skips intact. Catalog stays **2,111 operations (+4/−0)**
and application source is unchanged. Exact fresh receipt/source/log hashes are in
[M3 report §12](MILESTONE_M3_REPORT.md#12-fresh-database-correction-and-current-source-checks--1542-utc).
The complete fresh PG owner run is still pending. M3 stays PARTIAL; full-product
hosted CI awaits publication, and browser/user-Windows/inference proof is separate.

### 11.7 Final local M3-A checkpoint, 15:47 UTC

The fresh real PostgreSQL 17.11 run is now **PASS: 2,076 passed / 1,132 skipped**,
831.24 s, with the same stable **1,677-input** map as File **2,109/1,099**, full
frontend **1,981/8**, passing build/45-file token and **279** infrastructure/catalog
checks. Actual fresh DB OID **32129**, empty-before-migration proof, all 20 original
SQL hashes, retained data and normal shutdown at 15:45:46 UTC were verified.
[M3 report §13](MILESTONE_M3_REPORT.md#13-final-local-m3-a-checkpoint--1547-utc)
contains exact current receipts/log hashes and publication identity rules.

This completes the **selected 53-file owner range**, not full-product execution
of all **10,362** manifest nodes. Catalog 2,111 (+4/−0), written manifest and 7+11
browser collection retain their separate inventory level. Earlier failed attempts,
including the diagnosed reused-database run and M2 hosted failures, remain intact.
M3-A is a publishable **PARTIAL** checkpoint. Exact end SHA/tree will be bound via
PR 47's publication receipt, not self-embedded or replaced with the M2 parent.
New-SHA full-product hosted CI and M3 browser/visual results remain pending; actual
user Windows, real inference/quality and full M3 model/API gates remain open.

## 12. Append-only M3-B same-scan file projection

The [M3-B report](MILESTONE_M3B_REPORT.md#2-actual-bounded-implementation) records
an additive consumer of the original discovery scan: optional typed file/root
fields and `LocalAiModelFiles`, V2/schema-2 gated, with 20-item local pages over
the original bounded result. Exact same-scan candidate IDs and existing registry
IDs bind displayed associations; names and paths grant no authority. Existing
host/session/project/epoch fencing remains in charge. No production backend API,
registry, filesystem read or scan is added. MODEL-06 content deduplication remains
partial. Source-bound evidence and hosted-parent separation are in that report;
this does not supersede earlier M3-A outcomes or complete full M3.

The later [M3-B correction](MILESTONE_M3B_REPORT.md#12-corrected-source-freeze-and-terminal-frontend-checks--1634-utc)
also reuses the original request-token policy and React owner for legacy
presentation, fencing epoch/ABA/late-body responses and purging cached private
forms on denial. Server authority, credential storage and protected App keys are
unchanged; the Agent selection fix binds display and mutation to the same role.

[Final M3-B verification](MILESTONE_M3B_REPORT.md#12-corrected-source-freeze-and-terminal-frontend-checks--1634-utc)
now binds the selected 56-file File/real-PG range to that corrected source, with
normal PG shutdown and original source/inventory contracts preserved. It is not
full-product or new-SHA hosted acceptance; M3 remains PARTIAL.

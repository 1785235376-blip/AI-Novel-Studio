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

# V2 Master Roadmap feature matrix

## Identity, vocabulary and evidence limits

**M0 source inventory, 2026-10-09.** Audited HEAD
`4350a61fb9f61acccb845fef96b24b9b1275bbd3`, tree
`a05d33f75c5af6f26171d6370c0efeb13a68619d` on
`feature/v2-narrative-platform`. Requirements are the user's fully read 904-line
V2 Master Roadmap and 28-line start instructions, supplied on 2026-10-09.
Section numbers below trace to that roadmap. This is a new current engineering
inventory, not a reopening/reclassification of the historical independent review.

- **EXISTS**: the precisely described bounded implementation exists in the
  audited source. It does not imply every broader Studio acceptance criterion.
- **PARTIAL**: a reusable implementation exists, but specified UX, coverage,
  semantics, integration or real execution evidence remains missing.
- **MISSING**: the requested contract/surface was not found in the audited owner
  and adjacent source. The evidence identifies the nearest extension seam.
- **BLOCKED**: dependent on unavailable authority, external product, risk decision
  or intentionally deferred scope; do not execute merely to improve the matrix.
- **LOCAL_REQUIRED**: target Windows/GPU/native/two-product acceptance cannot be
  substituted by cloud or mock results.

Evidence IDs link to code and representative tests in §30. A listed test is
**source evidence**, not an assertion that M0 ran it or that it proves the entire
row. M0 ran no product tests and made no runtime changes. Current historical
execution evidence is separately recorded in [M0 report](MILESTONE_M0_REPORT.md).
The exact 4350a61 PR suite succeeded, but push File/PG capacity cancellation keeps
overall CI **PARTIAL_CI_CAPACITY**. No cross-event stitching or rerun-to-green.
The original **39 PARTIAL + F00 INTEGRATED**, independent review **BLOCKED**, remain.

See [architecture](AI_NOVEL_STUDIO_V2_ARCHITECTURE.md) for the owner reuse map,
cross-entry security seam, migration and rollback. Rows remain bound to the M0
source even while a later stage is being implemented; later milestones must add
their exact-source evidence rather than retroactively turn this baseline green.

## 1–3. Product independence and core contracts

| ID / roadmap | Sub-capability | Status | Authoritative owner / evidence and exact remaining boundary |
|---|---|---|---|
| CORE-01 §1.1 | Single Studio open/create/save/export without mandatory upstream novel/chapter | PARTIAL | [E01], [E02], [E03]. Standalone creative documents and media primitives exist, but project/entry UX remains novel-oriented; neutral blank image path is M1. |
| CORE-02 §1.1 | Optional, removable/reorderable cross-module chain | PARTIAL | [E04], [E05]. Derivations and bounded workflows exist; general typed cross-module connections do not. |
| CORE-03 §1.2 | Mutable multiple CreativeIntent values; skip/customize/change intent | MISSING | [E01], [E06]. First-use is a novel sample flow; no neutral intent preference contract. |
| CORE-04 §1.2 | Editable workspace preset, empty graph, no automatic execution or permission restriction | MISSING | [E05], [E06]. Recipes/templates exist; free intent-to-layout mapping remains to be implemented. |
| CORE-05 §1.2 | On-demand workspaces and model/executor loading | PARTIAL | [E07], [E08]. Existing capability gating and discovery launch-on-demand; not all requested Studio surfaces exist. |
| CORE-06 §1.3 | Ordinary forms/task cards and professional graph share assets/routes/jobs | PARTIAL | [E03], [E05], [E08]. Original owners exist; common professional typed graph is missing. |
| CORE-07 §1.3 | Preview/edit/reject AI workflow suggestions before execution | PARTIAL | [E05], [E09]. Reviewed proposals exist; generalized graph-proposal review not implemented. |
| CORE-08 §3.1 | Project identity, owner/scope, lifecycle, authorization | EXISTS | [E01], [E02]. Original repository and current-incarnation guard; no new project registry is needed. |
| CORE-09 §3.1 | Project asset root, default export directory, preference metadata/version | PARTIAL | [E01], [E10]. Original roots/export owners exist; neutral user-configurable per-project metadata remains. |
| CORE-10 §3.1 | Compatible reversible bridge to Novel Project | PARTIAL | [E01], [E02]. Existing repositories preserve novel data; neutral adapter/upgrade evidence is M1. |
| CORE-11 §3.2 | Stable asset ID, kind, MIME, size, SHA256, timestamps, metadata revision | EXISTS | [E03]. AssetLibraryService owns bytes and metadata; generic declared MIME alone is not media validity. |
| CORE-12 §3.2 | Unified source_kind/provider/model/parameters/review/license metadata | PARTIAL | [E03], [E04]. Fields/provenance exist across asset/media owners; independent V2 index projection and complete field parity remain. |
| CORE-13 §3.2 | Independent image/audio/video import and saved-byte export | PARTIAL | [E03], [E11]. Asset primitives accept these, but neutral no-chapter UI/lifecycle path is not yet proven. |
| CORE-14 §3.2 | 3D/reference model/white-model screenshot/previs imports with distinct typed semantics | MISSING | [E03], [E11]. Opaque file upload is not a 3D or reference-condition contract. |
| CORE-15 §3.2 | Chapter/Version remains prose owner, asset index references only | EXISTS | [E01], [E02], [E04]. Existing creative source evidence references rather than overwrites source chapters. |
| CORE-16 §3.2 | Exact source version/digest, stale detection, immutable old result | PARTIAL | [E02], [E04]. Implemented for covered creative/media lineage; not every future asset kind. |
| CORE-17 §3.2 | Trash/restore, dependency display, retention-authorized physical cleanup | PARTIAL | [E03], [E10]. Recoverable binary deletion/reference queries exist; comprehensive dependency-protected cleanup is not a general manager. |
| CORE-18 §3.2 | New V2 binary assets protected against slug reuse through all entry points | MISSING | [E02], [E03]. Creative documents are incarnation-bound; AssetLibrary binary records currently lack that binding. M1 must fence the original owner. |
| CORE-19 §3.2 | Redacted metadata exports without credentials or absolute paths | PARTIAL | [E04], [E10], [E12]. Existing allowlists exist; new neutral asset/export projection requires its own regression. |
| CORE-20 §3.3 | SOURCE_OF / DERIVED_FROM / REFERENCES / USED_IN / ALTERNATE_VERSION / APPROVED_FOR / LINKED_CONTEXT | PARTIAL | [E04]. Existing parent DAG and provenance cover derivation; full named relation taxonomy/reason/status is not implemented. |
| CORE-21 §3.3 | Relation scope, actor, exact target version/hash; no cross-project edge | PARTIAL | [E03], [E04]. Existing lineage captures measured parents and scope; general typed relations remain. |
| CORE-22 §3.4 | Graph ID/version/snapshot and node/edge persistence | PARTIAL | [E05]. Existing bounded DAG snapshots; complete creative graph geometry/draft contract missing. |
| CORE-23 §3.4 | NodeDefinition version, typed ports, capabilities, validation, resource/cost estimate | PARTIAL | [E05], [E08]. Restricted declarative schemas/capability metadata exist; media typed-port registry missing. |
| CORE-24 §3.4 | NodeInstance parameters, input bindings, independent enablement, cache/execution history | PARTIAL | [E05]. Config and run/node state exist; reusable creative cache/typed bindings missing. |
| CORE-25 §3.4 | Edge port/type/format/version constraints and explicit conversions | MISSING | [E05]. Current edges are source/target IDs; no general media port contract. |
| CORE-26 §3.4 | Cycle rejection and bounded execution | EXISTS | [E05]. Original topological validation rejects cycles; bounded step/time execution. No implicit loop support. |
| CORE-27 §3.4 | Node removal preserves approved assets; partial failure preserves truthful results | PARTIAL | [E03], [E05]. Separate asset/run owners exist; future graph deletion/recovery semantics require tests. |
| CORE-28 §3.5 | Draft/ready/queued/preparing/running/review/complete/fail/cancel/block/unknown projection | PARTIAL | [E08], [E11], [E13]. Existing states differ by owner; unify truthful projection, not a second state machine. |
| CORE-29 §3.5 | Execution receipt actor, exact inputs, route/model, authority, time/resource/cost/digest/error | PARTIAL | [E08], [E09], [E11]. Several original receipts carry these; missing observations stay unknown. |
| CORE-30 §3.5 | Cancel-request versus upstream cancellation; no replay of unknown billing | EXISTS | [E08], [E09]. Existing broker/admission/creative unknown-result fences are reusable. Real paid reconciliation is not tested here. |
| CORE-31 §3.5 | Idempotent retry and original/new-task linkage | PARTIAL | [E05], [E08], [E13]. Implemented per owner; not universal graph retry/cache semantics. |
| CORE-32 §3.5 | One cross-module orchestration authority reusing original jobs | PARTIAL | [E05], [E08], [E11], [E13]. Original author/media/workflow owners coexist; no new parallel queue is justified. |

## 4–5. Startup, project entry and storage

| ID / roadmap | Sub-capability | Status | Owner / evidence and remaining boundary |
|---|---|---|---|
| START-01 §4.1 | First-run language, safe storage defaults and optional advanced setup | PARTIAL | [E06], [E10]. Existing onboarding/packaged paths; unified language/storage first-run experience incomplete. |
| START-02 §4.1 | Explicitly authorized bounded Windows/service/model-directory scan | PARTIAL | [E07]. Code and fixture tests exist; actual Windows observation is LOCAL_REQUIRED. |
| START-03 §4.1 | Distinguish discovered file, advertised model, validated runtime and inference | EXISTS | [E07], [E08]. Source separates stages; no real-generation claim follows from discovery. |
| START-04 §4.1 | Trusted running-service connection suggestions without routine port entry | PARTIAL | [E07]. Known endpoints/trusted configuration supported; arbitrary nondefault-service discovery not guaranteed. |
| START-05 §4.1 | Reuse first; missing-capability install/API suggestions | PARTIAL | [E07], [E08]. Diagnostics exist; complete needs-driven install/size/license comparison remains. |
| START-06 §4.1 | Skip model installation and edit/import/export offline | PARTIAL | [E01], [E03], [E06]. Manual core works; neutral independent Studio onboarding requires M1+. |
| START-07 §4.2 | Per-project intention/preset/capability entry without rescanning machine | MISSING | [E06], [E07]. Scan is explicitly initiated, but new independent project wizard/preferences missing. |
| START-08 §4.2 | Enter chosen Studio; all others remain available; change intent | MISSING | [E01], [E06]. No intent-based policy exists; requested neutral navigation still missing. |
| START-09 §4.2 | Select project/asset/cache locations and optional immediate import | PARTIAL | [E03], [E10]. Paths/import primitives exist; project-level setup/relocation UX incomplete. |
| STORE-01 §5 | Separate app/runtime, models, project/assets, cache/proxy, temp/test and export | PARTIAL | [E07], [E10]. Existing packaging separation; complete user-selected category policy missing. |
| STORE-02 §5 | Reference existing model locations without copying/deleting weights | EXISTS | [E07]. Discovery/registry use configured paths and do not install weights. |
| STORE-03 §5 | Per-project measured occupancy | PARTIAL | [E10]. Portable storage reports authorized categories, not whole-disk/complete media occupancy. |
| STORE-04 §5 | Free space and task estimated space | MISSING | [E10], [E13]. General measured disk admission/estimation not found. |
| STORE-05 §5 | Cache limits and reclaim policy | PARTIAL | [E10]. Bounded archive/cache records exist; proxy/thumbnail quota service missing. |
| STORE-06 §5 | Cleanup list, exact preview digest and confirmation | EXISTS | [E10]. Only verified unused reproducible portable export cache; no general model/project deletion. |
| STORE-07 §5 | Verify directory-migration copies and remap references | PARTIAL | [E10], [E23]. Existing backup/portable relink patterns; full V2 directory migration absent. |
| STORE-08 §5 | Interrupted migration / crash recovery without user-data deletion | PARTIAL | [E02], [E10]. Atomic writes/recovery checkpoints exist; storage migration state machine not implemented. |
| STORE-09 §5 | Low-space pause/admission and resume | MISSING | [E10], [E13]. Not covered by generic task failure status. |
| STORE-10 §5 | High-volume media/model roots independent of install directory | PARTIAL | [E07], [E10]. Packaging safeguards exist; fully configurable per-category media policy missing. |

## 6. Model Center, download and optional API

| ID / roadmap | Sub-capability | Status | Owner / evidence and remaining boundary |
|---|---|---|---|
| MODEL-01 §6.1 | Reuse ModelCenter, Discovery, HardwareInventory, Runtime Registry and Broker | EXISTS | [E07], [E08]. These are actual owners, not proposed new services. |
| MODEL-02 §6.1 | Ollama / LM Studio / ComfyUI / llama.cpp trusted discovery | PARTIAL | [E07]. Bounded probes/bridges; each real user runtime still requires validation. |
| MODEL-03 §6.1 | Nondefault ports via trusted configuration, no LAN/public/unbounded probing | PARTIAL | [E07]. Configured runtime support; automatic enumeration coverage remains bounded. |
| MODEL-04 §6.1 | Authorized model roots; GGUF / Safetensors / Diffusers metadata | EXISTS | [E07]. Bounded parsing without loading model code/weights; not real inference. |
| MODEL-05 §6.1 | Format, component dependencies, model family and runtime compatibility | PARTIAL | [E07], [E11]. Metadata/probe checks exist; complete multimodal workflow component validation missing. |
| MODEL-06 §6.1 | Content deduplication across locations, retain all paths, no physical merge | PARTIAL | [E07]. Existing discovery identity/digest records; full cross-root content identity UX not established. |
| MODEL-07 §6.1 | Register disabled → explicit enable → launch on demand | EXISTS | [E07]. Existing separation and safe connection bridge; opening summary does not launch. |
| MODEL-08 §6.1 | Need-specific official source/license/size/hardware/install guidance | PARTIAL | [E07], [E08]. Diagnostics/catalogs are not a complete install recommendation workflow. |
| MODEL-09 §6.1 | DISCOVERED/INSPECTED/UNKNOWN/VERIFIED/DISABLED/ENABLED/READY/RUNNING/FAILED/STALE | PARTIAL | [E07], [E08]. Evidence distinctions exist; complete unified vocabulary/projection remains. |
| MODEL-10 §6.2 | TEXT for novel/screenplay/Agent and context/JSON constraints | PARTIAL | [E08], [E09]. Real text adapter route exists; Chinese/literary quality and memory benchmark LOCAL_REQUIRED. |
| MODEL-11 §6.2 | Embedding / reranker / OCR as optional capabilities | PARTIAL | [E19]. Embedding/vision extraction adapters exist; no promise all optional runtimes installed. |
| MODEL-12 §6.2 | IMAGE T2I/I2I/edit with VAE/encoder/LoRA/ControlNet dependency checks | PARTIAL | [E07], [E11]. Registered image paths exist; all component combinations not covered. |
| MODEL-13 §6.2 | VIDEO T2V/I2V/V2V/reference capability per model version | PARTIAL | [E11]. T2V/I2V operations/adapters exist; V2V/reference video is not a generic proven capability. |
| MODEL-14 §6.2 | AUDIO TTS/ASR/music/SFX evidence and sample-rate/duration limits | PARTIAL | [E11], [E16]. Separate contracts exist; supported execution depends on actual adapter. |
| MODEL-15 §6.2 | 3D generation/depth/pose adapters and model-free white-model import | MISSING | [E11]. No supported 3D parser/generation bridge found. |
| MODEL-16 §6.2 | FFmpeg versus AI interpolation/upscale capability distinction | EXISTS | [E11], [E17]. Processing families are not advertised as fabricated video generators. |
| MODEL-17 §6.2 | Dynamic quantization/workflow/peak-memory matching; low-resource alternative | PARTIAL | [E07], [E08]. Capacity/unknown evidence is preserved; actual peak-memory scheduler/benchmarks incomplete. |
| MODEL-18 §6.2 | 8 GB / 12 GB / RTX 5080 16 GB + 64 GB performance evidence | LOCAL_REQUIRED | [E07], [E08]. Cloud/mock evidence cannot validate these target devices. |
| MODEL-19 §6.3 | No duplicate download, user-selected existing/new model root | PARTIAL | [E07]. Current discovery does not download; complete managed download UI missing. |
| MODEL-20 §6.3 | Source/author/license/card/restrictions/size/platform/resource/checksum disclosure | PARTIAL | [E07], [E08]. Some catalog metadata; complete version-current download receipts missing. |
| MODEL-21 §6.3 | Chunked download, pause/resume, digest/signature verification, failure cleanup | MISSING | [E07]. No complete authorized model downloader was found. |
| MODEL-22 §6.3 | Unknown code, pickle/custom-node installer requires separate authorization | EXISTS | [E07], [E24]. Safe scanner does not execute code; plugin execution remains denied. |
| MODEL-23 §6.4 | Local-versus-API capability, estimated price and exact outbound data comparison | PARTIAL | [E08]. Broker preview exists; independent multimodal route UX/receipts incomplete. |
| MODEL-24 §6.4 | Independent Provider adapters, Vault, user routing, budget/price-version binding | EXISTS | [E08], [E11]. Existing bounded implementations; no need for another router/Vault. |
| MODEL-25 §6.4 | Explicit egress approval/revoke, async status/cancel, billing reconciliation | PARTIAL | [E08], [E11]. Existing guards/receipts; not every modality/provider has production proof. |
| MODEL-26 §6.4 | Actual paid-provider end-to-end proof or personal subscription usage | BLOCKED | [E08]. This engineering task does not authorize personal paid API calls. |

## 7–8. Shared Creative Graph and optional Director Console

| ID / roadmap | Sub-capability | Status | Owner / evidence and remaining boundary |
|---|---|---|---|
| GRAPH-01 §7.1 | Shared Image/Video/Audio/3D/Research DAG and ordinary/pro UI | PARTIAL | [E05], [E14]. Bounded workflow authority exists; common multimodal graph contract/renderer missing. |
| GRAPH-02 §7.2 | Pan/zoom, marquee/multiselect and draggable visual objects | PARTIAL | [E14]. Reference image board supports them; not executable graph node editing. |
| GRAPH-03 §7.2 | Drag-connect, typed-port highlighting, invalid-edge explanation/conversion | MISSING | [E05], [E14]. No typed media connection editor. |
| GRAPH-04 §7.2 | Context-menu and keyboard command search | PARTIAL | [E06], [E14]. Workspace search exists; node-specific quick insertion/search missing. |
| GRAPH-05 §7.2 | Undo/redo and copy/paste | PARTIAL | [E14]. Existing board undo/redo; graph-aware copy/paste and history not implemented. |
| GRAPH-06 §7.2 | Node grouping, annotations, collapse, MiniMap and alignment | PARTIAL | [E14]. Board grouping exists; full graph-specific set absent. |
| GRAPH-07 §7.2 | Keyboard node/port navigation and error location | MISSING | [E05], [E14]. Requires accessible graph semantics and focused regression. |
| GRAPH-08 §7.2 | Graph version, visible autosaved drafts and reload/disconnect recovery | PARTIAL | [E05], [E14]. Durable workflows and board persistence exist; common loss-resistant graph drafts absent. |
| GRAPH-09 §7.2 | Import/export graph templates; disconnect/delete consequence preview | PARTIAL | [E05], [E06]. Restricted templates exist; typed graph format and impact preview missing. |
| GRAPH-10 §7.2 | Large-graph virtualization/LOD benchmark | MISSING | [E14]. No 1,000-object benchmark/threshold is established. |
| GRAPH-11 §7.3 | Input nodes: Text/Image/Video/Audio/3D/AssetRef/reference/Depth/external file | MISSING | [E05], [E11]. Original owner contracts are reusable; unified typed registry missing. |
| GRAPH-12 §7.3 | Processing nodes: Agent/image/edit/upscale/video/interpolate/TTS/ASR/convert/quality | PARTIAL | [E05], [E11], [E16], [E17]. Individual adapters exist; graph node registration/binding remains. |
| GRAPH-13 §7.3 | Control nodes: Director/style/character/camera/motion/budget/review/conditions | PARTIAL | [E05], [E08], [E15]. Manual review exists; generalized controls and conditions not available. |
| GRAPH-14 §7.3 | Output nodes: Asset Save/Preview/Export/Timeline Handoff/Package | PARTIAL | [E03], [E05], [E17], [E23]. Individual outputs exist; graph output adapter contract missing. |
| GRAPH-15 §7.3 | Text/Image/Video/Audio/Model/Scene/Camera/Pose/Depth/Style/AssetRef/Timeline ports | MISSING | [E05]. Source/target ID edges cannot represent this type system. |
| GRAPH-16 §7.3 | Single-node or graph execution with no Director node | PARTIAL | [E11]. Standalone media calls exist; generic single-node execution not integrated. |
| GRAPH-17 §7.4 | Preview inputs/outputs/models/permissions/privacy/resources/cost/overwrite | PARTIAL | [E08], [E09], [E11]. Existing route/request previews; whole-graph preview missing. |
| GRAPH-18 §7.4 | Dependency execution and bounded concurrency | PARTIAL | [E05]. Topological ordered host exists; multimodal bounded parallel execution not implemented. |
| GRAPH-19 §7.4 | VRAM conflict queue, staged unload and resource release | PARTIAL | [E07], [E08]. Runtime lifecycle exists; graph-wide memory resource scheduler missing. |
| GRAPH-20 §7.4 | Cache binds input version/model/parameters/definition/permission; descendant invalidation | MISSING | [E04], [E05]. Existing stale-source evidence is not graph execution cache. |
| GRAPH-21 §7.4 | Node/local rerun, queue pause, explicit retry, cancel requested versus acknowledged | PARTIAL | [E05], [E08], [E13]. Original run/job operations exist; partial graph replay remains. |
| GRAPH-22 §7.4 | Truthful node progress/time/resource/missing-capability/error navigation | PARTIAL | [E13], [E14]. Existing task projections; per-node graph UI missing. |
| CONSOLE-01 §8 | Optional Director Console carries vision/duration/audience/story/style/performance/sound/review | PARTIAL | [E02], [E15]. Director data/proposals exist; graph Console contract missing. |
| CONSOLE-02 §8 | Versioned suggestions/parameters to multiple targets without elevated authority | MISSING | [E05], [E15]. Requires graph ports and reviewed propagation. |
| CONSOLE-03 §8 | Collapsible card, expanded Console, dependency/progress preview | MISSING | [E14], [E15]. Current panels are not a graph Console node. |
| CONSOLE-04 §8 | Multiple independent Director nodes, duplicate as sub-console | MISSING | [E05], [E15]. Multiple documents are not multiple typed console nodes. |
| CONSOLE-05 §8 | Preview/review graph/Shot List proposals before replacing/rerunning/sending | PARTIAL | [E02], [E15]. Reviewed shot/director proposals exist; graph proposal adoption missing. |
| CONSOLE-06 §8 | Disconnect/delete Director without breaking unrelated valid nodes/assets | MISSING | [E05]. Requires actual typed graph dependency tests. |

## 9. Text and Screenplay

| ID / roadmap | Sub-capability | Status | Owner / evidence and remaining boundary |
|---|---|---|---|
| TEXT-01 §9.1 | Existing project/world/character/outline/chapter/version/CAS/revision retained | EXISTS | [E01], [E20]. Preserve original owners; M0 does not reimplement V1. |
| TEXT-02 §9.1 | Memory/context/Agent and existing exports retained | EXISTS | [E08], [E20], [E23]. New graph references must not replace these systems. |
| TEXT-03 §9.1 | Long/short manual writing, continue/generate/rewrite/shorten/expand/style proposals | PARTIAL | [E08], [E20]. Original author actions exist; each real model's language/quality not accepted here. |
| TEXT-04 §9.1 | Annotation/diff, explicit acceptance and new revision restoration | EXISTS | [E08], [E20]. Original review/CAS authorities apply. |
| TEXT-05 §9.1 | Character state/event/time/location/foreshadow/world-rule continuity with evidence | PARTIAL | [E19], [E20]. Rule/knowledge/quality owners exist; full semantic continuity quality not proved. |
| TEXT-06 §9.1 | Rich text and chapter identity preserved outside Graph text boxes | EXISTS | [E01], [E20]. Existing document/revision contracts remain authoritative. |
| TEXT-07 §9.2 | Geography/history/organization/politics/rules/items/events/references/custom fields | PARTIAL | [E19], [E20]. Existing world/story schemas cover substantial subset; complete extensible domain UX remains. |
| TEXT-08 §9.2 | Character identity/personality/motivation/relations/growth/language/state | PARTIAL | [E19], [E20]. Current owner evidence and temporal knowledge are reusable; quality beyond represented facts unverified. |
| TEXT-09 §9.2 | Optional appearance/reference assets/Voice Profile links with privacy | PARTIAL | [E03], [E16], [E20]. Existing links; full cross-Studio optional selection/consent UX incomplete. |
| TEXT-10 §9.3 | Independent screenplay with no novel chapter source | EXISTS | [E02]. `source_independent` structured document path; neutral project navigation still CORE-01. |
| TEXT-11 §9.3 | Film/short/animation/ad/game screenplay presets | PARTIAL | [E02], [E06]. Flexible fields/templates, not all specialized presets verified. |
| TEXT-12 §9.3 | Selected chapter/range source, scene/location/time/action/dialogue/performance structure | PARTIAL | [E02], [E20]. Existing adaptation and creative schemas; current text scaffolding is not full adaptation. |
| TEXT-13 §9.3 | Real adaptation: scene splitting/visualization/dialogue restructuring/deletion/difference report | PARTIAL | [E20], [E09]. Adaptation proposal lifecycle exists; new V2 source-aware Agent depth/quality needs M4. |
| TEXT-14 §9.3 | Independent revisions, human review, source comparison and downstream ScreenplayAsset | PARTIAL | [E02], [E20]. Original screenplay and creative contracts exist; avoid two authoritative copies in bridge. |
| TEXT-15 §9.3 | Fountain/DOCX exports reused for independent V2 screenplay | PARTIAL | [E23]. Industry exporters exist; creative document export is JSON and needs an adapter. |
| TEXT-16 §9.3 | Markdown/PDF/EPUB according to actual supported export route | PARTIAL | [E23]. Novel format support does not establish each V2 screenplay format. |
| TEXT-17 §9.4 | Generic Document/Script for ads/MV/podcast/game dialogue/presentation text | MISSING | [E02], [E20]. Dedicated reusable neutral script asset contract not found. |
| TEXT-18 §9.4 | Writer/Editor/Critic/Continuity/Adaptation reuse context and review | PARTIAL | [E08], [E20], [E24]. Existing roles/skills; full independent script integration missing. |
| TEXT-19 §9 acceptance | Novel, independent screenplay and selected-chapter adaptation complete E2E | PARTIAL | [E02], [E20]. Exact current suites cover bounded creative flows; real adaptation quality LOCAL_REQUIRED. |

## 10. Image Studio

| ID / roadmap | Sub-capability | Status | Owner / evidence and remaining boundary |
|---|---|---|---|
| IMAGE-01 §10.1 | Standalone T2I, imported image edit and I2I | PARTIAL | [E03], [E11], [E14]. Existing provider/API/media routes, but neutral end-to-end independence incomplete. |
| IMAGE-02 §10.1 | Multi-candidate, batch variants and side-by-side reuse | PARTIAL | [E11], [E14]. Candidate/task surfaces exist; full comparison/graph batch UX incomplete. |
| IMAGE-03 §10.1 | Shared nodes for prompt/model/LoRA/style/character/composition/Pose/Depth/edit/upscale | MISSING | [E05], [E14]. Reference canvas is not the requested typed node system. |
| IMAGE-04 §10.1 | Preview thumbnails, drag output reuse, saved graph groups | PARTIAL | [E14]. Image board previews/groups exist; executable graph persistence/reuse absent. |
| IMAGE-05 §10.1 | External reference equal to generated asset, no Text/Storyboard prerequisite | PARTIAL | [E03], [E11]. Byte/reference contracts exist; no-chapter project path is M1. |
| IMAGE-06 §10.2 Generate | T2I/I2I, negative prompt, size/aspect/seed/batch/preset | PARTIAL | [E11]. Capability-dependent provider paths; not all adapters support all parameters. |
| IMAGE-07 §10.2 Generate | Multiple references only when actual adapter supports them | PARTIAL | [E11]. Operation schema exists; names/catalog claims are not real generation proof. |
| IMAGE-08 §10.2 Edit | Inpaint mask/local redraw/outpaint/object/background/erase/repair | PARTIAL | [E11]. Generic image-edit adapter exists; full interactive mask/tools and supported-provider matrix missing. |
| IMAGE-09 §10.2 Enhance | Upscale/denoise/repair/cutout, before-after comparison, new asset output | PARTIAL | [E11]. Processing registry/output lineage exists; complete four-operation editor not delivered. |
| IMAGE-10 §10.2 Consistency | Character/outfit/style/scene reference sets pinned to exact versions | PARTIAL | [E04], [E11], [E20]. Existing visual identity/reference evidence; absolute visual consistency not guaranteed. |
| IMAGE-11 §10.2 Character | Front/side/back, expression/pose/outfit variants and optional character atlas link | PARTIAL | [E11], [E20]. Character-reference contracts exist; atlas-specific UI/execution coverage missing. |
| IMAGE-12 §10.2 Scene | Concept/architecture/atmosphere/layout/angle and optional Director/3D linkage | PARTIAL | [E11], [E15]. Scene reference capability exists; 3D/typed control absent. |
| IMAGE-13 §10.2 Asset | Dimensions/color space/EXIF policy/rights/version compare/reuse | PARTIAL | [E03], [E04], [E11]. Measured media/lineage exists; complete color/EXIF policy and comparison UX missing. |
| IMAGE-14 §10.3 | Separate pixel editor with layers/masks/brush/region/local generation; saved version → port | MISSING | [E14]. Node/reference canvas is not a layered pixel editor. |
| IMAGE-15 §10.4 | Discover/reuse ComfyUI and validate graph components without reinstalling base model | PARTIAL | [E07], [E11]. Existing adapter/probes; complete per-graph dependencies missing. |
| IMAGE-16 §10.4 | Optional approved API image egress and cost receipt | PARTIAL | [E08], [E11]. Guarded provider paths; no paid invocation in this task. |
| IMAGE-17 §10 acceptance | PNG/JPEG/WebP actual encoding, graph save/reopen/local rerun/stale reference | PARTIAL | [E03], [E11], [E14]. Raw format-preserving download exists; conversion and graph path require separate tests. |
| IMAGE-18 §10 acceptance | Actual local image model execution and quality on target Windows | LOCAL_REQUIRED | [E07], [E11]. Synthetic media/mock transport is not this evidence. |

## 11–12. Director and Storyboard

| ID / roadmap | Sub-capability | Status | Owner / evidence and remaining boundary |
|---|---|---|---|
| DIR-01 §11.1 | Start blank or with screenplay/shot/image/video/white-model/prompt | PARTIAL | [E02], [E15]. Independent structured Director possible; all media entry adapters missing. |
| DIR-02 §11.1 | Vision/audience/duration/platform/art/story pacing/emotion curve | PARTIAL | [E02], [E15]. Notes/plans cover subset; full independent intent Console missing. |
| DIR-03 §11.1 | Color/light/material/blocking/composition/camera/performance controls | PARTIAL | [E02], [E15]. Structured fields and rule checks exist; not all are executable model controls. |
| DIR-04 §11.1 | Director notes/unknowns, A/B proposals, explicit review and rollback | PARTIAL | [E02], [E09], [E15]. Rule/model proposals and immutable revision recovery exist; broad A/B media workflow incomplete. |
| DIR-05 §11.2 | Optional expandable/copyable/dragged Console in any project graph | MISSING | [E05], [E14], [E15]. See CONSOLE-02–06. |
| DIR-06 §11.2 | Show related graph input/output/progress/resources/risks; proposal workflow/task groups | MISSING | [E05], [E13], [E15]. Task projection not yet a Console graph. |
| DIR-07 §11.2 | Versioned suggestion port; no execution/fee/overwrite bypass | PARTIAL | [E09], [E15]. Existing review boundaries; port contract missing. |
| DIR-08 §11.3 | Shot size/orientation/focal length/camera motion/eyeline/spatial/blocking/sound plan | PARTIAL | [E02], [E15]. Data and bounded rule diagnostics; geometry only when supplied evidence exists. |
| DIR-09 §11.3 | Evidenced 3D camera/video motion analysis; unknown when absent | PARTIAL | [E15]. Current camera checks distinguish missing evidence; actual 3D/video analysis adapter absent. |
| SHOT-01 §12.1 | Stable ShotId/order/duration/scene, lens/angle/motion/action/light/color/dialogue/sound | EXISTS | [E02], [E15]. Existing shot records cover this bounded field set. |
| SHOT-02 §12.1 | Truly independent shot with optional scene/project link, timecode/media/review/source | PARTIAL | [E02], [E15]. Current creative ShotCard requires scene ID; generic independent Shot Asset missing. |
| SHOT-03 §12.2 | Shot List sort/bulk edit/filter/import/export | PARTIAL | [E15], [E23]. Existing list/edit/export; complete bulk/import/filter semantics not all implemented. |
| SHOT-04 §12.2 | Shot Board cards/scene groups/text-image mapping/thumbnails/comparison | PARTIAL | [E14], [E15]. Existing cards/board; comparison and generic grouping incomplete. |
| SHOT-05 §12.2 | Storyboard Canvas branches/transitions with Image/Video/Director nodes | MISSING | [E05], [E14]. No shared executable typed Storyboard canvas. |
| SHOT-06 §12.3 | Suggested breakdown from screenplay/director/image/uploaded video without forced script | PARTIAL | [E02], [E15]. Structured derivation exists; image/video breakdown and no-script UX incomplete. |
| SHOT-07 §12.3 | Direct Shot→Image or Shot→Video without required image intermediate | PARTIAL | [E11], [E15]. Individual operations exist; free graph handoff and independent shot contract missing. |
| SHOT-08 §12.3 | Depth/Pose/Camera/white-model/3D preview inputs and honest incompatibility | MISSING | [E11], [E15]. No complete typed 3D/reference input seam. |
| SHOT-09 §12.3 | Stable reorder identity, timeline references and stale-impact indication | PARTIAL | [E02], [E04], [E15]. Stable IDs and source revisions; final NLE reference propagation missing. |

## 13. Video Studio and reference control

| ID / roadmap | Sub-capability | Status | Owner / evidence and remaining boundary |
|---|---|---|---|
| VIDEO-01 §13.1 | Prompt→independent T2V asset | PARTIAL | [E11]. Operation/provider seam exists; neutral UI and real provider result still separate. |
| VIDEO-02 §13.1 | Any uploaded image→I2V without Image Studio history | PARTIAL | [E03], [E11]. Reference inputs exist; full M1/M7 independent path absent. |
| VIDEO-03 §13.1 | Imported video→V2V/style/reference generation | MISSING | [E11]. No generic V2V operation in current media operation schema. |
| VIDEO-04 §13.1 | Character/scene/action/style/camera constrained references | PARTIAL | [E11], [E15]. Some frame/continuation contracts; comprehensive validated controls unavailable. |
| VIDEO-05 §13.1 | Previs/gray model screenshot/video/scene-camera→candidate video | MISSING | [E11]. Not established by a video model family catalog. |
| VIDEO-06 §13.1 | MP4/MOV import directly into edit workflow without model generation | PARTIAL | [E03], [E17]. Imported bytes and bounded assembly exist; standalone NLE missing. |
| VIDEO-07 §13.2 | Shared video node canvas, reference fan-out, candidates and batch execution | MISSING | [E05], [E14]. Existing shot sequence is not typed graph execution. |
| VIDEO-08 §13.2 | Per-step actual input/output/time/resource/cost | PARTIAL | [E08], [E11], [E13]. Existing task receipts; full graph view/resource measurements missing. |
| VIDEO-09 §13.3 | Separate static gray-image composition reference | MISSING | [E11]. Requires a typed reference intent and supported-provider mapping. |
| VIDEO-10 §13.3 | Separate temporal Previs video/action/camera reference | MISSING | [E11]. No proven temporal-control capability. |
| VIDEO-11 §13.3 | Separate actual 3D scene/animation/camera with extracted geometry | MISSING | [E11], [E18]. No parser/camera interchange owner exists yet. |
| VIDEO-12 §13.3 | Import/preview/media metadata and keyframe selection/sampling | PARTIAL | [E11], [E17]. Media validation/frame helpers exist; full reference review UI incomplete. |
| VIDEO-13 §13.3 | Reference purpose/weights/capability mapping/duration alignment/risk preview/comparison | PARTIAL | [E08], [E11]. Preflight supports bounded capabilities; complete controls/quality review missing. |
| VIDEO-14 §13.3 | Optional optical flow/pose/depth/camera extraction | MISSING | [E11], [E18]. No validated complete extraction pipeline. |
| VIDEO-15 §13.4 | Local/ComfyUI adapters advertise T2V/I2V/V2V separately | PARTIAL | [E07], [E11]. Registry/HTTP provider exists; all local workflow variants not implemented. |
| VIDEO-16 §13.4 | Submit/progress/query/cancel/download/verify/usage/privacy/size contract | PARTIAL | [E11]. HttpVideoProvider and worker cover subset; production vendor semantics need explicit adapters. |
| VIDEO-17 §13.4 | Low-spec alternatives or approved API without silent private upload | PARTIAL | [E08], [E11]. Guardrails exist; actual provider comparison/approved async paid path not proven. |
| VIDEO-18 §13.4 | Stable result asset/model parameters/exact references, compare and independent export | PARTIAL | [E03], [E04], [E11]. Core receipts exist; standalone Video UI incomplete. |
| VIDEO-19 §13.5 | Queue/VRAM-disk estimate/load-release/draft-final mode/fail-cancel-retry | PARTIAL | [E07], [E08], [E11], [E13]. Owner operations exist; full shared resource scheduling missing. |
| VIDEO-20 §13.5 | Validate actual output codecs/metadata; retain confirmed results offline | PARTIAL | [E03], [E11]. Measured fixture media and persisted tasks exist; all crash/offline cases not accepted. |
| VIDEO-21 §13 acceptance | Real target Windows local-video inference and reference-control quality | LOCAL_REQUIRED | [E07], [E11]. Cloud contracts do not prove model output or GPU throughput. |

## 14. Audio Studio

| ID / roadmap | Sub-capability | Status | Owner / evidence and remaining boundary |
|---|---|---|---|
| AUDIO-01 §14.1 | Independent TTS text and optional character Voice Profile | PARTIAL | [E11], [E16]. Existing TTS/profile services; neutral no-Text-project surface missing. |
| AUDIO-02 §14.1 | Voice language/rate/emotion/performance suggestions | PARTIAL | [E16]. Voice-direction fields/adapters exist; provider support is explicit, not universal. |
| AUDIO-03 §14.1 | Audio import, ASR transcription and subtitle alignment | PARTIAL | [E03], [E16], [E17]. Import/caption/ASR seams; full standalone path not complete. |
| AUDIO-04 §14.1 | SFX/ambience/Foley/music generation or licensed references | PARTIAL | [E11], [E16]. Processing contracts/assets exist; not a complete sound library or all real adapters. |
| AUDIO-05 §14.1 | Sample rate/channel/loudness processing | PARTIAL | [E16], [E17]. Metadata and audio tools exist; full conversion/normalization UI missing. |
| AUDIO-06 §14.1 | Voice conversion/denoise/separation/consistency according to capabilities | MISSING | [E16]. No complete supported independent toolset found. |
| AUDIO-07 §14.1 | Long dialogue segments, timecodes and role mapping | PARTIAL | [E16]. Audiobook/voice direction owners exist; standalone audio workflow incomplete. |
| AUDIO-08 §14.1 | Shared Audio Canvas with text/video analysis/reference/TTS/SFX/mix nodes | MISSING | [E05], [E16]. Common graph integration required. |
| AUDIO-09 §14.1 | Independent audition/light-edit/sync Audio Timeline | MISSING | [E16], [E17]. Voice/caption preparation is not an independent editable audio timeline. |
| AUDIO-10 §14.2 | Voice-clone/person-imitation authorization and rights evidence | BLOCKED | [E16]. Explicitly later advanced capability; no default cloning/training or external recording retention. |
| AUDIO-11 §14.3 | Distinct TTS/ASR/Music/SFX capability and local/approved API adapters | PARTIAL | [E11], [E16]. Source distinction exists; execution availability varies. |
| AUDIO-12 §14.3 | Provenance/duration/sample rate/channels/rights/version; WAV/FLAC/MP3 actual encoding | PARTIAL | [E03], [E16], [E17]. Existing audio export paths; all named codecs/standalone flow unverified. |
| AUDIO-13 §14 acceptance | Import→audition/trim/export and timeline stale-source detection | PARTIAL | [E03], [E04], [E16], [E17]. Full independent audio editor is not present. |
| AUDIO-14 §14 acceptance | Real TTS/ASR quality and target-device performance | LOCAL_REQUIRED | [E16]. Mock/fixture output is not a model-quality result. |

## 15. Editing Studio: actual NLE requirements

| ID / roadmap | Sub-capability | Status | Owner / evidence and remaining boundary |
|---|---|---|---|
| EDIT-01 §15.1 | Separate Editing Studio from generation; external-only project | MISSING | [E17]. Existing shot planning/assembly do not provide an independent NLE. |
| EDIT-02 §15.1 | Multiple editable video tracks; trim/split/move/insert/overwrite | MISSING | [E17]. Current assembly is an ordered single video-only cut, not track composition. |
| EDIT-03 §15.1 | Video overlays/transitions/crop/position/scale/opacity/lock/mute | MISSING | [E17]. Planning transition values do not execute these edit operations. |
| EDIT-04 §15.1 | Multiple audio tracks, waveform/gain/fade/mute/alignment/mix/link | MISSING | [E16], [E17]. Existing audio services are not multi-track NLE mixing. |
| EDIT-05 §15.1 | Subtitle track editing/timecode/style/preview/export | PARTIAL | [E17]. Caption owner supports timing/edit/export; final NLE integration missing. |
| EDIT-06 §15.1 | Ruler/playhead/zoom/snap/multiselect/track height/shortcuts/history | PARTIAL | [E14], [E17]. Planning timeline offers subsets; real media-edit history and track semantics missing. |
| EDIT-07 §15.1 | Parallel player/browser/Inspector and smooth proxy editing | MISSING | [E17]. No complete proxy-based NLE workspace. |
| EDIT-08 §15.2 | Real decoding, proxy/cache, preview-versus-final quality | PARTIAL | [E11], [E17]. Validation/review rendering exists; interactive playback/proxy owner missing. |
| EDIT-09 §15.2 | Rational timebase/FPS, sync and offline/unsupported/missing-frame errors | PARTIAL | [E17]. Caption/OTIO fractions and media checks exist; full NLE media resolution/sync absent. |
| EDIT-10 §15.2 | FFmpeg real trim/concat/compose/audio/subtitle mux or burn-in, final file validation | PARTIAL | [E17]. Verified video-only bounded assembly exists; audio/subtitle multi-track composition missing. |
| EDIT-11 §15.2 | OTIO exchange with real parser and explicit compatibility losses | EXISTS | [E17]. Bounded official parser contract; no implication of full external editor compatibility. |
| EDIT-12 §15.2 | FCPXML/EDL and real Resolve/Premiere compatibility | BLOCKED | [E17]. Planning text export is not certified exchange; target application acceptance not performed. |
| EDIT-13 §15.3 | AI scene/material/rhythm/rough-cut/subtitle/color/continuity proposals | PARTIAL | [E15], [E17], [E20]. Some rule/analysis suggestions exist; reviewed NLE edit plans missing. |
| EDIT-14 §15.3 | Review before timeline overwrite; regenerate candidate then explicit replace | MISSING | [E04], [E17]. Requires actual timeline authority and adoption contract. |
| EDIT-15 §15.3 | Trace clip to model/prompt/reference/approval history | PARTIAL | [E04], [E11], [E17]. Existing source receipts; no full NLE clip graph. |
| EDIT-16 §15 acceptance | External input→2 video+2 audio+subtitle tracks→preview→render→reopen | MISSING | [E17]. PRODUCTION/VideoTimeline cards must never satisfy this gate. |
| EDIT-17 §15 acceptance | Target Windows GPU playback/encoding/performance | LOCAL_REQUIRED | [E17]. Requires completed NLE and explicitly authorized target-machine acceptance. |

## 16–19. 3D, Research, Collaboration and Delivery

| ID / roadmap | Sub-capability | Status | Owner / evidence and remaining boundary |
|---|---|---|---|
| D3-01 §16 | GLB/glTF/OBJ/FBX/USD actual supported parser, metadata/license/version | MISSING | [E03], [E18]. Generic binary upload is not parser support. |
| D3-02 §16 | Orientation/camera/gray material lightweight preview and frame export | MISSING | [E18]. No verified 3D preview owner. |
| D3-03 §16 | Blender asset/camera/animation/timebase/previs interchange | MISSING | [E18]. Future adapter, no authority to manipulate user's DCC project. |
| D3-04 §16 | UE camera/Sequencer/render-result interchange and version compatibility | MISSING | [E18]. Contract needs actual supported format/version evidence. |
| D3-05 §16 | 3D generation/rigging/mocap/material advanced execution | BLOCKED | [E18]. Explicit later scope, not inferred from model names. |
| D3-06 §16 | Independent uploaded 3D→Video/Storyboard reference without Image Studio | MISSING | [E03], [E11], [E18]. Needs typed asset/parser/reference seam. |
| RESEARCH-01 §17 | Independent research project, manual organization without model | PARTIAL | [E19]. Source/note library exists under project scope; neutral independent entry missing. |
| RESEARCH-02 §17 | PDF/DOCX/Markdown/image/web reference/notes, cite without forced full copy | PARTIAL | [E19]. Bounded extraction/import and legacy metadata references exist; full type/view parity incomplete. |
| RESEARCH-03 §17 | Author/date/link/license/access/trust/summary/verification timestamp | PARTIAL | [E19]. Metadata/citation/version fields cover subset; complete trust/license schema missing. |
| RESEARCH-04 §17 | Search/RAG/embedding with traceable citations and missing-dependency fallback | PARTIAL | [E19]. Literal/vector/vision seams exist; real semantic performance not accepted. |
| RESEARCH-05 §17 | Historical/geographic/architecture/world/reference analysis for other modules | PARTIAL | [E19], [E20]. Reviewed evidence/context links exist; broad visual/3D integration missing. |
| RESEARCH-06 §17 | Explicit web fetch, no background private upload | EXISTS | [E19]. `confirm_fetch` and bounded source handling; no new online search was executed by M0. |
| RESEARCH-07 §17 | Licensed QingJian public knowledge references, no automatic private memory/training | PARTIAL | [E12], [E19]. Privacy boundaries exist; external knowledge product integration unavailable. |
| COLLAB-01 §18 | Workspace/members/roles/project/asset/task permissions and audit | EXISTS | [E01], [E21]. Existing authority must be reused. Neutral V2 asset paths need exact-scope regression. |
| COLLAB-02 §18 | Review/comments/annotations and human-task versus AI-job distinction | PARTIAL | [E13], [E21]. Existing review/task owners; not complete all-Studio assignment UI. |
| COLLAB-03 §18 | Branch/CAS/conflict/merge, immediate revocation | EXISTS | [E01], [E20], [E21]. Preserve original authorization and branch content ownership. |
| COLLAB-04 §18 | Production cloud sync/realtime enterprise media collaboration | BLOCKED | [E21]. Existing experimental realtime/sync surfaces do not imply broad production approval; later high-risk scope. |
| COLLAB-05 §18 | Team/branch ownership of all new asset/graph/timeline kinds | PARTIAL | [E01], [E03], [E05], [E21]. Existing scope guards; future media/graph kinds need complete proof. |
| DELIVER-01 §19 | Each supported module independently exports its real format | PARTIAL | [E03], [E23]. Original novel/assets/captions/creative JSON exist; missing Studios cannot claim formats. |
| DELIVER-02 §19 | Package manifest/assets/graph/relations/history/license list without weights | PARTIAL | [E10], [E23]. Existing portable package is selected chapters+referenced media; no full V2 graph/timeline package. |
| DELIVER-03 §19 | Editable novel/short/vertical/CG/competition delivery presets | PARTIAL | [E06], [E23]. Existing export/template choices; complete delivery presets/rules evidence missing. |
| DELIVER-04 §19 | Model/material/voice/API-output rights and permitted-use inventory | PARTIAL | [E04], [E08], [E16], [E23]. Declarations exist; not legal verification or comprehensive clearance. |
| DELIVER-05 §19 | Production notes/log/manifest/missing-dependency report | PARTIAL | [E04], [E10], [E23]. Existing receipts/packages; complete cross-Studio report not available. |
| DELIVER-06 §19 | Automatic submission or online portfolio publishing | BLOCKED | [E23]. Later optional externally consequential scope; no publish authorization here. |
| DELIVER-07 §19 | Device migration/path remap/digest checks/traversal and overwrite protection | PARTIAL | [E10], [E23]. Portable restore/relink safeguards exist; full graph/timeline migration incomplete. |
| DELIVER-08 §19 | Offline package reopen with finished media even if models absent | PARTIAL | [E10], [E23]. Bounded portable restore exists; full V2 package gate not met. |

## 20–22. Intelligence, QingJian and UX

| ID / roadmap | Sub-capability | Status | Owner / evidence and remaining boundary |
|---|---|---|---|
| AI-01 §20.1 | Writer/Editor/Adaptation/Director/Storyboard/Visual/Motion/Voice/RoughCut/Research/Quality/Delivery roles | PARTIAL | [E24], [E09], [E20]. Existing Agent/Skill owners; role names do not establish each capability. |
| AI-02 §20.1 | Task Planner proposes editable module/node/task plan | PARTIAL | [E05], [E24]. Recipes/declarative proposals exist; generalized multimodal planner missing. |
| AI-03 §20.1 | Orchestrator delegates execution to original Job/Provider owners | EXISTS | [E05], [E08], [E24]. Existing adapter pattern to preserve, not a second executor. |
| AI-04 §20.1 | Authorized Context Broker with source versions and goal/fact/advice/external separation | PARTIAL | [E08], [E19], [E20]. Original author context evidence exists; every future asset type not yet supported. |
| AI-05 §20.1 | Project memory versus user preference; no unreviewed output→canon promotion | EXISTS | [E20], [E24]. Existing gates and separate services. |
| AI-06 §20.1 | Separate schema validity/media metadata/rule continuity/subjective model quality | EXISTS | [E11], [E20]. Contracts preserve evidence boundaries; aesthetic quality still requires actual review. |
| AI-07 §20.2 | Suggested model/node/rework/reference/proxy/cleanup changes show egress/cost/impact | PARTIAL | [E04], [E08], [E10], [E24]. Existing preflights; complete generalized graph suggestion UX missing. |
| AI-08 §20.2 | No arbitrary Shell/download/plugin/network/user-file action from model content | EXISTS | [E07], [E24]. Restricted adapters and deny-all executable extensions. |
| AI-09 §20.3 | Route by capability/evidence/resources/language/quality/health/cost/privacy/preferences | PARTIAL | [E08]. Existing explainable broker; observed quality/resource data remains incomplete. |
| AI-10 §20.3 | Refuse incapable local route; no unapproved charged fallback | EXISTS | [E08], [E09]. `NO_LEGAL_ROUTE`/local-only preview fences are not replaced by model-name guesses. |
| TUTOR-01 §21.1 | Stable PoemSeed protocol 1.0 and both product IDs | EXISTS | [E12]. `poemseed.creative.studio`, `poemseed.tutor.desktop`; no new parallel protocol. |
| TUTOR-02 §21.2 | Observer/Advisor/Tutor only; read consent distinct from control/memory/execution | EXISTS | [E12]. Security contract forbids inferred authority. |
| TUTOR-03 §21.3 | Dock/collapse/float/close Tutor Slot beside Inspector, no canvas/track obstruction | MISSING | [E12], [E22]. Existing integration panel is not a complete dockable/floating slot. |
| TUTOR-04 §21.3 | Avatar/breathing state/permission cue/advice/task explanation/tutorial steps | PARTIAL | [E12]. Advice/consent UI exists; slot-specific visual states missing. |
| TUTOR-05 §21.3 | Absent QingJian and disconnect do not block Studio | EXISTS | [E12]. Optional default-off integration and failure isolation. |
| TUTOR-06 §21.3 | Disconnected/authorizing/connected/expired/incompatible/unavailable states | PARTIAL | [E12]. Session state UI exists; future slot requires integration tests. |
| TUTOR-07 §21.3 | Multi-monitor/high-DPI/resize/focus/reduced-motion real window behavior | LOCAL_REQUIRED | [E12], [E22]. Cloud React/native fixtures are not target-window UX acceptance. |
| TUTOR-08 §21.3 | Tutor identity separate from built-in Agent and fee/permission decisions | EXISTS | [E12], [E24]. Existing external bridge authority remains distinct. |
| TUTOR-09 §21.4 | Minimized semantic project/asset/task/module/graph/node/error/model/goal context | PARTIAL | [E12]. Existing chapter/task/model capsule; new graph/asset extensions need versioned schema. |
| TUTOR-10 §21.4 | No default prose/media/private-path/credential/raw-log share | EXISTS | [E12]. Allowlist and content-preview consent are existing contracts. |
| TUTOR-11 §21.4 | HELLO/capabilities/session/trust/expiry; restart invalidates old grants | EXISTS | [E12]. Current session lifecycle, not durable permission transfer. |
| TUTOR-12 §21.4 | Recommendation/TeachingStep/Diagnostic; graph creation remains reviewed proposal | PARTIAL | [E12]. Existing advisory messages; graph draft type and adoption missing. |
| TUTOR-13 §21.4 | Bounded loopback/Named Pipe SID/instance/version/size/deadline contract | PARTIAL | [E12]. Reference/native fixture evidence; complete production mutual attestation remains local. |
| TUTOR-14 §21.4 | Actual independent QingJian desktop source and two-product integration | LOCAL_REQUIRED | [E12]. Real target Desktop source/runtime absent; synthetic peer is MOCK_ONLY. |
| TUTOR-15 §21.5 | VRAM/LoRA/ControlNet/editing-continuity teaching for selected node/track | PARTIAL | [E12], [E07]. Advisory foundation exists; new node/track context not implemented. |
| UX-01 §22.1 | DS-v1.0/AppShell/Tokens/primitives and protected-surface process | EXISTS | [E22]. Mandatory existing owner, not permission to redesign shell. |
| UX-02 §22.2 | Home/intent/recent/capability cards without mandatory wizard | PARTIAL | [E06], [E22]. Existing entry/recents; neutral intent home missing. |
| UX-03 §22.2 | Text chapter/screenplay/version/world/character specialized view | PARTIAL | [E02], [E20], [E22]. Existing specialized consumers; neutral Studio integration remains. |
| UX-04 §22.2 | Image/Video graph+preview+Inspector+queue/simple form | PARTIAL | [E11], [E14], [E22]. Existing boards/forms; common typed canvas absent. |
| UX-05 §22.2 | Director Console/Storyboard board/canvas/review | PARTIAL | [E02], [E15]. Existing panels and cards; Console/canvas missing. |
| UX-06 §22.2 | Audio waveform/voice/design/preview/light timeline | MISSING | [E16], [E22]. Full independent Audio workspace not delivered. |
| UX-07 §22.2 | Editing browser/player/Inspector and resizable true multi-track timeline | MISSING | [E17], [E22]. Requires actual NLE implementation. |
| UX-08 §22.2 | 3D lightweight preview/structure/camera | MISSING | [E18], [E22]. No full 3D workspace. |
| UX-09 §22.2 | Research/Delivery source/license/checklist and optional Tutor workspace | PARTIAL | [E12], [E19], [E23]. Existing panels; unified independent workspaces incomplete. |
| UX-10 §22.3 | 1,000-object LOD/incremental rendering benchmark | MISSING | [E14], [E22]. No measured threshold frozen. |
| UX-11 §22.3 | Background generation/transcode/index, nonblocking UI | PARTIAL | [E08], [E11], [E13], [E17]. Existing jobs; not every current synchronous owner becomes background automatically. |
| UX-12 §22.3 | Thumbnail/proxy/chunked media loading, not all 4K media in React | PARTIAL | [E03], [E14], [E17]. Bounded previews exist; general proxy service missing. |
| UX-13 §22.3 | Visible save/dirty/conflict and safe workspace switch/reload recovery | PARTIAL | [E02], [E20], [E22]. Existing drafts/guards; unsaved creative in-memory drafts do not survive every process exit. |
| UX-14 §22.3 | Truthful queued/progress/cancel/error/retry from actual owner | EXISTS | [E13]. Unknown observations stay unknown; future nodes must adopt this contract. |
| UX-15 §22.3 | Keyboard/focus/reduced-motion/IME and 1366×768/1440×900/1920×1080/2560×1440 | PARTIAL | [E22]. Existing UI/three-size geometry evidence; new canvases, 2560 and native IME incomplete. |
| UX-16 §22.3 | Real screenshots plus independent subjective review and reproducible geometry | PARTIAL | [E22]. Historical current-source browser screenshots exist; new Studio review and historical independent audit are not closed. |

## 23–29. Journeys, milestone gates, verification and safety

| ID / roadmap | Sub-capability / gate | Status | Owner / evidence and remaining boundary |
|---|---|---|---|
| PATH-01 §23.1 | Novel-only manual/AI-approved writing and export, no media install | EXISTS | [E01], [E08], [E20], [E23]. Existing original path; actual model quality remains separate. |
| PATH-02 §23.2 | External image→optional I2V model/API→independent video export | PARTIAL | [E03], [E08], [E11]. Full neutral UI/model evidence not complete. |
| PATH-03 §23.3 | CG intent→free Image/3D/Director→references→Editing→delivery | MISSING | [E14], [E17], [E18]. Core graph/3D/NLE not implemented. |
| PATH-04 §23.4 | Optional novel adaptation→screenplay/director/shot/media/audio/edit/export | PARTIAL | [E02], [E09], [E11], [E15], [E16], [E17]. Structured planning exists; free full-chain production not complete. |
| PATH-05 §23.5 | Raw/previs video→reference analysis→capable provider→compare→NLE→output | MISSING | [E11], [E17], [E18]. Requires actual reference-video contract and NLE. |
| GATE-M0 §24 | Current owner inventory/frozen baseline/CI truth/migration plan | EXISTS | This matrix, [architecture](AI_NOVEL_STUDIO_V2_ARCHITECTURE.md), [M0 report](MILESTONE_M0_REPORT.md). Documentation audit only, no historical-review closure. |
| GATE-M1 §24 | Neutral Project/Intent/Storage/Asset plus independent image/video import/export | PARTIAL | [E01]–[E04], [E10]. Existing owner foundations; Appendix C image minimum remains next actual implementation. |
| GATE-M2 §24 | Typed common Graph/UI/local execution/cache/Console/Tutor placeholder | MISSING | [E05], [E14]. Existing workflow host must be extended, not replaced. |
| GATE-M3 §24 | Trusted reuse/onboarding/download choice/optional API proof | PARTIAL | [E07], [E08]. Existing discovery/route boundaries; full user workflow remains. |
| GATE-M4 §24 | Text and real source-aware adaptation plus generic scripts | PARTIAL | [E02], [E09], [E20], [E23]. Actual model-dependent gates remain LOCAL_REQUIRED where unavailable. |
| GATE-M5 §24 | Image graph/edit/reference/model/format path | PARTIAL | [E03], [E11], [E14]. Full graph/editor and real-model proof incomplete. |
| GATE-M6 §24 | Independent Director/Shot with optional graph/media/3D references | PARTIAL | [E02], [E15]. Structured planning exists; Console and free shot graph incomplete. |
| GATE-M7 §24 | Standalone video/reference/previs/local/API/resources | PARTIAL | [E08], [E11]. Existing provider seams; reference control and complete product flow missing. |
| GATE-M8 §24 | Standalone audio/TTS/ASR/edit/waveform/export | PARTIAL | [E16], [E17]. Existing audio owners, incomplete Studio. |
| GATE-M9 §24 | Real editable multi-track NLE and verified output/reopen | MISSING | [E17]. Planning timeline never satisfies this gate. |
| GATE-M10 §24 | Independent 3D/research/delivery and Studio Tutor adapter | PARTIAL | [E12], [E18], [E19], [E23]. 3D missing, existing research/delivery/Interop bounded. |
| GATE-M11 §24 | Five free-entry paths, combined UX/performance/full exact-source regression | MISSING | [E25]. Future modules and stable candidate required first. |
| GATE-M12 §24 | Authorized user Windows installation/GPU/models/native acceptance | LOCAL_REQUIRED | [E12], [E25]. Only explicit later authorization permits target machine use. |
| VERIFY-01 §25 | Schema/bad inputs/CAS/provenance/scope/restart per new module | PARTIAL | [E02]–[E05], [E25]. Current owners covered; future contracts require new tests. |
| VERIFY-02 §25 | API auth/revoke/stale/timeout/audit/redacted failures | PARTIAL | [E01], [E02], [E08], [E12], [E25]. Existing fences; new neutral paths need cross-entry cases. |
| VERIFY-03 §25 | Real UI click/drag/key/zoom/window/dirty/recovery checks | PARTIAL | [E14], [E22], [E25]. Current browser suites are not future graph/NLE tests. |
| VERIFY-04 §25 | Real adapter request/receipt/incompatibility/fee/cancel/unknown/no-model | PARTIAL | [E07], [E08], [E11], [E25]. Contract/mock versus actual provider explicitly separated. |
| VERIFY-05 §25 | Graph edge/type/cycle/invalidations/cache/partial failure/recovery | PARTIAL | [E05]. Cycle/limited workflow tests exist; typed graph suite missing. |
| VERIFY-06 §25 | Real output bytes/metadata/preview-final distinction and audiovisual sync | PARTIAL | [E11], [E17]. Fixture validation exists; complete NLE sync/media coverage missing. |
| VERIFY-07 §25 | Independent and optional cross-module journeys | PARTIAL | [E02], [E11], [E25]. Only bounded current flows, not five blueprint paths complete. |
| VERIFY-08 §25 | Strict File/real-PG/frontend/browser/native/Interop/source receipts | PARTIAL | [E25]. Exact 4350 PR complete; push File/PG0 cancelled, aggregates fail closed. |
| SAFE-01 §26 | No bundled weights/forced models; local storage, secret Vault, explicit paid egress | EXISTS | [E07], [E08], [E10]. Preserve these existing boundaries; no paid invocation made. |
| SAFE-02 §26 | Bounded trusted path/port scans, no arbitrary code/plugins/pickle | EXISTS | [E07], [E24]. Actual safe discovery and deny-all execution rules. |
| SAFE-03 §26 | No automatic move/delete of original models/media/personal files | EXISTS | [E03], [E10]. Existing safe cleanup is narrowly scoped; future migrations require explicit contract. |
| SAFE-04 §26 | Voice/reference rights evidence, no implicit commercial clearance | PARTIAL | [E04], [E16]. Declarations exist; advanced voice cloning remains blocked. |
| SAFE-05 §26 | Untrusted model output strict parsing, never executable instructions | EXISTS | [E09], [E11], [E24]. Typed/bounded parsing and host-owned execution. |
| SAFE-06 §26 | Tutor no global RW token; revocable/audited context/memory/case sharing | EXISTS | [E12]. Optional bridge grants are distinct and scoped. |
| SAFE-07 §26 | Server default-off V2 and V1_ACCEPTANCE_MODE absolute override | EXISTS | [E26]. Existing flag inventory/dependencies; no browser bypass. |
| EXEC-01 §27 | Stage commits/tests/reports with exact start/end source identity | PARTIAL | [E25]. Existing source-bound evidence; new M0→M12 history belongs to each actual stage. |
| EXEC-02 §27 | CI timeout diagnosis preserving test order/skips/manifests/failures | PARTIAL | [E25]. Actual push capacity evidence retained; no capacity fix proven. |
| EXEC-03 §27 | Main/freeze/RC1 untouched, Draft retained, no merge/tag/release/deploy | EXISTS | [E25], [E26]. M0 changes only new documents; publication remains parent-controlled. |
| DOC-01 §28 | Current feature matrix and actual architecture | EXISTS | This file and [architecture](AI_NOVEL_STUDIO_V2_ARCHITECTURE.md); current M0 deliverables. |
| DOC-02 §28 | New full UX review/local-model integration/milestone history/Windows plan | PARTIAL | [E25]. Prior reports/plans exist; blueprint-complete final set is future milestone work. |
| DOC-03 §28 | Final exact-source RC candidate/install-upgrade/package manifest without weights | BLOCKED | [E25]. Not ready before applicable implementation/acceptance; release needs separate approval. |
| WIN-01 §29 | Clean install/start/uninstall/upgrade/IME/storage/no-model entry | LOCAL_REQUIRED | [E10], [E22], [E25]. Hosted packaging smoke is a different level. |
| WIN-02 §29 | Actual trusted discovery/16 GB GPU/64 GB RAM/model reuse/no manual port | LOCAL_REQUIRED | [E07], [E25]. No cloud-host observation substitutes. |
| WIN-03 §29 | Discovery versus enable/inference, service restart and 8/12/16 GB resource limits | LOCAL_REQUIRED | [E07], [E08]. Actual hardware/model evidence required. |
| WIN-04 §29 | Independent Studios and free optional graph/white-model combinations | LOCAL_REQUIRED | [E25]. Also depends on missing implementation; no premature device test. |
| WIN-05 §29 | Disconnect/revoke/cancel/error/crash/cache persistence and real multi-track reopen | LOCAL_REQUIRED | [E05], [E17], [E25]. Cloud contract subset does not prove native recovery. |
| WIN-06 §29 | Real QingJian consent/disconnect/window behavior/no control | LOCAL_REQUIRED | [E12]. Two actual applications and target-window evidence required. |
| WIN-07 §29 | Disk cleanup/safe exit preserving user models/assets; package SHA/file hashes | LOCAL_REQUIRED | [E10], [E25]. Bind actual built package and revalidate after source changes. |

## Appendix scope and immediate gate

Appendix A's future expansions remain **BLOCKED/deferred**, not missing current
V2 acceptance items: distributed remote rendering, model quality ranking fleets,
advanced realtime coauthoring, professional pixel compositing, complex automatic
cinematography, complete 3D camera simulation, exact 3D-controlled generation,
advanced live mixing/voice cloning, Resolve-class grading/VFX, full DCC,
advanced active research, production enterprise sync and automatic online
submission. Their nearest owners are the corresponding rows above; none should
be implemented as a parallel core or silently included in a claimed V2 finish.

Appendix B's prohibited shortcuts are review invariants for the associated rows:
intent is advisory; no required novel/shot origin; no duplicate weights/library;
discovery is not inference; no copied private ComfyUI engine; no superuser
Director; no planning-cards-as-NLE; no invented 3D fidelity; no silent API upload;
no forced Tutor popup; no modified frozen truth; no cloud-as-Windows claim.

Appendix C's first actual implementation target is **M1 minimum image loop**.
It is not completed by this matrix. Storage quotas/migration, video import,
the full relationship taxonomy and later Graph/Model work remain explicitly
separate even after that minimum path passes.

## 30. Evidence and single-owner catalog

| Evidence | Actual source owners and representative existing verification source |
|---|---|
| <a id="e01"></a>E01 | [RepositoryBundle](app/repositories/bundle.py), [NovelService](app/services/novel_service.py), [File novel](app/repositories/file/novel.py), [PostgreSQL novel](app/repositories/postgres/novel.py), [scope service](app/services/collaboration_scope_service.py), [authorization](app/services/authorization_service.py). |
| <a id="e02"></a>E02 | [Creative models](app/creative/models.py), [service](app/creative/service.py), [project store](app/creative/project_store.py), [API](app/creative/api.py); [foundation tests](tests/test_v2_creative_foundation.py), [workflows](tests/test_v2_creative_workflows.py), [lifecycle](tests/test_v2_creative_project_lifecycle.py), [UI](frontend/src/creative/CreativeWorkspace.test.tsx). |
| <a id="e03"></a>E03 | [AssetLibraryService](app/services/asset_library_service.py), [original API](app/api.py), [lifecycle](app/asset_lifecycle_api.py); [asset tests](tests/test_asset_library.py), [safety](tests/test_asset_safety.py), [recovery](tests/test_asset_lifecycle_r2.py). |
| <a id="e04"></a>E04 | [ProductionLineageService](app/experimental/production_lineage.py), [change impact](app/experimental/change_impact.py), [original DAG](app/services/asset_library_service.py); [lineage tests](tests/test_r4_production_lineage.py). |
| <a id="e05"></a>E05 | [original workflow host](app/services/v1_capability_service.py), [workflow API](app/workflow_api.py), [declarative adapter](app/experimental/declarative_agents.py), [adapter SDK](app/experimental/declarative_adapter_sdk.py); [execution tests](tests/test_r2_workflow_execution.py), [host seam tests](tests/test_declarative_workflow_host_seam.py). |
| <a id="e06"></a>E06 | [First use](app/experimental/first_use.py), [UX](app/experimental/ux.py), [templates](app/experimental/template_library.py), [EntryExperience](frontend/src/novel/EntryExperience.tsx); [workspace UX tests](tests/test_post_interop_workspace_ux.py). |
| <a id="e07"></a>E07 | [ModelCenter](app/model_center/service.py), [discovery](app/model_center/discovery.py), [environment](app/model_center/discovery_environment.py), [bridge](app/model_center/discovery_bridge.py), [HardwareInventory](app/provider_runtime_v2_host_hardware_inventory.py); [ModelCenter tests](tests/test_model_center_phase1.py), [phase2](tests/test_model_center_phase2a.py), [snapshot bridge](tests/test_provider_runtime_v2_model_center_snapshot_bridge.py), [discovery report](LOCAL_AI_DISCOVERY.md). |
| <a id="e08"></a>E08 | [Broker](app/experimental/model_broker.py), [profiles](app/experimental/provider_profiles.py), [JobManager](app/jobs.py), [AuthorRequest](app/author_request.py), [Vault](app/credential_vault.py); [broker tests](tests/test_r4_model_broker.py), [cancel/dispatch](tests/test_r4_broker_cancel_dispatch.py). |
| <a id="e09"></a>E09 | [creative proposals](app/creative/proposals.py), [creative generation coordinator](app/creative/generation.py); [workflows](tests/test_v2_creative_workflows.py), [Director model UI](frontend/src/creative/DirectorModelControls.test.tsx). |
| <a id="e10"></a>E10 | [packaged path owner](app/packaging/paths.py), [atomic write](app/storage.py), [PortableProjectsService](app/experimental/portable_projects.py); [portable maintenance](tests/test_r4_portable_maintenance.py), [portable batches](tests/test_r4_portable_batches.py), [Windows plan](LOCAL_AI_WINDOWS_ACCEPTANCE.md). |
| <a id="e11"></a>E11 | [MediaService/registry](app/experimental/media.py), [AssetProviderRegistry/adapters](app/asset_providers.py), [AssetTaskWorker](app/services/asset_task_worker.py), [media validator](app/media_files.py), [frame helpers](app/media_frames.py); [media workflows](tests/test_r3_media_workflows.py), [adapter tests](tests/test_asset_provider_adapter.py), [media engine tests](tests/test_surface_freeze_media_engine_adapters.py). |
| <a id="e12"></a>E12 | [protocol](LOCAL_INTEROP_PROTOCOL_V1.md), [security](LOCAL_INTEROP_SECURITY.md), [Desktop mapping](QINGJIAN_DESKTOP_MAPPING_CHECKLIST.md), [host](app/local_interop/host.py), [provider](app/local_interop/provider.py), [integration UI](frontend/src/interop/LocalTutorIntegration.tsx); [contracts](tests/test_local_interop_contracts.py), [desktop tests](tests/test_local_interop_desktop_runtime.py). |
| <a id="e13"></a>E13 | [task projection owners](app/experimental/workspace_task_owners.py), [UX service](app/experimental/ux.py), [author task projection](app/experimental/author_task_projection.py); [workspace UX tests](tests/test_post_interop_workspace_ux.py). |
| <a id="e14"></a>E14 | [ImageInfiniteCanvas](frontend/src/novel/ImageInfiniteCanvas.tsx), [multimodal persistence](frontend/src/novel/useMultimodalWorkspacePersistence.ts), [CreativeCanvas](frontend/src/creative/CreativeCanvas.tsx); [canvas tests](frontend/src/novel/ImageInfiniteCanvas.test.tsx). These are not a typed executable Creative Graph. |
| <a id="e15"></a>E15 | [DirectorService](app/experimental/director.py), [ScreenplayService](app/services/screenplay_service.py), [creative models](app/creative/models.py), [DirectorShotList](frontend/src/novel/DirectorShotList.tsx), [DirectorPanel](frontend/src/experimental/DirectorPanel.tsx); [shot tests](frontend/src/novel/DirectorShotList.test.tsx), [screenplay CAS](tests/test_screenplay_cas_history.py). |
| <a id="e16"></a>E16 | [audio providers](app/audio_providers.py), [audio production store](app/audio_production_store.py), [AudiobookService](app/services/audiobook_service.py), [voice direction](app/experimental/voice_direction.py), [audiobook](app/experimental/audiobook.py); [audio provider tests](tests/test_audio_providers.py), [audio API tests](tests/test_audio_production_api.py). |
| <a id="e17"></a>E17 | [VideoAssemblyService](app/services/video_assembly_service.py), [subtitle timeline](app/experimental/subtitle_timeline.py), [OTIO exchange](app/experimental/timeline_exchange.py), [VideoTimeline](frontend/src/novel/VideoTimeline.tsx), [ProductionTimeline](frontend/src/creative/ProductionTimeline.tsx); [VideoTimeline tests](frontend/src/novel/VideoTimeline.test.tsx), [production tests](frontend/src/creative/ProductionTimeline.test.tsx). |
| <a id="e18"></a>E18 | Nearest future 3D seams: [asset owner](app/services/asset_library_service.py), [media operation schema](app/experimental/media.py), [Director camera grammar](app/experimental/director.py). Audited source has no supported GLB/glTF/OBJ/FBX/USD parser, Blender/UE bridge or 3D Studio acceptance path. |
| <a id="e19"></a>E19 | [ResearchLibrary](app/experimental/research_library.py), [extraction](app/experimental/research_extract.py), [vision](app/experimental/research_vision.py), [embeddings](app/experimental/embeddings.py), [vector index](app/experimental/vector_index.py), [World](app/experimental/world.py), [StoryGraph](app/experimental/story_graph.py); [research tests](tests/test_r4_research_library.py), [extract tests](tests/test_r4_research_extract.py), [embedding adapter tests](tests/test_post_interop_wave3_embedding_adapter.py). |
| <a id="e20"></a>E20 | [ChapterService](app/services/chapter_service.py), [AdaptationService](app/services/adaptation_service.py), [adaptation API](app/adaptation_api.py), [memory](app/services/memory_service.py), [user preferences](app/services/user_preference_service.py), [continuity](app/services/continuity_finding_service.py), [Editor](frontend/src/Editor.tsx); [branch screenplay tests](tests/test_screenplay_branch_revision.py), [screenplay PostgreSQL tests](tests/test_screenplay_cas_postgres.py). |
| <a id="e21"></a>E21 | [collaboration API](app/collaboration_api.py), [branch manuscript](app/repositories/branch_manuscript.py), [teams](app/experimental/teams.py), [writer room](app/experimental/writer_room.py), [offline sync](app/experimental/offline_sync.py); [realtime/sync boundary](docs/delivery/functional-surface-freeze/REALTIME_AND_SYNC.md). |
| <a id="e22"></a>E22 | [design system](docs/ui/design_system.md), [protected surfaces](docs/ui/protected_ui_surfaces.md), [AppShell](frontend/src/ui/AppShell.tsx), [tokens](frontend/src/ui/tokens.css), [V2 UI report](docs/delivery/v2-development/creative-workbench-ui.md), [CreativeWorkspace tests](frontend/src/creative/CreativeWorkspace.test.tsx). |
| <a id="e23"></a>E23 | [ExportJobService](app/services/export_job_service.py), [NovelService exporters](app/services/novel_service.py), [industry formats](app/industry_export_formats.py), [PortableProjects](app/experimental/portable_projects.py), [creative export](app/creative/service.py); [resource package tests](tests/test_export_resource_packages.py), [portable mounted tests](tests/test_r4_portable_batches_mounted.py). |
| <a id="e24"></a>E24 | [Agent catalog](app/agent_catalog.py), [Agent runner](app/agents.py), [AgentJobService](app/services/agent_job_service.py), [declarative agents](app/experimental/declarative_agents.py), [safe adapter SDK](app/experimental/declarative_adapter_sdk.py); [declarative model tests](tests/test_r5_declarative_model.py). |
| <a id="e25"></a>E25 | [current PR 47 body](https://github.com/1785235376-blip/AI-Novel-Studio/pull/47), [4350 PR Cloud CI](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37907528214), [4350 push Cloud CI](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37907521986), [existing evidence index](docs/delivery/v2-development/cloud-v2-evidence-index.md), [M0 ledger](MILESTONE_M0_REPORT.md). |
| <a id="e26"></a>E26 | [flags](app/experimental/flags.py), [V1 freeze](V1_SCOPE_FREEZE.md), [original historical matrix](POST_INTEROP_FEATURE_MATRIX.md), [continuation report](POST_INTEROP_R4_R5_CONTINUATION_REPORT.md), [compatibility/rollback](docs/delivery/post-interop-continuation/COMPATIBILITY_AND_ROLLBACK.md). |

[E01]: #e01
[E02]: #e02
[E03]: #e03
[E04]: #e04
[E05]: #e05
[E06]: #e06
[E07]: #e07
[E08]: #e08
[E09]: #e09
[E10]: #e10
[E11]: #e11
[E12]: #e12
[E13]: #e13
[E14]: #e14
[E15]: #e15
[E16]: #e16
[E17]: #e17
[E18]: #e18
[E19]: #e19
[E20]: #e20
[E21]: #e21
[E22]: #e22
[E23]: #e23
[E24]: #e24
[E25]: #e25
[E26]: #e26

## 31. Append-only M1 delta — 2026-10-09 13:00 UTC

**Full M1: PARTIAL.** The 325 M0 inventory rows above remain unchanged, including
**47 EXISTS / 196 PARTIAL / 60 MISSING / 7 BLOCKED / 15 LOCAL_REQUIRED**. The delta
below does not silently promote those baseline classifications. Source baseline:
`0df2640c4c1a2d3052bb0a84d14445744d04046f`; M1 is uncommitted at this checkpoint,
with no end SHA or published M1 CI claimed. Detailed contracts, exact receipt
links, preserved failures and unmet requirements: [M1 report](MILESTONE_M1_REPORT.md).

| Baseline requirement IDs | M1 implemented delta | Current evidence / remaining gap |
| --- | --- | --- |
| CORE-01/08/10; START-08 | Blank/neutral original project entry and independent manual IMAGE/VIDEO/AUDIO/ASSETS consumer; no compulsory chapter/model/graph. | Real decoded image/video/audio owner roundtrips and current unit contracts verified. Actual image/video file-picker, reopen/export browser acceptance **PENDING**. Full independent Studios remain **PARTIAL**. |
| CORE-03/04; START-07 | Bounded multiple/empty/custom intents and preset metadata, CAS and saved-preference UI. | Unit-tested preservation of modules and absence of implicit mutation on local selection. Applied preset-specific layouts/suggested graphs **MISSING**; no permission or execution authority derives from intent. |
| CORE-11/12/13; IMAGE-05 | Original asset ID/version/digest, actual media validation, author-declared external provenance/license and original-byte export. | Selected File/PG regressions pass. 25 MiB/asset and 512 MiB/scope bounds; declaration is a second write. Full cross-kind/generated-job catalog, large-media handling and transcode/export formats remain **PARTIAL**. |
| CORE-18/19 | Original-owner project-incarnation/exact-scope fences, old-route denial, feature/V1 exclusion and redaction. | Included in selected original-owner regressions. No automatic adoption of old unbound assets. Final hosted/source-bound gates still pending. |
| CORE-15/16/20/21 | Seven optional typed relationships, existing-parent constraints, version/digest snapshots and redacted current-state projection; original Chapter/Screenplay read-only bridge. | Integrated and original-owner File/PG plus frontend units pass. Browser acceptance remains pending. This list/overview is neither an executable M2 canvas nor a completed knowledge graph. |
| CORE-17 | Version-aware trash/restore, original dependencies and new active incoming-relation protection; relationship removal tombstones. | Bounded lifecycle regressions pass. General retention/purge/physical cleanup **PARTIAL/MISSING**. |
| CORE-09; START-09; STORE-01/02/10 | Existing packaging/storage owners retained; browser download destination; descriptive storage category projection. | No new configurable project/model/cache/export directory contract or default export path. Full path management/migration **PARTIAL/MISSING**. |
| STORE-03 | Current bound-asset active/trash record counts/bytes; trash consumes quota. | Not total disk occupancy across DB/history/proxies/cache/filesystem allocation; original unbound assets excluded from this view. **PARTIAL**. |
| STORE-04/09 | Real asset-filesystem free-space estimate, 64 MiB reserve, import-byte preflight, recheck and fail-closed 507; truthful capacity UI. | Current negative tests pass in File/PG and units. No task-sized reservation or running-job low-space pause/resume. **PARTIAL**. |
| STORE-05/06 | Existing import quotas and narrowly scoped original portable-export-cache cleanup retained. | No generalized cache/proxy/thumbnail limits or Studio preview-confirm cleanup. Do not reclassify narrow M0 STORE-06 EXISTS as a full Storage Manager. |
| STORE-07/08 | Existing original roots remain authoritative and are not automatically moved or cleaned. | Verified reference/copy migration, interruption journal/recovery and safe rollback **MISSING** for full Studio storage management. External model files are never cleanup targets. |
| GATE-M1 | Implemented minimum no-model path plus original-owner regression and corrected frontend/build evidence. | **PARTIAL**: actual browser/visual proof, full storage/preset semantics and final published source/CI receipts remain open. Safe nondependent M2/M3 may proceed; dependent operations remain blocked. |

Evidence checkpoint: File **1,047 passed / 954 skipped**; actual PG 17.11
**1,011 passed / 987 skipped**, normal shutdown; corrected frontend **1,773 passed
/ 8 existing skips**; corrected TypeScript/Vite/token **PASS**; catalog check
**3 passed**. Each receipt is source-stable and separately scoped; backend runs
are selected regressions, not the full manifest. The mounted API catalog has
**2,077 operations**, M1-only delta **+34 / −0**. Independent collection review
is **INVENTORY_ONLY**: **9,809 collected**, original **9,151** preserved in order,
**658** additions relative to the frozen baseline, historical skips unchanged;
no claim those 9,809 nodes executed.

All earlier failures remain archived, including M1's test-fixture/assertion/build
failures and the distinct M0 push browser failure with **403 TRACE_ACCESS_BLOCKED**.
M0 hosted CI was still `IN_PROGRESS_WITH_NONPASS` at its persisted 12:49 checkpoint.
Historical `PARTIAL_CI_CAPACITY`, `39 PARTIAL + F00 INTEGRATED`, independent-review
`BLOCKED` and M12 `USER_APPROVAL_REQUIRED / LOCAL_REQUIRED / NOT_RUN` remain intact.

## 32. Final M1 evidence delta: strict asset revisions

The M0 inventory and §31's 13:00 snapshot remain unchanged. Final
`IndependentWorkspaceService._row` adds a V2-only positive-actual-integer revision
boundary; seven corrupt values across both profiles are covered without changing
legacy owner semantics or repairing data implicitly. RED is **7 failed / 7 skipped
/ 150 deselected**; final focused File and actual PG 17.11 are each **215 passed /
186 opposite-profile skipped**, unchanged-source, with normal PG shutdown. This
strengthens bounded CORE-11/12/18/19 version/identity safety; it does not complete
every asset kind or full M1.

Earlier **1,047/1,011** owner-regression passes and **1,773/8** frontend evidence
are **pre-final-guard snapshots**. They are not advertised as a full regression
of the final backend adapter. Final catalog generation is **2,077 operations,
M1 +34/−0**, fingerprint
`a06abe220e300bad702981085001c7bd0259ba6d81a519bb3f855c1f8db56292`.
Final API catalog check is **3 passed**; coverage infrastructure **174 passed**.
Actual final inventory has **9,823 nodes**, including exactly 14 new corruption
variants since 9,809, original 9,151 ordered nodes and historical skips preserved.
Written manifest SHA256
`3e86bfabbdcb2c494968cf89d6efdd3ff2cc10edf921fa47f6a9669474dfce9f`
is verified; collection remains **INVENTORY_ONLY**, not execution. Detailed receipts:
[M1 report §11](MILESTONE_M1_REPORT.md#11-final-metadata-guard-delta-and-bounded-m1-closure).

**GATE-M1 remains PARTIAL**, bounded minimum-path closure only. Local browser is
**BLOCKED**, hosted current-M1 browser **NOT_RUN**, visual acceptance unverified.
Storage migration/recovery, generalized cache cleanup/limits, global reservation,
running-job low-space pause and applied presets remain missing/partial. Safe
nondependent M2/M3 work can continue while dependent operations remain blocked.
No final published SHA or user-Windows acceptance is claimed.

Separate M0 terminal state is [preserved](docs/delivery/v2-development/m0-ci-terminal.json):
push Cloud **FAILURE** and PR Cloud **CANCELLED**, including failed PR File/PG
aggregates despite PG execution success. Prior local Chromium socket denial / SIGABRT
explains the carried browser environment block; no new M1 local attempt or trace
retrieval around the M0 **403 TRACE_ACCESS_BLOCKED** occurred.

## 33. Append-only M2-A development delta

Checkpoint **2026-10-09 13:50 UTC**, baseline M1
`57986cb13d452731baf82bbc242bfc79f9cfd145`; M2 is uncommitted, **PARTIAL**.
All 325 M0 rows and preceding M1 snapshots remain unchanged. This delta describes
implemented source, not a final promoted status or full-stage test verdict.
See [M2 report](MILESTONE_M2_REPORT.md) for exact owners and execution evidence.

| M0 IDs | Implemented M2-A slice | Remaining gap |
| --- | --- | --- |
| GRAPH-01/11/15 | Closed seven-node/four-port graph registry, empty actor-private scoped graph, strict typed edges and CAS persistence. | Full multimodal port/adapters, shared ordinary/professional views; original Project/Asset/Workflow owners remain authoritative. |
| GRAPH-02/03/07 | Positioned node canvas, pan/zoom, marquee/multiselect, keyboard movement, typed port buttons/form connection and invalid-edge feedback. | Drag-to-connect, richer highlighting/conversion/error focus, actual browser/a11y/visual acceptance. |
| GRAPH-04/05/06/08/09/10 | Explicit save/reopen, in-memory undo/redo, conflict/dirty guards and bounded deletion. | Persistent draft autosave/reload recovery, command search, copy/paste/groups/MiniMap/templates and large-graph performance remain missing/partial. |
| GRAPH-12/13/14/16 | Original WorkflowRun host executes local text/rule/manual outputs; optional Director note and exact human review. | No JobManager/provider/model dispatch, generated-asset lineage, Asset Save/Export/Timeline adapter or professional Console/Tutor. |
| GRAPH-17/18/19/21/22 | Selected dependency closure/preflight, explicit queued execution, original review/pause/resume/cancel and fixed admission deadline. | Model capability/cost/privacy admission, parallel/VRAM scheduling, provider retry/cancellation reconciliation and full resource UI. |
| GRAPH-20 | Same-version, same-owner reviewed-ancestor local output cache; approval never reused. | Cross-version descendant invalidation, binary cache and storage cleanup/reservation absent. |
| CORE-17; GRAPH-11/14 | Asset reference displays original ID/version/digest and CURRENT/STALE/UNAVAILABLE state. | It is metadata, not an original parent/provenance/dependency edge. No graph-aware strong delete guard, atomic input CAS or output publication; saved detach/rebind and selected execution are blocked. |
| GATE-M2 | Independent manual graph foundation with no compulsory Director/model/chapter. | **PARTIAL**: actual image generation/material conversion, missing graph features/adapters and final integrated/browser gates remain open. |

Finite bounds are 16 nodes, 40 edges, **96,000/64,000 decimal bytes** for graph
and output, 25 graphs/100 runs/20 history entries. Original run deadline is
3,600 seconds from admission; node budget 5 seconds. These are not CI budget
changes, large-graph performance proof or M1 Storage Manager completion.

Verified development receipts include **257 passed / 44 PG deselected** for the
latest File/contracts deadline slice; first API **16 passed / 16 skipped** is an
earlier snapshot. Preserve the 241-pass run's explicit source drift and the wrong
interpreter's `No module named pytest` failure. Final integrated counts, actual
PG, full frontend/build, browser and current hosted M2 remain pending. The
separate M1 compatibility/media correction preserves its first TCP/browser
failures and **403 TRACE_ACCESS_BLOCKED** artifact, not a new whole-CI PASS.

### 33.1 Terminal-check delta, 13:55 UTC

Full frontend **1,923 passed / 8 existing skips**, build/token **PASS**, and
**279 CI-infrastructure/catalog checks** now have agreeing source-stable receipts.
Mounted API File **20 passed / 20 skips** is a separate earlier snapshot.
Current catalog **2,107 operations, +30/−0**; collection **10,178 nodes** is
inventory only, preserving original 9,151 order and skips. Written manifest,
integrated File/PG and actual browser/visual remain pending. See the
[M2 report](MILESTONE_M2_REPORT.md); none of these results promotes full GATE-M2.

### 33.2 Integrated File update, 13:59 UTC

[Original-owner File](docs/delivery/v2-development/stage-m2-integrated-owner-file.json)
finished **PASS: 1,490 passed / 1,098 skipped**, 299.01 seconds. It selects 33
original-owner/M1/M2/media-contract files; it is not the full backend manifest.
The stable 1,660-input map matches frontend/build/279-check evidence. Real PG
remains pending; no profile combination, browser PASS or full M2 completion is
inferred. Exact log/source binding is in [M2 report](MILESTONE_M2_REPORT.md).

### 33.3 Written inventory update, 14:01 UTC

[Manifest review](docs/delivery/v2-development/stage-m2-manifest-change-review.json)
and [independent recollection/write](docs/delivery/v2-development/stage-m2-manifest-written.json)
verify **10,178 nodes = M1 9,823 + 355**, preserved old order/skips/external gates,
and actual manifest SHA256
`acefe60873bd452ff663b254cb4c25a910c99dcb140732171105b7ba0b687d62`.
The frozen manifest remains unchanged. [Actual browser collection](docs/delivery/v2-development/m2-browser-inventory-review.json)
retains all prior 12 cases: **7 original + 8 independent (5 M1 + 3 M2)**, no overlap.
Both are **inventory only**; no browser launched or full backend execution inferred.
Real PG completion remains pending at this observation.

### 33.4 Current M2-A evidence summary, 14:07 UTC

Selected 33-file owner regression is terminal in both profiles: File **1,490
passed / 1,098 skipped**, real PG 17.11 **1,457 passed / 1,131 skipped**, normal
shutdown. Their stable 1,660-input maps match full frontend **1,923/8**, build/token
PASS and **279** infrastructure/catalog passes. Inventory remains distinct:
10,178 backend nodes and 7+8 browser cases were collected, not all executed.
[M2 report](MILESTONE_M2_REPORT.md) contains the final binding; **GATE-M2 remains
PARTIAL**, current hosted/browser NOT_RUN and visual acceptance unverified.
Final end SHA is deferred to the actual PR publication receipt. M0/M1 inventory,
all failures and M12 approval boundary remain unchanged.

## 34. Append-only M3-A host authority and consent delta

**2026-10-09 14:44 UTC; development source, full M3 PARTIAL.** Parent HEAD
`99c43b6892038233c390be2ae61acb669163d0b5`, tree
`69d69ffe71838263069d164a0a07b39b5f4a4333`. Original baseline rows and all earlier
milestone deltas remain unchanged. [M3 report](MILESTONE_M3_REPORT.md) supplies
source owners, exact bounds and per-run evidence rather than rewriting M0 status.

| Baseline IDs | Current source advancement | Remaining boundary |
| --- | --- | --- |
| START-02; MODEL-01/02/03/04 | Host-authorized preview and explicit strict-digest confirmation over existing discovery; known/saved loopback services; common roots default false; configured/registered file and executable metadata fully disclosed. | Development-only checks; actual Windows/runtime observation LOCAL_REQUIRED. No whole-disk, LAN/public or generic port scan. |
| START-03; MODEL-07/09 | Preview, Detect, Validate, Register, configuration/license review and Enable stay distinct; inference explicitly NOT_RUN. | Metadata/protocol checks never establish working inference, model fit or quality; full lifecycle projection remains PARTIAL. |
| START-05/06; MODEL-08/19/20/21 | Model Center can preview existing configuration or skip; advanced path/port forms and current blockers remain available. | Complete needs-driven sources/licenses/sizes/dependencies/install/download/resume/cleanup guidance remains PARTIAL/MISSING. |
| MODEL-05/10/12/13/14/15/17/18 | Original modality adapters and hardware inventory reused; unknown facts preserved. | Complete component validation and measured 8/12/16-GB profiles, actual generation/quality still missing or LOCAL_REQUIRED. |
| MODEL-23/24/25/26 | Broker, Vault, routing and budget owners preserved; no paid fallback or credential creation. | Full optional API consent/budget/reconciliation journey and paid proof not supplied by discovery. |
| GATE-M3 | Useful bounded M3-A host-private onboarding foundation. | **PARTIAL**. Source freeze, integrated final receipts, browser acceptance and full model/API scope still open. |

This is an intentional discovery compatibility/security tightening: all production
routes, cached reads included and V2 off included, require actual current Host
provenance. Nonpackaged project collaboration alone is rejected. The separate
shared Model Center role helper is unchanged. Before/after/precommit rechecks and
original trusted-session binding generations fence stale authority; a digest is
not a new access credential. Scanning may disable and persist stale registrations,
which is disclosed before consent; it is not an observation-only guarantee.

Verified development subsets include first cache reproduction **4 FAIL**, later
**23 PASS**, host-authority **296 PASS**, mounted precommit **23 PASS**, mutation
**223 PASS** and newest service/legacy **215 PASS**. Their overlapping, differing
source maps must not be summed or promoted to final integrated evidence. M3 final
File/real-PG/full frontend/build/catalog/manifest and hosted/browser are pending;
user Windows/inference remain NOT_RUN. Separate published M2 independent-media
jobs each retained **6 PASS / 2 FAIL**; the select-label correction's unit evidence
does not establish hosted/browser revalidation. See report §§5–7 for exact limits.

### 34.1 Bounded planning delta, 14:55 UTC

START-02 / MODEL-01–04 now also have a **5-second cooperative preview/replanning
budget** and at-most-50-ms owner-lock wait intervals with live guard checks.
`planning_budget_seconds` and `LOCAL_AI_SCOPE_BUDGET_REACHED` expose the bound;
45-second scanning and 120-second consent TTL are unchanged. The latest
[224-pass development receipt](docs/delivery/v2-development/m3-scope-planning-dev-01.json)
records concurrent addition of a browser-fixture test (1,673 → 1,674 inputs), so it
is not final-source proof. No browser has executed; full M3 remains PARTIAL.

### 34.2 Frozen-source evidence delta, 15:05 UTC

Final local source map is **1,676 inputs** (`aefdbfd9884879ab2e17b42754c8ae7cbb6ecd54de4b8e192c9b158e6fe22259`).
Stable agreeing receipts now show frontend **1,981 PASS / 8 existing skips**,
build/45-file token **PASS**, complete infrastructure/catalog **279 PASS** and
current-discovery catalog-owner regression **3 PASS**. Catalog has **2,111
operations, M3 +4/−0**; written backend inventory is **10,335 = 10,178 + 157**,
with all published old nodes/order/test/gate/skip contracts preserved. Actual
browser list output is **7 original + 11 independent**, not execution. See
[M3 report §9](MILESTONE_M3_REPORT.md#9-source-freeze-and-terminal-local-checks--2026-10-09-1505-utc)
for exact hashes. The selected 52-file File/real-PG integration remains pending;
full M3 PARTIAL and all real-model/user-Windows/paid-provider boundaries remain.

### 34.3 Integrated File update, 15:08 UTC

The [52-file selected File owner run](docs/delivery/v2-development/stage-m3-integrated-owner-file.json)
finished **2,082 PASS / 1,099 skips** (1,098 opposite-profile + one existing actual
Windows native check), 310.49 s, on the matching stable 1,676-input map. It is not
full-manifest/Windows/browser execution. Real PG remains pending; full M3 stays
PARTIAL. [M3 report §9.5](MILESTONE_M3_REPORT.md#95-integrated-file-result-1508-utc)
retains exact evidence and skip boundaries.

### 34.4 First integrated PG failure retained, 15:20 UTC

M3 real-PG selected integration is **FAIL: 2 failed / 2,047 passed / 1,132 skips**,
811.97 s, despite stable matching 1,676-input maps. Two unchanged original workflow
API tests failed on missing create-response `id`; diagnosis and normal-stop
verification remain pending. The transient evidence transport disconnect did not
restart tests or change source. Separately, the final M2 hosted manifest records
both Cloud events FAIL (File incomplete; PG execution successful but aggregate
prerequisite FAIL), with narrower passing browser/TCP/Windows/Interop selections.
[M3 report §§10–11](MILESTONE_M3_REPORT.md#10-terminal-published-m2-hosted-record--2026-10-09-1520-utc)
keeps each evidence level distinct. GATE-M3 remains PARTIAL; no PG aggregate or
full-roadmap completion is inferred.

### 34.5 Confirmed PG harness isolation issue, 15:24 UTC

The two first-PG failures are now traced to reused test data: SQL shows both
fixed-title rows created at 14:04:35 UTC during M2; the unchanged original API
correctly returns 409. The first diagnostic's unused-import failure is retained,
and the corrected diagnostic proves the conflict. Normal original-run shutdown
is verified at 15:15:57 UTC. [M3 report §11.1](MILESTONE_M3_REPORT.md#111-confirmed-reused-database-cause-and-normal-shutdown-1524-utc)
records hashes and exact evidence. A narrow runner-only fresh-database mode and
new isolation tests are being prepared, preserving existing data and original
assertions/titles. New source freeze and complete selected checks are required;
the first failed run and prior 1,676-input results remain historical, not rewritten.

### 34.6 Fresh-source File and local-check checkpoint, 15:42 UTC

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

### 34.7 Final local M3-A checkpoint, 15:47 UTC

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

## 35. Append-only M3-B file-observation delta

This updates evidence for only the rows below; original row text remains the
historical baseline. Source, tests, retained failures and execution limits are in
[MILESTONE_M3B_REPORT.md](MILESTONE_M3B_REPORT.md).

| Row | Current M3-B delta; status boundary |
| --- | --- |
| START-03 / MODEL-04 | **EXISTS**, now exposed in the V2/schema-2 Model Center view from the existing scan. Files/indexes, runtime candidates and generation evidence are visibly distinct. Metadata/header checks still do not verify weights or inference. |
| MODEL-05 | **PARTIAL**. Format, exact file/index byte size and family/capability hints are displayed. Diffusers size/path are only `model_index.json`; complete component/runtime compatibility is not established. |
| MODEL-06 | **PARTIAL, unchanged**. Path-based IDs and separate locations are retained. No content digest grouping, cross-location deduplication or physical merge is implemented. |
| MODEL-09 | **PARTIAL**. Same-scan candidate/registration associations, authorized-route state, unknown binding, missing/partial observations and uncertain registration state are projected honestly. Complete unified lifecycle vocabulary remains open. |
| MODEL-01 / MODEL-07 / STORE-02 | **EXISTS, preserved**. Original discovery/registry owners and explicit register/configure/enable/dispatch boundaries remain; the new view never copies weights or triggers actions. |

No broader MODEL/install/API/hardware or GATE-M3 row is promoted to complete.
New browser collection is inventory only; current source and published M3-A hosted
results retain separate identities. Full M3 remains **PARTIAL**.

The [corrected-source continuation](MILESTONE_M3B_REPORT.md#12-corrected-source-freeze-and-terminal-frontend-checks--1634-utc)
adds **START-02 / MODEL-02 (still PARTIAL)** compatibility evidence for legal
legacy host scanning and **MODEL-09 (still PARTIAL)** all-mode private-state
purging on denial/owner change. It restores existing owner reuse rather than
expanding host access. Browser 7+14 remains inventory only at that checkpoint.

The [final local M3-B ledger](MILESTONE_M3B_REPORT.md#12-corrected-source-freeze-and-terminal-frontend-checks--1634-utc)
now includes matching 56-file File/real-PG passes. Written 10,380-node and 7+14
browser inventories remain inventory only. No additional feature status or
GATE-M3 status is promoted by these results.

## 36. Append-only M3-C prerequisite-observation delta

[M3-C report](MILESTONE_M3C_REPORT.md) records the same-scan extension and its own
verification identity. **MODEL-05 and MODEL-09 remain PARTIAL**: exact ComfyUI
workflow node/loader advertisements now distinguish observed, not_observed and
unknown, while the original catalogue's component requirements remain unknown
without identity evidence. Valid bounded absence is not machine-wide absence;
complete response inspection is not component integrity or inference.

**MODEL-01 / MODEL-07 remain preserved**: original Model Center/discovery/consent
owners, registration, enablement and routing remain authoritative. The read-only
view introduces no second inventory, scan, install or model action. MODEL-06
content deduplication, complete compatibility, hardware profiles, install/API
workflows and GATE-M3 remain partial. Actual Windows/inference remain NOT_RUN.

[M3-B terminal CI](docs/delivery/v2-development/m3b-ci-terminal.json) retains both
Cloud FAIL outcomes, incomplete File execution and failed strict joins, plus
11-pass/3-fail independent media. Its new fixture correction has separate
source-contract evidence; neither old CI nor collection validates M3-C.

## 37. Append-only M4 AI Execution Layer delta

The current user-defined M4 scope is AI Execution Layer; historical feature rows
and the former M4 roadmap label remain unchanged as history. The six-module
owner/API/UI map is in [the execution contract](docs/v2/ai-execution.md), and
actual verification/remaining acceptance is in [M4 report](MILESTONE_M4_REPORT.md).

- Model Provider Adapter and local invocation reuse original TextModelNode,
  provider/model registries and enabled external Ollama/llama.cpp routes.
- Model Router is a thin original ModelBroker facade, with explicit exact route,
  capabilities/license/zero-price checks and no fallback.
- Creative Graph Node Runtime bridges one schema-2 text node to original
  WorkflowRun and JobManager. No chapter, second queue or second model registry
  is created. Human review exposes a proposal and never applies manuscript/Canon.
- APIProvider is **RESERVED**, not executable. Scheduling remains **PARTIAL**:
  existing project admission and dependency ordering, without global fairness,
  hardware allocation or measured inference performance.

These bounded changes do not complete the broader MODEL/API/install/hardware
rows, Image/Video execution, or GATE-M3. Real local inference/quality and actual
user Windows/GPU acceptance remain **NOT_RUN / LOCAL_REQUIRED**. M3-C's inherited
**PARTIAL_PR_CI_CAPACITY** and historical independent review **BLOCKED** persist.

## 38. Append-only M4-B provider and text-asset delta

[M4-B report](MILESTONE_M4B_REPORT.md) records this separate checkpoint and its
source-bound results. Original owners and historical feature rows are preserved.

- Uniform provider capability/availability/execution/result contracts and scoped
  task matching are **PARTIAL**: Ollama/llama.cpp reuse authorized local routes;
  LM Studio has tested codecs but trusted locality is unverified. ComfyUI,
  image/video and API remain declared/reserved, without automatic fallback.
- Hardware matching is advisory total RAM/VRAM filtering, not measured free
  capacity, model-fit validation or a global scheduler.
- Current TextNode UI execution archives every accepted result through original
  AssetLibraryService as a private DRAFT v1 before original human review. Review
  projects APPROVED/REJECTED v2; original reads/refresh recover bounded storage
  gaps without inference replay or added steps. This does not migrate historical
  clients or implement edited text-content versions, manuscript or Canon apply.
- Real local inference/quality remains NOT_RUN; actual user Windows/GPU remains
  LOCAL_REQUIRED. Historical PARTIAL_PR_CI_CAPACITY and independent review BLOCKED
  remain. Full M4 and broader MODEL/API/install/image/video gates are not promoted.

## 39. Append-only M4-C real CPU text delta

[M4-C report](MILESTONE_M4C_REPORT.md) records the first actual owned CPU
TextNode → original Router/JobManager → private TextAsset v1 → review v2 run,
using official Qwen GGUF and llama.cpp. Exact prompt/parameters/model evidence
and Workflow/settlement receipts are persisted and shown in the existing UI.
Repeated admission/reads do not replay inference; manuscript/Canon remain untouched.

This replaces the **NOT_RUN** boundary only for that explicit local CPU text
acceptance case. Other model families, quality, real-model browser flows,
Windows/GPU and full hosted CI remain separately qualified in the report.
API/Image/Video/global scheduling remain reserved or partial. The historical
M4-B File-capacity cancellations and independent-review BLOCKED are preserved.

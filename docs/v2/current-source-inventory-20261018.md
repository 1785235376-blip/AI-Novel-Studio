# Current pinned source inventory — 2026-10-18

Source: `2a6f0793067213592c5462b571505a3c1edf8f05`; tree: `bbdbde3b4ba6377910d7a884fdd60880b67d782a`.

This is a structural owner inventory and a bounded correction index. It is not
a new full functional audit, product acceptance, or completion percentage. The
historical matrices remain unchanged. Every unreviewed historical gap is explicitly
labelled as historical in the JSON rather than silently asserted to remain missing.

## Scope and result

- 40 original F/A/B/U IDs, 22 Graph IDs, 6 Console IDs and 33 additional CORE/FS IDs.
- All 101 unique IDs are represented; all named source references exist at this pin.
- Individual files include Git blob identity, SHA-256 and last modifying commit.
- Directories record tracked-file counts, not a claim that every file was audited.
- Bounded recent observations are added to relevant rows without changing global status.
- Runtime availability and source existence never imply dispatch authorization.

## Material current-source findings

Older table prose still calls pointer connection, insertion, visual grouping and
draft recovery absent. Their actual implementation and tests are now present.
Use the current files and reports listed here before selecting more development.
Do not add another graph, draft or workflow owner to satisfy stale wording.

Research OCR/vision is a different case: current `ReviewAdapterJobs.run` explicitly
rejects non-MOCK_ONLY providers with `ADAPTER_MODEL_ADMISSION_NOT_CONFIGURED`.
Real adapters must use the original JobManager/admission pipeline. A local Tesseract
executable was observed with only eng/osd language data; it was not run against
research content, installed, wired into dispatch, or described as Chinese OCR support.
The next OCR integration must preserve source-incarnation, actor, review, cancellation,
resource and terminal-result ownership rather than relaxing the synthetic-only guard.

## Reproduce

`python scripts/inventory_v2_continuation.py --output .runtime/v2-inventory/source.json`

This reads committed HEAD and writes only the chosen report; it does not run product
tests or alter historical matrices. A later HEAD produces a different legitimate pin.
Companion: `current-source-inventory-20261018.json`.

## Row index

| ID | Name | Retained status | Current observation |
|---|---|---|---|
| A01 | Bounded story simulation | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| A02 | Style metrics and drift | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| A03 | Evidence-based narrative judge | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| A04 | Temporal semantic story graph | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| A05 | Character knowledge and mind state | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| A06 | Explainable model broker | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| A07 | Model benchmark and capability evidence | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| A08 | Camera grammar and scene direction | PARTIAL | See current Director/PG/review/CSV slices; film/model quality remains distinct. |
| A09 | Asset lineage and derived relationships | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| A10 | Layered research library | PARTIAL | Current-source audit: ReviewAdapterJobs.run rejects non-MOCK_ONLY with ADAPTER_MODEL_ADMISSION_NOT_CONFIGURED. An installed OCR executable alone must not bypass the original JobManager/admission requirement. |
| A11 | Revision intelligence and partial changes | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| A12 | OTIO and NLE exchange | PARTIAL | NLE source-bound diagnostics/local repair and cache review controls added; no target NLE interoperability claim. |
| A13 | Production manifest and controlled replay | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| B01 | Declarative template library | PARTIAL | Reviewed Graph text to personal brief bridge now exists; no public third-party marketplace. |
| B02 | Custom agents and workflow SDK | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| B03 | Voice direction and speaker attribution | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| B04 | Subtitle editing and timeline | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| B05 | Multilingual revisions and terminology | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| B06 | Comic and Webtoon layouts | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| B07 | Interactive narrative export | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| B08 | Writer room and team review | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| B09 | Project fork and merge | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| B10 | Offline synchronization foundation | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| CONSOLE-01 | Optional Director Console carries vision/duration/audience/story/style/performance/sound/review | PARTIAL | Current mounted Console has original review and storyboard handoff; this inventory does not re-run its end-to-end gate. |
| CONSOLE-02 | Versioned suggestions/parameters to multiple targets without elevated authority | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| CONSOLE-03 | Collapsible card, expanded Console, dependency/progress preview | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| CONSOLE-04 | Multiple independent Director nodes, duplicate as sub-console | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| CONSOLE-05 | Preview/review graph/Shot List proposals before replacing/rerunning/sending | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| CONSOLE-06 | Disconnect/delete Director without breaking unrelated valid nodes/assets | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| CORE_ADAPTATION | Adaptation / Blueprint / Screenplay draft | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| CORE_ASSETS | Asset library / References / Integrity | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| CORE_AUDIO | Audio / TTS / BGM / Ambience / SFX | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| CORE_AUTOMATION | Original Agent / Workflow execution | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| CORE_COLLAB | Workspace / Membership / Permissions | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| CORE_CREATION | Creation workbench / Structured plans / Review threads | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| CORE_EXPORT | Export / History / Snapshot preflight | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| CORE_GENERATION | AI writing / Draft-Diff-Accept / Recovery | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| CORE_IMAGES | Image / Cover / Storyboard / Character reference / Edit / Multi-reference | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| CORE_INTEROP | Frozen PoemSeed Local Interop 1.0 | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| CORE_MANUSCRIPT | Project / Chapter tree / Authoritative manuscript | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| CORE_MODELS | Model Center / Provider configuration | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| CORE_SCREENPLAY | Screenplay / Scene / Shot authoring | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| CORE_VIDEO | Video / Motion / Assembly / Post | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| F00 | Foundation, reuse and dependency registry | INTEGRATED | Owner references inventoried; functional gap not re-audited here. |
| FS_BRANCH | Branch manuscript / Fork / Compare / Human merge | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| FS_CANON | Canon / Evidence / Pending decisions | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| FS_CONTINUITY | Continuity / Evidence / Author feedback | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| FS_ENGINES | Godot / Ren'Py export adapters | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| FS_FORESHADOWING | Foreshadowing / Narrative progress | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| FS_IMPORT | Manuscript import / Import health / Extraction | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| FS_INTERACTION | Command Palette / Keyboard / Accessibility preferences | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| FS_PLANNING | Layered planning / Proposals / Templates | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| FS_PROCESSING | ASR / Forced alignment / Burn-in adapters | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| FS_REALTIME | Realtime protocol / Presence / Co-edit inspector | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| FS_RESEARCH_VISION | OCR / Scanned PDF / Image / Chart / Table | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| FS_REVIEW | Unified review inbox | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| FS_SDK | Model / Import / Export Adapter SDK | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| FS_SEMANTIC | Semantic / Hybrid retrieval and indexes | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| FS_STORY_DATABASE | Characters / Locations / Relationships / World rules | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| FS_SYNC | Production sync / Manifest / Device / Checkpoint | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| FS_TIMELINE | Story timeline / World chronology | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| FS_UNIVERSE | Shared Universe / Selected snapshots | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| FS_VISUAL | Visual Identity / Similarity / Drift | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| GRAPH-01 | Shared Image/Video/Audio/3D/Research DAG and ordinary/pro UI | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| GRAPH-02 | Pan/zoom, marquee/multiselect and draggable visual objects | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| GRAPH-03 | Drag-connect, typed-port highlighting, invalid-edge explanation/conversion | PARTIAL | Pointer drag connection implementation and focused tests now exist. Historical pointer-MISSING wording is not current absence evidence. |
| GRAPH-04 | Context-menu and keyboard command search | PARTIAL | Current canvas insertion controls and tests exist; real keyboard/browser acceptance remains separate. |
| GRAPH-05 | Undo/redo and copy/paste | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| GRAPH-06 | Node grouping, annotations, collapse, MiniMap and alignment | PARTIAL | Persisted visual groups, two-level hierarchy and explicit direct membership edits exist. Not an executable nested subworkflow. |
| GRAPH-07 | Keyboard node/port navigation and error location | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| GRAPH-08 | Graph version, visible autosaved drafts and reload/disconnect recovery | PARTIAL | Explicit graph draft recovery exists; inspect its bounded contract rather than treating old missing text as current absence. |
| GRAPH-09 | Import/export graph templates; disconnect/delete consequence preview | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| GRAPH-10 | Large-graph virtualization/LOD benchmark | PARTIAL | Large-note bounded rendering and note navigation exist; browser FPS/memory remain unmeasured here. |
| GRAPH-11 | Input nodes: Text/Image/Video/Audio/3D/AssetRef/reference/Depth/external file | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| GRAPH-12 | Processing nodes: Agent/image/edit/upscale/video/interpolate/TTS/ASR/convert/quality | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| GRAPH-13 | Control nodes: Director/style/character/camera/motion/budget/review/conditions | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| GRAPH-14 | Output nodes: Asset Save/Preview/Export/Timeline Handoff/Package | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| GRAPH-15 | Text/Image/Video/Audio/Model/Scene/Camera/Pose/Depth/Style/AssetRef/Timeline ports | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| GRAPH-16 | Single-node or graph execution with no Director node | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| GRAPH-17 | Preview inputs/outputs/models/permissions/privacy/resources/cost/overwrite | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| GRAPH-18 | Dependency execution and bounded concurrency | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| GRAPH-19 | VRAM conflict queue, staged unload and resource release | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| GRAPH-20 | Cache binds input version/model/parameters/definition/permission; descendant invalidation | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| GRAPH-21 | Node/local rerun, queue pause, explicit retry, cancel requested versus acknowledged | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| GRAPH-22 | Truthful node progress/time/resource/missing-capability/error navigation | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| U01 | Resume the previous workspace | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| U02 | Loss-resistant editing and visible save state | PARTIAL | Independent loaded Prompt copy is a new local manual draft, not durable autosave. |
| U03 | Search, commands and recents | PARTIAL | Read-only creative scene/shot navigation and bounded local search added. |
| U04 | Focus, reference split and inspiration | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| U05 | Selection assistant and partial accept | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| U06 | Change impact and selective refresh | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| U07 | Unified task center and honest progress | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| U08 | Context and privacy inspector | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| U09 | Local AI diagnostic and setup guidance | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| U10 | Scenario onboarding and progressive disclosure | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| U11 | Reading, proofreading and publishing checks | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| U12 | Actionable errors and private diagnostic export | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| U13 | Chinese input, accessibility and scale | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| U14 | Portable project, relink and safe cleanup | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| U15 | Writing goals and controlled notices | PARTIAL | Owner references inventoried; functional gap not re-audited here. |
| U16 | Safe batch preflight | PARTIAL | Owner references inventoried; functional gap not re-audited here. |

Reproduction check: the committed-script candidate was run again against the same
pinned source, then `cmp` matched its JSON byte-for-byte with this report. Exit 0.
This check verifies deterministic inventory reproduction only; no product tests or
new runtime acceptance are implied.

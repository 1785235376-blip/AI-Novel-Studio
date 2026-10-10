# Post-Interop continuation API catalog

Baseline: `e58c72b04182cd374af092314386b90f8250a173`
Frozen published source: `c12f9b61bf732b40181fabd88e432c6b8deb5bae`
Source tree: `f28e15f020505e5779ace2355f5c2bfacfba4952`
Application Python-source inventory SHA-256: `bf664c5617445d513ce2866da85ea3db2e605d9819e3f853f9f8f531ba1c6148`

## Summary

- Mounted OpenAPI operations: 1721 → 1833.
- Added: 56 logical operations, represented by 112 actual method/path entries across both aliases. Removed: 0.
- Catalogued: 129 logical operations (258 actual alias entries), including 73 existing operations with an observed contract, validation-model or referenced implementation change.
- Existing-operation categories overlap: 16 OpenAPI contract changes, 28 source validation-model changes, 56 referenced implementation changes.
- Extraction reads mounted schemas and source definitions. No endpoint, lifespan, server or model was executed. Network connections and process launches were blocked during imports.
- Interface inspection does not establish runtime acceptance, authorization correctness, real-model quality or a final CI pass. Feature flags default OFF; existing session/project/workspace/branch gates remain authoritative.

## How to read this catalog

Both paths in every row are verified mounted aliases. Owners identify the existing route file and referenced service classes; the JSON also states whether each service class existed in the baseline. Flag/permission lists are observed checks and can be conditional. They are not blanket permissions. Dynamic `{action}` values are not expanded into invented HTTP routes.
`ADD` = new mounted operation; `API` = OpenAPI contract delta; `MODEL` = source validation-model delta, including manually parsed request bodies; `IMPL` = referenced route/helper/direct-service AST changed. Same-shape implementation changes do not imply wire incompatibility. Generic/unannotated response bodies remain unspecified.
Full schema details and source-function evidence are supplied separately in the final API-catalog attachment. The adjacent `API_CATALOG.json` retains paths, owners, flags, authority and schema summaries under 100 KB. Catalog authority-profile IDs Axx below are local documentation references, not the original product feature IDs.

## Route owners and reused authority

### O01: `app/experimental/comic_layouts_api.py`

Referenced services: `app.experimental.comic_layouts.ComicLayoutsService` (existing).

- A01: flag checks: `ai_director_v2`, `asset_lineage_v2`, `comic_layouts_v2`; observed permission literals: `domain.read`; authority functions: `app.experimental.api.authorize`.
- A22: flag checks: `ai_director_v2`, `asset_lineage_v2`, `comic_layouts_v2`; observed permission literals: `domain.write`; authority functions: `app.experimental.api.authorize`.

### O02: `app/experimental/director_api.py`

Referenced services: `app.experimental.director.DirectorService` (existing).

- A02: flag checks: `ai_director_v2`; observed permission literals: `domain.read`; authority functions: `app.experimental.api.authorize`.
- A25: flag checks: `ai_director_v2`; observed permission literals: `domain.write`; authority functions: `app.experimental.api.authorize`.

### O03: `app/experimental/embeddings_api.py`

Referenced services: `app.experimental.embeddings.EmbeddingService` (existing).

- A03: flag checks: `visual_embeddings`; observed permission literals: `domain.read`; authority functions: `app.experimental.api.authorize`.
- A26: flag checks: `visual_embeddings`; observed permission literals: `domain.read`, `domain.write`; authority functions: `app.experimental.api.authorize`.

### O04: `app/experimental/interactive_story_api.py`

Referenced services: `app.experimental.interactive_story.InteractiveStoryService` (existing).

- A04: flag checks: `interactive_story_v2`; observed permission literals: `domain.write`; authority functions: `app.experimental.api.authorize`.

### O05: `app/experimental/media_api.py`

Referenced services: `app.experimental.media.MediaService` (existing).

- A05: flag checks: `cover_storyboard_generation`, `media_adapter_registry`; observed permission literals: `domain.read`; authority functions: `app.experimental.api.authorize`.
  Conditional flag expressions: `'media_adapter_registry' if registry else 'cover_storyboard_generation'`.
- A29: flag checks: `cover_storyboard_generation`, `media_adapter_registry`; observed permission literals: `domain.read`, `domain.write`; authority functions: `app.experimental.api.authorize`.
  Conditional flag expressions: `'media_adapter_registry' if registry else 'cover_storyboard_generation'`.

### O06: `app/experimental/model_benchmark_api.py`

Referenced services: `app.experimental.model_benchmark.ModelBenchmarkService` (existing).

- A06: flag checks: `model_benchmark_v2`; observed permission literals: `domain.read`; authority functions: `app.experimental.api.authorize`, `app.experimental.api.require_inspection_host_session`.
- A30: flag checks: `model_benchmark_v2`; observed permission literals: `domain.read`, `domain.write`; authority functions: `app.experimental.api.authorize`, `app.experimental.api.require_inspection_host_session`.

### O07: `app/experimental/narrative_judge_api.py`

Referenced services: `app.experimental.narrative_judge.NarrativeJudgeService` (existing).

- A07: flag checks: `narrative_quality_judge_v2`, `writer_room_v2`; observed permission literals: `domain.review`, `domain.write`; authority functions: `app.experimental.api.authorize`.
- A32: flag checks: `narrative_quality_judge_v2`; observed permission literals: `domain.review`, `domain.write`; authority functions: `app.experimental.api.authorize`.

### O08: `app/experimental/production_lineage_api.py`

Referenced services: `app.experimental.production_lineage.ProductionLineageService` (existing).

- A08: flag checks: `asset_lineage_v2`, `cover_storyboard_generation`, `media_adapter_registry`, `production_manifest_v2`; observed permission literals: `domain.read`; authority functions: `app.experimental.api.authorize`.
- A33: flag checks: `asset_lineage_v2`, `cover_storyboard_generation`, `media_adapter_registry`, `production_manifest_v2`; observed permission literals: `domain.read`, `domain.write`; authority functions: `app.experimental.api.authorize`.

### O09: `app/experimental/project_forks_api.py`

Referenced services: `app.experimental.project_forks.ProjectForksService` (existing); `app.experimental.structured_forks.StructuredForksService` (existing).

- A09: flag checks: `project_forks_v2`, `world_character_engines_v2`; observed permission literals: `domain.read`, `domain.review`; authority functions: `app.experimental.api.authorize`, `app.experimental.api.require_inspection_host_session`.

### O10: `app/experimental/research_library_api.py`

Referenced services: `app.experimental.research_library.ResearchLibraryService` (existing).

- A10: flag checks: `research_library_v2`; observed permission literals: `domain.write`; authority functions: `app.experimental.api.authorize`.

### O11: `app/experimental/revision_intelligence_api.py`

Referenced services: `app.experimental.revision_intelligence.RevisionIntelligenceService` (existing).

- A11: flag checks: `revision_intelligence_v2`; observed permission literals: `domain.write`; authority functions: `app.experimental.api.authorize`.
- A12: flag checks: `author_context_inspector_v2`, `model_broker_v2`, `revision_intelligence_v2`; observed permission literals: `domain.review`, `domain.write`; authority functions: `app.experimental.api.authorize`, `app.experimental.api.require_inspection_host_session`.
- A34: flag checks: `revision_intelligence_v2`; observed permission literals: `domain.review`, `domain.write`; authority functions: `app.experimental.api.authorize`.

### O12: `app/experimental/story_graph_api.py`

Referenced services: `app.experimental.story_graph.StoryGraphService` (existing).

- A13: flag checks: `character_mind_v2`, `temporal_story_graph_v2`; observed permission literals: `domain.read`, `domain.write`; authority functions: `app.experimental.api.authorize`.
- A35: flag checks: `character_mind_v2`, `temporal_story_graph_v2`; observed permission literals: `domain.read`; authority functions: `app.experimental.api.authorize`.
- A36: flag checks: `character_mind_v2`, `temporal_story_graph_v2`; observed permission literals: `domain.read`, `domain.review`, `domain.write`; authority functions: `app.experimental.api.authorize`.

### O13: `app/experimental/story_simulator_api.py`

Referenced services: `app.experimental.story_simulator.StorySimulatorService` (existing).

- A14: flag checks: `story_simulator_v2`; observed permission literals: `domain.write`; authority functions: `app.experimental.api.authorize`.

### O14: `app/experimental/style_analysis_api.py`

Referenced services: `app.experimental.style_analysis.StyleAnalysisService` (existing).

- A15: flag checks: `style_dna_v2`; observed permission literals: `domain.write`; authority functions: `app.experimental.api.authorize`.
- A16: flag checks: `author_context_inspector_v2`, `model_broker_v2`, `style_dna_v2`; observed permission literals: `domain.write`; authority functions: `app.experimental.api.authorize`, `app.experimental.api.require_inspection_host_session`.
- A37: flag checks: `style_dna_v2`; observed permission literals: `domain.review`, `domain.write`; authority functions: `app.experimental.api.authorize`.

### O15: `app/experimental/ux_api.py`

Referenced services: `app.experimental.ux.WorkspaceToolsService` (existing).

- A17: flag checks: `workspace_tools_v2`; observed permission literals: `domain.read`, `domain.write`; authority functions: `app.experimental.api.authorize`.

### O16: `app/experimental/writer_room_api.py`

Referenced services: `app.experimental.writer_room.WriterRoomService` (existing).

- A18: flag checks: `writer_room_v2`; observed permission literals: `domain.read`, `domain.write`; authority functions: `app.experimental.api.authorize`.

### O17: `app/model_center/discovery_api.py`

Referenced services: `app.model_center.discovery.LocalDiscoveryService` (existing).

- A19: flag checks: none observed in the inspected route/helper source; observed permission literals: not statically established; authority functions: `app.main._model_center_mutation_authorization`, `app.model_center.discovery_api.create_local_discovery_router.<locals>.require_session`.

### O18: `app/experimental/author_context_api.py`

Referenced services: `app.experimental.author_context_api.AuthorPreparer` (existing); `app.jobs.JobManager` (existing).

- A20: flag checks: `author_context_inspector_v2`; observed permission literals: `domain.write`; authority functions: `app.experimental.api.authorize`.
- A21: flag checks: `author_context_inspector_v2`; observed permission literals: `domain.read`; authority functions: `app.experimental.api.authorize`.

### O19: `app/experimental/author_context_api.py`

Referenced services: `app.experimental.author_context_api.AuthorPreparer` (existing).

- A21: flag checks: `author_context_inspector_v2`; observed permission literals: `domain.read`; authority functions: `app.experimental.api.authorize`.

### O20: `app/experimental/declarative_agents_api.py`

Referenced services: `app.experimental.declarative_agents.DeclarativeAgentsService` (existing).

- A23: flag checks: `declarative_agents_v2`; observed permission literals: `domain.read`, `domain.write`; authority functions: `app.experimental.api.authorize`.
- A24: flag checks: `declarative_agents_v2`; observed permission literals: `domain.read`; authority functions: `app.experimental.api.authorize`.

### O21: `app/experimental/interactive_story_api.py`

Referenced services: See original handler/closure source; no service class was reliably identified..

- A04: flag checks: `interactive_story_v2`; observed permission literals: `domain.write`; authority functions: `app.experimental.api.authorize`.

### O22: `app/experimental/multilingual_editions_api.py`

Referenced services: `app.experimental.multilingual_editions.MultilingualEditionsService` (existing).

- A27: flag checks: `multilingual_editions_v2`; observed permission literals: `domain.write`; authority functions: `app.experimental.api.authorize`.
- A28: flag checks: `multilingual_editions_v2`; observed permission literals: `domain.review`, `domain.write`; authority functions: `app.experimental.api.authorize`.

### O23: `app/experimental/model_broker_api.py`

Referenced services: `app.experimental.model_broker.ModelBrokerService` (existing); `app.jobs.JobManager` (existing); `builtins.method` (introduced coordinator/service).

- A31: flag checks: `model_broker_v2`; observed permission literals: `domain.read`, `domain.write`; authority functions: `app.experimental.api.authorize`, `app.experimental.api.require_inspection_host_session`.

### O24: `app/experimental/model_broker_api.py`

Referenced services: `app.experimental.model_broker.ModelBrokerService` (existing).

- A31: flag checks: `model_broker_v2`; observed permission literals: `domain.read`, `domain.write`; authority functions: `app.experimental.api.authorize`, `app.experimental.api.require_inspection_host_session`.

### O25: `app/experimental/template_library_api.py`

Referenced services: `app.experimental.template_library.TemplateLibraryService` (existing).

- A38: flag checks: `template_library_v2`; observed permission literals: `domain.read`, `domain.write`; authority functions: `app.experimental.api.authorize`.

### O26: `app/experimental/timeline_exchange_api.py`

Referenced services: `app.experimental.timeline_exchange.TimelineExchangeService` (existing).

- A39: flag checks: `asset_lineage_v2`, `timeline_exchange_v2`; observed permission literals: `domain.write`; authority functions: `app.experimental.api.authorize`.

### O27: `app/experimental/world_api.py`

Referenced services: `app.experimental.world.WorldService` (existing).

- A40: flag checks: `world_character_engines_v2`; observed permission literals: `domain.read`, `domain.write`; authority functions: `app.experimental.api.authorize`.
- A41: flag checks: `world_character_engines_v2`; observed permission literals: `domain.read`, `domain.review`, `domain.write`; authority functions: `app.experimental.api.authorize`.

### O28: `app/experimental/voice_direction_api.py`

Referenced services: `app.experimental.voice_direction.DirectedAudiobookService` (existing).

- A42: flag checks: `audiobook_v2`; observed permission literals: `domain.write`; authority functions: `app.experimental.api.authorize`.
  Conditional flag expressions: `VOICE_FLAG`.

## Added operations

| Method | Actual `/api` path | Actual `/api/v1` alias | Change | Owner / authority | Schema refs |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/novels/{nid}/experimental/embeddings/providers` | `/api/v1/novels/{nid}/experimental/embeddings/providers` | ADD | O03 / A03 | S11, S26 |
| GET | `/api/novels/{nid}/experimental/embeddings/sources` | `/api/v1/novels/{nid}/experimental/embeddings/sources` | ADD | O03 / A03 | S11, S26 |
| GET | `/api/novels/{nid}/experimental/interactive-stories/engine-contract` | `/api/v1/novels/{nid}/experimental/interactive-stories/engine-contract` | ADD | O04 / A04 | S11, S26, S42 |
| GET | `/api/novels/{nid}/experimental/media/catalog` | `/api/v1/novels/{nid}/experimental/media/catalog` | ADD | O05 / A05 | S11, S26 |
| GET | `/api/novels/{nid}/experimental/model-benchmarks/profiles` | `/api/v1/novels/{nid}/experimental/model-benchmarks/profiles` | ADD | O06 / A06 | S11, S26 |
| GET | `/api/novels/{nid}/experimental/narrative-judge/findings/{rid}/revision-task` | `/api/v1/novels/{nid}/experimental/narrative-judge/findings/{rid}/revision-task` | ADD | O07 / A07 | S11, S26 |
| GET | `/api/novels/{nid}/experimental/project-forks/universe/catalog` | `/api/v1/novels/{nid}/experimental/project-forks/universe/catalog` | ADD | O09 / A09 | S11, S26 |
| GET | `/api/novels/{nid}/experimental/project-forks/universe/incoming` | `/api/v1/novels/{nid}/experimental/project-forks/universe/incoming` | ADD | O09 / A09 | S11, S26 |
| GET | `/api/novels/{nid}/experimental/project-forks/universe/incoming/{source_nid}/{pin_id}` | `/api/v1/novels/{nid}/experimental/project-forks/universe/incoming/{source_nid}/{pin_id}` | ADD | O09 / A09 | S11, S26 |
| GET | `/api/novels/{nid}/experimental/project-forks/universe/pins` | `/api/v1/novels/{nid}/experimental/project-forks/universe/pins` | ADD | O09 / A09 | S11, S26 |
| GET | `/api/novels/{nid}/experimental/project-forks/universe/pins/{rid}/history` | `/api/v1/novels/{nid}/experimental/project-forks/universe/pins/{rid}/history` | ADD | O09 / A09 | S11, S26 |
| GET | `/api/novels/{nid}/experimental/project-forks/universe/snapshots` | `/api/v1/novels/{nid}/experimental/project-forks/universe/snapshots` | ADD | O09 / A09 | S11, S26 |
| GET | `/api/novels/{nid}/experimental/research-library/note-repairs` | `/api/v1/novels/{nid}/experimental/research-library/note-repairs` | ADD | O10 / A10 | S11, S26 |
| GET | `/api/novels/{nid}/experimental/research-library/notes/{rid}/history` | `/api/v1/novels/{nid}/experimental/research-library/notes/{rid}/history` | ADD | O10 / A10 | S11, S26 |
| GET | `/api/novels/{nid}/experimental/research-library/sources-archive` | `/api/v1/novels/{nid}/experimental/research-library/sources-archive` | ADD | O10 / A10 | S11, S26 |
| GET | `/api/novels/{nid}/experimental/research-library/sources/{rid}/history` | `/api/v1/novels/{nid}/experimental/research-library/sources/{rid}/history` | ADD | O10 / A10 | S11, S26 |
| GET | `/api/novels/{nid}/experimental/research-library/sources/{rid}/history/{version}/original` | `/api/v1/novels/{nid}/experimental/research-library/sources/{rid}/history/{version}/original` | ADD | O10 / A10 | S11, S26 |
| GET | `/api/novels/{nid}/experimental/revisions/comparisons` | `/api/v1/novels/{nid}/experimental/revisions/comparisons` | ADD | O11 / A11 | S11, S26 |
| GET | `/api/novels/{nid}/experimental/revisions/comparisons-model/catalog` | `/api/v1/novels/{nid}/experimental/revisions/comparisons-model/catalog` | ADD | O11 / A12 | S11, S26 |
| GET | `/api/novels/{nid}/experimental/revisions/comparisons/{rid}` | `/api/v1/novels/{nid}/experimental/revisions/comparisons/{rid}` | ADD | O11 / A11 | S11, S26 |
| GET | `/api/novels/{nid}/experimental/revisions/original-versions` | `/api/v1/novels/{nid}/experimental/revisions/original-versions` | ADD | O11 / A11 | S11, S26 |
| GET | `/api/novels/{nid}/experimental/style-analysis/analyses/{rid}` | `/api/v1/novels/{nid}/experimental/style-analysis/analyses/{rid}` | ADD | O14 / A15 | S11, S26 |
| GET | `/api/novels/{nid}/experimental/style-analysis/model/catalog` | `/api/v1/novels/{nid}/experimental/style-analysis/model/catalog` | ADD | O14 / A16 | S11, S26 |
| GET | `/api/novels/{nid}/experimental/writer-room/presence-contract` | `/api/v1/novels/{nid}/experimental/writer-room/presence-contract` | ADD | O16 / A18 | S11, S26 |
| POST | `/api/novels/{nid}/experimental/author-context/sources` | `/api/v1/novels/{nid}/experimental/author-context/sources` | ADD | O19 / A21 | S11, S26, S29, S30 |
| POST | `/api/novels/{nid}/experimental/interactive-stories/{sid}/history` | `/api/v1/novels/{nid}/experimental/interactive-stories/{sid}/history` | ADD | O21 / A04 | S11, S26, S43 |
| POST | `/api/novels/{nid}/experimental/interactive-stories/{sid}/restore-revision` | `/api/v1/novels/{nid}/experimental/interactive-stories/{sid}/restore-revision` | ADD | O21 / A04 | S11, S26, S41 |
| POST | `/api/novels/{nid}/experimental/language-editions/{eid}/segments/{sid}/{action}` | `/api/v1/novels/{nid}/experimental/language-editions/{eid}/segments/{sid}/{action}` | ADD | O22 / A27 | S11, S26, S49, S50, S53 |
| POST | `/api/novels/{nid}/experimental/model-benchmarks/evidence/{rid}/review` | `/api/v1/novels/{nid}/experimental/model-benchmarks/evidence/{rid}/review` | ADD | O06 / A30 | S11, S26, S46 |
| POST | `/api/novels/{nid}/experimental/narrative-judge/findings/{rid}/revision-task` | `/api/v1/novels/{nid}/experimental/narrative-judge/findings/{rid}/revision-task` | ADD | O07 / A07 | S11, S16, S26, S55 |
| POST | `/api/novels/{nid}/experimental/project-forks/universe/pin-preview` | `/api/v1/novels/{nid}/experimental/project-forks/universe/pin-preview` | ADD | O09 / A09 | S11, S26, S73 |
| POST | `/api/novels/{nid}/experimental/project-forks/universe/pins` | `/api/v1/novels/{nid}/experimental/project-forks/universe/pins` | ADD | O09 / A09 | S11, S26, S72 |
| POST | `/api/novels/{nid}/experimental/project-forks/universe/pins/{rid}/release` | `/api/v1/novels/{nid}/experimental/project-forks/universe/pins/{rid}/release` | ADD | O09 / A09 | S11, S26, S59 |
| POST | `/api/novels/{nid}/experimental/project-forks/universe/snapshot-preview` | `/api/v1/novels/{nid}/experimental/project-forks/universe/snapshot-preview` | ADD | O09 / A09 | S11, S26, S75 |
| POST | `/api/novels/{nid}/experimental/project-forks/universe/snapshots` | `/api/v1/novels/{nid}/experimental/project-forks/universe/snapshots` | ADD | O09 / A09 | S11, S26, S74 |
| POST | `/api/novels/{nid}/experimental/research-library/notes/{rid}/delete` | `/api/v1/novels/{nid}/experimental/research-library/notes/{rid}/delete` | ADD | O10 / A10 | S11, S26, S27, S63 |
| POST | `/api/novels/{nid}/experimental/research-library/sources/{rid}/restore` | `/api/v1/novels/{nid}/experimental/research-library/sources/{rid}/restore` | ADD | O10 / A10 | S11, S20, S26, S62 |
| POST | `/api/novels/{nid}/experimental/revisions/comparisons` | `/api/v1/novels/{nid}/experimental/revisions/comparisons` | ADD | O11 / A11 | S11, S26, S68 |
| POST | `/api/novels/{nid}/experimental/revisions/comparisons/preview` | `/api/v1/novels/{nid}/experimental/revisions/comparisons/preview` | ADD | O11 / A11 | S11, S26, S65 |
| POST | `/api/novels/{nid}/experimental/revisions/comparisons/{rid}/model/cancel` | `/api/v1/novels/{nid}/experimental/revisions/comparisons/{rid}/model/cancel` | ADD | O11 / A12 | S11, S12, S26, S56 |
| POST | `/api/novels/{nid}/experimental/revisions/comparisons/{rid}/model/dispatch` | `/api/v1/novels/{nid}/experimental/revisions/comparisons/{rid}/model/dispatch` | ADD | O11 / A12 | S11, S13, S26, S57 |
| POST | `/api/novels/{nid}/experimental/revisions/comparisons/{rid}/model/opinions/{oid}/{action}` | `/api/v1/novels/{nid}/experimental/revisions/comparisons/{rid}/model/opinions/{oid}/{action}` | ADD | O11 / A12 | S11, S12, S26, S56 |
| POST | `/api/novels/{nid}/experimental/revisions/comparisons/{rid}/model/preview` | `/api/v1/novels/{nid}/experimental/revisions/comparisons/{rid}/model/preview` | ADD | O11 / A12 | S11, S14, S26, S58 |
| POST | `/api/novels/{nid}/experimental/revisions/comparisons/{rid}/model/refresh` | `/api/v1/novels/{nid}/experimental/revisions/comparisons/{rid}/model/refresh` | ADD | O11 / A12 | S11, S12, S26, S56 |
| POST | `/api/novels/{nid}/experimental/revisions/comparisons/{rid}/review` | `/api/v1/novels/{nid}/experimental/revisions/comparisons/{rid}/review` | ADD | O11 / A34 | S11, S26, S67 |
| POST | `/api/novels/{nid}/experimental/style-analysis/analyses/{rid}/model/cancel` | `/api/v1/novels/{nid}/experimental/style-analysis/analyses/{rid}/model/cancel` | ADD | O14 / A16 | S11, S12, S26, S56 |
| POST | `/api/novels/{nid}/experimental/style-analysis/analyses/{rid}/model/dispatch` | `/api/v1/novels/{nid}/experimental/style-analysis/analyses/{rid}/model/dispatch` | ADD | O14 / A16 | S11, S13, S26, S57 |
| POST | `/api/novels/{nid}/experimental/style-analysis/analyses/{rid}/model/preview` | `/api/v1/novels/{nid}/experimental/style-analysis/analyses/{rid}/model/preview` | ADD | O14 / A16 | S11, S14, S26, S58 |
| POST | `/api/novels/{nid}/experimental/style-analysis/analyses/{rid}/model/refresh` | `/api/v1/novels/{nid}/experimental/style-analysis/analyses/{rid}/model/refresh` | ADD | O14 / A16 | S11, S12, S26, S56 |
| POST | `/api/novels/{nid}/experimental/style-analysis/analyses/{rid}/opinions/{opinion_id}/review` | `/api/v1/novels/{nid}/experimental/style-analysis/analyses/{rid}/opinions/{opinion_id}/review` | ADD | O14 / A37 | S11, S24, S26, S76 |
| POST | `/api/novels/{nid}/experimental/workspace/tasks/{authority}/{task_id}/cancel` | `/api/v1/novels/{nid}/experimental/workspace/tasks/{authority}/{task_id}/cancel` | ADD | O15 / A17 | S11, S25, S26, S80 |
| PUT | `/api/novels/{nid}/experimental/embeddings/indexes/{rid}` | `/api/v1/novels/{nid}/experimental/embeddings/indexes/{rid}` | ADD | O03 / A26 | S08, S10, S11, S26, S38 |
| PUT | `/api/novels/{nid}/experimental/media/storyboard-briefs/{rid}` | `/api/v1/novels/{nid}/experimental/media/storyboard-briefs/{rid}` | ADD | O05 / A29 | S11, S23, S26, S45 |
| PUT | `/api/novels/{nid}/experimental/research-library/notes/{rid}` | `/api/v1/novels/{nid}/experimental/research-library/notes/{rid}` | ADD | O10 / A10 | S04, S07, S11, S26, S60 |
| PUT | `/api/novels/{nid}/experimental/research-library/sources/{rid}/file` | `/api/v1/novels/{nid}/experimental/research-library/sources/{rid}/file` | ADD | O10 / A10 | S11, S18, S26, S61 |
| PUT | `/api/novels/{nid}/experimental/revisions/comparisons/{rid}` | `/api/v1/novels/{nid}/experimental/revisions/comparisons/{rid}` | ADD | O11 / A11 | S11, S26, S66 |

## Existing operations with observed changes

| Method | Actual `/api` path | Actual `/api/v1` alias | Change | Owner / authority | Schema refs |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/novels/{nid}/experimental/comic-layouts/catalog` | `/api/v1/novels/{nid}/experimental/comic-layouts/catalog` | IMPL | O01 / A01 | — |
| GET | `/api/novels/{nid}/experimental/comic-layouts/records/{rid}/export` | `/api/v1/novels/{nid}/experimental/comic-layouts/records/{rid}/export` | IMPL | O01 / A01 | — |
| GET | `/api/novels/{nid}/experimental/director/catalog` | `/api/v1/novels/{nid}/experimental/director/catalog` | IMPL | O02 / A02 | — |
| GET | `/api/novels/{nid}/experimental/embeddings/indexes` | `/api/v1/novels/{nid}/experimental/embeddings/indexes` | IMPL | O03 / A03 | — |
| GET | `/api/novels/{nid}/experimental/embeddings/indexes/{rid}/records` | `/api/v1/novels/{nid}/experimental/embeddings/indexes/{rid}/records` | IMPL | O03 / A03 | — |
| GET | `/api/novels/{nid}/experimental/interactive-stories/catalog` | `/api/v1/novels/{nid}/experimental/interactive-stories/catalog` | IMPL | O04 / A04 | — |
| GET | `/api/novels/{nid}/experimental/media/cover-briefs` | `/api/v1/novels/{nid}/experimental/media/cover-briefs` | IMPL | O05 / A05 | — |
| GET | `/api/novels/{nid}/experimental/media/storyboard-briefs` | `/api/v1/novels/{nid}/experimental/media/storyboard-briefs` | IMPL | O05 / A05 | — |
| GET | `/api/novels/{nid}/experimental/model-benchmarks/status` | `/api/v1/novels/{nid}/experimental/model-benchmarks/status` | IMPL | O06 / A06 | — |
| GET | `/api/novels/{nid}/experimental/production/manifests/{rid}/export` | `/api/v1/novels/{nid}/experimental/production/manifests/{rid}/export` | IMPL | O08 / A08 | — |
| GET | `/api/novels/{nid}/experimental/research-library/notes` | `/api/v1/novels/{nid}/experimental/research-library/notes` | IMPL | O10 / A10 | — |
| GET | `/api/novels/{nid}/experimental/story-graph/catalog` | `/api/v1/novels/{nid}/experimental/story-graph/catalog` | IMPL | O12 / A13 | — |
| GET | `/api/novels/{nid}/experimental/story-graph/query` | `/api/v1/novels/{nid}/experimental/story-graph/query` | API, IMPL | O12 / A13 | — |
| GET | `/api/novels/{nid}/experimental/story-graph/records` | `/api/v1/novels/{nid}/experimental/story-graph/records` | IMPL | O12 / A13 | — |
| GET | `/api/novels/{nid}/experimental/story-graph/records/{rid}` | `/api/v1/novels/{nid}/experimental/story-graph/records/{rid}` | IMPL | O12 / A13 | — |
| GET | `/api/novels/{nid}/experimental/story-graph/records/{rid}/history` | `/api/v1/novels/{nid}/experimental/story-graph/records/{rid}/history` | IMPL | O12 / A13 | — |
| GET | `/api/novels/{nid}/experimental/story-graph/records/{rid}/impact` | `/api/v1/novels/{nid}/experimental/story-graph/records/{rid}/impact` | IMPL | O12 / A13 | — |
| GET | `/api/novels/{nid}/experimental/story-simulator/catalog` | `/api/v1/novels/{nid}/experimental/story-simulator/catalog` | IMPL | O13 / A14 | — |
| GET | `/api/novels/{nid}/experimental/workspace/resume` | `/api/v1/novels/{nid}/experimental/workspace/resume` | MODEL | O15 / A17 | S77 |
| GET | `/api/novels/{nid}/experimental/workspace/resume/history` | `/api/v1/novels/{nid}/experimental/workspace/resume/history` | IMPL | O15 / A17 | — |
| GET | `/api/novels/{nid}/experimental/workspace/search` | `/api/v1/novels/{nid}/experimental/workspace/search` | IMPL | O15 / A17 | — |
| GET | `/api/novels/{nid}/experimental/workspace/tasks` | `/api/v1/novels/{nid}/experimental/workspace/tasks` | IMPL | O15 / A17 | — |
| POST | `/api/model-center/local-ai/candidates/{candidate_id}/validate` | `/api/v1/model-center/local-ai/candidates/{candidate_id}/validate` | IMPL | O17 / A19 | — |
| POST | `/api/novels/{nid}/experimental/author-context/generate` | `/api/v1/novels/{nid}/experimental/author-context/generate` | MODEL | O18 / A20 | S29 |
| POST | `/api/novels/{nid}/experimental/author-context/generate-variants` | `/api/v1/novels/{nid}/experimental/author-context/generate-variants` | MODEL | O18 / A20 | S29, S31 |
| POST | `/api/novels/{nid}/experimental/author-context/preview` | `/api/v1/novels/{nid}/experimental/author-context/preview` | MODEL, IMPL | O18 / A21 | S29 |
| POST | `/api/novels/{nid}/experimental/author-context/preview-variants` | `/api/v1/novels/{nid}/experimental/author-context/preview-variants` | MODEL, IMPL | O18 / A21 | S29, S31 |
| POST | `/api/novels/{nid}/experimental/comic-layouts/records` | `/api/v1/novels/{nid}/experimental/comic-layouts/records` | API, MODEL | O01 / A22 | S02, S05, S33 |
| POST | `/api/novels/{nid}/experimental/declarative-agents/definitions` | `/api/v1/novels/{nid}/experimental/declarative-agents/definitions` | API, MODEL | O20 / A23 | S01, S34 |
| POST | `/api/novels/{nid}/experimental/declarative-agents/preflight` | `/api/v1/novels/{nid}/experimental/declarative-agents/preflight` | API, MODEL | O20 / A24 | S01, S35 |
| POST | `/api/novels/{nid}/experimental/director/plans` | `/api/v1/novels/{nid}/experimental/director/plans` | API, MODEL | O02 / A25 | S03, S36 |
| POST | `/api/novels/{nid}/experimental/embeddings/indexes` | `/api/v1/novels/{nid}/experimental/embeddings/indexes` | API, MODEL, IMPL | O03 / A26 | S09, S10, S39 |
| POST | `/api/novels/{nid}/experimental/embeddings/indexes/{rid}/{action}` | `/api/v1/novels/{nid}/experimental/embeddings/indexes/{rid}/{action}` | MODEL, IMPL | O03 / A26 | S37, S40 |
| POST | `/api/novels/{nid}/experimental/embeddings/query` | `/api/v1/novels/{nid}/experimental/embeddings/query` | MODEL, IMPL | O03 / A03 | S37 |
| POST | `/api/novels/{nid}/experimental/language-editions/{eid}/rules` | `/api/v1/novels/{nid}/experimental/language-editions/{eid}/rules` | MODEL | O22 / A27 | S51 |
| POST | `/api/novels/{nid}/experimental/language-editions/{eid}/rules/{rid}/review` | `/api/v1/novels/{nid}/experimental/language-editions/{eid}/rules/{rid}/review` | MODEL, IMPL | O22 / A28 | S52 |
| POST | `/api/novels/{nid}/experimental/media/cover-briefs` | `/api/v1/novels/{nid}/experimental/media/cover-briefs` | API, MODEL | O05 / A29 | S06, S44 |
| POST | `/api/novels/{nid}/experimental/media/proposals/compare` | `/api/v1/novels/{nid}/experimental/media/proposals/compare` | IMPL | O05 / A05 | — |
| POST | `/api/novels/{nid}/experimental/model-broker/generate` | `/api/v1/novels/{nid}/experimental/model-broker/generate` | MODEL, IMPL | O23 / A31 | S48 |
| POST | `/api/novels/{nid}/experimental/model-broker/preview` | `/api/v1/novels/{nid}/experimental/model-broker/preview` | MODEL, IMPL | O24 / A31 | S47 |
| POST | `/api/novels/{nid}/experimental/narrative-judge/findings/{rid}/review` | `/api/v1/novels/{nid}/experimental/narrative-judge/findings/{rid}/review` | API, MODEL, IMPL | O07 / A32 | S15, S54 |
| POST | `/api/novels/{nid}/experimental/narrative-judge/runs` | `/api/v1/novels/{nid}/experimental/narrative-judge/runs` | IMPL | O07 / A32 | — |
| POST | `/api/novels/{nid}/experimental/production/manifests/{rid}/preflight` | `/api/v1/novels/{nid}/experimental/production/manifests/{rid}/preflight` | IMPL | O08 / A33 | — |
| POST | `/api/novels/{nid}/experimental/research-library/sources/{rid}/{action}` | `/api/v1/novels/{nid}/experimental/research-library/sources/{rid}/{action}` | IMPL | O10 / A10 | — |
| POST | `/api/novels/{nid}/experimental/revisions/proposals` | `/api/v1/novels/{nid}/experimental/revisions/proposals` | MODEL | O11 / A11 | S64 |
| POST | `/api/novels/{nid}/experimental/story-graph/character-context` | `/api/v1/novels/{nid}/experimental/story-graph/character-context` | API, MODEL, IMPL | O12 / A35 | S28, S69 |
| POST | `/api/novels/{nid}/experimental/story-graph/records` | `/api/v1/novels/{nid}/experimental/story-graph/records` | IMPL | O12 / A13 | — |
| POST | `/api/novels/{nid}/experimental/story-graph/records/{rid}/{action}` | `/api/v1/novels/{nid}/experimental/story-graph/records/{rid}/{action}` | IMPL | O12 / A36 | — |
| POST | `/api/novels/{nid}/experimental/story-simulator/context` | `/api/v1/novels/{nid}/experimental/story-simulator/context` | API, MODEL | O13 / A14 | S22, S71 |
| POST | `/api/novels/{nid}/experimental/story-simulator/runs` | `/api/v1/novels/{nid}/experimental/story-simulator/runs` | API, MODEL | O13 / A14 | S21, S70 |
| POST | `/api/novels/{nid}/experimental/style-analysis/analyses` | `/api/v1/novels/{nid}/experimental/style-analysis/analyses` | IMPL | O14 / A15 | — |
| POST | `/api/novels/{nid}/experimental/style-analysis/profiles` | `/api/v1/novels/{nid}/experimental/style-analysis/profiles` | IMPL | O14 / A15 | — |
| POST | `/api/novels/{nid}/experimental/style-analysis/profiles/{rid}/preview` | `/api/v1/novels/{nid}/experimental/style-analysis/profiles/{rid}/preview` | IMPL | O14 / A15 | — |
| POST | `/api/novels/{nid}/experimental/style-analysis/profiles/{rid}/{action}` | `/api/v1/novels/{nid}/experimental/style-analysis/profiles/{rid}/{action}` | IMPL | O14 / A37 | — |
| POST | `/api/novels/{nid}/experimental/template-library/install` | `/api/v1/novels/{nid}/experimental/template-library/install` | IMPL | O25 / A38 | — |
| POST | `/api/novels/{nid}/experimental/template-library/instances` | `/api/v1/novels/{nid}/experimental/template-library/instances` | MODEL, IMPL | O25 / A38 | S35 |
| POST | `/api/novels/{nid}/experimental/timeline-exchange/from-screenplay` | `/api/v1/novels/{nid}/experimental/timeline-exchange/from-screenplay` | IMPL | O26 / A39 | — |
| POST | `/api/novels/{nid}/experimental/workspace/diagnostics/export` | `/api/v1/novels/{nid}/experimental/workspace/diagnostics/export` | IMPL | O15 / A17 | — |
| POST | `/api/novels/{nid}/experimental/workspace/diagnostics/preview` | `/api/v1/novels/{nid}/experimental/workspace/diagnostics/preview` | IMPL | O15 / A17 | — |
| POST | `/api/novels/{nid}/experimental/workspace/search/rebuild` | `/api/v1/novels/{nid}/experimental/workspace/search/rebuild` | IMPL | O15 / A17 | — |
| POST | `/api/novels/{nid}/experimental/workspace/search/resolve` | `/api/v1/novels/{nid}/experimental/workspace/search/resolve` | API, MODEL | O15 / A17 | S19, S78 |
| POST | `/api/novels/{nid}/experimental/world/records` | `/api/v1/novels/{nid}/experimental/world/records` | IMPL | O27 / A40 | — |
| POST | `/api/novels/{nid}/experimental/world/records/{rid}/{action}` | `/api/v1/novels/{nid}/experimental/world/records/{rid}/{action}` | IMPL | O27 / A41 | — |
| PUT | `/api/novels/{nid}/experimental/comic-layouts/records/{rid}` | `/api/v1/novels/{nid}/experimental/comic-layouts/records/{rid}` | API, MODEL | O01 / A22 | S02, S05, S32 |
| PUT | `/api/novels/{nid}/experimental/declarative-agents/definitions/{rid}` | `/api/v1/novels/{nid}/experimental/declarative-agents/definitions/{rid}` | API, MODEL | O20 / A23 | S01, S34 |
| PUT | `/api/novels/{nid}/experimental/language-editions/{eid}/segments/{sid}` | `/api/v1/novels/{nid}/experimental/language-editions/{eid}/segments/{sid}` | IMPL | O22 / A27 | — |
| PUT | `/api/novels/{nid}/experimental/media/cover-briefs/{rid}` | `/api/v1/novels/{nid}/experimental/media/cover-briefs/{rid}` | API, MODEL | O05 / A29 | S06, S44 |
| PUT | `/api/novels/{nid}/experimental/research-library/sources/{rid}` | `/api/v1/novels/{nid}/experimental/research-library/sources/{rid}` | IMPL | O10 / A10 | — |
| PUT | `/api/novels/{nid}/experimental/story-graph/records/{rid}` | `/api/v1/novels/{nid}/experimental/story-graph/records/{rid}` | IMPL | O12 / A13 | — |
| PUT | `/api/novels/{nid}/experimental/style-analysis/profiles/{rid}` | `/api/v1/novels/{nid}/experimental/style-analysis/profiles/{rid}` | IMPL | O14 / A15 | — |
| PUT | `/api/novels/{nid}/experimental/voice-direction/plans/{rid}/segments/{sid}` | `/api/v1/novels/{nid}/experimental/voice-direction/plans/{rid}/segments/{sid}` | IMPL | O28 / A42 | — |
| PUT | `/api/novels/{nid}/experimental/workspace/resume` | `/api/v1/novels/{nid}/experimental/workspace/resume` | API, MODEL | O15 / A17 | S17, S79 |
| PUT | `/api/novels/{nid}/experimental/world/records/{rid}` | `/api/v1/novels/{nid}/experimental/world/records/{rid}` | IMPL | O27 / A40 | — |

## Schema summaries

`NEWLY_REFERENCED_BY_OPERATION` means reuse by an added/changed operation, not a changed schema definition. Nested-definition changes are listed because a top-level property may retain its reference while the referenced contract changes.

- **S01 `AgentDefinition`** (OPENAPI_COMPONENT; CHANGED): added fields: `capability_requirements`, `runtime_requirement`.
- **S02 `AppearanceReference`** (OPENAPI_COMPONENT; ADDED): added fields: `asset_id`, `character_id`, `expected_asset_version`, `note`; required fields added: `asset_id`, `character_id`, `expected_asset_version`.
- **S03 `CameraGrammar`** (OPENAPI_COMPONENT; CHANGED): added fields: `focus_intent`, `shot_function`.
- **S04 `CitationIn`** (OPENAPI_COMPONENT; NEWLY_REFERENCED_BY_OPERATION): definition reused; complete contract is in the JSON catalog.
- **S05 `ComicPanel`** (OPENAPI_COMPONENT; CHANGED): added fields: `appearance_references`, `image_brief`.
- **S06 `CoverBriefIn`** (OPENAPI_COMPONENT; CHANGED): added fields: `typography_intent`.
- **S07 `EditNoteIn`** (OPENAPI_COMPONENT; ADDED): added fields: `citations`, `expected_version`, `text`, `title`; required fields added: `citations`, `expected_version`, `text`, `title`.
- **S08 `EmbeddingIndexEditIn`** (OPENAPI_COMPONENT; ADDED): added fields: `dimensions`, `entities`, `expected_version`, `registration_id`, `title`; required fields added: `entities`, `expected_version`, `title`.
- **S09 `EmbeddingIndexIn`** (OPENAPI_COMPONENT; CHANGED): added fields: `dimensions`, `registration_id`.
- **S10 `EntityRef`** (OPENAPI_COMPONENT; CHANGED): changed fields: `entity_type`; `entity_type` enum adds ['RESEARCH']; removes [].
- **S11 `HTTPValidationError`** (OPENAPI_COMPONENT; NEWLY_REFERENCED_BY_OPERATION): definition reused; complete contract is in the JSON catalog.
- **S12 `JudgeModelActionIn`** (OPENAPI_COMPONENT; NEWLY_REFERENCED_BY_OPERATION): definition reused; complete contract is in the JSON catalog.
- **S13 `JudgeModelDispatchIn`** (OPENAPI_COMPONENT; NEWLY_REFERENCED_BY_OPERATION): definition reused; complete contract is in the JSON catalog.
- **S14 `JudgeModelPreviewIn`** (OPENAPI_COMPONENT; NEWLY_REFERENCED_BY_OPERATION): definition reused; complete contract is in the JSON catalog.
- **S15 `JudgeReviewIn`** (OPENAPI_COMPONENT; CHANGED): changed fields: `action`; `action` enum adds ['accept', 'intentional']; removes [].
- **S16 `JudgeRevisionTaskIn`** (OPENAPI_COMPONENT; ADDED): added fields: `assignee`, `description`, `expected_version`, `reviewer`, `title`; required fields added: `assignee`, `description`, `expected_version`, `reviewer`, `title`.
- **S17 `Layout`** (OPENAPI_COMPONENT; CHANGED): changed fields: `search_kind`; `search_kind` enum adds ['novel', 'volume', 'scene', 'timeline', 'organization', 'rule', 'story_graph', 'asset', 'workflow', 'review']; removes [].
- **S18 `ReplaceFileIn`** (OPENAPI_COMPONENT; ADDED): added fields: `access`, `author`, `content_base64`, `expected_version`, `filename`, `source`, `source_version`, `title`, `usage_notes`; required fields added: `content_base64`, `expected_version`, `filename`, `title`.
- **S19 `ResolveIn`** (OPENAPI_COMPONENT; CHANGED): changed fields: `kind`; `kind` enum adds ['novel', 'volume', 'scene', 'timeline', 'organization', 'rule', 'story_graph', 'asset', 'workflow', 'review']; removes [].
- **S20 `RestoreSourceIn`** (OPENAPI_COMPONENT; ADDED): added fields: `expected_version`, `restore_version`; required fields added: `expected_version`, `restore_version`.
- **S21 `SimulationRunIn`** (OPENAPI_COMPONENT; CHANGED): added fields: `scene_id`.
- **S22 `SimulatorContextIn`** (OPENAPI_COMPONENT; CHANGED): added fields: `scene_id`.
- **S23 `StoryboardBriefIn`** (OPENAPI_COMPONENT; NEWLY_REFERENCED_BY_OPERATION): definition reused; complete contract is in the JSON catalog.
- **S24 `StyleOpinionReviewIn`** (OPENAPI_COMPONENT; ADDED): added fields: `action`, `expected_version`, `reason`; required fields added: `action`, `expected_version`, `reason`.
- **S25 `TaskCancelIn`** (OPENAPI_COMPONENT; ADDED): added fields: `expected_revision`; required fields added: `expected_revision`.
- **S26 `ValidationError`** (OPENAPI_COMPONENT; NEWLY_REFERENCED_BY_OPERATION): definition reused; complete contract is in the JSON catalog.
- **S27 `app__experimental__research_library_api__VersionIn`** (OPENAPI_COMPONENT; NEWLY_REFERENCED_BY_OPERATION): definition reused; complete contract is in the JSON catalog.
- **S28 `app__experimental__story_graph_api__ContextIn`** (OPENAPI_COMPONENT; CHANGED): added fields: `scene_id`.
- **S29 `app.experimental.author_context_api.AuthorPreviewInput`** (SOURCE_DECLARED_VALIDATION_MODEL; ADDED): added fields: `calendar`, `chapter_id`, `chapter_version`, `character_id`, `generation_request_id`, `instruction`, `model_id`, `novel_id`, `operation`, `plot_plan_id`, `preview_digest`, `profile`, `provider_id`, `request_scope`, `revision_selection`, `revision_selection_digest`, `scene_id`, `selected_text`, `source`, `style`, `style_profile_id`, `world_time`; nested definitions changed: `AddedAuthorSource`, `AuthorRequestScope`, `AuthorSourceControl`, `CitationIn`, `SelectionIn`; required fields added: `chapter_id`, `chapter_version`, `model_id`, `novel_id`, `operation`, `provider_id`.
- **S30 `app.experimental.author_context_api.AuthorSourceCatalogInput`** (SOURCE_DECLARED_VALIDATION_MODEL; ADDED): added fields: `kind`, `provider_id`, `query`; required fields added: `provider_id`.
- **S31 `app.experimental.author_context_api.AuthorVariantsInput`** (SOURCE_DECLARED_VALIDATION_MODEL; CHANGED): nested definitions changed: `AddedAuthorSource`, `AuthorPreviewInput`, `AuthorRequestScope`, `CitationIn`.
- **S32 `app.experimental.comic_layouts.LayoutEdit`** (SOURCE_DECLARED_VALIDATION_MODEL; CHANGED): nested definitions changed: `AppearanceReference`, `ComicPanel`.
- **S33 `app.experimental.comic_layouts.LayoutIn`** (SOURCE_DECLARED_VALIDATION_MODEL; CHANGED): nested definitions changed: `AppearanceReference`, `ComicPanel`.
- **S34 `app.experimental.declarative_agents.SaveDefinitionIn`** (SOURCE_DECLARED_VALIDATION_MODEL; CHANGED): nested definitions changed: `AgentDefinition`.
- **S35 `app.experimental.declarative_agents.WorkflowAuthoring`** (SOURCE_DECLARED_VALIDATION_MODEL; CHANGED): nested definitions changed: `AgentDefinition`.
- **S36 `app.experimental.director.DirectorPlanIn`** (SOURCE_DECLARED_VALIDATION_MODEL; CHANGED): nested definitions changed: `CameraGrammar`.
- **S37 `app.experimental.embeddings.EmbeddingCapability`** (SOURCE_DECLARED_VALIDATION_MODEL; ADDED): added fields: `dimensions`, `input_types`, `local`, `model_id`, `model_revision`, `provider_id`, `verification`; required fields added: `dimensions`, `input_types`, `local`, `model_id`, `model_revision`, `provider_id`, `verification`.
- **S38 `app.experimental.embeddings.EmbeddingIndexEditIn`** (SOURCE_DECLARED_VALIDATION_MODEL; ADDED): added fields: `dimensions`, `entities`, `expected_version`, `registration_id`, `title`; nested definitions changed: `EntityRef`; required fields added: `entities`, `expected_version`, `title`.
- **S39 `app.experimental.embeddings.EmbeddingIndexIn`** (SOURCE_DECLARED_VALIDATION_MODEL; CHANGED): added fields: `dimensions`, `registration_id`; nested definitions changed: `EntityRef`.
- **S40 `app.experimental.embeddings.VectorRecord`** (SOURCE_DECLARED_VALIDATION_MODEL; CHANGED): nested definitions changed: `EntityRef`.
- **S41 `app.experimental.interactive_story.RestoreIn`** (SOURCE_DECLARED_VALIDATION_MODEL; ADDED): added fields: `expected_version`, `preview_digest`, `restore_version`; required fields added: `expected_version`, `preview_digest`, `restore_version`.
- **S42 `app.experimental.interactive_story.StorySpec`** (SOURCE_DECLARED_VALIDATION_MODEL; ADDED): added fields: `entry_node_id`, `graph_id`, `graph_record_ids`, `graph_version`, `max_steps`, `nodes`, `title`, `variables`; nested definitions changed: `Choice`, `StoryNode`, `Variable`; required fields added: `entry_node_id`, `graph_id`, `graph_version`, `nodes`, `title`.
- **S43 `app.experimental.interactive_story.VersionIn`** (SOURCE_DECLARED_VALIDATION_MODEL; ADDED): added fields: `expected_version`; required fields added: `expected_version`.
- **S44 `app.experimental.media.CoverBriefIn`** (SOURCE_DECLARED_VALIDATION_MODEL; CHANGED): added fields: `typography_intent`.
- **S45 `app.experimental.media.StoryboardBriefIn`** (SOURCE_DECLARED_VALIDATION_MODEL; ADDED): added fields: `expected_screenplay_version`, `privacy_level`, `prompt`, `reference_asset_ids`, `screenplay_id`, `shot_id`; required fields added: `expected_screenplay_version`, `screenplay_id`, `shot_id`.
- **S46 `app.experimental.model_benchmark.EvidenceReviewInput`** (SOURCE_DECLARED_VALIDATION_MODEL; ADDED): added fields: `expected_version`, `note`, `reviewed_identity_and_outputs`; required fields added: `expected_version`, `note`, `reviewed_identity_and_outputs`.
- **S47 `app.experimental.model_broker.BrokerRequest`** (SOURCE_DECLARED_VALIDATION_MODEL; CHANGED): added fields: `allow_cloud_fallback`, `require_confirmed_license`; changed fields: `policy`; `policy` enum adds ['PRIVACY_FIRST', 'BALANCED', 'COST_FIRST', 'QUALITY_FIRST', 'SPEED_FIRST']; removes [].
- **S48 `app.experimental.model_broker_api.BrokerGenerateInput`** (SOURCE_DECLARED_VALIDATION_MODEL; CHANGED): nested definitions changed: `AddedAuthorSource`, `AuthorPreviewInput`, `AuthorRequestScope`, `CitationIn`.
- **S49 `app.experimental.multilingual_editions.MemoryAdoptIn`** (SOURCE_DECLARED_VALIDATION_MODEL; ADDED): added fields: `expected_version`, `preview_digest`, `source_edition_id`, `source_segment_id`; required fields added: `expected_version`, `preview_digest`, `source_edition_id`, `source_segment_id`.
- **S50 `app.experimental.multilingual_editions.RestoreSegmentIn`** (SOURCE_DECLARED_VALIDATION_MODEL; ADDED): added fields: `expected_version`, `preview_digest`, `restore_version`; required fields added: `expected_version`, `preview_digest`, `restore_version`.
- **S51 `app.experimental.multilingual_editions.RuleIn`** (SOURCE_DECLARED_VALIDATION_MODEL; CHANGED): changed fields: `category`; `category` enum adds ['place', 'world']; removes [].
- **S52 `app.experimental.multilingual_editions.RuleReviewIn`** (SOURCE_DECLARED_VALIDATION_MODEL; CHANGED): changed fields: `action`; `action` enum adds ['lock', 'unlock']; removes [].
- **S53 `app.experimental.multilingual_editions.VersionIn`** (SOURCE_DECLARED_VALIDATION_MODEL; ADDED): added fields: `expected_version`; required fields added: `expected_version`.
- **S54 `app.experimental.narrative_judge.JudgeReviewIn`** (SOURCE_DECLARED_VALIDATION_MODEL; CHANGED): changed fields: `action`; `action` enum adds ['accept', 'intentional']; removes [].
- **S55 `app.experimental.narrative_judge.JudgeRevisionTaskIn`** (SOURCE_DECLARED_VALIDATION_MODEL; ADDED): added fields: `assignee`, `description`, `expected_version`, `reviewer`, `title`; required fields added: `assignee`, `description`, `expected_version`, `reviewer`, `title`.
- **S56 `app.experimental.narrative_judge_model.JudgeModelActionIn`** (SOURCE_DECLARED_VALIDATION_MODEL; ADDED): added fields: `expected_version`; required fields added: `expected_version`.
- **S57 `app.experimental.narrative_judge_model.JudgeModelDispatchIn`** (SOURCE_DECLARED_VALIDATION_MODEL; ADDED): added fields: `expected_version`, `reviewed_preview_digest`; required fields added: `expected_version`, `reviewed_preview_digest`.
- **S58 `app.experimental.narrative_judge_model.JudgeModelPreviewIn`** (SOURCE_DECLARED_VALIDATION_MODEL; ADDED): added fields: `expected_version`, `route_id`; required fields added: `expected_version`, `route_id`.
- **S59 `app.experimental.project_forks.VersionIn`** (SOURCE_DECLARED_VALIDATION_MODEL; ADDED): added fields: `expected_version`; required fields added: `expected_version`.
- **S60 `app.experimental.research_library.EditNoteIn`** (SOURCE_DECLARED_VALIDATION_MODEL; ADDED): added fields: `citations`, `expected_version`, `text`, `title`; nested definitions changed: `CitationIn`; required fields added: `citations`, `expected_version`, `text`, `title`.
- **S61 `app.experimental.research_library.ReplaceFileIn`** (SOURCE_DECLARED_VALIDATION_MODEL; ADDED): added fields: `access`, `author`, `content_base64`, `expected_version`, `filename`, `source`, `source_version`, `title`, `usage_notes`; required fields added: `content_base64`, `expected_version`, `filename`, `title`.
- **S62 `app.experimental.research_library.RestoreSourceIn`** (SOURCE_DECLARED_VALIDATION_MODEL; ADDED): added fields: `expected_version`, `restore_version`; required fields added: `expected_version`, `restore_version`.
- **S63 `app.experimental.research_library_api.VersionIn`** (SOURCE_DECLARED_VALIDATION_MODEL; ADDED): added fields: `expected_version`; required fields added: `expected_version`.
- **S64 `app.experimental.revision_intelligence.ProposalIn`** (SOURCE_DECLARED_VALIDATION_MODEL; CHANGED): nested definitions changed: `ExplanationIn`.
- **S65 `app.experimental.revision_intelligence.VersionCompareIn`** (SOURCE_DECLARED_VALIDATION_MODEL; ADDED): added fields: `after_version`, `before_version`, `chapter_id`, `current_version`; required fields added: `after_version`, `before_version`, `chapter_id`, `current_version`.
- **S66 `app.experimental.revision_intelligence.VersionComparisonEditIn`** (SOURCE_DECLARED_VALIDATION_MODEL; ADDED): added fields: `changes`, `expected_version`, `title`; nested definitions changed: `SemanticChangeIn`; required fields added: `expected_version`, `title`.
- **S67 `app.experimental.revision_intelligence.VersionComparisonReviewIn`** (SOURCE_DECLARED_VALIDATION_MODEL; ADDED): added fields: `action`, `expected_version`; required fields added: `action`, `expected_version`.
- **S68 `app.experimental.revision_intelligence.VersionComparisonSaveIn`** (SOURCE_DECLARED_VALIDATION_MODEL; ADDED): added fields: `changes`, `comparison`, `preview_digest`, `title`; nested definitions changed: `SemanticChangeIn`, `VersionCompareIn`; required fields added: `comparison`, `preview_digest`, `title`.
- **S69 `app.experimental.story_graph_api.ContextIn`** (SOURCE_DECLARED_VALIDATION_MODEL; CHANGED): added fields: `scene_id`.
- **S70 `app.experimental.story_simulator.SimulationRunIn`** (SOURCE_DECLARED_VALIDATION_MODEL; CHANGED): added fields: `scene_id`.
- **S71 `app.experimental.story_simulator.SimulatorContextIn`** (SOURCE_DECLARED_VALIDATION_MODEL; CHANGED): added fields: `scene_id`.
- **S72 `app.experimental.structured_forks.UniversePinConfirm`** (SOURCE_DECLARED_VALIDATION_MODEL; ADDED): added fields: `confirmed`, `expected_version`, `preview_digest`, `role`, `snapshot_id`, `target_project_id`; required fields added: `confirmed`, `expected_version`, `preview_digest`, `role`, `snapshot_id`, `target_project_id`.
- **S73 `app.experimental.structured_forks.UniversePinIn`** (SOURCE_DECLARED_VALIDATION_MODEL; ADDED): added fields: `expected_version`, `role`, `snapshot_id`, `target_project_id`; required fields added: `expected_version`, `role`, `snapshot_id`, `target_project_id`.
- **S74 `app.experimental.structured_forks.UniverseSnapshotConfirm`** (SOURCE_DECLARED_VALIDATION_MODEL; ADDED): added fields: `allow_local_copy`, `license`, `preview_digest`, `records`, `request_id`, `title`, `universe_key`; nested definitions changed: `UniverseSelection`; required fields added: `allow_local_copy`, `license`, `preview_digest`, `records`, `request_id`, `title`, `universe_key`.
- **S75 `app.experimental.structured_forks.UniverseSnapshotIn`** (SOURCE_DECLARED_VALIDATION_MODEL; ADDED): added fields: `allow_local_copy`, `license`, `records`, `title`, `universe_key`; nested definitions changed: `UniverseSelection`; required fields added: `allow_local_copy`, `license`, `records`, `title`, `universe_key`.
- **S76 `app.experimental.style_analysis_model.StyleOpinionReviewIn`** (SOURCE_DECLARED_VALIDATION_MODEL; ADDED): added fields: `action`, `expected_version`, `reason`; required fields added: `action`, `expected_version`, `reason`.
- **S77 `app.experimental.ux.Layout`** (SOURCE_DECLARED_VALIDATION_MODEL; CHANGED): changed fields: `search_kind`; `search_kind` enum adds ['novel', 'volume', 'scene', 'timeline', 'organization', 'rule', 'story_graph', 'asset', 'workflow', 'review']; removes [].
- **S78 `app.experimental.ux.ResolveIn`** (SOURCE_DECLARED_VALIDATION_MODEL; CHANGED): changed fields: `kind`; `kind` enum adds ['novel', 'volume', 'scene', 'timeline', 'organization', 'rule', 'story_graph', 'asset', 'workflow', 'review']; removes [].
- **S79 `app.experimental.ux.ResumeIn`** (SOURCE_DECLARED_VALIDATION_MODEL; CHANGED): nested definitions changed: `Layout`.
- **S80 `app.experimental.ux.TaskCancelIn`** (SOURCE_DECLARED_VALIDATION_MODEL; ADDED): added fields: `expected_revision`; required fields added: `expected_revision`.

## Verification limits

- Source hashes were rechecked against the published commit after extraction.
- No model inference, provider request, external network service, application server or lifespan was started by this extraction.
- Some request bodies are manually validated and are incompletely exposed by OpenAPI; the separate source-model entries record those reliably identified validation classes.
- Source-difference labels inspect referenced functions, not every transitive dependency.
- This catalog does not change historical test evidence, audit status, API enablement, permissions or runtime code.

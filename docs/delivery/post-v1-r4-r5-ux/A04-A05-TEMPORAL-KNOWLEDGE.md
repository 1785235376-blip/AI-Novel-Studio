# A04 / A05: temporal graph and fictional knowledge

Classification: **EXTEND** the R3 world/planning authority. This document is an implementation contract, not a claim of model quality or user acceptance.

## Authority and persistence

- `StoryGraphService` extends `WorldService`. It stores typed `STORY_CONCEPT`, `STORY_RELATION`, and `KNOWLEDGE_EVENT` records in the existing isolated `world_records` collection. Characters and locations remain existing IDs. Scenes remain existing planning node IDs. Organizations, historical events, rules, and psychology use existing reviewed world records.
- Review, version history, optimistic concurrency, archive/reopen, and experimental Canon updates reuse `WorldService.review` and its one scope transaction. Only explicitly approved WORLD_FACT relations promote to experimental Canon. Beliefs, research, speculation, and knowledge events remain reviewed metadata. No legacy Canon or manuscript writes occur.
- Additive `story_graph_index` metadata is in the same File/PostgreSQL scope document; no new SQL migration or graph database. Graph changes refresh the changed record and dependent subgraph atomically. Queries revalidate current evidence instead of trusting cached index status. An external chapter/entity change immediately excludes derived stale content, even before manual index recomputation.
- Legacy world endpoints and its existing inbox binding exclude all extension kinds. Their flag cannot bypass the new capability gates. Do not register an unfiltered graph inbox binding: knowledge records additionally require the mind flag.

## Routes and capabilities

Prefix: `/api/novels/{nid}/experimental/story-graph`.

- `GET /catalog`, `GET/POST /records`, `GET/PUT /records/{id}`, `GET /records/{id}/history`.
- `POST /records/{id}/{approve,reject,reopen,archive}` delegates to existing world review authority.
- `GET /records/{id}/impact`, `POST /records/{id}/recompute` are version-fenced and bounded.
- `GET /query?chapter_id=...&character_id=...&world_time=...&calendar=...` supplies author or character projections. Omit character only in the author view.
- `POST /character-context` takes character ID, chapter ID, optional world time, and calendar. No model is called.
- `temporal_story_graph_v2` requires `world_character_engines_v2`; `character_mind_v2` requires the temporal graph. Registry/composition integration is owned by the wave lead. All remain default-off and V1 acceptance disables them.
- Author catalog, record details/history/impact, and omniscient queries require existing `domain.write`. Character projection requires existing `domain.read`; mutations and review require their existing permissions. This is a fictional viewpoint filter, not a new character-to-user account ACL.

## Time and knowledge semantics

- Narrative sequence uses actual chapter order plus event order. `world_time` is separate, allowing flashbacks. `valid_from` is inclusive, `valid_to` exclusive; `until_chapter_id` is a separate exclusive narrative endpoint.
- Null world time remains unknown. A world-time query excludes records with no temporal evidence, rather than coercing them to zero or treating them as timeless truth. With no world-time query, results use narrative chronology and display unknown time explicitly.
- Contradictory assertions remain separate typed relations. They are not merged into one claim or one time. The relation list is a real query of reviewed records; it does not fake a spatial graph layout.
- LEARN, HEARSAY, FORGET, MISUNDERSTAND, CORRECT, GOAL_CHANGE, and SET_STATE are explicit, versioned review events. Research, speculation, and another character's belief cannot silently become known world facts.
- False beliefs transmit only their explicitly authored belief text, never the true referenced statement or hidden endpoints. Goals, fears, values, emotion, and intent use explicit states. Motives default to HYPOTHESIS. Psychology references must belong to the same existing character.
- Later stale or revoked knowledge changes leave a fail-closed tombstone, preventing fallback from resurrecting older secrets. Explicit correction can establish a new current state. Time rollback replays the earlier valid event sequence.

## Character context boundary

`character_context(nid, scope, character_id, chapter_id, world_time=None, calendar='story')` returns `CHARACTER_KNOWLEDGE_V1`: separate facts, beliefs, false beliefs, secrets, goals, fears, values, emotion and intent; current evidence record/chapter IDs and versions; and `context_digest`.

Unknown relations, concept titles, hidden counts, full entity descriptions, chapter contents, evidence quotations, and another character's psychology are not serialized. Character graph counts include only visible relations. No author catalog is fetched while the panel is in character mode. Changing viewpoint/chapter immediately removes the previous projection from the UI.

The generation integration must **replace** omniscient context with this projection before constructing the Adapter request, not append it beside old world/character/research content or rely on an instruction to hide secrets. The endpoint and current captured-request contract test alone do not establish end-to-end integration in the main generation pipeline. The wave lead owns that integration and exact Adapter capture test.

## Limits and validation boundaries

- Scope is limited to 5,000 world records and semantic dependency depth 128. No scan, timer, model request, paid service, or unbounded recomputation starts automatically.
- Collaboration chapter sources must actually belong to the requested branch. Without the branch source adapter, reads/writes fail closed instead of using base manuscript evidence. Metadata remains scope-isolated.
- Real File service/API and component tests are implemented. Tests are parameterized for genuine PostgreSQL with `TEST_POSTGRES_DATABASE_URL`; absent local PostgreSQL is NOT_RUN, never a simulated pass. Hosted CI must enforce its no-silent-skip gate.
- No real-model, literary-quality, human psychology, or user-acceptance claims. The source snapshot is local-only; selecting a cloud provider is not permission to transmit it.
- Evidence quotes are checked at exact Unicode code-point offsets. The author form edits the primary quote and preserves any additional existing evidence links.
- Browser integration/geometry tests are a separate gate from component tests. `frontend/tests/e2e/r4-story-graph.spec.ts` is authored for the integrated real File API. Local Chromium failed before the test body because the environment denies its process-singleton socket; browser/geometry remain NOT_RUN pending hosted CI. Re-run against the exact integrated commit.

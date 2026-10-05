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

The main `JobManager` and shared author builder now **replace** omniscient context with this projection before constructing the Adapter request. They do not call the ordinary context builder in character mode and omit the automatic manuscript tail, selection, derived style and planning instruction. Strict author preview and generation share the same `AuthorPreparer`; mounted `/api` and `/api/v1` tests capture the production local-discovery Adapter request and serialized urllib payload using a synthetic wire. This verifies software request boundaries, not real-model quality.

## Limits and validation boundaries

- Scope is limited to 5,000 world records and semantic dependency depth 128. No scan, timer, model request, paid service, or unbounded recomputation starts automatically.
- Collaboration chapter sources must actually belong to the requested branch. Without the branch source adapter, reads/writes fail closed instead of using base manuscript evidence. Metadata remains scope-isolated.
- Real File service/API and component tests are implemented. Tests are parameterized for genuine PostgreSQL with `TEST_POSTGRES_DATABASE_URL`; absent local PostgreSQL is NOT_RUN, never a simulated pass. Hosted CI must enforce its no-silent-skip gate.
- No real-model, literary-quality, human psychology, or user-acceptance claims. The source snapshot is local-only; selecting a cloud provider is not permission to transmit it.
- Evidence quotes are checked at exact Unicode code-point offsets. The author form edits the primary quote and preserves any additional existing evidence links.
- Browser integration/geometry tests are a separate gate from component tests. `frontend/tests/e2e/r4-story-graph.spec.ts` is authored for the integrated real File API. Local Chromium failed before the test body because the environment denies its process-singleton socket; browser/geometry remain NOT_RUN pending hosted CI. Re-run against the exact integrated commit.

## Main-author coordinator binding (integration contract)

`character_author_context.py` provides a pure binding helper over the existing service:

1. Construct `CharacterContextSource(novel_id=..., scope=..., actor=..., token=..., branch=..., service=story_graph_service, user_instruction=original_request.instruction)`. It extends the existing read-context shape. The original user instruction must be captured **before** approved planning text is appended by generation payload enrichment.
2. Call `configure_character_job(job, ctx, character_id, chapter_id, world_time=None, calendar='story', authorize=current_authority_callback)`. The callback is zero-argument and closes over the captured trusted session; raise on denial. The helper clears selection/source, style and approved creation records, replaces enriched instruction with the explicit user instruction, binds exact job identity/scope and reviewed projection digest, and permits only LOCAL_ONLY continue/brainstorm.
3. Persist only `job.character_viewpoint` (coordinates, schema and digest). Never persist `job.character_context_resolver`, the callback, or the source context/token. A reloaded viewpoint job with no live resolver fails closed and needs a fresh preview.
4. `is_character_job(job)` must select the character branch even for an invalid empty descriptor. `resolve_character_author_context(job, cloud=route_is_remote)` returns the **whole replacement context**, `{'character_viewpoint': projection}`. Do not merge it into the ordinary context. Recheck it immediately before Adapter dispatch.
5. In the shared author builder, character mode uses an empty source unconditionally. It must bypass `job.source or chapter['content'][-2000:]`; `job.source=''` alone is insufficient. Omit creation/style-derived prompts. Unknown source text or IDs must not appear in prompt, context, metadata or omission audit fields.
6. The helper validates current flags, local route, original instruction, scope/identity, cancellation, permission, evidence digest and review revocation on each resolution. Unexpected projection fields/epistemic category changes are rejected rather than serialized.

The panel now accepts `onUseCharacter(characterId, chapterId)`, `onExitCharacter()` and `activeCharacterId`. The handoff is offered only for a successfully displayed narrative-chapter projection using the default story calendar; a world-time filter cannot silently change into a different generation point. It explains local-only continue/brainstorm and the omitted manuscript/selection/style/plan inputs. The composition root connects the shared coordinator and panel callbacks. Browser interaction remains its separate hosted-CI gate; component/request tests do not substitute for browser verification.


## Shared prepared-job and broker lifecycle

`create_author_preparer(manager, authorize, require_flag, generation_context, generation_payload, story_graph=...)` returns the shared callable object. Its `prepare_author(nid, AuthorPreviewInput, token, branch)` returns a PREPARED, unstarted, unpersisted job only after exact preview digest comparison; `prepare_preview` uses the same request mapping. `character_id`, `world_time`, and `calendar` are strict input fields. Character preview reports `CHARACTER_KNOWLEDGE_ONLY` and zero manuscript characters.

`JobManager.start_prepared(job)` persists and starts that exact object once; ordinary `create` delegates to it. Broker `before_dispatch` and `on_terminal` are transient zero-argument hooks. Only the actual Adapter-facing dispatch guard invokes `before_dispatch`; source preflight and request construction never mark a budget dispatched. Adapters may call the guard again after metadata preparation, so the broker hook remains idempotent. The worker invokes `on_terminal` once in `finally`, including cancellation and failures. Settlement failure preserves draft output, reports `TERMINAL_RECONCILIATION_REQUIRED`, and does not release ambiguous reservations or retry upstream work.

Only safe viewpoint coordinates/digest and `dispatch_hooks_required`/terminal accounting status are persisted. Callbacks, source context, tokens, and resolver closures are excluded from both public serialization and restart loading. A reloaded job without its required session guards cannot dispatch. Focused lifecycle tests cover exact-object start, duplicate start, failed persistence, cancelled/preflight/dispatch failures, missing restart guards, and conservative settlement errors.

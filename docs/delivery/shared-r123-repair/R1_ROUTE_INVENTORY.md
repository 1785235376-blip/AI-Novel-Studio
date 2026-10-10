# R1 original shared-route authority inventory

Scope: ordinary bug repair against fixed c6f2126115b52e17839d48efea091dc21ec08c61. Both `/api` and `/api/v1` mount the same router and dependencies. Experimental OFF/ON and V1 acceptance mode do not affect these original authority checks. The restrictive non-packaged collaboration allowlist is unchanged; an intentionally unadmitted route still returns 501.

## Authority and source contract

- A valid Host token identifies an actor only. Current identity membership, project/workspace ownership and original NOVEL read/write/review grants govern project data.
- Project-global legacy records require PROJECT-level authority (inherited WORKSPACE grants remain valid). A branch-only grant is not a project-wide grant. Explicit scope paths use the declared PROJECT/STORYLINE/BRANCH level and validate parents through the original authority.
- The newly guarded project-global routes reject `X-Branch-ID` with `BRANCH_SOURCE_UNAVAILABLE` after checking project and branch authority; they never label base manuscript/context/counts as branch data.
- Established chapter CAS/history continues to operate on the original project manuscript under a currently authorized, parent-validated scope. This is the existing project-level manuscript contract, not branch-exclusive manuscript storage. Valid project/workspace grants and existing branch grants remain accepted there; arbitrary/cross-project/cross-workspace branch ownership is rejected. New regressions exercise the original atomic CAS/audit service and read/history routes without weakening existing assertions. Generation, export, asset, media, workbench and experimental source-specific handlers keep their checks. Explicit branch-source requests on the newly guarded project-global paths are rejected rather than borrowing base manuscript data. No branch storage feature is introduced.
- Unpartitioned global asset workers and legacy derivative sources have no supported shared-runtime adapter; after project authorization they return 501. Legacy non-collaboration operation without a branch retains existing service behavior.
- Record-only paths resolve the owning project from persisted pending-canon/release-gate/asset records. Missing project ownership cannot default to allow. Lists filter by current project authority before pagination and total calculation; unowned global rows are excluded.

## Additional entry points without a static dependency

| Route | Authority / projection |
| --- | --- |
| GET `/novels` (both API prefixes) | Current session; project-read filter over actual repository list |
| GET `/novels` (unprefixed) | Delegates to the same authorized list, emits IDs only |
| POST `/novels` | Current workspace `domain.write`; link newly created project to that workspace |
| POST `/novels/import` | Current workspace `domain.write`; cache identity includes workspace and actor; authorize/link imported project before returning cached or new content |
| POST `/context-packs` (unprefixed) | Current project read and unsupported-branch rejection before original context service |
| GET `/workspaces` | Current actor workspace and active membership only |
| GET `/release-gates`, GET `/audit` | Explicit project filters authorized; global lists filtered by actual row ownership before totals/pagination |
| GET `/harness/access-audit[.csv]` | Project filter authorized; retained bounded journal filtered before pagination and CSV |
| DELETE `/harness/access-audit` | Global destructive operation unavailable in shared runtime; local behavior retained |
| `/novels/{nid}/adaptations...` | Existing operation-specific branch authorization retained; missing branch can no longer bypass it in shared mode |

## Explicit route dependencies

`read`, `write`, and `review` below refer to original `domain.*` permissions, not inferred roles. `_shared_scope_*` uses exact scope-path authority; `_shared_pending_review`, `_shared_gate_*`, and `_shared_asset_*` resolve persisted ownership; `_shared_worker_*` additionally rejects the unsupported shared source.

| Method | Original path (both prefixes) | Handler | Dependency |
| --- | --- | --- | --- |
| GET | `/harness/context` | `harness_context` | `[Depends(_shared_project_read)]` |
| POST | `/workspaces/{workspace_id}/projects/{project_id}/storylines` | `create_storyline` | `[Depends(_shared_scope_write)]` |
| GET | `/workspaces/{workspace_id}/projects/{project_id}/storylines` | `list_storylines` | `[Depends(_shared_scope_read)]` |
| POST | `/workspaces/{workspace_id}/projects/{project_id}/storylines/{storyline_id}/branches` | `create_branch` | `[Depends(_shared_scope_write)]` |
| GET | `/workspaces/{workspace_id}/projects/{project_id}/storylines/{storyline_id}/branches` | `list_branches` | `[Depends(_shared_scope_read)]` |
| GET | `/workspaces/{workspace_id}/projects/{project_id}/storylines/{storyline_id}/branches/{branch_id}` | `get_branch` | `[Depends(_shared_scope_read)]` |
| POST | `/workspaces/{workspace_id}/projects/{project_id}/storylines/{storyline_id}/branches/{branch_id}/narrative/mysteries/{item_id}/transition` | `scoped_mystery_transition` | `[Depends(_shared_scope_write)]` |
| POST | `/workspaces/{workspace_id}/projects/{project_id}/storylines/{storyline_id}/branches/{branch_id}/narrative/proposals/{proposal_id}/accept` | `scoped_proposal_accept` | `[Depends(_shared_scope_review)]` |
| GET | `/novels/{nid}` | `get_novel` | `[Depends(_shared_project_read)]` |
| PUT | `/novels/{nid}` | `update_novel` | `[Depends(_shared_project_write)]` |
| GET | `/novels/{nid}/chapters` | `chapters` | `[Depends(_shared_project_read)]` |
| GET | `/novels/{nid}/chapters/archived` | `archived_chapters` | `[Depends(_shared_project_read)]` |
| PUT | `/novels/{nid}/characters/{character_id}` | `upsert_character` | `[Depends(_shared_project_write)]` |
| PUT | `/novels/{nid}/locations/{location_id}` | `upsert_location` | `[Depends(_shared_project_write)]` |
| PUT | `/novels/{nid}/timeline/{event_id}` | `upsert_timeline_event` | `[Depends(_shared_project_write)]` |
| PUT | `/novels/{nid}/foreshadowing/{foreshadowing_id}` | `upsert_foreshadowing` | `[Depends(_shared_project_write)]` |
| GET | `/novels/{nid}/foreshadowing/reminders` | `foreshadowing_reminders` | `[Depends(_shared_project_read)]` |
| PUT | `/novels/{nid}/relationships/{relationship_id}` | `upsert_relationship` | `[Depends(_shared_project_write)]` |
| GET | `/novels/{nid}/outline` | `get_outline` | `[Depends(_shared_project_read)]` |
| PUT | `/novels/{nid}/outline` | `update_outline` | `[Depends(_shared_project_write)]` |
| PUT | `/novels/{nid}/volumes/{volume_id}` | `upsert_volume` | `[Depends(_shared_project_write)]` |
| PUT | `/novels/{nid}/scenes/{scene_id}` | `upsert_scene` | `[Depends(_shared_project_write)]` |
| PUT | `/novels/{nid}/story-routes/{route_id}` | `upsert_story_route` | `[Depends(_shared_project_write)]` |
| GET | `/novels/{nid}/story-routes` | `story_routes` | `[Depends(_shared_project_read)]` |
| GET | `/novels/{nid}/secrets` | `secrets` | `[Depends(_shared_project_read)]` |
| GET | `/context-preview` | `context_preview` | `[Depends(_shared_project_read)]` |
| GET | `/pending-canon` | `pending` | `[Depends(_shared_project_read)]` |
| POST | `/pending-canon/{pid}/approve` | `approve` | `[Depends(_shared_pending_review)]` |
| POST | `/pending-canon/{pid}/reject` | `reject_pending` | `[Depends(_shared_pending_review)]` |
| POST | `/novels/{nid}/asset-tasks/recover` | `recover_all_asset_tasks` | `[Depends(_shared_worker_write)]` |
| GET | `/novels/{nid}/asset-tasks/stats` | `asset_task_stats` | `[Depends(_shared_project_read)]` |
| POST | `/novels/{nid}/asset-tasks/claim` | `claim_asset_tasks` | `[Depends(_shared_worker_write)]` |
| POST | `/novels/{nid}/asset-tasks/dispatch` | `dispatch_asset_tasks` | `[Depends(_shared_worker_write)]` |
| POST | `/novels/{nid}/asset-tasks/timeout` | `timeout_asset_tasks` | `[Depends(_shared_worker_write)]` |
| POST | `/novels/{nid}/asset-tasks/worker/run-once` | `run_asset_task_worker` | `[Depends(_shared_worker_write)]` |
| POST | `/novels/{nid}/asset-tasks/worker/start` | `start_asset_task_worker` | `[Depends(_shared_worker_write)]` |
| POST | `/novels/{nid}/asset-tasks/worker/stop` | `stop_asset_task_worker` | `[Depends(_shared_worker_write)]` |
| GET | `/novels/{nid}/asset-tasks/worker/status` | `asset_task_worker_status` | `[Depends(_shared_worker_read)]` |
| POST | `/projects/{project_id}/continuity/checks` | `continuity_checks` | `[Depends(_shared_project_write)]` |
| POST | `/novels/{nid}/continuity/scan-chapter` | `scan_chapter_continuity` | `[Depends(_shared_project_write)]` |
| POST | `/novels/{nid}/characters/consistency-check` | `character_consistency_check` | `[Depends(_shared_project_write)]` |
| GET | `/projects/{project_id}/continuity/findings` | `continuity_findings` | `[Depends(_shared_project_read)]` |
| GET | `/projects/{project_id}/continuity/findings/{finding_id}` | `continuity_finding` | `[Depends(_shared_project_read)]` |
| POST | `/projects/{project_id}/continuity/findings/{finding_id}/resolve` | `resolve_continuity_finding` | `[Depends(_shared_project_review)]` |
| POST | `/projects/{project_id}/narrative/threads` | `create_narrative_thread` | `[Depends(_shared_project_write)]` |
| POST | `/projects/{project_id}/narrative/foreshadowing` | `create_narrative_foreshadowing` | `[Depends(_shared_project_write)]` |
| GET | `/projects/{project_id}/narrative/state` | `narrative_state` | `[Depends(_shared_project_read)]` |
| POST | `/projects/{project_id}/narrative/mysteries` | `create_mystery` | `[Depends(_shared_project_write)]` |
| GET | `/projects/{project_id}/narrative/mysteries` | `list_mysteries` | `[Depends(_shared_project_read)]` |
| GET | `/projects/{project_id}/narrative/mysteries/{item_id}` | `get_mystery` | `[Depends(_shared_project_read)]` |
| POST | `/projects/{project_id}/narrative/mysteries/{item_id}/transition` | `transition_mystery_api` | `[Depends(_shared_project_write)]` |
| POST | `/projects/{project_id}/narrative/character-goals` | `create_character_goal` | `[Depends(_shared_project_write)]` |
| GET | `/projects/{project_id}/narrative/character-goals` | `list_character_goals` | `[Depends(_shared_project_read)]` |
| GET | `/projects/{project_id}/narrative/character-goals/{item_id}` | `get_character_goal` | `[Depends(_shared_project_read)]` |
| POST | `/projects/{project_id}/narrative/character-goals/{item_id}/transition` | `transition_character_goal_api` | `[Depends(_shared_project_write)]` |
| POST | `/projects/{project_id}/narrative/chapter-progress` | `record_chapter_progress` | `[Depends(_shared_project_write)]` |
| GET | `/projects/{project_id}/narrative/chapter-progress` | `list_chapter_progress` | `[Depends(_shared_project_read)]` |
| POST | `/projects/{project_id}/narrative/proposals` | `create_narrative_proposal` | `[Depends(_shared_project_write)]` |
| GET | `/projects/{project_id}/narrative/proposals` | `list_narrative_proposals` | `[Depends(_shared_project_read)]` |
| GET | `/projects/{project_id}/narrative/proposals/{proposal_id}` | `get_narrative_proposal` | `[Depends(_shared_project_read)]` |
| POST | `/projects/{project_id}/narrative/proposals/{proposal_id}/accept` | `accept_narrative_proposal` | `[Depends(_shared_project_review)]` |
| POST | `/projects/{project_id}/narrative/proposals/{proposal_id}/reject` | `reject_narrative_proposal` | `[Depends(_shared_project_review)]` |
| POST | `/projects/{project_id}/narrative/threads/{thread_id}/transition` | `transition_narrative_thread` | `[Depends(_shared_project_write)]` |
| POST | `/projects/{project_id}/narrative/foreshadowing/{item_id}/transition` | `transition_narrative_foreshadowing` | `[Depends(_shared_project_write)]` |
| POST | `/projects/{project_id}/narrative/expectations` | `create_narrative_expectation` | `[Depends(_shared_project_write)]` |
| POST | `/projects/{project_id}/narrative/checks` | `check_narrative_findings` | `[Depends(_shared_project_write)]` |
| GET | `/projects/{project_id}/narrative/findings` | `list_narrative_findings` | `[Depends(_shared_project_read)]` |
| GET | `/projects/{project_id}/narrative/findings/{finding_id}` | `get_narrative_finding` | `[Depends(_shared_project_read)]` |
| POST | `/projects/{project_id}/narrative/findings/{finding_id}/resolve` | `resolve_narrative_finding` | `[Depends(_shared_project_review)]` |
| GET | `/novels/{nid}/overview` | `novel_overview` | `[Depends(_shared_project_read)]` |
| GET | `/novels/{nid}/writing-goal` | `writing_goal` | `[Depends(_shared_project_read)]` |
| PUT | `/novels/{nid}/writing-goal` | `update_writing_goal` | `[Depends(_shared_project_write)]` |
| GET | `/novels/{nid}/research` | `novel_research` | `[Depends(_shared_project_read)]` |
| POST | `/novels/{nid}/research` | `create_novel_research` | `[Depends(_shared_project_write)]` |
| GET | `/research` | `research_index` | `[Depends(_shared_project_read)]` |
| GET | `/novels/{nid}/research/{research_id}` | `get_novel_research` | `[Depends(_shared_project_read)]` |
| PUT | `/novels/{nid}/research/{research_id}` | `update_novel_research` | `[Depends(_shared_project_write)]` |
| DELETE | `/novels/{nid}/research/{research_id}` | `delete_novel_research` | `[Depends(_shared_project_write)]` |
| GET | `/novels/{nid}/character-evolution` | `character_evolution` | `[Depends(_shared_project_read)]` |
| POST | `/novels/{nid}/character-evolution` | `create_character_evolution` | `[Depends(_shared_project_write)]` |
| GET | `/novels/{nid}/character-evolution/{evolution_id}` | `get_character_evolution` | `[Depends(_shared_project_read)]` |
| PUT | `/novels/{nid}/character-evolution/{evolution_id}` | `update_character_evolution` | `[Depends(_shared_project_write)]` |
| DELETE | `/novels/{nid}/character-evolution/{evolution_id}` | `delete_character_evolution` | `[Depends(_shared_project_write)]` |
| GET | `/novels/{nid}/characters/{character_id}/evolution` | `character_evolution_for_character` | `[Depends(_shared_project_read)]` |
| POST | `/novels/{nid}/characters/{character_id}/evolution` | `create_character_evolution_for_character` | `[Depends(_shared_project_write)]` |
| GET | `/novels/{nid}/visual-memory` | `visual_memory` | `[Depends(_shared_project_read)]` |
| POST | `/novels/{nid}/visual-memory` | `create_visual_memory` | `[Depends(_shared_project_write)]` |
| GET | `/memory` | `memory_index` | `[Depends(_shared_project_read)]` |
| POST | `/memory` | `create_memory_index` | `[Depends(_shared_project_write)]` |
| GET | `/novels/{nid}/visual-memory/{memory_id}` | `get_visual_memory` | `[Depends(_shared_project_read)]` |
| PUT | `/novels/{nid}/visual-memory/{memory_id}` | `update_visual_memory` | `[Depends(_shared_project_write)]` |
| DELETE | `/novels/{nid}/visual-memory/{memory_id}` | `delete_visual_memory` | `[Depends(_shared_project_write)]` |
| GET | `/assets/{asset_id}/derivatives` | `asset_derivatives` | `[Depends(_shared_asset_read)]` |
| POST | `/assets/{asset_id}/derivatives` | `create_asset_derivative` | `[Depends(_shared_asset_write)]` |
| GET | `/novels/{nid}/lore/evidence` | `list_lore_evidence` | `[Depends(_shared_project_read)]` |
| POST | `/novels/{nid}/lore/evidence` | `create_lore_evidence` | `[Depends(_shared_project_write)]` |
| GET | `/novels/{nid}/lore/proposals` | `list_lore_proposals` | `[Depends(_shared_project_read)]` |
| GET | `/novels/{nid}/world-rules` | `list_world_rules` | `[Depends(_shared_project_read)]` |
| POST | `/novels/{nid}/world-rules` | `create_world_rule` | `[Depends(_shared_project_write)]` |
| POST | `/novels/{nid}/lore/proposals` | `create_lore_proposal` | `[Depends(_shared_project_write)]` |
| POST | `/novels/{nid}/lore/proposals/{proposal_id}/approve` | `approve_lore_proposal` | `[Depends(_shared_project_review)]` |
| POST | `/novels/{nid}/lore/proposals/{proposal_id}/reject` | `reject_lore_proposal` | `[Depends(_shared_project_review)]` |
| POST | `/novels/{nid}/lore/proposals/{proposal_id}/approve-memory` | `approve_lore_memory` | `[Depends(_shared_project_review)]` |
| GET | `/novels/{nid}/memories` | `list_character_memories` | `[Depends(_shared_project_read)]` |
| GET | `/novels/{nid}/characters/{character_id}/memories` | `list_memories_for_character` | `[Depends(_shared_project_read)]` |
| POST | `/novels/{nid}/memories/{memory_id}/retract` | `retract_character_memory` | `[Depends(_shared_project_review)]` |
| GET | `/novels/{nid}/memory-snapshots` | `list_memory_snapshots` | `[Depends(_shared_project_read)]` |
| POST | `/novels/{nid}/memory-snapshots` | `create_memory_snapshot` | `[Depends(_shared_project_write)]` |
| POST | `/release-gates` | `evaluate_release_gate` | `[Depends(_shared_gate_write)]` |
| GET | `/release-gates/{gate_id}` | `get_release_gate` | `[Depends(_shared_gate_read)]` |
| GET | `/novels/{nid}/characters` | `get_characters` | `Depends(_shared_project_read)` |
| GET | `/novels/{nid}/locations` | `get_locations` | `Depends(_shared_project_read)` |
| GET | `/novels/{nid}/canon` | `get_canon` | `Depends(_shared_project_read)` |
| GET | `/novels/{nid}/foreshadowing` | `get_foreshadowing` | `Depends(_shared_project_read)` |
| GET | `/novels/{nid}/timeline` | `get_timeline` | `Depends(_shared_project_read)` |
| GET | `/novels/{nid}/relationships` | `get_relationships` | `Depends(_shared_project_read)` |
| GET | `/novels/{nid}/volumes` | `get_volumes` | `Depends(_shared_project_read)` |
| GET | `/novels/{nid}/scenes` | `get_scenes` | `Depends(_shared_project_read)` |
| GET | `/novels/{nid}/story_routes` | `get_story_routes` | `Depends(_shared_project_read)` |

## Regression evidence boundaries

`tests/test_shared_project_route_authority.py` reuses the real File/PostgreSQL repository fixture, trusted session resolver, identity/membership and permission services. Packaged cases obtain tokens through original `LocalSessionBootstrap.exchange`, then use the original middleware. The matrix covers owner, member, reader, nonmember, revoked membership, cross-workspace actor, both prefixes, OFF/ON/V1 flags, absent/unknown/revoked sessions, denied mutation readback, unsupported branch source and filtered counts/pagination.

Mounted HTTP tests cover original novel/chapter/archived/overview/goal/research/evolution/lore/dataset/outline reads; research and goal writes; pending-canon review; release-gate/audit/global lists; top-level context and workspace-linked project creation. In addition, every dependency registration is evaluated using a real Request and original authorization for each actor. That supplemental per-registration check is not falsely described as full end-to-end business-flow acceptance for every record mutation. Existing original test assertions and the three fixed-source reproducer scripts are not replaced or weakened.

All 40 product rows retain their prior bounded state (39 PARTIAL, F00 INTEGRATED). Historical independent second-slice review remains platform BLOCKED, and this work does not restart or substitute that review. No PR #37/#38 change, merge, release, deployment, real model/GPU/provider call or private user content is part of this regression.

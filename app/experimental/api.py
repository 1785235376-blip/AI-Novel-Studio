"""Experimental router composition, separate from the frozen API module."""
from fastapi import APIRouter
from .flags import flag_status

router = APIRouter()

@router.get('/experimental/features')
def features():
    return flag_status()

@router.get('/experimental/capabilities')
def capabilities():
    from .capabilities import capability_status
    return capability_status()

from .. import api as legacy_api
from ..config import settings
from .store import ExperimentalStore
from .flags import require_flag
from .planning import PlanningService
from .planning_api import create_planning_router
from .world import WorldService
from .world_api import create_world_router
from .imports import SemanticImportService
from .imports_api import create_import_router
from .teams import TeamService
from .teams_api import create_team_router
from ..dependencies import asset_provider_registry
from .media import MediaService, MediaAdapterRegistry
from .media_api import create_media_router
from .embeddings import EmbeddingService
from .embeddings_api import create_embeddings_router
from .voice_direction import DirectedAudiobookService
from .voice_direction_api import create_voice_direction_router, create_runtime_executor, resolve_runtime_provider
from .subtitle_timeline import SubtitleTimelineService
from .subtitle_timeline_api import create_subtitle_timeline_router
from .audiobook import LocalPcmMixer
from .audiobook_api import create_audiobook_router
from .inbox import UnifiedReviewInbox, ReviewBinding
from .inbox_api import create_inbox_router
from .legacy_inbox import register_legacy_bindings
from .ux import WorkspaceToolsService, TaskReader
from .author_task_projection import create_author_task_reader, create_author_task_canceller
from .ux_api import create_ux_router
from .search_sources import create_search_candidates
from ..services.import_apply_service import ImportApplyService

store = ExperimentalStore(settings.data_path(), settings.storage_backend, settings.database_url)
planning_service = PlanningService(store, legacy_api.novel_service, legacy_api.chapter_service)
world_service = WorldService(store, legacy_api.novel_service, legacy_api.chapter_service)
import_service = SemanticImportService(store, legacy_api.novel_service, legacy_api.chapter_service,
    apply_service=ImportApplyService(legacy_api.novel_service, settings.data_path()))
team_service = TeamService(store, legacy_api.novel_service, legacy_api.chapter_service)
media_service = MediaService(store, legacy_api.novel_service, legacy_api.chapter_service,
    assets=legacy_api.asset_library_service, screenplays=legacy_api.screenplay_service,
    registry=MediaAdapterRegistry(original_registry=asset_provider_registry))
embedding_service = EmbeddingService(store, legacy_api.novel_service, legacy_api.chapter_service,
    assets=legacy_api.asset_library_service, screenplays=legacy_api.screenplay_service)
audiobook_service = DirectedAudiobookService(store, legacy_api.novel_service, legacy_api.chapter_service,
    assets=legacy_api.asset_library_service, mixer=LocalPcmMixer())


def authorize(nid, token, branch, permission):
    # The existing resolver remains the authority; no new role or bypass exists.
    return legacy_api._workbench_authorize(nid, token, branch, permission)


for factory, service in ((create_planning_router, planning_service), (create_world_router, world_service),
                         (create_import_router, import_service), (create_team_router, team_service),
                         (create_media_router, media_service), (create_embeddings_router, embedding_service),
                         (create_audiobook_router, audiobook_service)):
    router.include_router(factory(service, authorize, require_flag))

inbox_service = UnifiedReviewInbox()

def review_guard(ctx, feature):
    def current():
        from fastapi import HTTPException
        require_flag('unified_review_inbox')
        require_flag(feature)
        if authorize(ctx.novel_id, ctx.token, ctx.branch, 'domain.review') != (ctx.actor, ctx.scope):
            raise HTTPException(403, {'code': 'REVIEW_AUTHORITY_CHANGED'})
    return current


def bind_domain(domain, service, feature, batch_actions=()):
    inbox_service.register(ReviewBinding(domain,
        lambda ctx: service.list_review_items(ctx.novel_id, ctx.scope),
        lambda ctx, rid, action, version: service.review(ctx.novel_id, ctx.scope, ctx.actor, rid, action, version,
            **({'reauthorize': review_guard(ctx, feature)} if domain == 'planning' else {})),
        feature, frozenset(batch_actions)))

bind_domain('planning', planning_service, 'advanced_planning_v2', ('reject',))
bind_domain('world', world_service, 'world_character_engines_v2', ('reject',))
bind_domain('import', import_service, 'semantic_import_v2', ('reject',))
bind_domain('agent_team', team_service, 'agent_team_recipes')
bind_domain('media', media_service, 'cover_storyboard_generation')
def read_audiobook_inbox(ctx):
    def current():
        from fastapi import HTTPException
        require_flag('unified_review_inbox')
        require_flag('audiobook_v2')
        if authorize(ctx.novel_id, ctx.token, ctx.branch, 'domain.read') != (ctx.actor, ctx.scope):
            raise HTTPException(403, {'code': 'REVIEW_AUTHORITY_CHANGED'})
    current()
    result = audiobook_service.as_actor(ctx.actor, audiobook_service.list_review_items, ctx.novel_id, ctx.scope)
    current()
    return result


def review_audiobook_inbox(ctx, rid, action, version):
    current = review_guard(ctx, 'audiobook_v2')
    current()
    result = audiobook_service.as_actor(ctx.actor, audiobook_service.review,
        ctx.novel_id, ctx.scope, ctx.actor, rid, action, version)
    current()
    return result


inbox_service.register(ReviewBinding('audiobook', read_audiobook_inbox,
    review_audiobook_inbox, 'audiobook_v2', frozenset()))
subtitle_timeline_service = SubtitleTimelineService(store, legacy_api.novel_service,
    legacy_api.chapter_service, audiobook_service, legacy_api.asset_library_service)
router.include_router(create_voice_direction_router(audiobook_service, authorize, require_flag))
router.include_router(create_subtitle_timeline_router(subtitle_timeline_service, authorize, require_flag))
register_legacy_bindings(inbox_service)
router.include_router(create_inbox_router(inbox_service, authorize, require_flag))


def read_legacy_workflow_tasks(ctx):
    from .. import workflow_api
    authorized = workflow_api.workflows(novel_id=ctx.novel_id, x_session_token=ctx.token)['items']
    definitions = [row for row in authorized if row.get('branch_id') == ctx.branch]
    result, truncated = [], len(definitions) > 20
    for definition in definitions[:20]:
        if definition.get('branch_id') != ctx.branch:
            continue
        rows = workflow_api.runs(workflow_id=definition['id'], x_session_token=ctx.token)['items']
        result.extend(rows[:50])
        truncated = truncated or len(rows) > 50
        if len(result) >= 200:
            truncated = True
            break
    return {'items': result[:200], 'has_more': truncated}


def read_voice_tasks(ctx):
    from fastapi import HTTPException
    from .voice_direction_api import voice_task_projection
    def current():
        require_flag('voice_direction_v2')
        if authorize(ctx.novel_id, ctx.token, ctx.branch, 'domain.read') != (ctx.actor, ctx.scope):
            raise HTTPException(403, {'code': 'VOICE_AUTHORITY_CHANGED'})
    current()
    value = voice_task_projection(audiobook_service, ctx.novel_id, ctx.scope, ctx.actor)
    current()
    return {**value, 'items': [{**row, 'novel_id': ctx.novel_id, 'scope': ctx.scope} for row in value['items']]}


# U07 is a read-only projection over existing task authorities. Each legacy
# reader executes its original access check with captured request authority.
workspace_tools_service = WorkspaceToolsService(
    store, legacy_api.novel_service, legacy_api.chapter_service,
    search_candidates=lambda ctx, service: create_search_candidates(legacy_api.collaboration_scope_service.repository)(ctx, service),
    finding_reader=lambda ctx: legacy_api.continuity_finding_service.list_findings(ctx.novel_id) if ctx.scope.get('mode') == 'local' else [],
    task_readers=(
        TaskReader('author_generation', '正文生成', 'history',
                   create_author_task_reader(legacy_api.jobs, authorize, require_flag,
                       lambda jid, token: legacy_api.generation(jid=jid, x_session_token=token)),
                   cancel=create_author_task_canceller(legacy_api.jobs, authorize, require_flag,
                       lambda jid, token: legacy_api.cancel(jid=jid, x_session_token=token))),
        TaskReader('workflows', 'Workflow 任务', 'workflow', read_legacy_workflow_tasks),
        TaskReader('semantic_import', '长篇导入', 'semantic_import_v2',
                   lambda ctx: import_service.jobs(ctx.novel_id, ctx.scope), 'semantic_import_v2'),
        TaskReader('media', '封面与分镜', 'cover_storyboard_generation',
                   lambda ctx: media_service.tasks(ctx.novel_id, ctx.scope), 'cover_storyboard_generation'),
        TaskReader('agent_team', '创作团队', 'agent_team_recipes',
                   lambda ctx: team_service.list_runs(ctx.novel_id, ctx.scope), 'agent_team_recipes'),
        TaskReader('audiobook', '有声书 V2', 'audiobook_v2',
                   lambda ctx: audiobook_service.as_actor(ctx.actor, audiobook_service.plans, ctx.novel_id, ctx.scope), 'audiobook_v2'),
        TaskReader('voice_direction', '声音导演任务', 'voice_direction_v2', read_voice_tasks, 'voice_direction_v2'),
        TaskReader('agents', 'Agent 任务', 'agents', lambda ctx: legacy_api.list_agent_jobs(
            novel_id=ctx.novel_id, agent_id=None, status=None, created_after=None,
            created_before=None, branch_id=ctx.branch, page=1, page_size=100,
            x_session_token=ctx.token)),
        TaskReader('exports', '导出任务', 'exports', lambda ctx: legacy_api.list_exports(
            novel_id=ctx.novel_id, branch_id=ctx.branch, status=None, limit=100, offset=0,
            x_branch_id=ctx.branch, x_session_token=ctx.token)),
        TaskReader('images', '图片任务', 'assets', lambda ctx: legacy_api.list_image_jobs(
            nid=ctx.novel_id, x_session_token=ctx.token, x_branch_id=ctx.branch)),
    ),
)
from .workspace_task_owners import extend_workspace_task_readers
workspace_tools_service.task_readers = extend_workspace_task_readers(
    workspace_tools_service.task_readers, legacy_api, import_service, team_service, media_service,
    audiobook_service, inbox_service, authorize, require_flag)
router.include_router(create_ux_router(workspace_tools_service, authorize, require_flag))


from .local_ai_inspection import LocalAIInspectionService
from .local_ai_inspection_api import create_local_ai_inspection_router
from ..dependencies import local_ai_discovery
embedding_service.discovery_bridge = local_ai_discovery.route_bridge


def require_inspection_host_session(token):
    # Use exactly the existing Model Center authority, resolved lazily after
    # app composition to avoid creating an alternate authentication boundary.
    from ..main import _model_center_mutation_authorization
    from fastapi import HTTPException
    if not _model_center_mutation_authorization(token).get('can_mutate'):
        raise HTTPException(401, {'code': 'SESSION_REQUIRED'})


local_ai_inspection_service = LocalAIInspectionService(
    store, legacy_api.novel_service, legacy_api.chapter_service,
    discovery_snapshot=local_ai_discovery.snapshot,
    adapter_definitions=media_service.registry.definitions,
)
router.include_router(create_local_ai_inspection_router(
    local_ai_inspection_service, authorize, require_flag, require_inspection_host_session))


from .writing_focus import WritingFocusService
from .writing_focus_api import create_writing_focus_router
writing_focus_service = WritingFocusService(store, legacy_api.novel_service, legacy_api.chapter_service, planning=planning_service)
workspace_tools_service.focus_reader = lambda ctx: {'preferences': writing_focus_service.preferences(ctx), 'pins': writing_focus_service.pinned(ctx)}
router.include_router(create_writing_focus_router(writing_focus_service, authorize, require_flag))


from .story_graph import StoryGraphService
from .story_graph_api import create_story_graph_router
story_graph_service = StoryGraphService(store, legacy_api.novel_service, legacy_api.chapter_service)
router.include_router(create_story_graph_router(story_graph_service, authorize, require_flag))


def variant_policy_guard(nid, scope, actor_id, provider_id, model_id, count):
    from fastapi import HTTPException
    # Local does not prove zero cost. Preserve active or persisted A06 policy,
    # even if someone disables its flag after creating a budget/reservation.
    if 'model_broker_v2' in enabled_flags():
        raise HTTPException(409, {'code': 'AUTHOR_VARIANTS_BROKER_POLICY_REQUIRES_RESERVATION'})
    model_broker_service.novels.get(nid)
    collections = model_broker_service.store.read(nid, scope).get('collections', {})
    if any(collections.get(name) for name in (model_broker_service.BUDGET, model_broker_service.LEDGER, model_broker_service.PRICES)):
        raise HTTPException(409, {'code': 'AUTHOR_VARIANTS_BROKER_POLICY_REQUIRES_RESERVATION'})
    return {'policy': 'NO_BROKER_BUDGET', 'budget_version': 0, 'local_cost_state': 'UNKNOWN', 'max_local_variants': 3}


from .author_context_api import create_author_context_router, create_author_preparer
author_preparer = create_author_preparer(legacy_api.jobs, authorize, require_flag,
    legacy_api._generation_request_context, legacy_api._generation_payload, story_graph=story_graph_service,
    revision_selection_validator=lambda nid, scope, value: revision_intelligence_service.selection(nid, scope, value),
    variant_policy_guard=variant_policy_guard)
router.include_router(create_author_context_router(
    legacy_api.jobs, authorize, require_flag,
    legacy_api._generation_request_context, legacy_api._generation_payload, preparer=author_preparer))


from ..runtime import runtime
from ..dependencies import model_center_service
from .model_broker import ModelBrokerService
from .model_broker_api import create_model_broker_router
from .model_benchmark import ModelBenchmarkService
from .model_benchmark_api import create_model_benchmark_router
model_broker_service = ModelBrokerService(store, legacy_api.novel_service, legacy_api.chapter_service,
    runtime=runtime, model_center=model_center_service, media_registry=media_service.registry,
    audio_resolver=resolve_runtime_provider)
media_service.broker = model_broker_service
media_service.broker_enabled = lambda: "model_broker_v2" in enabled_flags()
model_benchmark_service = ModelBenchmarkService(store, legacy_api.novel_service, legacy_api.chapter_service,
    broker=model_broker_service, media=media_service)
model_broker_service.evidence_reader = model_benchmark_service.evidence
router.include_router(create_model_broker_router(model_broker_service, authorize, require_flag,
    require_inspection_host_session, prepare_author=author_preparer.prepare_author, manager=legacy_api.jobs))
router.include_router(create_model_benchmark_router(model_benchmark_service, authorize, require_flag,
    require_inspection_host_session))


from .flags import enabled_flags
from .production_lineage import ProductionLineageService
from .production_lineage_api import create_production_lineage_router
production_lineage_service = ProductionLineageService(store, legacy_api.novel_service, legacy_api.chapter_service,
    assets=legacy_api.asset_library_service, media=media_service, broker=model_broker_service,
    broker_enabled=lambda: 'model_broker_v2' in enabled_flags())
router.include_router(create_production_lineage_router(production_lineage_service, authorize, require_flag))


from .style_analysis import StyleAnalysisService
from .style_analysis_api import create_style_analysis_router
from .narrative_judge import NarrativeJudgeService
from .narrative_judge_api import create_narrative_judge_router
style_analysis_service = StyleAnalysisService(store, legacy_api.novel_service, legacy_api.chapter_service,
    legacy_api.creation_workbench_service)
narrative_judge_service = NarrativeJudgeService(store, legacy_api.novel_service, legacy_api.chapter_service,
    legacy_api.creation_workbench_service, world_service, planning_service)
router.include_router(create_style_analysis_router(style_analysis_service, authorize, require_flag))
router.include_router(create_narrative_judge_router(narrative_judge_service, authorize, require_flag,
    preparer=author_preparer, manager=legacy_api.jobs, broker=model_broker_service,
    require_host_session=require_inspection_host_session))
def read_narrative_judge_reviews(ctx):
    from fastapi import HTTPException
    # Inbox read is weaker than the author's private review authority.
    require_flag('narrative_quality_judge_v2')
    if authorize(ctx.novel_id, ctx.token, ctx.branch, 'domain.write') != (ctx.actor, ctx.scope):
        raise HTTPException(403, {'code': 'REVIEW_AUTHORITY_CHANGED'})
    result = narrative_judge_service.list_review_items(ctx.novel_id, ctx.scope)
    require_flag('narrative_quality_judge_v2')
    if authorize(ctx.novel_id, ctx.token, ctx.branch, 'domain.write') != (ctx.actor, ctx.scope):
        raise HTTPException(403, {'code': 'REVIEW_AUTHORITY_CHANGED'})
    return result


inbox_service.register(ReviewBinding('narrative_judge', read_narrative_judge_reviews,
    feature='narrative_quality_judge_v2'))


from .change_impact import ChangeImpactService
from .change_impact_api import create_change_impact_router
change_impact_service = ChangeImpactService(store, legacy_api.novel_service, legacy_api.chapter_service,
    story_graph_service, production_lineage_service, planning_service, audiobook_service)
router.include_router(create_change_impact_router(change_impact_service, authorize, require_flag))


from .story_simulator import StorySimulatorService
from .story_simulator_api import create_story_simulator_router
story_simulator_service = StorySimulatorService(store, legacy_api.novel_service, legacy_api.chapter_service,
    planning_service, story_graph_service, broker=model_broker_service)
router.include_router(create_story_simulator_router(story_simulator_service, authorize, require_flag,
    preparer=author_preparer, manager=legacy_api.jobs, require_host_session=require_inspection_host_session))


from .research_library import ResearchLibraryService
from .research_library_api import create_research_library_router
research_library_service = ResearchLibraryService(store, legacy_api.novel_service, legacy_api.chapter_service,
    legacy=legacy_api.v1_capability_service, world=world_service)
embedding_service.research = research_library_service
router.include_router(create_research_library_router(research_library_service, authorize, require_flag))


from .revision_intelligence import RevisionIntelligenceService
from .revision_intelligence_api import create_revision_intelligence_router
revision_intelligence_service = RevisionIntelligenceService(store, legacy_api.novel_service, legacy_api.chapter_service)


def save_revision_document(chapter_id, document, expected_version, source, token, branch):
    require_flag('revision_intelligence_v2')
    return legacy_api.update_chapter(chapter_id,
        legacy_api.ChapterUpdate(document=document, version=expected_version, source=source),
        x_session_token=token, x_branch_id=branch)


def read_revision_job(job_id, token, branch):
    from fastapi import HTTPException
    require_flag('revision_intelligence_v2')
    row = legacy_api.generation(job_id, x_session_token=token)
    if (row.get('scope') or {}).get('branch_id') != branch:
        raise HTTPException(404, {'code': 'GENERATION_NOT_IN_CURRENT_BRANCH'})
    return row


router.include_router(create_revision_intelligence_router(revision_intelligence_service, authorize, require_flag,
    save_document=save_revision_document, read_job=read_revision_job))


from .reader_preflight import ReaderPreflightService
from .reader_preflight_api import create_reader_preflight_router
from .writing_sessions import WritingSessionsService
from .writing_sessions_api import create_writing_sessions_router


def read_author_candidates(ctx):
    from fastapi import HTTPException
    if authorize(ctx.novel_id, ctx.token, ctx.branch, 'domain.read') != (ctx.actor, ctx.scope):
        raise HTTPException(403, {'code': 'CANDIDATE_AUTHORITY_CHANGED'})
    visible = []
    # Snapshot identities only; each result uses the original current guard.
    for job in list(legacy_api.jobs.jobs.values()):
        if job.novel_id != ctx.novel_id or (job.scope or {}).get('branch_id') != ctx.branch:
            continue
        if ctx.scope.get('mode') != 'local' and job.actor_id != ctx.actor:
            continue
        try:
            current = legacy_api.generation(job.id, x_session_token=ctx.token)
        except HTTPException as exc:
            if exc.status_code not in {401, 403, 404}: raise
            continue
        if current.get('status') in {'COMPLETED', 'FAILED', 'CANCELLED'} and current.get('output'):
            visible.append({'id': current['id'], 'chapter_id': current['chapter_id'],
                'base_version': current.get('base_chapter_version'), 'status': current['status']})
            if len(visible) > 100: break
    if authorize(ctx.novel_id, ctx.token, ctx.branch, 'domain.read') != (ctx.actor, ctx.scope):
        raise HTTPException(403, {'code': 'CANDIDATE_AUTHORITY_CHANGED'})
    return {'items': visible[:100], 'truncated': len(visible) > 100}


def read_optional_workspace_tasks(ctx):
    if 'workspace_tools_v2' not in enabled_flags():
        return {'items': [], 'unavailable': [{'authority': 'workspace_tasks', 'label': '任务中心', 'reason': 'FEATURE_DISABLED'}], 'truncated': False}
    return workspace_tools_service.tasks(ctx, require_flag)


reader_preflight_service = ReaderPreflightService(store, legacy_api.novel_service, legacy_api.chapter_service,
    sources=writing_focus_service, assets=legacy_api.asset_library_service,
    task_reader=read_optional_workspace_tasks, candidate_reader=read_author_candidates)
writing_sessions_service = WritingSessionsService(store, legacy_api.novel_service, legacy_api.chapter_service,
    sources=writing_focus_service, task_reader=read_optional_workspace_tasks,
    history_reader=lambda ctx, cid: legacy_api.chapter_history(cid, x_session_token=ctx.token, x_branch_id=ctx.branch))
router.include_router(create_reader_preflight_router(reader_preflight_service, authorize, require_flag))
router.include_router(create_writing_sessions_router(writing_sessions_service, authorize, require_flag))


from .director import DirectorService
from .director_api import create_director_router
from .timeline_exchange import TimelineExchangeService
from .timeline_exchange_api import create_timeline_exchange_router
director_service = DirectorService(store, legacy_api.novel_service, legacy_api.chapter_service, legacy_api.screenplay_service)
timeline_exchange_service = TimelineExchangeService(store, legacy_api.novel_service, legacy_api.chapter_service,
    legacy_api.screenplay_service, legacy_api.asset_library_service, lineage=production_lineage_service)
router.include_router(create_director_router(director_service, authorize, require_flag))
router.include_router(create_timeline_exchange_router(timeline_exchange_service, authorize, require_flag))


from .portable_projects import PortableProjectsService
from .portable_projects_api import create_portable_projects_router
from .safe_batches import SafeBatchesService
from .safe_batches_api import create_safe_batches_router
from .safe_batch_voice import BatchVoiceAuthority
portable_projects_service = PortableProjectsService(store, legacy_api.novel_service,
    legacy_api.chapter_service, sources=writing_focus_service, assets=legacy_api.asset_library_service)
safe_batches_service = SafeBatchesService(store, legacy_api.novel_service,
    legacy_api.chapter_service, sources=writing_focus_service, reader=reader_preflight_service,
    media=media_service, broker=model_broker_service, flag_check=require_flag,
    voice=BatchVoiceAuthority(audiobook_service, create_runtime_executor, resolve_runtime_provider))
router.include_router(create_portable_projects_router(portable_projects_service, authorize, require_flag, require_inspection_host_session))
router.include_router(create_safe_batches_router(safe_batches_service, authorize, require_flag, require_inspection_host_session))

from .multilingual_editions import MultilingualEditionsService
from .multilingual_editions_api import create_multilingual_editions_router
multilingual_editions_service = MultilingualEditionsService(store, legacy_api.novel_service, legacy_api.chapter_service)
router.include_router(create_multilingual_editions_router(multilingual_editions_service, authorize, require_flag,
    preparer=author_preparer, broker=model_broker_service, manager=legacy_api.jobs,
    require_host_session=require_inspection_host_session))

from .template_library import TemplateLibraryService
from .template_library_api import create_template_library_router
from .declarative_agents import DeclarativeAgentsService
from .declarative_agents_api import create_declarative_agents_router
from .flags import enabled_flags
template_library_service = TemplateLibraryService(store, legacy_api.novel_service,
    legacy_api.chapter_service, planning=planning_service, enabled_features=enabled_flags)
safe_batches_service.templates = template_library_service
declarative_agents_service = DeclarativeAgentsService(store, legacy_api.novel_service,
    legacy_api.chapter_service, sources=writing_focus_service, broker=model_broker_service)
router.include_router(create_template_library_router(template_library_service, authorize, require_flag))
router.include_router(create_declarative_agents_router(declarative_agents_service, authorize, require_flag,
    preparer=author_preparer, manager=legacy_api.jobs, require_host_session=require_inspection_host_session))

from .interactive_story import InteractiveStoryService
from .interactive_story_api import create_interactive_story_router
interactive_story_service = InteractiveStoryService(store, legacy_api.novel_service, legacy_api.chapter_service,
    planning_service, story_graph_service, legacy_api.asset_library_service)
router.include_router(create_interactive_story_router(interactive_story_service, authorize, require_flag))

from .writer_room import WriterRoomService
from .writer_room_api import create_writer_room_router
writer_room_service = WriterRoomService(store, legacy_api.novel_service, legacy_api.chapter_service,
    sources=writing_focus_service, creation=legacy_api.creation_workbench_service, inbox=inbox_service,
    assets=legacy_api.asset_library_service, membership=lambda: legacy_api.membership_authorization_service,
    asset_authorize=lambda ctx: legacy_api._authorize_asset_project(ctx.novel_id, ctx.token, ctx.branch, 'domain.read'))
router.include_router(create_writer_room_router(writer_room_service, authorize, require_flag))

from .comic_layouts import ComicLayoutsService
from .comic_layouts_api import create_comic_layouts_router
comic_layouts_service = ComicLayoutsService(store, legacy_api.novel_service, legacy_api.chapter_service,
    legacy_api.screenplay_service, legacy_api.asset_library_service, lineage=production_lineage_service)
router.include_router(create_comic_layouts_router(comic_layouts_service, authorize, require_flag))

from .project_forks import ProjectForksService
from .project_forks_api import create_project_forks_router
project_forks_service = ProjectForksService(store, legacy_api.novel_service, legacy_api.chapter_service,
    sources=writing_focus_service, assets=legacy_api.asset_library_service)


def fork_write_authority(cid, token, branch):
    require_flag('project_forks_v2')
    require_inspection_host_session(token)
    current = legacy_api.chapter_service.get(cid)
    authorize(current['novel_id'], token, branch, 'domain.write')


def save_fork_document(cid, document, expected_version, source, token, branch):
    fork_write_authority(cid, token, branch)
    return legacy_api.update_chapter(cid, legacy_api.ChapterUpdate(document=document, version=expected_version, source=source),
        x_session_token=token, x_branch_id=branch)


def rename_fork_chapter(cid, title, expected_version, token, branch):
    fork_write_authority(cid, token, branch)
    return legacy_api.rename_chapter(cid, legacy_api.RenameIn(title=title, version=expected_version),
        x_session_token=token, x_branch_id=branch)


def archive_fork_chapter(cid, expected_version, token, branch):
    fork_write_authority(cid, token, branch)
    return legacy_api.archive_chapter(cid, expected_version, x_session_token=token, x_branch_id=branch)


def restore_fork_chapter(cid, expected_version, token, branch):
    fork_write_authority(cid, token, branch)
    return legacy_api.restore_archived_chapter(cid, expected_version, x_session_token=token, x_branch_id=branch)


router.include_router(create_project_forks_router(project_forks_service, authorize, require_flag,
    require_inspection_host_session, save_document=save_fork_document, rename_chapter=rename_fork_chapter,
    archive_chapter=archive_fork_chapter, restore_archive=restore_fork_chapter))

from .offline_sync import OfflineSyncService
from .offline_sync_api import create_offline_sync_router
offline_sync_service = OfflineSyncService(store, legacy_api.novel_service, legacy_api.chapter_service,
    sources=writing_focus_service)


def sync_write_authority(nid, token, branch):
    require_flag('offline_sync_v2')
    require_inspection_host_session(token)
    return authorize(nid, token, branch, 'domain.write')


def save_sync_document(cid, document, expected_version, source, token, branch):
    current = legacy_api.chapter_service.get(cid)
    sync_write_authority(current['novel_id'], token, branch)
    return legacy_api.update_chapter(cid, legacy_api.ChapterUpdate(document=document, version=expected_version, source=source),
        x_session_token=token, x_branch_id=branch)


def archive_sync_chapter(cid, expected_version, token, branch):
    current = legacy_api.chapter_service.get(cid)
    sync_write_authority(current['novel_id'], token, branch)
    return legacy_api.archive_chapter(cid, expected_version, x_session_token=token, x_branch_id=branch)


def create_sync_chapter(nid, title, document, token, branch):
    from fastapi import HTTPException
    from ..document import document_to_markdown
    authority = sync_write_authority(nid, token, branch)
    if authority[1] != {'mode': 'local', 'novel_id': nid} or branch:
        raise HTTPException(409, {'code': 'SYNC_BRANCH_WRITER_UNAVAILABLE'})
    # The caller durably claims this two-step original-authority write first.
    # Any interruption after create is UNKNOWN and must be reconciled, not retried.
    created = legacy_api.create_chapter(nid, legacy_api.ChapterIn(title=title, content=document_to_markdown(document)))
    current = legacy_api.chapter_service.get(created['id'])
    if (sync_write_authority(nid, token, branch) != authority or current['version'] != 1
            or current['content'] != created['content']):
        raise HTTPException(409, {'code': 'SYNC_CREATED_CHAPTER_CHANGED_OR_AUTHORITY_REVOKED'})
    return legacy_api.update_chapter(created['id'], legacy_api.ChapterUpdate(document=document,
        version=current['version'], source='OFFLINE_SYNC_APPLY'), x_session_token=token, x_branch_id=branch)


router.include_router(create_offline_sync_router(offline_sync_service, authorize, require_flag,
    require_inspection_host_session, save_document=save_sync_document, archive_chapter=archive_sync_chapter,
    create_chapter=create_sync_chapter))


from .first_use import FirstUseService, OriginalFirstUseAuthorities
from .first_use_api import create_first_use_router
from ..dependencies import collaboration_read_service
first_use_service = FirstUseService(store, OriginalFirstUseAuthorities(legacy_api, collaboration_read_service))
router.include_router(create_first_use_router(first_use_service, require_flag))

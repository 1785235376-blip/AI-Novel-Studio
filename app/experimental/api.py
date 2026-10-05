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
from .media import MediaService
from .media_api import create_media_router
from .embeddings import EmbeddingService
from .embeddings_api import create_embeddings_router
from .audiobook import AudiobookV2Service
from .audiobook_api import create_audiobook_router
from .inbox import UnifiedReviewInbox, ReviewBinding
from .inbox_api import create_inbox_router
from .legacy_inbox import register_legacy_bindings
from .ux import WorkspaceToolsService, TaskReader
from .ux_api import create_ux_router
from ..services.import_apply_service import ImportApplyService

store = ExperimentalStore(settings.data_path(), settings.storage_backend, settings.database_url)
planning_service = PlanningService(store, legacy_api.novel_service, legacy_api.chapter_service)
world_service = WorldService(store, legacy_api.novel_service, legacy_api.chapter_service)
import_service = SemanticImportService(store, legacy_api.novel_service, legacy_api.chapter_service,
    apply_service=ImportApplyService(legacy_api.novel_service, settings.data_path()))
team_service = TeamService(store, legacy_api.novel_service, legacy_api.chapter_service)
media_service = MediaService(store, legacy_api.novel_service, legacy_api.chapter_service,
    assets=legacy_api.asset_library_service, screenplays=legacy_api.screenplay_service)
embedding_service = EmbeddingService(store, legacy_api.novel_service, legacy_api.chapter_service,
    assets=legacy_api.asset_library_service, screenplays=legacy_api.screenplay_service)
audiobook_service = AudiobookV2Service(store, legacy_api.novel_service, legacy_api.chapter_service,
    assets=legacy_api.asset_library_service)


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
bind_domain('audiobook', audiobook_service, 'audiobook_v2')
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


# U07 is a read-only projection over existing task authorities. Each legacy
# reader executes its original access check with captured request authority.
workspace_tools_service = WorkspaceToolsService(
    store, legacy_api.novel_service, legacy_api.chapter_service,
    task_readers=(
        TaskReader('workflows', 'Workflow 任务', 'workflow', read_legacy_workflow_tasks),
        TaskReader('semantic_import', '长篇导入', 'semantic_import_v2',
                   lambda ctx: import_service.jobs(ctx.novel_id, ctx.scope), 'semantic_import_v2'),
        TaskReader('media', '封面与分镜', 'cover_storyboard_generation',
                   lambda ctx: media_service.tasks(ctx.novel_id, ctx.scope), 'cover_storyboard_generation'),
        TaskReader('agent_team', '创作团队', 'agent_team_recipes',
                   lambda ctx: team_service.list_runs(ctx.novel_id, ctx.scope), 'agent_team_recipes'),
        TaskReader('audiobook', '有声书 V2', 'audiobook_v2',
                   lambda ctx: audiobook_service.plans(ctx.novel_id, ctx.scope), 'audiobook_v2'),
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
router.include_router(create_ux_router(workspace_tools_service, authorize, require_flag))


from .local_ai_inspection import LocalAIInspectionService
from .local_ai_inspection_api import create_local_ai_inspection_router
from ..dependencies import local_ai_discovery


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
router.include_router(create_writing_focus_router(writing_focus_service, authorize, require_flag))


from .story_graph import StoryGraphService
from .story_graph_api import create_story_graph_router
story_graph_service = StoryGraphService(store, legacy_api.novel_service, legacy_api.chapter_service)
router.include_router(create_story_graph_router(story_graph_service, authorize, require_flag))


from .author_context_api import create_author_context_router, create_author_preparer
author_preparer = create_author_preparer(legacy_api.jobs, authorize, require_flag,
    legacy_api._generation_request_context, legacy_api._generation_payload, story_graph=story_graph_service,
    revision_selection_validator=lambda nid, scope, value: revision_intelligence_service.selection(nid, scope, value))
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
    runtime=runtime, model_center=model_center_service, media_registry=media_service.registry)
model_benchmark_service = ModelBenchmarkService(store, legacy_api.novel_service, legacy_api.chapter_service,
    broker=model_broker_service)
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
router.include_router(create_narrative_judge_router(narrative_judge_service, authorize, require_flag))
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
    planning_service, story_graph_service)
router.include_router(create_story_simulator_router(story_simulator_service, authorize, require_flag))


from .research_library import ResearchLibraryService
from .research_library_api import create_research_library_router
research_library_service = ResearchLibraryService(store, legacy_api.novel_service, legacy_api.chapter_service,
    legacy=legacy_api.v1_capability_service, world=world_service)
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


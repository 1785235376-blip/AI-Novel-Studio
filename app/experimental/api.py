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

def bind_domain(domain, service, feature, batch_actions=()):
    inbox_service.register(ReviewBinding(domain,
        lambda ctx: service.list_review_items(ctx.novel_id, ctx.scope),
        lambda ctx, rid, action, version: service.review(ctx.novel_id, ctx.scope, ctx.actor, rid, action, version),
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


from .author_context_api import create_author_context_router
router.include_router(create_author_context_router(
    legacy_api.jobs, authorize, require_flag,
    legacy_api._generation_request_context, legacy_api._generation_payload))


from .writing_focus import WritingFocusService
from .writing_focus_api import create_writing_focus_router
writing_focus_service = WritingFocusService(store, legacy_api.novel_service, legacy_api.chapter_service, planning=planning_service)
router.include_router(create_writing_focus_router(writing_focus_service, authorize, require_flag))


from .story_graph import StoryGraphService
from .story_graph_api import create_story_graph_router
story_graph_service = StoryGraphService(store, legacy_api.novel_service, legacy_api.chapter_service)
router.include_router(create_story_graph_router(story_graph_service, authorize, require_flag))

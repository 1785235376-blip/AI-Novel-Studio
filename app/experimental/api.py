"""Experimental router composition, separate from the frozen API module."""
from fastapi import APIRouter
from .flags import flag_status

router = APIRouter()

@router.get('/experimental/features')
def features():
    return flag_status()

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

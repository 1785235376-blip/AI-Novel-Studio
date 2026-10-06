"""Author-only impact projection and current-authority selective dispatch."""
from fastapi import APIRouter, Header

from .change_impact import ImpactRequest, LockInput, PreflightInput, RefreshInput, TaskVersion
from .production_lineage_api import PrivateProductionRoute, api_call


def create_change_impact_router(service, authorize, require_flag):
    router = APIRouter(prefix='/novels/{nid}/experimental/change-impact', tags=['Experimental change impact'], route_class=PrivateProductionRoute)

    def access(nid, token, branch):
        for flag in ('change_impact_v2', 'temporal_story_graph_v2', 'asset_lineage_v2'): require_flag(flag)
        # As with the temporal graph author view, a read-only collaborator must
        # never enumerate author-only secrets through dependency titles/counts.
        return authorize(nid, token, branch, 'domain.write')

    def fresh(nid, token, branch, actor, scope):
        def guard():
            if access(nid, token, branch) != (actor, scope): raise ValueError('CHANGE_IMPACT_AUTHORITY_CHANGED')
        return guard

    @router.get('/sources')
    def sources(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id)
        result = api_call(service.catalog, nid, scope)
        fresh(nid, x_session_token, x_branch_id, actor, scope)()
        return result

    @router.post('/query')
    def query(nid: str, body: ImpactRequest, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id)
        result = api_call(service.impact, nid, scope, body)
        fresh(nid, x_session_token, x_branch_id, actor, scope)()
        return result

    @router.put('/locks')
    def lock(nid: str, body: LockInput, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id)
        return api_call(service.set_lock, nid, scope, actor, body, fresh(nid, x_session_token, x_branch_id, actor, scope))

    @router.post('/preflights', status_code=201)
    def preflight(nid: str, body: PreflightInput, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id)
        return api_call(service.preflight, nid, scope, actor, body, fresh(nid, x_session_token, x_branch_id, actor, scope))

    @router.post('/preflights/{rid}/prepare', status_code=201)
    def prepare(nid: str, rid: str, body: RefreshInput, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id)
        return api_call(service.prepare, nid, scope, actor, rid, body, fresh(nid, x_session_token, x_branch_id, actor, scope))

    @router.get('/refreshes')
    def refreshes(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id)
        result = api_call(service.refreshes, nid, scope, actor)
        fresh(nid, x_session_token, x_branch_id, actor, scope)()
        return result

    @router.post('/refreshes/{rid}/execute')
    def execute(nid: str, rid: str, body: TaskVersion, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id)
        return api_call(service.execute, nid, scope, actor, rid, body.expected_task_version, fresh(nid, x_session_token, x_branch_id, actor, scope))

    @router.post('/refreshes/{rid}/cancel')
    def cancel(nid: str, rid: str, body: TaskVersion, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id)
        return api_call(service.cancel, nid, scope, actor, rid, body.expected_task_version, fresh(nid, x_session_token, x_branch_id, actor, scope))

    return router

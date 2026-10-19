"""Author-only impact projection and current-authority selective dispatch."""
from fastapi import APIRouter, Header, HTTPException, Query, Request

from .change_impact import DecisionInput, DecisionSaveInput, ImpactRequest, LockInput, PreflightInput, RefreshInput, TaskVersion
from .production_lineage_api import PrivateProductionRoute, api_call
from .storyboard_impact_adapter import SOURCE_KIND, observe_storyboard
from .common import StaleSourceError
from ..services.v1_capability_service import CapabilityVersionConflict


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

    def observed(request, nid, token, branch, actor, scope, source, callback):
        guard = fresh(nid, token, branch, actor, scope)
        def operation():
            if source['kind'] != SOURCE_KIND:
                result = callback(guard, None)
                guard()
                return result
            require_flag('narrative_production_v2')
            try:
                readers = service.storyboard_readers(request, token, branch)
                with observe_storyboard(nid, scope, actor, source['id'], readers, guard) as observation:
                    result = callback(guard, observation)
                guard()
                return result
            except PermissionError:
                raise HTTPException(403, {'code': 'CHANGE_IMPACT_ORIGINAL_OWNER_AUTHORITY_CHANGED'}) from None
            except HTTPException as exc:
                if exc.status_code == 422:
                    # An inner original invoker can map validation before this
                    # adapter regains control; do not echo its private DTO values.
                    raise HTTPException(422, {'code': 'CHANGE_IMPACT_STORYBOARD_EVIDENCE_INVALID'}) from None
                raise
            except (StaleSourceError, CapabilityVersionConflict):
                raise
            except ValueError as exc:
                # Strict owner validation must never serialize private DTO input.
                code = ('CHANGE_IMPACT_STORYBOARD_TARGET_LIMIT' if str(exc) == 'CHANGE_IMPACT_STORYBOARD_TARGET_LIMIT'
                        else 'CHANGE_IMPACT_STORYBOARD_EVIDENCE_INVALID')
                raise HTTPException(422, {'code': code}) from None
        return api_call(operation)

    @router.get('/sources')
    def sources(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id)
        result = api_call(service.catalog, nid, scope)
        fresh(nid, x_session_token, x_branch_id, actor, scope)()
        return result

    @router.post('/query')
    def query(nid: str, body: ImpactRequest, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id)
        return observed(request, nid, x_session_token, x_branch_id, actor, scope, body.source.model_dump(),
                        lambda guard, observation: service.impact(nid, scope, body, actor=actor, observation=observation))

    @router.put('/locks')
    def lock(nid: str, body: LockInput, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id)
        return api_call(service.set_lock, nid, scope, actor, body, fresh(nid, x_session_token, x_branch_id, actor, scope))

    @router.post('/decisions/preview')
    def preview_decisions(nid: str, body: DecisionInput, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id)
        return observed(request, nid, x_session_token, x_branch_id, actor, scope, body.source.model_dump(),
                        lambda guard, observation: service.preview_decisions(nid, scope, actor, body, guard, observation=observation))

    @router.post('/decisions', status_code=201)
    def save_decisions(nid: str, body: DecisionSaveInput, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id)
        return observed(request, nid, x_session_token, x_branch_id, actor, scope, body.source.model_dump(),
                        lambda guard, observation: service.save_decisions(nid, scope, actor, body, guard, observation=observation))

    @router.get('/decisions')
    def decisions(nid: str, request: Request, source_kind: str = Query(min_length=1, max_length=30), source_id: str = Query(min_length=1, max_length=240),
                  x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id)
        source = {'kind': source_kind, 'id': source_id}
        return observed(request, nid, x_session_token, x_branch_id, actor, scope, source,
                        lambda guard, observation: service.decisions(nid, scope, actor, {'source': source}, guard, observation=observation))

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

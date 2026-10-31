"""Author-only story fact associations through the original Host invoker."""
from fastapi import APIRouter, Header, HTTPException, Request

from ..experimental.production_lineage_api import PrivateProductionRoute
from .story_fact_bindings import FactUseIn, FactCapacityError
from ..experimental.common import StaleSourceError


def create_story_fact_router(service, storyboard_call, access, require_flag):
    router = APIRouter(route_class=PrivateProductionRoute)

    def call(request, nid, token, branch, operation, *, confirm=False):
        def authorized(actor, scope, guard):
            incarnation = service.store.incarnation(nid)
            def current():
                guard()
                require_flag('temporal_story_graph_v2')
                require_flag('change_impact_v2')
                require_flag('asset_lineage_v2')
                if (access(nid, token, branch, 'domain.write') != (actor, scope)
                        or service.store.incarnation(nid) != incarnation):
                    raise HTTPException(403, {'code': 'CREATIVE_STORY_FACT_AUTHORITY_CHANGED'})
            current()
            try:
                result = operation(actor, scope, current)
            except FactCapacityError as exc:
                current()
                reason = str(exc) if str(exc) in {'CREATIVE_STORY_FACT_TRAVERSAL_LIMIT', 'CREATIVE_STORY_FACT_CYCLE_OR_DEPTH'} else 'BOUNDED_EVIDENCE_REQUIRED'
                raise HTTPException(422, {'code': 'CREATIVE_STORY_FACT_BOUNDED_EVIDENCE_REQUIRED', 'blocker': reason}) from None
            except StaleSourceError:
                current()
                raise HTTPException(409, {'code': 'CREATIVE_STORY_FACT_SOURCE_CHANGED'}) from None
            except ValueError:
                # Validation errors from stored owner metadata may embed private
                # input values. Never serialize those values in this projection.
                current()
                raise HTTPException(422, {'code': 'CREATIVE_STORY_FACT_EVIDENCE_INVALID'}) from None
            except Exception:
                current()
                raise
            current()
            return result
        # Observation and pointer confirmation never mint a missing project epoch.
        with service.store.existing_owner_only():
            return storyboard_call(request, nid, token, branch, 'domain.review' if confirm else 'domain.write', authorized)

    @router.get('/story-facts')
    def facts(nid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id,
                    lambda actor, scope, guard: service.story_facts.catalog(nid, scope, actor, guard))

    @router.post('/documents/{rid}/shots/{shot_id}/fact-uses', status_code=201)
    def confirm(nid: str, rid: str, shot_id: str, request: Request, body: FactUseIn,
                x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id,
                    lambda actor, scope, guard: service.story_facts.confirm(nid, scope, actor, rid, shot_id, body, guard), confirm=True)

    @router.get('/documents/{rid}/fact-uses')
    def document_impact(nid: str, rid: str, request: Request,
                        x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id,
                    lambda actor, scope, guard: service.story_facts.impact(nid, scope, actor, document_id=rid, guard=guard))

    @router.get('/story-facts/{fact_id}/impact')
    def fact_impact(nid: str, fact_id: str, request: Request,
                    x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id,
                    lambda actor, scope, guard: service.story_facts.impact(nid, scope, actor, fact_id=fact_id, guard=guard))

    return router

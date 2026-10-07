from fastapi import APIRouter, Header, Response
from fastapi.routing import APIRoute
from pydantic import Field
from .common import api_call
from .embeddings import EmbeddingIndexIn, EmbeddingIndexEditIn, EmbeddingQueryIn, HybridQueryIn
from .media import StrictModel
from .visual_identity import VisualIdentityCheckIn


class EmbeddingActionIn(StrictModel):
    expected_version: int = Field(ge=1)


def create_embeddings_router(service, authorize, require_flag):
    service.research_guard = lambda: require_flag("research_library_v2")
    class GuardedRoute(APIRoute):
        def get_route_handler(self):
            handler = super().get_route_handler()
            async def guarded(request):
                nid, token, branch = request.path_params['nid'], request.headers.get('X-Session-Token'), request.headers.get('X-Branch-ID')
                permission = 'domain.read' if request.method == 'GET' or request.url.path.endswith(('/query', '/hybrid-query')) else 'domain.write'
                require_flag('visual_embeddings')
                authority = authorize(nid, token, branch, permission)
                response = await handler(request)
                require_flag('visual_embeddings')
                if authorize(nid, token, branch, permission) != authority:
                    from fastapi import HTTPException
                    raise HTTPException(403, {'code': 'EMBEDDING_AUTHORITY_CHANGED'})
                response.headers['Cache-Control'] = 'no-store'
                return response
            return guarded
    router = APIRouter(route_class=GuardedRoute, prefix="/novels/{nid}/experimental/embeddings", tags=["Experimental embeddings"])

    def access(nid, token, branch, permission="domain.read"):
        require_flag("visual_embeddings")
        return authorize(nid, token, branch, permission)

    def guard(nid, token, branch, actor, scope, permission):
        def verify():
            if access(nid, token, branch, permission) != (actor, scope):
                raise ValueError("EMBEDDING_SCOPE_CHANGED")
        return verify

    @router.get("/status")
    def status(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        access(nid, x_session_token, x_branch_id)
        return service.status()

    @router.get('/sources')
    def sources(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id)
        response.headers['Cache-Control'] = 'no-store'
        return api_call(service.catalog, nid, scope, actor)

    @router.get('/providers')
    def providers(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        access(nid, x_session_token, x_branch_id)
        response.headers['Cache-Control'] = 'no-store'
        return api_call(service.providers)

    @router.get("/indexes")
    def indexes(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id)
        return {"items": api_call(service.indexes, nid, scope, actor)}

    @router.post("/indexes", status_code=201)
    def create(nid: str, body: EmbeddingIndexIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, "domain.write")
        return api_call(service.create_index, nid, scope, actor, body,
                        guard(nid, x_session_token, x_branch_id, actor, scope, 'domain.write'))

    @router.put('/indexes/{rid}')
    def edit(nid: str, rid: str, body: EmbeddingIndexEditIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, 'domain.write')
        return api_call(service.edit_index, nid, scope, actor, rid, body,
                        guard(nid, x_session_token, x_branch_id, actor, scope, 'domain.write'))

    @router.get("/indexes/{rid}/records")
    def records(nid: str, rid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id)
        return {"items": api_call(service.records, nid, scope, rid, actor)}

    @router.post("/indexes/{rid}/{action}")
    def action(nid: str, rid: str, action: str, body: EmbeddingActionIn,
               x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, "domain.write")
        if action == "rebuild":
            return api_call(service.rebuild, nid, scope, actor, rid, body.expected_version,
                            guard(nid, x_session_token, x_branch_id, actor, scope, "domain.write"))
        return api_call(service.transition, nid, scope, actor, rid, action, body.expected_version,
                        guard(nid, x_session_token, x_branch_id, actor, scope, 'domain.write'))

    @router.post("/query")
    def query(nid: str, body: EmbeddingQueryIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id)
        return api_call(service.query, nid, scope, body, guard(nid, x_session_token, x_branch_id, actor, scope, "domain.read"), actor=actor)

    @router.post('/hybrid-query')
    def hybrid_query(nid: str, body: HybridQueryIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id)
        return api_call(service.query, nid, scope, body, guard(nid, x_session_token, x_branch_id, actor, scope, 'domain.read'), actor=actor)

    @router.get('/visual-identity/profiles')
    def profiles(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id)
        return api_call(service.visual_profiles, nid, scope, actor)

    @router.get('/visual-identity/checks')
    def visual_checks(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id)
        return api_call(service.visual_checks, nid, scope, actor)

    @router.get('/visual-identity/checks/{rid}')
    def visual_check(nid: str, rid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id)
        return api_call(service.visual_check, nid, scope, actor, rid)

    @router.get('/visual-identity/checks/{rid}/selection')
    def visual_selection(nid: str, rid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id)
        return api_call(service.visual_selection, nid, scope, actor, rid)

    @router.post('/visual-identity/checks', status_code=201)
    def create_visual_check(nid: str, body: VisualIdentityCheckIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, 'domain.write')
        return api_call(service.create_visual_check, nid, scope, actor, body,
                        guard(nid, x_session_token, x_branch_id, actor, scope, 'domain.write'))

    @router.post('/visual-identity/checks/{rid}/{action}')
    def visual_action(nid: str, rid: str, action: str, body: EmbeddingActionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, 'domain.write')
        return api_call(service.visual_action, nid, scope, actor, rid, action, body.expected_version,
                        guard(nid, x_session_token, x_branch_id, actor, scope, 'domain.write'))

    return router

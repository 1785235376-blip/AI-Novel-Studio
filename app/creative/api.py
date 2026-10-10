"""Explicit opt-in Creative Layer routes over the existing authority resolver."""
from fastapi import APIRouter, Header, HTTPException, Query, Response

from ..experimental.flags import enabled_flags
from ..experimental.production_lineage_api import PrivateProductionRoute, api_call
from ..experimental.store import canonical
from ..experimental.ux import ReadContext
from .models import (CreativeDocumentIn, CreativeDocumentUpdate, CreativeDocumentRestore, CreativeDocumentDerive,
                     DirectorProposalIn, DirectorProposalReview, DirectorModelPreview,
                     DirectorModelDispatch, ProposalAction, MODES, USER_MODES, LEGACY_MODES)

FLAG = "narrative_production_v2"


def create_creative_router(service, authorize, require_flag, *, require_host_session=None):
    router = APIRouter(prefix="/novels/{nid}/experimental/creative", tags=["Creative Layer V2"],
                       route_class=PrivateProductionRoute)

    def access(nid, token, branch, permission, *, gated=True):
        if gated:
            require_flag(FLAG)
        actor, scope = authorize(nid, token, branch, permission)
        service.store.key(nid, scope)
        if not isinstance(actor, str) or not actor:
            raise HTTPException(403, {"code": "CREATIVE_AUTHORITY_INVALID"})
        return actor, scope

    def invoke(nid, token, branch, permission, callback):
        def operation():
            actor, scope = access(nid, token, branch, permission)

            def guard():
                if access(nid, token, branch, permission) != (actor, scope):
                    raise HTTPException(403, {"code": "CREATIVE_AUTHORITY_CHANGED"})

            try:
                result = callback(actor, scope, guard)
            except Exception:
                # Recheck authority before returning a private error projection,
                # as well as before returning successful document content.
                guard()
                raise
            guard()
            return result
        return api_call(operation)

    @router.get("/capabilities")
    def capabilities(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        def operation():
            actor, scope = access(nid, x_session_token, x_branch_id, "domain.read", gated=False)
            enabled = FLAG in enabled_flags()
            can_mutate = False
            if enabled:
                try:
                    can_mutate = access(nid, x_session_token, x_branch_id, "domain.write") == (actor, scope)
                except HTTPException as exc:
                    if exc.status_code != 403:
                        raise
            if access(nid, x_session_token, x_branch_id, "domain.read", gated=False) != (actor, scope):
                raise HTTPException(403, {"code": "CREATIVE_AUTHORITY_CHANGED"})
            result = {"enabled": enabled, "modes": list(MODES if enabled else LEGACY_MODES), "can_mutate": can_mutate}
            if enabled:
                result.update(user_modes=list(USER_MODES), mode_aliases={"VIDEO_PLANNING": "PRODUCTION"},
                    director_proposals=True, proposal_generation="RULE_ASSISTED_WITH_OPTIONAL_REVIEWED_LOCAL_MODEL")
            return result
        return api_call(operation)

    @router.get("/documents")
    def documents(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: {"items": service.list(nid, scope)})

    @router.post("/documents", status_code=201)
    def create(nid: str, body: CreativeDocumentIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.create(nid, scope, actor, body, reauthorize=guard))

    @router.get("/documents/{rid}")
    def document(nid: str, rid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.get(nid, scope, rid))

    @router.put("/documents/{rid}")
    def update(nid: str, rid: str, body: CreativeDocumentUpdate, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.update(nid, scope, actor, rid, body.expected_version,
                          body.model_dump(exclude={"expected_version"}), reauthorize=guard))

    @router.delete("/documents/{rid}")
    def archive(nid: str, rid: str, expected_version: int = Query(ge=1), x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.archive(nid, scope, actor, rid, expected_version, reauthorize=guard))

    @router.post("/documents/{rid}/derive", status_code=201)
    def derive(nid: str, rid: str, body: CreativeDocumentDerive, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.derive(nid, scope, actor, rid, body, reauthorize=guard))

    @router.post("/documents/{rid}/restore")
    def restore(nid: str, rid: str, body: CreativeDocumentRestore, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.restore(nid, scope, actor, rid, body.expected_version,
                          body.restore_version, reauthorize=guard))

    @router.get("/documents/{rid}/history")
    def history(nid: str, rid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.history(nid, scope, rid))

    @router.get("/documents/{rid}/export")
    def export(nid: str, rid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        result = invoke(nid, x_session_token, x_branch_id, "domain.read",
                        lambda actor, scope, guard: service.export(nid, scope, rid))
        # The filename uses the server-created document identifier, not a title.
        return Response(canonical(result).encode("utf-8"), media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="creative-{result["document"]["id"]}.json"'})

    @router.get("/director-proposals")
    def proposals(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: {"items": service.proposals.list(nid, scope, actor)})

    @router.post("/director-proposals", status_code=201)
    def propose(nid: str, body: DirectorProposalIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.proposals.create(nid, scope, actor, body, guard=guard))

    def model_call(nid, token, branch, method, rid=None, body=None):
        def operation(actor, scope, guard):
            generation = service.proposals.generation
            if generation is None:
                raise HTTPException(409, {"code": "CREATIVE_MODEL_NOT_CONFIGURED"})
            if require_host_session is None:
                raise HTTPException(409, {"code": "CREATIVE_MODEL_HOST_AUTHORITY_REQUIRED"})
            def model_guard():
                guard()
                require_host_session(token)
            ctx = ReadContext(nid, scope, actor, token, branch)
            model_guard()
            try:
                result = ({"items": generation.catalog(ctx)} if method == "catalog"
                          else getattr(generation, method)(ctx, rid, body, model_guard))
            except Exception:
                model_guard()
                raise
            model_guard()
            return result
        return invoke(nid, token, branch, "domain.read" if method == "catalog" else "domain.write", operation)

    @router.get("/director-proposals/model-routes")
    def model_routes(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return model_call(nid, x_session_token, x_branch_id, "catalog")

    @router.get("/director-proposals/{rid}")
    def proposal(nid: str, rid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.proposals.get(nid, scope, actor, rid))

    @router.post("/director-proposals/{rid}/review")
    def review_proposal(nid: str, rid: str, body: DirectorProposalReview, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.proposals.review(nid, scope, actor, rid, body, guard=guard))

    @router.post("/director-proposals/{rid}/cancel")
    def cancel_proposal(nid: str, rid: str, body: ProposalAction, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.proposals.cancel(nid, scope, actor, rid, body, guard=guard))

    @router.post("/director-proposals/{rid}/preview")
    def preview_model(nid: str, rid: str, body: DirectorModelPreview, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return model_call(nid, x_session_token, x_branch_id, "preview", rid, body)

    @router.post("/director-proposals/{rid}/dispatch")
    def dispatch_model(nid: str, rid: str, body: DirectorModelDispatch, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return model_call(nid, x_session_token, x_branch_id, "dispatch", rid, body)

    @router.post("/director-proposals/{rid}/refresh")
    def refresh_model(nid: str, rid: str, body: ProposalAction, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return model_call(nid, x_session_token, x_branch_id, "refresh", rid, body)

    return router

"""Explicit opt-in Creative Layer routes over the existing authority resolver."""
from typing import Literal
from fastapi import APIRouter, Header, HTTPException, Query, Request, Response

from ..experimental.flags import enabled_flags
from ..experimental.production_lineage_api import PrivateProductionRoute, api_call
from ..experimental.store import canonical
from ..experimental.ux import ReadContext
from .models import (CreativeProductionDocumentIn, CreativeDocumentUpdate, CreativeDocumentRestore, CreativeDocumentDerive,
                     DirectorProposalIn, DirectorProposalReview, DirectorModelPreview,
                     DirectorModelDispatch, ProposalAction, MODES, USER_MODES, LEGACY_MODES)

from .adaptation_models import AdaptationIn, AdaptationReview, AdaptationPreview
from .storyboard import (StoryboardApproval, ShotImageBinding, ShotImageRequest, StoryboardTimelineDraft,
    ShotVideoRequest, ShotVideoBinding, StoryboardTimelineCreate, StoryboardVideoAdoption)

FLAG = "narrative_production_v2"


def create_creative_router(service, authorize, require_flag, *, require_host_session=None, model_host_authority=None):
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

    def capture_adaptation_host(request, token):
        if model_host_authority is None:
            raise HTTPException(403, {"code": "CREATIVE_MODEL_HOST_REQUIRED"})
        authority = model_host_authority(request, token)
        if not authority.principal:
            raise HTTPException(403, {"code": "CREATIVE_MODEL_HOST_BINDING_REQUIRED"})
        authority.guard()
        return authority

    def storyboard_call(request, nid, token, branch, permission, callback):
        # Asset-backed production planning shares the original trusted Host
        # invoker. This never enables model execution or starts a runtime.
        from .production_execution_api import create_production_invoker
        call = create_production_invoker(invoke, require_host_session=require_host_session, model_host_authority=model_host_authority)
        return call(request, nid, token, branch, permission, callback)

    @router.get("/capabilities")
    def capabilities(nid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
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
                result["document_type_stages"] = {"SCRIPT": "SCREENPLAY"}
                result["source_adaptation"] = "HOST_SESSION_REQUIRED"
                if require_host_session is not None:
                    try:
                        authority = capture_adaptation_host(request, x_session_token)
                        require_host_session(x_session_token)
                        authority.guard()
                        result["source_adaptation"] = "REVIEWED_LOCAL_MODEL"
                    except HTTPException as exc:
                        if exc.status_code not in {401, 403}:
                            raise
            return result
        return api_call(operation)

    @router.get("/screenplay-presets")
    def screenplay_presets(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.screenplay_presets(nid, scope))

    @router.get("/documents")
    def documents(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: {"items": service.list(nid, scope)})

    @router.post("/documents", status_code=201)
    def create(nid: str, body: CreativeProductionDocumentIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
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

    @router.get("/documents/{rid}/director-advice")
    def director_advice(nid: str, rid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.storyboards.director_advice(nid, scope, rid))

    @router.get("/documents/{rid}/storyboard")
    def storyboard(nid: str, rid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return storyboard_call(request, nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.storyboards.get(nid, scope, actor, rid, guard))

    @router.post("/documents/{rid}/storyboard/approve")
    def approve_storyboard(nid: str, rid: str, request: Request, body: StoryboardApproval, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return storyboard_call(request, nid, x_session_token, x_branch_id, "domain.review",
                      lambda actor, scope, guard: service.storyboards.approve(nid, scope, actor, rid, body, guard))

    @router.post("/documents/{rid}/shots/{shot_id}/image-binding")
    def bind_storyboard_image(nid: str, rid: str, shot_id: str, request: Request, body: ShotImageBinding, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return storyboard_call(request, nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.storyboards.bind_image(nid, scope, actor, rid, shot_id, body, guard))

    @router.post("/documents/{rid}/shots/{shot_id}/image-request")
    def storyboard_image_request(nid: str, rid: str, shot_id: str, request: Request, body: ShotImageRequest, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return storyboard_call(request, nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.storyboards.image_request(nid, scope, actor, rid, shot_id, body, guard))

    @router.post("/documents/{rid}/storyboard/timeline-draft", status_code=201)
    def storyboard_timeline(nid: str, rid: str, request: Request, body: StoryboardTimelineDraft, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return storyboard_call(request, nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.storyboards.timeline_draft(nid, scope, actor, rid, body, guard))

    @router.post("/documents/{rid}/shots/{shot_id}/video-request")
    def storyboard_video_request(nid: str, rid: str, shot_id: str, request: Request, body: ShotVideoRequest, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return storyboard_call(request, nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.storyboards.video_request(nid, scope, actor, rid, shot_id, body, guard))

    @router.post("/documents/{rid}/shots/{shot_id}/video-binding")
    def storyboard_video_binding(nid: str, rid: str, shot_id: str, request: Request, body: ShotVideoBinding, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return storyboard_call(request, nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.storyboards.bind_video(nid, scope, actor, rid, shot_id, body, guard))

    @router.post("/documents/{rid}/storyboard/timeline-create", status_code=201)
    def storyboard_timeline_create(nid: str, rid: str, request: Request, body: StoryboardTimelineCreate, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return storyboard_call(request, nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.storyboards.timeline_create(nid, scope, actor, rid, body, guard))

    @router.get("/documents/{rid}/storyboard/timeline-creations/{request_id}")
    def storyboard_timeline_creation(nid: str, rid: str, request_id: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return storyboard_call(request, nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.storyboards.timeline_creation(nid, scope, actor, rid, request_id, guard))

    @router.post("/documents/{rid}/shots/{shot_id}/timelines/{tid}/video-adoption")
    def storyboard_video_adoption(nid: str, rid: str, shot_id: str, tid: str, request: Request, body: StoryboardVideoAdoption, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return storyboard_call(request, nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.storyboards.adopt_video(nid, scope, actor, rid, shot_id, tid, body, guard))

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

    @router.get("/documents/{rid}/screenplay-export")
    def screenplay_export(nid: str, rid: str, format: Literal["fountain", "docx", "markdown", "epub"],
                          expected_version: int = Query(ge=1),
                          x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        result = invoke(nid, x_session_token, x_branch_id, "domain.read",
                        lambda actor, scope, guard: service.export_screenplay(nid, scope, rid,
                            expected_version, format, reauthorize=guard))
        return Response(result["content"], media_type=result["media_type"], headers={
            "Content-Disposition": f'attachment; filename="{result["filename"]}"',
            "X-Creative-Document-Version": str(result["document_version"]),
            "X-Creative-Document-Digest": result["document_digest"],
            "X-Content-SHA256": result["sha256"],
        })

    @router.get("/documents/{rid}/script-export")
    def script_export(nid: str, rid: str, format: Literal["txt", "docx", "markdown"],
                      expected_version: int = Query(ge=1),
                      x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        result = invoke(nid, x_session_token, x_branch_id, "domain.read",
                        lambda actor, scope, guard: service.export_script(nid, scope, rid,
                            expected_version, format, reauthorize=guard))
        return Response(result["content"], media_type=result["media_type"], headers={
            "Content-Disposition": f'attachment; filename="{result["filename"]}"',
            "X-Creative-Document-Version": str(result["document_version"]),
            "X-Creative-Document-Digest": result["document_digest"],
            "X-Content-SHA256": result["sha256"],
        })

    @router.get("/director-proposals")
    def proposals(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: {"items": service.proposals.list(nid, scope, actor)})

    @router.post("/director-proposals", status_code=201)
    def propose(nid: str, body: DirectorProposalIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.proposals.create(nid, scope, actor, body, guard=guard))

    def model_call(nid, token, branch, method, rid=None, body=None, *, adaptation=False, request=None):
        def operation(actor, scope, guard):
            generation = (service.adaptations if adaptation else service.proposals).generation
            if generation is None:
                raise HTTPException(409, {"code": "CREATIVE_MODEL_NOT_CONFIGURED"})
            if require_host_session is None:
                raise HTTPException(409, {"code": "CREATIVE_MODEL_HOST_AUTHORITY_REQUIRED"})
            authority = capture_adaptation_host(request, token) if adaptation else None
            def model_guard():
                guard()
                require_host_session(token)
                if authority is not None:
                    authority.guard()
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

    def invoke_adaptation(request, nid, token, branch, permission, callback):
        def operation(actor, scope, guard):
            if require_host_session is None:
                raise HTTPException(409, {"code": "CREATIVE_MODEL_HOST_AUTHORITY_REQUIRED"})
            authority = capture_adaptation_host(request, token)
            def private_guard():
                guard()
                require_host_session(token)
                authority.guard()
            private_guard()
            try:
                result = callback(actor, scope, private_guard)
            except Exception:
                private_guard()
                raise
            private_guard()
            return result
        return invoke(nid, token, branch, permission, operation)

    @router.get("/adaptation-proposals")
    def adaptations(nid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke_adaptation(request, nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: {"items": service.adaptations.list(nid, scope, actor, guard=guard)})

    @router.post("/adaptation-proposals", status_code=201)
    def create_adaptation(nid: str, request: Request, body: AdaptationIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke_adaptation(request, nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.adaptations.create(nid, scope, actor, body, guard=guard))

    @router.get("/adaptation-proposals/model-routes")
    def adaptation_routes(nid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return model_call(nid, x_session_token, x_branch_id, "catalog", adaptation=True, request=request)

    @router.get("/adaptation-proposals/{rid}")
    def adaptation(nid: str, request: Request, rid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke_adaptation(request, nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.adaptations.get(nid, scope, actor, rid, guard=guard))

    @router.post("/adaptation-proposals/{rid}/preview")
    def preview_adaptation(nid: str, request: Request, rid: str, body: AdaptationPreview, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return model_call(nid, x_session_token, x_branch_id, "preview", rid, body, adaptation=True, request=request)

    @router.post("/adaptation-proposals/{rid}/dispatch")
    def dispatch_adaptation(nid: str, request: Request, rid: str, body: DirectorModelDispatch, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return model_call(nid, x_session_token, x_branch_id, "dispatch", rid, body, adaptation=True, request=request)

    @router.post("/adaptation-proposals/{rid}/refresh")
    def refresh_adaptation(nid: str, request: Request, rid: str, body: ProposalAction, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return model_call(nid, x_session_token, x_branch_id, "refresh", rid, body, adaptation=True, request=request)

    @router.post("/adaptation-proposals/{rid}/review")
    def review_adaptation(nid: str, request: Request, rid: str, body: AdaptationReview, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke_adaptation(request, nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.adaptations.review(nid, scope, actor, rid, body, guard=guard))

    @router.post("/adaptation-proposals/{rid}/cancel")
    def cancel_adaptation(nid: str, request: Request, rid: str, body: ProposalAction, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke_adaptation(request, nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.adaptations.cancel(nid, scope, actor, rid, body, guard=guard))

    return router

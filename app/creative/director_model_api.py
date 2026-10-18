"""Explicit versioned Director actions behind original feature and Host guards.

No background retries, implicit model calls on reads, alternate Job engine or
raw private proposal projection. Original owners authorize and commit actions.
"""
from fastapi import APIRouter, Header, Request, HTTPException
from .director_observation_api import DirectorObservationRoute, create_director_owner_invoker
from .director_lifecycle import AdoptionReceipt, CancelInput, StatusReceipt
from .director_transport_contract import PreviewInput, ScreenplayPreviewInput, DispatchInput, PrepareInput, project_preview, project_pending
from .models import DirectorProposalReview


def create_director_model_router(service, invoke, *, require_host_session, model_host_authority, screenplay=False):
    if type(screenplay) is not bool: raise ValueError("DIRECTOR_MODEL_TRANSPORT_OPTION_INVALID")
    model_path = "model-v2" if screenplay else "model-v1"
    router = APIRouter(route_class=DirectorObservationRoute)
    call = create_director_owner_invoker(service, invoke,
        require_host_session=require_host_session, model_host_authority=model_host_authority)

    def action(request, nid, token, branch, rid, method, body=None):
        def operation(generation, ctx, current, authority):
            generation._require_independent_transport(ctx, rid, screenplay=screenplay)
            # Durable terminal evidence is currently implemented by the File
            # owner only. Reject unsupported backends before preview writes.
            generation._pending_repository()
            if method == 'preview':
                preview_method = generation._preview_independent_screenplay if screenplay else generation._preview_independent_review
                payload = body.model_dump()
                if payload.get("planning_mode") is None:
                    payload.pop("planning_mode", None)
                try:
                    row = preview_method(ctx, rid, payload, current, host_authority=authority)
                except ValueError as exc:
                    if str(exc) == "CREATIVE_MODEL_SHOT_PLAN_REQUIRES_ONE_OR_TWO_SCENES":
                        raise HTTPException(409, {"code": str(exc)}) from None
                    raise
                return project_preview(row, screenplay=screenplay)
            if method == 'read-preview':
                row = generation._read_independent_preview(ctx, rid, current, host_authority=authority)
                return project_preview(row, screenplay=screenplay)
            if method == 'dispatch':
                generation._dispatch_independent(ctx, rid, body.model_dump(), current,
                    host_authority=authority, terminal_evidence=True)
                raw = generation._read_independent_status(ctx, rid, current, host_authority=authority)
                return StatusReceipt.model_validate(raw).model_dump()
            if method == 'prepare-review':
                try:
                    raw = generation._prepare_independent_pending_review(ctx, rid, body.model_dump(), current, host_authority=authority)
                except ValueError as exc:
                    if str(exc) == "CREATIVE_MODEL_SHOT_PLAN_INVALID_OR_INCOMPLETE_JSON":
                        raise HTTPException(409, {"code": str(exc)}) from None
                    raise
                return project_pending(raw, screenplay=screenplay)
            if method == 'pending-review':
                raw = generation._read_independent_pending_review(ctx, rid, current, host_authority=authority)
                return project_pending(raw, screenplay=screenplay)
            if method == 'review':
                generation._review_independent_pending(ctx, rid, body, current, host_authority=authority)
                raw = generation._read_independent_adopted(ctx, rid, current, host_authority=authority)
                return AdoptionReceipt.model_validate(raw).model_dump()
            if method == 'cancel':
                raw = generation._cancel_independent(ctx, rid, body, current, host_authority=authority)
                return StatusReceipt.model_validate(raw).model_dump()
            raise ValueError('DIRECTOR_MODEL_ACTION_INVALID')
        kind = ('preview' if method in {'preview','read-preview'} else
                'pending-review' if method in {'prepare-review','pending-review'} else
                'adopted-draft' if method == 'review' else 'status')
        permission = 'domain.read' if method in {'read-preview','pending-review'} else 'domain.write'
        # A lost post-action response must be reconciled with original reads.
        # The adapter never retries the action or claims that no write occurred.
        return call(request, nid, token, branch, rid, permission, kind, operation,
            error_code='DIRECTOR_MODEL_ACTION_NOT_CONFIRMED')

    preview_input = ScreenplayPreviewInput if screenplay else PreviewInput

    @router.post(f'/director-proposals/{{rid}}/{model_path}/preview')
    def preview(nid: str, rid: str, request: Request, body: preview_input,
                x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return action(request,nid,x_session_token,x_branch_id,rid,'preview',body)

    @router.get(f'/director-proposals/{{rid}}/{model_path}/preview')
    def read_preview(nid: str, rid: str, request: Request,
                     x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return action(request,nid,x_session_token,x_branch_id,rid,'read-preview')

    @router.post(f'/director-proposals/{{rid}}/{model_path}/dispatch')
    def dispatch(nid: str, rid: str, request: Request, body: DispatchInput,
                 x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return action(request,nid,x_session_token,x_branch_id,rid,'dispatch',body)

    @router.post(f'/director-proposals/{{rid}}/{model_path}/prepare-review')
    def prepare(nid: str, rid: str, request: Request, body: PrepareInput,
                x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return action(request,nid,x_session_token,x_branch_id,rid,'prepare-review',body)

    @router.get(f'/director-proposals/{{rid}}/{model_path}/pending-review')
    def pending(nid: str, rid: str, request: Request,
                x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return action(request,nid,x_session_token,x_branch_id,rid,'pending-review')

    @router.post(f'/director-proposals/{{rid}}/{model_path}/review')
    def review(nid: str, rid: str, request: Request, body: DirectorProposalReview,
               x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return action(request,nid,x_session_token,x_branch_id,rid,'review',body)

    @router.post(f'/director-proposals/{{rid}}/{model_path}/cancel')
    def cancel(nid: str, rid: str, request: Request, body: CancelInput,
               x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return action(request,nid,x_session_token,x_branch_id,rid,'cancel',body)
    return router

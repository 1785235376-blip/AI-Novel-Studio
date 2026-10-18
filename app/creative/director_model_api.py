"""Explicit versioned Director actions behind original feature and Host guards.

No background retries, implicit model calls on reads, alternate Job engine or
raw private proposal projection. Original owners authorize and commit actions.
"""
from fastapi import APIRouter, Header, Request
from .director_observation_api import DirectorObservationRoute, create_director_owner_invoker
from .director_lifecycle import AdoptionReceipt, CancelInput, StatusReceipt
from .director_transport_contract import PreviewInput, DispatchInput, PrepareInput, project_preview, project_pending
from .models import DirectorProposalReview


def create_director_model_router(service, invoke, *, require_host_session, model_host_authority):
    router = APIRouter(route_class=DirectorObservationRoute)
    call = create_director_owner_invoker(service, invoke,
        require_host_session=require_host_session, model_host_authority=model_host_authority)

    def action(request, nid, token, branch, rid, method, body=None):
        def operation(generation, ctx, current, authority):
            generation._require_independent_transport_v1(ctx, rid)
            # Durable terminal evidence is currently implemented by the File
            # owner only. Reject unsupported backends before preview writes.
            generation._pending_repository()
            if method == 'preview':
                row = generation._preview_independent_review(ctx, rid, body.model_dump(), current, host_authority=authority)
                return project_preview(row)
            if method == 'read-preview':
                row = generation._read_independent_preview(ctx, rid, current, host_authority=authority)
                return project_preview(row)
            if method == 'dispatch':
                generation._dispatch_independent(ctx, rid, body.model_dump(), current,
                    host_authority=authority, terminal_evidence=True)
                raw = generation._read_independent_status(ctx, rid, current, host_authority=authority)
                return StatusReceipt.model_validate(raw).model_dump()
            if method == 'prepare-review':
                raw = generation._prepare_independent_pending_review(ctx, rid, body.model_dump(), current, host_authority=authority)
                return project_pending(raw)
            if method == 'pending-review':
                raw = generation._read_independent_pending_review(ctx, rid, current, host_authority=authority)
                return project_pending(raw)
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

    @router.post('/director-proposals/{rid}/model-v1/preview')
    def preview(nid: str, rid: str, request: Request, body: PreviewInput,
                x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return action(request,nid,x_session_token,x_branch_id,rid,'preview',body)

    @router.get('/director-proposals/{rid}/model-v1/preview')
    def read_preview(nid: str, rid: str, request: Request,
                     x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return action(request,nid,x_session_token,x_branch_id,rid,'read-preview')

    @router.post('/director-proposals/{rid}/model-v1/dispatch')
    def dispatch(nid: str, rid: str, request: Request, body: DispatchInput,
                 x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return action(request,nid,x_session_token,x_branch_id,rid,'dispatch',body)

    @router.post('/director-proposals/{rid}/model-v1/prepare-review')
    def prepare(nid: str, rid: str, request: Request, body: PrepareInput,
                x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return action(request,nid,x_session_token,x_branch_id,rid,'prepare-review',body)

    @router.get('/director-proposals/{rid}/model-v1/pending-review')
    def pending(nid: str, rid: str, request: Request,
                x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return action(request,nid,x_session_token,x_branch_id,rid,'pending-review')

    @router.post('/director-proposals/{rid}/model-v1/review')
    def review(nid: str, rid: str, request: Request, body: DirectorProposalReview,
               x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return action(request,nid,x_session_token,x_branch_id,rid,'review',body)

    @router.post('/director-proposals/{rid}/model-v1/cancel')
    def cancel(nid: str, rid: str, request: Request, body: CancelInput,
               x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return action(request,nid,x_session_token,x_branch_id,rid,'cancel',body)
    return router

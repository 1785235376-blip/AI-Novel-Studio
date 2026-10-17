"""Versioned Director observation adapter, not mounted by the application.

Only the existing lifecycle owners read state. This adapter cannot preview,
dispatch, publish, review, cancel, or restore an execution capability.
"""
from copy import deepcopy

from anyio import fail_after
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute

from ..experimental.ux import ReadContext
from .director_lifecycle import AdoptionReceipt, StatusReceipt
from .models import DirectorProposalReview


class DirectorObservationRoute(APIRoute):
    MAX_BODY = 1024 * 1024

    def get_route_handler(self):
        handler = super().get_route_handler()

        async def bounded(request):
            headers = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
            try:
                parts, total = [], 0
                with fail_after(15):
                    async for part in request.stream():
                        total += len(part)
                        if total > self.MAX_BODY:
                            raise HTTPException(413, {"code": "DIRECTOR_OBSERVATION_REQUEST_LIMIT"})
                        parts.append(part)
                request._body = b"".join(parts)
                response = await handler(request)
                response.headers.update(headers)
                return response
            except TimeoutError:
                raise HTTPException(408, {"code": "DIRECTOR_OBSERVATION_REQUEST_TIMEOUT"}, headers=headers) from None
            except RequestValidationError:
                # FastAPI's default body error includes private submitted text.
                raise HTTPException(422, {"code": "DIRECTOR_OBSERVATION_REQUEST_INVALID"}, headers=headers) from None
            except HTTPException as exc:
                exc.headers = {**(exc.headers or {}), **headers}
                raise
        return bounded


def create_director_observation_router(service, invoke, *, require_host_session, model_host_authority):
    """The parent Creative router supplies its original scoped invoker.

    The original router can opt in at construction for isolated verification.
    Application callers keep the default disabled; this is not an HTTP option.
    """
    router = APIRouter(route_class=DirectorObservationRoute)

    def observe(request, nid, token, branch, rid, action, body=None):
        def operation(actor, scope, guard):
            if require_host_session is None or model_host_authority is None:
                raise HTTPException(403, {"code": "CREATIVE_MODEL_HOST_REQUIRED"})
            authority = model_host_authority(request, token)
            if not authority.principal:
                raise HTTPException(403, {"code": "CREATIVE_MODEL_HOST_BINDING_REQUIRED"})

            def current():
                guard()
                require_host_session(token)
                authority.guard()

            current()
            generation = service.proposals.generation
            if generation is None:
                raise HTTPException(409, {"code": "CREATIVE_MODEL_NOT_CONFIGURED"})
            ctx = ReadContext(nid, scope, actor, token, branch)
            try:
                if action == "status":
                    raw = generation._read_independent_status(ctx, rid, current, host_authority=authority)
                    result = StatusReceipt.model_validate(raw).model_dump()
                elif action == "adopted":
                    raw = generation._read_independent_adopted(ctx, rid, current, host_authority=authority)
                    result = AdoptionReceipt.model_validate(raw).model_dump()
                else:
                    raw = generation._reconcile_independent_review(ctx, rid, body, current, host_authority=authority)
                    result = AdoptionReceipt.model_validate(raw).model_dump()
                current()
                return {"contract": "DIRECTOR_OBSERVATION_V1", "project_id": nid,
                        "scope": deepcopy(scope), "kind": "status" if action == "status" else "adopted-draft",
                        "receipt": result}
            except HTTPException:
                current()
                raise
            except (ValueError, TypeError, KeyError, FileNotFoundError, PermissionError):
                current()
                # No lower-owner exception text, raw Job, request or prompt.
                raise HTTPException(409, {"code": "DIRECTOR_OBSERVATION_UNAVAILABLE"}) from None

        # Read-only endpoints must not provision a missing incarnation marker.
        with service.store.existing_owner_only():
            return invoke(nid, token, branch, "domain.read", operation)

    @router.get("/director-proposals/{rid}/model-v1/status")
    def status(nid: str, rid: str, request: Request,
               x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return observe(request, nid, x_session_token, x_branch_id, rid, "status")

    @router.get("/director-proposals/{rid}/model-v1/adopted-draft")
    def adopted(nid: str, rid: str, request: Request,
                x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return observe(request, nid, x_session_token, x_branch_id, rid, "adopted")

    @router.post("/director-proposals/{rid}/model-v1/reconcile-review")
    def reconcile(nid: str, rid: str, request: Request, body: DirectorProposalReview,
                  x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return observe(request, nid, x_session_token, x_branch_id, rid, "reconcile", body)

    return router

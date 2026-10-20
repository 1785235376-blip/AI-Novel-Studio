"""Host-private V2 operations; the project UI never supplies download authority."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from .discovery_api import PrivateDiscoveryRoute, PRIVATE_HEADERS
from .discovery_authority import DiscoveryAuthority
from .transfer_types import (CleanupInput, ConfirmationInput, PreviewInput,
    ResumeInput, TransferError, VersionInput)


def create_model_transfer_router(service, *, prefix='/api/model-center/transfers', host_authorization):
    def require_host(request: Request, x_session_token: str | None = Header(default=None, alias='X-Session-Token')):
        from ..experimental.flags import require_flag
        authority = host_authorization(request, x_session_token)
        def current():
            authority.guard()
            require_flag('narrative_production_v2')
        current()
        if not authority.principal:
            raise HTTPException(401, {'code': 'MODEL_TRANSFER_HOST_PRINCIPAL_REQUIRED'}, headers=PRIVATE_HEADERS)
        request.state.local_ai_authority = DiscoveryAuthority(authority.principal, current)

    router = APIRouter(prefix=prefix, tags=['model-center-transfers'], route_class=PrivateDiscoveryRoute,
                       dependencies=[Depends(require_host)])

    def invoke(request, function, *args, principal=False):
        authority = request.state.local_ai_authority
        authority.guard()
        try:
            result = function(*args, **({'principal': authority.principal} if principal else {}), guard=authority.guard)
            authority.guard()
            return result
        except TransferError as exc:
            authority.guard()
            status = 404 if exc.code == 'MODEL_TRANSFER_NOT_FOUND' else 409
            if exc.code in {'MODEL_TRANSFER_LOW_SPACE_OR_QUOTA', 'MODEL_TRANSFER_CAPACITY_UNAVAILABLE'}: status = 507
            raise HTTPException(status, {'code': exc.code}, headers=PRIVATE_HEADERS) from None
        except FileNotFoundError:
            authority.guard()
            raise HTTPException(404, {'code': 'MODEL_TRANSFER_NOT_FOUND'}, headers=PRIVATE_HEADERS) from None
        except OSError:
            authority.guard()
            raise HTTPException(409, {'code': 'MODEL_TRANSFER_IO_FAILED'}, headers=PRIVATE_HEADERS) from None

    @router.get('')
    def snapshot(request: Request):
        return invoke(request, service.snapshot)

    @router.post('/preview')
    def preview(request: Request, body: PreviewInput):
        return invoke(request, service.preview, body.source_id, principal=True)

    @router.post('/start')
    def start(request: Request, body: ConfirmationInput):
        return invoke(request, service.start, body, principal=True)

    @router.post('/{identifier}/pause')
    def pause(request: Request, identifier: str, body: VersionInput):
        return invoke(request, service.control, identifier, 'pause', body.expected_version)

    @router.post('/{identifier}/cancel')
    def cancel(request: Request, identifier: str, body: VersionInput):
        return invoke(request, service.control, identifier, 'cancel', body.expected_version)

    @router.post('/{identifier}/resume')
    def resume(request: Request, identifier: str, body: ResumeInput):
        return invoke(request, service.resume, identifier, body.expected_version)

    @router.post('/{identifier}/cleanup-preview')
    def cleanup_preview(request: Request, identifier: str, body: VersionInput):
        return invoke(request, service.cleanup_preview, identifier, body.expected_version, principal=True)

    @router.post('/{identifier}/cleanup')
    def cleanup(request: Request, identifier: str, body: CleanupInput):
        return invoke(request, service.cleanup, identifier, body, principal=True)

    return router

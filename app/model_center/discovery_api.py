"""Every discovery endpoint is host-session protected, including local path reads."""
from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute

from .discovery_authority import DiscoveryAuthority
from .discovery_onboarding_types import ScanScopeConfirmation, ScanScopePreview

from .discovery_types import AIEnvironmentReport, DiscoverySettingsInput, EnableInput, LocalRuntimeInput, RegistrationInput


PRIVATE_HEADERS = {'Cache-Control': 'no-store', 'Pragma': 'no-cache',
                   'Referrer-Policy': 'no-referrer', 'X-Content-Type-Options': 'nosniff'}


class PrivateDiscoveryRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def private(request):
            def current():
                authority = getattr(request.state, 'local_ai_authority', None)
                if authority:
                    authority.guard()
                gated = getattr(request.state, 'local_ai_feature_guard', None)
                if gated:
                    gated()
            try:
                try:
                    response = await handler(request)
                except Exception:
                    current()
                    raise
                current()
            except RequestValidationError:
                # Validation errors never echo supplied filesystem paths/tokens.
                raise HTTPException(422, {'code': 'LOCAL_AI_INVALID_CONFIGURATION'}, headers=PRIVATE_HEADERS) from None
            except HTTPException as exc:
                exc.headers = {**(exc.headers or {}), **PRIVATE_HEADERS}
                raise
            response.headers.update(PRIVATE_HEADERS)
            return response
        return private


def create_local_discovery_router(service, *, prefix='/api/model-center/local-ai', mutation_authorization=None,
                                  host_authorization=None):
    def require_session(request: Request, x_session_token: str | None = Header(default=None, alias='X-Session-Token')):
        if host_authorization:
            authority = host_authorization(request, x_session_token)
        else:
            # Existing explicitly injected local test/embedding seam. Production
            # always supplies its independent current Host authority resolver.
            def current():
                permission = mutation_authorization(x_session_token) if mutation_authorization else {}
                if not permission.get('can_mutate'):
                    raise HTTPException(401, {'code':'SESSION_REQUIRED'})
            current()
            authority = DiscoveryAuthority('', current)
        authority.guard()
        request.state.local_ai_authority = authority
        return authority
    router = APIRouter(prefix=prefix, tags=['local-ai-discovery'],
                       route_class=PrivateDiscoveryRoute, dependencies=[Depends(require_session)])
    def call(request, function, *args, **kwargs):
        guard = request.state.local_ai_authority.guard
        guard()
        try:
            result = function(*args, **kwargs)
            guard()
            return result
        except KeyError:
            guard()
            raise HTTPException(404, {'code':'LOCAL_AI_NOT_FOUND'}) from None
        except ValueError as exc:
            guard()
            code = str(exc)
            if not re.fullmatch(r'LOCAL_AI_[A-Z0-9_]+', code): code = 'LOCAL_AI_INVALID_CONFIGURATION'
            raise HTTPException(409, {'code':code}) from exc
    def onboarding(request):
        from ..experimental.flags import require_flag
        authority = request.state.local_ai_authority
        def guard():
            authority.guard()
            require_flag('narrative_production_v2')
        guard()
        if not authority.principal:
            raise HTTPException(401, {'code': 'LOCAL_AI_HOST_IDENTITY_REQUIRED'})
        request.state.local_ai_feature_guard = guard
        return authority.principal, guard
    @router.get('')
    def snapshot(request: Request): return call(request, service.snapshot)
    @router.get('/environment', response_model=AIEnvironmentReport)
    def environment(request: Request):
        from ..experimental.flags import require_flag
        require_flag('narrative_production_v2')
        request.state.local_ai_feature_guard = lambda: require_flag('narrative_production_v2')
        return call(request, service.environment_report)
    @router.get('/onboarding/scan-scope', response_model=ScanScopePreview)
    def scan_scope(request: Request, include_common_model_dirs: Literal['true', 'false'] = 'false'):
        principal, guard = onboarding(request)
        return call(request, service.preview_scan_scope, include_common_model_dirs == 'true', principal, guard)
    @router.post('/onboarding/scan', status_code=202)
    def consented_scan(request: Request, body: ScanScopeConfirmation):
        principal, guard = onboarding(request)
        return call(request, service.start_consented_scan, body.scope_digest, principal, guard)
    @router.post('/scan', status_code=202)
    def scan(request: Request):
        if host_authorization:
            return call(request, service.start_legacy_http_scan, request.state.local_ai_authority.guard)
        return call(request, service.start_scan)
    @router.get('/scan/{scan_id}')
    def get_scan(request: Request, scan_id: str): return call(request, service.get_scan, scan_id)
    @router.post('/scan/{scan_id}/cancel')
    def cancel(request: Request, scan_id: str): return call(request, service.cancel_scan, scan_id)
    @router.put('/settings')
    def settings(request: Request, body: DiscoverySettingsInput): return call(request, service.configure_roots, body, guard=request.state.local_ai_authority.guard)
    @router.post('/runtimes')
    def add_runtime(request: Request, body: LocalRuntimeInput): return call(request, service.configure_runtime, body, guard=request.state.local_ai_authority.guard)
    @router.put('/runtimes/{runtime_id}')
    def edit_runtime(request: Request, runtime_id: str, body: LocalRuntimeInput): return call(request, service.configure_runtime, body, runtime_id, guard=request.state.local_ai_authority.guard)
    @router.post('/candidates/{candidate_id}/validate')
    def validate(request: Request, candidate_id: str): return call(request, service.validate, candidate_id, guard=request.state.local_ai_authority.guard)
    @router.post('/candidates/{candidate_id}/register')
    def register(request: Request, candidate_id: str): return call(request, service.register, candidate_id, guard=request.state.local_ai_authority.guard)
    @router.put('/registrations/{registration_id}')
    def configure(request: Request, registration_id: str, body: RegistrationInput): return call(request, service.configure_registration, registration_id, body, guard=request.state.local_ai_authority.guard)
    @router.post('/registrations/{registration_id}/enable')
    def enable(request: Request, registration_id: str, body: EnableInput): return call(request, service.enable, registration_id, guard=request.state.local_ai_authority.guard)
    @router.post('/registrations/{registration_id}/disable')
    def disable(request: Request, registration_id: str): return call(request, service.disable, registration_id, guard=request.state.local_ai_authority.guard)
    @router.delete('/registrations/{registration_id}')
    def remove(request: Request, registration_id: str): return call(request, service.remove, registration_id, guard=request.state.local_ai_authority.guard)
    return router

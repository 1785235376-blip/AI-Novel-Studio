"""Every discovery endpoint is host-session protected, including local path reads."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException

from .discovery_types import DiscoverySettingsInput, EnableInput, LocalRuntimeInput, RegistrationInput


def create_local_discovery_router(service, *, prefix='/api/model-center/local-ai', mutation_authorization=None):
    def require_session(x_session_token: str | None = Header(default=None, alias='X-Session-Token')):
        permission = mutation_authorization(x_session_token) if mutation_authorization else {}
        if not permission.get('can_mutate'):
            raise HTTPException(401, {'code':'SESSION_REQUIRED'})
    router = APIRouter(prefix=prefix, tags=['local-ai-discovery'], dependencies=[Depends(require_session)])
    def call(function, *args):
        try: return function(*args)
        except KeyError: raise HTTPException(404, {'code':'LOCAL_AI_NOT_FOUND'}) from None
        except ValueError as exc:
            code = str(exc)
            if not code.startswith('LOCAL_AI_'): code = 'LOCAL_AI_INVALID_CONFIGURATION'
            raise HTTPException(409, {'code':code}) from exc
    @router.get('')
    def snapshot(): return service.snapshot()
    @router.post('/scan', status_code=202)
    def scan(): return call(service.start_scan)
    @router.get('/scan/{scan_id}')
    def get_scan(scan_id: str): return call(service.get_scan, scan_id)
    @router.post('/scan/{scan_id}/cancel')
    def cancel(scan_id: str): return call(service.cancel_scan, scan_id)
    @router.put('/settings')
    def settings(body: DiscoverySettingsInput): return call(service.configure_roots, body)
    @router.post('/runtimes')
    def add_runtime(body: LocalRuntimeInput): return call(service.configure_runtime, body)
    @router.put('/runtimes/{runtime_id}')
    def edit_runtime(runtime_id: str, body: LocalRuntimeInput): return call(service.configure_runtime, body, runtime_id)
    @router.post('/candidates/{candidate_id}/validate')
    def validate(candidate_id: str): return call(service.validate, candidate_id)
    @router.post('/candidates/{candidate_id}/register')
    def register(candidate_id: str): return call(service.register, candidate_id)
    @router.put('/registrations/{registration_id}')
    def configure(registration_id: str, body: RegistrationInput): return call(service.configure_registration, registration_id, body)
    @router.post('/registrations/{registration_id}/enable')
    def enable(registration_id: str, body: EnableInput): return call(service.enable, registration_id)
    @router.post('/registrations/{registration_id}/disable')
    def disable(registration_id: str): return call(service.disable, registration_id)
    @router.delete('/registrations/{registration_id}')
    def remove(registration_id: str): return call(service.remove, registration_id)
    return router

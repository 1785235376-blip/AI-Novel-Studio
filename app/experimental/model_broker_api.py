"""Trusted-host/project authorized broker; generation reuses author JobManager."""
from __future__ import annotations
from starlette.concurrency import run_in_threadpool
from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import Field, ValidationError
from .common import api_call, check_version
from .model_broker import FEATURE, Strict, BrokerRequest, BudgetInput, PriceInput, ReconcileInput, digest
from .author_context_api import AuthorPreviewInput


class ReservationVersionInput(Strict):
    expected_version: int = Field(ge=1)


class BrokerGenerateInput(Strict):
    preview_id: str = Field(min_length=1, max_length=160)
    expected_version: int = Field(ge=1)
    request_id: str = Field(min_length=1, max_length=160)
    author: AuthorPreviewInput


def cancellation_version_matches(entry, expected):
    """Cancel is monotonic: the same owned reservation may just have dispatched.

    This never rewrites ledger data or accepts a generic stale financial edit.
    Only the original RESERVED -> DISPATCHED transition is admissible.
    """
    if expected == entry.get('version'):
        return True
    if entry.get('status') != 'DISPATCHED' or entry.get('version') != expected + 1:
        return False
    immutable = ('id', 'job_id', 'created_by', 'novel_id', 'scope', 'authorization_digest',
        'preview_id', 'route_id', 'route_fingerprint', 'provider_id', 'model_id',
        'price', 'currency', 'reserve_microusd')
    return any(row.get('version') == expected and row.get('status') == 'RESERVED'
        and all(row.get(key) == entry.get(key) for key in immutable)
        for row in entry.get('history', []) if isinstance(row, dict))


def create_model_broker_router(service, authorize, require_flag, require_host_session, *, prepare_author=None, manager=None):
    router = APIRouter(prefix='/novels/{nid}/experimental/model-broker', tags=['Experimental Model Broker'])

    def access(nid, token, branch, permission='domain.read'):
        require_flag(FEATURE)
        require_host_session(token)
        return authorize(nid, token, branch, permission)

    def recovery_access(nid, token, branch, permission='domain.read'):
        # Disabling generation must not prevent stopping an owned job or
        # conservatively reconciling its existing cost hold. No content read.
        require_host_session(token)
        return authorize(nid, token, branch, permission)

    def recovery_guard(nid, token, branch, authority):
        def verify():
            if recovery_access(nid, token, branch, 'domain.write') != authority:
                raise ValueError('BROKER_AUTHORITY_CHANGED')
        return verify

    def content_enabled():
        try: require_flag(FEATURE)
        except HTTPException as exc:
            if exc.status_code == 404: return False
            raise
        return True

    def recovery_ledger(entry):
        return {key: entry.get(key) for key in ('id', 'job_id', 'version', 'status', 'dispatched',
            'currency', 'cost_state', 'accounted_microusd', 'actual_microusd')}

    def public_job(current):
        if current is None: return None
        from ..jobs import generation_content_available
        if content_enabled() and generation_content_available(current): return current.public()
        return {'id': current.id, 'status': current.public()['status'], 'content_available': False}

    def guard(nid, token, branch, authority, permission='domain.write'):
        def verify():
            if access(nid, token, branch, permission) != authority:
                raise ValueError('BROKER_AUTHORITY_CHANGED')
        return verify

    async def body(request, model):
        data = bytearray()
        async for part in request.stream():
            data.extend(part)
            if len(data) > 2 * 1024 * 1024: raise HTTPException(413, {'code': 'BROKER_REQUEST_TOO_LARGE'})
        try: return model.model_validate_json(data)
        except (ValidationError, ValueError): raise HTTPException(422, {'code': 'BROKER_INPUT_INVALID'}) from None

    def execution_state(entry):
        try: current = manager.get(entry['job_id']) if manager else None
        except KeyError: current = None
        pending = entry['status'] in {'RESERVED', 'DISPATCHED'}
        terminal = current is not None and current.status in {'COMPLETED', 'FAILED', 'CANCELLED', 'ACCEPTED', 'REJECTED', 'ACCEPTANCE_UNCERTAIN'}
        missing = current is None or (terminal and (not callable(getattr(current, 'on_terminal', None))
            or str(getattr(current, 'terminal_hook_status', '')).endswith('RECONCILIATION_REQUIRED')))
        orphan = bool(manager is not None and pending and missing)
        recovery = 'EXECUTOR_OR_SETTLEMENT_NOT_RESUMABLE_NO_AUTOMATIC_REPLAY' if orphan else 'EXECUTOR_NOT_RESUMABLE_NO_AUTOMATIC_REPLAY' if current is None else None
        return current, recovery, orphan

    @router.get('/status')
    def status(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id)
        response.headers['Cache-Control'] = 'no-store'
        return {'candidates': api_call(service.candidates), 'budget': api_call(service.budget, nid, scope),
                'prices': api_call(service.list, nid, scope, service.PRICES),
                'author_execution_available': callable(prepare_author) and manager is not None,
                'provider_profile_state': 'USES_EXISTING_HOST_VAULT_AND_RUNTIME_REGISTRATIONS',
                'supports': ['TEXT_AUTHOR_EXECUTOR'], 'unsupported_capabilities': ['IMAGE', 'VIDEO', 'AUDIO', 'EMBEDDING'],
                'source_privacy': 'CURRENT_CHAPTER_AND_PROJECT_AUTHORITY', 'auto_fallback': False}

    @router.post('/preview')
    async def preview(nid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        authority = access(nid, x_session_token, x_branch_id, 'domain.write')
        value = await body(request, BrokerRequest)
        response.headers['Cache-Control'] = 'no-store'
        return await run_in_threadpool(api_call, service.preview, nid, authority[1], authority[0], value, guard(nid, x_session_token, x_branch_id, authority))

    @router.put('/budget')
    async def budget(nid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        authority = access(nid, x_session_token, x_branch_id, 'domain.write')
        value = await body(request, BudgetInput)
        return api_call(service.configure_budget, nid, authority[1], authority[0], value, guard(nid, x_session_token, x_branch_id, authority))

    @router.put('/price')
    async def price(nid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        authority = access(nid, x_session_token, x_branch_id, 'domain.write')
        value = await body(request, PriceInput)
        return await run_in_threadpool(api_call, service.configure_price, nid, authority[1], authority[0], value, guard(nid, x_session_token, x_branch_id, authority))

    @router.get('/history')
    def history(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id)
        response.headers['Cache-Control'] = 'no-store'
        return {'decisions': api_call(service.decisions, nid, scope, actor), 'ledger': api_call(service.ledger, nid, scope, actor)}

    @router.post('/generate', status_code=202)
    async def generate(nid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        authority = access(nid, x_session_token, x_branch_id, 'domain.write')
        actor, scope = authority
        value = await body(request, BrokerGenerateInput)
        if not callable(prepare_author) or manager is None: raise HTTPException(409, {'code': 'BROKER_AUTHOR_COORDINATOR_UNAVAILABLE'})
        row = api_call(service.get, nid, scope, service.DECISIONS, value.preview_id)
        api_call(check_version, row, value.expected_version)
        await run_in_threadpool(api_call, service._assert_preview, nid, scope, actor, row)
        chosen = row['chosen']
        if (row['request']['chapter_ids'] != [value.author.chapter_id] or value.author.novel_id != nid
            or row['request']['profile'] != value.author.profile
            or (chosen['provider_id'], chosen['model_id']) != (value.author.provider_id, value.author.model_id)):
            raise HTTPException(409, {'code': 'BROKER_AUTHOR_ROUTE_OR_SOURCE_MISMATCH'})
        if not value.author.preview_digest: raise HTTPException(409, {'code': 'AUTHOR_PREVIEW_REQUIRED'})
        # Shared coordinator validates the exact prompt/context receipt and makes
        # the existing job's late author authorization guard. No second builder.
        job = await run_in_threadpool(prepare_author, nid, value.author, x_session_token, x_branch_id)
        guard_now = guard(nid, x_session_token, x_branch_id, authority)
        guard_now()
        receipt = digest(value.author.model_dump(mode='json'))
        key = digest([actor, value.request_id])
        existing = service.store.read(nid, scope)['collections'].get(service.LEDGER, {}).get(key)
        if existing:
            if existing['preview_id'] != value.preview_id or existing.get('authorization_digest') != receipt:
                raise HTTPException(409, {'code': 'BROKER_IDEMPOTENCY_MISMATCH'})
            return {'job_id': existing['job_id'], 'reservation_id': existing['id'], 'status': existing['status'], 'replayed': True}
        reservation = await run_in_threadpool(api_call, service.reserve, nid, scope, actor, value.preview_id, value.expected_version,
            value.request_id, job.id, guard_now, receipt)
        if reservation['job_id'] != job.id:
            return {'job_id': reservation['job_id'], 'reservation_id': reservation['id'], 'status': reservation['status'], 'replayed': True}
        from ..jobs import mark_generation_origin
        mark_generation_origin(job, 'model_broker')
        job.before_dispatch = lambda: service.guard_dispatch(nid, scope, actor, reservation['id'], job.id, guard_now)
        job.on_terminal = lambda: service.finalize(nid, scope, actor, reservation['id'], job.id, getattr(job, 'execution_outcome', None) or 'UNKNOWN', job.usage)
        try:
            manager.start_prepared(job)
        except Exception:
            service.finalize(nid, scope, actor, reservation['id'], job.id, 'FAILED')
            raise
        response.headers['Cache-Control'] = 'no-store'
        return {'job_id': job.id, 'reservation_id': reservation['id'], 'status': job.public()['status'] if callable(getattr(job, 'public', None)) else job.status,
                'events_url': f'/api/generation/{job.id}/events', 'replayed': False}

    @router.post('/ledger/{reservation_id}/reconcile')
    async def reconcile(nid: str, reservation_id: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        authority = recovery_access(nid, x_session_token, x_branch_id, 'domain.write')
        value = await body(request, ReconcileInput)
        entry = api_call(service.get, nid, authority[1], service.LEDGER, reservation_id)
        current, _, orphan = execution_state(entry)
        result = api_call(service.reconcile, nid, authority[1], authority[0], reservation_id, value, recovery_guard(nid, x_session_token, x_branch_id, authority), orphan)
        from ..jobs import generation_content_available
        visible = content_enabled() and (current is None or generation_content_available(current))
        return result if visible else recovery_ledger(result)

    @router.get('/jobs/{reservation_id}')
    def job(nid: str, reservation_id: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = recovery_access(nid, x_session_token, x_branch_id)
        entry = api_call(service.get, nid, scope, service.LEDGER, reservation_id)
        if entry['created_by'] != actor: raise HTTPException(404, {'code': 'BROKER_JOB_NOT_FOUND'})
        response.headers['Cache-Control'] = 'no-store'
        current, recovery, orphan = execution_state(entry)
        from ..jobs import generation_content_available
        visible = content_enabled() and (current is None or generation_content_available(current))
        return {'ledger': entry if visible else recovery_ledger(entry), 'job': public_job(current),
                'recovery': recovery if visible else 'FEATURE_DISABLED_CONTENT_HIDDEN', 'orphan_reconciliation_available': orphan}

    @router.post('/jobs/{reservation_id}/cancel')
    async def cancel(nid: str, reservation_id: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = recovery_access(nid, x_session_token, x_branch_id, 'domain.write')
        value = await body(request, ReservationVersionInput)
        entry = api_call(service.get, nid, scope, service.LEDGER, reservation_id)
        if entry['created_by'] != actor: raise HTTPException(404, {'code': 'BROKER_JOB_NOT_FOUND'})
        if not cancellation_version_matches(entry, value.expected_version):
            # Do not return historical source-bound ledger contents in errors,
            # including the feature-OFF recovery path.
            raise HTTPException(409, {'code': 'BROKER_CANCELLATION_STATE_CHANGED'})
        recovery_access(nid, x_session_token, x_branch_id, 'domain.write')
        try: current = manager.cancel(entry['job_id']) if manager else None
        except KeyError: raise HTTPException(409, {'code': 'BROKER_EXECUTOR_NOT_RESUMABLE'}) from None
        if current is None: raise HTTPException(409, {'code': 'BROKER_EXECUTOR_NOT_RESUMABLE'})
        entry = service.get(nid, scope, service.LEDGER, reservation_id)
        from ..jobs import generation_content_available
        visible = content_enabled() and generation_content_available(current)
        return {'ledger': entry if visible else recovery_ledger(entry), 'job': public_job(current),
                'recovery': None if visible else 'FEATURE_DISABLED_CONTENT_HIDDEN'}

    return router

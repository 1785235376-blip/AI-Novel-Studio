"""Explicit benchmark steps only; installing or reading never runs a benchmark."""
import copy
from starlette.concurrency import run_in_threadpool
from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import Field, ValidationError
from ..services.v1_capability_service import CapabilityVersionConflict
from .common import api_call
from .model_broker import Strict
from .model_benchmark import FEATURE, TASK_KINDS, BenchmarkSetInput, BenchmarkRunInput, EvidenceImportInput, EvidenceReviewInput
from .production_lineage_api import PrivateProductionRoute


class ComparisonInput(Strict):
    left_id: str = Field(min_length=1, max_length=160)
    right_id: str = Field(min_length=1, max_length=160)


class VoteInput(Strict):
    expected_version: int = Field(ge=1)
    choice: str = Field(pattern=r'^(A|B|TIE|NEITHER)$')


class VersionInput(Strict):
    expected_version: int = Field(ge=1)


class VideoExecuteInput(VersionInput):
    reviewed_preview_digest: str = Field(pattern=r'^[0-9a-f]{64}$')


class UpdateSetInput(BenchmarkSetInput):
    expected_version: int = Field(ge=1)


def create_model_benchmark_router(service, authorize, require_flag, require_host_session, *, model_host_authority=None):
    router = APIRouter(prefix='/novels/{nid}/experimental/model-benchmarks', tags=['Experimental model benchmarks'], route_class=PrivateProductionRoute)
    def public_video_run(row):
        if not isinstance(row, dict) or row.get('capability') != 'VIDEO': return row
        result = copy.deepcopy(row)
        # The browser gets the reviewed preview and original job projection,
        # never the server admission binding or its nested historical copies.
        for key in ('history', 'video_samples', 'studio_incarnation'): result.pop(key, None)
        if isinstance(result.get('video_sample'), dict): result['video_sample'].pop('binding', None)
        return result
    def access(nid, token, branch, permission='domain.read'):
        require_flag(FEATURE)
        require_host_session(token)
        return authorize(nid, token, branch, permission)
    def guard(nid, token, branch, authority, permission='domain.write'):
        def verify():
            if access(nid, token, branch, permission) != authority: raise ValueError('BENCHMARK_AUTHORITY_CHANGED')
        return verify
    def video_guard(request, nid, token, branch, authority, *, execution=True, permission='domain.write'):
        if model_host_authority is None: raise HTTPException(403, {'code': 'CREATIVE_MODEL_HOST_REQUIRED'})
        host = model_host_authority(request, token)
        if not host.principal: raise HTTPException(403, {'code': 'CREATIVE_MODEL_HOST_BINDING_REQUIRED'})
        base = guard(nid, token, branch, authority, permission)
        if service.video is None: raise HTTPException(404, {'code': 'BENCHMARK_VIDEO_OWNER_UNAVAILABLE'})
        owner = service.video.production.store
        def identity():
            # This guard is also called inside original Asset phases. Read
            # only the existing owner identity, never a scope snapshot or a
            # lazily provisioned marker; retain Asset -> project lock order.
            try:
                with owner.existing_owner_only():
                    return owner.incarnation(nid)
            except (FileNotFoundError, ValueError):
                raise HTTPException(403, {'code': 'BENCHMARK_VIDEO_OWNER_CHANGED'}) from None
        base(); host.guard()
        incarnation = identity()
        def current():
            base(); host.guard()
            if identity() != incarnation:
                raise HTTPException(403, {'code': 'BENCHMARK_VIDEO_OWNER_CHANGED'})
            for flag in (('narrative_production_v2', 'ai_execution_v2', 'model_broker_v2') if execution else ('narrative_production_v2',)): require_flag(flag)
        current()
        return current
    def video_call(current, fn, *args):
        # Match the original Production invoker: lower owner CAS rows may
        # contain private context, URLs and executor tokens. Never echo them.
        def checked():
            current()
            try:
                result = fn(*args)
            except CapabilityVersionConflict as exc:
                current()
                version = exc.current.get('version') if isinstance(exc.current, dict) else None
                raise HTTPException(409, {'code': 'BENCHMARK_VIDEO_VERSION_CONFLICT',
                    'current_version': version if type(version) is int and 1 <= version <= 2**53 - 1 else None}) from None
            except Exception:
                current()
                raise
            current()
            return public_video_run(result)
        return api_call(checked)
    async def read(request, model):
        raw = bytearray()
        async for part in request.stream():
            raw.extend(part)
            if len(raw) > 128 * 1024: raise HTTPException(413, {'code': 'BENCHMARK_INPUT_TOO_LARGE'})
        try: return model.model_validate_json(raw)
        except (ValidationError, ValueError): raise HTTPException(422, {'code': 'BENCHMARK_INPUT_INVALID'}) from None

    @router.get('/status')
    def status(nid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id)
        runs = api_call(service.runs, nid, scope, actor)
        current = None
        if any(r.get('capability') == 'VIDEO' for r in runs):
            current = video_guard(request, nid, x_session_token, x_branch_id, (actor, scope), execution=False, permission='domain.read')
            # The first projection only selected the stronger guard. Read the
            # returned rows after its incarnation capture, then fence the full
            # response below; an old projection cannot cross owner recreation.
            runs = api_call(service.runs, nid, scope, actor)
        response.headers['Cache-Control'] = 'no-store'
        result = {'sets': api_call(service.sets, nid, scope), 'runs': [public_video_run(row) for row in runs],
                'evidence': api_call(service.evidence, nid, scope), 'comparisons': api_call(service.comparisons, nid, scope, actor), 'task_kinds': TASK_KINDS,
                'execution': 'ONE_EXPLICIT_LOCAL_STEP', 'max_samples': 6, 'startup_runs': False,
                'image_execution': 'ONE_REGISTERED_LOCAL_IMAGE_THROUGH_ORIGINAL_MEDIA_REVIEW',
                'video_execution': 'ONE_REGISTERED_LOCAL_T2V_THROUGH_ORIGINAL_STUDIO_REVIEW' if service.video is not None else 'IMPORT_ONLY_LOCAL_ADMISSION_UNAVAILABLE'}
        if current is not None: current()
        return result

    @router.get('/profiles')
    def profiles(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        authority = access(nid, x_session_token, x_branch_id)
        result = api_call(service.capability_profiles, nid, authority[1])
        if access(nid, x_session_token, x_branch_id) != authority: raise HTTPException(403, {'code': 'BENCHMARK_AUTHORITY_CHANGED'})
        response.headers['Cache-Control'] = 'no-store'
        return result

    @router.post('/sets', status_code=201)
    async def create(nid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        authority = access(nid, x_session_token, x_branch_id, 'domain.write')
        value = await read(request, BenchmarkSetInput)
        guard(nid, x_session_token, x_branch_id, authority)()
        return api_call(service.create_set, nid, authority[1], authority[0], value)

    @router.put('/sets/{rid}')
    async def update(nid: str, rid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        authority = access(nid, x_session_token, x_branch_id, 'domain.write')
        value = await read(request, UpdateSetInput)
        guard(nid, x_session_token, x_branch_id, authority)()
        return api_call(service.update_set, nid, authority[1], authority[0], rid, value.expected_version, value.model_dump(exclude={'expected_version'}))

    @router.post('/runs', status_code=201)
    async def start(nid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        authority = access(nid, x_session_token, x_branch_id, 'domain.write')
        value = await read(request, BenchmarkRunInput)
        current = guard(nid, x_session_token, x_branch_id, authority)
        test_set = api_call(service.get, nid, authority[1], service.SETS, value.set_id)
        if any(c['kind'] == 'VIDEO_WORKFLOW' for c in test_set['cases']) and service.video is not None:
            current = video_guard(request, nid, x_session_token, x_branch_id, authority)
            return await run_in_threadpool(video_call, current, service.start, nid, authority[1], authority[0], value, current)
        return await run_in_threadpool(api_call, service.start, nid, authority[1], authority[0], value, current)

    @router.post('/runs/{rid}/{action}')
    async def run_action(nid: str, rid: str, action: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        authority = access(nid, x_session_token, x_branch_id, 'domain.write')
        value = await read(request, VideoExecuteInput if action == 'execute' else VersionInput)
        current_guard = guard(nid, x_session_token, x_branch_id, authority)
        current_guard()
        row = api_call(service.get, nid, authority[1], service.RUNS, rid)
        if row.get('capability') == 'VIDEO':
            if service.video is None: raise HTTPException(422, {'code': 'BENCHMARK_VIDEO_OWNER_UNAVAILABLE'})
            current_guard = video_guard(request, nid, x_session_token, x_branch_id, authority, execution=action != 'cancel')
            if action == 'execute':
                return await run_in_threadpool(video_call, current_guard, service.video.execute, nid, authority[1], authority[0], rid,
                    value.expected_version, value.reviewed_preview_digest, current_guard)
            if action in {'preview', 'refresh', 'reconcile'}:
                return await run_in_threadpool(video_call, current_guard, getattr(service.video, action), nid, authority[1], authority[0], rid,
                    value.expected_version, current_guard)
            if action in {'step', 'cancel'}:
                return await run_in_threadpool(video_call, current_guard, getattr(service, action), nid, authority[1], authority[0], rid,
                    value.expected_version, current_guard)
        if action == 'step': return await run_in_threadpool(api_call, service.step, nid, authority[1], authority[0], rid, value.expected_version, current_guard)
        if action == 'cancel': return await run_in_threadpool(api_call, service.cancel, nid, authority[1], authority[0], rid, value.expected_version, current_guard)
        raise HTTPException(404, {'code': 'BENCHMARK_ACTION_NOT_FOUND'})

    @router.post('/evidence/import', status_code=201)
    async def import_evidence(nid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        authority = access(nid, x_session_token, x_branch_id, 'domain.write')
        value = await read(request, EvidenceImportInput)
        guard(nid, x_session_token, x_branch_id, authority)()
        return await run_in_threadpool(api_call, service.import_evidence, nid, authority[1], authority[0], value)

    @router.post('/evidence/{rid}/review')
    async def review_evidence(nid: str, rid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        authority = access(nid, x_session_token, x_branch_id, 'domain.write')
        value = await read(request, EvidenceReviewInput)
        current = guard(nid, x_session_token, x_branch_id, authority)
        evidence = api_call(service.get, nid, authority[1], service.EVIDENCE, rid)
        if evidence.get('capability') == 'VIDEO':
            current = video_guard(request, nid, x_session_token, x_branch_id, authority)
            return await run_in_threadpool(video_call, current, service.review_evidence, nid, authority[1], authority[0], rid, value, current)
        return await run_in_threadpool(api_call, service.review_evidence, nid, authority[1], authority[0], rid, value, current)

    @router.get('/runs/{rid}/video/{index}/candidate')
    def video_candidate(nid: str, rid: str, index: int, request: Request,
                        x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        authority = access(nid, x_session_token, x_branch_id)
        current = video_guard(request, nid, x_session_token, x_branch_id, authority, execution=False, permission='domain.read')
        if service.video is None: raise HTTPException(404, {'code': 'BENCHMARK_VIDEO_OWNER_UNAVAILABLE'})
        meta, data = video_call(current, service.video.candidate, nid, authority[1], authority[0], rid, index, current)
        return Response(data, media_type=meta['media_type'], headers={'Cache-Control': 'no-store',
            'X-Content-Type-Options': 'nosniff', 'X-Asset-SHA256': meta['sha256'], 'X-Asset-Version': str(meta['version'])})

    @router.post('/evidence/{rid}/invalidate')
    async def invalidate(nid: str, rid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        authority = access(nid, x_session_token, x_branch_id, 'domain.write')
        value = await read(request, VersionInput)
        guard(nid, x_session_token, x_branch_id, authority)()
        return api_call(service.invalidate, nid, authority[1], authority[0], rid, value.expected_version)
    @router.post('/comparisons', status_code=201)
    async def compare(nid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        authority = access(nid, x_session_token, x_branch_id, 'domain.write')
        value = await read(request, ComparisonInput)
        guard(nid, x_session_token, x_branch_id, authority)()
        return await run_in_threadpool(api_call, service.compare_blind, nid, authority[1], authority[0], value.left_id, value.right_id)

    @router.post('/comparisons/{rid}/vote')
    async def vote(nid: str, rid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        authority = access(nid, x_session_token, x_branch_id, 'domain.write')
        value = await read(request, VoteInput)
        guard(nid, x_session_token, x_branch_id, authority)()
        return await run_in_threadpool(api_call, service.vote_blind, nid, authority[1], authority[0], rid, value.expected_version, value.choice)
    return router

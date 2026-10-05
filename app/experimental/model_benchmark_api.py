"""Explicit benchmark steps only; installing or reading never runs a benchmark."""
from starlette.concurrency import run_in_threadpool
from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import Field, ValidationError
from .common import api_call
from .model_broker import Strict
from .model_benchmark import FEATURE, TASK_KINDS, BenchmarkSetInput, BenchmarkRunInput, EvidenceImportInput


class ComparisonInput(Strict):
    left_id: str = Field(min_length=1, max_length=160)
    right_id: str = Field(min_length=1, max_length=160)


class VoteInput(Strict):
    expected_version: int = Field(ge=1)
    choice: str = Field(pattern=r'^(A|B|TIE|NEITHER)$')


class VersionInput(Strict):
    expected_version: int = Field(ge=1)


class UpdateSetInput(BenchmarkSetInput):
    expected_version: int = Field(ge=1)


def create_model_benchmark_router(service, authorize, require_flag, require_host_session):
    router = APIRouter(prefix='/novels/{nid}/experimental/model-benchmarks', tags=['Experimental model benchmarks'])
    def access(nid, token, branch, permission='domain.read'):
        require_flag(FEATURE)
        require_host_session(token)
        return authorize(nid, token, branch, permission)
    def guard(nid, token, branch, authority):
        def verify():
            if access(nid, token, branch, 'domain.write') != authority: raise ValueError('BENCHMARK_AUTHORITY_CHANGED')
        return verify
    async def read(request, model):
        raw = bytearray()
        async for part in request.stream():
            raw.extend(part)
            if len(raw) > 128 * 1024: raise HTTPException(413, {'code': 'BENCHMARK_INPUT_TOO_LARGE'})
        try: return model.model_validate_json(raw)
        except (ValidationError, ValueError): raise HTTPException(422, {'code': 'BENCHMARK_INPUT_INVALID'}) from None

    @router.get('/status')
    def status(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id)
        response.headers['Cache-Control'] = 'no-store'
        return {'sets': api_call(service.sets, nid, scope), 'runs': api_call(service.runs, nid, scope, actor),
                'evidence': api_call(service.evidence, nid, scope), 'comparisons': api_call(service.comparisons, nid, scope, actor), 'task_kinds': TASK_KINDS,
                'execution': 'ONE_EXPLICIT_LOCAL_STEP', 'max_samples': 6, 'startup_runs': False,
                'image_execution': 'ONE_REGISTERED_LOCAL_IMAGE_THROUGH_ORIGINAL_MEDIA_REVIEW',
                'video_execution': 'IMPORT_ONLY_LOCAL_ADMISSION_UNAVAILABLE'}

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
        return await run_in_threadpool(api_call, service.start, nid, authority[1], authority[0], value, guard(nid, x_session_token, x_branch_id, authority))

    @router.post('/runs/{rid}/{action}')
    async def run_action(nid: str, rid: str, action: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        authority = access(nid, x_session_token, x_branch_id, 'domain.write')
        value = await read(request, VersionInput)
        current_guard = guard(nid, x_session_token, x_branch_id, authority)
        current_guard()
        if action == 'step': return await run_in_threadpool(api_call, service.step, nid, authority[1], authority[0], rid, value.expected_version, current_guard)
        if action == 'cancel': return api_call(service.cancel, nid, authority[1], authority[0], rid, value.expected_version)
        raise HTTPException(404, {'code': 'BENCHMARK_ACTION_NOT_FOUND'})

    @router.post('/evidence/import', status_code=201)
    async def import_evidence(nid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        authority = access(nid, x_session_token, x_branch_id, 'domain.write')
        value = await read(request, EvidenceImportInput)
        guard(nid, x_session_token, x_branch_id, authority)()
        return await run_in_threadpool(api_call, service.import_evidence, nid, authority[1], authority[0], value)

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

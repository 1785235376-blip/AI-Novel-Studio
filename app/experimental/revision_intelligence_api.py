"""Revision routes recheck authoritative actor/branch/flags before every write."""
from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import ValidationError

from .common import api_call
from .revision_intelligence import FEATURE, SelectionIn, ProposalIn, ReviewIn, LockIn, MilestoneIn, RebaseIn, UnlockBlockIn
from ..repositories.chapter_repository import VersionConflict
from ..revision_constraints import RevisionConstraintError


def create_revision_intelligence_router(service, authorize, require_flag, *, save_document=None, read_job=None):
    router = APIRouter(prefix='/novels/{nid}/experimental/revisions', tags=['experimental-revision-intelligence'])

    def access(nid, token, branch, response, permission='domain.write'):
        require_flag(FEATURE)
        authority = authorize(nid, token, branch, permission)
        response.headers['Cache-Control'] = 'no-store'
        def again():
            require_flag(FEATURE)
            if authorize(nid, token, branch, permission) != authority:
                raise HTTPException(409, {'code': 'REVISION_AUTHORITY_CHANGED'})
        return (*authority, again)

    def call(fn, *args, **kwargs):
        try: return api_call(fn, *args, **kwargs)
        except VersionConflict: raise HTTPException(409, {'code': 'REVISION_CHAPTER_CHANGED'}) from None
        except RevisionConstraintError as exc: raise HTTPException(409, {'code': exc.code, 'message': str(exc)}) from None

    async def body(request, model):
        require_flag(FEATURE)
        raw = bytearray()
        async for part in request.stream():
            raw.extend(part)
            if len(raw) > 2 * 1024 * 1024: raise HTTPException(413, {'code': 'REVISION_INPUT_TOO_LARGE'})
        try: return model.model_validate_json(bytes(raw))
        except (ValidationError, ValueError): raise HTTPException(422, {'code': 'REVISION_INPUT_INVALID'}) from None

    def writer(token, branch):
        if save_document is None: return None
        return lambda cid, doc, version, source: save_document(cid, doc, version, source, token, branch)

    def reader(token, branch):
        if read_job is None: return None
        return lambda jid: read_job(jid, token, branch)

    @router.get('/catalog')
    def catalog(nid: str, response: Response, chapter_id: str | None = None, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope, again = access(nid, x_session_token, x_branch_id, response)
        result = call(service.catalog, nid, scope, chapter_id); again(); return result

    @router.get('/proposals')
    def proposals(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope, again = access(nid, x_session_token, x_branch_id, response)
        result = call(service.proposals, nid, scope, job_reader=reader(x_session_token, x_branch_id)); again(); return result

    @router.get('/proposals/{rid}')
    def proposal(nid: str, rid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope, again = access(nid, x_session_token, x_branch_id, response)
        result = call(service.proposal, nid, scope, rid, job_reader=reader(x_session_token, x_branch_id)); again(); return result

    @router.post('/selection')
    async def selection(nid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        value = await body(request, SelectionIn)
        _, scope, again = access(nid, x_session_token, x_branch_id, response)
        result = call(service.selection, nid, scope, value); again(); return result

    @router.post('/proposals', status_code=201)
    async def create(nid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        value = await body(request, ProposalIn)
        actor, scope, again = access(nid, x_session_token, x_branch_id, response)
        return call(service.create_proposal, nid, scope, actor, value, reauthorize=again, job_reader=reader(x_session_token, x_branch_id))

    @router.post('/proposals/{rid}/preview')
    async def preview(nid: str, rid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        value = await body(request, ReviewIn)
        _, scope, again = access(nid, x_session_token, x_branch_id, response, 'domain.review')
        return call(service.preview, nid, scope, rid, value, reauthorize=again, job_reader=reader(x_session_token, x_branch_id))

    @router.post('/proposals/{rid}/apply')
    async def apply(nid: str, rid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        value = await body(request, ReviewIn)
        actor, scope, again = access(nid, x_session_token, x_branch_id, response, 'domain.review')
        return call(service.apply, nid, scope, actor, rid, value, reauthorize=again, save_document=writer(x_session_token, x_branch_id), job_reader=reader(x_session_token, x_branch_id))

    @router.post('/proposals/{rid}/rebase', status_code=201)
    async def rebase(nid: str, rid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        value = await body(request, RebaseIn)
        actor, scope, again = access(nid, x_session_token, x_branch_id, response, 'domain.review')
        return call(service.rebase, nid, scope, actor, rid, value, reauthorize=again, job_reader=reader(x_session_token, x_branch_id))

    @router.post('/locks')
    async def locks(nid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        value = await body(request, LockIn)
        actor, scope, again = access(nid, x_session_token, x_branch_id, response)
        return call(service.locks, nid, scope, actor, value, reauthorize=again, save_document=writer(x_session_token, x_branch_id))

    @router.post('/locks/unlock')
    async def unlock_block(nid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        value = await body(request, UnlockBlockIn)
        actor, scope, again = access(nid, x_session_token, x_branch_id, response)
        return call(service.unlock_block, nid, scope, actor, value, reauthorize=again, save_document=writer(x_session_token, x_branch_id))

    @router.get('/milestones')
    def milestones(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope, again = access(nid, x_session_token, x_branch_id, response)
        result = {'items': call(service.list, nid, scope, service.MILESTONES)}; again(); return result

    @router.post('/milestones', status_code=201)
    async def milestone(nid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        value = await body(request, MilestoneIn)
        actor, scope, again = access(nid, x_session_token, x_branch_id, response)
        return call(service.milestone, nid, scope, actor, value, reauthorize=again)

    return router

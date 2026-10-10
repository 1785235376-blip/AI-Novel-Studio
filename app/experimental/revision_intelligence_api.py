"""Revision routes recheck authoritative actor/branch/flags before every write."""
from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import ValidationError

from .common import api_call
from .revision_intelligence import FEATURE, SelectionIn, ProposalIn, ReviewIn, LockIn, MilestoneIn, RebaseIn, UnlockBlockIn
from .revision_intelligence import VersionCompareIn, VersionComparisonSaveIn, VersionComparisonEditIn, VersionComparisonReviewIn
from ..repositories.chapter_repository import VersionConflict
from ..revision_constraints import RevisionConstraintError


def create_revision_intelligence_router(service, authorize, require_flag, *, save_document=None, read_job=None, preparer=None, manager=None, broker=None, require_host_session=None):
    from .revision_intelligence_model import RevisionComparisonModelCoordinator
    from .narrative_judge_model import JudgeModelActionIn, JudgeModelPreviewIn, JudgeModelDispatchIn
    from .ux import ReadContext
    if preparer is not None and manager is not None and broker is not None:
        service.model_coordinator = RevisionComparisonModelCoordinator(service, preparer, manager, broker)
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

    @router.get('/original-versions')
    def versions(nid: str, chapter_id: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope, again = access(nid, x_session_token, x_branch_id, response)
        result = call(service.version_catalog, nid, scope, chapter_id); again(); return result

    @router.post('/comparisons/preview')
    async def compare(nid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        value = await body(request, VersionCompareIn)
        _, scope, again = access(nid, x_session_token, x_branch_id, response)
        return call(service.compare_versions, nid, scope, value, reauthorize=again)

    @router.get('/comparisons')
    def comparisons(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope, again = access(nid, x_session_token, x_branch_id, response)
        result = call(service.comparisons, nid, scope); again(); return result

    @router.post('/comparisons', status_code=201)
    async def save_comparison(nid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        value = await body(request, VersionComparisonSaveIn)
        actor, scope, again = access(nid, x_session_token, x_branch_id, response)
        return call(service.save_comparison, nid, scope, actor, value, reauthorize=again)

    @router.get('/comparisons/{rid}')
    def comparison(nid: str, rid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope, again = access(nid, x_session_token, x_branch_id, response)
        result = call(service.comparison, nid, scope, rid); again(); return result

    @router.put('/comparisons/{rid}')
    async def edit_comparison(nid: str, rid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        value = await body(request, VersionComparisonEditIn)
        actor, scope, again = access(nid, x_session_token, x_branch_id, response)
        return call(service.edit_comparison, nid, scope, actor, rid, value, reauthorize=again)

    @router.post('/comparisons/{rid}/review')
    async def review_comparison(nid: str, rid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        value = await body(request, VersionComparisonReviewIn)
        actor, scope, again = access(nid, x_session_token, x_branch_id, response, 'domain.review')
        return call(service.review_comparison, nid, scope, actor, rid, value, reauthorize=again)

    def model_access(nid, token, branch, response, review=False):
        actor, scope, again = access(nid, token, branch, response, 'domain.review' if review else 'domain.write')
        if service.model_coordinator is None or not callable(require_host_session):
            raise HTTPException(409, {'code': 'REVISION_REGISTERED_MODEL_EXECUTOR_UNAVAILABLE'})
        def current():
            again(); require_flag('model_broker_v2'); require_flag('author_context_inspector_v2'); require_host_session(token)
            if authorize(nid, token, branch, 'domain.write') != (actor, scope):
                raise HTTPException(403, {'code': 'REVISION_MODEL_AUTHOR_REQUIRED'})
        current()
        return ReadContext(nid, scope, actor, token, branch), current

    @router.get('/comparisons-model/catalog')
    def model_catalog(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, current = model_access(nid, x_session_token, x_branch_id, response)
        return call(service.model_coordinator.catalog, ctx, current)

    @router.post('/comparisons/{rid}/model/preview')
    def model_preview(nid: str, rid: str, body: JudgeModelPreviewIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, current = model_access(nid, x_session_token, x_branch_id, response)
        result = call(service.model_coordinator.preview, ctx, rid, body, current); current(); return result

    @router.post('/comparisons/{rid}/model/dispatch')
    def model_dispatch(nid: str, rid: str, body: JudgeModelDispatchIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, current = model_access(nid, x_session_token, x_branch_id, response)
        result = call(service.model_coordinator.dispatch, ctx, rid, body, current); current(); return result

    @router.post('/comparisons/{rid}/model/refresh')
    def model_refresh(nid: str, rid: str, body: JudgeModelActionIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, current = model_access(nid, x_session_token, x_branch_id, response)
        result = call(service.model_coordinator.refresh, ctx, rid, body, current); current(); return result

    @router.post('/comparisons/{rid}/model/cancel')
    def model_cancel(nid: str, rid: str, body: JudgeModelActionIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, current = model_access(nid, x_session_token, x_branch_id, response)
        result = call(service.model_coordinator.cancel, ctx, rid, body, current); current(); return result

    @router.post('/comparisons/{rid}/model/opinions/{oid}/{action}')
    def model_review(nid: str, rid: str, oid: str, action: str, body: JudgeModelActionIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, current = model_access(nid, x_session_token, x_branch_id, response, True)
        result = call(service.review_model_opinion, ctx, rid, oid, body.expected_version, action, current); current(); return result

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

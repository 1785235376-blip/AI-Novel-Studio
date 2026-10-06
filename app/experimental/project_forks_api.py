"""B09 bounded request inputs and original authority at every write boundary."""
from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from ..repositories.chapter_repository import VersionConflict
from ..revision_constraints import RevisionConstraintError
from .common import api_call as domain_call
from .project_forks import FEATURE, ForkIn, ConfirmIn, CompareIn, ApplyIn, VersionIn
from .ux import ReadContext


def call(fn, *args, **kwargs):
    try: return domain_call(fn, *args, **kwargs)
    except VersionConflict: raise HTTPException(409, {'code': 'FORK_CHAPTER_VERSION_CONFLICT'}) from None
    except RevisionConstraintError: raise HTTPException(409, {'code': 'FORK_REVISION_LOCKED'}) from None
    except HTTPException as exc:
        if exc.status_code == 409:
            raise HTTPException(409, {'code': 'FORK_STALE_OR_CONFLICT', 'message': 'Refresh the authorized comparison or inspect recovery; no automatic retry.'}) from None
        raise


def create_project_forks_router(service, authorize, require_flag, require_host_session, *, save_document=None, rename_chapter=None, archive_chapter=None, restore_archive=None):
    router = APIRouter(prefix='/novels/{nid}/experimental/project-forks', tags=['project-forks'])

    def access(nid, token, branch, write=False):
        permission = 'domain.review' if write else 'domain.read'
        require_flag(FEATURE); require_host_session(token)
        actor, scope = authorize(nid, token, branch, permission)
        def again():
            require_flag(FEATURE); require_host_session(token)
            if authorize(nid, token, branch, permission) != (actor, scope): raise HTTPException(409, {'code': 'FORK_AUTHORITY_CHANGED'})
        def target(target_id):
            again()
            current_actor, target_scope = authorize(target_id, token, None, permission)
            if current_actor != actor or target_scope != {'mode': 'local', 'novel_id': target_id}:
                raise HTTPException(409, {'code': 'FORK_TARGET_AUTHORITY_CHANGED'})
        return ReadContext(nid, scope, actor, token, branch), again, target

    async def body(request, model):
        data = bytearray()
        async for part in request.stream():
            data.extend(part)
            if len(data) > 128 * 1024: raise HTTPException(413, {'code': 'FORK_INPUT_LIMIT'})
        try: return model.model_validate_json(bytes(data))
        except (ValueError, ValidationError): raise HTTPException(422, {'code': 'FORK_INPUT_INVALID'}) from None

    def writers(token, branch):
        return {'save_document': (lambda cid, doc, version, source: save_document(cid, doc, version, source, token, branch)) if save_document else None,
                'archive_chapter': (lambda cid, version: archive_chapter(cid, version, token, branch)) if archive_chapter else None,
                'restore_archive': (lambda cid, version: restore_archive(cid, version, token, branch)) if restore_archive else None}

    @router.get('/catalog')
    def catalog(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again, _ = access(nid, x_session_token, x_branch_id); response.headers['Cache-Control'] = 'no-store'
        result = call(service.catalog, ctx); again(); return result

    @router.get('/records')
    def records(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again, target = access(nid, x_session_token, x_branch_id); response.headers['Cache-Control'] = 'no-store'
        result = call(service.records, ctx, target); again(); return result

    @router.post('/preflight')
    async def preflight(nid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again, _ = access(nid, x_session_token, x_branch_id, True); value = await body(request, ForkIn); response.headers['Cache-Control'] = 'no-store'
        return await run_in_threadpool(call, service.preflight, ctx, value, again)

    @router.post('/{rid}/create')
    async def create(nid: str, rid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again, target = access(nid, x_session_token, x_branch_id, True); value = await body(request, ConfirmIn); response.headers['Cache-Control'] = 'no-store'
        return await run_in_threadpool(call, service.create_fork, ctx, rid, value, again, target)

    @router.post('/{rid}/compare')
    async def compare(nid: str, rid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again, target = access(nid, x_session_token, x_branch_id); value = await body(request, CompareIn); response.headers['Cache-Control'] = 'no-store'
        return await run_in_threadpool(call, service.compare, ctx, rid, value, again, target)

    @router.post('/{rid}/apply')
    async def apply(nid: str, rid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again, target = access(nid, x_session_token, x_branch_id, True); value = await body(request, ApplyIn); response.headers['Cache-Control'] = 'no-store'
        return await run_in_threadpool(call, service.apply, ctx, rid, value, again, target, **writers(x_session_token, x_branch_id))

    @router.post('/merges/{mid}/recovery')
    async def recovery(nid: str, mid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again, target = access(nid, x_session_token, x_branch_id); value = await body(request, VersionIn); response.headers['Cache-Control'] = 'no-store'
        return await run_in_threadpool(call, service.recovery, ctx, mid, value, again, target)

    @router.post('/merges/{mid}/restore')
    async def restore(nid: str, mid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again, target = access(nid, x_session_token, x_branch_id, True); value = await body(request, ConfirmIn); response.headers['Cache-Control'] = 'no-store'
        return await run_in_threadpool(call, service.restore_checkpoint, ctx, mid, value, again, target, **writers(x_session_token, x_branch_id))
    # Selected original structured records share B09 authorization and feature
    # gates; they do not create a separate manuscript or identity authority.
    from .structured_forks import StructuredForksService, StructuredForkIn
    def structured():
        return StructuredForksService(service.store, service.novels, service.chapters, sources=service.sources, assets=service.assets)

    @router.get('/structured/catalog')
    def structured_catalog(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again, _ = access(nid, x_session_token, x_branch_id); response.headers['Cache-Control'] = 'no-store'
        result = call(structured().catalog, ctx); again(); return result

    @router.get('/structured/records')
    def structured_records(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again, target = access(nid, x_session_token, x_branch_id); response.headers['Cache-Control'] = 'no-store'
        result = call(structured().records, ctx, target); again(); return result

    @router.post('/structured/preflight')
    async def structured_preflight(nid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again, target = access(nid, x_session_token, x_branch_id, True); value = await body(request, StructuredForkIn); response.headers['Cache-Control'] = 'no-store'
        return await run_in_threadpool(call, structured().preflight, ctx, value, again, target)

    @router.post('/structured/{rid}/create')
    async def structured_create(nid: str, rid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again, target = access(nid, x_session_token, x_branch_id, True); value = await body(request, ConfirmIn); response.headers['Cache-Control'] = 'no-store'
        return await run_in_threadpool(call, structured().create_fork, ctx, rid, value, again, target)

    @router.post('/structured/{rid}/compare')
    async def structured_compare(nid: str, rid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again, target = access(nid, x_session_token, x_branch_id); value = await body(request, CompareIn); response.headers['Cache-Control'] = 'no-store'
        return await run_in_threadpool(call, structured().compare, ctx, rid, value, again, target)

    @router.post('/structured/{rid}/apply')
    async def structured_apply(nid: str, rid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again, target = access(nid, x_session_token, x_branch_id, True); value = await body(request, ApplyIn); response.headers['Cache-Control'] = 'no-store'
        return await run_in_threadpool(call, structured().apply, ctx, rid, value, again, target)

    @router.post('/structured/merges/{mid}/recovery')
    async def structured_recovery(nid: str, mid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again, target = access(nid, x_session_token, x_branch_id); value = await body(request, VersionIn); response.headers['Cache-Control'] = 'no-store'
        return await run_in_threadpool(call, structured().recovery, ctx, mid, value, again, target)

    @router.post('/structured/merges/{mid}/restore')
    async def structured_restore(nid: str, mid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again, target = access(nid, x_session_token, x_branch_id, True); value = await body(request, ConfirmIn); response.headers['Cache-Control'] = 'no-store'
        return await run_in_threadpool(call, structured().restore_checkpoint, ctx, mid, value, again, target)
    return router

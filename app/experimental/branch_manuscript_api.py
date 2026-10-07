"""Write / Collaboration branch surface with repeated original authority checks."""
from __future__ import annotations
from copy import deepcopy
import re
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import Field, ValidationError
from starlette.concurrency import run_in_threadpool

from ..repositories.chapter_repository import VersionConflict
from ..revision_constraints import RevisionConstraintError
from ..services.branch_manuscript_service import FEATURE, FORKS, MERGES
from .common import api_call
from .planning import StrictModel
from .ux import ReadContext


class CreateIn(StrictModel):
    title: str = Field(min_length=1, max_length=300)
    document: dict | None = None
    content: str = Field(default='', max_length=500000)


class SaveIn(StrictModel):
    document: dict
    expected_version: int = Field(ge=1)
    operation_id: str = Field(min_length=1, max_length=200)


class VersionIn(StrictModel):
    expected_version: int = Field(ge=1)


class RestoreIn(VersionIn):
    version: int = Field(ge=1)


class ForkIn(StrictModel):
    source_branch_id: str | None = Field(default=None, min_length=1, max_length=240)
    chapter_ids: list[str] = Field(min_length=1, max_length=40)


class ConfirmIn(VersionIn):
    preview_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    confirmed: Literal[True]


class CompareIn(StrictModel):
    chapter_id: str = Field(min_length=1, max_length=240)
    target_branch_id: str | None = Field(default=None, min_length=1, max_length=240)
    target_chapter_id: str = Field(min_length=1, max_length=240)
    choices: dict[str, Literal['ORIGINAL', 'FORK']] = Field(default_factory=dict, max_length=1000)


class MergePrepareIn(CompareIn):
    preview_digest: str = Field(pattern=r'^[a-f0-9]{64}$')


class MoveIn(StrictModel):
    direction: Literal['up', 'down']
    expected_revision: int = Field(ge=0)


def call(fn, *args, **kwargs):
    try: return api_call(fn, *args, **kwargs)
    except VersionConflict as exc:
        raise HTTPException(409, {'code': 'BRANCH_VERSION_CONFLICT', 'conflict': exc.as_dict()}) from None
    except RevisionConstraintError:
        raise HTTPException(409, {'code': 'BRANCH_REVISION_LOCKED'}) from None
    except PermissionError:
        raise HTTPException(403, {'code': 'BRANCH_FORBIDDEN'}) from None
    except HTTPException as exc:
        if exc.status_code == 422 and isinstance(exc.detail, dict):
            code = str(exc.detail.get('message', ''))
            if re.fullmatch(r'BRANCH_[A-Z_]+', code):
                raise HTTPException(422, {'code': code}) from None
        raise


def create_branch_manuscript_router(service, authorize, require_flag, require_host_session,
                                     *, authorize_mainline=None, save_mainline=None):
    router = APIRouter(prefix='/novels/{nid}/experimental/branch-manuscript', tags=['branch-manuscript'])

    def access(nid, token, branch, permission='domain.read'):
        require_flag(FEATURE); require_host_session(token)
        authorize(nid, token, branch, 'domain.read')
        actor, scope = authorize(nid, token, branch, permission)
        if scope.get('mode') != 'collaboration' or scope.get('branch_id') != branch:
            raise HTTPException(400, {'code': 'BRANCH_SCOPE_REQUIRED'})
        def again():
            require_flag(FEATURE); require_host_session(token)
            authorize(nid, token, branch, 'domain.read')
            if authorize(nid, token, branch, permission) != (actor, scope):
                raise HTTPException(403, {'code': 'BRANCH_AUTHORITY_CHANGED'})
        return ReadContext(nid, scope, actor, token, branch), again

    def other(ctx, branch, permission='domain.read'):
        if branch is None:
            if authorize_mainline is None:
                raise HTTPException(501, {'code': 'BRANCH_MAINLINE_ACCESS_NOT_CONFIGURED'})
            authorize_mainline(ctx.novel_id, ctx.token, 'domain.read')
            authorize_mainline(ctx.novel_id, ctx.token, permission)
            scope = {'mode': 'local', 'novel_id': ctx.novel_id}
            def again():
                authorize_mainline(ctx.novel_id, ctx.token, 'domain.read')
                authorize_mainline(ctx.novel_id, ctx.token, permission)
            return scope, again
        authorize(ctx.novel_id, ctx.token, branch, 'domain.read')
        actor, scope = authorize(ctx.novel_id, ctx.token, branch, permission)
        if actor != ctx.actor or scope.get('mode') != 'collaboration' or scope.get('branch_id') != branch:
            raise HTTPException(403, {'code': 'BRANCH_SOURCE_AUTHORITY_CHANGED'})
        def again():
            authorize(ctx.novel_id, ctx.token, branch, 'domain.read')
            if authorize(ctx.novel_id, ctx.token, branch, permission) != (actor, scope):
                raise HTTPException(403, {'code': 'BRANCH_SOURCE_AUTHORITY_CHANGED'})
        return scope, again

    def combine(*checks):
        def check():
            for fn in checks: fn()
        return check

    async def body(request, model):
        data = bytearray()
        async for part in request.stream():
            data.extend(part)
            if len(data) > 2_050_000: raise HTTPException(413, {'code': 'BRANCH_INPUT_LIMIT'})
        try: return model.model_validate_json(bytes(data))
        except (ValidationError, ValueError, RecursionError):
            raise HTTPException(422, {'code': 'BRANCH_INPUT_INVALID'}) from None

    @router.get('/catalog')
    def catalog(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again = access(nid, x_session_token, x_branch_id); response.headers['Cache-Control'] = 'no-store'
        result = call(service.manifest, ctx)
        for field, permission in [('can_write', 'domain.write'), ('can_review', 'domain.review')]:
            try: authorize(nid, x_session_token, x_branch_id, permission); result[field] = True
            except HTTPException as exc:
                if exc.status_code not in {401, 403, 404}: raise
                result[field] = False
        again(); return result

    @router.get('/chapters')
    def chapters(nid: str, response: Response, archived: bool = False, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again = access(nid, x_session_token, x_branch_id); response.headers['Cache-Control'] = 'no-store'
        repo = service.repository(ctx.scope)
        result = call(repo.list_archived if archived else repo.list, nid); again(); return {'items': result}

    @router.post('/chapters', status_code=201)
    async def create(nid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again = access(nid, x_session_token, x_branch_id, 'domain.write'); value = await body(request, CreateIn)
        return await run_in_threadpool(call, service.create, ctx, value.model_dump(exclude_none=True), again)

    @router.get('/chapters/{cid}')
    def chapter(nid: str, cid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again = access(nid, x_session_token, x_branch_id); response.headers['Cache-Control'] = 'no-store'
        result = call(service.read, ctx, cid); again(); return result

    @router.put('/chapters/{cid}')
    async def save(nid: str, cid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again = access(nid, x_session_token, x_branch_id, 'domain.write'); value = await body(request, SaveIn)
        return await run_in_threadpool(call, service.commit, ctx, cid, value.expected_version, value.document, value.operation_id, again)

    @router.get('/chapters/{cid}/history')
    def history(nid: str, cid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again = access(nid, x_session_token, x_branch_id); response.headers['Cache-Control'] = 'no-store'
        result = call(service.repository(ctx.scope).history, cid); again(); return {'items': result}

    @router.post('/chapters/{cid}/restore')
    async def restore(nid: str, cid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again = access(nid, x_session_token, x_branch_id, 'domain.write'); value = await body(request, RestoreIn)
        return await run_in_threadpool(call, service.restore, ctx, cid, value.version, value.expected_version, again)

    @router.post('/chapters/{cid}/archive/{action}')
    async def archive(nid: str, cid: str, action: Literal['archive', 'restore'], request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again = access(nid, x_session_token, x_branch_id, 'domain.write'); value = await body(request, VersionIn)
        return await run_in_threadpool(call, service.archive, ctx, cid, action == 'archive', value.expected_version, again)

    @router.post('/chapters/{cid}/delete')
    async def delete(nid: str, cid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again = access(nid, x_session_token, x_branch_id, 'domain.write'); value = await body(request, VersionIn)
        return await run_in_threadpool(call, service.delete, ctx, cid, value.expected_version, again)

    @router.post('/chapters/{cid}/move')
    async def move(nid: str, cid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again = access(nid, x_session_token, x_branch_id, 'domain.write'); value = await body(request, MoveIn)
        return await run_in_threadpool(call, service.repository(ctx.scope).move, cid, value.direction, value.expected_revision, check=again)

    @router.get('/records')
    def records(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again = access(nid, x_session_token, x_branch_id); response.headers['Cache-Control'] = 'no-store'
        result = call(service.records, ctx)
        for kind in ('forks', 'merges'):
            visible = []
            for row in result[kind]:
                scope = row['source_scope' if kind == 'forks' else 'target_scope']
                try: _, check = other(ctx, scope.get('branch_id')); check()
                except HTTPException as exc:
                    if exc.status_code in {401, 403, 404}: continue
                    raise
                visible.append(row)
            result[kind] = visible
        again(); return result

    @router.get('/sources')
    def sources(nid: str, response: Response, source_branch_id: str | None = None, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again = access(nid, x_session_token, x_branch_id); response.headers['Cache-Control'] = 'no-store'
        source_scope, source_check = other(ctx, source_branch_id)
        rows = call(service.for_scope(source_scope).list, nid)
        again(); source_check()
        return {'scope': source_scope, 'items': [{'id': row['id'], 'title': row['title'], 'version': row['version']}
                                               for row in rows if not row.get('is_archived')]}

    @router.post('/forks/preview')
    async def fork_preview(nid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again = access(nid, x_session_token, x_branch_id, 'domain.write'); value = await body(request, ForkIn)
        source, source_check = other(ctx, value.source_branch_id)
        return await run_in_threadpool(call, service.preview_fork, ctx, source, value.chapter_ids, combine(again, source_check))

    @router.post('/forks/{rid}/apply')
    async def fork_apply(nid: str, rid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again = access(nid, x_session_token, x_branch_id, 'domain.write'); value = await body(request, ConfirmIn)
        row = call(service._row, ctx, FORKS, rid); _, source_check = other(ctx, row['source_scope'].get('branch_id'))
        return await run_in_threadpool(call, service.apply_fork, ctx, rid, value.expected_version, value.preview_digest, value.confirmed, combine(again, source_check))

    @router.post('/compare')
    async def compare(nid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again = access(nid, x_session_token, x_branch_id); value = await body(request, CompareIn)
        target, target_check = other(ctx, value.target_branch_id)
        return await run_in_threadpool(call, service.compare, ctx, value.chapter_id, target, value.target_chapter_id, value.choices, combine(again, target_check))

    @router.post('/merges', status_code=201)
    async def propose(nid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again = access(nid, x_session_token, x_branch_id, 'domain.review'); value = await body(request, MergePrepareIn)
        target, target_check = other(ctx, value.target_branch_id)
        return await run_in_threadpool(call, service.propose_merge, ctx, value.chapter_id, target, value.target_chapter_id, value.choices, combine(again, target_check), expected_digest=value.preview_digest)

    def merge_checks(ctx, row, again, write):
        _, target_check = other(ctx, row['target_scope'].get('branch_id'), 'domain.write' if write else 'domain.read')
        _, target_review = other(ctx, row['target_scope'].get('branch_id'), 'domain.review')
        return combine(again, target_check, target_review)

    @router.get('/merges/{rid}/review')
    def merge_review(nid: str, rid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again = access(nid, x_session_token, x_branch_id, 'domain.review'); response.headers['Cache-Control'] = 'no-store'
        row = call(service._row, ctx, MERGES, rid); check = merge_checks(ctx, row, again, False)
        check()
        current = call(service.compare, ctx, row['chapter_id'], row['target_scope'], row['target_chapter_id'], row['choices'], check)
        check()
        return {'id': row['id'], 'version': row['version'], 'status': row['status'],
                'preview_digest': row['preview_digest'], 'stale': current['preview_digest'] != row['preview_digest'],
                'source': row['source'], 'target': row['target'], 'checkpoint': deepcopy(row['checkpoint']),
                'desired_document': deepcopy(row['desired_document']), 'segments': deepcopy(row['segments'])}

    @router.post('/merges/{rid}/apply')
    async def merge_apply(nid: str, rid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again = access(nid, x_session_token, x_branch_id, 'domain.review'); value = await body(request, ConfirmIn)
        row = call(service._row, ctx, MERGES, rid); check = merge_checks(ctx, row, again, True)
        writer = (lambda cid, document, version, source: save_mainline(nid, cid, document, version, source, ctx.token)) if save_mainline else None
        return await run_in_threadpool(call, service.apply_merge, ctx, rid, value.expected_version, value.preview_digest, value.confirmed, check, mainline_writer=writer)

    @router.post('/merges/{rid}/recovery')
    async def recovery(nid: str, rid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again = access(nid, x_session_token, x_branch_id, 'domain.review'); value = await body(request, VersionIn)
        row = call(service._row, ctx, MERGES, rid); check = merge_checks(ctx, row, again, False)
        return await run_in_threadpool(call, service.recover_merge, ctx, rid, value.expected_version, check)

    @router.post('/{kind}/{rid}/cancel')
    async def cancel(nid: str, kind: Literal['fork', 'merge'], rid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again = access(nid, x_session_token, x_branch_id, 'domain.review'); value = await body(request, VersionIn)
        return await run_in_threadpool(call, service.cancel, ctx, kind, rid, value.expected_version, again)

    return router

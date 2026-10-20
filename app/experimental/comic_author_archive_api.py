"""Bounded private author archive transport under existing Comic authority."""
import base64
import binascii
import hashlib
import re
from contextlib import nullcontext
from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from .comic_layouts_api import ComicPrivateRoute
from .comic_author_archive import (MAX_ARCHIVE, ExportPreviewIn, ExportIn, ArchiveIn, RestoreIn,
    export_preview, export_archive, inspect_archive, restore_archive)
from .production_lineage_api import api_call
from ..creative.storage_admission import StudioStorageCapacityError

HEADERS = {'Cache-Control':'no-store', 'X-Content-Type-Options':'nosniff'}
MAX_BODY = 4 * ((MAX_ARCHIVE + 2) // 3) + 4096

class AuthorArchiveRoute(ComicPrivateRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def private(request):
            try: return await handler(request)
            except Exception:
                return JSONResponse({'detail':{'code':'COMIC_AUTHOR_ARCHIVE_REQUEST_FAILED'}}, status_code=500, headers=HEADERS)
        return private


def create_comic_author_archive_router(service, authorize, require_flag, *, authority_lease):
    router = APIRouter(prefix='/novels/{nid}/experimental/comic-layouts',
                       tags=['Experimental comic layouts'], route_class=AuthorArchiveRoute)
    def access(nid, request):
        for flag in ('comic_layouts_v2','asset_lineage_v2','ai_director_v2'):
            require_flag(flag)
        actor, scope = authorize(nid,request.headers.get('x-session-token'),request.headers.get('x-branch-id'),'domain.write')
        service.store.key(nid,scope)
        return actor,scope,service._independent_identity(nid)

    async def process(nid, request, model, callback, *, archive=False, commit=False):
        captured = api_call(access,nid,request)
        data = bytearray(); total = 0
        async for chunk in request.stream():
            total += len(chunk)
            if total > (MAX_BODY if archive else 4096):
                raise HTTPException(413,{'code':'COMIC_AUTHOR_ARCHIVE_BODY_LIMIT'})
            data.extend(chunk)
        def operation():
            actor,scope,_ = captured
            def guard():
                if access(nid,request) != captured:
                    raise HTTPException(403,{'code':'COMIC_AUTHOR_ARCHIVE_AUTHORITY_CHANGED'})
            lease = authority_lease(nid,request.headers.get('x-session-token'),actor,scope) if commit else nullcontext()
            with lease:
                guard()
                try:
                    # Base64 body is bounded before parse. Reject duplicate envelope
                    # keys as well as unknown fields; author JSON uses tighter bounds.
                    import json
                    def pairs(items):
                        result = {}
                        for key,value in items:
                            if key in result: raise ValueError('duplicate envelope key')
                            result[key] = value
                        return result
                    body = model.model_validate(json.loads(data,object_pairs_hook=pairs),strict=True)
                except (ValidationError,ValueError,RecursionError,UnicodeError):
                    raise HTTPException(422,{'code':'COMIC_AUTHOR_ARCHIVE_INPUT_INVALID'}) from None
                raw = None
                if archive:
                    try: raw = base64.b64decode(body.archive_base64,validate=True)
                    except (binascii.Error,ValueError):
                        raise HTTPException(422,{'code':'COMIC_AUTHOR_ARCHIVE_BASE64_INVALID'}) from None
                    if not 22 <= len(raw) <= MAX_ARCHIVE:
                        raise HTTPException(413,{'code':'COMIC_AUTHOR_ARCHIVE_SIZE_LIMIT'})
                    if hashlib.sha256(raw).hexdigest() != body.archive_sha256:
                        raise HTTPException(422,{'code':'COMIC_AUTHOR_ARCHIVE_HASH_MISMATCH'})
                try:
                    result = callback(actor,scope,guard,body,raw)
                except StudioStorageCapacityError as exc:
                    guard(); raise HTTPException(507,{'code':str(exc)}) from None
                except ValueError as exc:
                    guard()
                    if not re.fullmatch(r'[A-Z0-9_]{1,100}',str(exc)):
                        raise ValueError('COMIC_AUTHOR_ARCHIVE_INVALID_OR_UNSUPPORTED') from None
                    raise
                except Exception:
                    guard(); raise
                guard(); return result
        return await run_in_threadpool(lambda: api_call(operation))

    @router.post('/books/{rid}/author-archive-preview')
    async def preview(nid:str,rid:str,request:Request):
        return await process(nid,request,ExportPreviewIn,
            lambda a,s,g,b,r: export_preview(service,nid,s,a,rid,b,g))

    @router.post('/books/{rid}/export-author-archive')
    async def export(nid:str,rid:str,request:Request):
        def output(a,s,g,b,r):
            raw = export_archive(service,nid,s,a,rid,b,g)
            return Response(raw,media_type='application/zip',headers={**HEADERS,
                'Content-Disposition':'attachment; filename="comic-private-author.zip"',
                'X-Content-SHA256':hashlib.sha256(raw).hexdigest(),
                'X-Comic-Author-Export-Digest':b.export_digest})
        return await process(nid,request,ExportIn,output)

    @router.post('/author-archive/inspect')
    async def inspect(nid:str,request:Request):
        return await process(nid,request,ArchiveIn,
            lambda a,s,g,b,r: inspect_archive(service,nid,s,a,r,g),archive=True)

    @router.post('/author-archive/restore')
    async def restore(nid:str,request:Request):
        return await process(nid,request,RestoreIn,
            lambda a,s,g,b,r: restore_archive(service,nid,s,a,r,b,g),archive=True,commit=True)
    return router

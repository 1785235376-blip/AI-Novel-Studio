"""Current-authority B06 APIs; raster bytes only, no executable exports."""
from fastapi import APIRouter, Header, HTTPException, Response, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import Field
from .comic_layouts import LayoutIn, LayoutEdit
from .comic_collections import ComicBookIn, ComicBookEdit, ComicBookPageIn
from .media import StrictModel
from .comic_publication import EPUBPublicationIn, EPUBPublicationExportIn, epub_publication_preflight, export_epub, PageArchiveIn, PageArchiveExportIn, page_archive_preflight, export_page_archive, PublicationIn, PublicationExportIn, publication_preflight, export_cbz, PDFPublicationIn, PDFPublicationExportIn, pdf_publication_preflight, export_pdf
import hashlib
from .production_lineage_api import PrivateProductionRoute, api_call


class ComicPrivateRoute(PrivateProductionRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def private(request):
            try:
                return await handler(request)
            except StarletteHTTPException as error:
                # Keep B06 validation and domain failures on one bounded private
                # response contract. The shared error envelope also preserves headers.
                return JSONResponse({'detail': error.detail}, status_code=error.status_code,
                                    headers={**(error.headers or {}), 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
            except RequestValidationError:
                return JSONResponse({'detail': {'code': 'COMIC_INPUT_INVALID'}}, status_code=422,
                                    headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
        return private


class VersionIn(StrictModel):
    expected_version: int = Field(ge=1, strict=True)


class ReviewIn(VersionIn):
    review_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    acknowledge_warnings: bool = False


class RestoreIn(VersionIn):
    target_version: int = Field(ge=1, strict=True)


def create_comic_layouts_router(service, authorize, require_flag, *, comic_authorize=None, authority_lease=None):
    router = APIRouter(prefix='/novels/{nid}/experimental/comic-layouts', tags=['Experimental comic layouts'], route_class=ComicPrivateRoute)
    def invoke(nid, token, branch, permission, callback):
        def access():
            require_flag('comic_layouts_v2'); require_flag('asset_lineage_v2'); require_flag('ai_director_v2')
            if comic_authorize is not None:
                return comic_authorize(nid, token, branch, permission)
            actor, scope = authorize(nid, token, branch, permission)
            return actor, scope, False
        actor, scope, source_free = access()
        def guard():
            if access() != (actor, scope, source_free): raise HTTPException(403, {'code': 'COMIC_AUTHORITY_CHANGED'})
        from contextlib import nullcontext
        lease = authority_lease(nid, token, actor, scope) if authority_lease else nullcontext()
        with lease, service.access_policy(source_free):
            guard()
            result = api_call(callback, actor, scope, guard); guard(); return result

    @router.get('/books')
    def books(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, 'domain.read', lambda a,s,g: service.books(nid,s,a))

    @router.post('/books', status_code=201)
    def create_book(nid: str, body: ComicBookIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, 'domain.write', lambda a,s,g: service.save_book(nid,s,a,body,g))

    @router.put('/books/{rid}')
    def update_book(nid: str, rid: str, body: ComicBookEdit, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, 'domain.write', lambda a,s,g: service.save_book(nid,s,a,body.model_dump(exclude={'expected_version'}),g,rid,body.expected_version))

    @router.post('/books/{rid}/pages', status_code=201)
    def book_page(nid: str, rid: str, body: ComicBookPageIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, 'domain.write', lambda a,s,g: service.book_page(nid,s,a,rid,body,g))

    @router.post('/books/{rid}/restore')
    def restore_book(nid: str, rid: str, body: RestoreIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, 'domain.write', lambda a,s,g: service.restore_book(nid,s,a,rid,body.expected_version,body.target_version,g))

    @router.post('/books/{rid}/publication-preflight')
    def book_publication_preflight(nid: str, rid: str, body: PublicationIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, 'domain.read', lambda a,s,g: publication_preflight(service,nid,s,a,rid,body,g))

    @router.post('/books/{rid}/export-cbz')
    def book_export_cbz(nid: str, rid: str, body: PublicationExportIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        def output(actor, scope, guard):
            data, receipt = export_cbz(service,nid,scope,actor,rid,body,guard)
            return Response(data, media_type='application/vnd.comicbook+zip', headers={
                'Content-Disposition': 'attachment; filename="comic-book.cbz"',
                'X-Comic-Publication-Digest': receipt, 'X-Content-SHA256': hashlib.sha256(data).hexdigest()})
        return invoke(nid, x_session_token, x_branch_id, 'domain.read', output)

    @router.post('/books/{rid}/pdf-publication-preflight')
    def book_pdf_preflight(nid: str, rid: str, body: PDFPublicationIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, 'domain.read', lambda a,s,g: pdf_publication_preflight(service,nid,s,a,rid,body,g))

    @router.post('/books/{rid}/export-pdf')
    def book_export_pdf(nid: str, rid: str, body: PDFPublicationExportIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        def output(actor, scope, guard):
            data, receipt = export_pdf(service,nid,scope,actor,rid,body,guard)
            return Response(data, media_type='application/pdf', headers={
                'Content-Disposition': 'attachment; filename="comic-book.pdf"',
                'X-Comic-Publication-Digest': receipt, 'X-Content-SHA256': hashlib.sha256(data).hexdigest()})
        return invoke(nid, x_session_token, x_branch_id, 'domain.read', output)

    @router.post('/books/{rid}/epub-publication-preflight')
    def book_epub_preflight(nid: str, rid: str, body: EPUBPublicationIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, 'domain.read', lambda a,s,g: epub_publication_preflight(service,nid,s,a,rid,body,g))

    @router.post('/books/{rid}/export-epub')
    def book_export_epub(nid: str, rid: str, body: EPUBPublicationExportIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        def output(actor, scope, guard):
            data, receipt = export_epub(service,nid,scope,actor,rid,body,guard)
            return Response(data, media_type='application/epub+zip', headers={
                'Content-Disposition': 'attachment; filename="comic-book.epub"',
                'X-Comic-Publication-Digest': receipt, 'X-Content-SHA256': hashlib.sha256(data).hexdigest()})
        return invoke(nid, x_session_token, x_branch_id, 'domain.read', output)

    @router.post('/books/{rid}/page-archive-preflight')
    def book_page_archive_preflight(nid: str, rid: str, body: PageArchiveIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, 'domain.read', lambda a,s,g: page_archive_preflight(service,nid,s,a,rid,body,g))

    @router.post('/books/{rid}/export-page-archive')
    def book_export_page_archive(nid: str, rid: str, body: PageArchiveExportIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        def output(actor, scope, guard):
            data, receipt = export_page_archive(service,nid,scope,actor,rid,body,guard)
            return Response(data, media_type='application/zip', headers={
                'Content-Disposition': 'attachment; filename="comic-pages.zip"',
                'X-Comic-Publication-Digest': receipt, 'X-Content-SHA256': hashlib.sha256(data).hexdigest()})
        return invoke(nid, x_session_token, x_branch_id, 'domain.read', output)

    @router.get('/catalog')
    def catalog(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, 'domain.read', lambda a,s,g: service.catalog(nid,s,a))

    @router.get('/records')
    def records(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, 'domain.read', lambda a,s,g: service.records(nid,s,a))

    @router.get('/images/{aid}')
    def image(nid: str, aid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, 'domain.read', lambda a,s,g: Response(service.image_preview(nid,s,a,aid), media_type='image/png'))

    @router.post('/images/{aid}/approve')
    def approve_image(nid: str, aid: str, body: VersionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, 'domain.review', lambda a,s,g: service.approve_image(nid,s,a,aid,body.expected_version,g))

    @router.post('/records', status_code=201)
    def create(nid: str, body: LayoutIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, 'domain.write', lambda a,s,g: service.save(nid,s,a,body,g))

    @router.put('/records/{rid}')
    def update(nid: str, rid: str, body: LayoutEdit, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, 'domain.write', lambda a,s,g: service.save(nid,s,a,body.model_dump(exclude={'expected_version'}),g,rid,body.expected_version))

    @router.post('/records/{rid}/preflight')
    def preflight(nid: str, rid: str, body: VersionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, 'domain.read', lambda a,s,g: service.preflight(nid,s,a,rid,body.expected_version))

    @router.post('/records/{rid}/approve')
    def approve(nid: str, rid: str, body: ReviewIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, 'domain.review', lambda a,s,g: service.approve(nid,s,a,rid,body.expected_version,body.review_digest,body.acknowledge_warnings,g))

    @router.post('/records/{rid}/restore')
    def restore(nid: str, rid: str, body: RestoreIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, 'domain.write', lambda a,s,g: service.restore(nid,s,a,rid,body.expected_version,body.target_version,g))

    @router.get('/records/{rid}/segments/{index}')
    def preview(nid: str, rid: str, index: int, expected_version: int = Query(ge=1), x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, 'domain.read', lambda a,s,g: Response(service.preview(nid,s,a,rid,expected_version,index,g), media_type='image/png'))

    @router.get('/records/{rid}/export')
    def export(nid: str, rid: str, expected_version: int = Query(ge=1), x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, 'domain.read', lambda a,s,g: Response(service.export(nid,s,a,rid,expected_version,g), media_type='application/zip', headers={'Content-Disposition': 'attachment; filename="comic-segments.zip"'}))
    @router.get('/records/{rid}/export-ora')
    def export_ora(nid: str, rid: str, expected_version: int = Query(ge=1), x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, 'domain.read', lambda a,s,g: Response(service.export_ora(nid,s,a,rid,expected_version,g), media_type='image/openraster', headers={'Content-Disposition': 'attachment; filename="comic-page.ora"'}))
    return router

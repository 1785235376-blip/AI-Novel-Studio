"""Ordered flattened CBZ/PDF copies from the original current Comic book/page owner.

No persistence, queue, source promotion or new approval authority lives here.
"""
import copy
import hashlib
import io
import json
import zipfile
from typing import Literal
from pydantic import Field, model_validator, field_validator
from .media import StrictModel, digest
from .common import check_version, StaleSourceError
from .comic_publication_budget import (publication_budget, consume, MAX_PAGE_PIXELS, MAX_ARCHIVE_BYTES)


class PublicationIn(StrictModel):
    expected_version: int = Field(ge=1, strict=True)
    reading_direction: Literal['LTR', 'RTL']


class PagePin(StrictModel):
    id: str = Field(min_length=1, max_length=80)
    version: int = Field(ge=1, strict=True)
    review_digest: str = Field(pattern=r'^[a-f0-9]{64}$')


class PublicationExportIn(PublicationIn):
    pages: list[PagePin] = Field(min_length=1, max_length=100)
    publication_digest: str = Field(pattern=r'^[a-f0-9]{64}$')


class PDFPublicationIn(PublicationIn):
    # Required caller choice: physical scale, never a print-quality assertion.
    dpi: int = Field(ge=36, le=600, strict=True)


class PDFPublicationExportIn(PDFPublicationIn, PublicationExportIn):
    pass


class EPUBPublicationIn(PublicationIn):
    format: Literal['comic-epub-fixed-raster-v1']
    # Explicit caller acknowledgement: content language is unspecified, not inferred.
    language: Literal['und']


class EPUBPublicationExportIn(EPUBPublicationIn, PublicationExportIn):
    pass


class PageArchiveIn(PublicationIn):
    image_format: Literal['JPEG', 'WEBP']
    loss_mode: Literal['LOSSY', 'LOSSLESS']
    quality: Literal[60, 80, 95, 100] | None

    @field_validator('quality', mode='before')
    @classmethod
    def strict_quality(cls, value):
        if value is not None and type(value) is not int:
            raise ValueError('COMIC_PAGE_ARCHIVE_INTEGER_QUALITY_REQUIRED')
        return value

    @model_validator(mode='after')
    def codec_contract(self):
        if self.loss_mode == 'LOSSLESS':
            if self.image_format != 'WEBP' or self.quality is not None:
                raise ValueError('COMIC_PAGE_ARCHIVE_LOSSLESS_WEBP_NULL_QUALITY_REQUIRED')
        elif type(self.quality) is not int:
            raise ValueError('COMIC_PAGE_ARCHIVE_LOSSY_QUALITY_REQUIRED')
        return self


class PageArchiveExportIn(PageArchiveIn, PublicationExportIn):
    pass


def _archive_options(request):
    return {'format': 'comic-page-archive-v1', 'image_format': request.image_format,
            'loss_mode': request.loss_mode, 'quality': request.quality}


def _archive_losses(request):
    return ['FLATTENED_RGB_RASTER_PAGES', 'NO_EDITABLE_LAYERS_OR_TEXT',
            'DIRECTION_METADATA_DOES_NOT_REORDER_PAGES_OR_PANELS',
            'NO_COLOR_PROFILE_OR_PRINT_FIDELITY', 'SOURCE_IMAGE_RIGHTS_NOT_VERIFIED',
            'EXTERNAL_READER_VALIDATION_NOT_RUN',
            'PIXEL_EXACT_FLATTENED_RGB_ONLY' if request.loss_mode == 'LOSSLESS'
            else 'LOSSY_PIXELS_INCLUDING_QUALITY_100']


def _archive_admission(rows, request):
    from .comic_page_archive_codec import admit
    return admit([(r['document']['width'], r['document']['height']) for r in rows], request)


PDF_LOSSES = ['FLATTENED_RGB_RASTER_PAGES', 'NO_EDITABLE_LAYERS_OR_TEXT',
              'DIRECTION_METADATA_DOES_NOT_REORDER_PAGES_OR_PANELS',
              'CALLER_SELECTED_DPI_NOT_PRINT_QUALITY', 'NO_BLEED_OR_PDF_A_PDF_X_CONFORMANCE',
              'SOURCE_IMAGE_RIGHTS_NOT_VERIFIED', 'EXTERNAL_READER_VALIDATION_NOT_RUN']


def _pdf_admission(rows, dpi):
    from app.pdf_export import raster_pdf_bounds
    from . import comic_publication_budget as budget
    # PDF 1.4 default user-space MediaBox limit, without a /UserUnit extension.
    if any(max(r['document']['width'], r['document']['height']) * 72 / dpi > 14400 for r in rows):
        raise ValueError('COMIC_PUBLICATION_PDF_PAGE_SIZE_LIMIT')
    work, output = raster_pdf_bounds((r['document']['width'], r['document']['height']) for r in rows)
    if work > budget.MAX_PDF_WORK_BYTES:
        raise ValueError('COMIC_PUBLICATION_PDF_LIMIT')
    if output > MAX_ARCHIVE_BYTES:
        raise ValueError('COMIC_PUBLICATION_ARCHIVE_LIMIT')
    return work


LOSSES = ['FLATTENED_RGB_PNG_PAGES', 'NO_EDITABLE_LAYERS_OR_TEXT',
          'DIRECTION_METADATA_DOES_NOT_REORDER_PAGES_OR_PANELS',
          'NO_DPI_BLEED_OR_PRINT_CONFORMANCE', 'SOURCE_IMAGE_RIGHTS_NOT_VERIFIED',
          'EXTERNAL_READER_VALIDATION_NOT_RUN']


class BoundedBuffer(io.BytesIO):
    def write(self, data):
        if self.tell() + len(data) > MAX_ARCHIVE_BYTES:
            raise ValueError('COMIC_PUBLICATION_ARCHIVE_LIMIT')
        consume('encoded', len(data))
        return super().write(data)


def _snapshot(service, nid, scope, actor, rid, request, guard):
    # Reject missing owners/scopes before entering the existing lock boundary.
    service._book_row(nid, scope, actor, rid)
    with service._independent_transaction(nid, scope):
        return _locked_snapshot(service, nid, scope, actor, rid, request, guard)


def _locked_snapshot(service, nid, scope, actor, rid, request, guard):
    guard()
    book = copy.deepcopy(service._book_row(nid, scope, actor, rid))
    check_version(book, request.expected_version)
    ids = service._book_pages(book['document'])
    if not ids or len(ids) > 100 or len(set(ids)) != len(ids):
        raise ValueError('COMIC_PUBLICATION_PAGE_SET_INVALID')
    # Cheap geometry admission before any source decoding.
    rows = []
    for pid in ids:
        row = copy.deepcopy(service._row(nid, scope, actor, pid))
        if not service._independent(row) or row['document']['preset'] != 'PAGE':
            raise ValueError('COMIC_PUBLICATION_INDEPENDENT_PAGE_REQUIRED')
        rows.append(row)
    if sum(r['document']['width'] * r['document']['height'] for r in rows) > MAX_PAGE_PIXELS:
        raise ValueError('COMIC_PUBLICATION_PAGE_PIXEL_LIMIT')
    if isinstance(request, PDFPublicationIn):
        _pdf_admission(rows, request.dpi)
    if isinstance(request, PageArchiveIn):
        archive_limits = _archive_admission(rows, request)
    if isinstance(request, EPUBPublicationIn):
        from .comic_epub_package import admit
        epub_limits = admit(book, rows, MAX_ARCHIVE_BYTES)
    pages = []
    for row in rows:
        guard()
        report = service.preflight(nid, scope, actor, row['id'], row['version'])
        if row['status'] != 'APPROVED' or (row.get('approval') or {}).get('digest') != report['review_digest']:
            raise ValueError('COMIC_CURRENT_EXPLICIT_APPROVAL_REQUIRED')
        if not report['can_render']:
            raise ValueError('COMIC_PREFLIGHT_BLOCKED')
        pages.append({'id': row['id'], 'version': row['version'], 'review_digest': report['review_digest']})
    binding = {'book_id': rid, 'book_version': book['version'], 'book': book['document'],
               'project_incarnation': book['project_incarnation'], 'actor': actor, 'scope': scope,
               'pages': pages, 'reading_direction': request.reading_direction, 'format': 'comic-cbz-v1'}
    if isinstance(request, PDFPublicationIn):
        binding.update(format='comic-pdf-raster-v1', dpi=request.dpi)
    if isinstance(request, PageArchiveIn):
        binding.update(_archive_options(request))
    if isinstance(request, EPUBPublicationIn):
        binding.update(format=request.format, language=request.language)
    guard()
    # Prevent a structure change during the preflight itself.
    latest = service._book_row(nid, scope, actor, rid)
    check_version(latest, request.expected_version)
    if latest['document'] != book['document']:
        raise StaleSourceError('COMIC_PUBLICATION_CHANGED')
    receipt = {'book_version': book['version'], 'reading_direction': request.reading_direction,
                        'pages': pages, 'publication_digest': digest(binding), 'page_count': len(pages), 'losses': LOSSES}
    if isinstance(request, PDFPublicationIn):
        from . import comic_publication_budget as budget
        receipt['pdf_limits'] = {
            'max_pdf_work_bytes': budget.MAX_PDF_WORK_BYTES,
            'max_output_bytes': MAX_ARCHIVE_BYTES,
            'total_page_pixels': sum(r['document']['width'] * r['document']['height'] for r in rows),
            'max_total_page_pixels_for_page_count': max(0, min(MAX_PAGE_PIXELS,
                (budget.MAX_PDF_WORK_BYTES - (len(rows) + 4) * 1024 * 1024) // 192,
                (MAX_ARCHIVE_BYTES - len(rows) * 65536 - 4 * 1024 * 1024) // 4)),
        }
        receipt.update(format='comic-pdf-raster-v1', dpi=request.dpi, losses=PDF_LOSSES,
                       page_dimensions=[{'width_pixels': r['document']['width'], 'height_pixels': r['document']['height'],
                           'width_points': r['document']['width'] * 72 / request.dpi,
                           'height_points': r['document']['height'] * 72 / request.dpi} for r in rows])
    if isinstance(request, PageArchiveIn):
        receipt.update(**_archive_options(request), losses=_archive_losses(request), page_archive_limits=archive_limits)
    if isinstance(request, EPUBPublicationIn):
        from .comic_epub_package import LOSSES as EPUB_LOSSES
        receipt.update(format=request.format, language=request.language, losses=EPUB_LOSSES,
                       epub_limits=epub_limits, page_dimensions=[{
                           'width_pixels': r['document']['width'], 'height_pixels': r['document']['height']} for r in rows])
    return book, rows, receipt


def publication_preflight(service, nid, scope, actor, rid, value, guard=lambda: None):
    request = PublicationIn.model_validate(value)
    with publication_budget():
        return _snapshot(service, nid, scope, actor, rid, request, guard)[2]


def _full_page(document, report, segments):
    from PIL import Image
    width, height = document['width'], document['height']
    consume('render', width * height * 2)  # stitch surface and PNG encoder input
    if len(report['segments']) != len(segments):
        raise ValueError('COMIC_PUBLICATION_SEGMENTS_INVALID')
    with Image.new('RGB', (width, height), 'white') as canvas:
        cursor = 0
        for descriptor, data in zip(report['segments'], segments):
            if descriptor['y'] != cursor or descriptor['width'] != width:
                raise ValueError('COMIC_PUBLICATION_SEGMENTS_INVALID')
            consume('decode', width * descriptor['height'])
            with Image.open(io.BytesIO(data)) as segment:
                if segment.format != 'PNG' or segment.size != (width, descriptor['height']):
                    raise ValueError('COMIC_PUBLICATION_SEGMENTS_INVALID')
                segment.load(); canvas.paste(segment, (0, cursor))
            cursor += descriptor['height']
        if cursor != height:
            raise ValueError('COMIC_PUBLICATION_SEGMENTS_INVALID')
        output = BoundedBuffer()
        canvas.save(output, format='PNG', compress_level=6)
        return output.getvalue()


def _render_work(document, report):
    pixels = 2 * document['width'] * document['height']
    pixels += sum(p['size'][0] * p['size'][1] for p in report['placements'].values())
    panels = {p['id']: p for p in document['panels']}
    bubbles = {b['id']: b for p in document['panels'] for b in p['bubbles']}
    if 'layer_stack' in document:
        pixels += document['width'] * document['height']  # RGBA to RGB canvas conversion
        for item in document['layer_stack']['items']:
            obj = item if item['kind'] == 'RASTER' else (panels if item['kind'].startswith('PANEL_') else bubbles)[item['target_id']]
            # Surface + worst-case opacity copy/channel/compositing work, even
            # invisible layers: the existing renderer still constructs them.
            pixels += 4 * obj['width'] * obj['height']
    else:
        pixels += sum(2 * p['width'] * p['height'] for p in panels.values() if p.get('artwork_mode', 'IMAGE') != 'BLANK')
    return pixels


def export_cbz(service, nid, scope, actor, rid, value, guard=lambda: None):
    from .comic_layouts import licensed_font
    request = PublicationExportIn.model_validate(value)
    with publication_budget():
        book, rows, receipt = _snapshot(service, nid, scope, actor, rid, request, guard)
        if request.publication_digest != receipt['publication_digest'] or [p.model_dump() for p in request.pages] != receipt['pages']:
            raise StaleSourceError('COMIC_PUBLICATION_CHANGED')
        stream = BoundedBuffer()
        manifest = {'format': 'comic-cbz-v1', 'title': book['document']['title'],
                    'book_version': book['version'], 'publication_digest': receipt['publication_digest'],
                    'reading_direction': request.reading_direction, 'page_order': 'SAVED_CHAPTER_THEN_PAGE_ORDER',
                    'losses': LOSSES, 'automatic_publication': False, 'pages': [],
                    'chapters': [{'title': c['title'], 'page_count': len(c['pages'])} for c in book['document']['chapters']]}
        def put(archive, name, data):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            archive.writestr(info, data)
        with zipfile.ZipFile(stream, 'w') as archive:
            for index, (row, pin) in enumerate(zip(rows, receipt['pages'])):
                guard()
                data = _render_page(service, nid, scope, actor, row)
                filename = f'{index + 1:04}.png'
                put(archive, filename, data)
                manifest['pages'].append({'filename': filename, 'sha256': hashlib.sha256(data).hexdigest(),
                    'version': pin['version'], 'review_digest': pin['review_digest'],
                    'width': row['document']['width'], 'height': row['document']['height'],
                    'safe_area_pixels': row['document']['safe_area']})
                del data
            put(archive, 'manifest.json', json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode())
            if any(p['bubbles'] for row in rows for p in row['document']['panels']):
                put(archive, 'OFL.txt', licensed_font()[1])
        # No byte escapes until every page and source has been rechecked globally.
        final = _snapshot(service, nid, scope, actor, rid, request, guard)[2]
        if final != receipt:
            raise StaleSourceError('COMIC_PUBLICATION_CHANGED')
        guard()
        return stream.getvalue(), receipt['publication_digest']


def _render_page(service, nid, scope, actor, row):
    from .comic_layouts import compose
    images = service._current(nid, scope, actor, row)
    report, _ = compose(row['document'], images)
    if not report['can_render']:
        raise ValueError('COMIC_PREFLIGHT_BLOCKED')
    consume('render', _render_work(row['document'], report))
    report, segments = compose(row['document'], images, render=True)
    return _full_page(row['document'], report, segments)


def pdf_publication_preflight(service, nid, scope, actor, rid, value, guard=lambda: None):
    request = PDFPublicationIn.model_validate(value)
    with publication_budget():
        return _snapshot(service, nid, scope, actor, rid, request, guard)[2]


def export_pdf(service, nid, scope, actor, rid, value, guard=lambda: None):
    from app.pdf_export import RasterPDFCopy
    request = PDFPublicationExportIn.model_validate(value)
    with publication_budget():
        book, rows, receipt = _snapshot(service, nid, scope, actor, rid, request, guard)
        if request.publication_digest != receipt['publication_digest'] or [p.model_dump() for p in request.pages] != receipt['pages']:
            raise StaleSourceError('COMIC_PUBLICATION_CHANGED')
        # Reserve all ReportLab pixel copies and whole-document serialization
        # BEFORE creating its canvas or rendering any pages. This is additional
        # to the shared source/decode/render/PNG/output budget, not a replacement.
        consume('pdf', _pdf_admission(rows, request.dpi))
        stream = BoundedBuffer()
        public_receipt = {k: receipt[k] for k in ('format', 'dpi', 'reading_direction', 'page_count',
                                                 'page_dimensions', 'publication_digest', 'losses')}
        public_receipt.update(page_order='SAVED_CHAPTER_THEN_PAGE_ORDER', automatic_publication=False)
        writer = RasterPDFCopy(stream, title=book['document']['title'],
                               receipt=json.dumps(public_receipt, ensure_ascii=True, sort_keys=True))
        for row in rows:
            guard()
            data = _render_page(service, nid, scope, actor, row)
            width, height = row['document']['width'], row['document']['height']
            consume('decode', width * height)
            writer.page(data, width, height, request.dpi)
            del data
        writer.finish()
        # Serialization cannot release bytes before full current-source, privacy,
        # approval, owner incarnation and actor/scope authorization revalidation.
        final = _snapshot(service, nid, scope, actor, rid, request, guard)[2]
        if final != receipt:
            raise StaleSourceError('COMIC_PUBLICATION_CHANGED')
        guard()
        return stream.getvalue(), receipt['publication_digest']


def page_archive_preflight(service, nid, scope, actor, rid, value, guard=lambda: None):
    request = PageArchiveIn.model_validate(value)
    with publication_budget():
        return _snapshot(service, nid, scope, actor, rid, request, guard)[2]


def export_page_archive(service, nid, scope, actor, rid, value, guard=lambda: None):
    from .comic_page_archive_codec import encode
    from .comic_layouts import licensed_font
    request = PageArchiveExportIn.model_validate(value)
    with publication_budget():
        book, rows, receipt = _snapshot(service, nid, scope, actor, rid, request, guard)
        if request.publication_digest != receipt['publication_digest'] or [p.model_dump() for p in request.pages] != receipt['pages']:
            raise StaleSourceError('COMIC_PUBLICATION_CHANGED')
        # Admission covers the ENTIRE codec request before the first allocation.
        # Source loading/rendering retain their existing cumulative budgets.
        _archive_admission(rows, request)
        stream = BoundedBuffer()
        manifest = {**_archive_options(request), 'title': book['document']['title'],
            'publication_digest': receipt['publication_digest'], 'book_version': book['version'],
            'reading_direction': request.reading_direction, 'page_order': 'SAVED_CHAPTER_THEN_PAGE_ORDER',
            'automatic_publication': False, 'losses': receipt['losses'], 'pages': [],
            'chapters': [{'title': c['title'], 'page_count': len(c['pages'])} for c in book['document']['chapters']]}
        def put(archive, name, data):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            archive.writestr(info, data)
        with zipfile.ZipFile(stream, 'w') as archive:
            for index, (row, pin) in enumerate(zip(rows, receipt['pages'])):
                guard()
                png = _render_page(service, nid, scope, actor, row)
                data = encode(png, row['document']['width'], row['document']['height'], request)
                filename = f'{index + 1:04}.' + ('jpg' if request.image_format == 'JPEG' else 'webp')
                put(archive, filename, data)
                manifest['pages'].append({'filename': filename, 'sha256': hashlib.sha256(data).hexdigest(),
                    'version': pin['version'], 'review_digest': pin['review_digest'],
                    'width': row['document']['width'], 'height': row['document']['height'],
                    'safe_area_pixels': row['document']['safe_area']})
                del png, data
            put(archive, 'manifest.json', json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode())
            if any(p['bubbles'] for row in rows for p in row['document']['panels']):
                put(archive, 'OFL.txt', licensed_font()[1])
        final = _snapshot(service, nid, scope, actor, rid, request, guard)[2]
        if final != receipt:
            raise StaleSourceError('COMIC_PUBLICATION_CHANGED')
        guard()
        return stream.getvalue(), receipt['publication_digest']


def epub_publication_preflight(service, nid, scope, actor, rid, value, guard=lambda: None):
    request = EPUBPublicationIn.model_validate(value)
    with publication_budget():
        return _snapshot(service, nid, scope, actor, rid, request, guard)[2]


def export_epub(service, nid, scope, actor, rid, value, guard=lambda: None):
    from .comic_epub_package import Package
    request = EPUBPublicationExportIn.model_validate(value)
    with publication_budget():
        book, rows, receipt = _snapshot(service, nid, scope, actor, rid, request, guard)
        if request.publication_digest != receipt['publication_digest'] or [p.model_dump() for p in request.pages] != receipt['pages']:
            raise StaleSourceError('COMIC_PUBLICATION_CHANGED')
        stream = BoundedBuffer()
        writer = Package(stream, book, rows, request, receipt)
        try:
            for index, row in enumerate(rows, 1):
                guard()
                data = _render_page(service, nid, scope, actor, row)
                writer.page(index, data)
                del data
        finally:
            writer.finish()
        # No bytes leave the original current approval/source/authority boundary
        # before the entire ZIP and all pages have been globally revalidated.
        final = _snapshot(service, nid, scope, actor, rid, request, guard)[2]
        if final != receipt:
            raise StaleSourceError('COMIC_PUBLICATION_CHANGED')
        guard()
        return stream.getvalue(), receipt['publication_digest']

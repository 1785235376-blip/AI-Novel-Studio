"""Ordered flattened CBZ copies from the original current Comic book/page owner.

No persistence, queue, source promotion or new approval authority lives here.
"""
import copy
import hashlib
import io
import json
import zipfile
from typing import Literal
from pydantic import Field
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
    guard()
    # Prevent a structure change during the preflight itself.
    latest = service._book_row(nid, scope, actor, rid)
    check_version(latest, request.expected_version)
    if latest['document'] != book['document']:
        raise StaleSourceError('COMIC_PUBLICATION_CHANGED')
    return book, rows, {'book_version': book['version'], 'reading_direction': request.reading_direction,
                        'pages': pages, 'publication_digest': digest(binding), 'page_count': len(pages), 'losses': LOSSES}


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
    from .comic_layouts import compose, licensed_font
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
                images = service._current(nid, scope, actor, row)
                report, _ = compose(row['document'], images)
                if not report['can_render']:
                    raise ValueError('COMIC_PREFLIGHT_BLOCKED')
                # Covers canvas, segment encoder inputs, and actual resampling.
                consume('render', _render_work(row['document'], report))
                report, segments = compose(row['document'], images, render=True)
                data = _full_page(row['document'], report, segments)
                filename = f'{index + 1:04}.png'
                put(archive, filename, data)
                manifest['pages'].append({'filename': filename, 'sha256': hashlib.sha256(data).hexdigest(),
                    'version': pin['version'], 'review_digest': pin['review_digest'],
                    'width': row['document']['width'], 'height': row['document']['height'],
                    'safe_area_pixels': row['document']['safe_area']})
                del images, segments, data
            put(archive, 'manifest.json', json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode())
            if any(p['bubbles'] for row in rows for p in row['document']['panels']):
                put(archive, 'OFL.txt', licensed_font()[1])
        # No byte escapes until every page and source has been rechecked globally.
        final = _snapshot(service, nid, scope, actor, rid, request, guard)[2]
        if final != receipt:
            raise StaleSourceError('COMIC_PUBLICATION_CHANGED')
        guard()
        return stream.getvalue(), receipt['publication_digest']

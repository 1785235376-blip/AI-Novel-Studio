"""Publication of existing reviewed raster/text layers, no new ORA implementation."""
import copy
import io
import json
import os
import zipfile
import pytest
from PIL import Image
from test_v2_independent_workspace import rig
from test_comic_ora_staging import staging, prepare, stage
from test_comic_ora_review_attach import reviewed, page, attach
from app.experimental.comic_publication import export_cbz, publication_preflight, _render_work
from app.experimental import comic_publication_budget as budget


def approved(service, rig, target):
    report = service.preflight(rig.nid, rig.scope, rig.actor, target['id'], target['version'])
    return service.approve(rig.nid, rig.scope, rig.actor, target['id'], target['version'], report['review_digest'], True)


def publication(service, rig, pages):
    book = service.save_book(rig.nid, rig.scope, rig.actor, {'title': 'Layer book', 'chapters': [
        {'id': 'chapter', 'title': 'Pages', 'pages': [p['id'] for p in pages]}],
        'expected_page_versions': {p['id']: p['version'] for p in pages}})
    base = {'expected_version': book['version'], 'reading_direction': 'LTR'}
    report = publication_preflight(service, rig.nid, rig.scope, rig.actor, book['id'], base)
    return book, {**base, 'pages': report['pages'], 'publication_digest': report['publication_digest']}


def test_visible_and_hidden_reviewed_raster_pages(rig, staging):
    row = prepare(rig, staging); stage(rig, staging, row)
    target = page(rig, staging); review = reviewed(rig, staging, row)
    attached = attach(rig, staging, review, target)['page']; service = staging.comic
    visible = approved(service, rig, attached)
    document = copy.deepcopy(visible['document']); document['layer_stack']['items'][0]['visible'] = False
    hidden = approved(service, rig, service.save(rig.nid, rig.scope, rig.actor, document))
    book, body = publication(service, rig, [visible, hidden])
    data, _ = export_cbz(service, rig.nid, rig.scope, rig.actor, book['id'], body)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert Image.open(io.BytesIO(archive.read('0001.png'))).getpixel((10, 20)) == (255, 127, 127)
        assert Image.open(io.BytesIO(archive.read('0002.png'))).getpixel((10, 20)) == (255, 255, 255)
        assert len(json.loads(archive.read('manifest.json'))['pages']) == 2


def test_text_publication_includes_exact_pinned_license(rig, staging, monkeypatch):
    from app.experimental.comic_layouts import licensed_font
    path = os.environ.get('R2_TEST_FONT_FILE')
    if path: monkeypatch.setenv('AI_NOVEL_STUDIO_PDF_FONT', path)
    try: _, license_bytes, _ = licensed_font()
    except ValueError: pytest.skip('verified pinned OFL font required')
    service = staging.comic
    document = {'title': 'Text page', 'source_mode': 'INDEPENDENT', 'width': 640, 'height': 640,
        'panels': [{'id': 'p', 'order': 1, 'artwork_mode': 'BLANK', 'x': 24, 'y': 24, 'width': 592, 'height': 592,
                    'bubbles': [{'id': 'b', 'text': '原始对白', 'x': 40, 'y': 40, 'width': 500, 'height': 200}]}]}
    target = approved(service, rig, service.save(rig.nid, rig.scope, rig.actor, document))
    book, body = publication(service, rig, [target])
    data, _ = export_cbz(service, rig.nid, rig.scope, rig.actor, book['id'], body)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert archive.read('OFL.txt') == license_bytes
        assert not any(name.endswith(('.ttf', '.otf')) for name in archive.namelist())


def test_layer_canvas_conversion_is_budgeted_before_render(rig, staging, monkeypatch):
    row = prepare(rig, staging); stage(rig, staging, row)
    target = attach(rig, staging, reviewed(rig, staging, row), page(rig, staging))['page']
    service = staging.comic; target = approved(service, rig, target)
    book, body = publication(service, rig, [target])
    from app.experimental import comic_layouts as layouts
    report = service.preflight(rig.nid, rig.scope, rig.actor, target['id'], target['version'])
    required = _render_work(target['document'], report)
    monkeypatch.setattr(budget, 'MAX_RENDER_PIXELS', required - 1)
    original = layouts.compose
    rendered = []
    def spy(*args, **kwargs):
        if kwargs.get('render'): rendered.append(True)
        return original(*args, **kwargs)
    monkeypatch.setattr(layouts, 'compose', spy)
    with pytest.raises(ValueError, match='PUBLICATION_RENDER_LIMIT'):
        export_cbz(service, rig.nid, rig.scope, rig.actor, book['id'], body)
    assert rendered == []

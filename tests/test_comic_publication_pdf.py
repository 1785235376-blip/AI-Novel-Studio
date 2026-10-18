"""Actual ReportLab bytes parsed by pypdf; NOT independent viewer acceptance.

Same opt-in File/PostgreSQL original owners and trusted-session fixtures as CBZ.
"""
import copy
import hashlib
import io
import json
import pytest
from pypdf import PdfReader
from PIL import Image
import test_comic_publication as cbz
from test_comic_publication import setup_book, publication_scope
from test_comic_independent import original_independent_owner
from test_r3_mounted_contracts import mounted, prefix, checked
from app.experimental import comic_publication_budget as budget
from app.experimental.comic_publication import export_pdf


def request(e, book, path, dpi=144):
    body = {'expected_version': book['version'], 'reading_direction': 'RTL', 'dpi': dpi}
    receipt = checked(e.client.post(path + '/pdf-publication-preflight', json=body))
    return {**body, 'pages': receipt['pages'], 'publication_digest': receipt['publication_digest']}, receipt


def test_actual_ordered_raster_pdf_dimensions_receipt_and_no_mutation(mounted):
    e = mounted; service, pages, book, path = setup_book(e, 6)
    # One differently sized page proves MediaBox follows each page, not a preset.
    document = copy.deepcopy(pages[2]['document']); document.update(width=400, height=720)
    page = service.save(e.nid, e.scope, 'local-author', document, rid=pages[2]['id'], expected_version=pages[2]['version'])
    report = service.preflight(e.nid, e.scope, 'local-author', page['id'], page['version'])
    service.approve(e.nid, e.scope, 'local-author', page['id'], page['version'], report['review_digest'], True)
    before = e.store.read(e.nid, e.scope)
    body, report = request(e, book, path)
    assert report['pdf_limits']['total_page_pixels'] == 5 * 320 * 640 + 400 * 720
    assert report['pdf_limits']['max_total_page_pixels_for_page_count'] < 2_800_000
    response = e.client.post(path + '/export-pdf', json=body)
    assert response.status_code == 200, response.text
    assert response.headers['content-type'] == 'application/pdf'
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['x-comic-publication-digest'] == report['publication_digest']
    assert response.headers['x-content-sha256'] == hashlib.sha256(response.content).hexdigest()
    reader = PdfReader(io.BytesIO(response.content), strict=True)
    assert len(reader.pages) == 6
    receipt = json.loads(reader.metadata.subject)
    assert receipt['format'] == 'comic-pdf-raster-v1' and receipt['dpi'] == 144
    assert receipt['reading_direction'] == 'RTL' and receipt['automatic_publication'] is False
    assert receipt['page_order'] == 'SAVED_CHAPTER_THEN_PAGE_ORDER'
    assert 'EXTERNAL_READER_VALIDATION_NOT_RUN' in receipt['losses']
    assert 'NO_BLEED_OR_PDF_A_PDF_X_CONFORMANCE' in receipt['losses']
    for i, page in enumerate(reader.pages):
        width, height = (400, 720) if i == 2 else (320, 640)
        assert tuple(float(x) for x in page.mediabox) == (0, 0, width / 2, height / 2)
        assert not page.extract_text()  # bubbles/text, when present, are pixels
        assert len(page.images) == 1
        with Image.open(io.BytesIO(page.images[0].data)) as image:
            assert image.size == (width, height)
            assert image.getpixel((24+i, 24)) == (0, 0, 0)
            assert image.getpixel((24+i, 603)) == (0, 0, 0)
            assert image.getpixel((23+i, 24)) == (255, 255, 255)
        assert '/Annots' not in page
    assert '/OpenAction' not in reader.trailer['/Root']
    assert '/Names' not in reader.trailer['/Root']
    assert not any(value in str(reader.metadata) for value in ('asset_sources', 'source_evidence', 'project_incarnation', 'local-author'))
    assert before == e.store.read(e.nid, e.scope)
    assert e.client.post(path + '/export-pdf', json=body).content == response.content


@pytest.mark.parametrize('dpi', [None, 0, 35, 601, 72.5, True, '144'])
def test_explicit_bounded_integer_scale(mounted, dpi):
    e = mounted; _, _, book, path = setup_book(e, 1)
    body = {'expected_version': book['version'], 'reading_direction': 'LTR'}
    if dpi is not None: body['dpi'] = dpi
    response = e.client.post(path + '/pdf-publication-preflight', json=body)
    assert response.status_code == 422 and response.headers['cache-control'] == 'no-store'


def test_scale_and_format_are_bound_to_approval_receipt(mounted):
    e = mounted; _, _, book, path = setup_book(e, 1)
    body, first = request(e, book, path, 72)
    _, second = request(e, book, path, 144)
    old = cbz.request(e, book, path)
    assert len({first['publication_digest'], second['publication_digest'], old['publication_digest']}) == 3
    for altered in ({**body, 'dpi': 144}, {**old, 'dpi': 72}):
        assert e.client.post(path + '/export-pdf', json=altered).status_code == 409
    # Existing CBZ schema does not silently acquire PDF fields.
    assert e.client.post(path + '/export-cbz', json=body).status_code == 422


@pytest.mark.parametrize('kind', ['pdf', 'output', 'decode', 'render', 'encoded'])
def test_whole_request_pdf_admission_and_encoding_budgets(mounted, monkeypatch, kind):
    import app.pdf_export as pdf
    import app.experimental.comic_publication as publication
    e = mounted; _, _, book, path = setup_book(e, 2); body, _ = request(e, book, path)
    if kind in ('pdf', 'output'):
        def forbidden(*args, **kwargs): raise AssertionError('ReportLab allocation before admission')
        monkeypatch.setattr(pdf.RasterPDFCopy, '__init__', forbidden)
        if kind == 'pdf': monkeypatch.setattr(budget, 'MAX_PDF_WORK_BYTES', 1)
        else: monkeypatch.setattr(publication, 'MAX_ARCHIVE_BYTES', 1)
    else:
        name = {'decode': 'MAX_DECODE_PIXELS', 'render': 'MAX_RENDER_PIXELS', 'encoded': 'MAX_BUFFER_WRITE_BYTES'}[kind]
        monkeypatch.setattr(budget, name, 1)
    response = e.client.post(path + '/export-pdf', json=body)
    assert response.status_code == 422, response.text
    assert not response.content.startswith(b'%PDF')


def test_pdf_work_is_cumulative_before_canvas_allocation(mounted, monkeypatch):
    from app.pdf_export import raster_pdf_bounds
    import app.pdf_export as pdf
    e = mounted; _, _, book, path = setup_book(e, 2); body, _ = request(e, book, path)
    single, _ = raster_pdf_bounds([(320, 640)])
    monkeypatch.setattr(budget, 'MAX_PDF_WORK_BYTES', single + 1)
    def forbidden(*args, **kwargs): raise AssertionError('cumulative budget must fail before canvas')
    monkeypatch.setattr(pdf.RasterPDFCopy, '__init__', forbidden)
    response = e.client.post(path + '/export-pdf', json=body)
    assert response.status_code == 422 and 'PUBLICATION_PDF_LIMIT' in response.text


def test_final_authority_check_after_reportlab_serialization(mounted, monkeypatch):
    import app.pdf_export as pdf
    e = mounted; service, _, book, path = setup_book(e, 1); body, _ = request(e, book, path)
    revoked = False; finish = pdf.RasterPDFCopy.finish
    def revoke(self):
        nonlocal revoked
        finish(self); revoked = True
    monkeypatch.setattr(pdf.RasterPDFCopy, 'finish', revoke)
    def guard():
        if revoked: raise PermissionError('revoked')
    with pytest.raises(PermissionError):
        export_pdf(service, e.nid, e.scope, 'local-author', book['id'], body, guard)


# Reuse the original adverse owner/source scenarios against the real PDF routes.
# Only URL/request adaptation is changed; assertions and actual original stores,
# mutation races, privacy transitions and session revocations remain unchanged.
def pdf_routes(e, monkeypatch):
    post = e.client.post
    def pdf_post(url, **kwargs):
        if url.endswith(('/publication-preflight', '/export-cbz')):
            url = url.removesuffix('/publication-preflight') + '/pdf-publication-preflight' if url.endswith('/publication-preflight') else url.removesuffix('/export-cbz') + '/export-pdf'
            kwargs['json'] = {**kwargs['json'], 'dpi': 144}
        response = post(url, **kwargs)
        if response.status_code != 200: assert not response.content.startswith(b'%PDF')
        return response
    monkeypatch.setattr(e.client, 'post', pdf_post)


@pytest.mark.parametrize('change', ['page_pin', 'digest', 'missing', 'extra', 'order', 'book_version', 'direction'])
def test_exact_pdf_pins(mounted, monkeypatch, change):
    pdf_routes(mounted, monkeypatch); cbz.test_exact_export_pins(mounted, change)


@pytest.mark.parametrize('change', ['page', 'book', 'approval'])
def test_pdf_global_final_recheck(mounted, monkeypatch, change):
    pdf_routes(mounted, monkeypatch); cbz.test_global_final_recheck_first_page_after_render(mounted, monkeypatch, change)


@pytest.mark.parametrize('change', ['asset', 'privacy', 'decode', 'source'])
def test_pdf_current_sources(mounted, monkeypatch, change):
    pdf_routes(mounted, monkeypatch); cbz.test_actual_source_pins_and_decode_budget(mounted, monkeypatch, change)


@pytest.mark.parametrize('change', ['draft', 'webtoon', 'owner', 'actor', 'scope'])
def test_pdf_current_owner(mounted, monkeypatch, change):
    pdf_routes(mounted, monkeypatch); cbz.test_unapproved_or_foreign_page_fail_closed(mounted, change)


def test_pdf_real_scope_and_revocation(publication_scope, monkeypatch):
    pdf_routes(publication_scope, monkeypatch); cbz.test_real_session_scope_and_mid_render_revocation(publication_scope, monkeypatch)


def test_equal_rgb_bytes_different_rectangular_geometry_never_deduplicate():
    # Reproduces ReportLab 4.5.1 Canvas.drawImage geometry-blind RGB cache.
    # Nonuniform stripes must retain both byte order AND each image's shape.
    from app.pdf_export import RasterPDFCopy, raster_pdf_bounds
    stream = io.BytesIO()
    writer = RasterPDFCopy(stream, title='Geometry adversary', receipt='{}')
    raw = (bytes((255, 0, 0)) * 160 + bytes((0, 0, 255)) * 160) * 640
    dimensions = [(320, 640), (640, 320)]
    for width, height in dimensions:
        with Image.frombytes('RGB', (width, height), raw) as image:
            png = io.BytesIO(); image.save(png, format='PNG')
            writer.page(png.getvalue(), width, height, 72)
    writer.finish()
    data = stream.getvalue(); reader = PdfReader(io.BytesIO(data), strict=True)
    assert len(data) < raster_pdf_bounds(dimensions)[1]
    for page, dimensions in zip(reader.pages, dimensions):
        assert tuple(float(v) for v in page.mediabox)[2:] == dimensions
        image = page.images[0].image
        assert image.size == dimensions
        assert image.tobytes() == raw
        assert image.getpixel((159, 0)) == (255, 0, 0)
        assert image.getpixel((160, 0)) == (0, 0, 255)
    assert reader.pages[1].images[0].image.getpixel((320, 0)) == (255, 0, 0)


def test_pdf_14_physical_size_limit_before_decode():
    import app.experimental.comic_publication as publication
    rows = [{'document': {'width': 320, 'height': 8000}}]
    with pytest.raises(ValueError, match='PDF_PAGE_SIZE_LIMIT'):
        publication._pdf_admission(rows, 36)
    assert publication._pdf_admission(rows, 72) > 0


from test_v2_independent_workspace import rig
from test_comic_ora_staging import staging, prepare, stage
from test_comic_ora_review_attach import reviewed, page, attach
from test_comic_publication_layers import approved


def layer_pdf(service, rig, pages):
    from app.experimental.comic_publication import pdf_publication_preflight
    book = service.save_book(rig.nid, rig.scope, rig.actor, {'title': 'Raster layers', 'chapters': [
        {'id': 'c', 'title': 'Pages', 'pages': [p['id'] for p in pages]}],
        'expected_page_versions': {p['id']: p['version'] for p in pages}})
    base = {'expected_version': book['version'], 'reading_direction': 'LTR', 'dpi': 96}
    report = pdf_publication_preflight(service, rig.nid, rig.scope, rig.actor, book['id'], base)
    data, _ = export_pdf(service, rig.nid, rig.scope, rig.actor, book['id'],
                         {**base, 'pages': report['pages'], 'publication_digest': report['publication_digest']})
    # Optional owned proof artifacts for a separate cloud renderer check. These
    # contain only disposable fixtures; normal tests make no extra copies.
    import os
    from pathlib import Path
    proof_root = os.environ.get('COMIC_PDF_PROOF_DIRECTORY')
    if proof_root:
        from app.experimental.comic_publication import _render_page
        has_text = any(p['bubbles'] for row in pages for p in row['document']['panels'])
        proof = Path(proof_root) / ('cjk' if has_text else 'raster')
        proof.mkdir(parents=True, exist_ok=True)
        (proof / 'comic.pdf').write_bytes(data)
        for index, page in enumerate(pages):
            row = service._row(rig.nid, rig.scope, rig.actor, page['id'])
            (proof / f'{index + 1:04}.png').write_bytes(_render_page(service, rig.nid, rig.scope, rig.actor, row))
        source_root = Path(__file__).resolve().parents[1]
        proof_receipt = {'preflight': report, 'sha256': hashlib.sha256(data).hexdigest(),
            'fixture_only': True, 'independent_viewer_acceptance': False,
            'source_sha256': {name: hashlib.sha256((source_root / name).read_bytes()).hexdigest()
                for name in ('app/pdf_export.py', 'app/experimental/comic_publication.py',
                             'app/experimental/comic_publication_budget.py', 'app/experimental/comic_layouts_api.py')}}
        (proof / 'receipt.json').write_text(json.dumps(proof_receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    return PdfReader(io.BytesIO(data), strict=True)


def test_reviewed_raster_visibility_and_opacity_survive_pdf(rig, staging):
    row = prepare(rig, staging); stage(rig, staging, row)
    target = page(rig, staging); review = reviewed(rig, staging, row)
    attached = attach(rig, staging, review, target)['page']; service = staging.comic
    visible = approved(service, rig, attached)
    document = copy.deepcopy(visible['document']); document['layer_stack']['items'][0]['visible'] = False
    hidden = approved(service, rig, service.save(rig.nid, rig.scope, rig.actor, document))
    reader = layer_pdf(service, rig, [visible, hidden])
    assert reader.pages[0].images[0].image.getpixel((10, 20)) == (255, 127, 127)
    assert reader.pages[1].images[0].image.getpixel((10, 20)) == (255, 255, 255)


def test_cjk_bubbles_flatten_to_original_exact_pixels(rig, staging, monkeypatch):
    import os
    from app.experimental.comic_layouts import licensed_font
    from app.experimental.comic_publication import _render_page
    font = os.environ.get('R2_TEST_FONT_FILE')
    if font: monkeypatch.setenv('AI_NOVEL_STUDIO_PDF_FONT', font)
    try: licensed_font()
    except ValueError: pytest.skip('verified pinned OFL font required')
    service = staging.comic
    document = {'title': 'Text page', 'source_mode': 'INDEPENDENT', 'width': 640, 'height': 640,
        'panels': [{'id': 'p', 'order': 1, 'artwork_mode': 'BLANK', 'x': 24, 'y': 24, 'width': 592, 'height': 592,
                    'bubbles': [{'id': 'b', 'text': '原始对白', 'x': 40, 'y': 40, 'width': 500, 'height': 200}]}]}
    target = approved(service, rig, service.save(rig.nid, rig.scope, rig.actor, document))
    original = _render_page(service, rig.nid, rig.scope, rig.actor,
                            service._row(rig.nid, rig.scope, rig.actor, target['id']))
    reader = layer_pdf(service, rig, [target])
    assert not reader.pages[0].extract_text()
    image = reader.pages[0].images[0].image
    with Image.open(io.BytesIO(original)) as expected:
        assert image.size == expected.size and image.tobytes() == expected.tobytes()
    # Interior contains real rasterized glyphs, independently of the border.
    assert min(image.crop((60, 60, 520, 220)).convert('L').getdata()) < 100


@pytest.mark.parametrize('change', ['asset', 'privacy'])
def test_current_source_is_rechecked_after_pdf_serialization(mounted, monkeypatch, change):
    import app.pdf_export as pdf
    e = mounted; _, pages, book, path = setup_book(e, 2, with_image=True)
    body, _ = request(e, book, path); finish = pdf.RasterPDFCopy.finish
    def mutate(self):
        finish(self)
        if change == 'asset':
            aid = pages[0]['document']['panels'][0]['asset_id']
            e.assets.update_metadata(aid, {'parameters': {'private_marker': 'never echo'}})
        else:
            from app.source_privacy import review_source_privacy, content_digest
            review_source_privacy(e.chapter, None, 'local-author', 'CLOUD_ALLOWED', e.chapter['version'], content_digest(e.chapter), e.root)
    monkeypatch.setattr(pdf.RasterPDFCopy, 'finish', mutate)
    response = e.client.post(path + '/export-pdf', json=body)
    assert response.status_code in (409, 422), response.text
    assert not response.content.startswith(b'%PDF') and 'never echo' not in response.text

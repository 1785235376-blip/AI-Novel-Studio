"""Actual EPUB ZIP/XML/PNG structural tests, not EPUBCheck/reader acceptance."""
import copy
import hashlib
import io
import struct
import zipfile
import xml.etree.ElementTree as ET
import pytest
from PIL import Image
import test_comic_publication as cbz
from test_comic_publication import setup_book, publication_scope
from test_comic_independent import original_independent_owner
from test_r3_mounted_contracts import mounted, prefix, checked
from app.experimental import comic_publication_budget as budget
from app.experimental.comic_publication import export_epub

OPTIONS = {'format': 'comic-epub-fixed-raster-v1', 'language': 'und'}
NS = {'o': 'http://www.idpf.org/2007/opf', 'd': 'http://purl.org/dc/elements/1.1/',
      'x': 'http://www.w3.org/1999/xhtml', 'c': 'urn:oasis:names:tc:opendocument:xmlns:container'}


def request(e, book, path):
    body = {'expected_version': book['version'], 'reading_direction': 'RTL', **OPTIONS}
    report = checked(e.client.post(path + '/epub-publication-preflight', json=body))
    return {**body, 'pages': report['pages'], 'publication_digest': report['publication_digest']}, report


def test_actual_epub_structure_order_viewports_hashes_and_no_mutation(mounted):
    e = mounted; service, pages, book, path = setup_book(e, 6)
    document = copy.deepcopy(pages[2]['document']); document.update(width=400, height=720)
    page = service.save(e.nid, e.scope, 'local-author', document, rid=pages[2]['id'], expected_version=pages[2]['version'])
    report = service.preflight(e.nid, e.scope, 'local-author', page['id'], page['version'])
    service.approve(e.nid, e.scope, 'local-author', page['id'], page['version'], report['review_digest'], True)
    before = e.store.read(e.nid, e.scope)
    body, report = request(e, book, path)
    response = e.client.post(path + '/export-epub', json=body)
    assert response.status_code == 200, response.text
    assert response.headers['content-type'] == 'application/epub+zip'
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['x-comic-publication-digest'] == report['publication_digest']
    assert response.headers['x-content-sha256'] == hashlib.sha256(response.content).hexdigest()
    assert len(response.content) <= report['epub_limits']['reserved_output_bytes']
    assert 'EPUBCHECK_NOT_RUN' in report['losses']
    raw = response.content
    assert raw[:4] == b'PK\x03\x04' and struct.unpack_from('<H', raw, 8)[0] == 0
    filename_length, extra_length = struct.unpack_from('<HH', raw, 26)
    assert filename_length == 8 and extra_length == 0
    assert raw[30:58] == b'mimetypeapplication/epub+zip'
    original = zipfile.ZipFile(io.BytesIO(e.client.post(path + '/export-cbz', json=cbz.request(e, book, path)).content))
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        assert len(names) == len(set(names)) == 4 + 6 * 2
        assert names[0] == 'mimetype' and archive.read('mimetype') == b'application/epub+zip'
        assert archive.getinfo('mimetype').compress_type == zipfile.ZIP_STORED
        assert archive.testzip() is None
        assert all(not n.startswith('/') and '..' not in n.split('/') for n in names)
        container = ET.fromstring(archive.read('META-INF/container.xml'))
        assert container.find('c:rootfiles/c:rootfile', NS).attrib == {
            'full-path': 'EPUB/package.opf', 'media-type': 'application/oebps-package+xml'}
        opf = ET.fromstring(archive.read('EPUB/package.opf'))
        assert opf.attrib['version'] == '3.0'
        assert opf.find('o:metadata/d:language', NS).text == 'und'
        assert opf.find('o:metadata/d:creator', NS) is None
        meta = {x.attrib['property']: x.text for x in opf.findall('o:metadata/o:meta', NS)}
        assert meta['rendition:layout'] == 'pre-paginated' and meta['rendition:spread'] == 'none'
        assert meta['dcterms:modified'].endswith('Z')
        manifest = {x.attrib['id']: x.attrib for x in opf.findall('o:manifest/o:item', NS)}
        assert len(manifest) == 13 and manifest['nav']['properties'] == 'nav'
        assert {'EPUB/' + v['href'] for v in manifest.values()} == set(names) - {'mimetype', 'META-INF/container.xml', 'EPUB/package.opf'}
        spine = opf.find('o:spine', NS)
        assert spine.attrib['page-progression-direction'] == 'rtl'
        assert [x.attrib['idref'] for x in spine] == [f'page-{i:04}' for i in range(1, 7)]
        nav = ET.fromstring(archive.read('EPUB/nav.xhtml'))
        assert [x.attrib['href'] for x in nav.findall('.//x:a', NS)] == [f'pages/{i:04}.xhtml' for i in range(1, 7)]
        for i in range(1, 7):
            width, height = (400, 720) if i == 3 else (320, 640)
            document = ET.fromstring(archive.read(f'EPUB/pages/{i:04}.xhtml'))
            assert document.find('x:head/x:meta', NS).attrib == {'name': 'viewport', 'content': f'width={width}, height={height}'}
            image = document.find('x:body/x:img', NS)
            assert image.attrib['src'] == f'../images/{i:04}.png'
            png = archive.read(f'EPUB/images/{i:04}.png')
            assert hashlib.sha256(png).digest() == hashlib.sha256(original.read(f'{i:04}.png')).digest()
            with Image.open(io.BytesIO(png)) as raster:
                assert raster.size == (width, height) and raster.mode == 'RGB'
            assert report['page_dimensions'][i-1] == {'width_pixels': width, 'height_pixels': height}
        xml = b''.join(archive.read(n) for n in names if n.endswith(('.opf', '.xml', '.xhtml')))
        assert not any(s.encode() in xml for s in ('local-author', 'project_incarnation', 'asset_sources', 'source_evidence', e.nid, book['id']))
        assert b'<script' not in xml and b'<form' not in xml
    assert before == e.store.read(e.nid, e.scope)


def test_titles_are_text_not_html(mounted):
    e = mounted; service, pages, book, path = setup_book(e, 1)
    title = '<script src="https://evil.example/x">& 😺 中文</script>'
    doc = copy.deepcopy(pages[0]['document']); doc['title'] = title
    row = service.save(e.nid, e.scope, 'local-author', doc, rid=pages[0]['id'], expected_version=pages[0]['version'])
    report = service.preflight(e.nid, e.scope, 'local-author', row['id'], row['version'])
    row = service.approve(e.nid, e.scope, 'local-author', row['id'], row['version'], report['review_digest'], True)
    book = service.save_book(e.nid, e.scope, 'local-author', {'title': title, 'chapters': book['chapters'],
        'expected_page_versions': {row['id']: row['version']}}, rid=book['id'], expected_version=book['version'])
    body, _ = request(e, book, path)
    response = e.client.post(path + '/export-epub', json=body)
    assert response.status_code == 200, response.text
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        opf = ET.fromstring(archive.read('EPUB/package.opf'))
        assert opf.find('o:metadata/d:title', NS).text == title
        for name in archive.namelist():
            if not name.endswith(('.xhtml', '.opf', '.xml')): continue
            root = ET.fromstring(archive.read(name))
            assert not any(x.tag.rsplit('}', 1)[-1] in ('script', 'iframe', 'form', 'object') for x in root.iter())
            assert not any(v.startswith(('http:', 'https:', 'data:', 'javascript:')) for x in root.iter() for k, v in x.attrib.items() if k in ('href', 'src'))


@pytest.mark.parametrize('title', ['bad\x00title', 'bad\x01title', 'bad\ufffetitle', 'bad\ud800title'])
def test_illegal_xml_metadata_before_allocation(title):
    from app.experimental.comic_epub_package import admit
    with pytest.raises(ValueError, match='XML_CHARACTER_INVALID'):
        admit({'document': {'title': title}}, [{'document': {'title': 'Page', 'width': 320, 'height': 640}}], 67108864)


@pytest.mark.parametrize('change', [{'language': 'en'}, {'language': None}, {'format': 'comic-cbz-v1'}, {'author': 'invented'}, {'isbn': 'invented'}])
def test_explicit_safe_options(mounted, change):
    e = mounted; _, _, book, path = setup_book(e, 1)
    response = e.client.post(path + '/epub-publication-preflight', json={'expected_version': book['version'], 'reading_direction': 'LTR', **OPTIONS, **change})
    assert response.status_code == 422


def test_required_options_and_format_binding(mounted):
    e = mounted; _, _, book, path = setup_book(e, 1)
    old = cbz.request(e, book, path)
    body, report = request(e, book, path)
    assert old['publication_digest'] != report['publication_digest']
    assert e.client.post(path + '/export-epub', json={**old, **OPTIONS}).status_code == 409
    assert e.client.post(path + '/export-cbz', json=body).status_code == 422
    for key in OPTIONS:
        altered = {k: v for k, v in body.items() if k != key}
        assert e.client.post(path + '/export-epub', json=altered).status_code == 422


@pytest.mark.parametrize('kind', ['metadata', 'xml', 'output', 'decode', 'render', 'encoded', 'source'])
def test_whole_request_budgets(mounted, monkeypatch, kind):
    import app.experimental.comic_epub_package as package
    import app.experimental.comic_publication as publication
    e = mounted; _, _, book, path = setup_book(e, 2, with_image=True); body, _ = request(e, book, path)
    if kind in ('metadata', 'xml', 'output'):
        def forbidden(*args, **kwargs): raise AssertionError('Package allocation before admission')
        monkeypatch.setattr(package.Package, '__init__', forbidden)
        if kind == 'output': monkeypatch.setattr(publication, 'MAX_ARCHIVE_BYTES', 1)
        else: monkeypatch.setattr(package, 'MAX_METADATA_BYTES' if kind == 'metadata' else 'MAX_XML_BYTES', 1)
    else:
        monkeypatch.setattr(budget, {'decode': 'MAX_DECODE_PIXELS', 'render': 'MAX_RENDER_PIXELS', 'encoded': 'MAX_BUFFER_WRITE_BYTES', 'source': 'MAX_SOURCE_BYTES'}[kind], 1)
    response = e.client.post(path + '/export-epub', json=body)
    assert response.status_code == 422, response.text
    assert not response.content.startswith(b'PK')


def test_cumulative_navigation_metadata_before_allocation(monkeypatch):
    from app.experimental import comic_epub_package as package
    rows = [{'document': {'title': '&' * 200, 'width': 320, 'height': 640}}] * 50
    # Each title fits alone, but complete nav must be admitted as one XML doc.
    with pytest.raises(ValueError, match='METADATA_LIMIT'):
        package.admit({'document': {'title': 'Book'}}, rows, 67108864)


def epub_routes(e, monkeypatch):
    post = e.client.post
    def epub_post(url, **kwargs):
        if url.endswith(('/publication-preflight', '/export-cbz')):
            url = url.removesuffix('/publication-preflight') + '/epub-publication-preflight' if url.endswith('/publication-preflight') else url.removesuffix('/export-cbz') + '/export-epub'
            kwargs['json'] = {**kwargs['json'], **OPTIONS}
        response = post(url, **kwargs)
        if response.status_code != 200: assert not response.content.startswith(b'PK')
        return response
    monkeypatch.setattr(e.client, 'post', epub_post)


@pytest.mark.parametrize('change', ['page_pin', 'digest', 'missing', 'extra', 'order', 'book_version', 'direction'])
def test_exact_epub_pins(mounted, monkeypatch, change):
    epub_routes(mounted, monkeypatch); cbz.test_exact_export_pins(mounted, change)


@pytest.mark.parametrize('change', ['page', 'book', 'approval'])
def test_global_final_recheck(mounted, monkeypatch, change):
    epub_routes(mounted, monkeypatch); cbz.test_global_final_recheck_first_page_after_render(mounted, monkeypatch, change)


@pytest.mark.parametrize('change', ['asset', 'privacy', 'decode', 'source'])
def test_current_sources(mounted, monkeypatch, change):
    epub_routes(mounted, monkeypatch); cbz.test_actual_source_pins_and_decode_budget(mounted, monkeypatch, change)


@pytest.mark.parametrize('change', ['draft', 'webtoon', 'owner', 'actor', 'scope'])
def test_current_owner(mounted, monkeypatch, change):
    epub_routes(mounted, monkeypatch); cbz.test_unapproved_or_foreign_page_fail_closed(mounted, change)


def test_real_scope_and_revocation(publication_scope, monkeypatch):
    epub_routes(publication_scope, monkeypatch); cbz.test_real_session_scope_and_mid_render_revocation(publication_scope, monkeypatch)


@pytest.mark.parametrize('change', ['authority', 'asset', 'privacy'])
def test_final_recheck_after_zip_close(mounted, monkeypatch, change):
    from app.experimental import comic_epub_package as package
    e = mounted; service, pages, book, path = setup_book(e, 2, with_image=True)
    body, _ = request(e, book, path); finish = package.Package.finish; revoked = False
    def mutate(self):
        nonlocal revoked
        finish(self); revoked = True
        if change == 'asset':
            aid = pages[0]['document']['panels'][0]['asset_id']
            e.assets.update_metadata(aid, {'parameters': {'private_marker': 'never echo'}})
        elif change == 'privacy':
            from app.source_privacy import review_source_privacy, content_digest
            review_source_privacy(e.chapter, None, 'local-author', 'CLOUD_ALLOWED', e.chapter['version'], content_digest(e.chapter), e.root)
    monkeypatch.setattr(package.Package, 'finish', mutate)
    if change == 'authority':
        def guard():
            if revoked: raise PermissionError('revoked')
        with pytest.raises(PermissionError):
            export_epub(service, e.nid, e.scope, 'local-author', book['id'], body, guard)
    else:
        response = e.client.post(path + '/export-epub', json=body)
        assert response.status_code in (409, 422), response.text
        assert not response.content.startswith(b'PK') and 'never echo' not in response.text


from test_v2_independent_workspace import rig
from test_comic_ora_staging import staging, prepare, stage
from test_comic_ora_review_attach import reviewed, page, attach
from test_comic_publication_layers import approved


def layer_epub(service, rig, pages):
    from app.experimental.comic_publication import epub_publication_preflight, _render_page
    book = service.save_book(rig.nid, rig.scope, rig.actor, {'title': 'Raster layers', 'chapters': [
        {'id': 'c', 'title': 'Pages', 'pages': [p['id'] for p in pages]}],
        'expected_page_versions': {p['id']: p['version'] for p in pages}})
    base = {'expected_version': book['version'], 'reading_direction': 'LTR', **OPTIONS}
    report = epub_publication_preflight(service, rig.nid, rig.scope, rig.actor, book['id'], base)
    data, _ = export_epub(service, rig.nid, rig.scope, rig.actor, book['id'],
        {**base, 'pages': report['pages'], 'publication_digest': report['publication_digest']})
    images = []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        opf = ET.fromstring(archive.read('EPUB/package.opf'))
        assert opf.find('o:spine', NS).attrib['page-progression-direction'] == 'ltr'
        for i, page in enumerate(pages, 1):
            png = archive.read(f'EPUB/images/{i:04}.png')
            row = service._row(rig.nid, rig.scope, rig.actor, page['id'])
            assert png == _render_page(service, rig.nid, rig.scope, rig.actor, row)
            with Image.open(io.BytesIO(png)) as image:
                images.append(image.copy())
    return images


def test_reviewed_layers_remain_original_raster_pixels(rig, staging):
    row = prepare(rig, staging); stage(rig, staging, row)
    target = page(rig, staging); review = reviewed(rig, staging, row)
    attached = attach(rig, staging, review, target)['page']; service = staging.comic
    visible = approved(service, rig, attached)
    document = copy.deepcopy(visible['document']); document['layer_stack']['items'][0]['visible'] = False
    hidden = approved(service, rig, service.save(rig.nid, rig.scope, rig.actor, document))
    images = layer_epub(service, rig, [visible, hidden])
    assert images[0].getpixel((10, 20)) == (255, 127, 127)
    assert images[1].getpixel((10, 20)) == (255, 255, 255)


def test_cjk_bubbles_are_original_pixels_not_searchable_text(rig, staging, monkeypatch):
    import os
    from app.experimental.comic_layouts import licensed_font
    font = os.environ.get('R2_TEST_FONT_FILE')
    if font: monkeypatch.setenv('AI_NOVEL_STUDIO_PDF_FONT', font)
    try: licensed_font()
    except ValueError: pytest.skip('verified pinned OFL font required')
    service = staging.comic
    document = {'title': 'Text page', 'source_mode': 'INDEPENDENT', 'width': 640, 'height': 640,
        'panels': [{'id': 'p', 'order': 1, 'artwork_mode': 'BLANK', 'x': 24, 'y': 24, 'width': 592, 'height': 592,
            'bubbles': [{'id': 'b', 'text': '原始对白', 'x': 40, 'y': 40, 'width': 500, 'height': 200}]}]}
    target = approved(service, rig, service.save(rig.nid, rig.scope, rig.actor, document))
    images = layer_epub(service, rig, [target])
    assert min(images[0].crop((60, 60, 520, 220)).convert('L').getdata()) < 100


@pytest.mark.parametrize('title', ['', ' ', '\t\r\n'])
def test_empty_xhtml_titles_rejected(title):
    from app.experimental.comic_epub_package import admit
    with pytest.raises(ValueError, match='TITLE_REQUIRED'):
        admit({'document': {'title': 'Book'}}, [{'document': {'title': title, 'width': 320, 'height': 640}}], 67108864)

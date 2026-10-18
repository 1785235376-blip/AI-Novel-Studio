"""Real mounted CBZ bytes; file and opt-in actual PostgreSQL contracts.

ZIP/Pillow verification is NOT independent reader acceptance.
"""
import copy
import hashlib
import io
import json
import zipfile
import pytest
from PIL import Image
from test_comic_independent import original_independent_owner, blank
from test_r3_mounted_contracts import mounted, prefix, checked
from app.experimental.comic_publication import export_cbz, publication_preflight, BoundedBuffer
from app.experimental import comic_publication_budget as budget


def setup_book(e, count=6, with_image=False, actor='local-author'):
    service = e.experimental.comic_layouts_service
    pages = []
    asset = None
    if with_image:
        import base64
        from test_r5_comic_layouts import synthetic_png
        asset = e.assets.create(e.nid, 'synthetic.png', base64.b64encode(synthetic_png()).decode(), 'image/png')
        asset = e.experimental.production_lineage_service.annotate(e.nid, e.scope, actor, asset['id'], {'expected_version': asset['version'], 'origin': 'ORIGINAL_INPUT', 'chapter_ids': [e.chapter['id']]})
        asset = service.approve_image(e.nid, e.scope, actor, asset['id'], asset['version'])
    for i in range(count):
        body = {**blank(), 'width': 320, 'height': 640, 'segment_height': 320,
                'panels': [{'id': 'p', 'order': 1, 'artwork_mode': 'BLANK',
                            'x': 24 + i, 'y': 24, 'width': 240, 'height': 580, 'bubbles': []}]}
        if asset:
            body['panels'][0].update(artwork_mode='IMAGE', asset_id=asset['id'], expected_asset_version=asset['version'])
        page = service.save(e.nid, e.scope, actor, body)
        report = service.preflight(e.nid, e.scope, actor, page['id'], page['version'])
        page = service.approve(e.nid, e.scope, actor, page['id'], page['version'], report['review_digest'], True)
        pages.append(page)
    book = service.save_book(e.nid, e.scope, actor, {
        'title': 'Public title', 'chapters': [
            {'id': 'b', 'title': 'Same title', 'pages': [p['id'] for p in pages[:3]]},
            {'id': 'a', 'title': 'Same title', 'pages': [p['id'] for p in pages[3:]]}],
        'expected_page_versions': {p['id']: p['version'] for p in pages}})
    path = e.base + '/comic-layouts/books/' + book['id']
    return service, pages, book, path


def request(e, book, path):
    body = {'expected_version': book['version'], 'reading_direction': 'RTL'}
    receipt = checked(e.client.post(path + '/publication-preflight', json=body))
    return {**body, 'pages': receipt['pages'], 'publication_digest': receipt['publication_digest']}


def test_six_full_pages_order_checksum_and_no_mutation(mounted):
    e = mounted; service, pages, book, path = setup_book(e)
    before = e.store.read(e.nid, e.scope)
    body = request(e, book, path)
    response = e.client.post(path + '/export-cbz', json=body)
    assert response.status_code == 200, response.text
    assert response.headers['content-type'] == 'application/vnd.comicbook+zip'
    assert response.headers['x-content-sha256'] == hashlib.sha256(response.content).hexdigest()
    assert response.headers['x-comic-publication-digest'] == body['publication_digest']
    assert response.headers['cache-control'] == 'no-store'
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert archive.namelist() == [f'{i:04}.png' for i in range(1, 7)] + ['manifest.json']
        assert archive.testzip() is None
        manifest = json.loads(archive.read('manifest.json'))
        assert manifest['reading_direction'] == 'RTL'
        for i, item in enumerate(manifest['pages']):
            data = archive.read(item['filename'])
            assert item['sha256'] == hashlib.sha256(data).hexdigest()
            with Image.open(io.BytesIO(data)) as image:
                assert image.size == (320, 640)
                assert image.getpixel((24 + i, 24)) == (0, 0, 0)
                assert image.getpixel((24 + i, 603)) == (0, 0, 0)
        assert not any(key in json.dumps(manifest) for key in ('asset_sources', 'source_evidence', 'project_incarnation', 'local-author'))
        assert 'EXTERNAL_READER_VALIDATION_NOT_RUN' in manifest['losses']
    assert before == e.store.read(e.nid, e.scope)


@pytest.mark.parametrize('change', ['page_pin', 'digest', 'missing', 'extra', 'order', 'book_version', 'direction'])
def test_exact_export_pins(mounted, change):
    e = mounted; _, _, book, path = setup_book(e, 2); body = request(e, book, path)
    if change == 'page_pin': body['pages'][0]['version'] += 1
    elif change == 'digest': body['pages'][0]['review_digest'] = '0' * 64
    elif change == 'missing': body['pages'].pop()
    elif change == 'extra': body['pages'].append(body['pages'][0])
    elif change == 'order': body['pages'].reverse()
    elif change == 'book_version': body['expected_version'] += 1
    else: body['reading_direction'] = 'LTR'
    response = e.client.post(path + '/export-cbz', json=body)
    assert response.status_code == 409, response.text
    assert response.headers['cache-control'] == 'no-store'
    assert 'Public title' not in response.text


@pytest.mark.parametrize('change', ['page', 'book', 'approval'])
def test_global_final_recheck_first_page_after_render(mounted, monkeypatch, change):
    e = mounted; service, pages, book, path = setup_book(e, 2); body = request(e, book, path)
    import app.experimental.comic_publication as module
    original = module._full_page; calls = 0
    def race(*args):
        nonlocal calls
        data = original(*args); calls += 1
        if calls == 2:
            if change == 'book':
                document = {k: copy.deepcopy(book[k]) for k in ('title', 'chapters')}
                document['chapters'][0]['pages'].reverse()
                service.save_book(e.nid, e.scope, 'local-author', {**document, 'expected_page_versions': {p['id']: p['version'] for p in pages}}, rid=book['id'], expected_version=book['version'])
            else:
                with service._independent_transaction(e.nid, e.scope) as state:
                    row = state['collections'][service.RECORDS][pages[0]['id']]
                    if change == 'approval': row['approval']['digest'] = '0' * 64
                    else: row['version'] += 1
        return data
    monkeypatch.setattr(module, '_full_page', race)
    response = e.client.post(path + '/export-cbz', json=body)
    assert response.status_code in (409, 422), response.text
    assert not response.content.startswith(b'PK')


@pytest.mark.parametrize('kind', ['page', 'render', 'source', 'decode', 'archive'])
def test_whole_request_budgets(mounted, monkeypatch, kind):
    e = mounted; _, _, book, path = setup_book(e, 2); body = request(e, book, path)
    import app.experimental.comic_publication as module
    if kind == 'page': monkeypatch.setattr(module, 'MAX_PAGE_PIXELS', 100)
    elif kind == 'archive': monkeypatch.setattr(module, 'MAX_ARCHIVE_BYTES', 200)
    elif kind in ('source', 'decode'):
        # Decode/source accounting is shared by original _image, including legacy pages.
        with budget.publication_budget():
            budget._remaining.get()[kind] = 1
            with pytest.raises(ValueError, match='_LIMIT'):
                budget.source_work(2, 2)
        return
    else: monkeypatch.setattr(budget, 'MAX_RENDER_PIXELS', 100)
    response = e.client.post(path + '/export-cbz', json=body)
    assert response.status_code == 422, response.text
    assert not response.content.startswith(b'PK')


def test_missing_book_read_does_not_create_owner(mounted):
    e = mounted; before = e.store.read(e.nid, e.scope)
    response = e.client.post(e.base + '/comic-layouts/books/missing/publication-preflight', json={'expected_version': 1, 'reading_direction': 'LTR'})
    assert response.status_code == 404
    assert before == e.store.read(e.nid, e.scope)


@pytest.mark.parametrize('change', ['asset', 'privacy', 'decode', 'source'])
def test_actual_source_pins_and_decode_budget(mounted, monkeypatch, change):
    e = mounted; service, pages, book, path = setup_book(e, 2, with_image=True)
    body = request(e, book, path)
    if change == 'asset':
        aid = pages[0]['document']['panels'][0]['asset_id']
        e.assets.update_metadata(aid, {'parameters': {'private_marker': 'never echo'}})
    elif change == 'privacy':
        from app.source_privacy import review_source_privacy, content_digest
        review_source_privacy(e.chapter, None, 'local-author', 'CLOUD_ALLOWED', e.chapter['version'], content_digest(e.chapter), e.root)
    elif change == 'decode': monkeypatch.setattr(budget, 'MAX_DECODE_PIXELS', 1)
    else: monkeypatch.setattr(budget, 'MAX_SOURCE_BYTES', 1)
    response = e.client.post(path + '/export-cbz', json=body)
    assert response.status_code in (409, 422), response.text
    assert 'never echo' not in response.text and not response.content.startswith(b'PK')


@pytest.mark.parametrize('change', ['draft', 'webtoon', 'owner', 'actor', 'scope'])
def test_unapproved_or_foreign_page_fail_closed(mounted, change):
    e = mounted; service, pages, book, path = setup_book(e, 1)
    body = request(e, book, path)
    with service._independent_transaction(e.nid, e.scope) as state:
        row = state['collections'][service.RECORDS][pages[0]['id']]
        if change == 'draft': row['status'] = 'DRAFT'
        elif change == 'webtoon': row['document']['preset'] = 'WEBTOON'
        elif change == 'owner': row['project_incarnation'] = 'retired-owner'
        elif change == 'actor': row['created_by'] = 'foreign-author'
        else: row['scope'] = {'mode': 'foreign'}
    response = e.client.post(path + '/export-cbz', json=body)
    assert response.status_code in (404, 409, 422), response.text
    assert 'Public title' not in response.text and not response.content.startswith(b'PK')


def test_guard_revoked_after_archive_before_bytes(mounted):
    e = mounted; service, _, book, path = setup_book(e, 2); body = request(e, book, path)
    calls = 0
    def guard():
        nonlocal calls
        calls += 1
        if calls >= 8: raise PermissionError('revoked')
    with pytest.raises(PermissionError):
        export_cbz(service, e.nid, e.scope, 'local-author', book['id'], body, guard)


def test_original_image_budget_is_inert_outside_export():
    from app.experimental.comic_layouts import _image
    from test_r5_comic_layouts import synthetic_png
    data = synthetic_png()
    image = _image(data); image.close()
    with budget.publication_budget():
        budget._remaining.get()['source'] = 1
        with pytest.raises(ValueError, match='PUBLICATION_SOURCE_LIMIT'): _image(data)
    image = _image(data); image.close()


@pytest.fixture
def publication_scope(mounted, monkeypatch):
    from test_r3_mounted_contracts import scoped
    e = scoped(mounted, monkeypatch)
    monkeypatch.setattr(e.api, 'authorization_service', e.authorization)
    yield e
    if e.backend == 'postgres':
        with e.store._connect() as connection:
            for table in ('domain_role_assignments', 'permission_assignments', 'authorization_audit_events'):
                connection.execute(f"DELETE FROM {table} WHERE payload->'scope'->>'workspace_id'=%s", (e.workspace,))
            connection.execute('DELETE FROM workspace_memberships WHERE workspace_id=%s AND user_id IN (%s,%s)', (e.workspace, e.lead, e.viewer))
            for table in ('storyline_branches', 'storylines'):
                connection.execute(f"DELETE FROM {table} WHERE payload->>'workspace_id'=%s AND payload->>'project_id'=%s", (e.workspace, e.nid))
            connection.execute('DELETE FROM project_workspaces WHERE project_id=%s AND workspace_id=%s', (e.nid, e.workspace))
            connection.execute("UPDATE novels SET workspace_id='default-workspace' WHERE slug=%s AND workspace_id=%s", (e.nid, e.workspace))
            connection.execute('DELETE FROM workspaces WHERE id=%s', (e.workspace,))
            connection.execute('DELETE FROM users WHERE id IN (%s,%s)', (e.lead, e.viewer))


def test_real_session_scope_and_mid_render_revocation(publication_scope, monkeypatch):
    e = publication_scope; _, _, book, path = setup_book(e, 2, actor=e.lead)
    body = {'expected_version': book['version'], 'reading_direction': 'LTR'}
    for headers in ({}, e.viewer_headers, {**e.headers, 'X-Branch-ID': e.other_branch}):
        denied = e.client.post(path + '/publication-preflight', json=body, headers=headers)
        assert denied.status_code in (401, 403, 404)
        assert 'Public title' not in denied.text
    preflight = checked(e.client.post(path + '/publication-preflight', json=body, headers=e.headers))
    body.update(pages=preflight['pages'], publication_digest=preflight['publication_digest'])
    import app.experimental.comic_publication as module
    original = module._full_page
    def revoke(*args):
        data = original(*args)
        e.sessions.revoke(e.lead)
        return data
    monkeypatch.setattr(module, '_full_page', revoke)
    denied = e.client.post(path + '/export-cbz', json=body, headers=e.headers)
    assert denied.status_code in (401, 403)
    assert not denied.content.startswith(b'PK') and 'Public title' not in denied.text


def test_source_budget_rejects_before_asset_read(mounted, monkeypatch):
    e = mounted; _, _, book, path = setup_book(e, 1, with_image=True); body = request(e, book, path)
    monkeypatch.setattr(budget, 'MAX_SOURCE_BYTES', 1)
    def forbidden(*args, **kwargs): raise AssertionError('source read exceeded request admission')
    monkeypatch.setattr(e.assets, 'content', forbidden)
    response = e.client.post(path + '/export-cbz', json=body)
    assert response.status_code == 422 and 'PUBLICATION_SOURCE_LIMIT' in response.text


def test_intermediate_segment_encoder_sink_is_bounded(mounted, monkeypatch):
    e = mounted; _, _, book, path = setup_book(e, 1); body = request(e, book, path)
    import app.experimental.comic_publication as publication
    monkeypatch.setattr(budget, 'MAX_ARCHIVE_BYTES', 20)
    def forbidden(*args): raise AssertionError('segment encoder should fail before stitching')
    monkeypatch.setattr(publication, '_full_page', forbidden)
    response = e.client.post(path + '/export-cbz', json=body)
    assert response.status_code == 422 and 'PUBLICATION_ARCHIVE_LIMIT' in response.text


def test_cumulative_encoder_write_limit(mounted, monkeypatch):
    e = mounted; _, _, book, path = setup_book(e, 2); body = request(e, book, path)
    monkeypatch.setattr(budget, 'MAX_BUFFER_WRITE_BYTES', 20)
    response = e.client.post(path + '/export-cbz', json=body)
    assert response.status_code == 422 and 'PUBLICATION_ENCODED_LIMIT' in response.text

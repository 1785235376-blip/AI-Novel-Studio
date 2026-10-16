"""EPUB uses the existing saved Creative owner, API and fresh-read fences."""
import copy
import hashlib
import io
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
from test_v2_creative_foundation import rig, client, payload, public
from test_v2_screenplay_export import independent


def content(data):
    with ZipFile(io.BytesIO(data)) as archive:
        assert archive.testzip() is None
        assert archive.namelist()[0] == 'mimetype'
        assert archive.getinfo('mimetype').compress_type == 0
        assert archive.read('mimetype') == b'application/epub+zip'
        return '\n'.join(ET.fromstring(archive.read('OEBPS/content.xhtml')).itertext())


@pytest.mark.parametrize('standalone', [True, False])
def test_saved_reopened_screenplay_epub_is_readonly_and_version_bound(rig, standalone):
    from app.creative.service import CreativeService, document_digest
    from app.services.v1_capability_service import CapabilityVersionConflict
    row = rig.service.create(rig.nid, rig.scope, rig.actor, independent(rig) if standalone else payload(rig))
    changed = public(row); changed['title'] = '已保存第二稿'
    row = rig.service.update(rig.nid, rig.scope, rig.actor, row['id'], 1, changed)
    before = copy.deepcopy(rig.store.read(rig.nid, rig.scope)); chapters = copy.deepcopy(rig.chapters.list(rig.nid))
    reopened = CreativeService(rig.store, rig.novels, rig.chapters)
    with pytest.raises(CapabilityVersionConflict):
        reopened.export_screenplay(rig.nid, rig.scope, row['id'], 1, 'epub')
    result = reopened.export_screenplay(rig.nid, rig.scope, row['id'], 2, 'epub')
    text = content(result['content'])
    assert row['title'] in text and row['scenes'][0]['action'] in text
    assert row['id'] in text and document_digest(row) in text
    assert result['media_type'] == 'application/epub+zip' and result['filename'].endswith('-v2.epub')
    assert result['document_version'] == 2 and result['sha256'] == hashlib.sha256(result['content']).hexdigest()
    assert rig.store.read(rig.nid, rig.scope) == before and rig.chapters.list(rig.nid) == chapters
    assert reopened.export(rig.nid, rig.scope, row['id'])['document']['scenes'] == row['scenes']


@pytest.mark.parametrize('change', ['document', 'chapter', 'permission', 'archive', 'privacy'])
def test_epub_postencode_rechecks_original_authority_and_snapshot(rig, monkeypatch, change):
    from app.creative import screenplay_export
    from app.experimental.common import StaleSourceError
    from app.services.v1_capability_service import CapabilityVersionConflict
    row = rig.service.create(rig.nid, rig.scope, rig.actor, payload(rig))
    original = screenplay_export.render
    revoked = False
    def guard():
        if revoked: raise PermissionError('revoked')
    def render(*args):
        nonlocal revoked
        result = original(*args); assert result['format'] == 'epub'; content(result['content'])
        if change == 'document':
            changed = public(row); changed['title'] = 'Changed by another writer'
            rig.service.update(rig.nid, rig.scope, rig.actor, row['id'], 1, changed)
        elif change == 'chapter': rig.chapters.save(rig.chapter['id'], {'content':'Changed', 'version':rig.chapter['version']})
        elif change == 'privacy':
            from app.source_privacy import content_digest, review_source_privacy
            review_source_privacy(rig.chapter, None, 'reviewer', 'CLOUD_ALLOWED', rig.chapter['version'], content_digest(rig.chapter), root=rig.root)
        elif change == 'archive': rig.service.archive(rig.nid, rig.scope, rig.actor, row['id'], 1)
        else: revoked = True
        return result
    monkeypatch.setattr(screenplay_export, 'render', render)
    expected = {'document':CapabilityVersionConflict, 'chapter':StaleSourceError, 'permission':PermissionError,
                'archive':FileNotFoundError, 'privacy':StaleSourceError}[change]
    with pytest.raises(expected):
        rig.service.export_screenplay(rig.nid, rig.scope, row['id'], 1, 'epub', reauthorize=guard)


def test_epub_api_returns_exact_private_binary_receipt_and_original_failures(rig, client):
    row = rig.service.create(rig.nid, rig.scope, rig.actor, independent(rig))
    url = f'/api/novels/{rig.nid}/experimental/creative/documents/{row["id"]}/screenplay-export'
    query = {'format':'epub','expected_version':1}
    response = client.get(url, params=query, headers={'X-Session-Token':'reader'})
    assert response.status_code == 200, response.text[:200]
    assert response.headers['Content-Type'] == 'application/epub+zip'
    assert response.headers['Cache-Control'] == 'no-store' and response.headers['X-Content-Type-Options'] == 'nosniff'
    assert response.headers['X-Creative-Document-Version'] == '1'
    assert response.headers['X-Content-SHA256'] == hashlib.sha256(response.content).hexdigest()
    assert row['id'] in response.headers['Content-Disposition'] and '风穿过空荡的码头。' in content(response.content)
    assert client.get(url, params=query).status_code == 401
    assert client.get(url, params=query, headers={'X-Session-Token':'owner','X-Branch-Id':'foreign'}).status_code == 404
    assert client.get(url, params={**query,'expected_version':2}, headers={'X-Session-Token':'reader'}).status_code == 409
    assert client.get(url, params={**query,'format':'pdf'}, headers={'X-Session-Token':'reader'}).status_code == 422
    assert rig.service.get(rig.nid, rig.scope, row['id']) == row


@pytest.mark.parametrize('v1', [False, True])
def test_epub_respects_default_off_and_v1_gate(rig, client, monkeypatch, v1):
    row = rig.service.create(rig.nid, rig.scope, rig.actor, independent(rig))
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2' if v1 else '')
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true' if v1 else 'false')
    response = client.get(f'/api/novels/{rig.nid}/experimental/creative/documents/{row["id"]}/screenplay-export',
        params={'format':'epub','expected_version':1}, headers={'X-Session-Token':'owner'})
    assert response.status_code == 404 and response.json()['detail']['code'] == 'EXPERIMENTAL_FEATURE_DISABLED'


def test_both_mounted_aliases_declare_epub_and_still_exclude_pdf():
    from app.main import app
    paths = app.openapi()['paths']
    for prefix in ('/api','/api/v1'):
        route = paths[prefix+'/novels/{nid}/experimental/creative/documents/{rid}/screenplay-export']['get']
        formats = next(p['schema']['enum'] for p in route['parameters'] if p['name']=='format')
        assert formats == ['fountain','docx','markdown','epub']


def test_invalid_xml_text_fails_api_without_download_or_document_change(rig, client):
    value = independent(rig)
    value['scenes'][0]['action'] = 'Before\x0bafter'
    row = rig.service.create(rig.nid, rig.scope, rig.actor, value)
    before = copy.deepcopy(rig.store.read(rig.nid, rig.scope))
    response = client.get(f'/api/novels/{rig.nid}/experimental/creative/documents/{row["id"]}/screenplay-export',
        params={'format':'epub','expected_version':1}, headers={'X-Session-Token':'reader'})
    assert response.status_code == 422
    assert response.headers['Content-Type'].startswith('application/json')
    assert 'Content-Disposition' not in response.headers and not response.content.startswith(b'PK')
    assert rig.store.read(rig.nid, rig.scope) == before

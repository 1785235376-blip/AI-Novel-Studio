"""Creative-owned screenplay exports using real File/PostgreSQL and old encoders."""
import copy
import hashlib
import io
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
from test_v2_creative_foundation import rig, client, payload, public


def independent(e):
    value = payload(e)
    value.update(source_independent=True, source_chapter_ids=[])
    value['scenes'][0].update(source_chapter_id=None, heading='EXT. 港口 - NIGHT',
        action='风穿过空荡的码头。\n原有动作。', emotion='克制', location='旧港码头', time='午夜之后',
        dialogue=[{'speaker':'旅人','text':'别忘记这座城。','delivery':'轻声'}])
    return value


def exported_text(result):
    if result['format'] != 'docx': return result['content'].decode('utf-8')
    with ZipFile(io.BytesIO(result['content'])) as archive:
        assert archive.testzip() is None
        assert not any('vba' in name.lower() for name in archive.namelist())
        root = ET.fromstring(archive.read('word/document.xml'))
        return '\n'.join(root.itertext())


@pytest.mark.parametrize('format', ['fountain', 'docx', 'markdown'])
def test_independent_saved_screenplay_reopens_exports_without_other_owner_write(rig, format):
    from app.creative.service import CreativeService, document_digest
    # Remove only this fixture's returned synthetic chapter; no chapter is required.
    rig.chapters.delete(rig.chapter['id'])
    assert rig.chapters.list(rig.nid) == []
    row = rig.service.create(rig.nid, rig.scope, rig.actor, independent(rig))
    reopened = CreativeService(rig.store, rig.novels, rig.chapters)
    before = copy.deepcopy(rig.store.read(rig.nid, rig.scope))
    chapters = copy.deepcopy(rig.chapters.list(rig.nid))
    result = reopened.export_screenplay(rig.nid, rig.scope, row['id'], 1, format)
    text = exported_text(result)
    for expected in ['风穿过空荡的码头。', '别忘记这座城。', '轻声', '旅人', '克制', '旧港码头', '午夜之后']:
        assert expected in text
    assert row['id'] in text and document_digest(row) in text
    assert result['document_version'] == 1
    assert hashlib.sha256(result['content']).hexdigest() == result['sha256']
    assert result['filename'].startswith('creative-'+row['id']+'-v1.')
    assert rig.store.read(rig.nid, rig.scope) == before
    assert rig.chapters.list(rig.nid) == chapters
    assert reopened.get(rig.nid, rig.scope, row['id']) == row
    assert reopened.export(rig.nid, rig.scope, row['id'])['document']['scenes'] == row['scenes']


@pytest.mark.parametrize('format', ['fountain', 'docx', 'markdown'])
def test_source_bound_export_pins_exact_saved_revision_and_source(rig, format):
    from app.services.v1_capability_service import CapabilityVersionConflict
    from app.experimental.common import StaleSourceError
    row = rig.service.create(rig.nid, rig.scope, rig.actor, payload(rig))
    changed = public(row); changed['scenes'][0]['dialogue'][0]['delivery'] = 'hesitant'
    row = rig.service.update(rig.nid, rig.scope, rig.actor, row['id'], 1, changed)
    with pytest.raises(CapabilityVersionConflict):
        rig.service.export_screenplay(rig.nid, rig.scope, row['id'], 1, format)
    result = rig.service.export_screenplay(rig.nid, rig.scope, row['id'], 2, format)
    assert 'hesitant' in exported_text(result) and rig.chapter['id'] in exported_text(result)
    rig.chapters.save(rig.chapter['id'], {'content':'Changed source', 'version':rig.chapter['version']})
    with pytest.raises(StaleSourceError):
        rig.service.export_screenplay(rig.nid, rig.scope, row['id'], 2, format)


@pytest.mark.parametrize('change', ['document', 'chapter', 'permission', 'archive', 'privacy'])
def test_rechecks_after_encoding_and_never_returns_stale_or_revoked_bytes(rig, monkeypatch, change):
    from app.creative import screenplay_export
    row = rig.service.create(rig.nid, rig.scope, rig.actor, payload(rig))
    original = screenplay_export.render
    revoked = False
    def guard():
        if revoked: raise PermissionError('revoked')
    def render(*args):
        nonlocal revoked
        result = original(*args)
        if change == 'document':
            value = public(row); value['title'] = 'Changed'
            rig.service.update(rig.nid, rig.scope, rig.actor, row['id'], 1, value)
        elif change == 'chapter': rig.chapters.save(rig.chapter['id'], {'content':'Different', 'version':rig.chapter['version']})
        elif change == 'privacy':
            from app.source_privacy import content_digest, review_source_privacy
            review_source_privacy(rig.chapter, None, 'reviewer', 'CLOUD_ALLOWED', rig.chapter['version'],
                                  content_digest(rig.chapter), root=rig.root)
        elif change == 'archive': rig.service.archive(rig.nid, rig.scope, rig.actor, row['id'], 1)
        else: revoked = True
        return result
    monkeypatch.setattr(screenplay_export, 'render', render)
    with pytest.raises(Exception) as failure:
        rig.service.export_screenplay(rig.nid, rig.scope, row['id'], 1, 'docx', reauthorize=guard)
    from app.experimental.common import StaleSourceError
    from app.services.v1_capability_service import CapabilityVersionConflict
    assert isinstance(failure.value, {'document':CapabilityVersionConflict, 'chapter':StaleSourceError, 'permission':PermissionError, 'archive':FileNotFoundError, 'privacy':StaleSourceError}[change])


@pytest.mark.parametrize('case', ['mode', 'empty', 'format', 'literal'])
def test_format_limits_are_explicit_without_mutating_or_truncating_document(rig, case):
    value = independent(rig)
    if case == 'mode': value['mode'] = 'DIRECTOR'
    if case == 'empty': value['scenes'] = []
    if case == 'literal': value['scenes'][0]['action'] = 'Visible [[literal]] author text'
    row = rig.service.create(rig.nid, rig.scope, rig.actor, value)
    before = copy.deepcopy(rig.store.read(rig.nid, rig.scope))
    with pytest.raises(ValueError):
        rig.service.export_screenplay(rig.nid, rig.scope, row['id'], 1, 'pdf' if case == 'format' else 'fountain')
    assert rig.store.read(rig.nid, rig.scope) == before
    if case == 'literal': assert '[[literal]]' in exported_text(rig.service.export_screenplay(rig.nid, rig.scope, row['id'], 1, 'docx'))


@pytest.mark.parametrize('format', ['fountain', 'docx', 'markdown'])
def test_private_readonly_api_returns_real_format_receipts_and_unchanged_json(rig, client, format):
    row = rig.service.create(rig.nid, rig.scope, rig.actor, independent(rig))
    url = f'/api/novels/{rig.nid}/experimental/creative/documents/{row["id"]}'
    response = client.get(url+'/screenplay-export', params={'format':format,'expected_version':1}, headers={'X-Session-Token':'reader'})
    assert response.status_code == 200, response.text[:200]
    assert response.headers['Cache-Control'] == 'no-store'
    assert response.headers['X-Content-Type-Options'] == 'nosniff'
    assert response.headers['X-Creative-Document-Version'] == '1'
    assert response.headers['X-Content-SHA256'] == hashlib.sha256(response.content).hexdigest()
    assert row['id'] in response.headers['Content-Disposition']
    assert client.get(url+'/export', headers={'X-Session-Token':'reader'}).json()['document']['id'] == row['id']
    assert client.get(url+'/screenplay-export', params={'format':format,'expected_version':2}, headers={'X-Session-Token':'reader'}).status_code == 409
    assert client.get(url+'/screenplay-export', params={'format':format,'expected_version':1}).status_code == 401
    assert client.get(url+'/screenplay-export', params={'format':format,'expected_version':1}, headers={'X-Session-Token':'owner','X-Branch-Id':'foreign'}).status_code == 404


@pytest.mark.parametrize('v1', [False, True])
def test_new_export_stays_default_off_and_v1_acceptance_off(rig, client, monkeypatch, v1):
    row = rig.service.create(rig.nid, rig.scope, rig.actor, independent(rig))
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2' if v1 else '')
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true' if v1 else 'false')
    response = client.get(f'/api/novels/{rig.nid}/experimental/creative/documents/{row["id"]}/screenplay-export', params={'format':'docx','expected_version':1}, headers={'X-Session-Token':'owner'})
    assert response.status_code == 404 and response.json()['detail']['code'] == 'EXPERIMENTAL_FEATURE_DISABLED'


def test_encoded_byte_capacity_rejects_without_partial_export_or_store_write(rig, monkeypatch):
    from app.creative import screenplay_export
    row = rig.service.create(rig.nid, rig.scope, rig.actor, independent(rig))
    before = copy.deepcopy(rig.store.read(rig.nid, rig.scope))
    monkeypatch.setattr(screenplay_export, 'MAX_EXPORT_BYTES', 32)
    with pytest.raises(ValueError, match='CREATIVE_SCREENPLAY_EXPORT_CAPACITY'):
        rig.service.export_screenplay(rig.nid, rig.scope, row['id'], 1, 'docx')
    assert rig.store.read(rig.nid, rig.scope) == before

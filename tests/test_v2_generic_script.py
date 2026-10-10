"""Neutral authored Script contracts on original Creative File/PostgreSQL owners."""
import copy
import hashlib
import io
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
from test_v2_creative_foundation import rig, client, payload, public

PURPOSES = ['CUSTOM', 'ADVERTISEMENT', 'MV_NARRATION', 'PODCAST', 'GAME_DIALOGUE', 'PRESENTATION', 'SHORT_VIDEO']
BODY = '  第一段，保留空格。\n\n角色甲：不要自动改写正文。\n'


def script(purpose='CUSTOM', body=BODY):
    return {'mode':'SCRIPT', 'title':'合成通用脚本', 'source_independent':True,
            'script':{'purpose':purpose, 'body':body}}


@pytest.mark.parametrize('purpose', PURPOSES)
def test_chapterless_script_create_edit_reopen_restore_and_json_share_one_owner(rig, purpose):
    from app.creative.service import CreativeService
    rig.chapters.delete(rig.chapter['id'])
    row = rig.service.create(rig.nid, rig.scope, rig.actor, script(purpose))
    assert row['script'] == {'purpose':purpose, 'body':BODY}
    assert row['scenes'] == row['shots'] == row['director_notes'] == [] and row['video_plan'] is None
    changed = public(row); changed['script']['body'] = BODY + '第二稿。'
    second = rig.service.update(rig.nid, rig.scope, rig.actor, row['id'], 1, changed)
    reopened = CreativeService(rig.store, rig.novels, rig.chapters)
    assert reopened.get(rig.nid, rig.scope, row['id']) == second
    third = reopened.restore(rig.nid, rig.scope, rig.actor, row['id'], 2, 1)
    assert third['version'] == 3 and third['restored_from_version'] == 1
    assert third['script'] == row['script']
    assert [r['version'] for r in reopened.history(rig.nid, rig.scope, row['id'])['items']] == [1,2,3]
    assert reopened.export(rig.nid, rig.scope, row['id'])['document']['script'] == row['script']
    assert len(reopened.list(rig.nid, rig.scope)) == 1 and rig.chapters.list(rig.nid) == []


@pytest.mark.parametrize('format', ['txt', 'markdown', 'docx'])
def test_private_export_reads_exact_saved_script_bytes_without_mutation(rig, client, format):
    row = rig.service.create(rig.nid, rig.scope, rig.actor, script())
    before = copy.deepcopy(rig.store.read(rig.nid, rig.scope))
    url = f'/api/novels/{rig.nid}/experimental/creative/documents/{row["id"]}/script-export'
    response = client.get(url, params={'format':format, 'expected_version':1}, headers={'X-Session-Token':'reader'})
    assert response.status_code == 200, response.text[:200]
    assert response.headers['X-Content-SHA256'] == hashlib.sha256(response.content).hexdigest()
    assert response.headers['X-Creative-Document-Version'] == '1'
    assert response.headers['Cache-Control'] == 'no-store' and response.headers['X-Content-Type-Options'] == 'nosniff'
    if format != 'docx': assert response.content == BODY.encode('utf-8')
    else:
        with ZipFile(io.BytesIO(response.content)) as archive:
            assert archive.testzip() is None
            root = ET.fromstring(archive.read('word/document.xml'))
            texts = [''.join(p.itertext()) for p in root.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p')]
            assert texts == [row['title'], *BODY.split('\n')]
    assert rig.store.read(rig.nid, rig.scope) == before
    assert client.get(url, params={'format':format,'expected_version':2}, headers={'X-Session-Token':'reader'}).status_code == 409
    assert client.get(url, params={'format':format,'expected_version':1}).status_code == 401
    assert client.get(url, params={'format':format,'expected_version':1}, headers={'X-Session-Token':'reader','X-Branch-Id':'foreign'}).status_code == 404


@pytest.mark.parametrize('invalid', [
    {'script':None}, {'scenes':[{'id':'s','sequence':1,'heading':'Not a screenplay'}]},
    {'video_plan':{}}, {'script':{'purpose':'UNKNOWN','body':'Text'}},
    {'script':{'purpose':'CUSTOM','body':'  \n '}}, {'script':{'purpose':'CUSTOM','body':3}},
    {'script':{'purpose':'CUSTOM','body':'x'*64001}}, {'script':{'purpose':'CUSTOM','body':'Text','tool':'execute'}},
    {'mode':'SCREENPLAY'},
], ids=['missing-body','scene-field','video-field','unknown-purpose','blank','wrong-type','overlong','extra-field','wrong-mode'])
def test_typed_script_rejects_incompatible_or_unbounded_inputs(rig, invalid):
    before = copy.deepcopy(rig.store.read(rig.nid, rig.scope))
    with pytest.raises(ValueError): rig.service.create(rig.nid, rig.scope, rig.actor, {**script(), **invalid})
    assert rig.store.read(rig.nid, rig.scope) == before


def test_script_keeps_original_cas_mode_and_derivation_boundaries(rig):
    from app.services.v1_capability_service import CapabilityVersionConflict
    row = rig.service.create(rig.nid, rig.scope, rig.actor, script())
    barrier = Barrier(2)
    def write(text):
        body = public(row); body['script']['body'] = text; barrier.wait()
        try: return rig.service.update(rig.nid, rig.scope, rig.actor, row['id'], 1, body)
        except CapabilityVersionConflict: return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(write, ['First', 'Second']))
    assert sum(isinstance(v, dict) for v in results) == 1 and results.count('conflict') == 1
    current = rig.service.get(rig.nid, rig.scope, row['id'])
    with pytest.raises(ValueError, match='MODE_IMMUTABLE'):
        rig.service.update(rig.nid, rig.scope, rig.actor, row['id'], 2,
                           {'mode':'SCREENPLAY','title':'Different kind','source_independent':True})
    with pytest.raises(ValueError, match='DERIVATION_STAGE_INVALID'):
        rig.service.derive(rig.nid, rig.scope, rig.actor, row['id'], {'expected_version':2,'mode':'STORYBOARD'})
    assert rig.service.get(rig.nid, rig.scope, row['id']) == current


def test_new_script_field_does_not_rewrite_legacy_snapshots_on_read(rig):
    from app.creative.service import document_digest
    row = rig.service.create(rig.nid, rig.scope, rig.actor, payload(rig))
    with rig.service.store.transaction(rig.nid, rig.scope) as state:
        state['collections'][rig.service.COLLECTION][row['id']].pop('script')
    legacy = rig.service.get(rig.nid, rig.scope, row['id']); before = copy.deepcopy(rig.store.read(rig.nid, rig.scope))
    digest = document_digest(legacy)
    assert 'script' not in rig.service.export(rig.nid, rig.scope, row['id'])['document']
    assert document_digest(rig.service.history(rig.nid, rig.scope, row['id'])['items'][0]) == digest
    assert rig.store.read(rig.nid, rig.scope) == before
    restored = rig.service.restore(rig.nid, rig.scope, rig.actor, row['id'], 1, 1)
    assert restored['version'] == 2 and restored['script'] is None


@pytest.mark.parametrize('change', ['source', 'permission', 'archive'])
def test_script_export_rechecks_original_owner_after_encoding(rig, monkeypatch, change):
    from app.creative import script_export
    from app.experimental.common import StaleSourceError
    body = script(); body.update(source_independent=False, source_chapter_ids=[rig.chapter['id']])
    row = rig.service.create(rig.nid, rig.scope, rig.actor, body)
    original = script_export.render; revoked = False
    def guard():
        if revoked: raise PermissionError('revoked')
    def render(*args):
        nonlocal revoked
        result = original(*args)
        if change == 'source': rig.chapters.save(rig.chapter['id'], {'content':'Updated source','version':rig.chapter['version']})
        elif change == 'archive': rig.service.archive(rig.nid, rig.scope, rig.actor, row['id'], 1)
        else: revoked = True
        return result
    monkeypatch.setattr(script_export, 'render', render)
    with pytest.raises({'source':StaleSourceError,'permission':PermissionError,'archive':FileNotFoundError}[change]):
        rig.service.export_script(rig.nid, rig.scope, row['id'], 1, 'docx', reauthorize=guard)


def test_script_exact_text_and_docx_limits_are_not_silent_loss(rig, monkeypatch):
    from app.creative import script_export
    row = rig.service.create(rig.nid, rig.scope, rig.actor, script(body='Keep\x01the original'))
    assert rig.service.export_script(rig.nid, rig.scope, row['id'], 1, 'txt')['content'] == b'Keep\x01the original'
    with pytest.raises(ValueError, match='TEXT_UNREPRESENTABLE'):
        rig.service.export_script(rig.nid, rig.scope, row['id'], 1, 'docx')
    monkeypatch.setattr(script_export, 'MAX_EXPORT_BYTES', 2)
    with pytest.raises(ValueError, match='EXPORT_CAPACITY'):
        rig.service.export_script(rig.nid, rig.scope, row['id'], 1, 'txt')
    assert rig.service.get(rig.nid, rig.scope, row['id']) == row


@pytest.mark.parametrize('v1', [False, True])
def test_script_creation_and_export_keep_default_off_and_v1_off(rig, client, monkeypatch, v1):
    row = rig.service.create(rig.nid, rig.scope, rig.actor, script())
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2' if v1 else '')
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true' if v1 else 'false')
    base = f'/api/novels/{rig.nid}/experimental/creative'
    assert client.post(base+'/documents', json=script(), headers={'X-Session-Token':'owner'}).status_code == 404
    assert client.get(base+f'/documents/{row["id"]}/script-export', params={'format':'txt','expected_version':1}, headers={'X-Session-Token':'owner'}).status_code == 404

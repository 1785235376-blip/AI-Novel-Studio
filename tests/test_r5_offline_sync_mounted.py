"""B10 composed File/real-PG API and original-session/feature/write authority."""
from copy import deepcopy
from uuid import uuid4
import pytest
from app.actor_context import SessionContext
from app.experimental.flags import FLAGS
from app.experimental.offline_sync import OfflineSyncService
from test_r3_mounted_contracts import mounted, prefix, scoped, checked


@pytest.fixture
def sync(mounted):
    e = mounted
    e.sessions.register('sync-host', SessionContext('sync-session', 'sync-client', 'sync-actor', 'sync-workspace'))
    e.client.headers['X-Session-Token'] = 'sync-host'; e.sbase = e.base + '/offline-sync'; e.sync = e.experimental.offline_sync_service
    return e


def create(e):
    return checked(e.client.post(e.sbase + '/channels', json={'stream_id': uuid4().hex, 'endpoint_id': 'local', 'peer_id': 'peer', 'chapter_ids': [e.chapter['id']], 'allow_new_chapters': True}), 201)


def incoming(e, channel, *, new=False):
    chapter = e.chapters.get(e.chapter['id']); base = {'title': chapter['title'], 'document': chapter['document']}; snapshot = deepcopy(base)
    snapshot['document']['content'].append({'type': 'paragraph', 'content': [{'type': 'text', 'text': 'B10 synthetic received addition'}]})
    envelope = {'protocol': 'AI_NOVEL_SYNC_1', 'stream_id': channel['stream_id'], 'source_endpoint': 'peer', 'destination_endpoint': 'local',
        'message_id': uuid4().hex, 'sequence': 1, 'source_chapter_id': 'peer-project:1', 'source_version': 2, 'operation': 'SNAPSHOT', 'base': base,
        'snapshot': snapshot, 'privacy_level': 'LOCAL_ONLY'}
    row = checked(e.client.post(e.sbase + '/channels/' + channel['id'] + '/receive', json={'expected_version': channel['version'], 'envelope': envelope,
        'target_chapter_id': None if new else e.chapter['id'], 'create_new': new}))
    plan = checked(e.client.post(e.sbase + '/inbox/' + row['id'] + '/review', json={'expected_version': row['version']}))
    return row, {'expected_version': row['version'], 'preview_digest': plan['preview_digest'], 'confirmed': True}


def test_mounted_scope_receive_review_apply_uses_original_writer(sync, monkeypatch):
    e = sync; before = deepcopy(e.chapters.get(e.chapter['id'])); channel = create(e); row, body = incoming(e, channel)
    original = e.api.update_chapter; calls = []
    def observed(*args, **kwargs): calls.append((args, kwargs)); return original(*args, **kwargs)
    monkeypatch.setattr(e.api, 'update_chapter', observed)
    assert e.chapters.get(e.chapter['id']) == before
    done = checked(e.client.post(e.sbase + '/inbox/' + row['id'] + '/apply', json=body))
    assert done['status'] == 'APPLIED' and len(calls) == 1
    assert calls[0][0][1].source == 'OFFLINE_SYNC_REVIEW' and calls[0][0][1].version == before['version']
    assert calls[0][1]['x_session_token'] == 'sync-host'
    assert e.chapters.get(e.chapter['id'])['version'] == before['version'] + 1
    assert e.client.get(e.sbase + '/records').headers['cache-control'] == 'no-store'


def test_mounted_new_chapter_create_and_save_are_original_authority(sync, monkeypatch):
    e = sync; channel = create(e); row, body = incoming(e, channel, new=True); before = len(e.chapters.list(e.nid))
    create_original, save_original = e.api.create_chapter, e.api.update_chapter; calls = []
    def create_spy(*args, **kwargs): calls.append('create'); return create_original(*args, **kwargs)
    def save_spy(*args, **kwargs): calls.append('save'); return save_original(*args, **kwargs)
    monkeypatch.setattr(e.api, 'create_chapter', create_spy); monkeypatch.setattr(e.api, 'update_chapter', save_spy)
    done = checked(e.client.post(e.sbase + '/inbox/' + row['id'] + '/apply', json=body))
    assert done['status'] == 'APPLIED' and calls == ['create', 'save'] and len(e.chapters.list(e.nid)) == before + 1
    assert e.client.post(e.sbase + '/inbox/' + row['id'] + '/apply', json=body).status_code == 409


def test_mounted_default_off_v1_dependency_host_session_and_strict_body(sync, monkeypatch):
    e = sync; e.client.headers.pop('X-Session-Token'); assert e.client.get(e.sbase + '/catalog').status_code == 401
    e.client.headers['X-Session-Token'] = 'sync-host'
    for flags, v1 in [('', 'false'), ('*', 'false'), ('offline_sync_v2', 'false'), (','.join(FLAGS), 'true')]:
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', flags); monkeypatch.setenv('V1_ACCEPTANCE_MODE', v1)
        assert e.client.get(e.sbase + '/records').status_code == 404
        assert e.client.post(e.sbase + '/channels', json={}).status_code == 404
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(FLAGS)); monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'false')
    response = e.client.post(e.sbase + '/channels', content='{"stream_id":"a","stream_id":"b"}', headers={'Content-Type': 'application/json'})
    assert response.status_code == 422
    assert e.client.post(e.sbase + '/channels', content='x' * 540000).status_code == 413
    assert e.client.post(e.sbase + '/channels', json={'stream_id': 'x', 'endpoint_id': 'a', 'peer_id': 'b', 'chapter_ids': [e.chapter['id']], 'url': 'https://not-allowed.invalid'}).status_code == 422
    assert not e.store.read(e.nid, e.scope)['collections'].get(OfflineSyncService.CHANNELS)


@pytest.mark.parametrize('fence', ['flag', 'v1', 'session', 'source'])
def test_mounted_final_apply_rechecks_before_original_dispatch(sync, monkeypatch, fence):
    e = sync; channel = create(e); row, body = incoming(e, channel); before = e.chapters.get(e.chapter['id'])
    actual = e.sync._review; count = []
    def revoke(*args, **kwargs):
        result = actual(*args, **kwargs); count.append(1)
        if len(count) == 2:
            if fence == 'flag': monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
            elif fence == 'v1': monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
            elif fence == 'session': e.sessions.revoke('sync-host')
            else:
                doc = deepcopy(before['document']); doc['content'].append({'type': 'paragraph', 'content': [{'type': 'text', 'text': 'Newer original edit'}]})
                e.chapters.save(e.chapter['id'], {'version': before['version'], 'document': doc})
        return result
    monkeypatch.setattr(e.sync, '_review', revoke)
    assert e.client.post(e.sbase + '/inbox/' + row['id'] + '/apply', json=body).status_code in {401, 404, 409}
    current = e.chapters.get(e.chapter['id'])
    assert 'B10 synthetic received addition' not in str(current['document'])
    if fence != 'source': assert current == before


def test_mounted_collaboration_branch_never_reads_base_chapters(sync, monkeypatch):
    e = scoped(sync, monkeypatch); e.client.headers.pop('X-Session-Token', None)
    response = e.client.get(e.sbase + '/catalog', headers=e.headers)
    assert response.status_code in {401, 403, 422} and 'city gate opened' not in response.text
    assert e.client.get(e.sbase + '/records').status_code == 401

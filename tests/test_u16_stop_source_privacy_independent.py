"""File mounted route: source visibility must precede stale-version disclosure."""
from types import SimpleNamespace
import pytest
from app.actor_context import SessionContext
from app.experimental.common import new_row
from test_studio_asset_query import rig
from test_audio_history_status_readonly import snapshot


@pytest.mark.parametrize('alias', ['', '/v1'])
def test_stale_nonimage_stop_does_not_reveal_batch_with_invisible_source(rig, monkeypatch, alias):
    from app.experimental import api as experimental_api
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,reader_preflight_v2,safe_batches_v2')
    rig.sessions.register('synthetic-host', SessionContext('synthetic-session', 'client', 'local-author', 'synthetic'))
    # Real File scope owner and real _owned source projection; the referenced
    # synthetic chapter does not exist and must conceal the whole record.
    batch = new_row(rig.nid, rig.scope, 'local-author', {'status': 'READY', 'confirmed': True,
        'snapshot_digest': 'b' * 64, 'snapshot': {'steps': [{'input': {'kind': 'EXPORT'},
           'sources': {rig.nid + ':1': 'a' * 64}}]},
        'items': [{'index': 0, 'status': 'PENDING', 'attempts': 0, 'receipts': []}]})
    with rig.workspace.store.store.transaction(rig.nid, rig.scope) as doc:
        doc['collections']['safe_batches_v2'] = {batch['id']: batch}
    mounted = experimental_api.safe_batches_service
    monkeypatch.setattr(mounted, 'store', rig.workspace.store.store)
    monkeypatch.setattr(mounted, 'novels', rig.novels)
    monkeypatch.setattr(mounted, 'chapters', rig.workspace.creative.chapters)
    monkeypatch.setattr(mounted, 'sources', SimpleNamespace(novels=rig.novels, chapter_reader=None))
    before = rig.workspace.store.store._file_bytes(rig.nid, rig.scope)
    response = rig.client.post(f'/api{alias}/novels/{rig.nid}/experimental/safe-batches/{batch["id"]}/stop',
        headers={'X-Session-Token': 'synthetic-host'}, json={'expected_version': batch['version'] + 1})
    assert response.status_code == 404, response.text
    assert rig.workspace.store.store._file_bytes(rig.nid, rig.scope) == before


@pytest.mark.parametrize('alias', ['', '/v1'])
def test_hidden_image_stop_does_not_initialize_missing_project_marker(rig, monkeypatch, alias):
    from app.experimental import api as experimental_api
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,reader_preflight_v2,safe_batches_v2')
    rig.sessions.register('synthetic-host', SessionContext('synthetic-session', 'client', 'local-author', 'synthetic'))
    batch = new_row(rig.nid, rig.scope, 'local-author', {'status': 'READY', 'confirmed': True,
        'snapshot_digest': 'b' * 64, 'snapshot': {'steps': [{'input': {'kind': 'STUDIO_IMAGE'},
           'sources': {rig.nid + ':1': 'a' * 64}}]},
        'items': [{'index': 0, 'status': 'PENDING', 'attempts': 0, 'receipts': []}]})
    with rig.workspace.store.store.transaction(rig.nid, rig.scope) as doc:
        doc['collections']['safe_batches_v2'] = {batch['id']: batch}
    mounted = experimental_api.safe_batches_service
    monkeypatch.setattr(mounted, 'store', rig.workspace.store.store)
    monkeypatch.setattr(mounted, 'novels', rig.novels)
    monkeypatch.setattr(mounted, 'chapters', rig.workspace.creative.chapters)
    monkeypatch.setattr(mounted, 'sources', SimpleNamespace(novels=rig.novels, chapter_reader=None))
    marker = rig.root / 'novels' / rig.nid / 'creative_project_v2.json'
    assert not marker.exists()
    before = snapshot(rig.root)
    response = rig.client.post(f'/api{alias}/novels/{rig.nid}/experimental/safe-batches/{batch["id"]}/stop',
        headers={'X-Session-Token': 'synthetic-host'}, json={'expected_version': batch['version']})
    assert response.status_code == 404, response.text
    assert not marker.exists()
    assert snapshot(rig.root) == before


@pytest.mark.parametrize('alias', ['', '/v1'])
def test_missing_image_owner_keeps_host_and_feature_denial_priority(rig, monkeypatch, alias):
    from app.experimental import api as experimental_api
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,reader_preflight_v2,safe_batches_v2')
    rig.sessions.register('synthetic-host', SessionContext('synthetic-session', 'client', 'local-author', 'synthetic'))
    batch = new_row(rig.nid, rig.scope, 'local-author', {'status': 'READY', 'confirmed': True,
        'snapshot_digest': 'b' * 64, 'snapshot': {'steps': [{'input': {'kind': 'STUDIO_IMAGE'},
           'sources': {rig.nid + ':1': 'a' * 64}}]},
        'items': [{'index': 0, 'status': 'PENDING', 'attempts': 0, 'receipts': []}]})
    with rig.workspace.store.store.transaction(rig.nid, rig.scope) as doc:
        doc['collections']['safe_batches_v2'] = {batch['id']: batch}
    mounted = experimental_api.safe_batches_service
    monkeypatch.setattr(mounted, 'store', rig.workspace.store.store)
    monkeypatch.setattr(mounted, 'novels', rig.novels)
    path = f'/api{alias}/novels/{rig.nid}/experimental/safe-batches/{batch["id"]}/stop'
    body = {'expected_version': batch['version']}
    before = snapshot(rig.root)
    assert rig.client.post(path, json=body).status_code == 401
    forwarded = rig.client.post(path, json=body, headers={'X-Session-Token': 'synthetic-host', 'X-Forwarded-For': '127.0.0.1'})
    assert forwarded.status_code == 403, forwarded.text
    origin = rig.client.post(path, json=body, headers={'X-Session-Token': 'synthetic-host', 'Origin': 'https://invalid.example'})
    assert origin.status_code == 403, origin.text
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'reader_preflight_v2,safe_batches_v2')
    disabled = rig.client.post(path, json=body, headers={'X-Session-Token': 'synthetic-host'})
    assert disabled.status_code == 404, disabled.text
    assert snapshot(rig.root) == before


@pytest.mark.parametrize('alias', ['', '/v1'])
def test_missing_image_owner_rechecks_real_host_session(rig, monkeypatch, alias):
    from app import main
    from app.experimental import api as experimental_api
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,reader_preflight_v2,safe_batches_v2')
    rig.sessions.register('synthetic-host', SessionContext('synthetic-session', 'client', 'local-author', 'synthetic'))
    batch = new_row(rig.nid, rig.scope, 'local-author', {'status': 'READY', 'confirmed': True,
        'snapshot_digest': 'b' * 64, 'snapshot': {'steps': [{'input': {'kind': 'STUDIO_IMAGE'},
           'sources': {rig.nid + ':1': 'a' * 64}}]},
        'items': [{'index': 0, 'status': 'PENDING', 'attempts': 0, 'receipts': []}]})
    with rig.workspace.store.store.transaction(rig.nid, rig.scope) as doc:
        doc['collections']['safe_batches_v2'] = {batch['id']: batch}
    mounted = experimental_api.safe_batches_service
    monkeypatch.setattr(mounted, 'store', rig.workspace.store.store)
    monkeypatch.setattr(mounted, 'novels', rig.novels)
    original = main._local_discovery_host_authority
    def revoked(request, token):
        authority = original(request, token)
        rig.sessions.revoke(token)
        return authority
    monkeypatch.setattr(main, '_local_discovery_host_authority', revoked)
    before = snapshot(rig.root)
    response = rig.client.post(f'/api{alias}/novels/{rig.nid}/experimental/safe-batches/{batch["id"]}/stop',
        headers={'X-Session-Token': 'synthetic-host'}, json={'expected_version': batch['version']})
    assert response.status_code in (401, 403), response.text
    assert snapshot(rig.root) == before

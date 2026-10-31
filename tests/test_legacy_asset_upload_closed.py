"""Legacy upload route closes before writes until unified capacity exists."""
import base64
import pytest

from test_audio_history_status_readonly import snapshot
from test_studio_asset_query import rig, shared_scope

pytestmark = pytest.mark.file_backend_only


@pytest.mark.parametrize('alias', [False, True])
def test_legacy_upload_refuses_all_kinds_and_preserves_download(rig, monkeypatch, alias):
    from app import api
    monkeypatch.setattr(api, 'asset_library_service', rig.assets)
    # Seed with the original legacy owner, not the project-bound Studio owner.
    existing = rig.assets.create(rig.nid, 'existing.wav',
        base64.b64encode(b'synthetic fixture bytes').decode(), 'audio/wav', 'audio')
    prefix = '/api/v1' if alias else '/api'
    before = snapshot(rig.root)
    for kind in ('audio', 'image'):
        body = {'novel_id': rig.nid, 'filename': 'upload.bin', 'kind': kind,
                'content_base64': base64.b64encode(b'synthetic').decode(), 'media_type': 'application/octet-stream'}
        response = rig.client.post(f'{prefix}/novels/{rig.nid}/assets', json=body)
        assert response.status_code == 503, response.text
        assert response.json()['detail']['code'] == 'PROJECT_CAPACITY_WRITE_UNAVAILABLE'
    listed = rig.client.get(f'{prefix}/novels/{rig.nid}/assets')
    assert listed.status_code == 200 and any(row['id'] == existing['id'] for row in listed.json())
    downloaded = rig.client.get(f"{prefix}/assets/{existing['id']}/download", params={'novel_id': rig.nid})
    assert downloaded.status_code == 200 and downloaded.content == b'synthetic fixture bytes'
    assert snapshot(rig.root) == before


@pytest.mark.parametrize('alias', [False, True])
def test_collaboration_denied_authority_precedes_unavailable(rig, monkeypatch, alias):
    from app import api
    monkeypatch.setattr(api, 'asset_library_service', rig.assets)
    scope, headers = shared_scope(rig)
    before = snapshot(rig.root)
    body = {'novel_id': rig.nid, 'filename': 'upload.wav', 'kind': 'audio',
            'content_base64': base64.b64encode(b'synthetic').decode()}
    prefix = '/api/v1' if alias else '/api'
    response = rig.client.post(f'{prefix}/novels/{rig.nid}/assets', json=body,
                               headers={**headers, 'X-Session-Token': 'token-no-grants'})
    assert response.status_code == 403, response.text
    assert snapshot(rig.root) == before


@pytest.mark.parametrize('alias', [False, True])
def test_authorized_collaboration_writer_refused_without_writes(rig, monkeypatch, alias):
    from app import api
    from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind
    monkeypatch.setattr(api, 'asset_library_service', rig.assets)
    scope, headers = shared_scope(rig)
    grant_scope = AuthorizationScope(ScopeKind.PROJECT, 'query-workspace', rig.nid)
    rig.grants.assign_permission(PermissionAssignment('query-write', 'reader', 'domain.write',
        ModalityDomain.NOVEL, grant_scope, 'synthetic'))
    before = snapshot(rig.root)
    body = {'novel_id': rig.nid, 'filename': 'upload.wav', 'kind': 'audio',
            'content_base64': base64.b64encode(b'synthetic').decode()}
    prefix = '/api/v1' if alias else '/api'
    response = rig.client.post(f'{prefix}/novels/{rig.nid}/assets', json=body, headers=headers)
    assert response.status_code == 503, response.text
    assert response.json()['detail']['code'] == 'PROJECT_CAPACITY_WRITE_UNAVAILABLE'
    assert snapshot(rig.root) == before

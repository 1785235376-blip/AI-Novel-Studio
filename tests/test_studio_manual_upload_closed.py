"""Direct Studio manual upload is closed before allocation, File fixtures."""
import pytest

from test_audio_history_status_readonly import snapshot
from test_audio_shared_replacement_plan_independent import candidate
from test_studio_asset_query import rig, shared_scope

pytestmark = pytest.mark.file_backend_only


def payload():
    return {'filename': 'synthetic.wav', 'kind': 'audio',
            'content_base64': candidate()['content_base64'], 'idempotency_key': 'synthetic-request'}


@pytest.mark.parametrize('alias', [False, True])
def test_manual_upload_closed_before_first_marker_or_asset_write(rig, alias):
    prefix = '/api/v1' if alias else '/api'
    marker = rig.root / 'novels' / rig.nid / 'creative_project_v2.json'
    assert not marker.exists()
    before = snapshot(rig.root)
    response = rig.client.post(f'{prefix}/projects/{rig.nid}/studio/assets', json=payload())
    assert response.status_code == 503, response.text
    assert response.json()['detail']['code'] == 'PROJECT_CAPACITY_WRITE_UNAVAILABLE'
    assert not marker.exists()
    assert snapshot(rig.root) == before


@pytest.mark.parametrize('alias', [False, True])
def test_original_existing_asset_read_is_preserved(rig, alias):
    asset = rig.seed('synthetic.wav', 'audio')
    prefix = '/api/v1' if alias else '/api'
    before = snapshot(rig.root)
    response = rig.client.get(f"{prefix}/projects/{rig.nid}/studio/assets/{asset['id']}")
    assert response.status_code == 200, response.text
    assert response.json()['id'] == asset['id']
    assert snapshot(rig.root) == before


@pytest.mark.parametrize('alias', [False, True])
def test_denied_collaboration_actor_is_denied_before_capacity_response(rig, alias):
    scope, headers = shared_scope(rig)
    prefix = '/api/v1' if alias else '/api'
    before = snapshot(rig.root)
    response = rig.client.post(f'{prefix}/projects/{rig.nid}/studio/assets', json=payload(),
                               headers={**headers, 'X-Session-Token': 'token-no-grants'})
    assert response.status_code == 403, response.text
    assert snapshot(rig.root) == before


@pytest.mark.parametrize('alias', [False, True])
def test_collaboration_writer_rejected_without_marker_or_asset_write(rig, alias):
    from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind
    scope, headers = shared_scope(rig)
    grant_scope = AuthorizationScope(ScopeKind.PROJECT, 'query-workspace', rig.nid)
    rig.grants.assign_permission(PermissionAssignment('write-fixture', 'reader', 'domain.write',
        ModalityDomain.NOVEL, grant_scope, 'synthetic'))
    prefix = '/api/v1' if alias else '/api'
    before = snapshot(rig.root)
    response = rig.client.post(f'{prefix}/projects/{rig.nid}/studio/assets', json=payload(), headers=headers)
    assert response.status_code == 503, response.text
    assert response.json()['detail']['code'] == 'PROJECT_CAPACITY_WRITE_UNAVAILABLE'
    assert snapshot(rig.root) == before


def test_direct_service_import_is_also_closed_before_any_write(rig):
    before = snapshot(rig.root)
    with pytest.raises(ValueError, match='PROJECT_CAPACITY_WRITE_UNAVAILABLE'):
        rig.workspace.import_asset(rig.nid, rig.scope, 'synthetic-actor', payload())
    assert snapshot(rig.root) == before

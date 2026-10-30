"""Independent negative controls for the legacy upload closure."""
import base64

import pytest

from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind
from test_audio_history_status_readonly import snapshot
from test_studio_asset_query import rig, shared_scope

pytestmark = pytest.mark.file_backend_only


def body(nid, kind='audio'):
    return {'novel_id': nid, 'filename': 'synthetic.wav', 'kind': kind,
            'content_base64': base64.b64encode(b'synthetic').decode(),
            'character_id': 'synthetic-character', 'scene_id': 'synthetic-scene'}


@pytest.mark.parametrize('alias', [False, True])
@pytest.mark.parametrize('kind', ['audio', 'image', 'text', 'video', 'arbitrary-client-kind'])
def test_gate_precedes_all_asset_owner_writes_on_empty_scope(rig, monkeypatch, alias, kind):
    from app import api
    monkeypatch.setattr(api, 'asset_library_service', rig.assets)
    def forbidden(*args, **kwargs):
        pytest.fail('legacy asset write reached')
    monkeypatch.setattr(rig.assets, 'create', forbidden)
    monkeypatch.setattr(rig.assets, 'update_metadata', forbidden)
    before = snapshot(rig.root)
    prefix = f"/api{'/v1' if alias else ''}"
    response = rig.client.post(prefix + f'/novels/{rig.nid}/assets', json=body(rig.nid, kind))
    assert response.status_code == 503, response.text
    assert response.json()['detail']['code'] == 'PROJECT_CAPACITY_WRITE_UNAVAILABLE'
    assert snapshot(rig.root) == before


@pytest.mark.parametrize('alias', [False, True])
def test_permission_precedes_path_body_mismatch_and_capacity_gate(rig, monkeypatch, alias):
    from app import api
    monkeypatch.setattr(api, 'asset_library_service', rig.assets)
    _, headers = shared_scope(rig)
    prefix = f"/api{'/v1' if alias else ''}"
    before = snapshot(rig.root)
    response = rig.client.post(prefix + f'/novels/{rig.nid}/assets', json=body('other-project'),
                               headers={**headers, 'X-Session-Token': 'token-no-grants'})
    assert response.status_code == 403, response.text
    assert 'PROJECT_CAPACITY_WRITE_UNAVAILABLE' not in response.text
    assert snapshot(rig.root) == before


@pytest.mark.parametrize('alias', [False, True])
def test_authorized_mismatched_project_remains_bad_request(rig, monkeypatch, alias):
    from app import api
    monkeypatch.setattr(api, 'asset_library_service', rig.assets)
    _, headers = shared_scope(rig)
    grant_scope = AuthorizationScope(ScopeKind.PROJECT, 'query-workspace', rig.nid)
    rig.grants.assign_permission(PermissionAssignment('independent-write', 'reader', 'domain.write',
        ModalityDomain.NOVEL, grant_scope, 'synthetic'))
    before = snapshot(rig.root)
    prefix = f"/api{'/v1' if alias else ''}"
    response = rig.client.post(prefix + f'/novels/{rig.nid}/assets', headers=headers, json=body('other-project'))
    assert response.status_code == 400, response.text
    assert snapshot(rig.root) == before

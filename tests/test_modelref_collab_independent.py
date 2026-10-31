"""Independent collaboration check for closed model-reference admission."""
import pytest
from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind
from test_studio_asset_query import rig, shared_scope
from test_audio_history_status_readonly import snapshot
from test_scope_residue_model_upload_independent import payload

@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_granted_project_writer_reaches_closed_gate_without_initialization(rig, prefix):
    _, headers = shared_scope(rig)
    scope = AuthorizationScope(ScopeKind.PROJECT, 'query-workspace', rig.nid)
    rig.grants.assign_permission(PermissionAssignment('model-writer', 'reader', 'domain.write', ModalityDomain.NOVEL, scope, 'synthetic'))
    marker = rig.root / 'novels' / rig.nid / 'creative_project_v2.json'
    assert not marker.exists()
    before = snapshot(rig.root)
    response = rig.client.post(f'{prefix}/projects/{rig.nid}/studio/assets/model-reference', headers=headers, json=payload())
    assert response.status_code == 503, response.text
    assert response.json()['detail']['code'] == 'PROJECT_CAPACITY_WRITE_UNAVAILABLE'
    assert not marker.exists() and snapshot(rig.root) == before

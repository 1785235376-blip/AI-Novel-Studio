"""A legacy row-size view must not claim capacity admission is available."""
import pytest

from app.creative.storage_admission import StudioStorageAdmission
from test_audio_history_status_readonly import snapshot
from test_studio_asset_query import rig, shared_scope
from test_studio_workspace_identity_history_contract import audio_history

pytestmark = pytest.mark.file_backend_only


def test_unproven_quota_does_not_probe_disk_or_claim_import_capacity(monkeypatch):
    admission = StudioStorageAdmission(None)
    def should_not_probe():
        raise AssertionError('disk space cannot prove project quota')
    monkeypatch.setattr(admission, 'available', should_not_probe)
    result = admission.view(None)
    assert result['state'] == 'UNAVAILABLE'
    assert result['available_import_bytes'] is None
    assert result['project_quota_status'] == 'UNVERIFIED'


def test_proven_quota_view_preserves_existing_contract(monkeypatch):
    admission = StudioStorageAdmission(None)
    monkeypatch.setattr(admission, 'available', lambda: 100)
    result = admission.view(40)
    assert result['state'] == 'READY'
    assert result['available_import_bytes'] == 40


@pytest.mark.parametrize('alias', [False, True])
def test_storage_does_not_present_unavailable_project_quota_as_ready(audio_history, alias):
    e = audio_history
    before = snapshot(e.rig.root)
    response = e.client.get(f"/api{'/v1' if alias else ''}/projects/{e.rig.nid}/studio/storage", headers=e.headers)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['assets']['count'] == 1
    assert result['assets']['bytes'] == len(e.content)
    admission = result['admission']
    assert admission['state'] == 'UNAVAILABLE'
    assert admission['available_import_bytes'] is None
    assert admission['project_quota_status'] == 'UNVERIFIED'
    # This legacy constant is required by the original client parser; the
    # UNAVAILABLE state explicitly says no project quota has been measured.
    assert admission['measurement'] == 'CURRENT_ORIGINAL_ASSET_FILESYSTEM_AND_PROJECT_QUOTA'
    assert admission['automatic_cleanup'] is False
    assert admission['automatic_migration'] is False
    assert admission['external_model_scan'] is False
    assert snapshot(e.rig.root) == before


@pytest.mark.parametrize('alias', [False, True])
def test_project_authority_and_revocation_still_precede_status(rig, alias):
    scope, headers = shared_scope(rig)
    rig.seed('fixture.wav', 'audio', scope_value=scope)
    url = f"/api{'/v1' if alias else ''}/projects/{rig.nid}/studio/storage"
    before = snapshot(rig.root)
    denied = rig.client.get(url, headers={**headers, 'X-Session-Token': 'token-no-grants'})
    assert denied.status_code == 403
    allowed = rig.client.get(url, headers=headers)
    assert allowed.status_code == 200
    assert allowed.json()['admission']['state'] == 'UNAVAILABLE'
    rig.sessions.revoke(headers['X-Session-Token'])
    assert rig.client.get(url, headers=headers).status_code in (401, 403)
    assert snapshot(rig.root) == before

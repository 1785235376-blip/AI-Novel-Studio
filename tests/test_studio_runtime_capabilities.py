"""Machine-readable runtime boundaries over the original guarded API."""
import hashlib

import pytest

from app.creative import asset_query_cursor
from test_studio_asset_query import rig, shared_scope


def snapshot(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob('*') if path.is_file()}


def test_runtime_capabilities_are_read_only_and_do_not_change_existing_catalog(rig):
    rig.workspace.activate(rig.nid, rig.scope, 'local-author')
    path = f'/projects/{rig.nid}/studio/production-contracts'
    original = rig.client.get('/api' + path)
    assert original.status_code == 200
    before = snapshot(rig.root)
    first = rig.client.get('/api' + path + '/runtime')
    second = rig.client.get('/api/v1' + path + '/runtime')
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    value = first.json()
    assert value['contract'] == 'studio-runtime-capabilities/1'
    assert value['project_id'] == rig.nid
    assert value['audio_asset_history'] == {'version_history_read': 'UNAVAILABLE', 'version_restore': 'UNAVAILABLE'}
    primitive = (asset_query_cursor.posix_signing_primitives_available()
                 or asset_query_cursor.windows_dpapi_available())
    assert value['asset_query_cursor']['key_primitives'] == ('PRESENT' if primitive else 'UNAVAILABLE')
    assert value['asset_query_cursor']['end_to_end'] == ('NOT_VERIFIED' if primitive else 'UNSUPPORTED')
    assert value['model_inference_acceptance'] == 'NOT_EVALUATED'
    assert first.headers['cache-control'] == 'no-store'
    assert snapshot(rig.root) == before
    assert rig.client.get('/api' + path).json() == original.json()


def test_runtime_capability_requires_active_membership(rig):
    from app.identity import IdentityStatus
    scope, headers = shared_scope(rig)
    rig.workspace.activate(rig.nid, scope, 'reader')
    path = f'/api/projects/{rig.nid}/studio/production-contracts/runtime'
    response = rig.client.get(path, headers=headers)
    assert response.status_code == 200, response.text
    rig.identities.set_membership_status('reader', 'query-workspace', IdentityStatus.INACTIVE)
    denied = rig.client.get(path, headers=headers)
    assert denied.status_code == 403
    assert 'studio-runtime-capabilities/1' not in denied.text


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_membership_revoked_during_observation_never_returns_capabilities(rig, monkeypatch, prefix):
    from app.creative import production_contract_api
    from app.identity import IdentityStatus
    scope, headers = shared_scope(rig)
    rig.workspace.activate(rig.nid, scope, 'reader')
    def revoke():
        rig.identities.set_membership_status('reader', 'query-workspace', IdentityStatus.INACTIVE)
        return False
    monkeypatch.setattr(production_contract_api, 'signing_key_primitives_available', revoke)
    response = rig.client.get(f'{prefix}/projects/{rig.nid}/studio/production-contracts/runtime', headers=headers)
    assert response.status_code == 403
    assert 'studio-runtime-capabilities/1' not in response.text


def test_only_exact_get_routes_are_admitted():
    from app.creative.workspace_api import is_independent_studio_route
    root = '/api/projects/example/studio/production-contracts'
    assert is_independent_studio_route('GET', root)
    assert is_independent_studio_route('GET', root + '/runtime')
    assert not is_independent_studio_route('GET', root + '/runtime/extra')
    assert not is_independent_studio_route('POST', root + '/runtime')


def test_runtime_schema_is_closed_and_never_claims_model_acceptance():
    from pydantic import ValidationError
    from app.creative.production_contract_api import StudioRuntimeCapabilities
    valid = {'project_id': 'p', 'asset_query_cursor': {'key_primitives': 'UNAVAILABLE', 'end_to_end': 'UNSUPPORTED'}}
    assert StudioRuntimeCapabilities.model_validate(valid).model_inference_acceptance == 'NOT_EVALUATED'
    with pytest.raises(ValidationError):
        StudioRuntimeCapabilities.model_validate({**valid, 'unexpected': True})
    with pytest.raises(ValidationError):
        StudioRuntimeCapabilities.model_validate({**valid, 'model_inference_acceptance': 'PASSED'})


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_feature_disabled_during_read_withholds_response(rig, monkeypatch, prefix):
    from app.creative import production_contract_api
    rig.workspace.activate(rig.nid, rig.scope, 'local-author')
    def disable():
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
        return False
    monkeypatch.setattr(production_contract_api, 'signing_key_primitives_available', disable)
    response = rig.client.get(f'{prefix}/projects/{rig.nid}/studio/production-contracts/runtime')
    assert response.status_code == 404
    assert 'studio-runtime-capabilities/1' not in response.text


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_foreign_project_is_not_visible_to_actor(rig, prefix):
    scope, headers = shared_scope(rig)
    rig.workspace.activate(rig.nid, scope, 'reader')
    other = rig.project()
    response = rig.client.get(f'{prefix}/projects/{other}/studio/production-contracts/runtime', headers=headers)
    assert response.status_code == 403
    assert 'studio-runtime-capabilities/1' not in response.text


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_recreated_project_needs_new_activation(rig, prefix):
    rig.workspace.activate(rig.nid, rig.scope, 'local-author')
    old_incarnation = rig.workspace.store.incarnation(rig.nid)
    path = f'{prefix}/projects/{rig.nid}/studio/production-contracts/runtime'
    assert rig.client.get(path).status_code == 200
    rig.novels.delete(rig.nid)
    rig.project(rig.nid)
    assert rig.workspace.store.incarnation(rig.nid) != old_incarnation
    response = rig.client.get(path)
    assert response.status_code == 409
    assert 'studio-runtime-capabilities/1' not in response.text


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_project_recreated_during_read_never_returns_old_observation(rig, monkeypatch, prefix):
    from app.creative import production_contract_api
    rig.workspace.activate(rig.nid, rig.scope, 'local-author')
    old_incarnation = rig.workspace.store.incarnation(rig.nid)
    def replace_project():
        rig.novels.delete(rig.nid)
        rig.project(rig.nid)
        assert rig.workspace.store.incarnation(rig.nid) != old_incarnation
        return False
    monkeypatch.setattr(production_contract_api, 'signing_key_primitives_available', replace_project)
    response = rig.client.get(f'{prefix}/projects/{rig.nid}/studio/production-contracts/runtime')
    assert response.status_code == 403
    assert 'studio-runtime-capabilities/1' not in response.text

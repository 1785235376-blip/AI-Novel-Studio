"""Independent mounted File GET checks, synthetic fixtures only."""
import hashlib
import pytest

from test_audio_history_status_readonly import snapshot
from test_studio_asset_query import rig, shared_scope

pytestmark = pytest.mark.file_backend_only


@pytest.mark.parametrize('alias', [False, True])
@pytest.mark.parametrize('missing', ['asset_lock', 'marker'])
def test_denied_actor_does_not_learn_missing_internal_facility(rig, alias, missing):
    scope, headers = shared_scope(rig)
    asset = rig.seed('synthetic.wav', 'audio', scope_value=scope)
    rig.workspace.store.incarnation(rig.nid)
    if missing == 'marker':
        path = rig.root / 'novels' / rig.nid / 'creative_project_v2.json'
    else:
        path = rig.assets.root / '.workspace-mutation-locks' / (hashlib.sha256(b'asset-library').hexdigest() + '.lock')
    assert path.is_file()
    path.unlink()
    before = snapshot(rig.root)
    url = f"/api{'/v1' if alias else ''}/projects/{rig.nid}/studio/storage"
    denied = rig.client.get(url, headers={**headers, 'X-Session-Token': 'token-no-grants'})
    assert denied.status_code == 403, denied.text
    assert asset['id'] not in denied.text
    assert snapshot(rig.root) == before
    assert not path.exists()


@pytest.mark.parametrize('alias', [False, True])
def test_storage_observation_preserves_existing_asset_listing(rig, alias):
    row = rig.seed('synthetic.wav', 'audio')
    rig.workspace.store.incarnation(rig.nid)
    before = snapshot(rig.root)
    prefix = f"/api{'/v1' if alias else ''}/projects/{rig.nid}/studio"
    storage = rig.client.get(prefix + '/storage')
    assert storage.status_code == 200, storage.text
    assert storage.json()['assets']['count'] == 1
    assert snapshot(rig.root) == before
    # The separate legacy assets GET may create its query index; only the
    # storage observation has the strict no-write contract under test here.
    listed = rig.client.get(prefix + '/assets')
    assert listed.status_code == 200, listed.text
    assert row['id'] in [entry['id'] for entry in listed.json()['items']]


@pytest.mark.parametrize('alias', [False, True])
def test_membership_revoked_during_observation(rig, alias, monkeypatch):
    from app.identity import IdentityStatus
    from concurrent.futures import ThreadPoolExecutor
    scope, headers = shared_scope(rig)
    rig.seed('synthetic.wav', 'audio', scope_value=scope)
    rig.workspace.store.incarnation(rig.nid)
    original = rig.assets.list
    def revoke(*args, **kwargs):
        rows = original(*args, **kwargs)
        # A separate actor does not inherit the observing request's strict
        # read-only ContextVar. Propagate failures instead of faking revocation.
        with ThreadPoolExecutor(max_workers=1) as executor:
            executor.submit(rig.identities.set_membership_status, 'reader', 'query-workspace',
                            IdentityStatus.INACTIVE).result(timeout=5)
        return rows
    monkeypatch.setattr(rig.assets, 'list', revoke)
    url = f"/api{'/v1' if alias else ''}/projects/{rig.nid}/studio/storage"
    response = rig.client.get(url, headers=headers)
    assert response.status_code in (401, 403), response.text
    assert 'assets' not in response.json()

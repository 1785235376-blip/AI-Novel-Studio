import pytest
import threading
from test_studio_asset_query import rig, shared_scope
from app.identity import IdentityStatus

def setup_shared(rig):
    scope, headers = shared_scope(rig)
    asset = rig.seed('synthetic.wav', 'audio', scope_value=scope)
    url = f'/api/projects/{rig.nid}/studio/assets/{asset["id"]}'
    warm = rig.client.get(url, headers=headers)
    assert warm.status_code == 200, warm.text
    return scope, headers, asset, url

def test_expired_session_matches_existing_asset_contract(rig):
    _, headers, asset, url = setup_shared(rig)
    headers = {**headers, 'X-Session-Token': 'invalid-token'}
    old = rig.client.get(url, headers=headers)
    new = rig.client.get(url + '/history', headers=headers)
    assert old.status_code == 401, old.text
    assert new.status_code == old.status_code, (old.status_code, old.text, new.status_code, new.text)

def test_membership_revoked_during_read(rig, monkeypatch):
    _, headers, asset, url = setup_shared(rig)
    warm_history = rig.client.get(url + '/history', headers=headers)
    assert warm_history.status_code == 200, warm_history.text
    original = rig.assets.content
    def revoked(*args, **kwargs):
        result = original(*args, **kwargs)
        thread = threading.Thread(target=lambda: rig.identities.set_membership_status('reader', 'query-workspace', IdentityStatus.INACTIVE))
        thread.start()
        thread.join(10)
        assert not thread.is_alive()
        return result
    monkeypatch.setattr(rig.assets, 'content', revoked)
    response = rig.client.get(url + '/history', headers=headers)
    assert response.status_code in (401, 403), response.text
    assert 'UNCAPTURED' not in response.text



def test_membership_revoke_then_regrant_during_observation(rig, monkeypatch):
    _, headers, asset, url = setup_shared(rig)
    assert rig.client.get(url + '/history', headers=headers).status_code == 200
    original = rig.assets.content
    def toggled(*args, **kwargs):
        result = original(*args, **kwargs)
        def change():
            rig.identities.set_membership_status('reader', 'query-workspace', IdentityStatus.INACTIVE)
            rig.identities.set_membership_status('reader', 'query-workspace', IdentityStatus.ACTIVE)
        thread = threading.Thread(target=change)
        thread.start()
        thread.join(10)
        assert not thread.is_alive()
        return result
    monkeypatch.setattr(rig.assets, 'content', toggled)
    response = rig.client.get(url + '/history', headers=headers)
    assert response.status_code != 200, response.text

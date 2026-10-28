"""Mounted, synthetic File status observations; no history writes."""
import hashlib
import json
import asyncio

import pytest

from test_studio_asset_query import rig
from test_studio_workspace_identity_history_contract import audio_history


def snapshot(root):
    return {str(p.relative_to(root)): ("dir" if p.is_dir() else hashlib.sha256(p.read_bytes()).hexdigest())
            for p in root.rglob("*")}


def url(e, *, alias=False, project=None, asset=None):
    prefix = "/api/v1" if alias else "/api"
    return f"{prefix}/projects/{project or e.rig.nid}/studio/assets/{asset or e.asset['id']}/history"


@pytest.mark.parametrize("alias", [False, True])
def test_uncaptured_status_is_private_read_only_and_verifies_bytes(audio_history, alias):
    e = audio_history
    before = snapshot(e.rig.root)
    response = e.client.get(url(e, alias=alias), headers=e.headers)
    assert response.status_code == 200, response.text
    assert response.json() == {"asset_id": e.asset['id'], "current_version": 1, "head": None,
                               "coverage": "UNCAPTURED", "items": [], "next_cursor": None}
    assert response.headers["cache-control"] == "no-store"
    assert snapshot(e.rig.root) == before
    assert not (e.rig.assets.root / ".audio-history").exists()


@pytest.mark.parametrize("marker", ["_audio_history_head", "_audio_history_restore_origin"])
def test_published_marker_is_not_misrepresented_as_uncaptured(audio_history, marker):
    e = audio_history
    path = e.rig.assets._meta_path(e.asset['id'])
    row = json.loads(path.read_text(encoding="utf-8"))
    row[marker] = "a" * 64
    path.write_text(json.dumps(row), encoding="utf-8")
    before = snapshot(e.rig.root)
    response = e.client.get(url(e), headers=e.headers)
    assert response.status_code == 409, response.text
    assert response.json()['detail']['code'] == 'AUDIO_HISTORY_FORMAT_NOT_INTEGRATED'
    assert snapshot(e.rig.root) == before


@pytest.mark.parametrize("failure", ["missing", "corrupt"])
def test_damaged_current_bytes_are_not_presented_as_a_baseline(audio_history, failure):
    e = audio_history
    path = e.rig.assets._bin_path(e.asset['id'])
    if failure == "missing":
        path.unlink()
    else:
        path.write_bytes(b"corrupt synthetic bytes")
    before = snapshot(e.rig.root)
    response = e.client.get(url(e), headers=e.headers)
    assert response.status_code == 409, response.text
    assert response.json()['detail']['code'] == 'AUDIO_HISTORY_CONTENT_UNAVAILABLE'
    assert snapshot(e.rig.root) == before


def test_scope_and_private_owner_are_not_bypassed(audio_history):
    e = audio_history
    other = e.rig.project()
    assert e.client.get(url(e, project=other), headers=e.headers).status_code == 404
    private = e.rig.seed("private.wav", "audio", owner="different-actor")
    assert e.client.get(url(e, asset=private['id']), headers=e.headers).status_code == 404


def test_revocation_during_content_check_prevents_return(audio_history, monkeypatch):
    e = audio_history
    content = e.rig.assets.content
    def revoked(*args, **kwargs):
        result = content(*args, **kwargs)
        e.rig.sessions.revoke(e.headers['X-Session-Token'])
        return result
    monkeypatch.setattr(e.rig.assets, 'content', revoked)
    before = snapshot(e.rig.root)
    response = e.client.get(url(e), headers=e.headers)
    assert response.status_code in (401, 403), response.text
    assert 'UNCAPTURED' not in response.text
    assert snapshot(e.rig.root) == before


@pytest.mark.parametrize("alias", [False, True])
def test_missing_original_lock_is_not_initialized(audio_history, alias):
    e = audio_history
    lock = e.rig.assets.root / '.workspace-mutation-locks' / (
        hashlib.sha256(b'asset-library').hexdigest() + '.lock')
    assert lock.is_file()
    lock.unlink()
    before = snapshot(e.rig.root)
    response = e.client.get(url(e, alias=alias), headers=e.headers)
    assert response.status_code == 409, response.text
    assert response.json()['detail']['code'] == 'AUDIO_HISTORY_READ_ONLY_UNAVAILABLE'
    assert snapshot(e.rig.root) == before
    assert not lock.exists()


def test_same_session_reregistered_during_read_is_stale(audio_history, monkeypatch):
    from app.actor_context import SessionContext
    e = audio_history
    content = e.rig.assets.content
    def replaced(*args, **kwargs):
        result = content(*args, **kwargs)
        token = e.headers['X-Session-Token']
        e.rig.sessions.revoke(token)
        e.rig.sessions.register(token, SessionContext(
            'history-session', 'history-client', 'local-author', 'history-workspace'))
        return result
    monkeypatch.setattr(e.rig.assets, 'content', replaced)
    before = snapshot(e.rig.root)
    response = e.client.get(url(e), headers=e.headers)
    assert response.status_code == 403, response.text
    assert 'UNCAPTURED' not in response.text
    assert snapshot(e.rig.root) == before


def test_feature_revocation_during_content_check_prevents_return(audio_history, monkeypatch):
    e = audio_history
    content = e.rig.assets.content
    def revoked(*args, **kwargs):
        result = content(*args, **kwargs)
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
        return result
    monkeypatch.setattr(e.rig.assets, 'content', revoked)
    before = snapshot(e.rig.root)
    response = e.client.get(url(e), headers=e.headers)
    assert response.status_code != 200, response.text
    assert 'UNCAPTURED' not in response.text
    assert snapshot(e.rig.root) == before


def test_cancelled_content_read_does_not_mutate_or_return_status(audio_history, monkeypatch):
    e = audio_history
    def cancelled(*args, **kwargs):
        raise asyncio.CancelledError()
    monkeypatch.setattr(e.rig.assets, 'content', cancelled)
    before = snapshot(e.rig.root)
    # Starlette's BaseHTTPMiddleware translates the injected cancellation into
    # this no-response error in TestClient; it must not emit a success result.
    with pytest.raises(RuntimeError, match="No response returned"):
        e.client.get(url(e), headers=e.headers)
    assert snapshot(e.rig.root) == before

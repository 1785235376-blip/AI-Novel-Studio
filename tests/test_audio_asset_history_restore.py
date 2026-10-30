"""Explicit audio history restore: new traceable current revision (flag-gated).

Product decision under test: confirming a target history version appends a new
current revision that keeps the old chain, restores only reversible
display/authoring fields, never inherits the target's review/approval/
provenance, and binds the confirmation to current version + target metadata
digest. Restore stays behind ENABLE_AUDIO_ASSET_HISTORY and commit authority;
these are File synthetic tests (no models, no PG).
"""
from __future__ import annotations

import concurrent.futures

import pytest

from app.config import settings
from test_audio_history_status_readonly import snapshot
from test_studio_asset_query import rig
from test_studio_workspace_identity_history_contract import audio_history

pytestmark = pytest.mark.file_backend_only


@pytest.fixture
def history_on():
    previous = settings.enable_audio_asset_history
    object.__setattr__(settings, "enable_audio_asset_history", True)
    try:
        yield
    finally:
        object.__setattr__(settings, "enable_audio_asset_history", previous)


def create_captured(e):
    import base64
    with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
        return e.rig.assets.create(e.rig.nid, "restore-api.wav",
                                   base64.b64encode(e.content).decode(), "audio/wav", "audio",
                                   required_features=("narrative_production_v2",))


def update(e, asset_id, fields):
    with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
        return e.rig.assets.update_metadata(asset_id, fields)


def history_url(e, asset_id, extra=""):
    return f"/api/v1/projects/{e.rig.nid}/studio/assets/{asset_id}/history{extra}"


def preview(e, asset_id, version_id):
    return e.client.post(history_url(e, asset_id, f"/{version_id}/restore/preview"),
                         headers=e.headers, json={"expected_version": 3})


def build_three_versions(e):
    asset = create_captured(e)  # version 1
    update(e, asset["id"], {"character_id": "char-old", "parameters": {"tone": "warm"},
                            "approved_at": "2026-10-01T00:00:00+00:00"})  # version 2
    update(e, asset["id"], {"character_id": "char-new", "parameters": {"tone": "cool"},
                            "approved_at": None})  # version 3
    listing = e.client.get(history_url(e, asset["id"]), headers=e.headers).json()
    assert [item["asset_version"] for item in listing["items"]] == [3, 2, 1]
    target = listing["items"][1]["version_id"]
    assert target == listing["items"][1]["version_id"]
    return asset, target


def test_preview_binds_plan_without_writing(audio_history, history_on):
    e = audio_history
    asset, target = build_three_versions(e)
    before = snapshot(e.rig.root)
    response = preview(e, asset["id"], target)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["contract"] == "studio-audio-history-restore-preview/1"
    assert result["current_version"] == 3 and result["expected_new_version"] == 4
    assert set(result["restored_fields"]) <= {"filename", "parameters", "character_id", "scene_id"}
    assert "character_id" in result["restored_fields"]
    assert result["review_inherited"] is False
    assert len(result["restore_digest"]) == 64
    assert result["restore_available"] is True
    assert snapshot(e.rig.root) == before
    listing = e.client.get(history_url(e, asset["id"]), headers=e.headers).json()
    assert len(listing["items"]) == 3


def test_confirm_appends_traceable_current_version(audio_history, history_on):
    e = audio_history
    asset, target = build_three_versions(e)
    plan = preview(e, asset["id"], target).json()
    response = e.client.post(history_url(e, asset["id"], f"/{target}/restore"), headers=e.headers,
                             json={"expected_version": 3,
                                   "expected_restore_digest": plan["restore_digest"]})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["contract"] == "audio-asset-history-restore/1"
    assert result["current_version"] == 4 and result["new_current_version"] == 4
    assert result["restore_origin"]["target_version_id"] == target
    assert result["restore_origin"]["review_inherited"] is False
    listing = e.client.get(history_url(e, asset["id"]), headers=e.headers).json()
    assert [item["asset_version"] for item in listing["items"]] == [4, 3, 2, 1]
    with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
        meta = e.rig.assets._load(asset["id"])
    assert meta["version"] == 4
    assert meta["character_id"] == "char-old"
    assert meta["parameters"] == {"tone": "warm"}
    assert meta["_audio_history_restore_origin"]["target_version_id"] == target
    # Review/approval is not inherited from the target record.
    assert meta.get("approved_at") is None


def test_stale_confirmation_and_wrong_digest_fail_without_write(audio_history, history_on):
    e = audio_history
    asset, target = build_three_versions(e)
    plan = preview(e, asset["id"], target).json()
    body = {"expected_version": 3, "expected_restore_digest": plan["restore_digest"]}
    assert e.client.post(history_url(e, asset["id"], f"/{target}/restore"),
                         headers=e.headers, json=body).status_code == 200
    before = snapshot(e.rig.root)
    stale = e.client.post(history_url(e, asset["id"], f"/{target}/restore"),
                          headers=e.headers, json=body)
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "AUDIO_HISTORY_VERSION_CONFLICT"
    refreshed = e.client.get(history_url(e, asset["id"]), headers=e.headers).json()
    wrong = {"expected_version": refreshed["current_version"],
             "expected_restore_digest": "0" * 64}
    invalid = e.client.post(history_url(e, asset["id"], f"/{target}/restore"),
                            headers=e.headers, json=wrong)
    assert invalid.status_code == 409
    assert invalid.json()["detail"]["code"] == "AUDIO_HISTORY_RESTORE_PLAN_CHANGED"
    assert snapshot(e.rig.root) == before


def test_concurrent_confirm_only_one_append(audio_history, history_on):
    e = audio_history
    asset, target = build_three_versions(e)
    plan = preview(e, asset["id"], target).json()
    body = {"expected_version": 3, "expected_restore_digest": plan["restore_digest"]}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(e.client.post, history_url(e, asset["id"], f"/{target}/restore"),
                               headers=e.headers, json=body) for _ in range(2)]
        responses = [future.result() for future in futures]
    codes = sorted(response.status_code for response in responses)
    assert codes == [200, 409], [(response.status_code, response.text) for response in responses]
    listing = e.client.get(history_url(e, asset["id"]), headers=e.headers).json()
    assert [item["asset_version"] for item in listing["items"]] == [4, 3, 2, 1]


def test_restore_requires_flag_captured_chain_and_known_target(audio_history):
    e = audio_history
    disabled = e.client.post(history_url(e, e.asset["id"], "/" + "0" * 64 + "/restore/preview"),
                             headers=e.headers, json={"expected_version": 1})
    assert disabled.status_code == 409
    assert disabled.json()["detail"]["code"] == "AUDIO_HISTORY_UNAVAILABLE"
    object.__setattr__(settings, "enable_audio_asset_history", True)
    try:
        uncaptured = e.client.post(history_url(e, e.asset["id"], "/" + "0" * 64 + "/restore/preview"),
                                   headers=e.headers, json={"expected_version": 1})
        assert uncaptured.status_code == 409
        assert uncaptured.json()["detail"]["code"] == "AUDIO_HISTORY_UNCAPTURED"
        asset = create_captured(e)
        unknown = e.client.post(history_url(e, asset["id"], "/" + "0" * 64 + "/restore/preview"),
                                headers=e.headers, json={"expected_version": 1})
        assert unknown.status_code == 409
        assert unknown.json()["detail"]["code"] == "AUDIO_HISTORY_VERSION_NOT_IN_CHAIN"
    finally:
        object.__setattr__(settings, "enable_audio_asset_history", False)


def test_restore_crash_before_current_commit_leaves_chain_unchanged(audio_history, history_on, monkeypatch):
    e = audio_history
    asset, target = build_three_versions(e)
    plan = preview(e, asset["id"], target).json()
    import app.services.asset_library_service as owner
    original = owner.atomic_write
    calls = {"count": 0}

    def failing(path, value):
        calls["count"] += 1
        raise OSError("synthetic crash before current metadata commit")
    monkeypatch.setattr(owner, "atomic_write", failing)
    with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
        with pytest.raises(OSError):
            e.rig.assets.restore_audio_history(
                asset["id"], branch_id=None, target_version_id=target, expected_version=3,
                expected_plan_digest=plan["restore_digest"], actor_id="local-author")
    assert calls["count"] >= 1
    monkeypatch.setattr(owner, "atomic_write", original)
    listing = e.client.get(history_url(e, asset["id"]), headers=e.headers).json()
    assert [item["asset_version"] for item in listing["items"]] == [3, 2, 1]
    retry = e.client.post(history_url(e, asset["id"], f"/{target}/restore"), headers=e.headers,
                          json={"expected_version": 3,
                                "expected_restore_digest": plan["restore_digest"]})
    assert retry.status_code == 200, retry.text


def test_restore_routes_are_allowlisted():
    from app.creative.workspace_api import is_independent_studio_route
    root = "/api/projects/example/studio"
    version = "a" * 64
    assert is_independent_studio_route("POST", root + f"/assets/asset/history/{version}/restore")
    assert is_independent_studio_route("POST", root + f"/assets/asset/history/{version}/restore/preview")
    assert not is_independent_studio_route("GET", root + f"/assets/asset/history/{version}/restore")
    assert not is_independent_studio_route("POST", root + "/assets/asset/history/not-a-digest/restore")

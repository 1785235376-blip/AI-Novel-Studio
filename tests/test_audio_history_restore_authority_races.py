"""Audio history restore: authority/revocation/recreate/concurrency races.

Reads never migrate; restore append must fail closed when the session is
revoked, the project incarnation is recreated, or another writer wins the
version CAS. Synthetic File tests only.
"""
from __future__ import annotations

import concurrent.futures

import pytest

from app.config import settings
from test_audio_history_status_readonly import snapshot
from test_audio_asset_history_restore import (
    build_three_versions,
    create_captured,
    history_on,
    history_url,
    preview,
)
from test_studio_asset_query import rig
from test_studio_workspace_identity_history_contract import audio_history

pytestmark = pytest.mark.file_backend_only


def token_of(e):
    return e.headers["X-Session-Token"]


def test_recreated_project_incarnation_cannot_confirm_restore(audio_history, history_on):
    e = audio_history
    asset, target = build_three_versions(e)
    plan = preview(e, asset["id"], target).json()
    confirmed = {"expected_version": 3, "expected_restore_digest": plan["restore_digest"]}
    old_incarnation = e.rig.workspace.store.incarnation(e.rig.nid)
    e.rig.novels.delete(e.rig.nid)
    e.rig.project(e.rig.nid)
    assert e.rig.workspace.store.incarnation(e.rig.nid) != old_incarnation
    before = snapshot(e.rig.root)
    response = e.client.post(history_url(e, asset["id"], f"/{target}/restore"),
                             headers=e.headers, json=confirmed)
    assert response.status_code in {404, 409}, response.text
    assert snapshot(e.rig.root) == before


def test_concurrent_restore_and_metadata_edit_append_exactly_one_version(audio_history, history_on):
    e = audio_history
    asset, target = build_three_versions(e)
    plan = preview(e, asset["id"], target).json()
    confirmed = {"expected_version": 3, "expected_restore_digest": plan["restore_digest"]}

    def post_restore():
        return ("restore", e.client.post(history_url(e, asset["id"], f"/{target}/restore"),
                                         headers=e.headers, json=confirmed))

    def edit_metadata():
        from app.services.v1_capability_service import CapabilityVersionConflict
        with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
            try:
                e.rig.assets.update_metadata(asset["id"],
                                             {"approved_at": "2026-10-31T00:00:00+00:00"},
                                             expected_version=3)
                return ("edit", None)
            except CapabilityVersionConflict as exc:
                return ("edit-conflict", exc)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        restore_future = pool.submit(post_restore)
        edit_future = pool.submit(edit_metadata)
        restore_kind, restore_response = restore_future.result()
        edit_kind, edit_result = edit_future.result()
    restore_ok = restore_response.status_code == 200
    edit_ok = edit_kind == "edit"
    assert [restore_ok, edit_ok].count(True) == 1, (
        restore_response.status_code, restore_response.text if restore_response is not None else "",
        edit_kind, edit_result)
    listing = e.client.get(history_url(e, asset["id"]), headers=e.headers).json()
    assert [item["asset_version"] for item in listing["items"]] == [4, 3, 2, 1]
    with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
        meta = e.rig.assets._load(asset["id"])
    assert meta["version"] == 4
    if restore_ok:
        assert meta["_audio_history_restore_origin"]["target_version_id"] == target
    else:
        assert restore_response.status_code == 409
        assert restore_response.json()["detail"]["code"] == "AUDIO_HISTORY_VERSION_CONFLICT"
        assert "_audio_history_restore_origin" not in meta


def test_preview_does_not_leak_restore_after_flag_disabled(audio_history):
    e = audio_history
    previous = settings.enable_audio_asset_history
    object.__setattr__(settings, "enable_audio_asset_history", True)
    try:
        asset, target = build_three_versions(e)
    finally:
        object.__setattr__(settings, "enable_audio_asset_history", previous)
    before = snapshot(e.rig.root)
    response = e.client.post(history_url(e, asset["id"], f"/{target}/restore/preview"),
                             headers=e.headers, json={"expected_version": 3})
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "AUDIO_HISTORY_UNAVAILABLE"
    assert snapshot(e.rig.root) == before


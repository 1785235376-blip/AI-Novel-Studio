"""Audio history read API and explicit migration (flag-gated, File synthetic).

Reads never migrate: a legacy uncaptured asset returns UNCAPTURED without
writing anything, and the only way to create its baseline history is the
explicit migrate POST (authority + CAS + content digest verification). The
restore write endpoint stays unavailable in this part.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.config import settings
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


def url(e, suffix, version_id=None, alias=True):
    prefix = "/api/v1" if alias else "/api"
    base = f"{prefix}/projects/{e.rig.nid}/studio/assets"
    return base + suffix


def history_url(e, asset_id, alias=True, extra=""):
    return url(e, f"/{asset_id}/history{extra}", alias=alias)


def create_captured(e):
    with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
        row = e.rig.assets.create(e.rig.nid, "history-api.wav",
                                  __import__("base64").b64encode(e.content).decode(),
                                  "audio/wav", "audio",
                                  required_features=("narrative_production_v2",))
    return row


@pytest.mark.parametrize("alias", [False, True])
def test_captured_history_lists_versions_newest_first(audio_history, history_on, alias):
    e = audio_history
    asset = create_captured(e)
    with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
        e.rig.assets.update_metadata(asset["id"], {"approved_at": "2026-10-31T00:00:00+00:00"})
    response = e.client.get(history_url(e, asset["id"], alias), headers=e.headers)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["coverage"] == "CAPTURED" and result["asset_id"] == asset["id"]
    assert result["current_version"] == 2 and len(result["items"]) == 2
    assert [item["asset_version"] for item in result["items"]] == [2, 1]

    assert result["next_cursor"] is None
    assert "metadata" in result["items"][0]
    assert set(result["items"][0]["metadata"]) == {"kind", "media_type", "deleted", "historically_approved"}


def test_history_query_limits_and_cursor(audio_history, history_on):
    e = audio_history
    asset = create_captured(e)
    base = history_url(e, asset["id"])
    for query, status in (("?limit=1", 200), ("?limit=0", 422), ("?limit=51", 422),
                          ("?limit=x", 422), ("?cursor=abc", 409)):
        response = e.client.get(base + query, headers=e.headers)
        assert response.status_code == status, (query, response.text)
        if query == "?cursor=abc":
            assert response.json()["detail"]["code"] == "AUDIO_HISTORY_CURSOR_UNAVAILABLE"
    with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
        e.rig.assets.update_metadata(asset["id"], {"approved_at": "2026-10-31T00:00:00+00:00"})
    too_many = e.client.get(base + "?limit=1", headers=e.headers)
    assert too_many.status_code == 409
    assert too_many.json()["detail"]["code"] == "AUDIO_HISTORY_CURSOR_UNAVAILABLE"


def test_history_detail_and_download(audio_history, history_on):
    e = audio_history
    asset = create_captured(e)
    listing = e.client.get(history_url(e, asset["id"]), headers=e.headers).json()
    item = listing["items"][0]
    detail = e.client.get(history_url(e, asset["id"], extra="/" + item["version_id"]), headers=e.headers)
    assert detail.status_code == 200, detail.text
    assert detail.json() == item
    download = e.client.get(history_url(e, asset["id"], extra="/" + item["version_id"] + "/download"),
                            headers=e.headers)
    assert download.status_code == 200, download.text
    assert download.content == e.content
    assert download.headers["X-Asset-SHA256"] == item["sha256"]
    assert download.headers["X-History-Version-Id"] == item["version_id"]
    missing = e.client.get(history_url(e, asset["id"], extra="/" + "0" * 64), headers=e.headers)
    assert missing.status_code == 409
    assert missing.json()["detail"]["code"] == "AUDIO_HISTORY_VERSION_NOT_IN_CHAIN"


def test_legacy_read_is_uncaptured_and_does_not_migrate(audio_history, history_on):
    e = audio_history
    marker = Path(e.rig.assets.root) / ".audio-history" / e.asset["id"]
    response = e.client.get(history_url(e, e.asset["id"]), headers=e.headers)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["coverage"] == "UNCAPTURED" and result["items"] == [] and result["head"] is None
    assert not marker.exists()


def test_explicit_migration_then_second_attempt_is_idempotent_conflict(audio_history, history_on):
    e = audio_history
    base = history_url(e, e.asset["id"], extra="/migrate")
    migrated = e.client.post(base, headers=e.headers, json={"expected_version": e.asset["version"]})
    assert migrated.status_code == 200, migrated.text
    result = migrated.json()
    assert result["contract"] == "audio-asset-history/capture/1"
    assert result["coverage"] == "CAPTURED" and result["migrated"] is True
    listing = e.client.get(history_url(e, e.asset["id"]), headers=e.headers).json()
    assert listing["coverage"] == "CAPTURED" and len(listing["items"]) == 1
    again = e.client.post(base, headers=e.headers, json={"expected_version": e.asset["version"]})
    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "AUDIO_HISTORY_ALREADY_CAPTURED"


def test_explicit_migration_cas_and_unavailable_when_flag_off(audio_history):
    e = audio_history
    disabled = e.client.post(history_url(e, e.asset["id"], extra="/migrate"),
                             headers=e.headers, json={"expected_version": e.asset["version"]})
    assert disabled.status_code == 409
    assert disabled.json()["detail"]["code"] == "AUDIO_HISTORY_UNAVAILABLE"
    object.__setattr__(settings, "enable_audio_asset_history", True)
    try:
        stale = e.client.post(history_url(e, e.asset["id"], extra="/migrate"),
                              headers=e.headers, json={"expected_version": e.asset["version"] + 5})
        assert stale.status_code == 409
        assert stale.json()["detail"]["code"] == "AUDIO_HISTORY_VERSION_CONFLICT"
        assert not (Path(e.rig.assets.root) / ".audio-history" / e.asset["id"]).exists()
    finally:
        object.__setattr__(settings, "enable_audio_asset_history", False)


def test_history_routes_and_query_are_allowlisted():
    from app.creative.workspace_api import is_independent_studio_route
    root = "/api/projects/example/studio"
    version = "a" * 64
    assert is_independent_studio_route("GET", root + f"/assets/asset/history/{version}")
    assert is_independent_studio_route("GET", root + f"/assets/asset/history/{version}/download")
    assert is_independent_studio_route("POST", root + "/assets/asset/history/migrate")
    assert not is_independent_studio_route("GET", root + "/assets/asset/history/not-a-digest")
    assert not is_independent_studio_route("POST", root + "/assets/asset/history/migrate/extra")


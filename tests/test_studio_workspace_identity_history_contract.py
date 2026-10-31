"""Existing File/HTTP identity and audio-history contracts, without execution.

Synthetic WAV bytes exercise the original Asset owner and Timeline metadata
routes. No provider, media probe, FFmpeg render, candidate review or new owner
is used. Mounted routing and Host/domain authorization remain real.
"""
import base64
from copy import deepcopy
import io
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID
import wave

import pytest

from app.actor_context import SessionContext
from app.audio_production_store import AudioProductionStore
from app.asset_providers import AssetProviderRegistry
from app.creative.production_execution import ProductionExecutionService
from app.experimental import api as experimental_api
from app.services.image_job_service import ImageJobService
from app.services.video_assembly_service import VideoAssemblyService
from test_studio_asset_query import rig


pytestmark = pytest.mark.file_backend_only


class NoExternalCalls:
    def __getattr__(self, name):
        raise AssertionError("History contract tests must not call " + name)


@pytest.fixture
def audio_history(rig, monkeypatch):
    from app import media_files
    from app.services import studio_timeline_export, studio_timeline_render

    production = ProductionExecutionService(rig.workspace,
        ImageJobService(rig.root / "history-image-jobs"), AssetProviderRegistry(),
        VideoAssemblyService(rig.root / "history-video-jobs", rig.assets), {}, {},
        AudioProductionStore(rig.root / "history-audio-jobs"), NoExternalCalls(), NoExternalCalls())
    mounted = experimental_api.studio_production_service
    for name, value in production.__dict__.items():
        monkeypatch.setattr(mounted, name, value, raising=False)
    forbidden = []
    for name in ("create", "execute", "review", "timeline_render", "timeline_export"):
        sentinel = Mock(side_effect=AssertionError("History metadata must not call " + name))
        monkeypatch.setattr(ProductionExecutionService, name, sentinel)
        forbidden.append(sentinel)
    for target, name in ((studio_timeline_render, "render_studio_timeline"),
                         (studio_timeline_export, "run_guarded_process"),
                         (media_files, "inspect_media")):
        sentinel = Mock(side_effect=AssertionError("History metadata must not call " + name))
        monkeypatch.setattr(target, name, sentinel)
        forbidden.append(sentinel)
    token = "history-contract-host"
    rig.sessions.register(token, SessionContext("history-session", "history-client", "local-author", "history-workspace"))
    e = SimpleNamespace(rig=rig, client=rig.client, production=production,
        base=f"/api/projects/{rig.nid}/studio", headers={"X-Session-Token": token})
    response = e.client.post(e.base + "/activate", headers=e.headers)
    assert response.status_code == 200, response.text
    data = io.BytesIO()
    with wave.open(data, "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(48000)
        output.writeframes(b"\x00" * 4800 * 4)
    e.content = data.getvalue()
    with rig.workspace._asset_scope(rig.nid, rig.scope):
        e.asset = rig.assets.create(rig.nid, "synthetic-history.wav",
            base64.b64encode(e.content).decode(), "audio/wav", "audio",
            required_features=("narrative_production_v2",))
    yield e
    for sentinel in forbidden:
        sentinel.assert_not_called()


def checked(response, status=200):
    assert response.status_code == status, response.text
    return response.json()


def create_timeline(e):
    source = {"id": e.asset["id"], "kind": "ASSET", "asset_kind": "audio",
        "version": e.asset["version"], "digest": e.asset["sha256"]}
    body = {"expected_version": 0, "title": "Synthetic audio edit history",
        "timeline": {"schema_version": 3, "media_kind": "AUDIO", "duration_ms": 100,
            "tracks": [{"id": "dialogue", "kind": "AUDIO", "order": 0,
                "clips": [{"id": "clip-one", "source_snapshot": source,
                    "start_ms": 0, "in_ms": 0, "out_ms": 100}]}]}}
    return checked(e.client.post(e.base + "/production/timelines", headers=e.headers, json=body), 201)


def edit_timeline(e, original):
    timeline = deepcopy(original["timeline"])
    timeline["tracks"][0]["gain_db"] = -6.0
    return checked(e.client.put(e.base + "/production/timelines/" + original["id"], headers=e.headers,
        json={"expected_version": original["version"], "title": original["title"], "timeline": timeline}))


def restore_body(current, original):
    return {"expected_version": current["version"], "reviewed_timeline_digest": current["timeline_digest"],
        "restore_version": original["version"], "restore_digest": original["timeline_digest"]}


def test_overview_exposes_stable_owner_incarnation_and_changes_on_same_id_recreation(rig):
    url = f"/api/projects/{rig.nid}/studio"
    first = checked(rig.client.get(url))["project"]
    assert first["id"] == rig.nid
    assert first["incarnation"] == rig.workspace.store.incarnation(rig.nid)
    assert UUID(first["incarnation"].removeprefix("file:")).version == 4
    assert checked(rig.client.get(url))["project"]["incarnation"] == first["incarnation"]
    rig.novels.delete(rig.nid)
    assert rig.client.get(url).status_code == 404
    rig.project(rig.nid)
    recreated = checked(rig.client.get(url))["project"]
    assert recreated["id"] == first["id"]
    assert recreated["incarnation"] != first["incarnation"]
    assert recreated["incarnation"] == rig.workspace.store.incarnation(rig.nid)


def test_audio_schema_three_history_restore_creates_new_timeline_version(audio_history):
    e = audio_history
    original = create_timeline(e)
    current = edit_timeline(e, original)
    url = e.base + "/production/timelines/" + original["id"]
    history = checked(e.client.get(url + "/history", headers=e.headers))
    assert history == {"timeline_id": original["id"], "current_version": 2, "items": [original]}
    restored = checked(e.client.post(url + "/restore", headers=e.headers, json=restore_body(current, original)))
    assert restored["id"] == original["id"] and restored["version"] == 3
    assert restored["timeline"] == original["timeline"]
    assert restored["timeline_digest"] == original["timeline_digest"] != current["timeline_digest"]
    assert checked(e.client.get(url, headers=e.headers)) == restored
    history = checked(e.client.get(url + "/history", headers=e.headers))
    assert history["current_version"] == 3 and history["items"] == [current, original]
    # The restored definition is not a binary or Asset-version rollback.
    with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
        assert e.rig.assets.get(e.asset["id"])["version"] == 1
        assert e.rig.assets.content(e.asset["id"]) == e.content
    assert checked(e.client.get(e.base + "/production/jobs", headers=e.headers))["items"] == []


def test_audio_timeline_restore_rechecks_exact_current_asset_pin(audio_history):
    e = audio_history
    original = create_timeline(e)
    current = edit_timeline(e, original)
    with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
        e.rig.assets.update_metadata(e.asset["id"], {"parameters": {"changed": True}}, expected_version=1)
    url = e.base + "/production/timelines/" + original["id"]
    before = checked(e.client.get(url + "/history", headers=e.headers))
    refused = e.client.post(url + "/restore", headers=e.headers, json=restore_body(current, original))
    assert refused.status_code == 409, refused.text
    assert checked(e.client.get(url, headers=e.headers)) == current
    assert checked(e.client.get(url + "/history", headers=e.headers)) == before


def test_audio_timeline_history_retains_original_host_revocation_guard(audio_history):
    e = audio_history
    original = create_timeline(e)
    edit_timeline(e, original)
    e.rig.sessions.revoke(e.headers["X-Session-Token"])
    denied = e.client.get(e.base + "/production/timelines/" + original["id"] + "/history", headers=e.headers)
    assert denied.status_code in {401, 403}, denied.text
    assert original["id"] not in denied.text


def test_asset_restore_only_undeletes_current_bytes_and_rejects_version_selection(audio_history):
    e = audio_history
    url = e.base + "/assets/" + e.asset["id"]
    deleted = checked(e.client.delete(url, params={"expected_version": 1}, headers=e.headers))
    assert deleted["version"] == 2 and deleted["deleted_at"] is not None
    assert e.client.get(url, headers=e.headers).status_code == 404
    rejected = e.client.post(url + "/restore", headers=e.headers,
        json={"expected_version": 2, "restore_version": 1})
    assert rejected.status_code == 422, rejected.text
    with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
        pending = e.rig.assets.get(e.asset["id"], include_deleted=True)
        assert pending["version"] == 2 and pending["deleted_at"] is not None
    restored = checked(e.client.post(url + "/restore", headers=e.headers, json={"expected_version": 2}))
    assert restored["id"] == e.asset["id"] and restored["version"] == 3
    assert restored["sha256"] == e.asset["sha256"] and restored["deleted_at"] is None
    download = e.client.get(url + "/download", headers=e.headers)
    assert download.status_code == 200 and download.content == e.content
    assert download.headers["x-asset-version"] == "3"

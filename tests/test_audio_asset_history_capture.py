"""Flag-gated immutable audio asset history capture at the original owner.

Default-off must leave media asset writes and the read-only history status
unchanged. With ``ENABLE_AUDIO_ASSET_HISTORY`` the current metadata commit point
also prepares an append-only record + content blob; reads never migrate legacy
assets, and a write to an uncaptured legacy asset fails closed instead of
fabricating a baseline from the current revision.

These are File-only synthetic tests; restore write endpoints stay unavailable.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pytest

from app.config import settings
from app.project_capacity_attribution import measure_assets
from app.services.audio_asset_history_store import HEAD
from test_audio_history_status_readonly import snapshot
from test_studio_asset_query import rig

pytestmark = pytest.mark.file_backend_only


@pytest.fixture
def audio_history_enabled():
    previous = settings.enable_audio_asset_history
    object.__setattr__(settings, "enable_audio_asset_history", True)
    try:
        yield
    finally:
        object.__setattr__(settings, "enable_audio_asset_history", previous)


@contextmanager
def scoped(rig):
    with rig.workspace._asset_scope(rig.nid, rig.scope):
        yield


def assets_service(rig):
    return rig.workspace.assets


def history_dir(rig, asset_id):
    return Path(rig.workspace.assets.root) / ".audio-history" / asset_id


def raw_meta(rig, asset_id):
    with scoped(rig):
        return assets_service(rig)._load(asset_id)


def update(rig, asset_id, fields):
    with scoped(rig):
        return assets_service(rig).update_metadata(asset_id, fields)


def test_flag_off_creates_no_history_directory(rig):
    row = rig.seed("plain.wav", "audio")
    assert not history_dir(rig, row["id"]).exists()
    assert HEAD not in raw_meta(rig, row["id"])


def test_create_captures_immutable_baseline(rig, audio_history_enabled):
    row = rig.seed("capture.wav", "audio")
    meta = raw_meta(rig, row["id"])
    assert HEAD in meta and isinstance(meta[HEAD], str) and len(meta[HEAD]) == 64
    store = assets_service(rig)._audio_history_store
    chain = store.chain(meta)
    assert len(chain) == 1
    record = chain[0]
    assert record["history_sequence"] == 1 and record["asset_version"] == 1
    assert record["parent_version_id"] is None
    assert record["sha256"] == meta["sha256"] and record["size"] == meta["size"]
    blob = history_dir(rig, row["id"]) / "blobs" / (meta["sha256"] + ".bin")
    assert blob.is_file()
    with scoped(rig):
        current = assets_service(rig).content(row["id"])
    assert store.content(record, maximum=25 * 1024 * 1024) == current


def test_new_metadata_revision_appends_and_noop_does_not(rig, audio_history_enabled):
    row = rig.seed("revisions.wav", "audio")
    store = assets_service(rig)._audio_history_store
    first = raw_meta(rig, row["id"])
    update(rig, row["id"], {"source_job_id": "synthetic-job"})
    second = raw_meta(rig, row["id"])
    assert second["version"] == first["version"] + 1
    assert second[HEAD] != first[HEAD]
    chain = store.chain(second)
    assert len(chain) == 2
    assert chain[0]["history_sequence"] == 2 and chain[0]["asset_version"] == 2
    assert chain[0]["parent_version_id"] == first[HEAD]
    assert chain[1]["parent_version_id"] is None
    blobs = list((history_dir(rig, row["id"]) / "blobs").glob("*.bin"))
    assert len(blobs) == 1  # identical content is stored once
    update(rig, row["id"], {"source_job_id": "synthetic-job"})
    third = raw_meta(rig, row["id"])
    assert third["version"] == second["version"] and third[HEAD] == second[HEAD]
    assert len(store.chain(third)) == 2


def test_legacy_uncaptured_asset_write_fails_closed_without_migration(rig):
    row = rig.seed("legacy.wav", "audio")
    before = raw_meta(rig, row["id"])
    assert HEAD not in before
    object.__setattr__(settings, "enable_audio_asset_history", True)
    try:
        with pytest.raises(ValueError, match="AUDIO_HISTORY_CAPTURE_REQUIRED"):
            update(rig, row["id"], {"source_job_id": "synthetic-job"})
    finally:
        object.__setattr__(settings, "enable_audio_asset_history", False)
    assert raw_meta(rig, row["id"]) == before
    assert not history_dir(rig, row["id"]).exists()


def test_delete_and_restore_are_captured_as_new_versions(rig, audio_history_enabled):
    row = rig.seed("lifecycle.wav", "audio")
    store = assets_service(rig)._audio_history_store
    with scoped(rig):
        assets_service(rig).delete(row["id"])
    deleted = raw_meta(rig, row["id"])
    with scoped(rig):
        assets_service(rig).restore(row["id"])
    restored = raw_meta(rig, row["id"])
    assert restored["version"] == 3 and restored.get("deleted_at") is None
    assert (deleted[HEAD], restored[HEAD]) != (None, None)
    chain = store.chain(restored)
    assert len(chain) == 3
    assert [item["asset_version"] for item in chain] == [3, 2, 1]


def test_tampered_history_record_fails_closed(rig, audio_history_enabled):
    row = rig.seed("tamper.wav", "audio")
    before = raw_meta(rig, row["id"])
    record = next((history_dir(rig, row["id"]) / "records").glob("*.bin"))
    record.write_bytes(record.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="AUDIO_HISTORY"):
        update(rig, row["id"], {"source_job_id": "synthetic-job"})
    current = raw_meta(rig, row["id"])
    assert current["version"] == before["version"] and current[HEAD] == before[HEAD]


def test_capture_is_read_only_for_legacy_get_route(rig, audio_history_enabled):
    row = rig.seed("captured.wav", "audio")
    before = snapshot(rig.root)
    response = rig.client.get(f"/api/v1/projects/{rig.nid}/studio/assets/{row['id']}/history")
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "AUDIO_HISTORY_FORMAT_NOT_INTEGRATED"
    assert snapshot(rig.root) == before


def test_capacity_attribution_counts_immutable_history_bytes(rig, audio_history_enabled):
    row = rig.seed("counted.wav", "audio")
    measured = measure_assets(Path(rig.workspace.assets.root), rig.nid)
    on_disk = sum(path.stat().st_size for path in history_dir(rig, row["id"]).rglob("*")
                  if path.is_file())
    assert on_disk > 0
    assert measured["counters"]["history_bytes"] == on_disk
    assert measured["counters"]["history_objects"] == sum(
        1 for path in history_dir(rig, row["id"]).rglob("*") if path.is_file())
    assert measured["logical_bytes"] >= on_disk
    assert measured["complete"] is True

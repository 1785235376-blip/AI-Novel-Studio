"""Bounded File-asset attribution for project capacity measurement.

Covers: exact project binding, real metadata+content bytes, same-physical-object
dedupe, other-project aggregate-only counters (no ids), corrupt/missing content
handling, metadata scan bounds, read-only behavior, and the mounted diagnostics
route combining project-root measurement with asset attribution.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.project_capacity_attribution import (
    CapacityAttributionError,
    measure_assets,
)
from test_audio_history_status_readonly import snapshot
from test_studio_asset_query import rig
from test_studio_workspace_identity_history_contract import audio_history

pytestmark = pytest.mark.file_backend_only


def asset_pair(assets_root: Path, project_id: str, asset_id: str, content: bytes,
               metadata: dict | None = None) -> tuple[Path, Path]:
    root = Path(assets_root)
    root.mkdir(parents=True, exist_ok=True)
    payload = {"id": asset_id, "novel_id": project_id, "branch_id": "main",
               "filename": f"{asset_id}.bin", "size": len(content)}
    payload.update(metadata or {})
    meta_path = root / f"{asset_id}.json"
    bin_path = root / f"{asset_id}.bin"
    meta_path.write_text(json.dumps(payload), encoding="utf-8")
    bin_path.write_bytes(content)
    return meta_path, bin_path


def test_attribution_counts_only_matching_project_and_aggregates_others(tmp_path):
    root = tmp_path / "assets"
    mine_meta, mine_bin = asset_pair(root, "project-a", "asset-mine", b"x" * 10)
    asset_pair(root, "project-b", "asset-other-secret", b"y" * 500)
    (root / "corrupt.json").write_bytes(b"{not-json")
    (root / "asset-nocontent.json").write_text(
        json.dumps({"id": "asset-nocontent", "novel_id": "project-a"}), encoding="utf-8")
    result = measure_assets(root, "project-a")
    expected = mine_meta.stat().st_size + mine_bin.stat().st_size
    assert result["attribution"] == "ASSET_METADATA_PROJECT_BINDING"
    assert result["logical_bytes"] == expected and result["objects"] == 2
    assert result["state"] == "MEASURED"
    assert result["counters"]["other_project_metadata"] == 1
    assert result["counters"]["unreadable_entries"] == 1
    assert result["counters"]["missing_content"] == 1
    assert result["complete"] is True
    assert "asset-other-secret" not in json.dumps(result)
    assert result["allocated_storage_bytes"] == "UNKNOWN"
    assert result["deleted"] is False and result["claimed"] is False


def test_same_physical_object_counted_once_across_metadata_and_content(tmp_path):
    root = tmp_path / "assets"
    meta1, bin1 = asset_pair(root, "project-a", "asset-1", b"z" * 20)
    meta2, bin2 = asset_pair(root, "project-a", "asset-2", b"z" * 20)
    bin2.unlink()
    os.link(bin1, bin2)  # same physical content object, different metadata rows
    result = measure_assets(root, "project-a")
    expected = meta1.stat().st_size + meta2.stat().st_size + bin1.stat().st_size
    assert result["logical_bytes"] == expected
    assert result["objects"] == 3


def test_metadata_scan_limit_and_invalid_arguments(tmp_path):
    root = tmp_path / "assets"
    asset_pair(root, "project-a", "asset-1", b"a")
    asset_pair(root, "project-a", "asset-2", b"b")
    bounded = measure_assets(root, "project-a", max_metadata_files=1)
    assert any(item["reason"] == "METADATA_FILE_LIMIT" for item in bounded["unknown"])
    assert bounded["complete"] is False and bounded["unknown_count"] == 1
    with pytest.raises(CapacityAttributionError):
        measure_assets(root, "")
    with pytest.raises(CapacityAttributionError):
        measure_assets(root, "project-a", max_metadata_files=0)
    with pytest.raises(CapacityAttributionError):
        measure_assets(root, "project-a", deadline_seconds=0)


def test_missing_assets_root_is_reported_not_created(tmp_path):
    root = tmp_path / "absent"
    result = measure_assets(root, "project-a")
    assert result["state"] == "MISSING" and result["logical_bytes"] == 0
    assert not root.exists()


def test_attribution_does_not_modify_or_delete(tmp_path):
    root = tmp_path / "assets"
    asset_pair(root, "project-a", "asset-1", b"payload")
    before = sorted((str(p.relative_to(tmp_path)), p.stat().st_size)
                    for p in tmp_path.rglob("*") if p.is_file())
    measure_assets(root, "project-a")
    after = sorted((str(p.relative_to(tmp_path)), p.stat().st_size)
                   for p in tmp_path.rglob("*") if p.is_file())
    assert before == after


def test_capacity_diagnostics_combines_project_root_and_asset_attribution(audio_history):
    e = audio_history
    asset_root = Path(e.rig.assets.root)
    direct_before = measure_assets(asset_root, e.rig.nid)
    meta, content = asset_pair(asset_root, e.rig.nid, "asset-capacity-fixture", b"c" * 32)
    asset_pair(asset_root, "other-secret-project", "asset-other-secret", b"d" * 64)
    expected_assets = measure_assets(asset_root, e.rig.nid)
    assert expected_assets["logical_bytes"] == direct_before["logical_bytes"] + meta.stat().st_size + content.stat().st_size
    before = snapshot(e.rig.root)
    response = e.client.get(f"/api/v1/projects/{e.rig.nid}/studio/capacity", headers=e.headers)
    assert response.status_code == 200, response.text
    result = response.json()
    attribution = result["assets_attribution"]
    assert attribution["logical_bytes"] == expected_assets["logical_bytes"]
    assert attribution["complete"] is True
    assert result["combined"]["logical_bytes"] == (
        result["measurement"]["logical_bytes"] + attribution["logical_bytes"]
        + result["scope_documents"]["bytes"])
    assert result["scope_documents"]["complete"] is True
    assert result["combined"]["unknown_count"] == 0
    assert result["combined"]["allocated_storage_bytes"] == "UNKNOWN"
    assert "other-secret-project" not in response.text
    assert "asset-other-secret" not in response.text
    assert result["admission"] == "UNAVAILABLE"
    assert snapshot(e.rig.root) == before


def orphan_history(root, project_id: str, asset_id: str, *, record: bool = True):
    history = Path(root) / ".audio-history" / asset_id
    (history / "records").mkdir(parents=True)
    (history / "blobs").mkdir()
    if record:
        payload = {"metadata": {"novel_id": project_id, "id": asset_id}}
        (history / "records" / ("a" * 64 + ".bin")).write_text(json.dumps(payload), encoding="utf-8")
    (history / "blobs" / ("b" * 64 + ".bin")).write_bytes(b"blob-residue")
    return history


def test_orphan_history_dir_with_same_project_record_is_unattributed_residue(tmp_path):
    root = tmp_path / "assets"
    meta, binary = asset_pair(root, "project-a", "asset-1", b"x" * 4)
    orphan_history(root, "project-a", "orphan-same")
    result = measure_assets(root, "project-a")
    # Only the committed asset is attributed; orphaned immutable history objects
    # are aggregate residue, not project bytes.
    assert result["logical_bytes"] == meta.stat().st_size + binary.stat().st_size
    assert result["counters"]["unattributed_files"] == 2
    assert result["counters"]["unattributed_bytes"] > 0
    assert result["complete"] is True
    assert "orphan-same" not in json.dumps(result)
    from app.project_capacity_admission import unproven_objects
    assert unproven_objects({"unknown_count": 0}, result) == 2


def test_orphan_history_dir_for_other_project_is_not_attributed(tmp_path):
    root = tmp_path / "assets"
    asset_pair(root, "project-a", "asset-1", b"x")
    foreign = orphan_history(root, "project-b", "foreign-orphan")
    result = measure_assets(root, "project-a")
    assert result["counters"]["unattributed_files"] == 0
    assert foreign.is_dir()  # read-only measurement leaves it in place
    assert result["complete"] is True


def test_orphan_history_dir_without_records_is_not_claimed(tmp_path):
    root = tmp_path / "assets"
    asset_pair(root, "project-a", "asset-1", b"x")
    orphan_history(root, "project-a", "blob-only", record=False)
    result = measure_assets(root, "project-a")
    # No immutable record, so no project can be safely inferred; do not claim
    # and do not block another project on ambiguous bytes.
    assert result["counters"]["unattributed_files"] == 0
    assert result["complete"] is True

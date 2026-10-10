"""Real queue/API ZIP exports, immutable asset capture and byte integrity."""
import base64
import hashlib
import io
import json
from zipfile import ZipFile

import pytest

from test_industry_export_queue import setup_queue, wait
from app.services.export_job_service import ExportJobService
from app.services.export_resource_snapshot import FrozenExportResources

RAW = b"synthetic owned resource"


class Assets:
    def __init__(self):
        self.raw = RAW
        self.meta = {"id": "asset-1", "novel_id": "project", "branch_id": "branch-a", "size": len(RAW),
                     "sha256": hashlib.sha256(RAW).hexdigest(), "filename": "../../synthetic.bin", "media_type": "application/octet-stream"}
        self.calls = []
    def get(self, aid):
        self.calls.append(("get", aid))
        return self.meta
    def content(self, aid):
        self.calls.append(("content", aid))
        return self.raw


def prepare(setup_queue):
    source, novels, queue, client = setup_queue
    assets = Assets()
    source.screenplays[0]["scenes"][0]["asset_ids"] = ["asset-1"]
    queue.snapshotter = lambda nid, format, permission_context=None: novels.export_snapshot(nid, format=format, asset_library=assets, permission_context=permission_context)
    queue._submit = lambda _: None
    return source, novels, queue, client, assets


@pytest.mark.parametrize("fmt", ["screenplay-package", "shot-list-package", "storyboard-package"])
def test_real_api_packages_freeze_assets_and_restart_without_live_reads(setup_queue, monkeypatch, tmp_path, fmt):
    import app.api as api
    source, novels, queue, client, assets = prepare(setup_queue)
    headers = {"X-Session-Token": "owner", "X-Branch-Id": "branch-a"}
    response = client.post("/api/exports?novel_id=project", json={"format": fmt}, headers=headers)
    assert response.status_code == 202
    original = response.json()
    assert "snapshot" not in original
    assets.raw = b"later content"
    source.screenplays.clear()
    assets.content = lambda _: pytest.fail("must not read live bytes")
    restarted = ExportJobService(tmp_path, novels.export, snapshotter=queue.snapshotter)
    monkeypatch.setattr(api, "export_job_service", restarted)
    try:
        job = wait(restarted, original["id"])
        assert job["status"] == "succeeded", job["error"]
        response = client.get(f"/api/exports/{job['id']}/download", headers=headers)
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
        with ZipFile(io.BytesIO(response.content)) as archive:
            assert archive.testzip() is None
            manifest = json.loads(archive.read("manifest.json"))
            assert manifest["source"]["snapshot_id"] == original["snapshot_id"]
            assert manifest["source"]["screenplay_id"] == "script-1"
            assert manifest["resources"]["missing_count"] == 0
            row = manifest["resources"]["available"][0]
            content = archive.read(row["package_path"])
            assert content == RAW
            assert row["sha256"] == hashlib.sha256(content).hexdigest()
            assert row["size"] == len(content)
            assert sorted(archive.namelist()) == manifest["files"]
            assert all(not name.startswith("/") and ".." not in name.split("/") for name in archive.namelist())
    finally:
        restarted._pool.shutdown(wait=True)


@pytest.mark.parametrize("fault", ["owner", "identity", "size", "hash", "missing", "oversized", "path"])
def test_invalid_resource_produces_failed_job_never_partial_zip(setup_queue, monkeypatch, fault):
    from app.services import export_resource_snapshot as frozen
    source, novels, queue, client, assets = prepare(setup_queue)
    if fault == "owner": assets.meta["novel_id"] = "other"
    if fault == "identity": assets.meta["id"] = "asset-2"
    if fault == "size": assets.meta["size"] += 1
    if fault == "hash": assets.meta["sha256"] = "0" * 64
    if fault == "missing": assets.raw = None
    if fault == "oversized": monkeypatch.setattr(frozen, "MAX_RESOURCE_BYTES", len(RAW)-1)
    if fault == "path": source.screenplays[0]["scenes"][0]["asset_ids"] = ["../private"]
    job = queue.create("project", "screenplay-package")
    queue._run(job["id"])
    failed = queue.get(job["id"])
    assert failed["status"] == "failed", failed
    assert failed["result"] is None
    assert failed["error"]["code"] == "EXPORT_RESOURCES_MISSING"
    assert failed["missing_resources"]
    if fault == "path": assert assets.calls == []


def test_frozen_resources_revalidate_bytes_and_bound_encoded_payload(setup_queue, monkeypatch):
    from app.services import export_resource_snapshot as frozen
    _, _, queue, _, _ = prepare(setup_queue)
    job = queue.create("project", "screenplay-package")
    snapshot = job["snapshot"]
    row = snapshot["resource_payloads"]["asset-1"]
    row["content_base64"] = base64.b64encode(b"replacement").decode()
    with pytest.raises(ValueError, match="size mismatch|checksum"):
        FrozenExportResources(snapshot).content("asset-1")
    row["content_base64"] = "A" * 100
    monkeypatch.setattr(frozen, "MAX_RESOURCE_BYTES", 10)
    with pytest.raises(ValueError, match="encoding or size"):
        FrozenExportResources(snapshot).content("asset-1")


def test_export_snapshot_filters_other_branches_and_legacy_screenplays(setup_queue):
    source, novels, _, _ = setup_queue
    source.screenplays.extend([{"id": "foreign", "branch_id": "branch-b", "scenes": []}, {"id": "legacy", "scenes": []}])
    snapshot = novels.export_snapshot("project", permission_context={"mode": "collaboration", "branch_id": "branch-a"})
    assert [row["id"] for row in snapshot["source"]["screenplays"]] == ["script-1"]
    assert [row["id"] for row in snapshot["source_versions"]["screenplays"]] == ["script-1"]

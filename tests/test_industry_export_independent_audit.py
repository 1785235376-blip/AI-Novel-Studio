"""Independent regression checks for the durable industry export boundary."""
import hashlib
import io
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from app.services.export_job_service import ExportJobResultInvalid, ExportJobService
from app.services.novel_service import NovelService


def test_snapshot_renderer_typeerror_never_falls_back_to_live_data(tmp_path):
    calls = []

    def exporter(novel_id, format, *, snapshot=None, progress_callback=None):
        calls.append(snapshot)
        if snapshot is not None:
            raise TypeError("renderer rejected frozen data")
        return {"format": format, "content": "LIVE CHANGED DATA"}

    queue = ExportJobService(tmp_path, exporter, snapshotter=lambda nid, format: {
        "snapshot_id": "frozen", "source": {"text": "ORIGINAL"},
    })
    job = queue.create("novel-a", "screenplay-fountain")
    queue._pool.shutdown(wait=True)
    completed = queue.get(job["id"])
    assert completed["status"] == "failed"
    assert len(calls) == 1
    assert completed["result"] is None


@pytest.mark.parametrize("changed_field,new_value", [
    ("actor_id", "other-user"), ("branch_id", "other-branch"),
    ("workspace_id", "other-workspace"), ("mode", "local"),
])
def test_idempotency_does_not_cross_permission_context(tmp_path, changed_field, new_value):
    scope = {"actor_id": "alice", "branch_id": "branch-a", "workspace_id": "workspace-a", "mode": "collaboration"}
    queue = ExportJobService(tmp_path, lambda nid, fmt: {"format": fmt, "content": "frozen"})
    try:
        original = queue.create("novel-a", "screenplay-fountain", "key", permission_context=scope)
        same = queue.create("novel-a", "screenplay-docx", "key", permission_context=dict(scope))
        other = queue.create("novel-a", "screenplay-fountain", "key", permission_context={**scope, changed_field: new_value})
        assert same["id"] == original["id"]  # Existing novel/key semantics, even across formats.
        assert other["id"] != original["id"]
    finally:
        queue._pool.shutdown(wait=True)


@pytest.mark.parametrize("format,mime", [
    ("screenplay-fountain", "text/x-fountain"),
    ("screenplay-docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
])
def test_frozen_industry_restart_provenance_and_artifact_checksum(tmp_path, format, mime):
    screenplay = {"id": "screenplay-old", "revision": 7, "shot_revision": 3, "storyboard_revision": 2, "title": "Frozen screenplay", "scenes": [{"id": "scene-1", "location": "ROOM", "action": "ORIGINAL ACTION", "dialogue": []}]}
    novels = SimpleNamespace(get=lambda nid: {"id": nid, "title": "Frozen novel"}, get_data_set=lambda *args: [], get_outline=lambda *args: {}, list_screenplays=lambda nid: [screenplay])
    service = NovelService(novels, SimpleNamespace(list=lambda nid: []))
    queue = ExportJobService(tmp_path, service.export, snapshotter=service.export_snapshot)
    queue._submit = lambda job_id: None
    job = queue.create("novel-a", format)
    queue._pool.shutdown(wait=True)
    screenplay["scenes"][0]["action"] = "LIVE MODIFIED ACTION"
    screenplay["revision"] = 8
    resumed = ExportJobService(tmp_path, service.export, snapshotter=service.export_snapshot)
    resumed._pool.shutdown(wait=True)
    completed = resumed.get(job["id"])
    assert completed["status"] == "succeeded"
    assert completed["recovery_count"] == 1
    assert completed["snapshot"]["source_versions"]["screenplays"][0]["revision"] == 7
    payload = resumed.download(job["id"])
    assert payload["media_type"] == mime
    raw = payload["content"]
    assert completed["artifact"]["sha256"] == hashlib.sha256(raw).hexdigest()
    if format.endswith("docx"):
        with ZipFile(io.BytesIO(raw)) as archive:
            assert archive.testzip() is None
            text = archive.read("word/document.xml").decode()
    else:
        text = raw.decode()
    assert "ORIGINAL ACTION" in text
    assert "LIVE MODIFIED ACTION" not in text
    assert job["snapshot_id"] in text
    artifact = tmp_path / "export_artifacts" / completed["artifact"]["path"]
    artifact.write_bytes(b"tampered")
    with pytest.raises(ExportJobResultInvalid, match="checksum"):
        resumed.download(job["id"])

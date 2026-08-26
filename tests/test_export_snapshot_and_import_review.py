import hashlib
import json
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

from app.services.export_job_service import ExportJobService
from app.services.import_review_service import ImportReviewService


def _wait(service, job_id, status="succeeded"):
    for _ in range(200):
        item = service.get(job_id)
        if item["status"] == status:
            return item
        time.sleep(0.01)
    return service.get(job_id)


def test_export_job_persists_immutable_snapshot_manifest_and_artifact():
    started = Event()
    release = Event()
    source = {"title": "初稿", "chapters": [{"title": "第一章", "content": "原文"}]}

    def snapshotter(novel_id, format=None):
        return {
            "schema_version": 1,
            "snapshot_id": "snapshot-1",
            "novel_id": novel_id,
            "source": json.loads(json.dumps(source, ensure_ascii=False)),
            "resource_manifest": {
                "referenced": ["asset-missing"],
                "available": [],
                "missing": [{"id": "asset-missing", "reason": "asset not found"}],
                "missing_count": 1,
            },
        }

    def exporter(novel_id, format, snapshot=None, progress_callback=None):
        started.set()
        release.wait(timeout=2)
        assert snapshot["source"]["chapters"][0]["content"] == "原文"
        return {"format": format, "filename": "snapshot.txt", "content": snapshot["source"]["chapters"][0]["content"]}

    with TemporaryDirectory() as root:
        service = ExportJobService(Path(root), exporter, snapshotter=snapshotter)
        try:
            job = service.create("novel-a", "txt")
            assert job["snapshot_id"] == "snapshot-1"
            assert job["missing_resources"][0]["id"] == "asset-missing"
            assert started.wait(timeout=1)
            source["chapters"][0]["content"] = "后改正文"
            release.set()
            completed = _wait(service, job["id"])
            assert completed["status"] == "succeeded"
            artifact = completed["artifact"]
            artifact_path = Path(root) / "export_artifacts" / artifact["path"]
            assert artifact_path.is_file()
            assert artifact["sha256"] == hashlib.sha256(artifact_path.read_bytes()).hexdigest()
            assert service.download(job["id"])["content"] == "原文".encode("utf-8")
        finally:
            release.set()
            service._pool.shutdown(wait=True)


def test_import_review_store_supports_resume_edit_and_history():
    with TemporaryDirectory() as root:
        service = ImportReviewService(Path(root))
        pending = service.ensure_pending("novel-a", {"characters": [{"name": "林默"}]}, source_format="txt")
        assert pending["status"] == "PENDING"
        edited = service.update_candidates(
            pending["id"],
            {"characters": [{"name": "林默"}, {"name": "沈舟"}]},
            selected={"characters": [True, False]},
        )
        assert len(edited["candidates"]["characters"]) == 2
        assert edited["selected"]["characters"] == [True, False]
        decided = service.decide(
            pending["id"],
            "ACCEPTED",
            selected={"characters": [{"name": "林默"}]},
            applied={"characters": [{"id": "lin-mo", "name": "林默"}]},
        )
        assert decided["status"] == "ACCEPTED"
        assert decided["history"][-1]["decision"] == "ACCEPTED"
        assert service.list_for_novel("novel-a", status="PENDING") == []
        assert service.list_for_novel("novel-a")[0]["id"] == pending["id"]

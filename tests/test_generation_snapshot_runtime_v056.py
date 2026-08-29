import json
import shutil
import time
import os
from uuid import uuid4
from pathlib import Path

from app import jobs as jobs_module
from app.config import settings
from app.jobs import JobManager
from app.providers import MockProvider
from app.config import Settings
from app.repositories.factory import create_repository_bundle
from app.services import NovelService, ChapterService
from app.services.context_snapshot_service import ContextSnapshotService
from app.repository import FileRepository
from app.repositories.file.lore import FileLoreRepository
from sample_novel_fixture import install_sample_novel
import pytest


def _wait(job):
    for _ in range(200):
        if job.status in JobManager.terminal:
            return
        time.sleep(.01)


def _wait_for_persisted_job(manager, job):
    last_error = None
    for _ in range(200):
        try:
            persisted = manager.persistence.repository.get(job.id)
            if (persisted.get("status") == job.status
                    and persisted.get("context_snapshot_id") == job.context_snapshot_id):
                return persisted
        except (KeyError, PermissionError) as exc:
            last_error = exc
        time.sleep(.01)
    raise AssertionError(
        f"job {job.id} did not reach its authoritative persisted state"
    ) from last_error


def _manager(tmp_path, monkeypatch, provider):
    install_sample_novel(tmp_path)
    monkeypatch.setattr(jobs_module.repo, "data", tmp_path)
    monkeypatch.setattr(jobs_module.repo, "novels", tmp_path / "novels")
    object.__setattr__(settings, "mock_provider", True)
    jobs_module.runtime.providers["mock"] = provider
    return JobManager(memory_extractor=type("Noop", (), {"enqueue": lambda *_: None})(),
                      snapshot_required=True)


@pytest.mark.file_backend_only
def test_generation_persists_snapshot_link_before_model_and_keeps_original_version(tmp_path, monkeypatch):
    manager = _manager(tmp_path, monkeypatch, MockProvider(delay_ms=0))
    before = manager.chapters.get("sample_novel:2")["version"]
    job = manager.create("continue", {"novel_id": "sample_novel", "chapter_id": "sample_novel:2",
                                      "profile": "LOCAL_ONLY"})
    _wait(job)
    assert job.status == "COMPLETED" and job.context_snapshot_id
    persisted = _wait_for_persisted_job(manager, job)
    assert persisted["context_snapshot_id"] == job.context_snapshot_id
    path = next((tmp_path / "novels" / "sample_novel" / "lore" / "context_snapshots").glob("*.json"))
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    assert snapshot["id"] == job.context_snapshot_id
    assert snapshot["generation_id"] == job.id
    assert snapshot["chapter_version_id"] == f"sample_novel:2:v{before}"


@pytest.mark.file_backend_only
def test_snapshot_failure_prevents_provider_stream(tmp_path, monkeypatch):
    class RecordingProvider(MockProvider):
        called = False
        def stream(self, *args, **kwargs):
            self.called = True
            yield from super().stream(*args, **kwargs)

    provider = RecordingProvider(delay_ms=0)
    manager = _manager(tmp_path, monkeypatch, provider)
    monkeypatch.setattr(manager.contexts, "save_snapshot",
                        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("snapshot failed")))
    job = manager.create("continue", {"novel_id": "sample_novel", "chapter_id": "sample_novel:2",
                                      "profile": "LOCAL_ONLY"})
    _wait(job)
    assert job.status == "FAILED"
    assert "snapshot failed" in job.error
    assert provider.called is False


def test_identical_context_for_two_generation_jobs_keeps_distinct_provenance(tmp_path):
    (tmp_path / "novels" / "book").mkdir(parents=True)
    service = ContextSnapshotService(FileLoreRepository(FileRepository(tmp_path)))
    common = dict(chapter_id="book:1", chapter_version=3, context={"canon": []},
                  prompt_version="writer:v1", model="mock")
    first = service.create(**common, actor_id="user-a", session_id="session-a", generation_id="job-a")
    second = service.create(**common, actor_id="user-b", session_id="session-b", generation_id="job-b")
    assert first["id"] != second["id"]
    rows = [json.loads(path.read_text(encoding="utf-8")) for path in
            (tmp_path / "novels" / "book" / "lore" / "context_snapshots").glob("*.json")]
    assert {(row["generation_id"], row["actor_id"], row["session_id"]) for row in rows} == {
        ("job-a", "user-a", "session-a"), ("job-b", "user-b", "session-b")}


@pytest.mark.postgres_backend_only
def test_real_postgres_generation_has_durable_snapshot_foreign_key():
    url = os.getenv("TEST_POSTGRES_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("real PostgreSQL unavailable")
    bundle = create_repository_bundle(Settings(storage_backend="postgres", database_url=url))
    novel_id = NovelService(bundle.novels, bundle.chapters).create(
        {"title": f"Snapshot link {uuid4()}"})["id"]
    chapter = ChapterService(bundle.chapters).create(novel_id, {"title": "One", "content": "Text"})
    snapshot = ContextSnapshotService(bundle.lore).create(
        chapter["id"], chapter["version"], {"canon": [], "characters": [], "timeline": []},
        "writer:v1", "mock")
    job_id = str(uuid4())
    bundle.generations.save({"id": job_id, "novel_id": novel_id, "chapter_id": chapter["id"],
                             "operation": "continue", "status": "COMPLETED",
                             "context_snapshot_id": snapshot["id"]})
    assert bundle.generations.get(job_id)["context_snapshot_id"] == snapshot["id"]


@pytest.mark.postgres_backend_only
def test_real_postgres_identical_generation_context_has_distinct_job_snapshots():
    url = os.getenv("TEST_POSTGRES_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("real PostgreSQL unavailable")
    bundle = create_repository_bundle(Settings(storage_backend="postgres", database_url=url))
    novel_id = NovelService(bundle.novels, bundle.chapters).create({"title": f"Snapshot owners {uuid4()}"})["id"]
    chapter = ChapterService(bundle.chapters).create(novel_id, {"title": "One", "content": "Text"})
    service = ContextSnapshotService(bundle.lore)
    common = dict(chapter_id=chapter["id"], chapter_version=chapter["version"],
                  context={"canon": []}, prompt_version="writer:v1", model="mock")
    first = service.create(**common, generation_id="job-a")
    second = service.create(**common, generation_id="job-b")
    assert first["id"] != second["id"]

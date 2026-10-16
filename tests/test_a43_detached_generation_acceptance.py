"""Shared accept-order regression using real temporary File storage.

A narrow injected completion-write refusal exercises stale durable state.
This is not a PostgreSQL substitute; the motivating PostgreSQL failure and
subsequent correction must be verified by the hosted PostgreSQL matrix.
"""
from types import SimpleNamespace

from fastapi import HTTPException
import pytest

from app.api import guard
from app.config import Settings
from app.jobs import JobManager
from app.repositories.factory import create_repository_bundle
from app.services import CanonService, ChapterService, ContextService, GenerationService, NovelService


@pytest.mark.file_backend_only
@pytest.mark.parametrize("source_deleted", [False, True])
def test_accept_resolves_original_source_before_rejecting_stale_durable_status(tmp_path, monkeypatch, source_deleted):
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "")
    monkeypatch.setenv("V1_ACCEPTANCE_MODE", "false")
    bundle = create_repository_bundle(Settings(storage_backend="file", novel_data=tmp_path), tmp_path)
    novels = NovelService(bundle.novels, bundle.chapters)
    chapters = ChapterService(bundle.chapters)
    nid = novels.create({"title": "Synthetic detached draft"})["id"]
    original = chapters.create(nid, {"title": "Original", "content": "KEEP_ORIGINAL"})
    persistence = GenerationService(bundle.generations)
    manager = JobManager(persistence, chapters, ContextService(bundle.novels, bundle.chapters),
                         CanonService(bundle.canon), memory_extractor=SimpleNamespace(enqueue=lambda *_: None),
                         snapshot_required=False)
    job = manager.prepare_job("polish", {"novel_id": nid, "chapter_id": original["id"], "profile": "LOCAL_ONLY"})
    job.status = "QUEUED"
    manager.jobs[job.id] = job
    manager._persist(job)
    durable_before = persistence.get(job.id)
    if source_deleted:
        chapters.delete(original["id"])
    current = chapters.create(nid, {"title": "Other owner", "content": "KEEP_REPLACEMENT"})
    current_before = chapters.get(current["id"])
    job.status, job.output = "COMPLETED", "UNCONFIRMED_LATE_DRAFT"
    if source_deleted:
        save = persistence.save
        def refuse_detached_completion(item):
            chapters.get(item["chapter_id"])
            return save(item)
        monkeypatch.setattr(persistence, "save", refuse_detached_completion)
        with pytest.raises(FileNotFoundError):
            manager._persist(job)
    # In-memory COMPLETED cannot override the durable QUEUED row. A deleted
    # original owner must be reported as missing, while a live queued draft
    # retains the existing not-completed rejection.
    with pytest.raises(HTTPException) as caught:
        guard(manager.accept, job.id, None, None, None, 1)
    assert caught.value.status_code == (404 if source_deleted else 400)
    assert persistence.get(job.id) == durable_before
    assert chapters.get(current["id"]) == current_before
    assert bundle.canon.list_pending(nid) == []
    if not source_deleted:
        assert "KEEP_ORIGINAL" in chapters.get(original["id"])["content"]

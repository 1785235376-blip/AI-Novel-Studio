"""Explicit File-backend Draft acceptance CAS, concurrency and recovery contracts.

These fixtures remain File-backed even inside the PostgreSQL matrix job. Real
PostgreSQL acceptance coverage lives in test_r2_acceptance_postgres.py.
"""
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import get_context
from threading import Event
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.jobs import Job, JobManager
from app.repositories.chapter_repository import VersionConflict
from app.repositories.factory import create_repository_bundle
from app.services import CanonService, ChapterService, ContextService, GenerationService


def build_manager(root):
    bundle = create_repository_bundle(Settings(storage_backend="file", database_url=""), data_root=root)
    manager = JobManager(
        GenerationService(bundle.generations), ChapterService(bundle.chapters),
        ContextService(bundle.novels, bundle.chapters), CanonService(bundle.canon),
        memory_extractor=SimpleNamespace(enqueue=lambda *args: None), snapshot_required=False,
    )
    return manager, bundle


def seed(root, operation="continue"):
    manager, bundle = build_manager(root)
    novel = bundle.novels.create({"title": "Synthetic acceptance integrity"})
    created = manager.chapters.create(novel["id"], {"title": "Original", "content": "Original text"})
    chapter = manager.chapters.get(created["id"])
    job = Job("accept-integrity", operation, novel["id"], chapter["id"], "", "LOCAL_ONLY",
              status="COMPLETED", output="Generated draft", base_chapter_version=chapter["version"])
    manager.jobs[job.id] = job
    manager._persist(job)
    return manager, bundle, novel, chapter, job


@pytest.mark.parametrize("operation", ["polish", "rewrite", "continue"])
@pytest.mark.parametrize("expected", [None, 1, 2])
def test_accept_cannot_rebase_generated_draft_using_new_expected_version(tmp_path, operation, expected):
    manager, bundle, novel, chapter, job = seed(tmp_path, operation)
    current = manager.chapters.save(chapter["id"], {"version": chapter["version"], "content": "NEWER USER EDIT"})
    with pytest.raises(VersionConflict):
        manager.accept(job.id, expected_version=expected)
    assert manager.chapters.get(chapter["id"])["content"] == current["content"]
    assert manager.chapters.get(chapter["id"])["version"] == current["version"]
    assert bundle.canon.list_pending(novel["id"]) == []
    assert bundle.generations.get(job.id)["status"] == "COMPLETED"


def test_two_manager_instances_share_acceptance_serialization(tmp_path, monkeypatch):
    manager, bundle, novel, chapter, job = seed(tmp_path)
    second, _ = build_manager(tmp_path)
    entered, release = Event(), Event()
    original = manager.chapters.create

    def paused_create(*args):
        entered.set()
        assert release.wait(5)
        return original(*args)

    monkeypatch.setattr(manager.chapters, "create", paused_create)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(manager.accept, job.id)
        assert entered.wait(3)
        other = pool.submit(second.accept, job.id)
        release.set()
        assert first.result()["chapter"]["number"] == 2
        with pytest.raises(ValueError):
            other.result()
    assert len(manager.chapters.list(novel["id"])) == 2
    assert len(bundle.canon.list_pending(novel["id"])) == 1


def accept_in_process(root, ready, start, results):
    manager, _ = build_manager(root)
    ready.put(True)
    if not start.wait(20):
        results.put("timed out")
        return
    try:
        manager.accept("accept-integrity")
        results.put("accepted")
    except ValueError:
        results.put("blocked")


def test_separate_processes_create_only_one_chapter_and_proposal(tmp_path, monkeypatch):
    # Spawn imports app dependencies before entering build_manager; keep those
    # child composition roots File-backed in every parent CI matrix lane.
    monkeypatch.setenv("STORAGE_BACKEND", "file")
    manager, bundle, novel, chapter, job = seed(tmp_path)
    context = get_context("spawn")
    ready, results, start = context.Queue(), context.Queue(), context.Event()
    processes = [context.Process(target=accept_in_process, args=(tmp_path, ready, start, results)) for _ in range(2)]
    try:
        for process in processes:
            process.start()
        for _ in processes:
            assert ready.get(timeout=30)
        start.set()
        assert sorted(results.get(timeout=30) for _ in processes) == ["accepted", "blocked"]
        for process in processes:
            process.join(10)
            assert process.exitcode == 0
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(10)
    assert len(manager.chapters.list(novel["id"])) == 2
    assert len(bundle.canon.list_pending(novel["id"])) == 1


def test_uncertain_acceptance_never_replays_after_restart(tmp_path, monkeypatch):
    manager, bundle, novel, chapter, job = seed(tmp_path)
    original = manager.canon.save_pending

    def write_then_fail(item):
        original(item)
        raise OSError("Synthetic failure after proposal persistence")

    monkeypatch.setattr(manager.canon, "save_pending", write_then_fail)
    with pytest.raises(OSError):
        manager.accept(job.id)
    assert bundle.generations.get(job.id)["status"] == "ACCEPTANCE_UNCERTAIN"
    restarted, _ = build_manager(tmp_path)
    with pytest.raises(ValueError):
        restarted.accept(job.id)
    with pytest.raises(ValueError):
        restarted.reject(job.id)
    assert len(manager.chapters.list(novel["id"])) == 2
    assert len(bundle.canon.list_pending(novel["id"])) == 1


def test_crashed_accepting_claim_is_not_replayed(tmp_path):
    manager, bundle, novel, chapter, job = seed(tmp_path)
    job.status = "ACCEPTING"
    manager._persist(job)
    restarted, _ = build_manager(tmp_path)
    with pytest.raises(ValueError):
        restarted.accept(job.id)
    assert len(manager.chapters.list(novel["id"])) == 1
    assert bundle.canon.list_pending(novel["id"]) == []


def test_stale_manager_reject_cannot_erase_accepted_state(tmp_path):
    manager, bundle, novel, chapter, job = seed(tmp_path)
    stale, _ = build_manager(tmp_path)
    manager.accept(job.id)
    with pytest.raises(ValueError):
        stale.reject(job.id)
    assert bundle.generations.get(job.id)["status"] == "ACCEPTED"


def test_cancel_during_acceptance_cannot_erase_the_durable_claim(tmp_path, monkeypatch):
    manager, bundle, novel, chapter, job = seed(tmp_path)
    original = manager.chapters.create

    def cancel_before_create(*args):
        manager.cancel(job.id)
        assert bundle.generations.get(job.id)["status"] == "ACCEPTING"
        return original(*args)

    monkeypatch.setattr(manager.chapters, "create", cancel_before_create)
    manager.accept(job.id)
    assert bundle.generations.get(job.id)["status"] == "ACCEPTED"
    assert len(bundle.canon.list_pending(novel["id"])) == 1


def test_replacement_without_generation_base_fails_closed(tmp_path):
    manager, bundle, novel, chapter, job = seed(tmp_path, "polish")
    job.base_chapter_version = None
    manager._persist(job)
    with pytest.raises(ValueError, match="base is missing"):
        manager.accept(job.id, expected_version=chapter["version"])
    assert manager.chapters.get(chapter["id"])["version"] == chapter["version"]
    assert bundle.canon.list_pending(novel["id"]) == []


def test_local_api_cannot_accept_old_draft_by_submitting_current_version(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app import api as api_module
    from app.main import app
    from app.config import settings

    manager, bundle, novel, chapter, job = seed(tmp_path, "polish")
    current = manager.chapters.save(chapter["id"], {"version": chapter["version"], "content": "NEWER USER EDIT"})
    monkeypatch.setattr(api_module, "jobs", manager)
    previous = settings.enable_collaboration_runtime
    object.__setattr__(settings, "enable_collaboration_runtime", False)
    try:
        response = TestClient(app).post(f"/api/generation/{job.id}/accept", json={"expected_version": current["version"]})
    finally:
        object.__setattr__(settings, "enable_collaboration_runtime", previous)
    assert response.status_code == 409
    assert manager.chapters.get(chapter["id"])["content"] == current["content"]
    assert bundle.canon.list_pending(novel["id"]) == []

"""Real PostgreSQL acceptance contracts, with an explicit disposable DB opt-in.

These tests use real PostgreSQL repositories and separate manager connections.
They verify same-host acceptance serialization plus database-persisted claims;
no distributed/multiple-host guarantee is claimed. Never use DATABASE_URL as a
fallback. Only uniquely named synthetic projects created here are deleted.
"""
from concurrent.futures import ThreadPoolExecutor
import os
from threading import Event
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.config import Settings, settings
from app.jobs import Job, JobManager
from app.repositories.chapter_repository import VersionConflict
from app.repositories.factory import create_repository_bundle
from app.repositories.postgres.chapter import PostgresChapterRepository
from app.repositories.postgres.generation import PostgresGenerationRepository
from app.services import CanonService, ChapterService, ContextService, GenerationService

TEST_URL = os.getenv("TEST_POSTGRES_DATABASE_URL", "")
pytestmark = [
    pytest.mark.postgres_backend_only,
    pytest.mark.skipif(not TEST_URL, reason="NOT_RUN: disposable TEST_POSTGRES_DATABASE_URL not configured"),
]


@pytest.fixture
def pg_acceptance(tmp_path):
    config = Settings(storage_backend="postgres", database_url=TEST_URL)
    object.__setattr__(settings, "novel_data", tmp_path / "same-host-acceptance-locks")
    bundles = []
    novel_ids = []

    def manager():
        # A supplied but unavailable test endpoint is a failure, not a skip or
        # a File fallback. Every reopened manager gets separate PG connections.
        bundle = create_repository_bundle(config)
        bundles.append(bundle)
        assert isinstance(bundle.chapters, PostgresChapterRepository)
        assert isinstance(bundle.generations, PostgresGenerationRepository)
        instance = JobManager(
            GenerationService(bundle.generations), ChapterService(bundle.chapters),
            ContextService(bundle.novels, bundle.chapters), CanonService(bundle.canon),
            memory_extractor=SimpleNamespace(enqueue=lambda *args: None), snapshot_required=False,
        )
        return instance, bundle

    def seed(operation="continue"):
        instance, bundle = manager()
        novel = bundle.novels.create({"id": "r2-acceptance-pg-" + uuid4().hex, "title": "Synthetic PG acceptance"})
        novel_ids.append(novel["id"])
        chapter = instance.chapters.create(novel["id"], {"title": "Original", "content": "Original synthetic manuscript"})
        job = Job(str(uuid4()), operation, novel["id"], chapter["id"], "", "LOCAL_ONLY",
                  status="COMPLETED", output="Generated synthetic draft", base_chapter_version=chapter["version"])
        instance.jobs[job.id] = job
        instance._persist(job)
        return instance, bundle, novel, chapter, job

    try:
        yield SimpleNamespace(seed=seed, reopen=manager)
    finally:
        try:
            for novel_id in novel_ids:
                # FK cascades remove only this fixture's project data and jobs.
                bundles[0].novels.delete(novel_id)
        finally:
            for bundle in bundles:
                bundle.novels.database.engine.dispose()


@pytest.mark.parametrize("expected", ["omitted", "generation_base", "new_current"])
def test_postgres_stale_generation_base_cannot_be_rebased(pg_acceptance, expected):
    manager, bundle, novel, chapter, job = pg_acceptance.seed("polish")
    current = manager.chapters.save(chapter["id"], {"version": chapter["version"], "content": "NEWER USER EDIT"})
    versions = {"omitted": None, "generation_base": chapter["version"], "new_current": current["version"]}
    with pytest.raises(VersionConflict) as conflict:
        manager.accept(job.id, expected_version=versions[expected])
    assert conflict.value.expected_version == chapter["version"]
    assert conflict.value.actual_version == current["version"]
    reopened, persisted = pg_acceptance.reopen()
    assert reopened.chapters.get(chapter["id"])["content"] == current["content"]
    assert reopened.chapters.get(chapter["id"])["version"] == current["version"]
    assert persisted.generations.get(job.id)["status"] == "COMPLETED"
    assert persisted.canon.list_pending(novel["id"]) == []
    assert len(reopened.chapters.list(novel["id"])) == 1


def test_postgres_concurrent_acceptance_has_one_durable_claim_and_proposal(pg_acceptance, monkeypatch):
    first, bundle, novel, chapter, job = pg_acceptance.seed()
    second, second_bundle = pg_acceptance.reopen()
    entered, release, second_entered = Event(), Event(), Event()
    create_first, create_second = first.chapters.create, second.chapters.create

    def paused_create(*args):
        entered.set()
        assert release.wait(10), "test did not release first acceptance"
        return create_first(*args)

    def competing_create(*args):
        second_entered.set()
        return create_second(*args)

    monkeypatch.setattr(first.chapters, "create", paused_create)
    monkeypatch.setattr(second.chapters, "create", competing_create)
    with ThreadPoolExecutor(max_workers=2) as pool:
        accepted = pool.submit(first.accept, job.id)
        try:
            assert entered.wait(10)
            # Read from an independent DB pool while the first writer is paused
            # before the first chapter side effect: the claim is already durable.
            assert second_bundle.generations.get(job.id)["status"] == "ACCEPTING"
            duplicate = pool.submit(second.accept, job.id)
            assert not second_entered.wait(0.25)
        finally:
            release.set()
        result = accepted.result(timeout=20)
        with pytest.raises(ValueError, match="completed drafts"):
            duplicate.result(timeout=20)
    assert result["chapter"]["number"] == 2
    assert not second_entered.is_set()
    reopened, persisted = pg_acceptance.reopen()
    assert persisted.generations.get(job.id)["status"] == "ACCEPTED"
    assert len(reopened.chapters.list(novel["id"])) == 2
    assert reopened.chapters.get(chapter["id"])["content"] == chapter["content"]
    pending = persisted.canon.list_pending(novel["id"])
    assert len(pending) == 1
    assert pending[0]["id"] == result["pending_canon"]["id"]
    assert pending[0]["proposals"][0]["source_job"] == job.id
    with pytest.raises(ValueError):
        reopened.accept(job.id)
    assert len(persisted.canon.list_pending(novel["id"])) == 1


def test_postgres_partial_acceptance_blocks_replay_after_manager_reopen(pg_acceptance, monkeypatch):
    manager, bundle, novel, chapter, job = pg_acceptance.seed()
    save_pending = manager.canon.save_pending

    def persist_then_fail(item):
        save_pending(item)
        raise OSError("Synthetic interruption after PostgreSQL proposal commit")

    monkeypatch.setattr(manager.canon, "save_pending", persist_then_fail)
    with pytest.raises(OSError):
        manager.accept(job.id)
    reopened, persisted = pg_acceptance.reopen()
    assert persisted.generations.get(job.id)["status"] == "ACCEPTANCE_UNCERTAIN"
    assert persisted.generations.get(job.id)["error_code"] == "ACCEPTANCE_REVIEW_REQUIRED"
    with pytest.raises(ValueError):
        reopened.accept(job.id)
    with pytest.raises(ValueError):
        reopened.reject(job.id)
    assert len(reopened.chapters.list(novel["id"])) == 2
    assert len(persisted.canon.list_pending(novel["id"])) == 1


def test_postgres_interrupted_accepting_claim_survives_manager_reopen(pg_acceptance):
    manager, bundle, novel, chapter, job = pg_acceptance.seed()
    job.status = "ACCEPTING"
    manager._persist(job)
    reopened, persisted = pg_acceptance.reopen()
    assert persisted.generations.get(job.id)["status"] == "ACCEPTING"
    with pytest.raises(ValueError):
        reopened.accept(job.id)
    assert len(reopened.chapters.list(novel["id"])) == 1
    assert persisted.canon.list_pending(novel["id"]) == []

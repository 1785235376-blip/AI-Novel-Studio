from __future__ import annotations

import os
import uuid
from threading import Barrier, Lock, Thread

import pytest

from app.autosave.coordinator import SaveCoordinator
from app.autosave.durable import DurableVersionAutosaveAdapter
from app.autosave.scheduler import FakeScheduler
from app.config import Settings
from app.document import markdown_to_document
from app.repositories.chapter_repository import VersionConflict
from app.repositories.factory import create_repository_bundle
from app.repositories.postgres.session import Database
from app.services import ChapterService, NovelService


@pytest.fixture
def chapter(tmp_path):
    bundle = create_repository_bundle(Settings(storage_backend="file", novel_data=tmp_path), tmp_path)
    novel_id = NovelService(bundle.novels, bundle.chapters).create({"title": "CAS"})["id"]
    service = ChapterService(bundle.chapters)
    created = service.create(novel_id, {"title": "One", "content": "initial"})
    return service, created["id"]


def test_conflict_has_backend_neutral_details(chapter):
    service, chapter_id = chapter
    current = service.get(chapter_id)
    saved = service.save(chapter_id, {"content": "winner", "version": current["version"]})
    assert saved["version"] == current["version"] + 1
    with pytest.raises(VersionConflict) as caught:
        service.save(chapter_id, {"content": "loser", "version": current["version"]})
    assert caught.value.as_dict() == {"resource_id": chapter_id,
                                     "expected_version": current["version"],
                                     "actual_version": saved["version"],
                                     "type": "VERSION_CONFLICT"}


def test_file_two_clients_have_one_deterministic_winner(chapter):
    service, chapter_id = chapter
    version = service.get(chapter_id)["version"]
    barrier = Barrier(3)
    outcomes = []

    def update(value):
        barrier.wait()
        try:
            outcomes.append(service.save(chapter_id, {"content": value, "version": version})["content"])
        except VersionConflict:
            outcomes.append("conflict")

    workers = [Thread(target=update, args=(value,)) for value in ("a", "b")]
    for worker in workers: worker.start()
    barrier.wait()
    for worker in workers: worker.join()
    assert len([item for item in outcomes if item == "conflict"]) == 1
    assert service.get(chapter_id)["version"] == version + 1
    assert len(service.history(chapter_id)) == 1


def test_autosave_uses_durable_version_and_preserves_dirty_latest_on_conflict(chapter):
    service, chapter_id = chapter
    original = service.get(chapter_id)
    adapter = DurableVersionAutosaveAdapter(service.repository.save)
    adapter.track(chapter_id, original["version"])
    coordinator = SaveCoordinator(adapter, scheduler=FakeScheduler(), periodic_interval=None)
    coordinator.content_changed(chapter_id, "local one")
    coordinator.content_changed(chapter_id, "local latest")
    service.save(chapter_id, {"content": "remote", "version": original["version"]})
    assert not coordinator.flush(chapter_id)
    state = coordinator.tracker.get(chapter_id)
    assert state.dirty and state.content == "local latest"
    assert isinstance(state.failure.cause, VersionConflict)
    assert adapter.durable_version(chapter_id) == original["version"]


def test_autosave_multiple_editor_generations_increment_one_durable_version(chapter):
    service, chapter_id = chapter
    original = service.get(chapter_id)
    adapter = DurableVersionAutosaveAdapter(service.repository.save)
    adapter.track(chapter_id, original["version"])
    coordinator = SaveCoordinator(adapter, scheduler=FakeScheduler(), periodic_interval=None)
    coordinator.content_changed(chapter_id, markdown_to_document("one"))
    coordinator.content_changed(chapter_id, markdown_to_document("latest"))
    assert coordinator.flush(chapter_id)
    assert adapter.durable_version(chapter_id) == original["version"] + 1
    assert service.get(chapter_id)["version"] == original["version"] + 1


@pytest.mark.skipif(
    not os.getenv("TEST_POSTGRES_DATABASE_URL")
    or not Database(os.getenv("TEST_POSTGRES_DATABASE_URL", "postgresql://invalid")).health_check(),
    reason="NOT VERIFIED: TEST_POSTGRES_DATABASE_URL is unavailable",
)
def test_postgres_two_clients_atomic_cas_and_single_history_row():
    url = os.environ["TEST_POSTGRES_DATABASE_URL"]
    first_bundle = create_repository_bundle(Settings(storage_backend="postgres", database_url=url))
    second_bundle = create_repository_bundle(Settings(storage_backend="postgres", database_url=url))
    first = ChapterService(first_bundle.chapters)
    second = ChapterService(second_bundle.chapters)
    novel_id = NovelService(first_bundle.novels, first_bundle.chapters).create(
        {"title": f"CAS race {uuid.uuid4()}"}
    )["id"]
    chapter_id = first.create(novel_id, {"title": "Race", "content": "initial"})["id"]
    version = first.get(chapter_id)["version"]
    barrier = Barrier(3)
    outcome_lock = Lock()
    outcomes = []

    def update(service, value):
        barrier.wait()
        try:
            result = ("saved", service.save(chapter_id, {"content": value, "version": version}))
        except VersionConflict as exc:
            result = ("conflict", exc.as_dict())
        except Exception as exc:  # Keep worker failures visible in the parent assertion.
            result = ("error", f"{type(exc).__name__}: {exc}")
        with outcome_lock:
            outcomes.append(result)

    workers = [Thread(target=update, args=(service, value))
               for service, value in ((first, "client-a"), (second, "client-b"))]
    for worker in workers: worker.start()
    barrier.wait()
    for worker in workers: worker.join(10)
    assert all(not worker.is_alive() for worker in workers)
    assert [item for item in outcomes if item[0] == "error"] == []
    assert sorted(item[0] for item in outcomes) == ["conflict", "saved"]
    current = first.get(chapter_id)
    assert current["version"] == version + 1
    assert [item["version"] for item in first.history(chapter_id)] == [version]
    conflict = next(item[1] for item in outcomes if item[0] == "conflict")
    assert conflict["expected_version"] == version
    assert conflict["actual_version"] == version + 1
    first.delete(chapter_id)
    NovelService(first_bundle.novels, first_bundle.chapters).delete(novel_id)

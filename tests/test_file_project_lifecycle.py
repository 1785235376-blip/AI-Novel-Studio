"""Synthetic regressions for participating File project lifecycle operations."""
from __future__ import annotations

import errno
import json
import multiprocessing
from pathlib import Path
from queue import Queue
from threading import Event, Thread

import pytest

from app.document import markdown_to_document
from app.file_project_lifecycle import project_operation
from app.repository import FileRepository
from app.repositories.chapter_repository import ChapterRepository, VersionConflict
from app.repositories.file.chapter import FileChapterRepository
from app.repositories.file.novel import FileNovelRepository

pytestmark = pytest.mark.file_backend_only


@pytest.fixture
def project(tmp_path):
    backend = FileRepository(tmp_path)
    novel_id = backend.create_novel({"id": "synthetic-race", "title": "Synthetic race"})["id"]
    chapter_id = backend.create_chapter(novel_id, {"title": "One", "content": "Original prose"})["id"]
    return backend, novel_id, chapter_id


def _run(outcomes, name, operation, started=None):
    if started is not None:
        started.set()
    try:
        outcomes.put((name, "ok", operation()))
    except Exception as exc:
        outcomes.put((name, type(exc).__name__, str(exc)))


def _join(workers):
    for worker in workers:
        worker.join(10)
    timed_out = [worker for worker in workers if worker.is_alive()]
    for worker in timed_out:
        if hasattr(worker, "terminate"):
            worker.terminate()
            worker.join(5)
    assert not timed_out, "lifecycle operation did not finish"


def _pause_first_read(backend, ready, release):
    original = backend.chapter
    paused = False

    def read(chapter_id):
        nonlocal paused
        result = original(chapter_id)
        if not paused:
            paused = True
            ready.set()
            assert release.wait(10), "reader was not released"
        return result

    backend.chapter = read


@pytest.mark.parametrize("operation", ["get", "save", "duplicate", "rename"])
def test_delete_waits_for_started_chapter_operation_across_instances(project, operation):
    backend, novel_id, chapter_id = project
    reader = ChapterRepository(backend)
    deleter = FileRepository(backend.data)
    ready, release, delete_started = Event(), Event(), Event()
    outcomes = Queue()
    _pause_first_read(backend, ready, release)
    calls = {
        "get": lambda: reader.get(chapter_id),
        "save": lambda: reader.save(chapter_id, markdown_to_document("Changed"), 1),
        "duplicate": lambda: reader.duplicate(chapter_id),
        "rename": lambda: reader.rename(chapter_id, "Renamed", 1),
    }
    first = Thread(daemon=True, target=_run, args=(outcomes, operation, calls[operation]))
    second = Thread(daemon=True, target=_run, args=(outcomes, "delete", lambda: deleter.delete_novel(novel_id), delete_started))
    first.start()
    try:
        assert ready.wait(5)
        second.start()
        assert delete_started.wait(5)
        # Deletion may wait, but must never complete between the source read
        # and the migration/save/duplicate writes.
        second.join(.1)
        assert second.is_alive()
    finally:
        release.set()
        _join([first, second] if second.ident else [first])
    results = [outcomes.get(timeout=1) for _ in range(2)]
    assert sorted((name, status) for name, status, _ in results) == sorted([(operation, "ok"), ("delete", "ok")])
    assert not (backend.novels / novel_id).exists()
    assert backend.list_novels() == []


@pytest.mark.parametrize("operation", ["get", "save", "create", "summary", "metadata", "character", "archive", "move"])
def test_late_operations_cannot_recreate_deleted_project(project, monkeypatch, operation):
    backend, novel_id, chapter_id = project
    chapters = FileChapterRepository(FileRepository(backend.data))
    novels = FileNovelRepository(chapters.backend)
    ready, release, operation_started = Event(), Event(), Event()
    outcomes = Queue()
    from app import repository
    rmtree = repository.shutil.rmtree

    def paused_delete(path):
        ready.set()
        assert release.wait(10), "delete was not released"
        return rmtree(path)

    monkeypatch.setattr(repository.shutil, "rmtree", paused_delete)
    calls = {
        "get": lambda: chapters.get(chapter_id),
        "save": lambda: chapters.save(chapter_id, markdown_to_document("Late"), 1),
        "create": lambda: chapters.create(novel_id, {"title": "Late"}),
        "summary": lambda: chapters.save_summary(novel_id, 1, "Late"),
        "metadata": lambda: novels.update(novel_id, {"title": "Late"}),
        "character": lambda: novels.upsert_character(novel_id, "late", {"name": "Late"}),
        "archive": lambda: chapters.archive(chapter_id, 1),
        "move": lambda: chapters.move(chapter_id, "up"),
    }
    first = Thread(daemon=True, target=_run, args=(outcomes, "delete", lambda: backend.delete_novel(novel_id)))
    second = Thread(daemon=True, target=_run, args=(outcomes, operation, calls[operation], operation_started))
    first.start()
    try:
        assert ready.wait(5)
        second.start()
        assert operation_started.wait(5)
    finally:
        release.set()
        _join([first, second] if second.ident else [first])
    results = {name: status for name, status, _ in [outcomes.get(timeout=1) for _ in range(2)]}
    assert results == {"delete": "ok", operation: "FileNotFoundError"}
    assert not (backend.novels / novel_id).exists()
    assert backend.list_novels() == []


def _process_operation(data, novel_id, chapter_id, action, ready, release, outcomes, started=None):
    """Spawn-based processes have independent Python lock registries."""
    backend = FileRepository(Path(data))
    chapters = ChapterRepository(backend)
    if action in {"held_get", "held_save"}:
        _pause_first_read(backend, ready, release)
    if action == "held_delete":
        from app import repository
        rmtree = repository.shutil.rmtree

        def paused_delete(path):
            ready.set()
            assert release.wait(10)
            return rmtree(path)

        repository.shutil.rmtree = paused_delete
    calls = {
        "held_get": lambda: chapters.get(chapter_id),
        "held_save": lambda: chapters.save(chapter_id, markdown_to_document("First"), 1),
        "save": lambda: chapters.save(chapter_id, markdown_to_document("Second"), 1),
        "delete": lambda: backend.delete_novel(novel_id),
        "held_delete": lambda: backend.delete_novel(novel_id),
    }
    _run(outcomes, action, calls[action], started)


@pytest.mark.parametrize(("first_action", "second_action", "expected"), [
    ("held_get", "delete", {"held_get": "ok", "delete": "ok"}),
    ("held_save", "delete", {"held_save": "ok", "delete": "ok"}),
    ("held_delete", "save", {"held_delete": "ok", "save": "FileNotFoundError"}),
    ("held_save", "save", {"held_save": "ok", "save": "VersionConflict"}),
])
def test_cross_process_lifecycle_and_version_cas(project, first_action, second_action, expected):
    backend, novel_id, chapter_id = project
    ctx = multiprocessing.get_context("spawn")
    ready, release, started = ctx.Event(), ctx.Event(), ctx.Event()
    outcomes = ctx.Queue()
    args = (str(backend.data), novel_id, chapter_id)
    first = ctx.Process(target=_process_operation, args=(*args, first_action, ready, release, outcomes))
    second = ctx.Process(target=_process_operation, args=(*args, second_action, ready, release, outcomes, started))
    first.start()
    try:
        assert ready.wait(10)
        second.start()
        assert started.wait(10)
        second.join(.1)
        assert second.is_alive()
    finally:
        release.set()
        _join([first, second] if second.pid else [first])
    assert first.exitcode == second.exitcode == 0
    results = {name: status for name, status, _ in [outcomes.get(timeout=2) for _ in range(2)]}
    outcomes.close()
    outcomes.join_thread()
    assert results == expected
    if expected.get("save") == "VersionConflict":
        service = ChapterRepository(FileRepository(backend.data))
        assert service.get(chapter_id)["version"] == 2
        assert [row["version"] for row in service.history(chapter_id)] == [1]
        assert "First" in service.get(chapter_id)["content"]
    else:
        assert not (backend.novels / novel_id).exists()
        assert backend.list_novels() == []


def test_legacy_migration_and_history_metadata_are_preserved(project):
    backend, novel_id, chapter_id = project
    service = FileChapterRepository(backend)
    path = backend.novels / novel_id / "documents/chapter-0001.json"
    assert not path.exists()
    original = service.get(cid=chapter_id)
    package = json.loads(path.read_text())
    assert package["source"] == "MIGRATED"
    assert original["version"] == package["version"] == 1
    assert "Original prose" in original["content"]
    assert service.get(chapter_id) == original
    assert json.loads(path.read_text()) == package
    saved = service.save(chapter_id, markdown_to_document("Second"), 1, "AI_ACCEPT", operator="synthetic-user")
    assert saved["version"] == 2
    assert service.history(chapter_id) == [{
        "version": 1, "document": original["document"], "timestamp": original["updated_at"],
        "source": "AI_ACCEPT", "reason": "AI_ACCEPT", "operator": "synthetic-user",
    }]
    with pytest.raises(VersionConflict):
        service.save(chapter_id, markdown_to_document("Stale"), 1)
    assert service.restore(chapter_id, 1, 2)["version"] == 3
    assert "Original prose" in service.get(chapter_id)["content"]
    assert service.archive(chapter_id, 3)["is_archived"]
    assert service.list(novel_id=novel_id) == []
    assert service.list_archived(novel_id)[0]["version"] == 3
    assert not service.restore_archive(chapter_id, 3)["is_archived"]
    service.delete(chapter_id)
    assert service.list(novel_id) == []


def test_unrelated_project_is_not_blocked_and_lock_survives_deletion(project):
    backend, novel_id, chapter_id = project
    other = backend.create_novel({"title": "Unrelated"})["id"]
    outcomes = Queue()
    with project_operation(backend.data, novel_id):
        worker = Thread(daemon=True, target=_run, args=(outcomes, "other", lambda: backend.create_chapter(other, {"title": "One"})))
        worker.start()
        _join([worker])
        assert outcomes.get(timeout=1)[1] == "ok"
    locks = set((backend.data / ".workspace-mutation-locks").glob("*.lock"))
    assert locks and not any(path.is_relative_to(backend.novels) for path in locks)
    backend.delete_novel(novel_id)
    assert all(path.is_file() for path in locks)
    # Explicit new-project creation remains allowed after deletion. This does
    # not provide an incarnation token for delayed callers across ID reuse.
    assert backend.create_novel({"id": novel_id, "title": "New incarnation"})["id"] == novel_id


def test_delete_error_is_visible_and_releases_lock(project, monkeypatch):
    backend, novel_id, chapter_id = project
    from app import repository
    with monkeypatch.context() as patch:
        def failed_delete(path):
            raise OSError(errno.ENOTEMPTY, "synthetic uncoordinated writer")
        patch.setattr(repository.shutil, "rmtree", failed_delete)
        with pytest.raises(OSError) as caught:
            backend.delete_novel(novel_id)
        assert caught.value.errno == errno.ENOTEMPTY
    # A different thread must reacquire, proving no leaked lock after errors.
    outcomes = Queue()
    worker = Thread(daemon=True, target=_run, args=(outcomes, "get", lambda: ChapterRepository(FileRepository(backend.data)).get(chapter_id)))
    worker.start()
    _join([worker])
    assert outcomes.get(timeout=1)[1] == "ok"


def _audit_ports(backend, novel_id):
    from app.actor_context import ActorContext, SessionContext
    from app.application.persistence import AtomicPathMutationPort, FileAtomicChapterAuditPort
    from app.repositories.file.scope import FileAuthorizationRepository, FileScopeRepository
    authorization = FileAuthorizationRepository(backend.data)
    scope = FileScopeRepository(backend.data)
    scope.link_project(novel_id, "synthetic-workspace")
    actor = ActorContext("synthetic-user", "synthetic-workspace", SessionContext(
        "synthetic-session", "synthetic-client", "synthetic-user", "synthetic-workspace"))
    path_port = AtomicPathMutationPort(FileNovelRepository(backend), scope, authorization)
    chapter_port = FileAtomicChapterAuditPort(FileChapterRepository(backend), authorization)
    return authorization, path_port, chapter_port, actor


@pytest.mark.parametrize("delete_path", ["repository", "audited"])
def test_audit_rollback_finishes_before_delete_without_resurrection(project, monkeypatch, delete_path):
    backend, novel_id, chapter_id = project
    authorization, paths, chapters, actor = _audit_ports(backend, novel_id)
    ChapterRepository(backend).get(chapter_id)
    ready, release, started = Event(), Event(), Event()
    outcomes = Queue()
    append = authorization.append_audit_event

    def fail_chapter_audit(event):
        if event.get("action") != "CHAPTER_UPDATED":
            return append(event)
        ready.set()
        assert release.wait(10)
        raise RuntimeError("synthetic audit failure")

    monkeypatch.setattr(authorization, "append_audit_event", fail_chapter_audit)
    save = lambda: chapters.save_chapter_with_audit(chapter_id, markdown_to_document("Roll back"), 1,
                                                   "MANUAL_SAVE", "synthetic-user", {"action": "CHAPTER_UPDATED"})
    delete = (lambda: backend.delete_novel(novel_id)) if delete_path == "repository" else (
        lambda: paths.delete_project("synthetic-workspace", novel_id, actor))
    first = Thread(daemon=True, target=_run, args=(outcomes, "save", save))
    second = Thread(daemon=True, target=_run, args=(outcomes, "delete", delete, started))
    first.start()
    try:
        assert ready.wait(5)
        second.start()
        assert started.wait(5)
        second.join(.1)
        assert second.is_alive()
    finally:
        release.set()
        _join([first, second] if second.ident else [first])
    results = {name: status for name, status, _ in [outcomes.get(timeout=1) for _ in range(2)]}
    assert results == {"save": "RuntimeError", "delete": "ok"}
    assert not (backend.novels / novel_id).exists()
    assert backend.list_novels() == []


@pytest.mark.parametrize("audit_fails", [False, True])
def test_atomic_project_delete_coordinates_lazy_read_and_compensation(project, monkeypatch, audit_fails):
    backend, novel_id, chapter_id = project
    authorization, paths, _, actor = _audit_ports(backend, novel_id)
    ready, release, started = Event(), Event(), Event()
    outcomes = Queue()
    _pause_first_read(backend, ready, release)
    if audit_fails:
        def fail(_event):
            raise RuntimeError("synthetic project audit failure")
        monkeypatch.setattr(authorization, "append_audit_event", fail)
    first = Thread(daemon=True, target=_run, args=(outcomes, "get", lambda: ChapterRepository(backend).get(chapter_id)))
    second = Thread(daemon=True, target=_run, args=(outcomes, "delete", lambda: paths.delete_project("synthetic-workspace", novel_id, actor), started))
    first.start()
    try:
        assert ready.wait(5)
        second.start()
        assert started.wait(5)
        second.join(.1)
        assert second.is_alive()
    finally:
        release.set()
        _join([first, second] if second.ident else [first])
    results = {name: status for name, status, _ in [outcomes.get(timeout=1) for _ in range(2)]}
    assert results == {"get": "ok", "delete": "RuntimeError" if audit_fails else "ok"}
    assert not list(backend.novels.glob(".*.delete-backup-*"))
    if audit_fails:
        assert paths.scopes.project_workspace(novel_id) == "synthetic-workspace"
        assert ChapterRepository(backend).get(chapter_id)["version"] == 1
        assert len(backend.list_novels()) == 1
    else:
        assert paths.scopes.project_workspace(novel_id) is None
        assert backend.list_novels() == []


def test_audited_call_after_delete_cannot_restore_stale_snapshot(project):
    backend, novel_id, chapter_id = project
    _, _, chapters, _ = _audit_ports(backend, novel_id)
    backend.delete_novel(novel_id)
    with pytest.raises(FileNotFoundError):
        chapters.save_chapter_with_audit(chapter_id, markdown_to_document("Late"), 1,
                                        "MANUAL_SAVE", "synthetic-user", {"action": "CHAPTER_UPDATED"})
    with pytest.raises(FileNotFoundError):
        chapters.create_chapter_with_audit(novel_id, "Late", "synthetic-user", lambda _: {})
    with pytest.raises(FileNotFoundError):
        chapters.set_chapter_archived_with_audit(chapter_id, 1, True, {})
    assert not (backend.novels / novel_id).exists()


@pytest.mark.parametrize("audit_fails", [False, True])
def test_list_during_atomic_delete_never_exposes_internal_backup(project, monkeypatch, audit_fails):
    backend, novel_id, _ = project
    _, paths, _, actor = _audit_ports(backend, novel_id)
    retained = backend.create_novel({"title": "Still visible"})["id"]
    renamed, release = Event(), Event()
    outcomes = Queue()
    append = paths.audit.append

    def pause_after_rename(event):
        renamed.set()
        assert release.wait(10)
        if audit_fails:
            raise RuntimeError("synthetic project audit failure")
        return append(event)

    monkeypatch.setattr(paths.audit, "append", pause_after_rename)
    worker = Thread(daemon=True, target=_run, args=(outcomes, "delete", lambda: paths.delete_project(
        "synthetic-workspace", novel_id, actor)))
    worker.start()
    try:
        assert renamed.wait(5)
        assert not (backend.novels / novel_id).exists()
        assert len(list(backend.novels.glob(f".{novel_id}.delete-backup-*"))) == 1
        # A separate repository instance must not expose title, chapter count
        # or a dead synthetic project ID for the internal rollback copy.
        assert [row["id"] for row in FileRepository(backend.data).list_novels()] == [retained]
    finally:
        release.set()
        _join([worker])
    assert outcomes.get(timeout=1)[1] == ("RuntimeError" if audit_fails else "ok")
    assert not list(backend.novels.glob(f".{novel_id}.delete-backup-*"))
    assert {row["id"] for row in backend.list_novels()} == (
        {novel_id, retained} if audit_fails else {retained})


def test_list_preserves_ordinary_and_legacy_project_names(project):
    backend, novel_id, _ = project
    # A broad hidden-directory or metadata-ID filter would silently hide
    # previously supported File projects and imported legacy directories.
    legacy_names = [".legacy-hidden", "ordinary.delete-backup-00000000-0000-0000-0000-000000000000",
                    ".legacy.delete-backup-not-a-uuid", "legacy-metadata-id"]
    for name in legacy_names:
        (backend.novels / name / "chapters").mkdir(parents=True)
    (backend.novels / "legacy-metadata-id" / "novel.json").write_text(
        json.dumps({"id": "original-imported-id", "title": "Legacy import"}), encoding="utf-8")
    assert {row["id"] for row in backend.list_novels()} == {novel_id, *legacy_names}

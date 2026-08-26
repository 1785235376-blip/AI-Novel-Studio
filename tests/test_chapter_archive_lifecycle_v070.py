from pathlib import Path
import pytest

from app.repository import FileRepository
from app.repositories.file.chapter import FileChapterRepository
from app.application.persistence import FileAtomicChapterAuditPort
from app.config import Settings
from app.repositories.factory import create_repository_bundle
from app.repositories.file.scope import FileAuthorizationRepository


def test_file_archive_restore_persists_without_deleting_content(tmp_path: Path):
    backend = FileRepository(tmp_path)
    novel = backend.create_novel({"title": "Lifecycle"})
    repo = FileChapterRepository(backend)
    created = repo.create(novel["id"], {"title": "Keep me", "content": "UNIQUE_MARKER"})
    cid = created["id"]

    assert repo.list(novel["id"])[0]["is_archived"] is False
    archived = repo.archive(cid, 1)
    assert archived["is_archived"] is True
    assert repo.list(novel["id"]) == []
    assert repo.list_archived(novel["id"])[0]["content"].endswith("UNIQUE_MARKER")

    restarted = FileChapterRepository(FileRepository(tmp_path))
    assert restarted.list(novel["id"]) == []
    restored = restarted.restore_archive(cid, 1)
    assert restored["id"] == cid
    assert restarted.list(novel["id"])[0]["content"].endswith("UNIQUE_MARKER")
    assert restarted.list_archived(novel["id"]) == []


def test_file_archive_is_idempotent(tmp_path: Path):
    backend = FileRepository(tmp_path)
    novel = backend.create_novel({"title": "Lifecycle"})
    repo = FileChapterRepository(backend)
    chapter = repo.create(novel["id"], {"title": "One"})
    first = repo.archive(chapter["id"], 1)
    second = repo.archive(chapter["id"], 1)
    assert first["id"] == second["id"]
    assert len(repo.list_archived(novel["id"])) == 1


def test_file_archive_restore_audit_is_atomic_and_idempotent(tmp_path: Path, monkeypatch):
    bundle = create_repository_bundle(Settings(storage_backend="file", novel_data=tmp_path), tmp_path)
    novel = bundle.novels.create({"title": "Audited lifecycle"})
    chapter = bundle.chapters.create(novel["id"], {"title": "One", "content": "marker"})
    auth = FileAuthorizationRepository(tmp_path)
    port = FileAtomicChapterAuditPort(bundle.chapters, auth)
    event = lambda action: {"id": action, "action": action, "target_type": "Chapter", "target_id": chapter["id"], "scope": {"kind": "PROJECT"}, "metadata": {}}

    archived = port.set_chapter_archived_with_audit(chapter["id"], 1, True, event("CHAPTER_ARCHIVED"))
    assert archived["is_archived"] is True
    assert [e["action"] for e in auth.list_audit_events()] == ["CHAPTER_ARCHIVED"]
    port.set_chapter_archived_with_audit(chapter["id"], 1, True, event("DUPLICATE"))
    assert len(auth.list_audit_events()) == 1

    before = bundle.chapters.get(chapter["id"])
    monkeypatch.setattr(auth, "append_audit_event", lambda _event: (_ for _ in ()).throw(RuntimeError("audit failed")))
    with pytest.raises(RuntimeError):
        port.set_chapter_archived_with_audit(chapter["id"], 1, False, event("CHAPTER_RESTORED"))
    assert bundle.chapters.get(chapter["id"])["is_archived"] == before["is_archived"]

"""A43-02: durable File identity; all data is synthetic and temporary."""
from pathlib import Path
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.document import markdown_to_document
from app.repository import FileRepository
from app.repositories.file.chapter import FileChapterRepository

pytestmark = pytest.mark.file_backend_only


def fixture_repo(tmp_path):
    backend = FileRepository(tmp_path)
    backend.create_novel({"id": "identity", "title": "Synthetic identity"})
    return FileChapterRepository(backend)


def test_deleted_last_and_all_ids_are_never_reissued_after_restart(tmp_path):
    repo = fixture_repo(tmp_path)
    one = repo.create("identity", {"title": "One"})
    two = repo.create("identity", {"title": "Two"})
    repo.delete(two["id"])
    three = repo.create("identity", {"title": "Three"})
    assert three["id"] not in {one["id"], two["id"]}
    repo.delete(one["id"])
    repo.delete(three["id"])
    restarted = FileChapterRepository(FileRepository(tmp_path))
    four = restarted.create("identity", {"title": "Four"})
    assert four["number"] > max(one["number"], two["number"], three["number"])


def test_collision_rejected_before_any_original_bytes_change(tmp_path):
    repo = fixture_repo(tmp_path)
    one = repo.create("identity", {"number": 7, "title": "Keep", "content": "KEEP"})
    original = repo.get(one["id"])
    before = {p: p.read_bytes() for p in (tmp_path / "novels/identity").rglob("*") if p.is_file()}
    with pytest.raises(FileExistsError):
        repo.create("identity", {"number": 7, "title": "Overwrite", "content": "BAD"})
    assert repo.get(one["id"]) == original
    assert {p: p.read_bytes() for p in before} == before


def test_deleted_history_archive_summary_cannot_pollute_new_generation(tmp_path):
    repo = fixture_repo(tmp_path)
    old = repo.create("identity", {"title": "Old", "content": "OLD_SECRET"})
    repo.save(old["id"], markdown_to_document("old v2"), 1)
    repo.save_summary("identity", old["number"], "OLD_SUMMARY")
    repo.archive(old["id"], 2)
    root = tmp_path / "novels/identity"
    history_path = root / "history/chapter-0001/v000001.json"
    saved_history = history_path.read_bytes()
    repo.delete(old["id"])
    new = repo.create("identity", {"title": "New", "content": "NEW"})
    assert new["id"] != old["id"]
    assert not new["is_archived"]
    assert repo.history(new["id"]) == []
    with pytest.raises(FileNotFoundError):
        repo.restore(new["id"], 1, 1)
    with pytest.raises(FileNotFoundError):
        repo.save(old["id"], markdown_to_document("LATE_JOB_OR_STALE_EDITOR"), 1)
    with pytest.raises(FileNotFoundError):
        repo.save_summary("identity", old["number"], "LATE_JOB_SUMMARY")
    assert "NEW" in repo.get(new["id"])["content"]
    assert history_path.read_bytes() == saved_history
    assert json.loads((root / "summaries/index.json").read_text())[0]["summary"] == "OLD_SUMMARY"


def test_deleted_id_explicit_recreation_is_rejected(tmp_path):
    repo = fixture_repo(tmp_path)
    old = repo.create("identity", {"title": "Old"})
    repo.delete(old["id"])
    with pytest.raises(FileExistsError):
        repo.create("identity", {"number": old["number"], "title": "Replacement"})


def test_deleted_history_lookup_fails_closed_without_purging(tmp_path):
    repo = fixture_repo(tmp_path)
    old = repo.create("identity", {"title": "Old"})
    repo.save(old["id"], markdown_to_document("v2"), 1)
    repo.delete(old["id"])
    with pytest.raises(FileNotFoundError):
        repo.history(old["id"])
    assert list((tmp_path / "novels/identity/history/chapter-0001").glob("*.json"))


def test_file_move_preserves_same_version_identity_and_stale_save_target(tmp_path):
    repo = fixture_repo(tmp_path)
    a = repo.get(repo.create("identity", {"title": "A", "content": "A_BODY"})["id"])
    b = repo.get(repo.create("identity", {"title": "B", "content": "B_BODY"})["id"])
    assert a["version"] == b["version"] == 1
    assert repo.move(a["id"], "down") == [b["id"], a["id"]]
    assert repo.get(a["id"])["document"] == a["document"]
    assert repo.get(b["id"])["document"] == b["document"]
    repo.save(a["id"], markdown_to_document("A_SAVED"), 1)
    assert repo.get(b["id"])["document"] == b["document"]


def test_parallel_allocations_have_distinct_durable_ids(tmp_path):
    fixture_repo(tmp_path)
    def create(i):
        return FileChapterRepository(FileRepository(tmp_path)).create("identity", {"title": str(i)})["id"]
    with ThreadPoolExecutor(max_workers=4) as workers:
        ids = list(workers.map(create, range(12)))
    assert len(set(ids)) == 12
    restarted = FileChapterRepository(FileRepository(tmp_path))
    for cid in ids:
        restarted.delete(cid)
    assert restarted.create("identity", {"title": "Next"})["id"] not in ids


def test_untracked_empty_legacy_uses_disjoint_typed_generation_and_full_id_summary(tmp_path):
    import uuid
    backend = FileRepository(tmp_path)
    root = backend.novels / "legacy"
    (root / "chapters").mkdir(parents=True)
    (root / "novel.json").write_text(json.dumps({"id": "legacy", "title": "Legacy"}))
    repo = FileChapterRepository(backend)
    first = repo.create("legacy", {"title": "New generation", "content": "NEW_UUID_BODY"})
    token = first["id"].rsplit(":", 1)[1]
    assert token == "~" + str(uuid.UUID(token[1:]))
    assert first["number"] == 1
    for action in (
        lambda: repo.get("legacy:1"),
        lambda: repo.save("legacy:1", markdown_to_document("STALE_SAVE"), 1),
        lambda: repo.save_summary("legacy", 1, "STALE_SUMMARY"),
        lambda: repo.archive("legacy:1", 1),
        lambda: repo.delete("legacy:1"),
    ):
        with pytest.raises(FileNotFoundError):
            action()
    repo.save_summary("legacy", first["id"], "OWNED_SUMMARY")
    from app.repositories.file.novel import FileNovelRepository
    assert FileNovelRepository(backend).get_context_sources("legacy")["summaries"][0]["chapter_id"] == first["id"]
    saved = repo.save(first["id"], markdown_to_document("UUID v2"), 1)
    copied = repo.duplicate(first["id"])
    assert copied["id"] != first["id"] and ":~" in copied["id"]
    assert repo.move(first["id"], "down") == [copied["id"], first["id"]]
    repo.archive(first["id"], saved["version"])
    restarted = FileChapterRepository(FileRepository(tmp_path))
    assert restarted.get(first["id"])["is_archived"]
    restarted.restore_archive(first["id"], saved["version"])
    restored = restarted.restore(first["id"], 1, saved["version"])
    assert "NEW_UUID_BODY" in restored["content"]
    restarted.delete(first["id"])
    with pytest.raises(FileNotFoundError):
        restarted.get(first["id"])
    fresh = restarted.create("legacy", {"title": "Later"})
    assert fresh["id"] not in {first["id"], copied["id"]}
    assert fresh["number"] > copied["number"]


def test_typed_tokens_are_canonical_scoped_and_never_numeric_aliases(tmp_path):
    backend = FileRepository(tmp_path)
    for name in ("one", "two"):
        (backend.novels / name / "chapters").mkdir(parents=True)
    repo = FileChapterRepository(backend)
    chapter = repo.create("one", {"title": "Typed"})
    repo.get(chapter["id"])
    token = chapter["id"].split(":", 1)[1]
    outside = tmp_path / "one"
    (outside / "chapters").mkdir(parents=True)
    (outside / "chapters/chapter-0001.md").write_text("# Outside novels\n\nPRESERVE")
    def source_bytes():
        return {path: path.read_bytes() for root in (backend.novels, outside)
                for path in root.rglob("*") if path.is_file()}
    before = source_bytes()
    invalid = ["one:01", "one:0", "one:-1", "one:+1", "one: 1", "one:1:v1", "one:~not-a-uuid", "two:" + token,
               "one:" + token.replace("-", ""), "one:" + token.upper(), "one:~{" + token[1:] + "}",
               *[prefix + ":" + token for prefix in ("", ".", "..", "../one", "one/../two", "one\\..\\two", "one\x00bad")]]
    for cid in invalid:
        with pytest.raises(FileNotFoundError):
            repo.get(cid)
    with pytest.raises(FileNotFoundError):
        repo.save_summary("two", chapter["id"], "CROSS_PROJECT")
    from threading import RLock
    from types import SimpleNamespace
    from app.application.persistence import FileAtomicChapterAuditPort
    audited = FileAtomicChapterAuditPort(repo, SimpleNamespace(lock=RLock()))
    for project_id in ("../one", "..", "one/two", "one\\two"):
        with pytest.raises(FileNotFoundError):
            audited.create_chapter_with_audit(project_id, "Must not create", "synthetic", lambda row: {})
    assert not (backend.data / "one" / "chapter_identity.json").exists()
    assert "Typed" in repo.get(chapter["id"])["content"]
    assert source_bytes() == before
    assert not (outside / "chapter_identity.json").exists()


def test_uuid_collision_is_rejected_before_write_even_after_delete(tmp_path, monkeypatch):
    import uuid
    backend = FileRepository(tmp_path)
    root = backend.novels / "legacy"
    (root / "chapters").mkdir(parents=True)
    repo = FileChapterRepository(backend)
    old = repo.create("legacy", {"title": "Old UUID"})
    old_uuid = uuid.UUID(old["id"].rsplit(":~", 1)[1])
    repo.delete(old["id"])
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    monkeypatch.setattr("app.chapter_identity.uuid.uuid4", lambda: old_uuid)
    with pytest.raises(FileExistsError):
        repo.create("legacy", {"title": "Cannot reuse UUID"})
    assert {p: p.read_bytes() for p in root.rglob("*") if p.is_file()} == before


def test_duplicate_or_malformed_ledger_public_token_fails_closed(tmp_path):
    backend = FileRepository(tmp_path)
    root = backend.novels / "legacy"
    (root / "chapters").mkdir(parents=True)
    repo = FileChapterRepository(backend)
    one = repo.create("legacy", {"title": "One"})
    path = root / "chapter_identity.json"
    ledger = json.loads(path.read_text())
    ledger["high_water"] = 2
    ledger["allocations"]["2"] = {**ledger["allocations"]["1"], "state": "deleted"}
    path.write_text(json.dumps(ledger))
    before = path.read_bytes()
    with pytest.raises(FileNotFoundError, match="LEDGER_INVALID"):
        repo.get(one["id"])
    with pytest.raises(FileNotFoundError, match="LEDGER_INVALID"):
        repo.create("legacy", {"title": "Blocked"})
    assert path.read_bytes() == before


def test_legacy_future_navigation_and_planning_numbers_do_not_reserve_sources(tmp_path):
    backend = FileRepository(tmp_path)
    root = backend.novels / "legacy"
    (root / "chapters").mkdir(parents=True)
    (root / "chapters/chapter-0001.md").write_text("# One\n\nBody")
    (root / "chapters/chapter-0002.md").write_text("# Two\n\nBody")
    (root / "story_state.json").write_text(json.dumps({"chapter": 3}))
    (root / "foreshadowing.json").write_text(json.dumps([{"planted_chapter": 10, "target_chapter": 50}]))
    repo = FileChapterRepository(backend)
    new = repo.create("legacy", {"number": 3, "title": "Actual new chapter"})
    assert new["number"] == 3 and new["id"].startswith("legacy:~")
    with pytest.raises(FileNotFoundError):
        repo.get("legacy:3")
    assert repo.get(new["id"])["number"] == 3


def test_foreign_document_package_owner_fails_closed_without_rewrite(tmp_path):
    repo = fixture_repo(tmp_path)
    first = repo.get(repo.create("identity", {"title": "Original"})["id"])
    path = tmp_path / "novels/identity/documents/chapter-0001.json"
    package = json.loads(path.read_text())
    package["chapter_id"] = "another-project:1"
    package["document"] = markdown_to_document("FOREIGN_PACKAGE")
    path.write_text(json.dumps(package))
    before = path.read_bytes()
    for action in (lambda: repo.get(first["id"]), lambda: repo.save(first["id"], markdown_to_document("BAD_SAVE"), 1)):
        with pytest.raises(FileNotFoundError, match="DOCUMENT_IDENTITY_MISMATCH"):
            action()
    assert path.read_bytes() == before


def test_unregistered_restored_manuscript_cannot_be_overwritten(tmp_path):
    repo = fixture_repo(tmp_path)
    root = tmp_path / "novels/identity"
    restored = root / "chapters/chapter-0001.md"
    restored.write_text("# Restored owner\n\nKEEP_RESTORED_BYTES")
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    for payload in ({"title": "Auto replacement"}, {"number": 1, "title": "Explicit replacement"}):
        with pytest.raises(FileExistsError):
            repo.create("identity", payload)
    assert {p: p.read_bytes() for p in root.rglob("*") if p.is_file()} == before


def test_legacy_duplicate_rebinds_both_summary_owners_to_typed_copy(tmp_path):
    from app.repositories.file.novel import FileNovelRepository
    backend = FileRepository(tmp_path)
    root = backend.novels / "legacy"
    (root / "chapters").mkdir(parents=True)
    (root / "summaries").mkdir()
    (root / "chapters/chapter-0001.md").write_text("# Source\n\nOriginal")
    original = {"chapter": 1, "summary": "SUMMARY_COPY", "extra": {"preserved": True}}
    source_summary = root / "summaries/chapter-0001.json"
    source_summary.write_text(json.dumps(original))
    (root / "summaries/index.json").write_text(json.dumps([original]))
    before = source_summary.read_bytes()
    repo = FileChapterRepository(backend)
    copied = repo.duplicate("legacy:1")
    assert copied["id"].startswith("legacy:~")
    copied_summary = json.loads((root / f"summaries/chapter-{copied['number']:04d}.json").read_text())
    expected = {**original, "chapter": copied["number"], "chapter_id": copied["id"]}
    assert copied_summary == expected
    visible = FileNovelRepository(backend).get_context_sources("legacy")["summaries"]
    assert next(item for item in visible if item["chapter"] == copied["number"]) == expected
    assert source_summary.read_bytes() == before

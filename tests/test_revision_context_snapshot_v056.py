from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.document import markdown_to_document
from app.document_revision import SaveTrigger, permanent_revision_reason, restore_as_new_current
from app.repositories.chapter_repository import ChapterRepository
from app.repository import FileRepository
from app.services.context_snapshot_service import ContextSnapshotService, GenerationSnapshotGuard


def test_debounce_does_not_create_permanent_revision_but_checkpoints_do():
    assert permanent_revision_reason(SaveTrigger.DEBOUNCE_AUTOSAVE) is None
    assert permanent_revision_reason(SaveTrigger.MANUAL_SAVE).value == "MANUAL_SAVE"
    assert permanent_revision_reason(SaveTrigger.AI_ACCEPT).value == "AI_ACCEPT"
    assert permanent_revision_reason(SaveTrigger.CHAPTER_SWITCH).value == "CHAPTER_SWITCH"
    assert permanent_revision_reason(SaveTrigger.EXPLICIT_CHECKPOINT).value == "EXPLICIT_CHECKPOINT"


def test_restore_appends_new_current_and_preserves_selected_history(tmp_path):
    backend = FileRepository(tmp_path)
    backend.create_novel({"id": "revision", "title": "Revision"})
    created = backend.create_chapter("revision", {"title": "One", "content": "old"})
    repository = ChapterRepository(backend)
    current = repository.get(created["id"])
    current = repository.save(created["id"], markdown_to_document("new"), current["version"])
    selected_path = tmp_path / "novels" / "revision" / "history" / "chapter-0001" / "v000001.json"
    selected_before = selected_path.read_bytes()
    restored = restore_as_new_current(repository, created["id"], 1, current["version"])
    assert restored["version"] == current["version"] + 1
    assert selected_path.read_bytes() == selected_before
    assert {item["version"] for item in repository.history(created["id"])} == {1, 2}


def _snapshot_service(tmp_path):
    novel_root = tmp_path / "novels" / "novel"
    novel_root.mkdir(parents=True)
    return ContextSnapshotService(SimpleNamespace(backend=SimpleNamespace(novels=tmp_path / "novels")))


def test_snapshot_records_actor_scope_v2_order_budget_hash_and_generation(tmp_path):
    service = _snapshot_service(tmp_path)
    context = {
        "canon": [], "characters": [], "timeline": [],
        "context_pack_v2": {
            "chunks": [{"chunk_id": "b"}, {"chunk_id": "a"}],
            "token_budget": 800, "used_tokens": 233,
        },
    }
    first = service.create(
        "novel:1", 7, context, "writer:v2", "model",
        actor_id="actor", session_id="session", scope_type="BRANCH", scope_id="branch",
        generation_id="generation",
    )
    second = service.create(
        "novel:1", 7, context, "writer:v2", "model",
        actor_id="actor", session_id="session", scope_type="BRANCH", scope_id="branch",
        generation_id="generation",
    )
    assert first["context_mode"] == "V2"
    assert first["ordering"] == ["b", "a"]
    assert first["budget"] == {"token_budget": 800, "used_tokens": 233}
    assert first["actor_id"] == "actor" and first["scope_id"] == "branch"
    assert first["generation_id"] == "generation"
    assert first["context_pack_hash"] == second["context_pack_hash"]
    assert len(list((tmp_path / "novels" / "novel" / "lore" / "context_snapshots").glob("*.json"))) == 1


def test_snapshot_v1_remains_supported_and_cloud_rejects_local_only(tmp_path):
    service = _snapshot_service(tmp_path)
    snapshot = service.create("novel:1", 1, {"canon": []}, "writer:v1", "model")
    assert snapshot["context_mode"] == "V1"
    with pytest.raises(ValueError, match="LOCAL_ONLY"):
        service.create(
            "novel:1", 1,
            {"lore_memory": {"short_memory": [{"privacy": "LOCAL_ONLY", "secret": "x"}]}},
            "writer:v1", "model", cloud=True,
        )


def test_snapshot_failure_prevents_model_invocation():
    called = []

    class BrokenSnapshots:
        def create(self, **kwargs):
            raise RuntimeError("storage unavailable")

    guard = GenerationSnapshotGuard(BrokenSnapshots())
    with pytest.raises(RuntimeError, match="storage unavailable"):
        guard.invoke(lambda: called.append(True), snapshot_kwargs={})
    assert called == []

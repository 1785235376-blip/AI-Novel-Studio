from __future__ import annotations

import json
import os
import uuid
import time
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from app.config import Settings
from app.lore.context_intelligence import (
    ContextIntentAnalyzer,
    ContextIntentType,
    canonical_hash,
    detect_conflicts,
    priority_score,
)
from app.repositories.factory import create_repository_bundle
from app.repositories.postgres.session import Database
from app.services import ChapterService, ContextService, LoreService, NovelService


def test_writer_generation_records_context_snapshot(monkeypatch):
    from app import jobs as jobs_module
    from app.jobs import JobManager

    class Persistence:
        def __init__(self):
            self.items = {}
        def load_all(self):
            return []
        def save(self, item):
            self.items[item["id"]] = item

    class Chapters:
        def get(self, chapter_id):
            return {"id": chapter_id, "novel_id": "novel", "number": 1, "version": 3, "content": "Text"}

    class Contexts:
        def __init__(self):
            self.snapshots = []
        def for_chapter(self, *args):
            return {"novel_id": "novel", "canon": [], "characters": [], "timeline": []}
        def save_snapshot(self, *args, **kwargs):
            self.snapshots.append(args)
            return {"id": "snapshot"}

    route = SimpleNamespace(provider="mock", model="mock-writer")
    router = SimpleNamespace(routes={"writer": [route]}, providers={})
    monkeypatch.setattr(jobs_module.runtime, "router", lambda *args: router)
    contexts = Contexts()
    manager = JobManager(
        generations=Persistence(), chapters=Chapters(), contexts=contexts,
        canon=SimpleNamespace(), memory_extractor=SimpleNamespace(enqueue=lambda *args: None),
    )
    job = manager.create("continue", {
        "novel_id": "novel", "chapter_id": "novel:1", "profile": "LOCAL_ONLY"
    })
    for _ in range(100):
        if job.status in manager.terminal:
            break
        time.sleep(.01)
    assert job.status == "COMPLETED"
    assert contexts.snapshots[0][:2] == ("novel:1", 3)
    assert contexts.snapshots[0][-2:] == ("writer:v1", "mock-writer")


def test_job_identity_failure_never_executes_legacy_provider(monkeypatch, tmp_path):
    from app import jobs as jobs_module
    from app.jobs import JobManager
    from app.runtime import Runtime
    from app.stable_identity import StableIdentityStore

    calls = {"stream": 0}

    class Provider:
        def stream(self, prompt, model):
            calls["stream"] += 1
            yield "forbidden"

    class Persistence:
        def load_all(self): return []
        def save(self, item): pass

    class Chapters:
        def get(self, chapter_id):
            return {"id": chapter_id, "novel_id": "novel", "number": 1, "version": 1, "content": "Text"}

    class Contexts:
        def for_chapter(self, *args): return {"novel_id": "novel"}
        def save_snapshot(self, *args, **kwargs): return {"id": "snapshot"}

    store = StableIdentityStore(tmp_path / "identity.json")
    isolated = Runtime(store)
    store.delete("execution_node", "local")
    route = SimpleNamespace(provider="fake", model="legacy-model")
    isolated.router = lambda *args: SimpleNamespace(routes={"writer": [route]}, providers={"fake": Provider()})
    monkeypatch.setattr(jobs_module, "runtime", isolated)
    manager = JobManager(Persistence(), Chapters(), Contexts(), SimpleNamespace(), SimpleNamespace(enqueue=lambda *args: None))
    job = manager.create("continue", {"novel_id": "novel", "chapter_id": "chapter", "profile": "LOCAL_ONLY"})
    for _ in range(100):
        if job.status in manager.terminal: break
        time.sleep(.01)
    assert job.status == "FAILED"
    assert calls["stream"] == 0


def test_context_intent_resolves_character_location_and_operation():
    sources = {
        "characters": [{"id": "lin-hai", "name": "林海"}],
        "locations": [{"id": "underground-lab", "name": "地下实验室"}],
        "story_state": {"active_characters": []},
    }
    intent = ContextIntentAnalyzer().analyze(
        "novel", "改写林海进入地下实验室的章节", sources, "rewrite"
    )
    assert intent.intent_type == ContextIntentType.CHAPTER_REWRITE
    assert intent.characters == ["lin-hai"]
    assert intent.locations == ["underground-lab"]
    assert intent.required_memory_types == ["CHARACTER_MEMORY", "LOCATION_CONTEXT"]


def test_priority_ranking_is_deterministic():
    intent = ContextIntentAnalyzer().analyze(
        "novel", "Write Hero", {"characters": [{"id": "hero", "name": "Hero"}]}
    )
    close = {"character_id": "hero", "memory_type": "STATE_CHANGE", "valid_from_chapter": 9}
    distant = {"character_id": "hero", "memory_type": "KNOWLEDGE_CHANGE", "valid_from_chapter": 1}
    first = [priority_score(item, intent, 10, .8) for item in (close, distant)]
    second = [priority_score(item, intent, 10, .8) for item in (close, distant)]
    assert first == second
    assert first[0] > first[1]


def test_conflict_detection_reports_without_mutation():
    canon = [{"fact": "Hero has a broken leg and cannot walk"}]
    memory = [{"id": "m1", "content": {"event": "Hero is running"}}]
    before = json.dumps([canon, memory], sort_keys=True)
    report = detect_conflicts("ctx", canon, memory)
    assert report.conflicts[0].conflict_type == "CHARACTER_STATE"
    assert report.conflicts[0].severity == "HIGH"
    assert json.dumps([canon, memory], sort_keys=True) == before
    assert detect_conflicts("ctx", canon, [{"id": "m2", "content": {"event": "Hero rests"}}]).conflicts == []


def test_context_hash_is_reproducible_and_key_order_independent():
    assert canonical_hash({"b": 2, "a": [1, 2]}) == canonical_hash({"a": [1, 2], "b": 2})
    assert canonical_hash({"a": [1, 2]}) != canonical_hash({"a": [2, 1]})


@pytest.mark.file_backend_only
def test_file_context_snapshot_is_persisted(tmp_path):
    bundle = create_repository_bundle(data_root=tmp_path)
    novel_id = NovelService(bundle.novels, bundle.chapters).create(
        {"id": "snapshot-file", "title": "Snapshot File"}
    )["id"]
    chapter = ChapterService(bundle.chapters).create(novel_id, {"title": "One", "content": "Text"})
    chapter = ChapterService(bundle.chapters).get(chapter["id"])
    context = {"novel_id": novel_id, "canon": [], "characters": [], "timeline": []}
    service = ContextService(bundle.novels, bundle.chapters, LoreService(bundle.lore), False)
    one = service.save_snapshot(chapter["id"], chapter["version"], context, "writer:v1", "mock")
    two = service.save_snapshot(chapter["id"], chapter["version"], context, "writer:v1", "mock")
    assert one["context_pack_hash"] == two["context_pack_hash"]
    files = list((tmp_path / "novels" / novel_id / "lore" / "context_snapshots").glob("*.json"))
    assert len(files) == 1


def test_postgres_context_snapshot_is_idempotently_persisted():
    url = os.getenv("TEST_POSTGRES_DATABASE_URL", "")
    if not url or not Database(url).health_check():
        pytest.skip("real PostgreSQL unavailable")
    bundle = create_repository_bundle(Settings(storage_backend="postgres", database_url=url))
    slug = f"snapshot-postgres-{uuid.uuid4().hex[:8]}"
    novel_id = NovelService(bundle.novels, bundle.chapters).create(
        {"id": slug, "title": "Snapshot Postgres"}
    )["id"]
    chapter = ChapterService(bundle.chapters).create(novel_id, {"title": "One", "content": "Text"})
    chapter = ChapterService(bundle.chapters).get(chapter["id"])
    context = {"novel_id": novel_id, "canon": [], "characters": [], "timeline": []}
    service = ContextService(bundle.novels, bundle.chapters, LoreService(bundle.lore), False)
    one = service.save_snapshot(chapter["id"], chapter["version"], context, "writer:v1", "mock")
    two = service.save_snapshot(chapter["id"], chapter["version"], context, "writer:v1", "mock")
    assert one["context_pack_hash"] == two["context_pack_hash"]
    with bundle.novels.database.session() as session:
        count = session.scalar(text(
            "SELECT count(*) FROM chapter_context_snapshots s "
            "JOIN novels n ON n.id=s.novel_id WHERE n.slug=:slug"
        ), {"slug": novel_id})
    assert count == 1

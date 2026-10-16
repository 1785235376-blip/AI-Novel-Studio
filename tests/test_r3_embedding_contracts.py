from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.experimental.common import StaleSourceError
from app.experimental.embeddings import EmbeddingService, MockEmbeddingProvider
from app.experimental.embeddings_api import create_embeddings_router
from app.experimental.store import ExperimentalStore
from app.services.v1_capability_service import CapabilityVersionConflict
from test_r3_media_support import rig, branch_scope


def service(rig, provider=None):
    return EmbeddingService(rig.store, rig.novels, rig.chapters, provider=provider, assets=rig.assets, screenplays=rig.screenplays)


def index(rig, instance):
    return instance.create_index(rig.nid, rig.scope, rig.actor, {"title": "Characters", "entities": [{"entity_type": "CHARACTER", "entity_id": "alice"}]})


def test_embedding_not_configured_never_lexical_fallback(rig):
    instance = service(rig)
    assert instance.status() == {"status": "NOT_CONFIGURED", "capability": None, "lexical_fallback": False, "precision_claim": "VECTOR_SIMILARITY_ONLY"}
    row = index(rig, instance)
    assert row["status"] == "NOT_CONFIGURED"
    with pytest.raises(ValueError, match="EMBEDDING_NOT_CONFIGURED"):
        instance.rebuild(rig.nid, rig.scope, rig.actor, row["id"], 1)
    with pytest.raises(ValueError, match="EMBEDDING_NOT_CONFIGURED"):
        instance.query(rig.nid, rig.scope, {"index_id": row["id"], "text": "Alice"})
    assert instance.records(rig.nid, rig.scope, row["id"]) == []


def test_embedding_real_vector_lifecycle_model_lineage_restart(rig):
    provider = MockEmbeddingProvider()
    instance = service(rig, provider)
    row = index(rig, instance)
    ready = instance.rebuild(rig.nid, rig.scope, rig.actor, row["id"], 1)
    assert ready["status"] == "ACTIVE" and ready["index_version"] == 1
    records = instance.records(rig.nid, rig.scope, row["id"])
    assert records[0]["verification"] == "MOCK_ONLY" and records[0]["dimensions"] == 8
    assert "vector" not in records[0]
    query = instance.query(rig.nid, rig.scope, {"index_id": row["id"], "text": "Alice"})
    assert query["metric"] == "COSINE" and query["lexical_fallback"] is False
    assert query["items"][0]["entity"]["entity_id"] == "alice"
    reopened = EmbeddingService(ExperimentalStore(rig.root, rig.backend, rig.store.database_url), rig.novels, rig.chapters,
        provider=provider, assets=rig.assets, screenplays=rig.screenplays)
    assert reopened.query(rig.nid, rig.scope, {"index_id": row["id"], "text": "Alice"}) == query
    invalid = reopened.transition(rig.nid, rig.scope, rig.actor, row["id"], "invalidate", ready["version"])
    with pytest.raises(StaleSourceError):
        reopened.query(rig.nid, rig.scope, {"index_id": row["id"], "text": "Alice"})
    rebuilt = reopened.rebuild(rig.nid, rig.scope, rig.actor, row["id"], invalid["version"])
    assert rebuilt["index_version"] == 2
    assert len(reopened.records(rig.nid, rig.scope, row["id"])) == 2
    removed = reopened.transition(rig.nid, rig.scope, rig.actor, row["id"], "remove", rebuilt["version"])
    assert removed["status"] == "REMOVED"
    assert all(r["vector"] == [] for r in reopened.list(rig.nid, rig.scope, reopened.VECTORS))
    with pytest.raises(ValueError, match="INDEX_REMOVED"):
        reopened.rebuild(rig.nid, rig.scope, rig.actor, row["id"], removed["version"])


def test_embedding_source_and_model_invalidation(rig):
    instance = service(rig, MockEmbeddingProvider())
    row = index(rig, instance)
    ready = instance.rebuild(rig.nid, rig.scope, rig.actor, row["id"], 1)
    rig.novels.upsert_character(rig.nid, "alice", {"name": "Alice", "personality": "Changed"})
    assert instance.indexes(rig.nid, rig.scope)[0]["stale"] is True
    with pytest.raises(StaleSourceError):
        instance.query(rig.nid, rig.scope, {"index_id": row["id"], "text": "Alice"})
    ready = instance.rebuild(rig.nid, rig.scope, rig.actor, row["id"], ready["version"])
    instance.provider.capability = MockEmbeddingProvider.capability.model_copy(update={"model_revision": "new"})
    with pytest.raises(StaleSourceError):
        instance.query(rig.nid, rig.scope, {"index_id": row["id"], "text": "Alice"})


def test_embedding_branch_isolation_conflict_and_guard(rig):
    called = []
    class Remote(MockEmbeddingProvider):
        capability = MockEmbeddingProvider.capability.model_copy(update={"local": False})
        def embed(self, inputs):
            called.append(inputs)
            return super().embed(inputs)
    instance = service(rig, Remote())
    row = index(rig, instance)
    with pytest.raises(FileNotFoundError):
        instance.get(rig.nid, branch_scope(rig), instance.INDEXES, row["id"])
    with pytest.raises(FileNotFoundError):
        instance.create_index(rig.nid, branch_scope(rig), rig.actor, {"title": "Other", "entities": [{"entity_type": "CHARACTER", "entity_id": "alice"}]})
    with pytest.raises(CapabilityVersionConflict):
        instance.rebuild(rig.nid, rig.scope, rig.actor, row["id"], 99)
    with pytest.raises(ValueError, match="EGRESS_AUTHORITY_REQUIRED"):
        instance.rebuild(rig.nid, rig.scope, rig.actor, row["id"], 1)
    assert called == []


@pytest.mark.parametrize("vector", [[1, 2], [0] * 8, [float("nan")] * 8, [True] * 8])
def test_embedding_rejects_malformed_vectors_without_active_records(rig, vector):
    class Broken(MockEmbeddingProvider):
        def embed(self, inputs):
            return [vector for _ in inputs]
    instance = service(rig, Broken()); row = index(rig, instance)
    with pytest.raises(ValueError, match="EMBEDDING_"):
        instance.rebuild(rig.nid, rig.scope, rig.actor, row["id"], 1)
    assert instance.get(rig.nid, rig.scope, instance.INDEXES, row["id"])["status"] == "FAILED"
    assert instance.records(rig.nid, rig.scope, row["id"]) == []


def test_embedding_late_callback_cannot_restore_removed_index(rig):
    entered, release = Event(), Event()
    class Slow(MockEmbeddingProvider):
        def embed(self, inputs):
            entered.set(); assert release.wait(10)
            return super().embed(inputs)
    instance = service(rig, Slow()); row = index(rig, instance)
    with ThreadPoolExecutor() as pool:
        pending = pool.submit(instance.rebuild, rig.nid, rig.scope, rig.actor, row["id"], 1)
        assert entered.wait(10)
        building = instance.get(rig.nid, rig.scope, instance.INDEXES, row["id"])
        instance.transition(rig.nid, rig.scope, rig.actor, row["id"], "remove", building["version"])
        release.set()
        assert pending.result(timeout=20)["status"] == "REMOVED"
    assert instance.records(rig.nid, rig.scope, row["id"]) == []


def test_embedding_api_not_configured_authorization_and_flag(rig):
    instance = service(rig); flags = {"visual_embeddings"}
    def authorize(nid, token, branch, permission):
        if token != "valid": raise HTTPException(403, "denied")
        return rig.actor, rig.scope
    def enabled(flag):
        if flag not in flags: raise HTTPException(404, "disabled")
    app = FastAPI(); app.include_router(create_embeddings_router(instance, authorize, enabled)); client = TestClient(app)
    base = f"/novels/{rig.nid}/experimental/embeddings"; headers = {"X-Session-Token": "valid"}
    assert client.get(base + "/status").status_code == 403
    assert client.get(base + "/status", headers=headers).json()["status"] == "NOT_CONFIGURED"
    row = client.post(base + "/indexes", headers=headers, json={"title": "New", "entities": [{"entity_type": "CHARACTER", "entity_id": "alice"}]}).json()
    response = client.post(base + f"/indexes/{row['id']}/rebuild", headers=headers, json={"expected_version": 1})
    assert response.status_code == 422 and "NOT_CONFIGURED" in response.text
    flags.clear()
    assert client.get(base + "/indexes", headers=headers).status_code == 404


def test_embedding_provider_change_at_final_guard_cannot_dispatch(rig):
    called = []
    class Replacement(MockEmbeddingProvider):
        capability = MockEmbeddingProvider.capability.model_copy(update={"local": False})
        def embed(self, inputs):
            called.append(inputs)
            return super().embed(inputs)
    instance = service(rig, MockEmbeddingProvider()); row = index(rig, instance)
    def swap():
        instance.provider = Replacement()
    with pytest.raises(StaleSourceError, match="PROVIDER_CHANGED"):
        instance.rebuild(rig.nid, rig.scope, rig.actor, row["id"], 1, check_authority=swap)
    assert called == []


def test_embedding_scene_keeps_original_chapter_provenance(rig):
    screenplay = rig.screenplays.create(rig.nid)
    instance = service(rig, MockEmbeddingProvider())
    rig.chapters.save(rig.chapter["id"], {"version": rig.chapter["version"], "content": "Completely new chapter"})
    with pytest.raises(StaleSourceError, match="SCENE_SOURCE_VERSION_CHANGED"):
        instance.create_index(rig.nid, rig.scope, rig.actor, {"title": "Scene", "entities": [{"entity_type": "SCENE",
            "entity_id": screenplay["scenes"][0]["id"], "screenplay_id": screenplay["id"]}]})

"""Original generation persistence must never adopt a reused project slug.

Both profiles use real original owners and raw ExperimentalStore documents.
PostgreSQL cases require the dedicated real database, never a Session fake.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Event
from uuid import uuid4

import pytest

from app.repositories.generation_repository import GenerationProjectIdentityError
from test_v2_independent_workspace import rig  # Real File/PostgreSQL owner fixture.


def record(e):
    return {
        "id": str(uuid4()), "novel_id": e.nid, "chapter_id": None,
        "operation": "graph_text", "experimental_origin": "creative_graph_model",
        "actor_id": e.actor, "scope": deepcopy(e.scope), "status": "GENERATING",
        "expected_request_digest": "d" * 64,
        "graph_binding": {
            "graph_id": "graph-a", "graph_version": 1, "run_id": "run-a", "node_id": "model",
            "project_incarnation": e.store.incarnation(e.nid), "input_digest": "a" * 64,
            "reviewed_preview_digest": "b" * 64, "route_fingerprint": "c" * 64,
        },
    }


def seed_raw_source(e):
    with e.raw_store.transaction(e.nid, e.scope) as document:
        document["collections"]["creative_documents_v2"] = {
            "original-source": {"id": "original-source", "version": 1,
                "project_incarnation": e.store.incarnation(e.nid), "content": "Original source"}}
    return e.raw_store.read(e.nid, e.scope)


def test_same_slug_recreation_cannot_receive_late_original_generation(rig):
    e = rig; repository = e.bundle.generations; item = record(e)
    source = seed_raw_source(e)
    repository.save(item)
    assert repository.get(item["id"])["graph_binding"] == item["graph_binding"]
    original_bytes = (e.root / "runtime/jobs" / (item["id"] + ".json")).read_bytes() if e.backend == "file" else None
    e.novels.delete(e.nid)
    e.create_project(nid=e.nid)
    new_owner = e.store.incarnation(e.nid)
    assert new_owner != item["graph_binding"]["project_incarnation"]
    item.update(status="COMPLETED", output="Late discarded original output")
    with pytest.raises(GenerationProjectIdentityError, match="OWNER_CHANGED"):
        repository.save(item)
    with pytest.raises(KeyError): repository.get(item["id"])
    assert item["id"] not in {row["id"] for row in repository.load_all()}
    assert e.raw_store.read(e.nid, e.scope) == source
    assert e.chapters.list(e.nid) == []
    if e.backend == "file":
        assert (e.root / "runtime/jobs" / (item["id"] + ".json")).read_bytes() == original_bytes
    else:
        with e.raw_store._connect() as connection:
            assert connection.execute("SELECT count(*) FROM generation_jobs WHERE id = %s", (item["id"],)).fetchone()[0] == 0


def test_missing_original_project_save_and_load_never_recreate_an_owner(rig):
    e = rig; repository = e.bundle.generations; item = record(e)
    repository.save(item); e.novels.delete(e.nid)
    with pytest.raises(GenerationProjectIdentityError, match="OWNER_CHANGED"): repository.save(item)
    with pytest.raises(KeyError): repository.get(item["id"])
    assert item["id"] not in {row["id"] for row in repository.load_all()}
    with pytest.raises(FileNotFoundError): e.novels.get(e.nid)
    if e.backend == "file": assert not (e.root / "novels" / e.nid).exists()


@pytest.mark.parametrize("change", ["actor_id", "scope", "graph_binding", "expected_request_digest"])
def test_existing_graph_generation_binding_is_immutable(rig, change):
    e = rig; repository = e.bundle.generations; item = record(e)
    repository.save(item); changed = deepcopy(item)
    if change == "scope": changed["scope"] = dict(item["scope"], mode="collaboration", workspace_id="w", storyline_id="s", branch_id="b")
    elif change == "graph_binding": changed[change]["node_id"] = "other-node"
    else: changed[change] = "e" * 64
    with pytest.raises(GenerationProjectIdentityError, match="BINDING_CHANGED"): repository.save(changed)
    assert repository.get(item["id"])[change] == item[change]


def test_project_delete_waits_for_original_generation_save_transaction(rig, monkeypatch):
    e = rig; repository = e.bundle.generations; item = record(e); repository.save(item)
    import app.repositories.generation_repository as file_module
    import app.repositories.postgres.generation as postgres_module
    module = file_module if e.backend == "file" else postgres_module
    original = module.check_graph_job_update
    saving, release, deleting = Event(), Event(), Event()

    def held_check(previous, current):
        original(previous, current)
        saving.set()
        assert release.wait(5), "test must release the existing save transaction"

    def remove():
        deleting.set()
        e.novels.delete(e.nid)

    monkeypatch.setattr(module, "check_graph_job_update", held_check)
    with ThreadPoolExecutor(max_workers=2) as pool:
        save = pool.submit(repository.save, dict(item, status="COMPLETED"))
        try:
            assert saving.wait(5)
            deletion = pool.submit(remove)
            assert deleting.wait(5)
            # A completion event avoids depending on immediate thread scheduling.
            ended = Event(); deletion.add_done_callback(lambda _: ended.set())
            assert not ended.wait(.2), "project DELETE escaped the save's owner lock"
        finally:
            release.set()
        save.result(timeout=5); deletion.result(timeout=5)
    e.create_project(nid=e.nid); assert e.store.incarnation(e.nid) != item["graph_binding"]["project_incarnation"]
    with pytest.raises(GenerationProjectIdentityError): repository.save(item)
    with pytest.raises(KeyError): repository.get(item["id"])


def test_save_composes_with_existing_creative_owner_lease(rig):
    e = rig; item = record(e)
    # Separate PostgreSQL connections hold compatible KEY SHARE locks.
    # Use a bounded SQL lock timeout so accidental FOR UPDATE fails, not hangs.
    if e.backend == "postgres":
        from sqlalchemy import event
        engine = e.bundle.generations.database.engine
        def timeout(connection):
            connection.exec_driver_sql("SET LOCAL lock_timeout = '1500ms'")
        event.listen(engine, "begin", timeout)
    try:
        with e.store.owner_lease(e.nid): e.bundle.generations.save(item)
        assert e.bundle.generations.get(item["id"])["status"] == "GENERATING"
    finally:
        if e.backend == "postgres": event.remove(engine, "begin", timeout)


@pytest.mark.file_backend_only
def test_file_load_and_save_do_not_provision_a_missing_owner_marker(tmp_path):
    from app.repository import FileRepository
    from app.repositories.file.generation import FileGenerationRepository
    from app.experimental.store import ExperimentalStore
    from app.creative.project_store import CreativeProjectStore
    from types import SimpleNamespace
    owners = FileRepository(tmp_path); owners.create_novel({"id": "bare", "title": "Bare"})
    raw = ExperimentalStore(tmp_path, "file", "")
    e = SimpleNamespace(nid="bare", actor="author", scope={"mode": "local", "novel_id": "bare"}, store=CreativeProjectStore(raw))
    repository = FileGenerationRepository(tmp_path); item = record(e); repository.save(item)
    marker = tmp_path / "novels/bare/creative_project_v2.json"; marker.unlink()
    with pytest.raises(GenerationProjectIdentityError): repository.save(item)
    with pytest.raises(KeyError): repository.get(item["id"])
    assert repository.load_all() == [] and not marker.exists()
    assert (tmp_path / "novels/bare").is_dir()


def test_non_graph_generation_keeps_original_owner_contract(rig):
    e = rig; repository = e.bundle.generations
    legacy = {"id": str(uuid4()), "novel_id": e.nid, "operation": "writer", "status": "QUEUED"}
    repository.save(legacy); repository.save(dict(legacy, status="COMPLETED"))
    assert repository.get(legacy["id"])["status"] == "COMPLETED"

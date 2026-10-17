"""Inert CreativeDirector evidence over original generation persistence owners.

File cases use real files and JobManager reopen. PostgreSQL cases deliberately
reuse the original real-database fixture: definitions are not mock DB evidence.
No source validation, provider execution, public dispatch, or content adoption is
conferred by any record constructed here.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Event
from uuid import uuid4

import pytest

from app.creative.director_binding import CreativeDirectorBinding
from app.jobs import Job, JobManager, generation_content_available
from app.repositories.generation_repository import GenerationProjectIdentityError
from app.services.generation_service import GenerationService
from test_v2_independent_workspace import rig


class ForbiddenOwner:
    def __getattr__(self, name):
        raise AssertionError("Passive CreativeDirector record accessed live owner: " + name)


def record(e, status="QUEUED"):
    binding = CreativeDirectorBinding.model_validate({
        "contract": "CREATIVE_DIRECTOR_SOURCE_V1", "source_kind": "STORYBOARD",
        "project_id": e.nid, "project_incarnation": e.store.incarnation(e.nid),
        "actor_id": e.actor, "scope": deepcopy(e.scope),
        "source_document_id": "storyboard-source", "source_version": 1,
        "source_digest": "a" * 64, "reviewed_preview_digest": "b" * 64,
    }).model_dump(mode="json")
    return Job(id=str(uuid4()), operation="creative_director_text", novel_id=e.nid,
        chapter_id=None, instruction="Passive persistence fixture", profile="LOCAL_ONLY",
        status=status, actor_id=e.actor, scope=deepcopy(e.scope),
        experimental_origin="creative_director_source_model",
        creative_director_binding=binding, expected_request_digest="d" * 64).public()


def reopen(e):
    owner = ForbiddenOwner()
    return JobManager(GenerationService(e.bundle.generations), owner, owner, owner,
        memory_extractor=owner, snapshot_required=True, collaboration_updates=owner)


def assert_inert(job):
    assert not generation_content_available(job)
    for name in ("request_authorization", "prepared_text_invocation", "author_preparation_guard",
                 "before_dispatch", "on_terminal", "author_context_resolver", "character_context_resolver"):
        assert getattr(job, name) is None


def assert_saved_unchanged(e, item):
    assert e.bundle.generations.get(item["id"]) == item
    assert e.chapters.list(e.nid) == []


def test_actual_owner_roundtrip_and_detached_public_binding(rig):
    e = rig; item = record(e, "COMPLETED"); repo = e.bundle.generations
    repo.save(item)
    assert repo.get(item["id"]) == item
    assert item in repo.load_all()
    loaded = reopen(e).get(item["id"])
    assert_inert(loaded)
    assert loaded.creative_director_binding == item["creative_director_binding"]
    public = loaded.public()
    public["creative_director_binding"]["scope"]["novel_id"] = "detached-copy"
    assert loaded.creative_director_binding == item["creative_director_binding"]
    assert_saved_unchanged(e, item)


@pytest.mark.parametrize("status", ["QUEUED", "PREPARED", "RUNNING", "GENERATING", "SETTLING", "COMPLETED"])
def test_restart_never_rebuilds_authority_replays_or_releases_ledger(rig, monkeypatch, status):
    e = rig; item = record(e, status)
    item.update(output="Injected completed text is not execution evidence", execution_outcome="SUCCEEDED",
        dispatch_hooks_required=True, terminal_hook_status="COMPLETED")
    e.bundle.generations.save(item)
    before = e.raw_store.read(e.nid, e.scope)
    calls = []
    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("Passive reopen attempted execution or settlement")
    for method in ("start_prepared", "_run"):
        monkeypatch.setattr(JobManager, method, forbidden)
    manager = reopen(e); loaded = manager.get(item["id"])
    assert_inert(loaded)
    assert loaded.status == ("COMPLETED" if status == "COMPLETED" else "FAILED")
    assert loaded.creative_director_binding == item["creative_director_binding"]
    assert loaded.expected_request_digest == item["expected_request_digest"]
    assert e.raw_store.read(e.nid, e.scope) == before
    assert e.chapters.list(e.nid) == [] and calls == []
    second = reopen(e).get(item["id"])
    assert_inert(second)
    assert second.public() == loaded.public()


@pytest.mark.parametrize("field,value", [
    ("project_id", "other-project"), ("project_incarnation", "file:00000000-0000-4000-8000-000000000000"),
    ("actor_id", "other-author"), ("scope", {"mode": "local", "novel_id": "other-project"}),
    ("source_document_id", "other-source"), ("source_version", 2), ("source_digest", "c" * 64),
    ("reviewed_preview_digest", "c" * 64), ("contract", "CREATIVE_ADAPTATION_V1"),
    ("source_kind", "SCREENPLAY"),
])
def test_every_persisted_binding_field_is_immutable(rig, field, value):
    e = rig; item = record(e); e.bundle.generations.save(item)
    changed = deepcopy(item); changed["creative_director_binding"][field] = value
    with pytest.raises(GenerationProjectIdentityError): e.bundle.generations.save(changed)
    assert_saved_unchanged(e, item)


@pytest.mark.parametrize("field,value", [
    ("actor_id", "other-author"), ("scope", None), ("novel_id", "other-project"),
    ("operation", "brainstorm"), ("experimental_origin", "creative_director_model"),
    ("chapter_id", "wrong-chapter"), ("expected_request_digest", "e" * 64),
    ("creative_director_binding", None), ("graph_binding", {}), ("adaptation_binding", {}),
])
def test_job_authority_discriminators_and_request_identity_are_immutable(rig, field, value):
    e = rig; item = record(e); e.bundle.generations.save(item)
    changed = deepcopy(item); changed[field] = value
    with pytest.raises(GenerationProjectIdentityError): e.bundle.generations.save(changed)
    assert_saved_unchanged(e, item)


def test_complete_binding_removal_cannot_downgrade_saved_record(rig):
    e = rig; item = record(e); e.bundle.generations.save(item)
    changed = deepcopy(item)
    changed.pop("creative_director_binding"); changed.pop("expected_request_digest")
    changed.update(operation="writer", experimental_origin=None, actor_id=None, scope=None)
    with pytest.raises(GenerationProjectIdentityError): e.bundle.generations.save(changed)
    assert_saved_unchanged(e, item)


@pytest.mark.parametrize("field,value", [
    ("creative_director_binding", None), ("operation", "graph_text"),
    ("experimental_origin", "creative_graph_model"), ("experimental_origin", "creative_director_model"),
    ("experimental_origin", None), ("chapter_id", "wrong-chapter"), ("actor_id", None),
    ("actor_id", "other-author"), ("scope", None),
    ("scope", {"mode": "local", "novel_id": "wrong-project"}),
    ("scope", {"mode": "local", "novel_id": "extra", "hidden": True}),
    ("graph_binding", {}), ("adaptation_binding", {}),
    ("expected_request_digest", None), ("expected_request_digest", "A" * 64),
    ("expected_request_digest", "f" * 63), ("expected_request_digest", True),
])
def test_invalid_new_record_never_reaches_durable_store(rig, field, value):
    e = rig; item = record(e); item[field] = value
    with pytest.raises(GenerationProjectIdentityError): e.bundle.generations.save(item)
    assert item["id"] not in {row["id"] for row in e.bundle.generations.load_all()}
    assert e.chapters.list(e.nid) == []


def test_late_save_cannot_adopt_recreated_public_project_slug(rig):
    e = rig; item = record(e); repo = e.bundle.generations; repo.save(item)
    old_identity = item["creative_director_binding"]["project_incarnation"]
    e.novels.delete(e.nid); e.create_project(nid=e.nid)
    assert e.store.incarnation(e.nid) != old_identity
    with pytest.raises(GenerationProjectIdentityError, match="OWNER_CHANGED"):
        repo.save(dict(item, status="COMPLETED", output="Late output"))
    with pytest.raises(KeyError): repo.get(item["id"])
    assert item["id"] not in {row["id"] for row in repo.load_all()}
    assert item["id"] not in reopen(e).jobs
    assert e.chapters.list(e.nid) == []


def test_deleted_owner_is_not_recreated_by_save_load_or_restart(rig):
    e = rig; item = record(e); repo = e.bundle.generations; repo.save(item)
    e.novels.delete(e.nid)
    with pytest.raises(GenerationProjectIdentityError, match="OWNER_CHANGED"): repo.save(item)
    with pytest.raises(KeyError): repo.get(item["id"])
    assert item["id"] not in {row["id"] for row in repo.load_all()}
    assert item["id"] not in reopen(e).jobs
    with pytest.raises(FileNotFoundError): e.novels.get(e.nid)
    if e.backend == "file": assert not (e.root / "novels" / e.nid).exists()


@pytest.mark.file_backend_only
@pytest.mark.parametrize("rig", ["file"], indirect=True)
def test_missing_marker_is_never_provisioned_by_persistence(rig):
    e = rig; item = record(e); repo = e.bundle.generations; repo.save(item)
    marker = e.root / "novels" / e.nid / "creative_project_v2.json"
    marker.unlink()
    with pytest.raises(GenerationProjectIdentityError): repo.save(item)
    with pytest.raises(KeyError): repo.get(item["id"])
    assert repo.load_all() == [] and reopen(e).jobs == {}
    assert not marker.exists() and (e.root / "novels" / e.nid).is_dir()


def test_existing_owner_lease_composes_with_bound_generation_save(rig):
    e = rig; item = record(e)
    if e.backend == "postgres":
        from sqlalchemy import event
        engine = e.bundle.generations.database.engine
        def timeout(connection): connection.exec_driver_sql("SET LOCAL lock_timeout = '1500ms'")
        event.listen(engine, "begin", timeout)
    try:
        with e.store.owner_lease(e.nid): e.bundle.generations.save(item)
        assert_saved_unchanged(e, item)
    finally:
        if e.backend == "postgres": event.remove(engine, "begin", timeout)


def test_delete_waits_for_existing_generation_owner_transaction(rig, monkeypatch):
    e = rig; item = record(e); repo = e.bundle.generations; repo.save(item)
    import app.repositories.generation_repository as file_module
    import app.repositories.postgres.generation as postgres_module
    module = file_module if e.backend == "file" else postgres_module
    original = module.check_graph_job_update
    saving, release, deleting, ended = Event(), Event(), Event(), Event()
    def held_check(previous, current):
        original(previous, current); saving.set()
        assert release.wait(5), "test did not release save transaction"
    def remove():
        deleting.set(); e.novels.delete(e.nid)
    monkeypatch.setattr(module, "check_graph_job_update", held_check)
    with ThreadPoolExecutor(max_workers=2) as pool:
        save = pool.submit(repo.save, dict(item, status="COMPLETED"))
        try:
            assert saving.wait(5)
            deletion = pool.submit(remove)
            assert deleting.wait(5)
            deletion.add_done_callback(lambda _: ended.set())
            assert not ended.wait(.2), "DELETE escaped the existing owner lock"
        finally: release.set()
        save.result(timeout=5); deletion.result(timeout=5)
    e.create_project(nid=e.nid)
    assert e.store.incarnation(e.nid) != item["creative_director_binding"]["project_incarnation"]
    with pytest.raises(GenerationProjectIdentityError): repo.save(item)
    with pytest.raises(KeyError): repo.get(item["id"])


@pytest.mark.file_backend_only
@pytest.mark.parametrize("rig", ["file"], indirect=True)
@pytest.mark.parametrize("after_commit", [False, True])
def test_file_commit_uncertainty_never_grants_output_or_restart_authority(rig, monkeypatch, after_commit):
    e = rig; item = record(e, "COMPLETED"); repo = e.bundle.generations
    import app.repositories.generation_repository as module
    original = module.atomic_write
    def uncertain(path, data):
        if after_commit: original(path, data)
        raise OSError("synthetic uncertain generation write")
    item["output"] = "Stored bytes alone cannot grant authority"
    with monkeypatch.context() as patch:
        patch.setattr(module, "atomic_write", uncertain)
        with pytest.raises(OSError, match="uncertain"): repo.save(item)
    manager = reopen(e)
    if after_commit:
        assert repo.get(item["id"]) == item
        assert_inert(manager.get(item["id"]))
    else:
        with pytest.raises(KeyError): repo.get(item["id"])
        assert item["id"] not in manager.jobs
    assert e.chapters.list(e.nid) == []


def test_full_collaboration_scope_roundtrips_without_becoming_branch_authority(rig):
    e = rig
    e.scope = {"mode": "collaboration", "novel_id": e.nid,
        "workspace_id": "workspace-a", "storyline_id": "storyline-a", "branch_id": "branch-a"}
    item = record(e, "COMPLETED"); e.bundle.generations.save(item)
    assert_inert(reopen(e).get(item["id"]))
    for field in ("workspace_id", "storyline_id", "branch_id"):
        changed = deepcopy(item)
        changed["scope"][field] = "other"
        changed["creative_director_binding"]["scope"][field] = "other"
        with pytest.raises(GenerationProjectIdentityError): e.bundle.generations.save(changed)
    changed = deepcopy(item)
    changed["actor_id"] = changed["creative_director_binding"]["actor_id"] = "other-author"
    with pytest.raises(GenerationProjectIdentityError): e.bundle.generations.save(changed)
    assert_saved_unchanged(e, item)


def test_serialized_transient_fields_are_not_restored_as_capabilities(rig):
    e = rig; item = record(e, "COMPLETED")
    for name in ("request_authorization", "prepared_text_invocation", "author_preparation_guard",
                 "before_dispatch", "on_terminal", "author_context_resolver", "character_context_resolver"):
        item[name] = {"forged": "serialized data is not a capability"}
    item.update(output="Injected output", execution_outcome="SUCCEEDED", terminal_hook_status="COMPLETED")
    e.bundle.generations.save(item)
    loaded = reopen(e).get(item["id"])
    assert_inert(loaded)
    assert e.chapters.list(e.nid) == []


@pytest.mark.parametrize("domain", ["graph", "adaptation", "author"])
@pytest.mark.parametrize("creative_first", [False, True])
def test_valid_cross_domain_records_cannot_replace_same_job_identity(rig, domain, creative_first):
    """Each candidate is independently valid; denial is the immutable boundary."""
    from app.repositories.generation_repository import graph_job_binding
    e = rig; creative = record(e, "COMPLETED")
    other = deepcopy(creative); other.pop("creative_director_binding")
    if domain == "graph":
        other.update(operation="graph_text", experimental_origin="creative_graph_model",
            graph_binding={"graph_id": "graph-a", "graph_version": 1, "run_id": "run-a", "node_id": "model",
                "project_incarnation": creative["creative_director_binding"]["project_incarnation"],
                "input_digest": "a" * 64, "reviewed_preview_digest": "b" * 64, "route_fingerprint": "c" * 64})
    elif domain == "adaptation":
        chapter = e.chapters.create(e.nid, {"title": "Existing source", "content": "Saved source text"})
        other.update(operation="brainstorm", experimental_origin="creative_adaptation_model",
            actor_id=None, scope=None, chapter_id=chapter["id"],
            adaptation_binding={"contract": "CREATIVE_ADAPTATION_V1", "proposal_id": "proposal-a",
                "project_id": e.nid, "actor_id": e.actor, "scope": deepcopy(e.scope),
                "project_incarnation": creative["creative_director_binding"]["project_incarnation"],
                "chapter_id": chapter["id"], "source_version": 1,
                "source_digest": "a" * 64, "preview_digest": "b" * 64})
    else:
        other.update(operation="writer", experimental_origin="author_context", actor_id=None, scope=None)
    assert graph_job_binding(creative) is not None
    assert (graph_job_binding(other) is not None) == (domain != "author")
    previous, replacement = (creative, other) if creative_first else (other, creative)
    chapters = deepcopy(e.chapters.list(e.nid))
    e.bundle.generations.save(previous)
    with pytest.raises(GenerationProjectIdentityError): e.bundle.generations.save(replacement)
    assert e.bundle.generations.get(previous["id"]) == previous
    assert e.chapters.list(e.nid) == chapters

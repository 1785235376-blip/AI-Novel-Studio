"""A43-02/03 identity integration contracts on disposable original repositories.

The mounted matrix is File / actual PostgreSQL x /api / /api/v1 x OFF / ON /
V1 x original numeric / legacy-qualified UUID namespaces. PostgreSQL is never emulated and needs TEST_POSTGRES_DATABASE_URL. Queued
jobs below use the original prepare/persist/read/accept owners, with explicitly
synthetic completion payloads; they make no model/provider quality claim.
"""
from __future__ import annotations

import copy
import json
import shutil
import time
from threading import Barrier, Event, Lock, Thread
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy import select, text

from app.autosave.durable import DurableVersionAutosaveAdapter
from app.config import Settings, settings
from app.collaboration_api import CollaborationReadService
from app.experimental.search_sources import chapter_manifest
from app.document import markdown_to_document
from app.experimental.flags import FLAGS
from app.jobs import JobManager
from app.repositories.factory import create_repository_bundle
from app.repositories.postgres.common import chapter_or_raise, external_uuid
from app.repositories.postgres.models import DocumentVersionModel, GenerationJobModel, NovelModel
from app.services import CanonService, ChapterService, ContextService, GenerationService, NovelService
from app.services.context_snapshot_service import ContextSnapshotService
from app.services.export_job_service import ExportJobService
from test_r3_mounted_contracts import checked, mounted, prefix


@pytest.fixture(params=["numeric", "qualified"])
def source_namespace(request):
    return request.param


def _assert_qualified(cid, novel_id):
    assert cid.startswith(novel_id + ":~"), cid
    token = cid.removeprefix(novel_id + ":~")
    assert str(UUID(token)) == token, cid


@pytest.fixture(params=["off", "on", "v1"])
def identity_app(mounted, request, monkeypatch, source_namespace):
    e = mounted
    e.feature_mode = request.param
    e.source_namespace = source_namespace
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "" if request.param == "off" else ",".join(FLAGS))
    monkeypatch.setenv("V1_ACCEPTANCE_MODE", "true" if request.param == "v1" else "false")
    # PG's original same-host acceptance coordinator must remain fixture-local.
    object.__setattr__(settings, "novel_data", e.root)
    if source_namespace == "qualified":
        if e.backend == "file":
            # Disposable copy of an existing source layout without an allocation
            # journal models a pre-fix project. Never remove a real user's log.
            (e.root / "novels" / e.nid / "chapter_identity.json").unlink(missing_ok=True)
        elif hasattr(NovelModel, "chapter_identity_provenance"):
            # Explicit historical provenance on this fixture's project only.
            # Untouched baseline has no such field and then fails the public
            # namespace assertion below, rather than emulating PostgreSQL.
            with e.bundle.chapters.database.session() as session:
                session.execute(text("UPDATE novels SET chapter_identity_provenance='LEGACY_UNKNOWN' WHERE slug=:nid"), {"nid": e.nid})
        created = checked(e.client.post(e.prefix + f"/novels/{e.nid}/chapters", json={
            "title": "Distinct A", "content": 'A_ONLY_MANUSCRIPT_甲\nAlice said: “Let us enter.”\nThe city gate opened.',
        }), 201)
        e.chapters.delete(e.chapter["id"])
        e.a = e.chapters.get(created["id"])
    else:
        e.a = e.chapters.get(e.chapter["id"])
    e.b = checked(e.client.post(e.prefix + f"/novels/{e.nid}/chapters", json={
        "title": "Distinct B", "content": "B_ONLY_MANUSCRIPT_乙",
    }), 201)
    e.b = e.chapters.get(e.b["id"])
    assert e.a["version"] == e.b["version"] == 1
    flags = checked(e.client.get(e.prefix + "/experimental/features"))
    assert any(flags["features"].values()) is (request.param == "on")
    return e


def _assert_namespace(e):
    if e.source_namespace == "qualified":
        _assert_qualified(e.a["id"], e.nid)
        _assert_qualified(e.b["id"], e.nid)


def _move(e):
    return checked(e.client.post(e.prefix + f"/chapters/{e.a['id']}/move", json={"direction": "down"}))["order"]


def _uuid(e, cid):
    if e.backend != "postgres":
        return None
    with e.bundle.chapters.database.session() as session:
        _, row = chapter_or_raise(session, cid)
        return row.id


def _manager(e, monkeypatch):
    manager = JobManager(
        GenerationService(e.bundle.generations), e.chapters,
        ContextService(e.bundle.novels, e.bundle.chapters), CanonService(e.bundle.canon),
        memory_extractor=SimpleNamespace(enqueue=lambda *_: None), snapshot_required=False,
    )
    monkeypatch.setattr(e.api, "jobs", manager)
    return manager


def _queued(e, manager, *, snapshot=False):
    job = manager.prepare_job("polish", {"novel_id": e.nid, "chapter_id": e.a["id"], "profile": "LOCAL_ONLY"})
    job.status = "QUEUED"
    manager.jobs[job.id] = job
    if snapshot:
        captured = ContextSnapshotService(e.bundle.lore).create(
            e.a["id"], e.a["version"], {"canon": [], "characters": [], "timeline": []},
            "a43-synthetic:v1", "none-no-provider-called", generation_id=job.id,
        )
        job.context_snapshot_id = captured["id"]
    manager._persist(job)
    return job


def test_same_version_old_url_save_history_and_uuid_keep_the_original_owner(identity_app):
    e = identity_app
    _assert_namespace(e)
    original_a, original_b = copy.deepcopy(e.a), copy.deepcopy(e.b)
    a_uuid, b_uuid = _uuid(e, e.a["id"]), _uuid(e, e.b["id"])
    # Equal version two is deliberate: CAS alone cannot distinguish swapped IDs.
    for chapter, marker in ((e.a, "A_SECOND_VERSION"), (e.b, "B_SECOND_VERSION")):
        checked(e.client.put(e.prefix + f"/chapters/{chapter['id']}", json={"version": 1, "content": marker}))
    a, b = e.chapters.get(e.a["id"]), e.chapters.get(e.b["id"])
    histories = {c["id"]: e.chapters.history(c["id"]) for c in (a, b)}
    assert _move(e) == [b["id"], a["id"]]
    for chapter in (a, b):
        loaded = checked(e.client.get(e.prefix + f"/chapters/{chapter['id']}"))
        assert loaded["document"] == chapter["document"]
        assert loaded["version"] == chapter["version"] == 2
        assert checked(e.client.get(e.prefix + f"/chapters/{chapter['id']}/history")) == histories[chapter["id"]]
    assert (_uuid(e, a["id"]), _uuid(e, b["id"])) == (a_uuid, b_uuid)
    saved = checked(e.client.put(e.prefix + f"/chapters/{a['id']}", json={"version": 2, "content": "A_OLD_URL_SAVED"}))
    assert saved["id"] == a["id"] and saved["version"] == 3
    assert e.chapters.get(b["id"])["document"] == b["document"]
    rejected = e.client.put(e.prefix + f"/chapters/{a['id']}", json={"version": 2, "content": "LOSER"})
    assert rejected.status_code == 409
    assert rejected.json()["detail"]["conflict"]["resource_id"] == a["id"]
    restored = checked(e.client.post(e.prefix + f"/chapters/{a['id']}/history/1/restore", params={"expected_version": 3}))
    assert restored["document"] == original_a["document"]
    assert e.chapters.history(b["id"])[0]["document"] == original_b["document"]
    if e.backend == "postgres":
        with e.bundle.chapters.database.session() as session:
            histories_by_uuid = {cid: session.scalars(select(DocumentVersionModel).where(DocumentVersionModel.chapter_id == cid)).all() for cid in (a_uuid, b_uuid)}
            assert {r.version for r in histories_by_uuid[a_uuid]} == {1, 2, 3}
            assert {r.version for r in histories_by_uuid[b_uuid]} == {1}
            assert histories_by_uuid[b_uuid][0].document == original_b["document"]

    current = e.chapters.get(a["id"])
    archived = checked(e.client.post(e.prefix + f"/chapters/{a['id']}/archive", params={"expected_version": current["version"]}))
    assert archived["id"] == a["id"] and archived["is_archived"] is True
    assert [c["id"] for c in e.chapters.repository.list_archived(e.nid)] == [a["id"]]
    unarchived = checked(e.client.post(e.prefix + f"/chapters/{a['id']}/restore-archive", params={"expected_version": e.chapters.get(a["id"])["version"]}))
    assert unarchived["id"] == a["id"] and unarchived["is_archived"] is False
    assert e.chapters.get(a["id"])["document"] == current["document"]
    assert e.chapters.get(b["id"])["document"] == b["document"]
    if e.source_namespace == "qualified":
        for chapter in (a, b):
            assert e.client.get(e.prefix + f"/chapters/{e.nid}:{chapter['number']}").status_code == 404


def test_queued_old_task_result_and_accept_after_move_keep_uuid_and_source(identity_app, monkeypatch):
    e = identity_app
    _assert_namespace(e)
    manager = _manager(e, monkeypatch)
    a_uuid = _uuid(e, e.a["id"])
    job = _queued(e, manager, snapshot=True)
    before = e.bundle.generations.get(job.id)
    assert before["chapter_id"] == e.a["id"] and before["base_chapter_version"] == 1
    _move(e)
    dispatch_source = manager._validate_outbound_sources(job, False)
    assert dispatch_source["id"] == e.a["id"] and dispatch_source["document"] == e.a["document"]
    # Model-free completion through the original persistence callback owner.
    job.output, job.status = "A_APPROVED_SYNTHETIC_DRAFT", "COMPLETED"
    manager._persist(job)
    stored = e.bundle.generations.get(job.id)
    assert stored["chapter_id"] == e.a["id"]
    assert stored["context_snapshot_id"] == before["context_snapshot_id"]
    result = checked(e.client.get(e.prefix + f"/generation/{job.id}"))
    assert result["chapter_id"] == e.a["id"]
    assert "Alice said" in result["diff"] and "B_ONLY_MANUSCRIPT" not in result["diff"]
    if e.backend == "postgres":
        with e.bundle.chapters.database.session() as session:
            assert session.get(GenerationJobModel, external_uuid(job.id)).chapter_id == a_uuid
            snapshot_owner = session.execute(text("SELECT chapter_id, snapshot FROM chapter_context_snapshots WHERE id=:id"), {"id": external_uuid(job.context_snapshot_id)}).one()
            assert snapshot_owner.chapter_id == a_uuid
            assert snapshot_owner.snapshot["chapter_version_id"] == e.a["id"] + ":v1"
    accepted = checked(e.client.post(e.prefix + f"/generation/{job.id}/accept", json={"expected_version": 1}))
    assert accepted["chapter"]["id"] == e.a["id"]
    assert accepted["chapter"]["content"].strip() == "A_APPROVED_SYNTHETIC_DRAFT"
    assert e.chapters.get(e.b["id"])["document"] == e.b["document"]
    assert e.chapters.history(e.a["id"])[0]["document"] == e.a["document"]
    assert _uuid(e, e.a["id"]) == a_uuid


def test_deleted_old_task_callback_result_accept_and_old_save_never_target_replacement(identity_app, monkeypatch):
    e = identity_app
    _assert_namespace(e)
    manager = _manager(e, monkeypatch)
    job = _queued(e, manager)
    # Delete every original chapter: old max+1 allocators now reuse exactly A's ID.
    for chapter in (e.a, e.b):
        response = e.client.delete(e.prefix + f"/chapters/{chapter['id']}")
        assert response.status_code == 204
    new = checked(e.client.post(e.prefix + f"/novels/{e.nid}/chapters", json={"title": "Replacement", "content": "NEW_GENERATION_ONLY"}), 201)
    new_before = e.chapters.get(new["id"])
    with pytest.raises(FileNotFoundError):
        manager._validate_outbound_sources(job, False)
    job.output, job.status = "LATE_DELETED_TASK_RESULT", "COMPLETED"
    # PG may refuse completion because its original chapter has gone. File can
    # retain the detached result. Neither is allowed to relink a new chapter.
    try:
        manager._persist(job)
    except FileNotFoundError:
        pass
    stored = e.bundle.generations.get(job.id)
    assert stored["chapter_id"] == e.a["id"]
    assert new["id"] not in {e.a["id"], e.b["id"]}
    assert e.client.get(e.prefix + f"/generation/{job.id}").status_code == 404
    assert e.client.post(e.prefix + f"/generation/{job.id}/accept", json={"expected_version": 1}).status_code in {404, 409}
    assert e.client.get(e.prefix + f"/chapters/{e.a['id']}").status_code == 404
    assert e.client.put(e.prefix + f"/chapters/{e.a['id']}", json={"version": 1, "content": "STALE_EDITOR"}).status_code == 404
    with pytest.raises(FileNotFoundError):
        e.chapters.save(e.a["id"], {"version": 1, "content": "STALE_EDITOR"})
    assert e.chapters.get(new["id"]) == new_before
    assert e.chapters.history(new["id"]) == []
    assert e.bundle.canon.list_pending(e.nid) == []
    if e.backend == "postgres":
        with e.bundle.chapters.database.session() as session:
            assert session.get(GenerationJobModel, external_uuid(job.id)).chapter_id is None


def test_cached_autosave_identity_survives_move_and_fails_closed_after_delete_restart(identity_app):
    e = identity_app
    _assert_namespace(e)
    adapter = DurableVersionAutosaveAdapter(e.bundle.chapters.save, load=e.bundle.chapters.get)
    adapter.track(e.a["id"], 1)
    _move(e)
    adapter(e.a["id"], "A_CACHED_EDITOR", 300)
    assert e.chapters.get(e.a["id"])["content"].strip() == "A_CACHED_EDITOR"
    assert e.chapters.get(e.b["id"])["document"] == e.b["document"]
    assert adapter.durable_version(e.a["id"]) == 2
    e.chapters.delete(e.a["id"])
    e.chapters.delete(e.b["id"])
    reopened = create_repository_bundle(Settings(storage_backend=e.backend, database_url=e.url, novel_data=e.root), e.root)
    try:
        new = reopened.chapters.create(e.nid, {"title": "New after restart", "content": "NEW_RESTART_ONLY"})
        assert new["id"] not in {e.a["id"], e.b["id"]}
        with pytest.raises(FileNotFoundError):
            adapter(e.a["id"], "OLD_CACHED_EDITOR_REPLAY", 301)
        assert "NEW_RESTART_ONLY" in reopened.chapters.get(new["id"])["content"]
        assert adapter.durable_version(e.a["id"]) == 2
    finally:
        if e.backend == "postgres":
            reopened.chapters.database.engine.dispose()


def test_graph_evidence_anchor_keeps_object_and_expires_when_order_or_lifecycle_changes(identity_app):
    e = identity_app
    _assert_namespace(e)
    graph = e.experimental.story_graph_service
    quote = "The city gate opened."
    evidence = {"chapter_id": e.a["id"], "quote": quote, "start": e.a["content"].index(quote)}
    # Original source owner can contain persisted records even when UI flags
    # later hide the surface. No flag-bypassing route or test service is added.
    row = graph.create_record(e.nid, e.scope, "local-author", {
        "kind": "STORY_RELATION", "title": "A reference", "chapter_id": e.a["id"],
        "data": {"subject": {"kind": "CHARACTER", "id": "alice"},
                 "object": {"kind": "CHAPTER", "id": e.a["id"]},
                 "relation": "ABOUT", "layer": "WORLD_FACT", "statement": "The gate is in A.", "evidence": [evidence]},
    })
    assert graph.record(e.nid, e.scope, row["id"])["stale"] is False
    _move(e)
    moved = graph.record(e.nid, e.scope, row["id"])
    assert moved["chapter_id"] == e.a["id"] and moved["sources"] == row["sources"]
    assert moved["data"]["evidence"] == [evidence]
    assert moved["stale"] is True  # narrative order changed, so review is needed
    current_source = e.chapters.get(e.a["id"])["content"]
    assert current_source[evidence["start"]:evidence["start"] + len(quote)] == quote
    response = e.client.get(e.base + f"/story-graph/records/{row['id']}")
    assert response.status_code == (200 if e.feature_mode == "on" else 404)
    e.chapters.delete(e.a["id"])
    e.chapters.delete(e.b["id"])
    replacement = e.chapters.create(e.nid, {"title": "Identical prose is a different object", "content": e.a["content"]})
    assert replacement["id"] != e.a["id"]
    deleted = graph.record(e.nid, e.scope, row["id"])
    assert deleted["stale"] is True and deleted["sources"] == row["sources"]


def test_export_queue_freezes_id_document_mapping_before_move_delete_and_replacement(identity_app):
    e = identity_app
    _assert_namespace(e)
    entered, release = Event(), Event()
    def paused_export(nid, format, **kwargs):
        entered.set()
        assert release.wait(8), "A43 export barrier was not released"
        return e.novels.export(nid, format, **kwargs)
    queue = ExportJobService(e.root / "a43-export", paused_export, snapshotter=e.novels.export_snapshot)
    try:
        queued = queue.create(e.nid, "json")
        assert entered.wait(8), "Original export queue did not enter exporter"
        frozen = copy.deepcopy(queue.get(queued["id"])["snapshot"])
        original = {c["id"]: c["document"] for c in frozen["source"]["chapters"]}
        assert original == {e.a["id"]: e.a["document"], e.b["id"]: e.b["document"]}
        _move(e)
        current = e.novels.export_snapshot(e.nid, format="json")
        assert [c["id"] for c in current["source"]["chapters"]] == [e.b["id"], e.a["id"]]
        assert {c["id"]: c["document"] for c in current["source"]["chapters"]} == original
        e.chapters.delete(e.a["id"])
        e.chapters.create(e.nid, {"title": "Later", "content": "LATER_NOT_IN_EXPORT"})
        release.set()
        deadline = time.monotonic() + 8
        while queue.get(queued["id"])["status"] in {"queued", "running"} and time.monotonic() < deadline:
            time.sleep(.01)
        completed = queue.get(queued["id"])
        assert completed["status"] == "succeeded", completed
        assert completed["snapshot"] == frozen
        output = queue.download(queued["id"])["content"].decode("utf-8")
        assert "Alice said" in output and "B_ONLY_MANUSCRIPT" in output
        assert "LATER_NOT_IN_EXPORT" not in output
    finally:
        release.set()
        queue._pool.shutdown(wait=True)


def test_concurrent_move_and_old_url_save_have_one_deterministic_object_outcome(identity_app):
    e = identity_app
    _assert_namespace(e)
    barrier, lock, outcomes = Barrier(3), Lock(), []
    def perform(kind):
        try:
            barrier.wait(timeout=8)
            if kind == "move":
                response = e.client.post(e.prefix + f"/chapters/{e.a['id']}/move", json={"direction": "down"})
            else:
                response = e.client.put(e.prefix + f"/chapters/{e.a['id']}", json={"version": 1, "content": "A_CONCURRENT_SAVE"})
            result = (kind, response.status_code, response.text)
        except Exception as exc:
            result = (kind, "error", repr(exc))
        with lock:
            outcomes.append(result)
    workers = [Thread(target=perform, args=(kind,), daemon=True) for kind in ("move", "save")]
    for worker in workers:
        worker.start()
    barrier.wait(timeout=8)
    for worker in workers:
        worker.join(10)
    assert all(not worker.is_alive() for worker in workers), "A43 move/save did not terminate within 10 seconds"
    assert sorted((kind, status) for kind, status, _ in outcomes) == [("move", 200), ("save", 200)], outcomes
    assert e.chapters.get(e.a["id"])["content"].strip() == "A_CONCURRENT_SAVE"
    assert e.chapters.get(e.a["id"])["version"] == 2
    assert e.chapters.get(e.b["id"])["document"] == e.b["document"]
    assert [c["id"] for c in e.chapters.list(e.nid)] == [e.b["id"], e.a["id"]]
    assert e.chapters.history(e.a["id"])[0]["document"] == e.a["document"]
    assert e.chapters.history(e.b["id"]) == []


def test_context_snapshot_read_and_late_creation_are_bound_to_exact_source(identity_app):
    e = identity_app
    _assert_namespace(e)
    snapshots = ContextSnapshotService(e.bundle.lore)
    reader = CollaborationReadService(
        sessions=e.sessions, membership_authorization=e.membership, identity=e.identity,
        authorization=e.authorization, scopes=e.scopes, chapters=e.chapters,
        generations=GenerationService(e.bundle.generations), lore_repository=e.bundle.lore,
        novels=e.bundle.novels,
    )
    original = {}
    for chapter in (e.a, e.b):
        original[chapter["id"]] = snapshots.create(
            chapter["id"], 1, {"canon": [], "source_marker": chapter["content"]},
            "identity-test:v1", "none-no-provider-called",
        )
    _move(e)
    for chapter in (e.a, e.b):
        rows = reader.snapshots(chapter["id"])
        assert [row["id"] for row in rows] == [original[chapter["id"]]["id"]]
        assert rows[0]["chapter_version_id"] == chapter["id"] + ":v1"
        assert rows[0]["context"]["source_marker"] == chapter["content"]
    e.chapters.delete(e.a["id"])
    with pytest.raises(FileNotFoundError):
        reader.snapshots(e.a["id"])
    with pytest.raises(FileNotFoundError):
        snapshots.create(e.a["id"], 1, {"canon": []}, "late:v1", "none-no-provider-called")
    assert [row["id"] for row in reader.snapshots(e.b["id"])] == [original[e.b["id"]]["id"]]


def test_warm_search_manifest_reference_never_reads_another_object(identity_app):
    e = identity_app
    _assert_namespace(e)
    service = e.experimental.workspace_tools_service
    ctx = SimpleNamespace(novel_id=e.nid, scope=e.scope)
    sources = chapter_manifest(service, ctx, lambda: None)
    assert sources is not None
    cached = {source.key: source for source in sources}
    a_source, b_source = cached["chapter:" + e.a["id"]], cached["chapter:" + e.b["id"]]
    assert a_source.read()["document"] == e.a["document"]
    _move(e)
    assert a_source.read()["document"] == e.a["document"]
    assert b_source.read()["document"] == e.b["document"]
    e.chapters.delete(e.a["id"])
    e.chapters.delete(e.b["id"])
    new = e.chapters.create(e.nid, {"title": "Fresh search object", "content": "NEW_SEARCH_ONLY"})
    with pytest.raises(FileNotFoundError):
        a_source.read()
    with pytest.raises(FileNotFoundError):
        b_source.read()
    refreshed = chapter_manifest(service, ctx, lambda: None)
    assert [source.key for source in refreshed] == ["chapter:" + new["id"]]
    assert all("NEW_SEARCH_ONLY" in json.dumps(source.read()["document"]) for source in refreshed)


@pytest.mark.file_backend_only
def test_legacy_copy_ambiguous_history_is_quarantined_without_destroying_evidence(tmp_path):
    """Raw pre-ledger fixture, copied for migration; original bytes never change."""
    source = tmp_path / "legacy-source"
    root = source / "novels/legacy"
    for folder in ("chapters", "documents", "history/chapter-0001", "cache"):
        (root / folder).mkdir(parents=True, exist_ok=True)
    (root / "novel.json").write_text(json.dumps({"id": "legacy", "title": "Synthetic legacy"}), encoding="utf-8")
    (root / "chapters/chapter-0001.md").write_text("# Reused live object\n\nNEW_LEGACY_CONTENT", encoding="utf-8")
    (root / "documents/chapter-0001.json").write_text(json.dumps({"chapter_id": "legacy:1", "version": 1, "document": markdown_to_document("NEW_LEGACY_CONTENT")}), encoding="utf-8")
    (root / "history/chapter-0001/v000001.json").write_text(json.dumps({"version": 1, "document": markdown_to_document("OLD_OTHER_GENERATION")}), encoding="utf-8")
    (root / "cache/references.json").write_text(json.dumps({"chapter_id": "legacy:44", "summary": "ORPHAN_REFERENCE"}), encoding="utf-8")
    before = {p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()}
    copy_root = tmp_path / "isolated-migration-copy"
    shutil.copytree(source, copy_root)
    bundle = create_repository_bundle(Settings(storage_backend="file", novel_data=copy_root), copy_root)
    service, novels = ChapterService(bundle.chapters), NovelService(bundle.novels, bundle.chapters)
    for action in (
        lambda: service.get("legacy:1"),
        lambda: service.save("legacy:1", {"content": "MUST_NOT_OVERWRITE", "version": 1}),
        lambda: service.history("legacy:1"),
        lambda: service.restore("legacy:1", 1, 1),
        lambda: service.duplicate("legacy:1"),
        lambda: novels.export_snapshot("legacy", format="json"),
    ):
        with pytest.raises(FileNotFoundError):
            action()
    assert {p: (source / p).read_bytes() for p in before} == before
    assert {p: (copy_root / p).read_bytes() for p in before} == before
    restarted = create_repository_bundle(Settings(storage_backend="file", novel_data=copy_root), copy_root)
    with pytest.raises(FileNotFoundError):
        restarted.chapters.get("legacy:1")
    with pytest.raises(FileExistsError):
        restarted.chapters.create("legacy", {"number": 44, "title": "Retained cache slot"})
    fresh = restarted.chapters.create("legacy", {"title": "Safe qualified allocation", "content": "NEW_QUALIFIED"})
    _assert_qualified(fresh["id"], "legacy")
    assert fresh["number"] > 44
    assert "NEW_QUALIFIED" in restarted.chapters.get(fresh["id"])["content"]
    with pytest.raises(FileNotFoundError):
        restarted.chapters.get("legacy:" + str(fresh["number"]))
    assert {p: (copy_root / p).read_bytes() for p in before} == before


@pytest.mark.file_backend_only
@pytest.mark.parametrize("owner", ["empty_no_evidence", "context_snapshot", "experimental_record", "capability_record"])
def test_legacy_unknown_provenance_creates_distinct_namespace_across_copy_and_restart(tmp_path, owner):
    """Remaining metadata cannot prove a complete historical allocation log."""
    source = tmp_path / "legacy-source"
    root = source / "novels/legacy"
    (root / "chapters").mkdir(parents=True)
    (root / "novel.json").write_text(json.dumps({"id": "legacy", "title": "Detached legacy reference"}), encoding="utf-8")
    if owner == "empty_no_evidence":
        path, value = None, None
    elif owner == "context_snapshot":
        path = root / "lore/context_snapshots/detached.json"
        value = {"id": "detached", "chapter_version_id": "legacy:57:v2", "context": {"canon": []}}
    elif owner == "experimental_record":
        from app.experimental.store import ExperimentalStore
        store = ExperimentalStore(source)
        scope = {"mode": "local", "novel_id": "legacy"}
        with store.transaction("legacy", scope) as state:
            state["collections"]["world_records"] = {
                "retained": {"id": "retained", "novel_id": "legacy", "scope": scope,
                             "chapter_id": "legacy:57", "sources": {"legacy:57": {"version": 2, "digest": "retained"}}},
            }
        path, value = None, None
    else:
        path = source / "v1_capabilities/records.json"
        value = {"retained": {"id": "retained", "novel_id": "legacy", "chapter_id": "legacy:57", "version": 2}}
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
    before = {p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()}
    copied = tmp_path / "isolated-migration-copy"
    shutil.copytree(source, copied)
    bundle = create_repository_bundle(Settings(storage_backend="file", novel_data=copied), copied)
    fresh = bundle.chapters.create("legacy", {"title": "Safe new namespace", "content": "NEW_OBJECT"})
    _assert_qualified(fresh["id"], "legacy")
    if owner != "empty_no_evidence":
        assert fresh["number"] > 57
        with pytest.raises(FileExistsError):
            bundle.chapters.create("legacy", {"number": 57, "title": "Retained source slot"})
    numeric_alias = "legacy:" + str(fresh["number"])
    with pytest.raises(FileNotFoundError):
        bundle.chapters.save(numeric_alias, markdown_to_document("OLD_CLIENT_VERSION_1"), 1)
    before_delete = bundle.chapters.get(fresh["id"])
    assert "NEW_OBJECT" in before_delete["content"]
    bundle.chapters.delete(fresh["id"])
    restarted = create_repository_bundle(Settings(storage_backend="file", novel_data=copied), copied)
    another = restarted.chapters.create("legacy", {"title": "After restart", "content": "AFTER_RESTART"})
    _assert_qualified(another["id"], "legacy")
    assert another["id"] != fresh["id"] and another["number"] > fresh["number"]
    with pytest.raises(FileNotFoundError):
        restarted.chapters.get(fresh["id"])
    with pytest.raises(FileNotFoundError):
        restarted.chapters.get("legacy:" + str(another["number"]))
    assert "AFTER_RESTART" in restarted.chapters.get(another["id"])["content"]
    assert {p: (source / p).read_bytes() for p in before} == before
    assert {p: (copied / p).read_bytes() for p in before} == before


@pytest.mark.file_backend_only
@pytest.mark.parametrize("feature_mode", ["off", "on", "v1"])
def test_legacy_allocation_http_uses_new_namespace_and_rejects_numeric_alias(tmp_path, monkeypatch, prefix, feature_mode):
    import app.api as api
    from app.main import app
    from fastapi.testclient import TestClient
    root = tmp_path / "novels/legacy"
    (root / "chapters").mkdir(parents=True)
    (root / "novel.json").write_text(json.dumps({"id": "legacy", "title": "Unverifiable empty legacy"}), encoding="utf-8")
    config = Settings(storage_backend="file", novel_data=tmp_path, enable_collaboration_runtime=False, enable_packaged_runtime=False)
    bundle = create_repository_bundle(config, tmp_path)
    monkeypatch.setattr(api, "settings", config)
    monkeypatch.setattr(api, "chapter_service", ChapterService(bundle.chapters))
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "" if feature_mode == "off" else ",".join(FLAGS))
    monkeypatch.setenv("V1_ACCEPTANCE_MODE", "true" if feature_mode == "v1" else "false")
    client = TestClient(app)
    try:
        created = checked(client.post(prefix + "/novels/legacy/chapters", json={"title": "New", "content": "LEGACY_SAFE_NEW"}), 201)
        _assert_qualified(created["id"], "legacy")
        numeric_alias = "legacy:" + str(created["number"])
        assert client.get(prefix + "/chapters/" + numeric_alias).status_code == 404
        assert client.put(prefix + "/chapters/" + numeric_alias, json={"version": 1, "content": "OLD_CLIENT"}).status_code == 404
        current = checked(client.get(prefix + "/chapters/" + created["id"]))
        assert "LEGACY_SAFE_NEW" in current["content"] and current["version"] == 1
        assert client.post(prefix + "/novels/legacy/chapters", json={"number": created["number"], "title": "Collision"}).status_code == 409
    finally:
        client.close()
    assert len(list((root / "chapters").glob("*.md"))) == 1

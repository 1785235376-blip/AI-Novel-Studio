"""Independent merge counterexamples: real File owners, synthetic inputs only.

The checks combine protections introduced on separate parents. Fixtures create
real original-owner records; hooks only inject failures, never authorize reads.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

import pytest

from app.creative.asset_usage_budget import (
    UsageBudgetError, current_usage_budget, usage_read_budget,
)
from app.creative.project_store import CreativeProjectStore
from app.experimental.store import ExperimentalStore
from app.repositories.file import mutation_coordinator as coordination
from app.repositories.file.identity import FileIdentityRepository
from app.repositories.file.scope import FileAuthorizationRepository, FileScopeRepository
from studio_asset_usage_fixture import usage_rig, audio_history, rig, graph_create

pytestmark = pytest.mark.file_backend_only
NID = "independent-merge-book"


def disk_snapshot(root):
    return {str(p.relative_to(root)): ("directory" if p.is_dir() else
            (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns))
            for p in root.rglob("*")}


def seed_scope(root, mode="local"):
    store = ExperimentalStore(root)
    (root / "novels" / NID).mkdir(parents=True, exist_ok=True)
    CreativeProjectStore(store).incarnation(NID)
    scope = {"mode": mode, "novel_id": NID}
    collection = "semantic_import_jobs"
    if mode == "collaboration":
        scope.update(workspace_id="w", storyline_id="s", branch_id="b")
        collection = "team_runs"
    with store.transaction(NID, scope) as doc:
        doc["collections"][collection] = {
            "job": {"id": "job", "novel_id": NID, "scope": deepcopy(scope),
                    "status": "QUEUED", "version": 1}}
    return store, scope, collection


def write_status(store, scope, collection, status):
    with store.transaction(NID, scope) as doc:
        doc["collections"][collection]["job"]["status"] = status


@pytest.mark.parametrize("mode", ["local", "collaboration"])
def test_guarded_committed_capture_does_not_borrow_rollback_buffer(tmp_path, mode):
    store, scope, collection = seed_scope(tmp_path, mode)
    original = store.capture_committed_collection(NID, scope, collection)
    before = disk_snapshot(tmp_path)
    with pytest.raises(RuntimeError, match="rollback independent"):
        with store.transaction(NID, scope) as active:
            active["collections"][collection]["job"]["status"] = "UNCOMMITTED"
            with coordination.existing_coordination_only(), usage_read_budget() as budget:
                first = store.capture_committed_collection(NID, scope, collection)
                second = ExperimentalStore(tmp_path).capture_committed_collection(NID, scope, collection)
                assert first == second == original
                assert budget.reads >= 2 and budget.read_bytes >= 2 * store.path(NID, scope).stat().st_size
            raise RuntimeError("rollback independent")
    assert disk_snapshot(tmp_path) == before
    assert current_usage_budget() is None and not coordination.strict_coordination_active()
    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(write_status, ExperimentalStore(tmp_path), scope, collection, "AFTER").result(timeout=10)
    after = store.capture_committed_collection(NID, scope, collection)
    assert after["rows"][0]["status"] == "AFTER"
    assert after["row_lifecycles"] != original["row_lifecycles"]


@pytest.mark.parametrize("outer_changes", [False, True])
def test_guarded_reentrant_other_instance_commit_is_not_overwritten(tmp_path, outer_changes):
    store, scope, collection = seed_scope(tmp_path)
    with coordination.existing_coordination_only(), usage_read_budget() as budget:
        with pytest.raises(ValueError, match="EXPERIMENTAL_SCOPE_CONCURRENT_WRITE"):
            with store.transaction(NID, scope) as doc:
                if outer_changes:
                    doc["collections"][collection]["job"]["status"] = "OUTER"
                write_status(ExperimentalStore(tmp_path), scope, collection, "INNER")
        assert budget.reads > 0
    assert store.capture_committed_collection(NID, scope, collection)["rows"][0]["status"] == "INNER"
    write_status(store, scope, collection, "RECOVERED")
    assert store.capture_committed_collection(NID, scope, collection)["rows"][0]["status"] == "RECOVERED"


def test_guarded_read_compares_physical_bytes_not_decoded_equivalence(tmp_path):
    from app.storage import atomic_write
    store, scope, collection = seed_scope(tmp_path)
    path = store.path(NID, scope)
    original = store.capture_committed_collection(NID, scope, collection)
    with usage_read_budget():
        with pytest.raises(ValueError, match="EXPERIMENTAL_SCOPE_CONCURRENT_WRITE"):
            with store.transaction(NID, scope):
                atomic_write(path, json.dumps(json.loads(path.read_text(encoding="utf-8")), indent=4))
    assert store.capture_committed_collection(NID, scope, collection) == original
    write_status(store, scope, collection, "AFTER")


@pytest.mark.parametrize("failure", ["strict-missing", "budget"])
def test_exception_context_resets_and_other_thread_can_use_original_writer(tmp_path, failure):
    store, scope, collection = seed_scope(tmp_path)
    before = disk_snapshot(tmp_path)
    locks_before = dict(coordination._locks)
    with pytest.raises((coordination.ReadOnlyCoordinationUnavailable, UsageBudgetError)):
        with coordination.existing_coordination_only(), usage_read_budget() as budget:
            if failure == "strict-missing":
                with coordination.workspace_mutation(tmp_path, "never-provisioned"):
                    pytest.fail("strict read created coordination")
            else:
                budget.MAX_READ_BYTES = 1
                store.capture_committed_collection(NID, scope, collection)
    assert disk_snapshot(tmp_path) == before and coordination._locks == locks_before
    assert current_usage_budget() is None and not coordination.strict_coordination_active()
    with usage_read_budget() as outer, coordination.existing_coordination_only():
        def ordinary_thread():
            assert current_usage_budget() is None and not coordination.strict_coordination_active()
            with coordination.workspace_mutation(tmp_path, "thread-new-lock"):
                write_status(ExperimentalStore(tmp_path), scope, collection, "THREAD")
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(ordinary_thread).result(timeout=10)
        assert current_usage_budget() is outer and coordination.strict_coordination_active()
    write_status(store, scope, collection, "MAIN")
    assert store.capture_committed_collection(NID, scope, collection)["rows"][0]["status"] == "MAIN"


def metadata_owner(root, kind):
    if kind == "experimental":
        repo, scope, _ = seed_scope(root)
        return repo.path(NID, scope), "_taskcenter_lifecycle_v1", lambda: repo.read(NID, scope)
    if kind == "identity":
        repo = FileIdentityRepository(root)
        repo.save_user({"id": "u", "status": "ACTIVE"})
        return repo.path, "_identity_lifecycle_v1", repo._read
    if kind == "scope":
        repo = FileScopeRepository(root)
        repo.create("workspaces", {"id": "w"})
        return repo.path, "_scope_lifecycle_v1", repo._read
    repo = FileAuthorizationRepository(root)
    repo.save_permission_assignment({"id": "grant", "principal_id": "u", "permission": "domain.read",
        "domain": "NOVEL", "scope": {"kind": "WORKSPACE", "workspace_id": "w"}})
    return repo.path, "_grant_lifecycle_v1", repo._read


@pytest.mark.parametrize("kind", ["experimental", "identity", "scope", "grant"])
def test_budget_admission_does_not_weaken_duplicate_metadata_rejection(tmp_path, kind):
    path, key, read = metadata_owner(tmp_path, kind)
    document = json.loads(path.read_text(encoding="utf-8"))
    # Equal repeated values are still ambiguous JSON; semantic equality must
    # not allow the second parent's strict lifecycle parser to be bypassed.
    raw = "{" + json.dumps(key) + ":" + json.dumps(document[key]) + "," + json.dumps(document)[1:]
    path.write_text(raw, encoding="utf-8")
    before = disk_snapshot(tmp_path)
    with coordination.existing_coordination_only(), usage_read_budget() as budget:
        with pytest.raises(ValueError):
            read()
        assert budget.reads >= 1
    assert disk_snapshot(tmp_path) == before


def test_current_actor_observation_survives_unrelated_user_writes_under_budget(tmp_path):
    identity = FileIdentityRepository(tmp_path)
    identity.save_user({"id": "selected", "status": "ACTIVE"})
    identity.save_membership({"id": "selected-membership", "user_id": "selected", "workspace_id": "w", "status": "ACTIVE"})
    with usage_read_budget(), coordination.existing_coordination_only():
        selected = identity.binding_observation("selected", "w")
    identity.save_user({"id": "unrelated", "status": "ACTIVE"})
    identity.save_membership({"id": "other-membership", "user_id": "unrelated", "workspace_id": "w", "status": "ACTIVE"})
    with usage_read_budget() as budget, coordination.existing_coordination_only():
        assert identity.revalidate_binding("selected", "w", selected)
        assert budget.reads >= 1


@pytest.mark.parametrize("mode", ["local", "collaboration"])
def test_selected_source_proofs_ignore_unselected_collection_with_guarded_reads(tmp_path, mode):
    store, scope, collection = seed_scope(tmp_path, mode)
    with usage_read_budget(), coordination.existing_coordination_only():
        selected = store.capture_committed_collection(NID, scope, collection)
    with store.transaction(NID, scope) as doc:
        doc["collections"]["independent-unselected"] = {"other": {"id": "other", "version": 1}}
    with usage_read_budget() as budget, coordination.existing_coordination_only():
        assert store.capture_committed_collection(NID, scope, collection) == selected
        assert budget.reads >= 1


@pytest.fixture
def export_owner(tmp_path, monkeypatch):
    from app.services.export_job_service import ExportJobService
    monkeypatch.setattr(ExportJobService, "_submit", lambda *args: pytest.fail("synthetic export must not execute"))
    owner = ExportJobService(tmp_path, lambda *args: pytest.fail("synthetic export must not execute"))
    owner._write({f"job-{i:03}": {"id": f"job-{i:03}", "novel_id": NID,
        "format": "txt", "status": "queued", "created_at": f"{i:05}",
        "permission_context": {"mode": "local", "novel_id": NID},
        "snapshot": {"synthetic": i}} for i in range(101)})
    yield owner
    owner._pool.shutdown(wait=True)


def test_export_guarded_selected_window_ignores_foreign_actor_and_hidden_tail(export_owner):
    owner = export_owner
    with usage_read_budget(), coordination.existing_coordination_only():
        initial = owner.local_task_observation(NID)
    assert len(initial["rows"]) == 100 and initial["source_more"]
    content = owner._read()
    content["job-000"]["snapshot"]["synthetic"] = "hidden tail update"
    content["foreign"] = {**deepcopy(content["job-100"]), "id": "foreign",
                          "permission_context": {"mode": "local", "novel_id": NID, "actor_id": "other"}}
    owner._write(content)
    with usage_read_budget() as budget, coordination.existing_coordination_only():
        assert owner.local_task_observation(NID) == initial
        assert budget.reads > 0


def test_export_guarded_failure_is_not_empty_success_and_original_writer_recovers(export_owner):
    owner = export_owner
    before = disk_snapshot(owner.path.parent)
    with pytest.raises(UsageBudgetError):
        with usage_read_budget() as budget, coordination.existing_coordination_only():
            budget.MAX_READ_BYTES = 1
            owner.local_task_observation(NID)
    assert disk_snapshot(owner.path.parent) == before
    assert current_usage_budget() is None and not coordination.strict_coordination_active()
    content = owner._read()
    content["job-100"]["snapshot"]["synthetic"] = "next committed version"
    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(owner._write, content).result(timeout=10)
    with usage_read_budget(), coordination.existing_coordination_only():
        assert owner.local_task_observation(NID)["rows"]


def test_export_equal_duplicate_metadata_is_rejected_under_budget(export_owner):
    owner = export_owner
    doc = json.loads(owner.path.read_text(encoding="utf-8"))
    key = "_export_lifecycle_v1"
    owner.path.write_text("{" + json.dumps(key) + ":" + json.dumps(doc[key]) + "," + json.dumps(doc)[1:], encoding="utf-8")
    before = disk_snapshot(owner.path.parent)
    with usage_read_budget() as budget, coordination.existing_coordination_only():
        with pytest.raises(ValueError):
            owner.local_task_observation(NID)
        assert budget.reads > 0
    assert disk_snapshot(owner.path.parent) == before


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_strict_http_missing_original_lock_never_initializes_then_writer_recovers(usage_rig, prefix):
    e = usage_rig
    graph_create(e, 2)
    root = e.rig.root
    key = "experimental:" + ExperimentalStore.key(e.rig.nid, e.rig.scope)
    lock = root / ".workspace-mutation-locks" / (hashlib.sha256(key.encode()).hexdigest() + ".lock")
    assert lock.exists()
    lock.unlink()  # Only a fixture lock is removed, before the observed request.
    before = disk_snapshot(root)
    locks_before = dict(coordination._locks)
    url = e.usage_base.replace("/api/", prefix + "/", 1) + "/studio-graph-usages"
    refused = e.client.get(url, headers=e.headers, params={"limit": 1, "strict_read_only": "true"})
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "STUDIO_USAGE_STRICT_READ_ONLY_UNAVAILABLE"
    assert "items" not in refused.json() and "next_cursor" not in refused.json()
    assert disk_snapshot(root) == before and coordination._locks == locks_before
    with ExperimentalStore(root).transaction(e.rig.nid, e.rig.scope) as doc:
        doc["collections"]["independent-recovery"] = {"ok": {"id": "ok"}}
    recovered = e.client.get(url, headers=e.headers, params={"limit": 1, "strict_read_only": "true"})
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()["next_cursor"]


@pytest.mark.skipif(os.name != "nt", reason="actual Windows native sharing refusal")
@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
@pytest.mark.parametrize("strict", [False, True])
def test_actual_native_reader_refusal_never_issues_cursor_and_releases_context(usage_rig, monkeypatch, prefix, strict):
    from app.creative import asset_usage_paging
    e = usage_rig
    graph_create(e, 3)
    monkeypatch.setattr(asset_usage_paging, "_tokens", {})
    url = e.usage_base.replace("/api/", prefix + "/", 1) + "/studio-graph-usages"
    params = {"limit": 1, **({"strict_read_only": "true"} if strict else {})}
    path = ExperimentalStore(e.rig.root).path(e.rig.nid, e.rig.scope)
    before = disk_snapshot(e.rig.root)
    with path.open("r+b"):
        rejected = e.client.get(url, headers=e.headers, params=params)
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["code"] == "STUDIO_USAGE_RESOURCE_UNAVAILABLE"
    assert "items" not in rejected.json() and "next_cursor" not in rejected.json()
    assert rejected.headers["cache-control"] == "no-store"
    assert asset_usage_paging._tokens == {} and disk_snapshot(e.rig.root) == before
    assert current_usage_budget() is None and not coordination.strict_coordination_active()
    with ExperimentalStore(e.rig.root).transaction(e.rig.nid, e.rig.scope) as doc:
        doc["collections"]["native-recovery"] = {"ok": {"id": "ok"}}
    recovered = e.client.get(url, headers=e.headers, params=params)
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()["next_cursor"] and asset_usage_paging._tokens

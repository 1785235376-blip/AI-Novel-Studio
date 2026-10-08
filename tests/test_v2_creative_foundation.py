"""Real File persistence and opt-in Creative Layer authority/source contracts.

Run through scripts/run_v2_checks.py so isolation is established before app
imports (including the repository's global autouse fixture).
"""
import copy
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4

import pytest
from test_r3_mounted_contracts import mounted, prefix, scoped

TEST_URL = os.getenv("TEST_POSTGRES_DATABASE_URL", "")

@pytest.fixture(params=[pytest.param("file", marks=pytest.mark.file_backend_only),
                       pytest.param("postgres", marks=[pytest.mark.postgres_backend_only,
                           pytest.mark.skipif(not TEST_URL, reason="NOT_RUN: owned V2 PostgreSQL endpoint not configured")])])
def rig(request, tmp_path):
    from app.config import Settings
    from app.creative.service import CreativeService
    from app.experimental.store import ExperimentalStore
    from app.repositories.factory import create_repository_bundle
    from app.services import NovelService, ChapterService
    root = Path(__file__).resolve().parents[1]
    assert Path(os.environ["PROJECT_ROOT"]).resolve() == root
    for key in ("LOCALAPPDATA", "NOVEL_DATA_PATH"):
        assert Path(os.environ[key]).resolve().is_relative_to(root / ".runtime")
    assert tmp_path.resolve().is_relative_to(root / ".runtime")
    backend = request.param
    url = TEST_URL if backend == "postgres" else ""
    bundle = create_repository_bundle(Settings(storage_backend=backend, database_url=url, novel_data=tmp_path), data_root=tmp_path)
    novels, chapters = NovelService(bundle.novels, bundle.chapters), ChapterService(bundle.chapters)
    nid = novels.create({"id": "v2-foundation-" + uuid4().hex, "title": "Synthetic source"})["id"]
    chapter = chapters.create(nid, {"title": "One", "content": "A visitor remembers the ruined city."})
    store = ExperimentalStore(tmp_path, backend, url)
    yield SimpleNamespace(nid=nid, scope={"mode": "local", "novel_id": nid}, actor="local-author",
                           novels=novels, chapters=chapters, chapter=chapters.get(chapter["id"]),
                           store=store, service=CreativeService(store, novels, chapters), root=tmp_path,
                           backend=backend, url=url)
    if backend == "postgres":
        try:
            with store._connect() as connection:
                connection.execute("DELETE FROM experimental_scope_documents WHERE novel_id = %s", (nid,))
            novels.delete(nid)
        finally:
            bundle.novels.database.engine.dispose()


def payload(rig, mode="SCREENPLAY"):
    value = {"mode": mode, "title": "City", "source_chapter_ids": [rig.chapter["id"]],
             "scenes": [{"id": "scene-1", "sequence": 1, "source_chapter_id": rig.chapter["id"],
                         "heading": "EXT. RUINS - NIGHT", "action": "The visitor pauses.",
                         "dialogue": [{"speaker": "Visitor", "text": "I know this place."}]}]}
    if mode != "SCREENPLAY":
        value["shots"] = [{"id": "shot-1", "number": 1, "scene_id": "scene-1", "duration_seconds": 5,
                           "sound_effect": "Wind through an empty street."}]
    if mode == "VIDEO_PLANNING":
        value["video_plan"] = {"segments": [{"shot_id": "shot-1", "duration_seconds": 5}]}
    return value


def public(row):
    from app.creative.models import CreativeDocumentIn
    return {key: copy.deepcopy(row[key]) for key in CreativeDocumentIn.model_fields}


def derived(rig, source, mode="STORYBOARD"):
    from app.creative.service import document_digest
    value = payload(rig, mode)
    return rig.service.create_derived(rig.nid, rig.scope, rig.actor, value,
        source_documents={source["id"]: {"version": source["version"], "digest": document_digest(source)}})


@pytest.mark.parametrize("mode", ["SCREENPLAY", "STORYBOARD", "VIDEO_PLANNING"])
def test_real_file_roundtrip_restart_history_export_and_archive(rig, mode):
    from app.creative.service import CreativeService
    from app.experimental.store import ExperimentalStore
    service = rig.service
    row = service.create(rig.nid, rig.scope, rig.actor, payload(rig, mode))
    on_disk = (json.loads(rig.store.path(rig.nid, rig.scope).read_text(encoding="utf-8"))
               if rig.backend == "file" else rig.store.read(rig.nid, rig.scope))
    assert on_disk["collections"][service.COLLECTION][row["id"]] == row
    reopened = CreativeService(ExperimentalStore(rig.root, rig.backend, rig.url), rig.novels, rig.chapters)
    assert reopened.get(rig.nid, rig.scope, row["id"]) == row
    changed = public(row); changed["title"] = "Revised title"
    latest = reopened.update(rig.nid, rig.scope, "editor", row["id"], 1, changed)
    assert latest["version"] == 2 and latest["created_by"] == rig.actor and latest["updated_by"] == "editor"
    history = reopened.history(rig.nid, rig.scope, row["id"])
    assert [item["version"] for item in history["items"]] == [1, 2]
    assert history["items"][0]["title"] == "City"
    assert reopened.export(rig.nid, rig.scope, row["id"])["document"]["title"] == "Revised title"
    assert reopened.list(rig.nid, rig.scope) == [latest]
    assert reopened.archive(rig.nid, rig.scope, "editor", row["id"], 2)["version"] == 3
    assert reopened.list(rig.nid, rig.scope) == []
    with pytest.raises(FileNotFoundError): reopened.get(rig.nid, rig.scope, row["id"])


def test_process_restart_reads_actual_store(rig):
    row = rig.service.create(rig.nid, rig.scope, rig.actor, payload(rig))
    script = """import json,sys
from app.experimental.store import ExperimentalStore
import os
s=ExperimentalStore(sys.argv[1],sys.argv[5],os.getenv('V2_FOUNDATION_DATABASE_URL','')); d=s.read(sys.argv[2],json.loads(sys.argv[3]))
print(json.dumps(d['collections']['creative_documents_v2'][sys.argv[4]],ensure_ascii=False))
"""
    child_env = {**os.environ, "V2_FOUNDATION_DATABASE_URL": rig.url}
    result = subprocess.run([sys.executable, "-B", "-X", "utf8", "-c", script, str(rig.root), rig.nid,
                             json.dumps(rig.scope), row["id"], rig.backend], cwd=Path(__file__).resolve().parents[1], env=child_env,
                            capture_output=True, text=True, encoding="utf-8", check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == row


def test_two_service_cas_rejects_lost_update_and_preserves_history(rig):
    from app.creative.service import CreativeService
    from app.experimental.store import ExperimentalStore
    from app.services.v1_capability_service import CapabilityVersionConflict
    row = rig.service.create(rig.nid, rig.scope, rig.actor, payload(rig))
    second = CreativeService(ExperimentalStore(rig.root, rig.backend, rig.url), rig.novels, rig.chapters)
    value = public(row); value["title"] = "First writer"
    first = rig.service.update(rig.nid, rig.scope, rig.actor, row["id"], 1, value)
    with pytest.raises(CapabilityVersionConflict): second.update(rig.nid, rig.scope, "other", row["id"], 1, payload(rig))
    assert second.get(rig.nid, rig.scope, row["id"]) == first
    assert len(first["history"]) == 1


def test_simultaneous_independent_file_writers_commit_exactly_one_revision(rig):
    from app.creative.service import CreativeService
    from app.experimental.store import ExperimentalStore
    from app.services.v1_capability_service import CapabilityVersionConflict
    row = rig.service.create(rig.nid, rig.scope, rig.actor, payload(rig))
    barrier = Barrier(2)
    def write(actor):
        service = CreativeService(ExperimentalStore(rig.root, rig.backend, rig.url), rig.novels, rig.chapters)
        value = public(row); value["title"] = actor
        barrier.wait(timeout=10)
        try:
            return service.update(rig.nid, rig.scope, actor, row["id"], 1, value)
        except CapabilityVersionConflict:
            return "CONFLICT"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, ("writer-a", "writer-b")))
    assert sum(result == "CONFLICT" for result in results) == 1
    winner = next(result for result in results if result != "CONFLICT")
    assert rig.service.get(rig.nid, rig.scope, row["id"]) == winner
    assert winner["version"] == 2 and len(winner["history"]) == 1


def test_chapter_change_fences_read_write_export_and_history(rig):
    from app.experimental.common import StaleSourceError
    row = rig.service.create(rig.nid, rig.scope, rig.actor, payload(rig))
    rig.chapters.save(rig.chapter["id"], {"content": "The source changed.", "version": rig.chapter["version"]})
    for operation in (lambda: rig.service.get(rig.nid, rig.scope, row["id"]),
                      lambda: rig.service.export(rig.nid, rig.scope, row["id"]),
                      lambda: rig.service.history(rig.nid, rig.scope, row["id"]),
                      lambda: rig.service.update(rig.nid, rig.scope, rig.actor, row["id"], 1, public(row))):
        with pytest.raises(StaleSourceError): operation()
    assert rig.service.list(rig.nid, rig.scope) == []


def test_privacy_review_change_revokes_previously_captured_source(rig):
    from app.experimental.common import StaleSourceError
    from app.source_privacy import content_digest, review_source_privacy
    row = rig.service.create(rig.nid, rig.scope, rig.actor, payload(rig))
    review_source_privacy(rig.chapter, None, "reviewer", "CLOUD_ALLOWED", rig.chapter["version"],
                          content_digest(rig.chapter), root=rig.root)
    with pytest.raises(StaleSourceError, match="PRIVACY"): rig.service.get(rig.nid, rig.scope, row["id"])


def test_cross_project_and_branch_are_fenced_without_mainline_fallback(rig):
    other = rig.novels.create({"id": "other-" + uuid4().hex, "title": "Other"})["id"]
    with pytest.raises(ValueError, match="another project"):
        rig.service.create(other, {"mode": "local", "novel_id": other}, rig.actor, payload(rig))
    branch = {"mode": "collaboration", "novel_id": rig.nid, "workspace_id": "w", "storyline_id": "s", "branch_id": "b"}
    with pytest.raises(FileNotFoundError): rig.service.create(rig.nid, branch, rig.actor, payload(rig))
    row = rig.service.create(rig.nid, rig.scope, rig.actor, payload(rig))
    with pytest.raises(FileNotFoundError): rig.service.get(rig.nid, branch, row["id"])
    assert rig.service.list(rig.nid, branch) == []


def test_independent_document_requires_explicit_opt_in_and_sources_cannot_be_forged(rig):
    value = {"mode": "SCREENPLAY", "title": "Independent"}
    with pytest.raises(ValueError, match="SOURCE_REQUIRED"): rig.service.create(rig.nid, rig.scope, rig.actor, value)
    value["source_independent"] = True
    assert rig.service.create(rig.nid, rig.scope, rig.actor, value)["source_evidence"] == {}
    conflicting = payload(rig); conflicting["source_independent"] = True
    with pytest.raises(ValueError, match="INDEPENDENT_SOURCE_CONFLICT"): rig.service.create(rig.nid, rig.scope, rig.actor, conflicting)


@pytest.mark.parametrize("mutation", [
    lambda p: p.update(source_documents={"forged": {"version": 1, "digest": "0" * 64}}),
    lambda p: p.update(version=7),
    lambda p: p.update(title="   "),
    lambda p: p["scenes"][0].update(sequence=True),
    lambda p: p["scenes"].append(copy.deepcopy(p["scenes"][0])),
    lambda p: p["scenes"][0].update(source_chapter_id="not-bound"),
    lambda p: p.update(shots=[{"number": 1, "scene_id": "missing", "duration_seconds": 0}]),
])
def test_strict_schema_rejects_untrusted_fields_and_invalid_structure(rig, mutation):
    value = payload(rig); mutation(value)
    with pytest.raises(ValueError): rig.service.create(rig.nid, rig.scope, rig.actor, value)
    assert rig.service.list(rig.nid, rig.scope) == []


def test_derived_sources_are_atomic_recursive_and_preserved_on_update(rig):
    from app.experimental.common import StaleSourceError
    source = rig.service.create(rig.nid, rig.scope, rig.actor, payload(rig))
    storyboard = derived(rig, source)
    plan = derived(rig, storyboard, "VIDEO_PLANNING")
    updated = rig.service.update(rig.nid, rig.scope, rig.actor, plan["id"], 1, public(plan))
    assert updated["source_documents"] == plan["source_documents"]
    rig.service.update(rig.nid, rig.scope, rig.actor, source["id"], 1, public(source))
    for row in (storyboard, updated):
        with pytest.raises(StaleSourceError): rig.service.get(rig.nid, rig.scope, row["id"])


def test_derived_archive_digest_and_scope_changes_fail_closed(rig):
    from app.creative.service import document_digest
    from app.experimental.common import StaleSourceError
    source = rig.service.create(rig.nid, rig.scope, rig.actor, payload(rig))
    refs = {source["id"]: {"version": 1, "digest": "0" * 64}}
    before = rig.store.read(rig.nid, rig.scope)
    with pytest.raises(StaleSourceError): rig.service.create_derived(rig.nid, rig.scope, rig.actor, payload(rig, "STORYBOARD"), source_documents=refs)
    assert rig.store.read(rig.nid, rig.scope) == before
    refs[source["id"]]["digest"] = document_digest(source)
    branch = {"mode": "collaboration", "novel_id": rig.nid, "workspace_id": "w", "storyline_id": "s", "branch_id": "b"}
    with pytest.raises(FileNotFoundError): rig.service.create_derived(rig.nid, branch, rig.actor, {"mode": "STORYBOARD", "title": "Branch"}, source_documents=refs)
    child = derived(rig, source)
    rig.service.archive(rig.nid, rig.scope, rig.actor, source["id"], 1)
    with pytest.raises(StaleSourceError): rig.service.get(rig.nid, rig.scope, child["id"])


def test_cycle_and_corrupt_persisted_evidence_are_rejected(rig):
    from app.creative.service import document_digest
    from app.experimental.common import StaleSourceError
    row = rig.service.create(rig.nid, rig.scope, rig.actor, payload(rig))
    # A forged on-disk self-reference cannot authorize a cyclic source graph.
    row["source_documents"] = {row["id"]: {"version": 1, "digest": document_digest(row)}}
    with rig.store.transaction(rig.nid, rig.scope) as state:
        state["collections"][rig.service.COLLECTION][row["id"]] = copy.deepcopy(row)
    with pytest.raises(StaleSourceError): rig.service.get(rig.nid, rig.scope, row["id"])
    with rig.store.transaction(rig.nid, rig.scope) as state:
        state["collections"][rig.service.COLLECTION][row["id"]]["source_documents"] = {"bad": {"version": True, "digest": "0" * 64}}
    with pytest.raises(StaleSourceError): rig.service.get(rig.nid, rig.scope, row["id"])


def test_authority_revocation_rolls_back_the_entire_scope_transaction(rig):
    calls = []
    def revoked():
        calls.append(1)
        if len(calls) == 2: raise PermissionError("revoked")
    with pytest.raises(PermissionError): rig.service.create(rig.nid, rig.scope, rig.actor, payload(rig), reauthorize=revoked)
    assert rig.service.list(rig.nid, rig.scope) == []
    source = rig.service.create(rig.nid, rig.scope, rig.actor, payload(rig))
    before = rig.store.read(rig.nid, rig.scope); calls.clear()
    with pytest.raises(PermissionError): rig.service.update(rig.nid, rig.scope, rig.actor, source["id"], 1, public(source), reauthorize=revoked)
    assert rig.store.read(rig.nid, rig.scope) == before


def test_document_capacity_rejection_keeps_the_existing_snapshot(rig, monkeypatch):
    import app.creative.service as module
    monkeypatch.setattr(module, "MAX_DOCUMENTS", 1)
    rig.service.create(rig.nid, rig.scope, rig.actor, payload(rig))
    before = rig.store.read(rig.nid, rig.scope)
    with pytest.raises(ValueError, match="DOCUMENT_CAPACITY"):
        rig.service.create(rig.nid, rig.scope, rig.actor, payload(rig))
    assert rig.store.read(rig.nid, rig.scope) == before


def test_api_error_rechecks_authority_before_returning_private_projection(rig, monkeypatch):
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient
    from app.creative.api import create_creative_router
    from app.experimental.flags import require_flag
    from app.services.v1_capability_service import CapabilityVersionConflict
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2")
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)
    state = {"allowed": True}
    def authorize(nid, token, branch, permission):
        if not state["allowed"]: raise HTTPException(403, {"code": "PERMISSION_DENIED"})
        return rig.actor, rig.scope
    def error_after_revoke(*args):
        state["allowed"] = False
        raise CapabilityVersionConflict({"version": 4, "status": "DRAFT", "title": "PRIVATE_SENTINEL"})
    monkeypatch.setattr(rig.service, "get", error_after_revoke)
    app = FastAPI(); app.include_router(create_creative_router(rig.service, authorize, require_flag), prefix="/api")
    response = TestClient(app).get(f"/api/novels/{rig.nid}/experimental/creative/documents/record")
    assert response.status_code == 403
    assert "PRIVATE_SENTINEL" not in response.text and "current" not in response.text
    assert response.headers["cache-control"] == "no-store"


@pytest.fixture
def client(rig, monkeypatch):
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient
    from app.creative.api import create_creative_router
    from app.experimental.flags import require_flag
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2")
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)
    def authorize(nid, token, branch, permission):
        if token not in {"owner", "reader"}: raise HTTPException(401, {"code": "AUTH_REQUIRED"})
        if token == "reader" and permission == "domain.write": raise HTTPException(403, {"code": "PERMISSION_DENIED"})
        if nid != rig.nid: raise HTTPException(404, {"code": "NOT_FOUND"})
        scope = rig.scope if not branch else {"mode": "collaboration", "novel_id": nid, "workspace_id": "w", "storyline_id": "s", "branch_id": branch}
        return "actor", scope
    app = FastAPI(); app.include_router(create_creative_router(rig.service, authorize, require_flag), prefix="/api")
    return TestClient(app)


@pytest.mark.parametrize("configured,v1", [("", False), ("*", False), ("narrative_production_v2", True)])
def test_api_flag_off_wildcard_and_v1_acceptance_fail_closed(rig, client, monkeypatch, configured, v1):
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", configured)
    monkeypatch.setenv("V1_ACCEPTANCE_MODE", "true" if v1 else "false")
    base = f"/api/novels/{rig.nid}/experimental/creative"
    assert client.get(base + "/capabilities", headers={"X-Session-Token": "owner"}).json() == {"enabled": False, "can_mutate": False, "modes": ["SCREENPLAY", "STORYBOARD", "VIDEO_PLANNING"]}
    blocked = client.post(base + "/documents", json=payload(rig), headers={"X-Session-Token": "owner"})
    assert blocked.status_code == 404 and blocked.json()["detail"]["code"] == "EXPERIMENTAL_FEATURE_DISABLED"


def test_api_authority_crud_private_cas_export_and_branch_scope(rig, client):
    base = f"/api/novels/{rig.nid}/experimental/creative"; headers = {"X-Session-Token": "owner"}
    assert client.get(base + "/capabilities").status_code == 401
    assert client.get(base + "/capabilities", headers={"X-Session-Token": "reader"}).json()["can_mutate"] is False
    assert client.post(base + "/documents", json=payload(rig), headers={"X-Session-Token": "reader"}).status_code == 403
    created = client.post(base + "/documents", json=payload(rig), headers=headers)
    assert created.status_code == 201, created.text
    row = created.json(); url = base + "/documents/" + row["id"]
    assert client.get(url, headers={**headers, "X-Branch-Id": "other"}).status_code == 404
    value = public(row); value.update(expected_version=1, title="API saved")
    assert client.put(url, json=value, headers=headers).json()["version"] == 2
    stale = client.put(url, json=value, headers=headers)
    assert stale.status_code == 409 and stale.json()["detail"]["current"] == {"version": 2, "status": "DRAFT"}
    assert stale.headers["cache-control"] == "no-store"
    assert client.get(url + "/history", headers=headers).json()["current_version"] == 2
    exported = client.get(url + "/export", headers=headers)
    assert exported.status_code == 200 and "attachment;" in exported.headers["content-disposition"]
    assert exported.json()["document"]["title"] == "API saved"
    assert client.delete(url + "?expected_version=2", headers=headers).json()["status"] == "ARCHIVED"
    assert client.get(url, headers=headers).status_code == 404


def test_composition_mounts_both_existing_api_aliases_and_keeps_published_flags():
    from app.main import app
    from app.experimental.flags import FLAGS, flag_status
    paths = set(app.openapi()["paths"])
    for prefix in ("/api", "/api/v1"):
        assert prefix + "/novels/{nid}/experimental/creative/documents" in paths
    # The inherited comment says forty; baseline 1b7ff50 actually contains 44.
    # Bind the entire published ordered list rather than silently deleting four.
    assert len(FLAGS) == 44 and len(flag_status()["features"]) == 44
    assert hashlib.sha256(json.dumps(FLAGS, separators=(",", ":")).encode()).hexdigest() == "555b14e42e22ec4bc097034dd1ded933d20c89dcf6d132a209ec2561118fb9cc"
    assert "experimental.narrative_production_v2" in flag_status()["runtime_features"]


def test_real_composed_identity_membership_permissions_and_scope(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch)
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2")
    # Existing mounted fixture owns real File/opt-in PostgreSQL repositories,
    # trusted sessions, workspace membership and branch-specific role grants.
    # Only captured foundation dependencies are rebound to its owned storage.
    for name, value in (("store", e.store), ("novels", e.novels), ("chapters", e.chapters)):
        monkeypatch.setattr(e.experimental.creative_service, name, value)
    base = e.base + "/creative"
    body = {"mode": "SCREENPLAY", "title": "Branch-owned draft", "source_independent": True}
    assert e.client.get(base + "/capabilities").status_code == 401
    assert e.client.get(base + "/capabilities", headers={"X-Session-Token": "untrusted", "X-Branch-Id": e.branch}).status_code == 401
    assert e.client.get(base + "/capabilities", headers={"X-Session-Token": e.lead}).status_code == 400
    reader = e.client.get(base + "/capabilities", headers=e.viewer_headers)
    assert reader.status_code == 200 and reader.json()["can_mutate"] is False
    assert e.client.post(base + "/documents", headers=e.viewer_headers, json=body).status_code == 403
    created = e.client.post(base + "/documents", headers=e.headers, json=body)
    assert created.status_code == 201, created.text
    row = created.json()
    assert row["scope"] == e.scope and row["created_by"] == e.lead
    assert e.client.get(base + "/documents/" + row["id"], headers=e.viewer_headers).json() == row
    assert e.client.get(base + "/documents/" + row["id"], headers={**e.headers, "X-Branch-ID": e.other_branch}).status_code == 403
    assert e.store.read(e.nid, {**e.scope, "branch_id": e.other_branch})["collections"] == {}

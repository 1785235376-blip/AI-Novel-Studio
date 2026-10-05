from __future__ import annotations

import copy
import os
import threading
import uuid
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.config import Settings
from app.experimental.common import StaleSourceError
from app.experimental.imports import CANDIDATES, CHUNKS, JOBS, SemanticImportService, digest
from app.experimental.imports_api import create_import_router
from app.experimental.store import ExperimentalStore
from app.repositories.factory import create_repository_bundle
from app.services.chapter_service import ChapterService
from app.services.import_apply_service import ImportApplyInterrupted, ImportApplyService
from app.services.novel_service import NovelService
from app.services.v1_capability_service import CapabilityVersionConflict


@pytest.fixture(params=["file", pytest.param("postgres", marks=pytest.mark.postgres_backend_only)])
def ctx(request, tmp_path):
    backend = request.param
    url = os.getenv("TEST_POSTGRES_DATABASE_URL", "")
    if backend == "postgres" and not url:
        pytest.skip("dedicated real PostgreSQL endpoint not configured")
    bundle = create_repository_bundle(Settings(storage_backend=backend, database_url=url), data_root=tmp_path / "data")
    novels, chapters = NovelService(bundle.novels, bundle.chapters), ChapterService(bundle.chapters)
    nid = "semantic-" + uuid.uuid4().hex[:14]
    novels.create({"id": nid, "title": "Semantic import test"})
    scope = {"mode": "local", "novel_id": nid}
    store = ExperimentalStore(tmp_path / "data", backend=backend, database_url=url)
    apply = ImportApplyService(novels, tmp_path / "data")
    service = SemanticImportService(store, novels, chapters, apply_service=apply)
    value = SimpleNamespace(nid=nid, scope=scope, actor="author", novels=novels, chapters=chapters, store=store,
                            service=service, apply=apply, root=tmp_path / "data", backend=backend, url=url)
    yield value
    novels.delete(nid)
    if backend == "postgres":
        import psycopg
        with psycopg.connect(url.replace("postgresql+psycopg://", "postgresql://")) as connection:
            connection.execute("DELETE FROM experimental_scope_documents WHERE novel_id=%s", (nid,))


def create(ctx, text="Alice said hello in Harbor. One day the secret would return.", **kwargs):
    chapter = ctx.chapters.create(ctx.nid, {"title": "Arrival", "content": text})
    job = ctx.service.create_job(ctx.nid, ctx.scope, ctx.actor, [chapter["id"]], **kwargs)
    return chapter, job


def finish(ctx, job):
    while job["status"] in {"QUEUED", "ANALYZING"}:
        job = ctx.service.process(ctx.nid, ctx.scope, ctx.actor, job["id"], job["version"], max_chunks=100)
    return job


def approve_classic(ctx, job):
    rows = [r for r in ctx.service.candidates(ctx.nid, ctx.scope, job["id"])
            if r["kind"] in {"characters", "locations", "timeline_events", "foreshadowing"}]
    ctx.service.review_batch(ctx.nid, ctx.scope, ctx.actor,
        [{"id": r["id"], "expected_version": r["version"], "action": "approve"} for r in rows])
    return [r["id"] for r in rows]


def test_chunk_resume_exact_evidence_dedup_and_explicit_commit(ctx):
    text = ("Alice said hello in Harbor. One day the secret would return.\n\n" * 16)
    chapter, job = create(ctx, text, chunk_size=256, overlap=64)
    original = ctx.chapters.get(chapter["id"])
    job = ctx.service.process(ctx.nid, ctx.scope, ctx.actor, job["id"], job["version"])
    assert job["completed_chunks"] == 1 < job["total_chunks"]
    job = ctx.service.transition(ctx.nid, ctx.scope, ctx.actor, job["id"], "pause", job["version"])
    reopened = SemanticImportService(ExperimentalStore(ctx.root, ctx.backend, ctx.url), ctx.novels, ctx.chapters, ctx.apply)
    ctx.service = reopened
    with pytest.raises(ValueError, match="NOT_RUNNABLE"):
        reopened.process(ctx.nid, ctx.scope, ctx.actor, job["id"], job["version"])
    job = reopened.transition(ctx.nid, ctx.scope, ctx.actor, job["id"], "resume", job["version"])
    job = finish(ctx, job)
    assert job["status"] == "NEEDS_REVIEW"
    candidates = reopened.candidates(ctx.nid, ctx.scope, job["id"])
    assert {c["kind"] for c in candidates} >= {"characters", "locations", "timeline_events", "foreshadowing"}
    alice = [c for c in candidates if c["kind"] == "characters" and c["label"] == "Alice"]
    assert len(alice) == 1 and len(alice[0]["source_evidence"]) > 1
    for row in candidates:
        for evidence in row["source_evidence"]:
            assert original["content"][evidence["start"]:evidence["end"]] == evidence["quote"]
            assert digest(evidence["quote"]) == evidence["quote_sha256"]
            assert evidence["chapter_version"] == original["version"]
            assert evidence["paragraph"] == original["content"][:evidence["start"]].count("\n\n") + 1
    assert ctx.novels.data_set(ctx.nid, "characters") == []
    selected = approve_classic(ctx, job)
    assert ctx.novels.data_set(ctx.nid, "characters") == []
    committed = reopened.commit(ctx.nid, ctx.scope, ctx.actor, job["id"], job["version"], selected)
    assert committed["status"] == "COMMITTED"
    again = reopened.commit(ctx.nid, ctx.scope, ctx.actor, job["id"], committed["version"], selected)
    assert again == committed
    assert len(ctx.novels.data_set(ctx.nid, "characters")) == 1
    assert ctx.chapters.get(chapter["id"])["content"] == original["content"]
    assert ctx.novels.data_set(ctx.nid, "canon") == []


def test_stale_sources_fail_closed_and_persist_candidate_stale(ctx):
    chapter, job = create(ctx)
    job = finish(ctx, job)
    rows = ctx.service.candidates(ctx.nid, ctx.scope, job["id"])
    current = ctx.chapters.get(chapter["id"])
    ctx.chapters.save(chapter["id"], {"content": "New author revision", "version": current["version"]})
    with pytest.raises(StaleSourceError):
        ctx.service.review(ctx.nid, ctx.scope, ctx.actor, rows[0]["id"], "approve", rows[0]["version"])
    assert ctx.service.job(ctx.nid, ctx.scope, job["id"])["status"] == "STALE"
    assert all(row["stale"] for row in ctx.service.list_review_items(ctx.nid, ctx.scope))
    assert ctx.novels.data_set(ctx.nid, "characters") == []


def test_batch_all_or_nothing_versions_evidence_and_scope(ctx):
    _, job = create(ctx)
    job = finish(ctx, job)
    rows = ctx.service.candidates(ctx.nid, ctx.scope, job["id"])
    items = [{"id": r["id"], "expected_version": r["version"], "action": "approve"} for r in rows]
    items[-1]["expected_version"] += 1
    with pytest.raises(CapabilityVersionConflict):
        ctx.service.review_batch(ctx.nid, ctx.scope, ctx.actor, items)
    assert all(row["status"] == "PENDING" for row in ctx.service.candidates(ctx.nid, ctx.scope))
    with ctx.store.transaction(ctx.nid, ctx.scope) as doc:
        doc["collections"][CANDIDATES][rows[-1]["id"]]["source_evidence"][0]["quote"] = "fabricated"
    items[-1]["expected_version"] -= 1
    with pytest.raises(ValueError, match="EVIDENCE_INVALID"):
        ctx.service.review_batch(ctx.nid, ctx.scope, ctx.actor, items)
    assert all(row["status"] == "PENDING" for row in ctx.service.candidates(ctx.nid, ctx.scope))
    other_scope = {**ctx.scope, "mode": "collaboration", "workspace_id": "w", "storyline_id": "s", "branch_id": "b"}
    assert ctx.service.candidates(ctx.nid, other_scope) == []
    with pytest.raises(FileNotFoundError):
        ctx.service.review(ctx.nid, other_scope, ctx.actor, rows[0]["id"], "approve", rows[0]["version"])
    with pytest.raises(ValueError, match="BRANCH_SOURCE_ADAPTER_REQUIRED"):
        ctx.service.create_job(ctx.nid, other_scope, ctx.actor, job["chapter_ids"])


def test_adapter_validation_retry_and_restart_claim_recovery(ctx):
    class Adapter:
        adapter_id = "test-contract"
        verification = "MOCK_ONLY"
        mode = "invalid"
        def extract(self, chunk):
            if self.mode == "crash":
                raise SystemExit("simulated process death")
            if self.mode == "invalid":
                return [{"kind": "characters", "label": "Alice", "start": 0, "end": 3, "quote": "bad"}]
            return [{"kind": "characters", "label": "Alice", "start": 0, "end": 3, "quote": chunk["text"][:3]}]
    adapter = Adapter()
    ctx.service.adapters[adapter.adapter_id] = adapter
    _, job = create(ctx, adapter_id=adapter.adapter_id)
    with pytest.raises(ValueError, match="quote"):
        ctx.service.process(ctx.nid, ctx.scope, ctx.actor, job["id"], job["version"])
    job = ctx.service.job(ctx.nid, ctx.scope, job["id"])
    assert job["status"] == "FAILED" and ctx.service.candidates(ctx.nid, ctx.scope) == []
    job = ctx.service.transition(ctx.nid, ctx.scope, ctx.actor, job["id"], "retry", job["version"])
    adapter.mode = "crash"
    with pytest.raises(SystemExit):
        ctx.service.process(ctx.nid, ctx.scope, ctx.actor, job["id"], job["version"])
    job = ctx.service.job(ctx.nid, ctx.scope, job["id"])
    with pytest.raises(ValueError, match="LEASE_STILL_ACTIVE"):
        ctx.service.transition(ctx.nid, ctx.scope, ctx.actor, job["id"], "recover", job["version"])
    with ctx.store.transaction(ctx.nid, ctx.scope) as doc:
        for chunk in doc["collections"][CHUNKS].values():
            chunk["lease_expires_at"] = "2000-01-01T00:00:00+00:00"
    job = ctx.service.transition(ctx.nid, ctx.scope, ctx.actor, job["id"], "recover", job["version"])
    adapter.mode = "valid"
    job = finish(ctx, job)
    assert job["status"] == "NEEDS_REVIEW" and job["verification"] == "MOCK_ONLY"
    assert ctx.service.chunks(ctx.nid, ctx.scope, job["id"])[0]["attempt"] == 3


def test_pause_fences_late_adapter_callback(ctx):
    class Adapter:
        adapter_id = "pause-during-extract"
        verification = "MOCK_ONLY"
        def extract(self, chunk):
            job = ctx.service.job(ctx.nid, ctx.scope, chunk["job_id"])
            ctx.service.transition(ctx.nid, ctx.scope, ctx.actor, job["id"], "pause", job["version"])
            return [{"kind": "characters", "label": "Late", "start": 0, "end": 3, "quote": chunk["text"][:3]}]
    adapter = Adapter()
    ctx.service.adapters[adapter.adapter_id] = adapter
    _, job = create(ctx, adapter_id=adapter.adapter_id)
    with pytest.raises(ValueError, match="LATE_CALLBACK_REJECTED"):
        ctx.service.process(ctx.nid, ctx.scope, ctx.actor, job["id"], job["version"])
    assert ctx.service.job(ctx.nid, ctx.scope, job["id"])["status"] == "PAUSED"
    assert ctx.service.candidates(ctx.nid, ctx.scope) == []


def test_partial_commit_resumes_only_unfinished_targets(ctx):
    _, job = create(ctx)
    job = finish(ctx, job)
    selected = approve_classic(ctx, job)
    class FailingNovels:
        fail = True
        calls = []
        def data_set(self, nid, kind):
            return ctx.novels.data_set(nid, kind)
        def review_import_knowledge(self, nid, decision, candidates):
            kind = next(iter(candidates))
            self.calls.append(kind)
            if self.fail and kind == "locations":
                raise OSError("synthetic failure")
            return ctx.novels.review_import_knowledge(nid, decision, candidates)
    failing = FailingNovels()
    ctx.service.apply_service = ImportApplyService(failing, ctx.root)
    with pytest.raises(ImportApplyInterrupted):
        ctx.service.commit(ctx.nid, ctx.scope, ctx.actor, job["id"], job["version"], selected)
    job = ctx.service.job(ctx.nid, ctx.scope, job["id"])
    assert job["status"] == "PARTIAL" and job["apply_checkpoint"]["completed"] == 1
    assert len(ctx.novels.data_set(ctx.nid, "characters")) == 1
    failing.fail = False
    job = ctx.service.commit(ctx.nid, ctx.scope, ctx.actor, job["id"], job["version"], selected)
    assert job["status"] == "COMMITTED" and failing.calls.count("characters") == 1
    assert len(ctx.novels.data_set(ctx.nid, "characters")) == 1


def test_commit_crash_gap_journal_prevents_duplicate_success(ctx, monkeypatch):
    _, job = create(ctx)
    job = finish(ctx, job)
    selected = approve_classic(ctx, job)
    original = ImportApplyService.apply
    def crash_after_apply(self, *args, **kwargs):
        original(self, *args, **kwargs)
        raise SystemExit("process lost after journal completion")
    monkeypatch.setattr(ImportApplyService, "apply", crash_after_apply)
    with pytest.raises(SystemExit):
        ctx.service.commit(ctx.nid, ctx.scope, ctx.actor, job["id"], job["version"], selected)
    job = ctx.service.job(ctx.nid, ctx.scope, job["id"])
    assert job["status"] == "APPLYING"
    before = ctx.novels.data_set(ctx.nid, "characters")
    monkeypatch.setattr(ImportApplyService, "apply", original)
    ctx.service = SemanticImportService(ExperimentalStore(ctx.root, ctx.backend, ctx.url), ctx.novels, ctx.chapters, ctx.apply)
    job = ctx.service.commit(ctx.nid, ctx.scope, ctx.actor, job["id"], job["version"], selected)
    assert job["status"] == "COMMITTED" and ctx.novels.data_set(ctx.nid, "characters") == before


def test_cross_chunk_alias_conflict_suggestions_require_review(ctx):
    class Adapter:
        adapter_id = "alias-test"
        verification = "MOCK_ONLY"
        def extract(self, chunk):
            return [{"kind": "characters", "label": "Alice" if chunk["start"] == 0 else "Red",
                     "aliases": ["Red"] if chunk["start"] == 0 else [], "attributes": {"status": "alive" if chunk["start"] == 0 else "dead"},
                     "start": 0, "end": 3, "quote": chunk["text"][:3]}]
    adapter = Adapter()
    ctx.service.adapters[adapter.adapter_id] = adapter
    _, job = create(ctx, "Alice Red " * 80, chunk_size=256, overlap=32, adapter_id=adapter.adapter_id)
    job = finish(ctx, job)
    rows = ctx.service.candidates(ctx.nid, ctx.scope, job["id"])
    assert len(rows) == 2 and all(r["conflicts"] and r["resolution_suggestions"] for r in rows)
    with pytest.raises(ValueError, match="CONFLICT_REQUIRES_RESOLUTION"):
        ctx.service.review_batch(ctx.nid, ctx.scope, ctx.actor,
            [{"id": r["id"], "expected_version": r["version"], "action": "approve"} for r in rows])
    reviewed = ctx.service.review_batch(ctx.nid, ctx.scope, ctx.actor,
        [{"id": r["id"], "expected_version": r["version"], "action": "approve" if i == 0 else "reject"} for i, r in enumerate(rows)])
    assert {r["status"] for r in reviewed} == {"APPROVED", "REJECTED"}


def test_extended_kinds_are_proposals_not_fake_canon_promotion(ctx):
    _, job = create(ctx, "Organization: Order of Dawn\nRule: Magic costs memory\nRelationship: Alice trusts Bob")
    job = finish(ctx, job)
    rows = ctx.service.candidates(ctx.nid, ctx.scope, job["id"])
    assert {row["kind"] for row in rows} >= {"organizations", "world_rules", "relationships"}
    row = next(row for row in rows if row["kind"] == "world_rules")
    approved = ctx.service.review(ctx.nid, ctx.scope, ctx.actor, row["id"], "approve", row["version"])
    assert approved["status"] == "APPROVED"
    with pytest.raises(ValueError, match="MANUAL_PROMOTION_ADAPTER"):
        ctx.service.commit(ctx.nid, ctx.scope, ctx.actor, job["id"], job["version"], [row["id"]])
    assert ctx.novels.data_set(ctx.nid, "canon") == []


def test_api_flag_auth_version_and_reauthorization_fences(ctx):
    state = {"enabled": True, "allowed": True}
    def authorize(nid, token, branch, permission):
        if token != "owner":
            raise HTTPException(401, "SESSION_REQUIRED")
        if not state["allowed"] or branch == "denied":
            raise HTTPException(403, "FORBIDDEN")
        return ctx.actor, {"mode": "local", "novel_id": nid}
    def flag(name):
        assert name == "semantic_import_v2"
        if not state["enabled"]:
            raise HTTPException(404, "EXPERIMENTAL_DISABLED")
    app = FastAPI()
    app.include_router(create_import_router(ctx.service, authorize, flag))
    client = TestClient(app)
    base = f"/novels/{ctx.nid}/experimental/imports"
    assert client.get(base + "/jobs").status_code == 401
    headers = {"X-Session-Token": "owner"}
    state["enabled"] = False
    assert client.get(base + "/jobs", headers=headers).status_code == 404
    state["enabled"] = True
    chapter = ctx.chapters.create(ctx.nid, {"title": "Test", "content": "Alice said hello in Harbor."})
    response = client.post(base + "/jobs", json={"chapter_ids": [chapter["id"]]}, headers=headers)
    assert response.status_code == 201
    job = response.json()
    assert client.post(base + f"/jobs/{job['id']}/process", json={}, headers=headers).status_code == 422
    assert client.post(base + f"/jobs/{job['id']}/process", json={"expected_version": 99}, headers=headers).status_code == 409
    response = client.post(base + f"/jobs/{job['id']}/process", json={"expected_version": job["version"], "max_chunks": 100}, headers=headers)
    assert response.status_code == 200
    job = response.json()
    rows = client.get(base + "/candidates", params={"job_id": job["id"]}, headers=headers).json()["items"]
    response = client.post(base + f"/jobs/{job['id']}/review-batch", json={"items": [
        {"id": row["id"], "expected_version": row["version"], "action": "approve"} for row in rows]}, headers=headers)
    assert response.status_code == 200
    assert client.post(base + f"/jobs/{job['id']}/commit", json={"expected_version": job["version"]},
                       headers={**headers, "X-Branch-Id": "denied"}).status_code == 403
    def revoke():
        raise HTTPException(403, "REVOKED")
    with pytest.raises(HTTPException):
        ctx.service.commit(ctx.nid, ctx.scope, ctx.actor, job["id"], job["version"], reauthorize=revoke)
    assert ctx.novels.data_set(ctx.nid, "characters") == []


def test_candidate_get_detects_stale_without_review_attempt(ctx):
    chapter, job = create(ctx)
    job = finish(ctx, job)
    current = ctx.chapters.get(chapter["id"])
    ctx.chapters.save(chapter["id"], {"content": "Changed source", "version": current["version"]})
    assert all(row["stale"] for row in ctx.service.candidates(ctx.nid, ctx.scope, job["id"]))


def test_commit_rechecks_each_target_source_and_stops_mid_batch(ctx):
    chapter, job = create(ctx)
    job = finish(ctx, job)
    selected = approve_classic(ctx, job)
    class EditingNovels:
        calls = []
        def data_set(self, nid, kind):
            return ctx.novels.data_set(nid, kind)
        def review_import_knowledge(self, nid, decision, candidates):
            self.calls.append(next(iter(candidates)))
            result = ctx.novels.review_import_knowledge(nid, decision, candidates)
            current = ctx.chapters.get(chapter["id"])
            ctx.chapters.save(chapter["id"], {"content": "Changed while applying", "version": current["version"]})
            return result
    editing = EditingNovels()
    ctx.service.apply_service = ImportApplyService(editing, ctx.root)
    with pytest.raises(ImportApplyInterrupted):
        ctx.service.commit(ctx.nid, ctx.scope, ctx.actor, job["id"], job["version"], selected)
    assert editing.calls == ["characters"]
    job = ctx.service.job(ctx.nid, ctx.scope, job["id"])
    assert job["status"] == "PARTIAL" and job["apply_checkpoint"]["completed"] == 1
    with pytest.raises(StaleSourceError):
        ctx.service.commit(ctx.nid, ctx.scope, ctx.actor, job["id"], job["version"], selected)
    assert len(ctx.novels.data_set(ctx.nid, "characters")) == 1
    assert ctx.novels.data_set(ctx.nid, "locations") == []


def test_concurrent_review_has_one_version_winner(ctx):
    _, job = create(ctx)
    job = finish(ctx, job)
    row = ctx.service.candidates(ctx.nid, ctx.scope, job["id"])[0]
    barrier = threading.Barrier(2)
    outcomes = []
    def review(action):
        barrier.wait()
        try:
            result = ctx.service.review(ctx.nid, ctx.scope, ctx.actor, row["id"], action, row["version"])
            outcomes.append(result["status"])
        except CapabilityVersionConflict:
            outcomes.append("VERSION_CONFLICT")
    threads = [threading.Thread(target=review, args=(action,)) for action in ("approve", "reject")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
        assert not thread.is_alive()
    assert outcomes.count("VERSION_CONFLICT") == 1 and len(outcomes) == 2


def test_inbox_projects_domain_owned_actions_and_evidence(ctx):
    _, job = create(ctx)
    job = finish(ctx, job)
    items = ctx.service.list_review_items(ctx.nid, ctx.scope)
    assert items and all(item["domain"] == "import" and "approve" in item["allowed_actions"] for item in items)
    item = items[0]
    assert item["source_versions"] and item["source_evidence"] and not item["applied"]
    approved = ctx.service.review(ctx.nid, ctx.scope, ctx.actor, item["id"], "approve", item["version"])
    assert approved["status"] == "APPROVED" and not approved["applied"]

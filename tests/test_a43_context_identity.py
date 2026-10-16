"""A43 typed identities through real context/agent/accept persistence owners.

Disposable File and real PostgreSQL fixtures; model execution is an explicitly
synthetic node only. PostgreSQL cases require the existing opted-in CI profile.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.actor_context import SessionContext
from app.config import settings
from app.jobs import JobManager
from app.model_runtime import TextGenerationResponse, TextModelNodeOutput
from app.repositories.factory import create_repository_bundle
from app.repositories.postgres.common import novel_or_raise
from app.services import CanonService, ChapterService, ContextService, GenerationService
from app.services.agent_context_service import AgentContextService
from app.workflow import NovelWorkflow
from test_r3_mounted_contracts import checked, mounted, prefix


@pytest.fixture
def typed_context_app(mounted, monkeypatch):
    e = mounted
    # Simulate an imported project whose old allocation provenance is unknown.
    # Its existing unambiguous numeric object stays valid; only new objects use UUID.
    if e.backend == "file":
        (e.root / "novels" / e.nid / "chapter_identity.json").unlink()
    else:
        with e.bundle.novels.database.session() as session:
            novel_or_raise(session, e.nid).chapter_identity_provenance = "UNKNOWN_NO_HISTORICAL_ALLOCATION_LOG"
    e.typed = e.chapters.get(e.chapters.create(e.nid, {"title": "Typed owner", "content": "TYPED_BODY_ONLY"})["id"])
    assert e.typed["id"].startswith(e.nid + ":~")
    e.alias = f"{e.nid}:{e.typed['number']}"
    e.contexts = ContextService(e.bundle.novels, e.bundle.chapters, e.lore,
        enable_lore_context=True, narrative_repository=e.bundle.narrative,
        enable_narrative_context=True, enable_context_pack_v2=True)
    e.agent_contexts = AgentContextService(e.bundle.novels, e.bundle.chapters, e.contexts)
    e.agents.contexts = e.agent_contexts
    monkeypatch.setattr(e.api, "agent_context_service", e.agent_contexts)
    monkeypatch.setattr(e.api, "context_service", e.contexts)
    monkeypatch.setattr(e.main, "context_service", e.contexts)
    object.__setattr__(settings, "novel_data", e.root)
    return e


def test_typed_context_keeps_narrative_policy_and_pack_identity(typed_context_app, monkeypatch):
    e = typed_context_app
    e.bundle.narrative.create(e.nid, "mysteries", {"id": e.nid + "-typed-mystery", "project_id": e.nid,
        "title": "Synthetic mystery", "status": "OPEN"})
    e.bundle.narrative.create(e.nid, "chapter_links", {"id": e.nid + "-typed-link", "project_id": e.nid,
        "chapter_id": e.typed["id"], "chapter_version": e.typed["version"], "entity_type": "MYSTERY",
        "entity_id": e.nid + "-typed-mystery", "progress_type": "DEVELOPED", "event_id": e.nid + "-typed-event"})
    context = e.contexts.for_chapter(e.typed["id"], "Synthetic instruction")
    assert context["chapter_id"] == e.typed["id"]
    assert context["chapter"] == e.typed["number"]
    assert context["narrative_context"]["mysteries"][0]["selection_reason"] == "CURRENT_CHAPTER_LINK"
    chunks = context["context_pack_v2"]["chunks"]
    assert any(item["source_id"] == e.typed["id"] for item in chunks)
    # Test the declared accepted-chapter source even when this backend has no state yet.
    policy = e.contexts._context_policy({**context, "current_story_state": {"active_characters": ["alice"]}})
    accepted = [item for item in policy.authoritative if item.metadata.source_type == "ACCEPTED_CHAPTER"]
    assert accepted and accepted[0].metadata.source_id == e.typed["id"]
    assert accepted[0].metadata.chapter_version_id == f"{e.typed['id']}:v{e.typed['version']}"
    with pytest.raises(FileNotFoundError):
        e.contexts.for_chapter(e.alias)
    with pytest.raises(FileNotFoundError):
        e.agent_contexts.build("writer", e.nid, e.typed["number"])
    calls = []
    def forbidden_read(chapter_id):
        calls.append(chapter_id)
        pytest.fail("wrong-project identity reached the chapter repository")
    with monkeypatch.context() as patch:
        patch.setattr(e.bundle.chapters, "get", forbidden_read)
        with pytest.raises(FileNotFoundError):
            e.contexts.build("foreign-project", e.typed["number"], chapter_id=e.typed["id"])
        with pytest.raises(FileNotFoundError):
            e.agent_contexts.build("writer", "foreign-project", e.typed["number"], chapter_id=e.typed["id"])
    assert calls == []


def test_agent_preview_create_retry_http_carries_selected_full_id(typed_context_app, monkeypatch):
    e = typed_context_app
    token = "a43-context-session"
    e.sessions.register(token, SessionContext(actor_id="synthetic-actor", workspace_id="synthetic-workspace", session_id="synthetic-session", client_id="test"))
    e.headers = {"X-Session-Token": token}
    params = {"novel_id": e.nid, "chapter": e.typed["number"], "chapter_id": e.typed["id"]}
    preview = checked(e.client.get(e.prefix + "/agents/writer/context-preview", params=params, headers=e.headers))
    assert preview["chapter_id"] == preview["sections"]["writing_context"]["chapter_id"] == e.typed["id"]
    assert next(item for item in preview["source_manifest"] if item["section"] == "writing_context")["chapter_id"] == e.typed["id"]
    body = {**params, "agent_id": "writer"}
    job = checked(e.client.post(e.prefix + "/agent-jobs", json=body, headers=e.headers), 202)
    assert job["chapter_id"] == e.typed["id"]
    checked(e.client.post(e.prefix + f"/agent-jobs/{job['id']}/cancel", headers=e.headers))
    retried = checked(e.client.post(e.prefix + f"/agent-jobs/{job['id']}/retry", headers=e.headers), 202)
    assert retried["chapter_id"] == e.typed["id"] and retried["retry_of"] == job["id"]
    assert retried["context_hash"] == job["context_hash"]
    old_params = {key: value for key, value in params.items() if key != "chapter_id"}
    assert e.client.get(e.prefix + "/agents/writer/context-preview", params=old_params, headers=e.headers).status_code == 404
    assert e.client.post(e.prefix + "/agent-jobs", json={**old_params, "agent_id": "writer"}, headers=e.headers).status_code == 404
    # Old unambiguous numeric chapter callers retain their previous contract.
    old_params["chapter"] = e.chapter["number"]
    assert checked(e.client.get(e.prefix + "/agents/writer/context-preview", params=old_params, headers=e.headers))["chapter_id"] == e.chapter["id"]


def test_model_dispatch_rebuild_uses_persisted_typed_id(typed_context_app):
    e = typed_context_app
    captured = []
    class Node:
        def execute(self, value):
            request = value.request
            request.dispatch_guard()
            captured.append(request.context)
            result = {"schema": "story_plan_proposal", "agent_id": "planner", "summary": "Synthetic only",
                "proposals": [], "findings": [], "context_hash": request.context["context_hash"]}
            response = TextGenerationResponse(json.dumps(result), "completed", "synthetic", "fixture", execution_mode="mock_standin")
            return TextModelNodeOutput(response.text, response, request.job_id)
    e.agents.runtime = SimpleNamespace(is_remote_text_provider=lambda _: False, providers={}, prepare_text_route=lambda *_: Node())
    e.agents.agent_runner = SimpleNamespace(build_prompt=lambda *_: "Synthetic identity contract")
    job = e.agents.create("planner", e.nid, e.typed["number"], provider="synthetic", model="fixture",
        execution_mode="model", chapter_id=e.typed["id"])
    e.chapters.move(e.typed["id"], "up")
    result = e.agents.execute(job["id"])
    assert result["status"] == "COMPLETED", result
    assert result["model_called"] is False
    assert len(captured) == 1 and captured[0]["chapter_id"] == e.typed["id"]
    assert e.bundle.generations.get(job["id"])["chapter_id"] == e.typed["id"]


@pytest.mark.parametrize("operation", ["polish", "continue"])
def test_generation_accept_summary_and_pending_keep_typed_owner(typed_context_app, operation):
    e = typed_context_app
    manager = JobManager(GenerationService(e.bundle.generations), e.chapters, e.contexts, CanonService(e.bundle.canon),
        memory_extractor=SimpleNamespace(enqueue=lambda *_: None), snapshot_required=False)
    job = manager.prepare_job(operation, {"novel_id": e.nid, "chapter_id": e.typed["id"], "profile": "LOCAL_ONLY"})
    job.output, job.status = "SYNTHETIC_APPROVED_RESULT", "COMPLETED"
    manager.jobs[job.id] = job
    manager._persist(job)
    accepted = manager.accept(job.id)
    saved = accepted["chapter"]
    assert saved["id"].startswith(e.nid + ":~")
    summary = next(row for row in e.bundle.novels.get_context_sources(e.nid)["summaries"] if row["chapter_id"] == saved["id"])
    assert summary["summary"] == "SYNTHETIC_APPROVED_RESULT"
    assert accepted["pending_canon"]["chapter_id"] == saved["id"]
    with pytest.raises(FileNotFoundError):
        e.chapters.save_summary(e.nid, saved["number"], "STALE_NUMERIC_RESULT")
    assert e.chapters.get(e.chapter["id"])["document"] == e.chapter["document"]


def test_deleted_typed_job_retry_cannot_resolve_replacement_by_number(typed_context_app):
    e = typed_context_app
    job = e.agents.create("writer", e.nid, e.typed["number"], chapter_id=e.typed["id"])
    e.agents.cancel(job["id"])
    e.chapters.delete(e.typed["id"])
    replacement = e.chapters.create(e.nid, {"title": "Replacement", "content": "DO_NOT_TOUCH"})
    with pytest.raises(FileNotFoundError):
        e.agents.retry(job["id"])
    assert e.chapters.get(replacement["id"])["version"] == 1
    assert e.bundle.generations.get(job["id"])["status"] == "CANCELLED"


@pytest.mark.file_backend_only
def test_legacy_fixture_writer_cannot_overwrite_typed_owner(tmp_path):
    root = tmp_path / "novels" / "legacy-fixture"
    root.mkdir(parents=True)
    (root / "novel.json").write_text(json.dumps({"id": "legacy-fixture", "title": "Synthetic fixture"}))
    bundle = create_repository_bundle(data_root=tmp_path)
    chapter = bundle.chapters.create("legacy-fixture", {"content": "KEEP_TYPED"})
    before = bundle.chapters.get(chapter["id"])
    with pytest.raises(FileNotFoundError):
        NovelWorkflow(tmp_path).run("legacy-fixture", chapter["number"], "", draft_override="BAD_NUMERIC_OVERWRITE")
    assert bundle.chapters.get(chapter["id"]) == before


@pytest.mark.parametrize("route", ["preview", "pack"])
def test_original_context_routes_accept_typed_id_and_reject_wrong_owner(typed_context_app, route):
    e = typed_context_app
    payload = {"novel_id": e.nid, "chapter": e.typed["number"], "instruction": "Synthetic", "chapter_id": e.typed["id"]}
    def request(value):
        if route == "preview":
            return e.client.get(e.prefix + "/context-preview", params={**value, "target": "local"})
        return e.client.post("/context-packs", json=value)
    context = checked(request(payload))
    assert context["chapter_id"] == e.typed["id"]
    assert context["chapter"] == e.typed["number"]
    assert request({**payload, "chapter_id": e.alias}).status_code == 404
    assert request({**payload, "novel_id": "foreign-project"}).status_code == 404
    # The existing numeric contract remains the plain context for an old owner.
    numeric = {key: value for key, value in payload.items() if key != "chapter_id"}
    numeric["chapter"] = e.chapter["number"]
    old = checked(request(numeric))
    explicit = checked(request({**numeric, "chapter_id": e.chapter["id"]}))
    assert explicit == old and "chapter_id" not in old

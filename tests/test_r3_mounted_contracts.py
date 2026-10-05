"""Mounted R3 integration contracts, with real persistence and authorization.

These tests use the production app/router composition rather than a test router.
Only disposable storage/service dependencies are rebound; authorization is the
existing trusted-session, membership and role stack, never an allow-all stub.
PostgreSQL cases require the existing explicitly opted-in test database profile.
No test invokes a model, GPU, paid provider or external workflow.
"""
from __future__ import annotations

import copy
import os
from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.actor_context import SessionContext
from app.authorization import (
    AuthorizationScope, DomainRole, DomainRoleAssignment, ModalityDomain,
    PermissionAssignment, ScopeKind,
)
from app.collaboration import Branch, Storyline, Workspace
from app.config import Settings
from app.experimental.flags import FLAGS
from app.experimental.store import ExperimentalStore
from app.identity import User, WorkspaceMembership
from app.repositories.factory import create_repository_bundle
from app.services import ChapterService, NovelService, CanonService, LoreService
from app.services.asset_library_service import AssetLibraryService
from app.services.agent_context_service import AgentContextService
from app.services.agent_job_service import AgentJobService
from app.services.authorization_service import AuthorizationService
from app.services.collaboration_scope_service import CollaborationScopeService
from app.services.creation_workbench_service import CreationWorkbenchService, WorkbenchRecordIn
from app.services.export_job_service import ExportJobService
from app.services.generation_service import GenerationService
from app.services.identity_service import IdentityService
from app.services.import_apply_service import ImportApplyService
from app.services.import_review_service import ImportReviewService
from app.services.membership_authorization_service import MembershipAuthorizationService
from app.services.screenplay_service import ScreenplayService
from app.services.v1_capability_service import V1CapabilityService
from app.trusted_sessions import TrustedSessionResolver


READ_PATHS = (
    "planning/graphs", "planning/templates", "planning/proposals",
    "world/schema", "world/records", "world/canon", "world/continuity",
    "imports/jobs", "imports/candidates", "teams/catalog", "teams/runs",
    "media/adapters", "media/cover-briefs", "media/storyboard-briefs",
    "media/tasks", "media/proposals", "embeddings/status", "embeddings/indexes",
    "audiobook/capabilities", "audiobook/profiles", "audiobook/mappings",
    "audiobook/plans", "audiobook/mixes", "review-inbox",
)


def checked(response, status=200):
    assert response.status_code == status, response.text
    return response.json()


@pytest.fixture(params=["/api", "/api/v1"])
def prefix(request):
    return request.param


@pytest.fixture(params=[
    pytest.param("file", marks=pytest.mark.file_backend_only),
    pytest.param("postgres", marks=pytest.mark.postgres_backend_only),
])
def mounted(request, tmp_path, monkeypatch, prefix):
    import app.api as api
    import app.dependencies as dependencies
    import app.experimental.api as experimental
    import app.main as main
    import app.workflow_api as workflows
    from app.audio_production_store import AudioProductionStore
    import app.audio_production_store as audio_module

    backend = request.param
    url = os.getenv("TEST_POSTGRES_DATABASE_URL", "") if backend == "postgres" else ""
    if backend == "postgres" and not url:
        pytest.fail("real PostgreSQL contracts require TEST_POSTGRES_DATABASE_URL")
    config = Settings(storage_backend=backend, database_url=url, novel_data=tmp_path,
                      enable_collaboration_runtime=False, enable_packaged_runtime=False,
                      mock_provider=True, enable_cloud=False)
    bundle = create_repository_bundle(config, data_root=tmp_path)
    novels = NovelService(bundle.novels, bundle.chapters)
    chapters = ChapterService(bundle.chapters)
    assets = AssetLibraryService(tmp_path)
    exports = ExportJobService(tmp_path, novels.export)
    capabilities = V1CapabilityService(tmp_path, novels, chapters, assets, exports)
    creation = CreationWorkbenchService(capabilities, chapters, novels)
    screenplays = ScreenplayService(bundle.novels, bundle.chapters)
    imports = ImportReviewService(tmp_path)
    canon, lore = CanonService(bundle.canon), LoreService(bundle.lore)
    from app.services.context_service import ContextService
    context = ContextService(bundle.novels, bundle.chapters, lore, enable_lore_context=False,
                             enable_narrative_context=False, enable_context_pack_v2=False)
    agent_context = AgentContextService(bundle.novels, bundle.chapters, context)
    agents = AgentJobService(GenerationService(bundle.generations), agent_context, bundle.novels)
    audio = AudioProductionStore(tmp_path / "audio-production")
    scopes = CollaborationScopeService(bundle.scope, bundle.novels)
    identity = IdentityService(bundle.identity, scopes)
    authorization = AuthorizationService(bundle.authorization, scopes)
    membership = MembershipAuthorizationService(identity, authorization)
    sessions = TrustedSessionResolver()
    store = ExperimentalStore(tmp_path, backend, url)
    services = (
        experimental.planning_service, experimental.world_service,
        experimental.import_service, experimental.team_service,
        experimental.media_service, experimental.embedding_service,
        experimental.audiobook_service, experimental.workspace_tools_service,
        experimental.writing_focus_service, experimental.story_graph_service,
        experimental.model_broker_service, experimental.model_benchmark_service,
        experimental.production_lineage_service, experimental.style_analysis_service,
        experimental.narrative_judge_service, experimental.change_impact_service,
        experimental.story_simulator_service, experimental.research_library_service,
        experimental.revision_intelligence_service, experimental.reader_preflight_service,
        experimental.writing_sessions_service, experimental.director_service,
        experimental.timeline_exchange_service, experimental.subtitle_timeline_service,
        experimental.portable_projects_service, experimental.safe_batches_service,
        experimental.multilingual_editions_service, experimental.template_library_service,
        experimental.declarative_agents_service,
    )
    # Router closures capture these real service instances at application import.
    # Rebind their dependencies, not the route implementation or approval methods.
    for service in services:
        for name, value in (("store", store), ("novels", novels), ("chapters", chapters)):
            monkeypatch.setattr(service, name, value)
        if hasattr(service, "assets"):
            monkeypatch.setattr(service, "assets", assets)
        if hasattr(service, "screenplays"):
            monkeypatch.setattr(service, "screenplays", screenplays)
        if hasattr(service, "creation"):
            monkeypatch.setattr(service, "creation", creation)
    monkeypatch.setattr(audio_module, "audio_production_store", audio)
    monkeypatch.setattr(experimental.research_library_service, "legacy", capabilities)
    monkeypatch.setattr(experimental.import_service, "apply_service", ImportApplyService(novels, tmp_path))
    for name, value in {
        "settings": config, "novel_service": novels, "chapter_service": chapters,
        "creation_workbench_service": creation, "canon_service": canon, "lore_service": lore,
        "asset_library_service": assets, "export_job_service": exports,
        "v1_capability_service": capabilities, "screenplay_service": screenplays,
        "import_review_service": imports, "audio_production_store": audio,
        "collaboration_scope_service": scopes, "membership_authorization_service": membership,
        "trusted_session_resolver": sessions,
        "agent_job_service": agents,
    }.items():
        monkeypatch.setattr(api, name, value)
    monkeypatch.setattr(dependencies, "repositories", bundle)
    monkeypatch.setattr(main, "settings", config)
    monkeypatch.setattr(main, "trusted_session_resolver", sessions)
    monkeypatch.setattr(workflows, "service", capabilities)
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", ",".join(FLAGS))
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)
    client = TestClient(main.app)
    nid = checked(client.post(prefix + "/novels", json={
        "id": "r3-mounted-" + uuid4().hex, "title": "Synthetic mounted R3",
    }), 201)["id"]
    chapter = checked(client.post(prefix + f"/novels/{nid}/chapters", json={
        "title": "The gate", "content": 'Alice said: “Let us enter.”\nThe city gate opened.',
    }), 201)
    chapter = chapters.get(chapter["id"])
    novels.upsert_character(nid, "alice", {"name": "Alice", "privacy_level": "LOCAL_ONLY"})
    novels.upsert_location(nid, "city", {"name": "City", "privacy_level": "LOCAL_ONLY"})
    novels.upsert_story_route(nid, "main-route", {"title": "Main route"})
    env = SimpleNamespace(
        client=client, prefix=prefix, base=prefix + f"/novels/{nid}/experimental",
        nid=nid, chapter=chapter, novels=novels, chapters=chapters, assets=assets,
        store=store, services=services, experimental=experimental, bundle=bundle,
        creation=creation, imports=imports, canon=canon, lore=lore, audio=audio,
        capabilities=capabilities, screenplays=screenplays, scopes=scopes, exports=exports,
        identity=identity, authorization=authorization, membership=membership,
        sessions=sessions, config=config, root=tmp_path, backend=backend, url=url,
        agents=agents,
        lore_cleanup={"proposals": [], "evidence": []},
        scope={"mode": "local", "novel_id": nid}, api=api, main=main,
    )
    yield env
    client.close()
    exports._pool.shutdown(wait=True)
    if backend == "postgres":
        try:
            with store._connect() as connection:
                connection.execute("DELETE FROM experimental_scope_documents WHERE novel_id = %s", (nid,))
            if env.lore_cleanup["proposals"] or env.lore_cleanup["evidence"]:
                from sqlalchemy import delete, select
                from app.models.lore import EvidenceModel, LoreProposalEvidenceModel, LoreProposalModel
                from app.repositories.postgres.common import external_uuid, novel_or_raise
                # Evidence references are RESTRICT, so remove this fixture's
                # exact junctions before its proposal/evidence and novel rows.
                # Both the generated IDs and the owning project must match.
                with bundle.novels.database.session() as session:
                    project = novel_or_raise(session, nid)
                    proposal_filter = (
                        LoreProposalModel.novel_id == project.id,
                        LoreProposalModel.id.in_([external_uuid(value) for value in env.lore_cleanup["proposals"]]),
                    )
                    evidence_filter = (
                        EvidenceModel.novel_id == project.id,
                        EvidenceModel.id.in_([external_uuid(value) for value in env.lore_cleanup["evidence"]]),
                    )
                    session.execute(delete(LoreProposalEvidenceModel).where(
                        LoreProposalEvidenceModel.proposal_id.in_(select(LoreProposalModel.id).where(*proposal_filter)),
                        LoreProposalEvidenceModel.evidence_id.in_(select(EvidenceModel.id).where(*evidence_filter)),
                    ))
                    session.execute(delete(LoreProposalModel).where(*proposal_filter))
                    session.execute(delete(EvidenceModel).where(*evidence_filter))
            novels.delete(nid)
        finally:
            bundle.novels.database.engine.dispose()


def scoped(mounted, monkeypatch):
    """Real session/identity/membership stack, including an exact branch role."""
    e = mounted
    # Authorization storage is real and isolated. IDs are unique for PG runs.
    suffix = uuid4().hex
    e.workspace, e.storyline = "w-" + suffix, "s-" + suffix
    e.branch, e.other_branch = "b-" + suffix, "other-" + suffix
    e.lead, e.viewer = "lead-" + suffix, "viewer-" + suffix
    e.scopes.create_workspace(Workspace(e.workspace, "Mounted workspace"))
    e.scopes.link_project(e.workspace, e.nid)
    e.scopes.create_storyline(Storyline(e.storyline, e.workspace, e.nid, "Main storyline"))
    for bid in (e.branch, e.other_branch):
        e.scopes.create_branch(Branch(bid, e.workspace, e.nid, e.storyline, bid))
    for user in (e.lead, e.viewer):
        e.identity.create_user(User(user, user))
        e.identity.add_membership(WorkspaceMembership("m-" + user, user, e.workspace))
        e.sessions.register(user, SessionContext("session-" + user, "client-" + user, user, e.workspace))
    auth_scope = AuthorizationScope(ScopeKind.BRANCH, e.workspace, e.nid, e.storyline, e.branch)
    e.role = "role-" + suffix
    e.authorization.assign_role(DomainRoleAssignment(e.role, e.lead, DomainRole.DOMAIN_LEAD,
                                                     ModalityDomain.NOVEL, auth_scope, e.lead))
    e.authorization.assign_permission(PermissionAssignment("read-" + suffix, e.viewer, "domain.read",
                                                            ModalityDomain.NOVEL, auth_scope, e.lead))
    e.scope = {"mode": "collaboration", "novel_id": e.nid, "workspace_id": e.workspace,
               "storyline_id": e.storyline, "branch_id": e.branch}
    config = replace(e.config, enable_collaboration_runtime=True)
    monkeypatch.setattr(e.api, "settings", config)
    monkeypatch.setattr(e.main, "settings", config)
    e.headers = {"X-Session-Token": e.lead, "X-Branch-ID": e.branch}
    e.viewer_headers = {"X-Session-Token": e.viewer, "X-Branch-ID": e.branch}
    return e


def planning_proposal(e, *, headers=None, with_sources=False, title="Open the gate"):
    headers = headers or {}
    graph = checked(e.client.post(e.base + "/planning/graphs", headers=headers,
                                  json={"title": "Gate plan"}), 201)
    body = {"node_id": graph["root_node_id"], "expected_node_version": 1,
            "title": title, "fields": {"goal": "Enter the city"}}
    if with_sources:
        body["links"] = {"chapter_ids": [e.chapter["id"]], "character_ids": ["alice"]}
    proposal = checked(e.client.post(e.base + "/planning/proposals", headers=headers, json=body), 201)
    return graph, proposal


def test_mounted_default_off_and_v1_override_all_domain_reads(mounted, monkeypatch):
    e = mounted
    for configured, v1 in (("", ""), (",".join(FLAGS), "true")):
        monkeypatch.setenv("EXPERIMENTAL_FEATURES", configured)
        monkeypatch.setenv("V1_ACCEPTANCE_MODE", v1)
        flags = checked(e.client.get(e.prefix + "/experimental/features"))
        assert flags["default_enabled"] is False and not any(flags["features"].values())
        for path in READ_PATHS:
            response = e.client.get(e.base + "/" + path)
            assert response.status_code == 404, (path, response.text)
            assert response.json()["detail"]["code"] == "EXPERIMENTAL_FEATURE_DISABLED"
        # Existing project/manuscript APIs remain available and unmodified.
        assert checked(e.client.get(e.prefix + f"/chapters/{e.chapter['id']}")) == e.chapter


def test_mounted_every_enabled_domain_read_uses_real_composition(mounted):
    e = mounted
    flags = checked(e.client.get(e.prefix + "/experimental/features"))
    assert all(flags["features"].values())
    for path in READ_PATHS:
        checked(e.client.get(e.base + "/" + path))
    embeddings = checked(e.client.get(e.base + "/embeddings/status"))
    assert embeddings["status"] == "NOT_CONFIGURED"
    inbox = checked(e.client.get(e.base + "/review-inbox"))
    assert inbox["items"] == []
    assert {x["domain"] for x in inbox["unavailable"]} == {"legacy_agent", "legacy_workflow"}


def test_mounted_planning_inbox_history_restart_preserves_manuscript_and_canon(mounted, monkeypatch):
    e = mounted
    before = (e.chapters.get(e.chapter["id"]),
              {name: e.novels.data_set(e.nid, name) for name in ("characters", "locations", "canon", "story_routes")})
    graph = checked(e.client.post(e.base + "/planning/graphs", json={"title": "Gate plan"}), 201)
    parent = graph["root_node_id"]
    for level in ("VOLUME", "CHAPTER", "SCENE"):
        body = {"graph_id": graph["id"], "parent_id": parent, "level": level, "title": level.title()}
        if level in {"CHAPTER", "SCENE"}:
            body["links"] = {"chapter_ids": [e.chapter["id"]]}
        node = checked(e.client.post(e.base + "/planning/nodes", json=body), 201)
        parent = node["id"]
    proposals = []
    for ending in ("Hope", "Tragedy"):
        proposals.append(checked(e.client.post(e.base + "/planning/proposals", json={
            "node_id": parent, "expected_node_version": 1, "title": ending,
            "fields": {"ending_intent": ending, "character_objectives": {"alice": "Enter"}},
            "links": {"chapter_ids": [e.chapter["id"]], "character_ids": ["alice"],
                      "location_ids": ["city"], "story_route_ids": ["main-route"]},
        }), 201))
    a, b = proposals
    compared = checked(e.client.post(e.base + "/planning/proposals/compare",
                                     json={"proposal_ids": [a["id"], b["id"]]}))
    assert compared["differences"]["ending_intent"] == {a["id"]: "Hope", b["id"]: "Tragedy"}
    item = checked(e.client.get(e.base + "/review-inbox", params={"domain": "planning", "search": "Hope"}))["items"][0]
    assert item["id"] == a["id"] and item["scope"] == e.scope
    assert item["source_versions"][e.chapter["id"]]["version"] == e.chapter["version"]
    assert item["created_by"] == "local-author" and not item["stale"]
    assert (e.chapters.get(e.chapter["id"]), {name: e.novels.data_set(e.nid, name) for name in before[1]}) == before
    review_path = e.base + "/review-inbox/planning/" + a["id"] + "/approve"
    conflict = e.client.post(review_path, json={"expected_version": 999})
    assert conflict.status_code == 409
    approved = checked(e.client.post(review_path, json={"expected_version": 1}))
    assert approved["status"] == "APPROVED" and approved["version"] == 2
    stale = e.client.post(e.base + "/review-inbox/planning/" + b["id"] + "/approve", json={"expected_version": 1})
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "EXPERIMENTAL_SOURCE_STALE"
    history = checked(e.client.get(e.base + f"/planning/proposals/{a['id']}/history"))["items"]
    assert len(history) == 1 and history[0]["status"] == "REVIEW"
    reread = ExperimentalStore(e.root, e.backend, e.url)
    for service in e.services:
        monkeypatch.setattr(service, "store", reread)
    assert checked(e.client.get(e.base + f"/planning/proposals/{a['id']}"))["status"] == "APPROVED"
    persisted = checked(e.client.get(e.base + f"/planning/graphs/{graph['id']}"))
    assert {n["level"] for n in persisted["nodes"]} == {"PROJECT", "VOLUME", "CHAPTER", "SCENE"}
    assert next(n for n in persisted["nodes"] if n["id"] == parent)["fields"]["ending_intent"] == "Hope"
    restored = checked(e.client.post(e.base + f"/planning/proposals/{a['id']}/restore",
                                     json={"expected_version": 2, "historical_version": 1}))
    assert restored["status"] == "REVIEW" and restored["version"] == 3
    assert (e.chapters.get(e.chapter["id"]), {name: e.novels.data_set(e.nid, name) for name in before[1]}) == before


def test_mounted_source_edit_fences_inbox_approval(mounted):
    e = mounted
    _, proposal = planning_proposal(e, with_sources=True)
    current = e.chapters.get(e.chapter["id"])
    document = copy.deepcopy(current["document"])
    document.setdefault("content", []).append({"type": "paragraph", "content": [{"type": "text", "text": "Changed source."}]})
    e.chapters.save(e.chapter["id"], {"document": document, "version": current["version"]})
    rows = checked(e.client.get(e.base + "/review-inbox", params={"domain": "planning", "stale": True}))["items"]
    assert [r["id"] for r in rows] == [proposal["id"]]
    response = e.client.post(e.base + f"/review-inbox/planning/{proposal['id']}/approve", json={"expected_version": 1})
    assert response.status_code == 409
    assert e.experimental.planning_service.proposal(e.nid, e.scope, proposal["id"])["status"] == "REVIEW"


def test_mounted_real_roles_branch_scope_viewer_and_revocation(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch)
    path = e.base + "/planning/graphs"
    assert e.client.get(path).status_code == 401
    assert e.client.get(path, headers={"X-Session-Token": "invalid", "X-Branch-ID": e.branch}).status_code == 401
    assert e.client.get(path, headers={"X-Session-Token": e.lead}).status_code == 400
    assert checked(e.client.get(path, headers=e.viewer_headers)) == {"items": []}
    assert e.client.post(path, headers=e.viewer_headers, json={"title": "Denied"}).status_code == 403
    graph, proposal = planning_proposal(e, headers=e.headers)
    assert proposal["created_by"] == e.lead and proposal["scope"] == e.scope
    approve = e.base + f"/review-inbox/planning/{proposal['id']}/approve"
    assert e.client.post(approve, headers=e.viewer_headers, json={"expected_version": 1}).status_code == 403
    other = {**e.headers, "X-Branch-ID": e.other_branch}
    assert e.client.get(path, headers=other).status_code == 403
    # Give the same actor genuine authority on branch B; branch A rows must
    # still not become visible or reviewable there.
    other_scope = AuthorizationScope(ScopeKind.BRANCH, e.workspace, e.nid, e.storyline, e.other_branch)
    e.authorization.assign_role(DomainRoleAssignment("other-" + e.role, e.lead, DomainRole.DOMAIN_LEAD,
                                                     ModalityDomain.NOVEL, other_scope, e.lead))
    assert checked(e.client.get(path, headers=other)) == {"items": []}
    assert e.client.get(path + "/" + graph["id"], headers=other).status_code == 404
    assert e.client.post(approve, headers=other, json={"expected_version": 1}).status_code == 404
    assert e.client.get(e.base.replace(e.nid, "foreign-project") + "/planning/graphs", headers=e.headers).status_code == 403
    e.authorization.revoke_role(e.role, e.lead)
    assert e.client.post(approve, headers=e.headers, json={"expected_version": 1}).status_code == 403
    assert e.experimental.planning_service.proposal(e.nid, e.scope, proposal["id"])["version"] == 1
    e.sessions.revoke(e.lead)
    assert e.client.get(path, headers=other).status_code == 401


def test_mounted_batch_rechecks_real_revoked_role_between_items(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch)
    proposals = [planning_proposal(e, headers=e.headers, title=f"Choice {i}")[1] for i in range(2)]
    original_review = e.experimental.planning_service.review
    calls = []
    def review_then_revoke(*args, **kwargs):
        result = original_review(*args, **kwargs)
        calls.append(result["id"])
        e.authorization.revoke_role(e.role, e.lead)
        return result
    monkeypatch.setattr(e.experimental.planning_service, "review", review_then_revoke)
    receipt = checked(e.client.post(e.base + "/review-inbox/batch", headers=e.headers, json={"items": [
        {"domain": "planning", "id": row["id"], "action": "reject", "expected_version": 1} for row in proposals
    ]}))
    assert receipt["status"] == "PARTIAL" and receipt["results"][1]["code"] == "HTTP_403"
    assert calls == [proposals[0]["id"]]
    assert [e.experimental.planning_service.proposal(e.nid, e.scope, row["id"])["status"] for row in proposals] == ["REJECTED", "REVIEW"]


def test_mounted_branch_read_access_preserves_authorized_inbox(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch)
    _, proposal = planning_proposal(e, headers=e.headers)
    for path in READ_PATHS:
        response = e.client.get(e.base + "/" + path, headers=e.viewer_headers)
        assert response.status_code == 200, (path, response.text)
    inbox = checked(e.client.get(e.base + "/review-inbox", headers=e.viewer_headers))
    assert proposal["id"] in {row["id"] for row in inbox["items"]}
    assert {"domain": "legacy_media", "reason": "ORIGINAL_DOMAIN_ACCESS_REQUIRED"} in inbox["unavailable"]
    assert not any(row["domain"] == "legacy_media" for row in inbox["items"])


def legacy_plan(e, scope, actor="local-author"):
    return e.creation.save_record(e.nid, scope, actor, WorkbenchRecordIn(
        kind="STYLE", title="Measured prose", instructions="Use precise language.",
    ))


def queued_screenplay(e, branch=None):
    """Create real legacy image/video queues without executing any provider."""
    screen = e.screenplays.create(e.nid, "Review screenplay", branch_id=branch)
    sid = screen["id"]
    for method in ("approve", "plan_shots", "approve_shots", "plan_storyboard",
                   "approve_storyboard", "plan_assets", "approve_assets"):
        screen = getattr(e.screenplays, method)(e.nid, sid, screen["edit_version"])
    screen = e.screenplays.create_asset_tasks(e.nid, sid)
    screen = e.screenplays.plan_transitions(e.nid, sid, screen["edit_version"])
    for transition in screen["transitions"]:
        screen = e.screenplays.save_motion_prompt(e.nid, sid, transition["id"], "Hold the frame, then cut.")
    return e.screenplays.create_motion_tasks(e.nid, sid)


def workflow_waiting(e, headers, branch=None):
    definition = checked(e.client.post(e.prefix + "/workflows", headers=headers, json={
        "novel_id": e.nid, "branch_id": branch, "title": "Human review contract",
        "nodes": [{"id": "human", "type": "manual_approval", "name": "Review"}],
    }), 201)
    run = checked(e.client.post(e.prefix + f"/workflows/{definition['id']}/runs", headers=headers, json={}), 202)
    assert run["node_states"]["human"]["status"] == "WAITING_APPROVAL"
    return run


def test_mounted_legacy_inbox_projects_real_queues_and_delegates_reviews(mounted):
    e = mounted
    from app.services.audiobook_service import AudiobookService
    e.sessions.register("owner", SessionContext("owner-session", "owner-client", "local-author", "local-workspace"))
    e.sessions.register("other-owner", SessionContext("other-session", "other-client", "other-author", "local-workspace"))
    headers = {"X-Session-Token": "owner"}
    other_headers = {"X-Session-Token": "other-owner"}
    other_scope = {"mode": "collaboration", "novel_id": e.nid, "workspace_id": "foreign-workspace",
                   "storyline_id": "foreign-storyline", "branch_id": "foreign-branch"}
    plan = legacy_plan(e, e.scope)
    hidden_plan = legacy_plan(e, other_scope)
    imported = e.imports.ensure_pending(e.nid, {"characters": [{"name": "Reviewer candidate"}]}, permission_context=e.scope)
    hidden_import = e.imports.ensure_pending(e.nid, {"characters": [{"name": "Private candidate"}]}, permission_context=other_scope)
    pending = e.canon.save_pending({"id": str(uuid4()), "novel_id": e.nid, "status": "PENDING",
                                    "proposals": [{"fact_key": "gate", "fact_value": "Closed"}]})
    evidence_id, proposal_id = str(uuid4()), str(uuid4())
    # Register before creation so cleanup also covers a partially failed setup.
    e.lore_cleanup["evidence"].append(evidence_id)
    e.lore_cleanup["proposals"].append(proposal_id)
    evidence = e.lore.create_evidence({"id": evidence_id, "novel_id": e.nid, "source_type": "USER_ACTION",
                                     "source_id": "mounted-fixture", "locator": {}, "content_hash": "a" * 64,
                                     "privacy": "LOCAL_ONLY"})
    lore = e.lore.create_proposal({"id": proposal_id, "novel_id": e.nid, "proposal_type": "WORLD_RULE",
                                   "payload": {"rule": "The gate opens at dawn"}},
                                  [{"evidence_id": evidence["id"], "relevance": "PRIMARY"}])
    # Two chapters provide a real transition and therefore a video task.
    e.chapters.create(e.nid, {"title": "Inside the city", "content": "The road continued."})
    screenplay = queued_screenplay(e)
    hidden_screenplay = queued_screenplay(e, "foreign-branch")
    audio = AudiobookService(e.audio, e.assets).queue(e.nid, e.chapter, {}, [])
    agent = checked(e.client.post(e.prefix + "/agent-jobs", headers=headers, json={
        "agent_id": "planner", "novel_id": e.nid, "chapter": 1,
    }), 202)
    validated = checked(e.client.post(e.prefix + f"/agent-jobs/{agent['id']}/execute", headers=headers))
    assert validated["status"] == "VALIDATED" and not validated["model_called"]
    hidden_agent = checked(e.client.post(e.prefix + "/agent-jobs", headers=other_headers, json={
        "agent_id": "planner", "novel_id": e.nid, "chapter": 1,
    }), 202)
    run = workflow_waiting(e, headers)
    hidden_run = workflow_waiting(e, other_headers)
    gate = e.capabilities.evaluate_release_gate(e.nid, {})
    exported = e.exports.create(e.nid, "json", permission_context={**e.scope, "actor_id": "local-author"})
    # This is an actual bounded local export, so wait for its worker before
    # taking the snapshot and testing projection stability.
    for future in tuple(e.exports._futures.values()):
        future.result(timeout=10)
    inbox = checked(e.client.get(e.base + "/review-inbox", headers=headers))
    rows = inbox["items"]
    domains = {r["domain"] for r in rows}
    assert domains == {"legacy_planning", "legacy_import", "legacy_canon", "legacy_world_rule",
                       "legacy_media", "legacy_agent", "legacy_workflow", "export_release_gate"}
    ids = {row["id"] for row in rows}
    assert {plan["id"], imported["id"], pending["id"], lore["id"], audio["id"], agent["id"],
            run["id"] + ":human", gate["id"], exported["id"]} <= ids
    assert not {hidden_plan["id"], hidden_import["id"], hidden_agent["id"], hidden_run["id"] + ":human"} & ids
    media = [row for row in rows if row["domain"] == "legacy_media"]
    assert {row["preview"]["kind"] for row in media} == {"IMAGE", "VIDEO", "AUDIO"}
    assert any(screenplay["id"] in row["id"] for row in media)
    assert all(hidden_screenplay["id"] not in row["id"] for row in media)
    assert all(row["scope"] == e.scope and row["novel_id"] == e.nid and row["source_hash"] for row in rows)
    assert all(not row["batch_safe"] for row in rows)
    before = (e.chapters.list(e.nid), e.canon.list(e.nid))
    for domain, item in (("legacy_planning", plan), ("legacy_workflow", run)):
        item_id = item["id"] + (":human" if domain == "legacy_workflow" else "")
        current = next(row for row in rows if row["id"] == item_id)
        result = checked(e.client.post(e.base + f"/review-inbox/{domain}/{item_id}/approve",
                                       headers=headers, json={"expected_version": current["version"]}))
        if domain == "legacy_planning":
            assert result["status"] == "APPROVED"
            assert e.creation.get_record(e.nid, e.scope, item_id)["status"] == "APPROVED"
        else:
            assert result["status"] == "SUCCEEDED"
            assert e.capabilities.get_workflow_run(run["id"])["node_states"]["human"]["output"]["approved_by"] == "local-author"
    # Unversioned/evidence-selecting legacy domains remain read-only; the Inbox
    # must not invent an approval input or bypass their original detail flow.
    for domain in ("legacy_import", "legacy_canon", "legacy_world_rule", "legacy_media", "legacy_agent", "export_release_gate"):
        row = next(r for r in rows if r["domain"] == domain)
        assert row["allowed_actions"] == []
        assert e.client.post(e.base + f"/review-inbox/{domain}/{row['id']}/approve", headers=headers,
                             json={"expected_version": row["version"]}).status_code == 422
    assert (e.chapters.list(e.nid), e.canon.list(e.nid)) == before


def test_mounted_legacy_branch_queues_do_not_leak_other_branches(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch)
    local_plan = legacy_plan(e, {"mode": "local", "novel_id": e.nid})
    own_plan = legacy_plan(e, e.scope, e.lead)
    other_scope = {**e.scope, "branch_id": e.other_branch}
    other_plan = legacy_plan(e, other_scope, e.lead)
    own_import = e.imports.ensure_pending(e.nid, {"characters": [{"name": "Own"}]}, permission_context=e.scope)
    other_import = e.imports.ensure_pending(e.nid, {"characters": [{"name": "Other"}]}, permission_context=other_scope)
    for domain, own_id, hidden in (
        ("legacy_planning", own_plan["id"], {local_plan["id"], other_plan["id"]}),
        ("legacy_import", own_import["id"], {other_import["id"]}),
    ):
        rows = checked(e.client.get(e.base + "/review-inbox", headers=e.headers, params={"domain": domain}))["items"]
        assert {row["id"] for row in rows} == {own_id}
        for item_id in hidden:
            assert e.client.post(e.base + f"/review-inbox/{domain}/{item_id}/approve", headers=e.headers,
                                 json={"expected_version": 1}).status_code == 404
    for domain in ("legacy_canon", "legacy_world_rule"):
        result = checked(e.client.get(e.base + "/review-inbox", headers=e.headers, params={"domain": domain}))
        assert result["items"] == [] and result["unavailable"][0]["domain"] == domain
    approved = checked(e.client.post(e.base + f"/review-inbox/legacy_planning/{own_plan['id']}/approve",
                                     headers=e.headers, json={"expected_version": 1}))
    assert approved["actor_id"] == e.lead and approved["scope"] == e.scope

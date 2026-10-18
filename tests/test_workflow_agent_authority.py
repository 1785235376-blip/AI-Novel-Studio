"""Mounted workflow execution uses real authority and a no-network model node."""
from __future__ import annotations

import json
import threading
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import workflow_api
from app.actor_context import SessionContext
from app.authorization import AuthorizationScope, DomainRole, DomainRoleAssignment, ModalityDomain, ScopeKind
from app.collaboration import Branch, Storyline, Workspace
from app.dependencies import (
    agent_job_service, authorization_service, chapter_service, collaboration_scope_service,
    identity_service, novel_service, trusted_session_resolver,
)
from app.identity import IdentityStatus, User, WorkspaceMembership
from app.main import app
from app.model_runtime import TextGenerationResponse, TextModelNodeOutput


@pytest.fixture
def workflow_execution(monkeypatch):
    client = TestClient(app)
    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    calls = []
    control = SimpleNamespace(before_dispatch=None)
    original_run = agent_job_service._run_started

    def delayed_run(job_id, check_authority):
        started.set()
        try:
            assert release.wait(10), "test did not release worker"
            return original_run(job_id, check_authority)
        finally:
            finished.set()

    class NoNetworkNode:
        def execute(self, node_input):
            request = node_input.request
            if control.before_dispatch is not None:
                callback, control.before_dispatch = control.before_dispatch, None
                callback()
            # Real providers also invoke the final dispatch fence at the send boundary.
            request.dispatch_guard()
            calls.append(request.job_id)
            job = agent_job_service.get(request.job_id)
            result = {"schema": job["output_schema"], "agent_id": job["agent_id"],
                      "context_hash": job["context_hash"], "summary": "Synthetic route result",
                      "proposals": [], "findings": []}
            text = json.dumps(result)
            response = TextGenerationResponse(text, "completed", "deepseek", "deepseek-chat",
                                              execution_mode="mock_standin")
            return TextModelNodeOutput(text, response, request.job_id)

    monkeypatch.setattr(agent_job_service, "_run_started", delayed_run)
    monkeypatch.setattr(agent_job_service.runtime, "prepare_text_route", lambda *_: NoNetworkNode())

    def create(scoped=True):
        uid = str(uuid4())
        token, actor_id, workspace_id = "workflow-token-" + uid, "workflow-owner-" + uid, "workflow-space-" + uid
        session = SessionContext("session-" + uid, "workflow-test", actor_id, workspace_id)
        trusted_session_resolver.register(token, session)
        headers = {"X-Session-Token": token}
        novel = novel_service.create({"title": "Workflow authority " + uid})
        nid = novel["id"]
        chapter_service.create(nid, {"title": "Synthetic chapter", "content": "Only synthetic test source."})
        branch_id, role_id = None, None
        if scoped:
            storyline_id, branch_id, role_id = "story-" + uid, "branch-" + uid, "role-" + uid
            collaboration_scope_service.create_workspace(Workspace(workspace_id, "Workflow test"))
            collaboration_scope_service.link_project(workspace_id, nid)
            collaboration_scope_service.create_storyline(Storyline(storyline_id, workspace_id, nid, "Main"))
            collaboration_scope_service.create_branch(Branch(branch_id, workspace_id, nid, storyline_id, "main"))
            identity_service.create_user(User(actor_id, "Workflow owner"))
            identity_service.add_membership(WorkspaceMembership("membership-" + uid, actor_id, workspace_id))
            scope = AuthorizationScope(ScopeKind.BRANCH, workspace_id, nid, storyline_id, branch_id)
            authorization_service.assign_role(DomainRoleAssignment(role_id, actor_id, DomainRole.DOMAIN_LEAD,
                                                                    ModalityDomain.NOVEL, scope, actor_id))
        definition = client.post("/api/workflows", headers=headers, json={
            "novel_id": nid, "branch_id": branch_id, "title": "Synthetic agent route",
            "nodes": [{"id": "agent", "type": "agent_task", "name": "Writer"},
                      {"id": "after", "type": "checkpoint", "name": "After"}],
            "edges": [{"source": "agent", "target": "after"}],
        })
        assert definition.status_code == 201, definition.text
        response = client.post(f"/api/workflows/{definition.json()['id']}/runs", headers=headers, json={})
        assert response.status_code == 202, response.text
        run_id = response.json()["id"]
        triggered = client.post(f"/api/workflow-runs/{run_id}/nodes/agent/trigger-agent", headers=headers)
        assert triggered.status_code == 200, triggered.text
        return SimpleNamespace(client=client, token=token, headers=headers, actor_id=actor_id,
                               workspace_id=workspace_id, role_id=role_id, session=session,
                               nid=nid, branch_id=branch_id, run_id=run_id,
                               workflow_id=definition.json()["id"], title=novel["title"],
                               url=f"/api/agent-queue/{run_id}/agent", calls=calls)

    def dispatch(rig):
        started.clear()
        release.clear()
        finished.clear()
        response = client.post(rig.url + "/execute", headers=rig.headers, json={
            "chapter": 1, "provider_id": "deepseek", "model_id": "deepseek-chat",
        })
        assert response.status_code == 202, response.text
        assert started.wait(5), "worker did not start"
        rig.job_id = response.json()["node_states"]["agent"]["output"]["agent_job_id"]
        return response.json()

    def finish(rig):
        release.set()
        assert finished.wait(10), "worker did not finish"
        return agent_job_service.get(rig.job_id)

    try:
        yield SimpleNamespace(create=create, dispatch=dispatch, finish=finish, control=control)
    finally:
        release.set()
        if started.is_set():
            assert finished.wait(10), "worker leaked beyond test"


@pytest.mark.parametrize("scoped", [False, True])
def test_mounted_workflow_agent_executes_for_current_owner(workflow_execution, scoped):
    rig = workflow_execution.create(scoped)
    linked = workflow_execution.dispatch(rig)
    assert linked["status"] == "RUNNING"
    assert linked["node_states"]["after"]["status"] == "PENDING"
    job = workflow_execution.finish(rig)
    assert job["status"] == "COMPLETED", job
    assert job["model_called"] is False
    assert rig.calls == [job["id"]]
    assert job["owner"] == {"actor_id": rig.actor_id, "workspace_id": rig.workspace_id}
    assert job["branch_id"] == rig.branch_id
    synced = rig.client.post(rig.url + "/sync", headers=rig.headers)
    assert synced.status_code == 200, synced.text
    assert synced.json()["status"] == "SUCCEEDED"
    receipt = synced.json()["node_states"]["agent"]["output"]
    assert receipt["execution"] == "COMPLETED"
    assert receipt["result"]["agent_job_id"] == job["id"]
    assert receipt["result"]["applied"] is False


def _update_run(rig, **changes):
    record = workflow_api.service.get_workflow_run(rig.run_id)
    return workflow_api.service._update("workflow_runs", rig.run_id, changes, novel_id=rig.nid,
                                       expected_version=record["version"], action="TEST_CHANGE", target_type="WorkflowRun")


def _grant_role(rig):
    branch = collaboration_scope_service.repository.get("branches", rig.branch_id)
    scope = AuthorizationScope(ScopeKind.BRANCH, rig.workspace_id, rig.nid, branch["storyline_id"], rig.branch_id)
    authorization_service.assign_role(DomainRoleAssignment("restored-" + str(uuid4()), rig.actor_id,
                                                         DomainRole.DOMAIN_LEAD, ModalityDomain.NOVEL,
                                                         scope, rig.actor_id))


@pytest.mark.parametrize("revocation", ["session", "session_rebound", "membership", "role"])
def test_mounted_workflow_agent_rechecks_real_authority_before_dispatch(workflow_execution, revocation):
    rig = workflow_execution.create()
    workflow_execution.dispatch(rig)
    if revocation == "session":
        trusted_session_resolver.revoke(rig.token)
    elif revocation == "session_rebound":
        trusted_session_resolver.register(rig.token, rig.session)
    elif revocation == "membership":
        identity_service.set_membership_status(rig.actor_id, rig.workspace_id, IdentityStatus.INACTIVE)
    else:
        authorization_service.revoke_role(rig.role_id, rig.actor_id)
    job = workflow_execution.finish(rig)
    assert job["status"] == "FAILED"
    assert job["error_code"] == "AGENT_PERMISSION_REVOKED"
    assert rig.calls == []
    assert workflow_api.service.get_workflow_run(rig.run_id)["node_states"]["after"]["status"] == "PENDING"
    # Recover only by an explicit owner action after real access is restored.
    trusted_session_resolver.register(rig.token, rig.session)
    if revocation == "membership":
        identity_service.set_membership_status(rig.actor_id, rig.workspace_id, IdentityStatus.ACTIVE)
    if revocation == "role":
        _grant_role(rig)
    synced = rig.client.post(rig.url + "/sync", headers=rig.headers)
    assert synced.status_code == 200, synced.text
    assert synced.json()["status"] == "FAILED"
    assert synced.json()["node_states"]["agent"]["error"]["message"] == "AGENT_PERMISSION_REVOKED"
    retried = rig.client.post(f"/api/workflow-runs/{rig.run_id}/retry", headers=rig.headers)
    assert retried.status_code == 202, retried.text
    assert retried.json()["project_incarnation"] == synced.json()["project_incarnation"]
    assert retried.json()["status"] == "WAITING_APPROVAL"
    assert retried.json()["node_states"]["agent"]["output"]["execution"] == "DEFERRED"
    assert rig.calls == []


@pytest.mark.parametrize("change", ["pause", "claim_replaced", "job_relinked", "owner", "branch", "project", "definition", "deadline"])
def test_mounted_workflow_agent_rejects_stale_workflow_claim(workflow_execution, change):
    rig = workflow_execution.create()
    linked = workflow_execution.dispatch(rig)
    if change == "pause":
        response = rig.client.post(f"/api/workflow-runs/{rig.run_id}/pause", headers=rig.headers)
        assert response.status_code == 200, response.text
    elif change in {"claim_replaced", "job_relinked"}:
        states = linked["node_states"]
        states["agent"]["output"]["claimed_at" if change == "claim_replaced" else "agent_job_id"] = "replacement-claim"
        _update_run(rig, node_states=states)
    elif change == "owner":
        _update_run(rig, owner={"actor_id": "someone-else", "workspace_id": rig.workspace_id})
    elif change == "branch":
        _update_run(rig, branch_id="another-branch")
    elif change == "project":
        _update_run(rig, novel_id="another-project")
    elif change == "definition":
        definition = linked["definition_snapshot"]
        definition["nodes"][0]["config"] = {"agent_role": "editor"}
        _update_run(rig, definition_snapshot=definition)
    else:
        _update_run(rig, started_at="2000-01-01T00:00:00+00:00")
    job = workflow_execution.finish(rig)
    assert job["status"] == "FAILED"
    assert job["error_code"] == "AGENT_PERMISSION_REVOKED"
    assert rig.calls == []
    current = workflow_api.service.get_workflow_run(rig.run_id)
    assert current["node_states"]["after"]["status"] == "PENDING"
    assert current["node_states"]["agent"]["status"] == "WORKING"


def test_mounted_workflow_cancel_blocks_late_worker_and_preserves_receipt(workflow_execution):
    rig = workflow_execution.create()
    workflow_execution.dispatch(rig)
    cancelled = rig.client.post(f"/api/workflow-runs/{rig.run_id}/cancel", headers=rig.headers)
    assert cancelled.status_code == 200
    job = workflow_execution.finish(rig)
    assert job["status"] == "CANCELLED"
    assert rig.calls == []
    assert workflow_api.service.get_workflow_run(rig.run_id)["status"] == "CANCELLED"
    assert rig.client.post(rig.url + "/sync", headers=rig.headers).status_code == 400


def test_mounted_workflow_rechecks_real_role_at_provider_send(workflow_execution):
    rig = workflow_execution.create()
    workflow_execution.control.before_dispatch = lambda: authorization_service.revoke_role(rig.role_id, rig.actor_id)
    workflow_execution.dispatch(rig)
    job = workflow_execution.finish(rig)
    assert job["status"] == "FAILED"
    assert job["error_code"] == "AGENT_PERMISSION_REVOKED"
    assert rig.calls == []


@pytest.mark.parametrize("action", ["execute", "retry"])
def test_legacy_unbound_claim_is_preserved_and_rejected_after_restart(workflow_execution, monkeypatch, action):
    from app.services.v1_capability_service import V1CapabilityService

    rig = workflow_execution.create()
    original = workflow_api.service
    records = original._read("workflow_runs")
    old = next(row for row in records if row["id"] == rig.run_id)
    old.pop("project_incarnation")
    if action == "retry":
        old["status"] = "FAILED"
    original._write("workflow_runs", records)
    restarted = V1CapabilityService(original.root, original.novels, original.chapters, original.assets,
                                    original.exports, original.project_root)
    monkeypatch.setattr(workflow_api, "service", restarted)
    before = restarted.get_workflow_run(rig.run_id)
    jobs_before = {job["id"] for job in agent_job_service.generations.load_all()}
    if action == "execute":
        response = rig.client.post(rig.url + "/execute", headers=rig.headers,
                                   json={"chapter": 1, "provider_id": "deepseek", "model_id": "deepseek-chat"})
    else:
        response = rig.client.post(f"/api/workflow-runs/{rig.run_id}/retry", headers=rig.headers)
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "WORKFLOW_EXECUTION_PROVENANCE_REQUIRED"
    assert "Create a new workflow run" in response.json()["detail"]["message"]
    assert restarted.get_workflow_run(rig.run_id) == before
    assert {job["id"] for job in agent_job_service.generations.load_all()} == jobs_before
    assert rig.calls == []


def test_bound_claim_can_execute_after_workflow_store_restart(workflow_execution, monkeypatch):
    from app.services.v1_capability_service import V1CapabilityService

    rig = workflow_execution.create()
    original = workflow_api.service
    monkeypatch.setattr(workflow_api, "service", V1CapabilityService(original.root, original.novels,
                        original.chapters, original.assets, original.exports, original.project_root))
    workflow_execution.dispatch(rig)
    job = workflow_execution.finish(rig)
    assert job["status"] == "COMPLETED", job
    assert rig.calls == [job["id"]]


def test_mounted_workflow_owner_is_required_before_claim(workflow_execution):
    rig = workflow_execution.create()
    other_token = "other-" + str(uuid4())
    trusted_session_resolver.register(other_token, SessionContext("other-session", "client", "other-owner", rig.workspace_id))
    before = workflow_api.service.get_workflow_run(rig.run_id)
    body = {"chapter": 1, "provider_id": "deepseek", "model_id": "deepseek-chat"}
    assert rig.client.post(rig.url + "/execute", json=body).status_code == 401
    assert rig.client.post(rig.url + "/execute", headers={"X-Session-Token": other_token}, json=body).status_code == 403
    assert workflow_api.service.get_workflow_run(rig.run_id) == before
    assert rig.calls == []


def test_delete_recreate_blocks_active_claim_and_allows_explicit_new_run(workflow_execution):
    from app.experimental.api import creative_service

    rig = workflow_execution.create(scoped=False)
    original_run = workflow_api.service.get_workflow_run(rig.run_id)
    original_incarnation = original_run["project_incarnation"]
    assert original_incarnation == creative_service.store.incarnation(rig.nid)

    def recreate_at_send():
        assert agent_job_service.get(rig.job_id)["status"] == "WORKING"
        novel_service.delete(rig.nid)
        replacement = novel_service.create({"title": rig.title})
        assert replacement["id"] == rig.nid
        chapter_service.create(rig.nid, {"title": "Synthetic chapter", "content": "Only synthetic test source."})

    workflow_execution.control.before_dispatch = recreate_at_send
    workflow_execution.dispatch(rig)
    try:
        job = workflow_execution.finish(rig)
    except KeyError:
        # PostgreSQL owns the job through the deleted novel FK; it must never
        # be recreated against the replacement project by a late callback.
        from app.config import settings
        assert settings.storage_backend == "postgres"
    else:
        assert job["status"] == "FAILED"
        assert job["error_code"] in {"AGENT_PERMISSION_REVOKED", "AGENT_JOB_CHANGED"}
    assert rig.calls == []
    assert workflow_api.service.get_workflow_run(rig.run_id)["project_incarnation"] == original_incarnation
    # The current record must not be rebound to a replacement incarnation.
    denied = rig.client.post(rig.url + "/execute", headers=rig.headers,
                             json={"chapter": 1, "provider_id": "deepseek", "model_id": "deepseek-chat"})
    assert denied.status_code in {404, 409}, denied.text
    fresh = rig.client.post(f"/api/workflows/{rig.workflow_id}/runs", headers=rig.headers, json={})
    assert fresh.status_code == 202, fresh.text
    assert fresh.json()["project_incarnation"] != original_incarnation
    assert fresh.json()["project_incarnation"] == creative_service.store.incarnation(rig.nid)
    rig.run_id = fresh.json()["id"]
    rig.url = f"/api/agent-queue/{rig.run_id}/agent"
    assert rig.client.post(f"/api/workflow-runs/{rig.run_id}/nodes/agent/trigger-agent", headers=rig.headers).status_code == 200
    workflow_execution.dispatch(rig)
    job = workflow_execution.finish(rig)
    assert job["status"] == "COMPLETED", job
    assert rig.calls == [job["id"]]


@pytest.mark.parametrize("field", ["branch_id", "owner"])
def test_mounted_workflow_job_cannot_be_retargeted_even_with_branch_access(workflow_execution, field):
    from app.api import _agent_job_actor_for_record

    rig = workflow_execution.create()
    workflow_execution.dispatch(rig)
    branch = collaboration_scope_service.repository.get("branches", rig.branch_id)
    other_branch = "other-" + str(uuid4())
    collaboration_scope_service.create_branch(Branch(other_branch, rig.workspace_id, rig.nid,
                                                       branch["storyline_id"], "Other"))
    other_scope = AuthorizationScope(ScopeKind.BRANCH, rig.workspace_id, rig.nid, branch["storyline_id"], other_branch)
    authorization_service.assign_role(DomainRoleAssignment("other-role-" + str(uuid4()), rig.actor_id,
                                    DomainRole.DOMAIN_LEAD, ModalityDomain.NOVEL, other_scope, rig.actor_id))
    job = agent_job_service.get(rig.job_id)
    job[field] = other_branch if field == "branch_id" else {"actor_id": "other-owner", "workspace_id": rig.workspace_id}
    agent_job_service.generations.save(job)
    # Access to both branches is legitimate. It does not authorize changing
    # the execution request or transferring an already-claimed workflow job.
    assert _agent_job_actor_for_record(rig.token, job, "domain.write").actor_id == rig.actor_id
    failed = workflow_execution.finish(rig)
    assert failed["status"] == "FAILED"
    assert failed["error_code"] == "AGENT_PERMISSION_REVOKED"
    assert rig.calls == []


def test_mounted_workflow_start_failure_keeps_original_failure_transition(workflow_execution, monkeypatch):
    rig = workflow_execution.create()

    def cannot_start(*_args):
        raise RuntimeError("synthetic worker start failure")

    monkeypatch.setattr(agent_job_service, "start", cannot_start)
    response = rig.client.post(rig.url + "/execute", headers=rig.headers,
                               json={"chapter": 1, "provider_id": "deepseek", "model_id": "deepseek-chat"})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "AGENT_START_FAILED"
    current = workflow_api.service.get_workflow_run(rig.run_id)
    state = current["node_states"]["agent"]
    assert current["status"] == "FAILED"
    assert state["status"] == "FAILED"
    assert state["output"]["execution"] == "FAILED"
    assert state["error"]["message"] == "AGENT_START_FAILED"
    assert current["node_states"]["after"]["status"] == "PENDING"
    assert rig.calls == []

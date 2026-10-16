"""Mounted M4 routes retain original trusted-session, scope and review owners."""
from copy import deepcopy
from uuid import uuid4

import pytest

from app.actor_context import SessionContext
from test_r3_mounted_contracts import checked, mounted, prefix, scoped
from test_v2_independent_workspace_api import client
from test_v2_creative_graph_api import graph_client, create, admit as api_admit
from test_v2_ai_execution_runtime import (FLAGS, configure, cleanup, definition, spy_transport, wait_job, generation_delta, owned_jobs)


pytestmark = pytest.mark.filterwarnings("error::pytest.PytestUnhandledThreadExceptionWarning")


@pytest.fixture
def ai_client(graph_client, monkeypatch):
    e = configure(graph_client, monkeypatch, graph_client.graphs)
    e.host = "m4-host-" + uuid4().hex
    e.sessions.register(e.host, SessionContext("session-" + e.host, "client-" + e.host, e.host, "m4-development-workspace"))
    e.headers = {"X-Session-Token": e.host}
    yield e
    cleanup(e)


def ready(e, headers=None):
    headers = e.headers if headers is None else headers
    graph = create(e, headers=headers, value=definition(text="private-m4-source"))
    row = api_admit(e, graph, headers=headers)
    path = e.studio_base + "/graph-runs/" + row["id"]
    row = checked(e.client.post(path + "/execute", headers=headers, json={"expected_version": row["version"]}))
    row = checked(e.client.post(path + "/model/preview", headers=headers, json={
        "expected_version": row["version"], "route_id": e.route["route_id"], "allow_synthetic": True}))
    return row, path


def body(row):
    return {"expected_version": row["version"], "reviewed_preview_digest": row["model_runtime"]["preview"]["preview_digest"]}


def test_mounted_real_worker_review_preserves_existing_chapter_and_canon(ai_client, monkeypatch):
    e = ai_client; spy_transport(e, monkeypatch)
    before_chapter, before_canon = deepcopy(e.chapters.get(e.chapter["id"])), deepcopy(e.canon.list(e.nid))
    response = e.client.get(e.graph_base + "/model-capabilities", headers=e.headers)
    assert response.headers["cache-control"] == "no-store" and response.headers["x-content-type-options"] == "nosniff"
    assert checked(response)["local_only"]
    row, path = ready(e)
    response = e.client.post(path + "/model/dispatch", headers=e.headers, json=body(row))
    admitted = checked(response)
    job = e.manager.get(admitted["model_runtime"]["execution"]["job_id"]); wait_job(e, job)
    waiting = checked(e.client.post(path + "/model/refresh", headers=e.headers, json={"expected_version": admitted["version"]}))
    assert waiting["status"] == "WAITING_APPROVAL" and waiting["review"]["draft"]["origin"] == "MODEL_PROPOSAL"
    assert e.client.post(path + "/approve", headers=e.headers, json={"expected_version": waiting["version"],
        "node_id": "Review", "reviewed_output_digest": "0" * 64}).status_code == 409
    done = checked(e.client.post(path + "/approve", headers=e.headers, json={"expected_version": waiting["version"],
        "node_id": "Review", "reviewed_output_digest": waiting["review"]["output_digest"]}))
    assert done["status"] == "SUCCEEDED" and done["reviewed"] and not done["applied"]
    assert e.chapters.get(e.chapter["id"]) == before_chapter and e.canon.list(e.nid) == before_canon
    assert len(e.calls) == len(generation_delta(e)) == 1
    assert job.chapter_id is None


@pytest.mark.parametrize("flag", [*FLAGS.split(","), "acceptance"])
def test_every_model_route_requires_all_flags_and_acceptance_override(ai_client, monkeypatch, flag):
    e = ai_client
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", FLAGS if flag == "acceptance" else ",".join(x for x in FLAGS.split(",") if x != flag))
    monkeypatch.setenv("V1_ACCEPTANCE_MODE", "true" if flag == "acceptance" else "")
    for method, suffix, payload in [
        ("GET", "/graphs/model-capabilities", None),
        ("POST", "/graph-runs/missing/model/preview", {"expected_version": 1, "route_id": "a" * 64}),
        ("POST", "/graph-runs/missing/model/dispatch", {"expected_version": 1, "reviewed_preview_digest": "a" * 64}),
        ("POST", "/graph-runs/missing/model/refresh", {"expected_version": 1})]:
        response = e.client.request(method, e.studio_base + suffix, headers=e.headers, json=payload)
        assert response.status_code == 404, (suffix, response.text)
        assert response.json()["detail"]["code"] == "EXPERIMENTAL_FEATURE_DISABLED"
    assert not owned_jobs(e) and not generation_delta(e)


def test_model_routes_require_real_host_session_in_local_mode(ai_client):
    e = ai_client
    for headers in ({}, {"X-Session-Token": "not-trusted"}):
        response = e.client.get(e.graph_base + "/model-capabilities", headers=headers)
        assert response.status_code == 401
        assert response.json()["detail"]["code"] == ("INVALID_SESSION" if headers else "SESSION_REQUIRED")
    assert checked(e.client.get(e.graph_base + "/catalog"))["capabilities"]["chapter_required"] is False
    assert not generation_delta(e)


def test_mounted_exact_preview_cas_unknown_fields_and_no_output_injection(ai_client, monkeypatch):
    e = ai_client; spy_transport(e, monkeypatch)
    row, path = ready(e)
    for payload, status in (({**body(row), "reviewed_preview_digest": "0" * 64}, 409),
                            ({**body(row), "expected_version": row["version"] - 1}, 409),
                            ({**body(row), "output": "caller-injected model output"}, 422),
                            ({**body(row), "allow_cloud_fallback": True}, 422)):
        response = e.client.post(path + "/model/dispatch", headers=e.headers, json=payload)
        assert response.status_code == status, response.text
        if status == 409:
            assert "private-m4-source" not in response.text and "project_incarnation" not in response.text
    assert not owned_jobs(e) and not e.calls and not generation_delta(e)


def test_collaboration_role_alone_never_grants_model_host_authority(ai_client, monkeypatch):
    e = scoped(ai_client, monkeypatch); spy_transport(e, monkeypatch)
    for headers, expected in ((e.headers, 403), (e.viewer_headers, 403), ({}, 401)):
        response = e.client.get(e.graph_base + "/model-capabilities", headers=headers)
        assert response.status_code == expected
    response = e.client.get(e.graph_base + "/model-capabilities", headers=e.headers)
    assert response.json()["detail"]["code"] == "LOCAL_AI_HOST_AUTHORITY_UNAVAILABLE"
    e.authorization.revoke_role(e.role, e.lead)
    assert e.client.get(e.graph_base + "/model-capabilities", headers=e.headers).status_code == 403
    assert not e.calls and not generation_delta(e)


@pytest.mark.parametrize("private_error", [False, True])
def test_late_host_revocation_masks_model_preview_and_private_errors(ai_client, monkeypatch, private_error):
    e = ai_client
    row, path = ready(e)
    original = e.models.preview
    def revoke(*args, **kwargs):
        result = original(*args, **kwargs)
        e.sessions.revoke(e.host)
        if private_error: raise ValueError("private-m4-provider-error")
        return result
    monkeypatch.setattr(e.models, "preview", revoke)
    response = e.client.post(path + "/model/preview", headers=e.headers, json={
        "expected_version": row["version"], "route_id": e.route["route_id"], "allow_synthetic": True})
    assert response.status_code == 401
    assert "private-m4-source" not in response.text and "private-m4-provider-error" not in response.text
    assert not owned_jobs(e)


def test_generic_generation_routes_cannot_read_cancel_retry_or_accept_graph_job(ai_client, monkeypatch):
    e = ai_client; monkeypatch.setattr(e.api, "jobs", e.manager)
    row, path = ready(e)
    admitted = checked(e.client.post(path + "/model/dispatch", headers=e.headers, json=body(row)))
    job = e.manager.get(admitted["model_runtime"]["execution"]["job_id"]); wait_job(e, job)
    for method, suffix in (("GET", ""), ("GET", "/events"), ("POST", "/cancel"),
                           ("POST", "/retry"), ("POST", "/accept"), ("POST", "/reject")):
        response = e.client.request(method, e.prefix + "/generation/" + job.id + suffix, headers=e.headers)
        assert response.status_code == 404, (suffix, response.text)
        assert job.output not in response.text and "private-m4-source" not in response.text
    assert job.status == "COMPLETED" and len(owned_jobs(e)) == 1


def test_re_registered_same_host_token_invalidates_inflight_original_job(ai_client, monkeypatch):
    e = ai_client; entered, release = spy_transport(e, monkeypatch, blocked=True)
    row, path = ready(e)
    admitted = checked(e.client.post(path + "/model/dispatch", headers=e.headers, json=body(row)))
    job = e.manager.get(admitted["model_runtime"]["execution"]["job_id"])
    try:
        assert entered.wait(3)
        e.sessions.register(e.host, SessionContext("session-" + e.host, "client-" + e.host,
            e.host, "m4-development-workspace"))
    finally: release.set()
    wait_job(e, job)
    assert job.status == "FAILED" and not job.output
    assert len(e.calls) == 1
    response = e.client.post(path + "/model/refresh", headers=e.headers, json={"expected_version": admitted["version"]})
    row = checked(response)
    assert row["review"] is None and row["status"] == "FAILED"


def test_schema_two_reads_require_current_host_and_block_forwarded_origin(ai_client):
    e = ai_client; row, path = ready(e)
    for target in (path, e.graph_base + "/" + row["graph_id"], e.graph_base,
                   e.graph_base + "/" + row["graph_id"] + "/runs"):
        assert e.client.get(target).status_code == 401
        for extra in ({"X-Forwarded-For": "127.0.0.1"}, {"Origin": "https://untrusted.invalid"}):
            response = e.client.get(target, headers={**e.headers, **extra})
            assert response.status_code == 403
            assert "private-m4-source" not in response.text


def test_unauthenticated_model_graph_mutations_do_not_commit_or_consume_versions(ai_client):
    e = ai_client
    empty = checked(e.client.get(e.graph_base, headers=e.headers))
    response = e.client.post(e.graph_base, json={"request_id": "no-host-create", "definition": definition()})
    assert response.status_code == 401
    assert checked(e.client.get(e.graph_base, headers=e.headers)) == empty
    row, path = ready(e)
    graph = checked(e.client.get(e.graph_base + "/" + row["graph_id"], headers=e.headers))
    routes = [
        ("PUT", e.graph_base + "/" + graph["id"], {"expected_version": graph["version"], "definition": definition(text="Unauthorized replacement")}),
        ("POST", e.graph_base + "/" + graph["id"] + "/preflight", {"expected_version": graph["version"]}),
        ("POST", e.graph_base + "/" + graph["id"] + "/runs", {"expected_graph_version": graph["version"], "request_id": "no-host-run", "reviewed_preflight_digest": "a" * 64}),
        *[("POST", path + "/" + suffix, {"expected_version": row["version"]}) for suffix in ("execute", "cancel", "approve")],
    ]
    for method, target, payload in routes:
        response = e.client.request(method, target, json=payload)
        assert response.status_code == 401, (target, response.text)
        assert checked(e.client.get(path, headers=e.headers)) == row
        assert checked(e.client.get(e.graph_base + "/" + graph["id"], headers=e.headers)) == graph
    assert not owned_jobs(e) and not generation_delta(e)


def test_upgrading_schema_one_to_model_graph_requires_host_before_save(ai_client):
    from test_v2_creative_graph_api import definition as original_definition
    e = ai_client
    graph = create(e, value=original_definition())
    response = e.client.put(e.graph_base + "/" + graph["id"], json={
        "expected_version": graph["version"], "definition": definition(text="Unauthorized model graph upgrade")})
    assert response.status_code == 401
    assert checked(e.client.get(e.graph_base + "/" + graph["id"], headers=e.headers)) == graph
    assert not owned_jobs(e) and not generation_delta(e)


def test_revoked_originating_host_masks_published_draft_and_blocks_approval(ai_client):
    e = ai_client
    row, path = ready(e)
    admitted = checked(e.client.post(path + "/model/dispatch", headers=e.headers, json=body(row)))
    job = e.manager.get(admitted["model_runtime"]["execution"]["job_id"]); wait_job(e, job)
    waiting = checked(e.client.post(path + "/model/refresh", headers=e.headers, json={"expected_version": admitted["version"]}))
    review = waiting["review"]
    e.sessions.revoke(e.host)
    e.sessions.register(e.host, SessionContext("renewed-" + e.host, "new-client-" + e.host,
        e.host, "m4-development-workspace"))
    visible = checked(e.client.get(path, headers=e.headers))
    assert visible["stale"] and visible["review"] is None
    assert all(value["output"] is None for value in visible["node_states"].values())
    response = e.client.post(path + "/approve", headers=e.headers, json={"expected_version": waiting["version"],
        "node_id": review["node_id"], "reviewed_output_digest": review["output_digest"]})
    assert response.status_code in {401, 409}
    assert job.output not in response.text and "private-m4-source" not in response.text


def test_original_broker_job_projection_redacts_graph_content(ai_client, monkeypatch):
    e = ai_client
    # The mounted router retains the original JobManager object. Rebind its
    # real job dictionary, leaving the original public-job route intact.
    monkeypatch.setattr(e.api.jobs, "jobs", e.manager.jobs)
    row, path = ready(e)
    admitted = checked(e.client.post(path + "/model/dispatch", headers=e.headers, json=body(row)))
    job = e.manager.get(admitted["model_runtime"]["execution"]["job_id"]); wait_job(e, job)
    ledger = next(entry for entry in e.broker.ledger(e.nid, job.scope, job.actor_id) if entry["job_id"] == job.id)
    response = e.client.get(e.base + "/model-broker/jobs/" + ledger["id"], headers=e.headers)
    value = checked(response)
    assert value["job"] == {"id": job.id, "status": "COMPLETED", "content_available": False}
    assert job.output not in response.text and "private-m4-source" not in response.text


def test_concurrent_hosted_upgrade_fences_unhosted_save_before_commit(ai_client, monkeypatch):
    from test_v2_creative_graph_api import definition as original_definition
    e = ai_client
    graph = create(e, value=original_definition())
    path = e.graph_base + "/" + graph["id"]
    original_save = e.graphs.save
    state = {"armed": True}
    def racing(*args, **kwargs):
        if state["armed"]:
            state["armed"] = False
            state["upgraded"] = checked(e.client.put(path, headers=e.headers, json={
                "expected_version": graph["version"], "definition": definition(text="Authorized concurrent model upgrade")}))
        return original_save(*args, **kwargs)
    monkeypatch.setattr(e.graphs, "save", racing)
    # The unhosted request was admitted against schema one, but guesses the
    # next version while another genuine hosted request upgrades it to two.
    response = e.client.put(path, json={"expected_version": graph["version"] + 1,
        "definition": original_definition("Unauthorized raced replacement")})
    assert response.status_code == 403, response.text
    assert state["upgraded"]["version"] == graph["version"] + 1
    assert checked(e.client.get(path, headers=e.headers)) == state["upgraded"]
    assert not owned_jobs(e) and not generation_delta(e)


def test_generic_cancel_cannot_signal_or_mutate_active_graph_job(ai_client, monkeypatch):
    e = ai_client
    monkeypatch.setattr(e.api, "jobs", e.manager)
    entered, release = spy_transport(e, monkeypatch, blocked=True)
    row, path = ready(e)
    admitted = checked(e.client.post(path + "/model/dispatch", headers=e.headers, json=body(row)))
    job = e.manager.get(admitted["model_runtime"]["execution"]["job_id"])
    try:
        assert entered.wait(3)
        before_job = deepcopy(job.public())
        before_saved = deepcopy(e.persistence.get(job.id))
        assert not job.cancelled.is_set() and job.status not in e.manager.terminal
        response = e.client.post(e.prefix + "/generation/" + job.id + "/cancel", headers=e.headers)
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "GENERATION_NOT_FOUND"
        assert not job.cancelled.is_set()
        assert job.public() == before_job and e.persistence.get(job.id) == before_saved
        assert checked(e.client.get(path, headers=e.headers)) == admitted
    finally:
        release.set()
    wait_job(e, job)
    assert job.status == "COMPLETED" and not job.cancelled.is_set()
    assert len(e.calls) == 1


def test_original_virtual_cancel_owner_runs_under_registration_lock_and_projects_after_unlock(ai_client, monkeypatch):
    e = ai_client
    owner = e.api.jobs
    calls = []
    identifiers = ["v1-virtual-a-" + uuid4().hex, "v1-virtual-b-" + uuid4().hex]
    class Item:
        def __init__(self, jid):
            self.id, self.status = jid, "GENERATING"
        def public(self):
            acquired = owner.lock.acquire(blocking=False)
            assert acquired, "Original cancellation result projection must run after registration lock release"
            owner.lock.release()
            return {"id": self.id, "status": self.status}
    items = {jid: Item(jid) for jid in identifiers}
    assert all(jid not in owner.jobs for jid in identifiers)
    def cancel(jid):
        acquired = owner.lock.acquire(blocking=False)
        if acquired:
            owner.lock.release()
        assert not acquired, "Original cancel owner must hold the original registration lock"
        calls.append(jid)
        items[jid].status = "CANCELLED"
        return items[jid]
    monkeypatch.setattr(owner, "cancel", cancel)
    monkeypatch.setattr(owner, "get", lambda *_: pytest.fail("Legacy virtual cancellation must reach its original owner without a new get prerequisite"))
    for jid in identifiers:
        assert checked(e.client.post(e.prefix + "/generation/" + jid + "/cancel")) == {
            "id": jid, "status": "CANCELLED"}
    assert calls == identifiers
    assert all(jid not in owner.jobs for jid in identifiers)

"""Mounted graph routes use original trusted authority and genuine persistence."""
import copy
from uuid import uuid4

import pytest
from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind

from test_r3_mounted_contracts import checked, mounted, prefix, scoped
from test_v2_independent_workspace_api import client, upload_body


@pytest.fixture
def graph_client(client, monkeypatch):
    e = client
    e.graphs = e.experimental.creative_graph_service
    monkeypatch.setattr(e.graphs, "store", e.studio.store)
    monkeypatch.setattr(e.graphs, "workspace", e.studio)
    e.graph_base = e.studio_base + "/graphs"
    return e


def definition(text="User-authored graph text", *, review=True):
    nodes = [
        {"id": "Input", "definition_id": "text_input", "parameters": {"text": text}},
        {"id": "Draft", "definition_id": "manual_transform", "parameters": {"result": "A human-authored revision."}},
    ]
    edges = [{"id": "Source", "source_node_id": "Input", "source_port": "text", "target_node_id": "Draft", "target_port": "text"}]
    if review:
        nodes.append({"id": "Review", "definition_id": "human_review", "parameters": {}})
        edges.append({"id": "Check", "source_node_id": "Draft", "source_port": "draft", "target_node_id": "Review", "target_port": "draft"})
    return {"title": "Independent local graph", "nodes": nodes, "edges": edges}


def create(e, *, headers=None, value=None, base=None):
    return checked(e.client.post(base or e.graph_base, headers=headers, json={
        "request_id": "api-" + uuid4().hex, "expected_version": 0,
        "definition": definition() if value is None else value}), 201)


def admit(e, row, headers=None, base=None):
    path = (base or e.graph_base) + "/" + row["id"]
    preflight = checked(e.client.post(path + "/preflight", headers=headers, json={"expected_version": row["version"]}))
    assert preflight["executable"] is True
    return checked(e.client.post(path + "/runs", headers=headers, json={
        "expected_graph_version": row["version"], "target_node_ids": [],
        "reviewed_preflight_digest": preflight["preflight_digest"], "request_id": "run-" + uuid4().hex}), 201)


def test_blank_project_graph_save_reopen_manual_review_keeps_chapters_empty(graph_client):
    e = graph_client
    project = checked(e.client.post(e.prefix + "/experimental/projects", json={"title": "Graph only", "id": "graph-only-" + uuid4().hex}), 201)
    nid = project["id"]
    base = e.prefix + f"/projects/{nid}/studio/graphs"
    try:
        assert checked(e.client.get(e.prefix + f"/novels/{nid}/chapters")) == []
        catalog = checked(e.client.get(base + "/catalog"))
        assert catalog["capabilities"]["chapter_required"] is False
        assert catalog["capabilities"]["model_execution"] is False
        row = create(e, base=base)
        assert row["version"] == 1
        response = e.client.get(base + "/" + row["id"])
        assert checked(response) == row
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
        run = admit(e, row, base=base)
        action = e.prefix + f"/projects/{nid}/studio/graph-runs/" + run["id"]
        assert run["status"] == "QUEUED"
        run = checked(e.client.post(action + "/execute", json={"expected_version": run["version"]}))
        assert run["status"] == "WAITING_APPROVAL" and run["review"]["node_id"] == "Review"
        assert run["model_called"] is False and run["external_calls"] == 0 and run["applied"] is False
        review = run["review"]
        run = checked(e.client.post(action + "/approve", json={"expected_version": run["version"],
            "node_id": review["node_id"], "reviewed_output_digest": review["output_digest"]}))
        assert run["status"] == "SUCCEEDED" and run["reviewed"] is True
        assert checked(e.client.get(action)) == run
        assert checked(e.client.get(base + f"/{row['id']}/runs"))["items"] == [run]
        assert checked(e.client.get(e.prefix + f"/novels/{nid}/chapters")) == []
    finally:
        if e.backend == "postgres":
            with e.store._connect() as connection:
                connection.execute("DELETE FROM experimental_scope_documents WHERE novel_id = %s", (nid,))
        e.novels.delete(nid)


@pytest.mark.parametrize("acceptance", [False, True])
def test_graph_routes_default_off_and_v1_override(graph_client, monkeypatch, acceptance):
    e = graph_client
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2" if acceptance else "")
    monkeypatch.setenv("V1_ACCEPTANCE_MODE", "true" if acceptance else "")
    for method, suffix, body in [
        ("GET", "/graphs/catalog", None), ("GET", "/graphs", None), ("GET", "/graphs/missing", None),
        ("POST", "/graphs", {"request_id": "create", "definition": {"title": "Blank"}}),
        ("PUT", "/graphs/missing", {"expected_version": 1, "definition": {"title": "Blank"}}),
        ("POST", "/graphs/missing/preflight", {"expected_version": 1}),
        ("GET", "/graphs/missing/runs", None),
        ("POST", "/graphs/missing/runs", {"expected_graph_version": 1, "reviewed_preflight_digest": "0" * 64, "request_id": "run"}),
        ("GET", "/graph-runs/missing", None),
        *[("POST", "/graph-runs/missing/" + action, {"expected_version": 1})
          for action in ("execute", "approve", "reject", "cancel", "pause", "resume")],
    ]:
        result = e.client.request(method, e.studio_base + suffix, json=body)
        assert result.status_code == 404, (method, suffix, result.text)
        assert result.json()["detail"]["code"] == "EXPERIMENTAL_FEATURE_DISABLED"


def test_graph_scoped_authority_actor_private_reads_and_exact_route_admission(graph_client, monkeypatch):
    e = scoped(graph_client, monkeypatch)
    assert e.client.get(e.graph_base).status_code == 401
    assert e.client.get(e.graph_base, headers={"X-Session-Token": e.lead}).status_code == 400
    row = create(e, headers=e.headers)
    assert checked(e.client.get(e.graph_base, headers=e.viewer_headers)) == {"items": []}
    assert e.client.get(e.graph_base + "/" + row["id"], headers=e.viewer_headers).status_code == 404
    assert e.client.post(e.graph_base, headers=e.viewer_headers, json={"request_id": "denied", "definition": {"title": "No write"}}).status_code == 403
    for method, suffix in (("PATCH", "/graphs/one"), ("DELETE", "/graphs/one"),
                           ("POST", "/graph-runs/one/complete"), ("GET", "/graphs/one/private")):
        result = e.client.request(method, e.studio_base + suffix, headers=e.headers)
        assert result.status_code == 501
        assert result.json()["detail"]["code"] == "COLLABORATION_ROUTE_NOT_ENABLED"
    e.authorization.revoke_role(e.role, e.lead)
    assert e.client.get(e.graph_base, headers=e.headers).status_code == 403


def test_graph_cas_conflict_is_sanitized_and_never_returns_authored_text(graph_client):
    e = graph_client
    secret = "private-graph-draft-" + uuid4().hex
    row = create(e, value=definition(secret))
    response = e.client.put(e.graph_base + "/" + row["id"], json={"expected_version": 7, "definition": definition("new")})
    assert response.status_code == 409
    assert set(response.json()["detail"]["current"]) <= {"version", "status"}
    assert secret not in response.text and "project_incarnation" not in response.text
    assert checked(e.client.get(e.graph_base + "/" + row["id"])) == row


@pytest.mark.parametrize("private_error", [False, True])
def test_graph_late_revocation_suppresses_results_and_private_errors(graph_client, monkeypatch, private_error):
    e = scoped(graph_client, monkeypatch)
    row = create(e, headers=e.headers)
    original = e.graphs.get
    def revoked(*args, **kwargs):
        result = original(*args, **kwargs)
        e.sessions.revoke(e.lead)
        if private_error:
            raise ValueError("private graph result")
        return result
    monkeypatch.setattr(e.graphs, "get", revoked)
    response = e.client.get(e.graph_base + "/" + row["id"], headers=e.headers)
    assert response.status_code == 401
    assert row["id"] not in response.text and "private graph" not in response.text


def test_asset_reference_is_display_only_and_cannot_admit_execution(graph_client):
    e = graph_client
    asset = checked(e.client.post(e.studio_base + "/assets", json=upload_body()), 201)
    row = create(e, value={"title": "Existing asset reference", "nodes": [{"id": "Image", "definition_id": "asset_reference",
        "parameters": {"asset_id": asset["id"], "version": asset["version"], "digest": asset["sha256"], "kind": asset["kind"]}}]})
    path = e.graph_base + "/" + row["id"]
    preflight = checked(e.client.post(path + "/preflight", json={"expected_version": row["version"]}))
    assert preflight["executable"] is False
    assert any(item["code"] == "CREATIVE_GRAPH_ATOMIC_INPUT_OWNER_ADAPTER_REQUIRED" for item in preflight["issues"])
    response = e.client.post(path + "/runs", json={"expected_graph_version": row["version"],
        "request_id": "blocked", "reviewed_preflight_digest": preflight["preflight_digest"]})
    assert response.status_code == 422
    assert checked(e.client.get(path + "/runs")) == {"items": []}
    assert checked(e.client.get(e.studio_base + "/assets/" + asset["id"])) == asset


def test_original_review_permission_is_distinct_from_graph_write(graph_client, monkeypatch):
    e = scoped(graph_client, monkeypatch)
    row = create(e, headers=e.headers)
    run = admit(e, row, headers=e.headers)
    path = e.studio_base + "/graph-runs/" + run["id"]
    run = checked(e.client.post(path + "/execute", headers=e.headers, json={"expected_version": run["version"]}))
    assert run["status"] == "WAITING_APPROVAL"
    e.authorization.revoke_role(e.role, e.lead)
    scope = AuthorizationScope(ScopeKind.BRANCH, e.workspace, e.nid, e.storyline, e.branch)
    for permission in ("domain.read", "domain.write"):
        e.authorization.assign_permission(PermissionAssignment("graph-" + uuid4().hex, e.lead,
            permission, ModalityDomain.NOVEL, scope, e.lead))
    body = {"expected_version": run["version"], "node_id": "Review", "reviewed_output_digest": run["review"]["output_digest"]}
    assert e.client.post(path + "/approve", headers=e.headers, json=body).status_code == 403
    assert checked(e.client.get(path, headers=e.headers)) == run
    e.authorization.assign_permission(PermissionAssignment("review-" + uuid4().hex, e.lead,
        "domain.review", ModalityDomain.NOVEL, scope, e.lead))
    assert e.client.post(path + "/approve", headers=e.headers, json={**body, "reviewed_output_digest": "0" * 64}).status_code == 409
    approved = checked(e.client.post(path + "/approve", headers=e.headers, json=body))
    assert approved["status"] == "SUCCEEDED"


def test_late_same_slug_recreation_suppresses_old_graph_response(graph_client, monkeypatch):
    e = graph_client
    row = create(e)
    original = e.graphs.get
    def recreated(*args, **kwargs):
        result = original(*args, **kwargs)
        e.novels.delete(e.nid)
        assert e.novels.create({"id": e.nid, "title": "New graph owner, same slug"})["id"] == e.nid
        return result
    monkeypatch.setattr(e.graphs, "get", recreated)
    response = e.client.get(e.graph_base + "/" + row["id"])
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "CREATIVE_AUTHORITY_CHANGED"
    assert row["id"] not in response.text
    assert checked(e.client.get(e.graph_base)) == {"items": []}

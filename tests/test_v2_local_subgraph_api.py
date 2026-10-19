"""Mounted original File authority and lost-response checks for server-only schema6."""
from copy import deepcopy
from uuid import uuid4
import pytest
from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind
from test_v2_creative_graph_api import graph_client, scoped_graph_client
from test_v2_local_subgraph import child_definition, parent_definition
from test_r3_mounted_contracts import checked, mounted, prefix
from test_v2_independent_workspace_api import client


def create(e, definition, headers=None):
    return checked(e.client.post(e.graph_base, headers=headers, json={"request_id": uuid4().hex, "definition": definition}), 201)


def admit(e, parent, headers=None):
    path = e.graph_base + "/" + parent["id"]
    preview = checked(e.client.post(path + "/preflight", headers=headers, json={"expected_version": 1}))
    assert preview["executable"] and preview["graph_schema_version"] == 6
    return checked(e.client.post(path + "/runs", headers=headers, json={"expected_graph_version": 1, "reviewed_preflight_digest": preview["preflight_digest"], "request_id": uuid4().hex}), 201)


def test_new_catalog_and_call_use_original_domain_permissions_and_real_review_gate(scoped_graph_client):
    e = scoped_graph_client
    catalog = checked(e.client.get(e.graph_base + "/catalog?include_local_subgraph=true", headers=e.headers))
    assert catalog["capabilities"]["local_subgraph_schema_version"] == 6
    assert catalog["capabilities"]["model_execution"] is False
    child = create(e, child_definition(), e.headers); parent = create(e, parent_definition(child), e.headers); run = admit(e, parent, e.headers)
    assert e.client.get(e.graph_base + "/" + parent["id"], headers=e.viewer_headers).status_code == 404
    path = e.studio_base + "/graph-runs/" + run["id"]
    run = checked(e.client.post(path + "/execute", headers=e.headers, json={"expected_version": 1}))
    assert run["status"] == "WAITING_APPROVAL" and not run["model_called"] and not run["external_calls"]
    e.authorization.revoke_role(e.role, e.lead)
    scope = AuthorizationScope(ScopeKind.BRANCH, e.workspace, e.nid, e.storyline, e.branch)
    for permission in ("domain.read", "domain.write"):
        e.authorization.assign_permission(PermissionAssignment(uuid4().hex, e.lead, permission, ModalityDomain.NOVEL, scope, e.lead))
    body = {"expected_version": run["version"], "node_id": "review", "reviewed_output_digest": run["review"]["output_digest"]}
    assert e.client.post(path + "/approve", headers=e.headers, json=body).status_code == 403
    assert checked(e.client.get(path, headers=e.headers)) == run
    e.authorization.assign_permission(PermissionAssignment(uuid4().hex, e.lead, "domain.review", ModalityDomain.NOVEL, scope, e.lead))
    approved = checked(e.client.post(path + "/approve", headers=e.headers, json=body))
    assert approved["status"] == "SUCCEEDED" and approved["reviewed"] and not approved["applied"]


def test_lost_execute_response_is_recovered_by_original_run_get_without_reexecution(graph_client, monkeypatch):
    e = graph_client; child = create(e, child_definition()); parent = create(e, parent_definition(child)); run = admit(e, parent)
    from app.creative import graph_local_subgraph as subgraph
    original_evaluate = subgraph.evaluate; calls = []
    def evaluate(*args, **kwargs): calls.append(1); return original_evaluate(*args, **kwargs)
    monkeypatch.setattr(subgraph, "evaluate", evaluate)
    original = e.graphs.action
    def lose(*args, **kwargs):
        value = original(*args, **kwargs)
        if args[4] == "execute": raise RuntimeError("synthetic response lost after durable action")
        return value
    monkeypatch.setattr(e.graphs, "action", lose)
    path = e.studio_base + "/graph-runs/" + run["id"]
    try:
        response = e.client.post(path + "/execute", json={"expected_version": 1})
        assert response.status_code >= 500
    except RuntimeError as exc: assert str(exc) == "synthetic response lost after durable action"
    monkeypatch.setattr(e.graphs, "action", original)
    recovered = checked(e.client.get(path))
    assert recovered["status"] == "WAITING_APPROVAL" and recovered["version"] == 2 and calls == [1]
    assert checked(e.client.get(e.graph_base + "/" + parent["id"] + "/runs"))["items"] == [recovered]
    assert calls == [1]
    assert e.client.post(path + "/execute", json={"expected_version": recovered["version"]}).status_code == 422
    assert checked(e.client.get(path)) == recovered and calls == [1]


def test_incarnation_recreation_after_read_suppresses_derived_run_response(graph_client, monkeypatch):
    e = graph_client; child = create(e, child_definition()); parent = create(e, parent_definition(child)); run = admit(e, parent)
    path = e.studio_base + "/graph-runs/" + run["id"]
    run = checked(e.client.post(path + "/execute", json={"expected_version": 1}))
    original = e.graphs.get_run
    def recreate(*args, **kwargs):
        value = original(*args, **kwargs)
        e.novels.delete(e.nid); e.novels.create({"id": e.nid, "title": "Recreated isolated fixture project"})
        return value
    monkeypatch.setattr(e.graphs, "get_run", recreate)
    response = e.client.get(path)
    assert response.status_code == 403 and "First authored beat" not in response.text and run["id"] not in response.text


def test_lost_run_admission_response_is_read_before_any_execute_and_request_id_is_idempotent(graph_client, monkeypatch):
    e = graph_client; child = create(e, child_definition()); parent = create(e, parent_definition(child))
    path = e.graph_base + "/" + parent["id"]
    preview = checked(e.client.post(path + "/preflight", json={"expected_version": 1}))
    body = {"expected_graph_version": 1, "reviewed_preflight_digest": preview["preflight_digest"], "request_id": uuid4().hex}
    original = e.graphs.create_run
    def lose(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("synthetic admission response lost after durable commit")
    monkeypatch.setattr(e.graphs, "create_run", lose)
    try:
        response = e.client.post(path + "/runs", json=body)
        assert response.status_code >= 500
    except RuntimeError as exc: assert str(exc) == "synthetic admission response lost after durable commit"
    monkeypatch.setattr(e.graphs, "create_run", original)
    rows = checked(e.client.get(path + "/runs"))["items"]
    assert len(rows) == 1 and rows[0]["status"] == "QUEUED" and rows[0]["version"] == 1
    assert all(v["output"] is None for v in rows[0]["node_states"].values())
    assert checked(e.client.get(e.studio_base + "/graph-runs/" + rows[0]["id"])) == rows[0]
    assert checked(e.client.post(path + "/runs", json=body), 201) == rows[0]
    assert checked(e.client.get(path + "/runs"))["items"] == rows


@pytest.mark.parametrize("retain_write", [False, True])
def test_real_domain_revocation_during_child_step_rolls_back_without_failed_write(scoped_graph_client, monkeypatch, retain_write):
    e = scoped_graph_client; child = create(e, child_definition(), e.headers); parent = create(e, parent_definition(child), e.headers); run = admit(e, parent, e.headers)
    scope = AuthorizationScope(ScopeKind.BRANCH, e.workspace, e.nid, e.storyline, e.branch)
    if retain_write:
        e.authorization.assign_permission(PermissionAssignment(uuid4().hex, e.lead, "domain.write", ModalityDomain.NOVEL, scope, e.lead))
    original = e.graphs.executor.adapter.execute
    def revoke(request):
        value = original(request)
        if request.node_type == "text_reference": e.authorization.revoke_role(e.role, e.lead)
        return value
    monkeypatch.setattr(e.graphs.executor.adapter, "execute", revoke)
    before = deepcopy(e.graphs.store.read(e.nid, parent["scope"]))
    path = e.studio_base + "/graph-runs/" + run["id"]
    response = e.client.post(path + "/execute", headers=e.headers, json={"expected_version": 1})
    assert response.status_code == 403 and "First authored beat" not in response.text
    assert e.graphs.store.read(e.nid, parent["scope"]) == before
    e.authorization.assign_permission(PermissionAssignment(uuid4().hex, e.lead, "domain.read", ModalityDomain.NOVEL, scope, e.lead))
    fresh = checked(e.client.get(path, headers=e.headers))
    assert fresh["status"] == "QUEUED" and fresh["version"] == 1 and all(v["output"] is None for v in fresh["node_states"].values())


@pytest.mark.parametrize("waiting", [False, True])
def test_source_read_revocation_blocks_execute_or_approve_but_retains_cancel_reject(scoped_graph_client, waiting):
    e = scoped_graph_client; child = create(e, child_definition(), e.headers); parent = create(e, parent_definition(child), e.headers); run = admit(e, parent, e.headers)
    path = e.studio_base + "/graph-runs/" + run["id"]
    if waiting: run = checked(e.client.post(path + "/execute", headers=e.headers, json={"expected_version": 1}))
    e.authorization.revoke_role(e.role, e.lead)
    scope = AuthorizationScope(ScopeKind.BRANCH, e.workspace, e.nid, e.storyline, e.branch)
    for permission in ("domain.write", "domain.review"):
        e.authorization.assign_permission(PermissionAssignment(uuid4().hex, e.lead, permission, ModalityDomain.NOVEL, scope, e.lead))
    assert e.client.get(e.graph_base + "/" + child["id"], headers=e.headers).status_code == 403
    before = deepcopy(e.graphs.store.read(e.nid, parent["scope"]))
    body = {"expected_version": run["version"]}
    if waiting: body.update(node_id="review", reviewed_output_digest=run["review"]["output_digest"])
    denied = e.client.post(path + ("/approve" if waiting else "/execute"), headers=e.headers, json=body)
    assert denied.status_code == 403 and "First authored beat" not in denied.text
    assert e.graphs.store.read(e.nid, parent["scope"]) == before
    cleaned = checked(e.client.post(path + ("/reject" if waiting else "/cancel"), headers=e.headers, json=body))
    assert cleaned["status"] == ("REJECTED" if waiting else "CANCELLED") and cleaned["review"] is None
    assert all(v["output"] is None for v in cleaned["node_states"].values())
    assert cleaned["local_subgraph_runtime"]["bindings"] == cleaned["local_subgraph_runtime"]["receipts"] == {}


def test_write_only_authority_cannot_create_save_or_admit_schema6_but_keeps_schema1_write(scoped_graph_client):
    e = scoped_graph_client; child = create(e, child_definition(), e.headers); parent = create(e, parent_definition(child), e.headers)
    path = e.graph_base + "/" + parent["id"]
    preview = checked(e.client.post(path + "/preflight", headers=e.headers, json={"expected_version": 1}))
    e.authorization.revoke_role(e.role, e.lead)
    scope = AuthorizationScope(ScopeKind.BRANCH, e.workspace, e.nid, e.storyline, e.branch)
    e.authorization.assign_permission(PermissionAssignment(uuid4().hex, e.lead, "domain.write", ModalityDomain.NOVEL, scope, e.lead))
    before = deepcopy(e.graphs.store.read(e.nid, parent["scope"]))
    denied = [
        e.client.post(e.graph_base, headers=e.headers, json={"request_id": uuid4().hex, "definition": parent["definition"]}),
        e.client.put(path, headers=e.headers, json={"expected_version": 1, "definition": parent["definition"]}),
        e.client.post(path + "/runs", headers=e.headers, json={"expected_graph_version": 1,
            "reviewed_preflight_digest": preview["preflight_digest"], "request_id": uuid4().hex}),
        e.client.post(path + "/preflight", headers=e.headers, json={"expected_version": 1}),
    ]
    assert all(response.status_code == 403 and "First authored beat" not in response.text for response in denied)
    assert e.graphs.store.read(e.nid, parent["scope"]) == before
    legacy = checked(e.client.put(e.graph_base + "/" + child["id"], headers=e.headers,
        json={"expected_version": 1, "definition": child["definition"]}))
    assert legacy["version"] == 2 and legacy["definition"] == child["definition"]

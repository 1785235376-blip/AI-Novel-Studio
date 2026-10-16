"""Mounted target budgets follow the saved graph schema on both route aliases.

Reuse the original File/PostgreSQL, session, scope, and application fixtures.
Only local text inputs execute; provider and job entry points fail if touched.
"""
from copy import deepcopy
from uuid import uuid4

import pytest

from app.creative.project_store import CreativeProjectStore
from app.experimental.store import ExperimentalStore
from test_r3_mounted_contracts import checked, mounted, prefix, scoped
from test_v2_independent_workspace_api import client
from test_v2_creative_graph_api import create, graph_client
from test_v2_ai_execution_api import ai_client
from test_v2_ai_execution_runtime import generation_delta, owned_jobs


@pytest.fixture
def budget_client(ai_client, monkeypatch):
    e = ai_client
    # This helper captures its owners at construction, before graph_client
    # substitutes the mounted fixture's disposable persistence and workspace.
    monkeypatch.setattr(e.graphs.asset_inputs, "store", e.graphs.store)
    monkeypatch.setattr(e.graphs.asset_inputs, "workspace", e.studio)

    def forbidden(*args, **kwargs):
        pytest.fail("Target-budget regression attempted provider or job execution")

    monkeypatch.setattr(e.manager, "prepare_graph_job", forbidden)
    monkeypatch.setattr(e.manager, "start_prepared", forbidden)
    monkeypatch.setattr(e.models, "dispatch", forbidden)
    monkeypatch.setattr(e.runtime.providers["mock"], "stream", forbidden)
    yield e
    assert not owned_jobs(e) and not generation_delta(e)


def definition(schema, count):
    return {"schema_version": schema, "title": "Private target-budget fixture",
        "nodes": [{"id": f"Node{index:02d}", "definition_id": "text_input",
                   "parameters": {"text": f"Private user-authored input {index}"}}
                  for index in range(count)], "edges": []}


def graph(e, schema, count):
    row = create(e, headers=e.headers, value=definition(schema, count))
    return row, e.graph_base + "/" + row["id"]


def targets(count):
    return [f"Node{index:02d}" for index in range(count)]


def preflight_body(row, selected):
    return {"expected_version": row["version"], "target_node_ids": selected}


def run_body(row, preflight, selected):
    return {"expected_graph_version": row["version"], "target_node_ids": selected,
        "reviewed_preflight_digest": preflight["preflight_digest"],
        "request_id": "budget-run-" + uuid4().hex}


def saved(e):
    return deepcopy(e.graphs.store.read(e.nid, e.scope))


def assert_local(value):
    assert value["model_called"] is False and value["external_calls"] == 0
    if "applied" in value:
        assert value["applied"] is False


def assert_private_conflict(response):
    assert response.status_code == 409, response.text
    assert "Private user-authored" not in response.text
    assert "project_incarnation" not in response.text
    assert set(response.json()["detail"].get("current", {})) <= {"version", "status"}


@pytest.mark.parametrize("schema", [1, 2])
def test_legacy_mounted_targets_accept_sixteen_and_reject_seventeen(budget_client, schema):
    e = budget_client
    row, path = graph(e, schema, 16)
    selected = targets(16)
    preflight = checked(e.client.post(path + "/preflight", headers=e.headers,
        json=preflight_body(row, selected)))
    assert preflight["executable"] and preflight["target_node_ids"] == selected
    assert_local(preflight)
    admitted = checked(e.client.post(path + "/runs", headers=e.headers,
        json=run_body(row, preflight, selected)), 201)
    assert admitted["status"] == "QUEUED" and not admitted["stale"]
    assert set(admitted["node_states"]) == set(selected)
    assert_local(admitted)
    before = saved(e)
    # A legacy graph has at most sixteen nodes. The seventeenth request entry
    # must still be rejected when the mounted union admits a media envelope.
    oversized = selected + [selected[0]]
    for suffix, body in (("preflight", preflight_body(row, oversized)),
                         ("runs", run_body(row, preflight, oversized))):
        response = e.client.post(path + "/" + suffix, headers=e.headers, json=body)
        assert response.status_code == 422, response.text
        # The saved schema must reject the media-sized envelope at its budget,
        # rather than accidentally rejecting only the duplicate seventeenth ID.
        assert "too_long" in response.json()["detail"]["message"]
        assert saved(e) == before
    assert checked(e.client.get(path, headers=e.headers)) == row
    assert checked(e.client.get(path + "/runs", headers=e.headers)) == {"items": [admitted]}


@pytest.mark.parametrize("count", [17, 24])
def test_schema_three_explicit_targets_persist_reopen_and_execute_locally(budget_client, monkeypatch, count):
    e = budget_client
    row, path = graph(e, 3, count)
    selected = targets(count)
    preflight = checked(e.client.post(path + "/preflight", headers=e.headers,
        json=preflight_body(row, selected)))
    assert preflight["executable"] and preflight["target_node_ids"] == selected
    assert preflight["graph_schema_version"] == 3
    body = run_body(row, preflight, selected)
    admitted = checked(e.client.post(path + "/runs", headers=e.headers, json=body), 201)
    assert not admitted["stale"] and set(admitted["node_states"]) == set(selected)
    assert_local(admitted)

    # Reopen through a new real persistence owner while keeping the production
    # mounted route/service composition and its original authority unchanged.
    reopened = CreativeProjectStore(ExperimentalStore(e.root, e.backend, e.url))
    monkeypatch.setattr(e.graphs, "store", reopened)
    monkeypatch.setattr(e.graphs.asset_inputs, "store", reopened)
    action = e.studio_base + "/graph-runs/" + admitted["id"]
    assert checked(e.client.get(action, headers=e.headers)) == admitted
    assert checked(e.client.get(path + "/runs", headers=e.headers)) == {"items": [admitted]}
    assert checked(e.client.post(path + "/runs", headers=e.headers, json=body), 201) == admitted
    done = checked(e.client.post(action + "/execute", headers=e.headers,
        json={"expected_version": admitted["version"]}))
    assert done["status"] == "SUCCEEDED" and not done["stale"]
    assert all(value["status"] == "SUCCEEDED" for value in done["node_states"].values())
    assert_local(done)
    assert checked(e.client.get(action, headers=e.headers)) == done
    assert checked(e.client.get(path + "/runs", headers=e.headers)) == {"items": [done]}


def test_empty_schema_three_preflight_returns_twenty_four_targets_for_existing_ui(budget_client):
    e = budget_client
    row, path = graph(e, 3, 24)
    preflight = checked(e.client.post(path + "/preflight", headers=e.headers,
        json=preflight_body(row, [])))
    assert preflight["executable"] and preflight["target_node_ids"] == targets(24)
    explicit = checked(e.client.post(path + "/preflight", headers=e.headers,
        json=preflight_body(row, preflight["target_node_ids"])))
    assert explicit == preflight  # Same reviewed digest; no caller schema flag.
    body = run_body(row, preflight, preflight["target_node_ids"])
    admitted = checked(e.client.post(path + "/runs", headers=e.headers, json=body), 201)
    assert not admitted["stale"] and len(admitted["node_states"]) == 24
    assert checked(e.client.post(path + "/runs", headers=e.headers, json=body), 201) == admitted
    assert_local(admitted)
    before = saved(e)
    oversized = targets(24) + ["Node00"]
    for suffix, payload in (("preflight", preflight_body(row, oversized)),
                            ("runs", run_body(row, preflight, oversized))):
        response = e.client.post(path + "/" + suffix, headers=e.headers, json=payload)
        assert response.status_code == 422, response.text
        assert saved(e) == before


@pytest.mark.parametrize("schema,count", [(1, 16), (2, 16), (3, 24)])
def test_target_validation_stays_strict_and_never_takes_a_caller_schema_flag(budget_client, schema, count):
    e = budget_client
    row, path = graph(e, schema, count)
    preflight = checked(e.client.post(path + "/preflight", headers=e.headers,
        json=preflight_body(row, targets(count))))
    before = saved(e)
    for selected in (["Node00", "Node00"], ["UnknownNode"], ["../private"], [42]):
        for suffix, body in (("preflight", preflight_body(row, selected)),
                             ("runs", run_body(row, preflight, selected))):
            response = e.client.post(path + "/" + suffix, headers=e.headers, json=body)
            assert response.status_code == 422, (schema, selected, response.text)
            assert saved(e) == before
    for suffix, body in (("preflight", preflight_body(row, targets(count))),
                         ("runs", run_body(row, preflight, targets(count)))):
        response = e.client.post(path + "/" + suffix, headers=e.headers,
            json={**body, "schema_version": 3})
        assert response.status_code == 422, response.text
        assert saved(e) == before
    assert checked(e.client.get(path, headers=e.headers)) == row
    assert checked(e.client.get(path + "/runs", headers=e.headers)) == {"items": []}


@pytest.mark.parametrize("schema,count", [(1, 16), (2, 16), (3, 24)])
def test_budget_admission_keeps_graph_run_cas_and_exact_preflight(budget_client, schema, count):
    e = budget_client
    row, path = graph(e, schema, count)
    selected = targets(count)
    preflight = checked(e.client.post(path + "/preflight", headers=e.headers,
        json=preflight_body(row, selected)))
    body = run_body(row, preflight, selected)
    run = checked(e.client.post(path + "/runs", headers=e.headers, json=body), 201)
    before = saved(e)
    for suffix, payload in (
        ("preflight", {**preflight_body(row, selected), "expected_version": row["version"] + 1}),
        ("runs", {**body, "expected_graph_version": row["version"] + 1}),
        ("runs", {**body, "reviewed_preflight_digest": "0" * 64}),
    ):
        assert_private_conflict(e.client.post(path + "/" + suffix, headers=e.headers, json=payload))
        assert saved(e) == before
    action = e.studio_base + "/graph-runs/" + run["id"]
    assert_private_conflict(e.client.post(action + "/execute", headers=e.headers,
        json={"expected_version": run["version"] + 1}))
    assert saved(e) == before
    assert checked(e.client.get(action, headers=e.headers)) == run


def test_legacy_budget_routes_keep_actor_scope_and_revoked_role_fences(budget_client, monkeypatch):
    e = scoped(budget_client, monkeypatch)
    row, path = graph(e, 1, 16)
    preflight = checked(e.client.post(path + "/preflight", headers=e.headers,
        json=preflight_body(row, targets(16))))
    body = run_body(row, preflight, targets(16))
    run = checked(e.client.post(path + "/runs", headers=e.headers, json=body), 201)
    action = e.studio_base + "/graph-runs/" + run["id"]
    before = saved(e)
    assert e.client.get(action, headers=e.viewer_headers).status_code == 404
    assert e.client.post(path + "/preflight", headers=e.viewer_headers,
        json=preflight_body(row, targets(16))).status_code == 404
    assert e.client.post(path + "/runs", headers=e.viewer_headers, json=body).status_code == 403
    assert e.client.get(action, headers={**e.headers, "X-Branch-ID": e.other_branch}).status_code == 403
    assert e.client.get(action, headers={"X-Session-Token": e.lead}).status_code == 400
    e.authorization.revoke_role(e.role, e.lead)
    for method, target, payload in (
        ("GET", action, None),
        ("POST", path + "/preflight", preflight_body(row, targets(16))),
        ("POST", path + "/runs", body),
        ("POST", action + "/execute", {"expected_version": run["version"]}),
    ):
        response = e.client.request(method, target, headers=e.headers, json=payload)
        assert response.status_code == 403, response.text
        assert "Private user-authored" not in response.text and run["id"] not in response.text
    assert saved(e) == before


def test_schema_three_late_host_revocation_cannot_commit_expanded_target_run(budget_client, monkeypatch):
    e = budget_client
    row, path = graph(e, 3, 24)
    preflight = checked(e.client.post(path + "/preflight", headers=e.headers,
        json=preflight_body(row, [])))
    before = saved(e)
    original = e.graphs._preflight

    def revoked(*args, **kwargs):
        result = original(*args, **kwargs)
        e.sessions.revoke(e.host)
        return result

    monkeypatch.setattr(e.graphs, "_preflight", revoked)
    response = e.client.post(path + "/runs", headers=e.headers,
        json=run_body(row, preflight, preflight["target_node_ids"]))
    assert response.status_code == 401, response.text
    assert row["id"] not in response.text and "Private user-authored" not in response.text
    assert saved(e) == before


@pytest.mark.parametrize("schema", [1, 2])
def test_schema_downgrade_keeps_stale_cas_before_saved_target_narrowing(budget_client, schema):
    e = budget_client
    original, path = graph(e, 3, 24)
    preflight = checked(e.client.post(path + "/preflight", headers=e.headers,
        json=preflight_body(original, [])))
    selected = preflight["target_node_ids"]
    assert len(selected) == 24
    current = checked(e.client.put(path, headers=e.headers, json={
        "expected_version": original["version"], "definition": definition(schema, 16)}))
    assert current["version"] == 2 and current["definition"]["schema_version"] == schema
    before = saved(e)
    for suffix, payload in (("preflight", preflight_body(original, selected)),
                            ("runs", run_body(original, preflight, selected))):
        # A page still showing the schema-3 revision must receive the original
        # conflict response even though its target list exceeds the new budget.
        assert_private_conflict(e.client.post(path + "/" + suffix, headers=e.headers, json=payload))
        assert saved(e) == before
    for suffix, payload in (("preflight", preflight_body(current, selected)),
                            ("runs", run_body(current, preflight, selected))):
        response = e.client.post(path + "/" + suffix, headers=e.headers, json=payload)
        assert response.status_code == 422, response.text
        assert "too_long" in response.json()["detail"]["message"]
        assert saved(e) == before
    assert checked(e.client.get(path, headers=e.headers)) == current
    assert checked(e.client.get(path + "/runs", headers=e.headers)) == {"items": []}

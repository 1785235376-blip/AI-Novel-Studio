"""Synthetic engineering contracts, parametrized against durable File and real PG."""
import copy
import os
import threading
import uuid
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.experimental.common import StaleSourceError
from app.experimental.store import ExperimentalStore
from app.experimental.planning import PlanningService, PlanningAdapterOutput, MockStructuredPlanningAdapter
from app.experimental.planning_api import create_planning_router
from app.services.v1_capability_service import CapabilityVersionConflict


@pytest.fixture(params=[pytest.param("file", marks=pytest.mark.file_backend_only), pytest.param("postgres", marks=pytest.mark.postgres_backend_only)])
def planning_env(tmp_path, request):
    backend = request.param
    url = os.getenv("TEST_POSTGRES_DATABASE_URL", "")
    if backend == "postgres" and not url:
        pytest.skip("NOT_RUN: real PostgreSQL endpoint unavailable")
    nid = "r3-" + uuid.uuid4().hex
    rows = {"characters": [{"id": "alice", "name": "Alice"}, {"id": "bob", "name": "Bob"}], "locations": [{"id": "city", "name": "City"}, {"id": "region", "name": "Region"}], "story_routes": [{"id": "route", "title": "Path"}], "canon": []}
    chapters = {f"{nid}:{i}": {"id": f"{nid}:{i}", "novel_id": nid, "number": i, "version": 1, "content": f"Synthetic chapter {i}"} for i in range(1, 5)}
    order = list(chapters)
    def get(cid):
        if cid not in chapters: raise FileNotFoundError(cid)
        return copy.deepcopy(chapters[cid])
    def novel_get(got):
        if got != nid: raise FileNotFoundError(got)
        return {"id": nid}
    novels = SimpleNamespace(get=novel_get, data_set=lambda got, name: copy.deepcopy(rows[name]))
    chapter_service = SimpleNamespace(get=get, list=lambda got: [get(cid) for cid in order])
    store = ExperimentalStore(tmp_path, backend=backend, database_url=url)
    scope = {"mode": "local", "novel_id": nid}
    env = SimpleNamespace(service=PlanningService(store, novels, chapter_service), store=store, nid=nid, scope=scope, chapters=chapters, chapter_service=chapter_service, novels=novels, rows=rows, order=order, root=tmp_path, backend=backend, url=url)
    yield env
    if backend == "postgres":
        with store._connect() as conn:
            conn.execute("DELETE FROM experimental_scope_documents WHERE novel_id = %s", (nid,))


def graph(env, **kwargs):
    return env.service.create_graph(env.nid, env.scope, "writer", {"title": "Project", **kwargs})


def proposal(env, node_id, **kwargs):
    return env.service.create_proposal(env.nid, env.scope, "writer", {"node_id": node_id, "expected_node_version": 1, "title": "Choice", **kwargs})


def test_planning_hierarchy_real_refs_and_restart(planning_env):
    e = planning_env
    g = graph(e)
    volume = e.service.create_node(e.nid, e.scope, "writer", {"graph_id": g["id"], "parent_id": g["root_node_id"], "level": "VOLUME", "title": "Volume"})
    chapter = e.service.create_node(e.nid, e.scope, "writer", {"graph_id": g["id"], "parent_id": volume["id"], "level": "CHAPTER", "title": "Chapter", "links": {"chapter_ids": [e.order[0]]}})
    scene = e.service.create_node(e.nid, e.scope, "writer", {"graph_id": g["id"], "parent_id": chapter["id"], "level": "SCENE", "title": "Scene", "links": {"chapter_ids": [e.order[0]], "character_ids": ["alice"], "location_ids": ["city"], "story_route_ids": ["route"]}, "fields": {"goal": "Find the gate", "character_objectives": {"alice": "Enter the city"}}})
    restarted = PlanningService(ExperimentalStore(e.root, e.backend, e.url), e.novels, e.chapter_service)
    assert {node["level"] for node in restarted.graph(e.nid, e.scope, g["id"])["nodes"]} == {"PROJECT", "VOLUME", "CHAPTER", "SCENE"}
    assert scene["sources"][e.order[0]]["version"] == 1
    with pytest.raises(ValueError, match="hierarchy"):
        e.service.create_node(e.nid, e.scope, "writer", {"graph_id": g["id"], "parent_id": g["root_node_id"], "level": "SCENE", "title": "Wrong"})
    with pytest.raises(ValueError, match="unknown characters"):
        proposal(e, g["root_node_id"], links={"character_ids": ["invented"]})
    with pytest.raises(ValueError, match="character objectives"):
        proposal(e, g["root_node_id"], fields={"character_objectives": {"alice": "Unlinked"}})
    with pytest.raises(FileNotFoundError):
        proposal(e, g["root_node_id"], links={"chapter_ids": ["another:1"]})


def test_planning_compare_approve_history_and_restore_are_manuscript_safe(planning_env):
    e = planning_env
    before = copy.deepcopy((e.chapters, e.rows))
    g = graph(e)
    a = proposal(e, g["root_node_id"], fields={"ending_intent": "Hope"})
    b = proposal(e, g["root_node_id"], fields={"ending_intent": "Tragedy"})
    result = e.service.compare(e.nid, e.scope, [a["id"], b["id"]])
    assert result["differences"]["ending_intent"] == {a["id"]: "Hope", b["id"]: "Tragedy"}
    assert e.service.graph(e.nid, e.scope, g["id"])["nodes"][0]["fields"]["ending_intent"] == ""
    approved = e.service.review(e.nid, e.scope, "reviewer", a["id"], "approve", 1)
    node = e.service.graph(e.nid, e.scope, g["id"])["nodes"][0]
    assert node["fields"]["ending_intent"] == "Hope" and node["version"] == 2
    assert approved["status"] == "APPROVED" and not e.service.proposal(e.nid, e.scope, a["id"])["stale"]
    assert e.service.proposal(e.nid, e.scope, b["id"])["stale"]
    with pytest.raises(StaleSourceError): e.service.review(e.nid, e.scope, "reviewer", b["id"], "approve", 1)
    assert e.service.history(e.nid, e.scope, a["id"])[0]["status"] == "REVIEW"
    restored = e.service.restore(e.nid, e.scope, "writer", a["id"], 2, 1)
    assert restored["status"] == "REVIEW" and restored["version"] == 3
    assert e.service.proposal(e.nid, e.scope, a["id"])["stale"]
    assert (e.chapters, e.rows) == before


def test_planning_reject_reopen_archive_and_stale_entity_fences(planning_env):
    e = planning_env
    g = graph(e)
    p = proposal(e, g["root_node_id"], links={"character_ids": ["alice"], "chapter_ids": [e.order[0]]})
    for action, status in [("reject", "REJECTED"), ("reopen", "REVIEW"), ("archive", "ARCHIVED"), ("reopen", "REVIEW")]:
        p = e.service.review(e.nid, e.scope, "reviewer", p["id"], action, p["version"])
        assert p["status"] == status
    e.rows["characters"][0]["name"] = "Changed without a version"
    assert e.service.proposal(e.nid, e.scope, p["id"])["stale"]
    with pytest.raises(StaleSourceError): e.service.review(e.nid, e.scope, "reviewer", p["id"], "approve", p["version"])
    e.rows["characters"][0]["name"] = "Alice"
    e.chapters[e.order[0]]["content"] += " unversioned change"
    with pytest.raises(StaleSourceError): e.service.review(e.nid, e.scope, "reviewer", p["id"], "approve", p["version"])
    assert e.service.proposal(e.nid, e.scope, p["id"])["version"] == p["version"]


def test_planning_custom_theory_and_mock_generation(planning_env):
    e = planning_env
    g = graph(e)
    template = e.service.create_template(e.nid, e.scope, "writer", {"title": "Spiral story", "beats": {"return": "A changed homecoming"}, "ending_options": ["Return", "Depart"]})
    result = e.service.generate(e.nid, e.scope, "writer", {"node_id": g["root_node_id"], "expected_node_version": 1, "template_id": template["id"], "candidate_count": 2})
    assert result["execution_mode"] == "MOCK_ONLY"
    assert [r["fields"]["ending_intent"] for r in result["items"]] == ["Return", "Depart"]
    assert all(r["status"] == "REVIEW" and r["execution_mode"] == "MOCK_ONLY" for r in result["items"])
    assert result["items"][0]["fields"]["beats"] == {"return": "A changed homecoming"}
    with pytest.raises(ValueError, match="NOT_CONFIGURED"):
        e.service.generate(e.nid, e.scope, "writer", {"node_id": g["root_node_id"], "expected_node_version": 1, "adapter_id": "paid-provider"})
    with pytest.raises(ValueError): PlanningAdapterOutput.model_validate({"execution_mode": "MOCK_ONLY", "candidates": [], "canon": "overwrite"})


def test_planning_atomic_approval_rollback_and_concurrent_one_winner(planning_env, monkeypatch):
    e = planning_env
    g = graph(e)
    p = proposal(e, g["root_node_id"], fields={"goal": "Win"})
    import app.experimental.planning as module
    original = module.change_row
    def fail_on_proposal(row, actor, version, callback):
        if "target_version" in row: raise RuntimeError("synthetic crash between node and proposal")
        return original(row, actor, version, callback)
    monkeypatch.setattr(module, "change_row", fail_on_proposal)
    with pytest.raises(RuntimeError): e.service.review(e.nid, e.scope, "reviewer", p["id"], "approve", 1)
    assert e.service.graph(e.nid, e.scope, g["id"])["nodes"][0]["version"] == 1
    assert e.service.proposal(e.nid, e.scope, p["id"])["status"] == "REVIEW"
    monkeypatch.setattr(module, "change_row", original)
    barrier, outcomes = threading.Barrier(3), []
    def update():
        service = PlanningService(ExperimentalStore(e.root, e.backend, e.url), e.novels, e.chapter_service)
        barrier.wait()
        try:
            service.review(e.nid, e.scope, "reviewer", p["id"], "approve", 1)
            outcomes.append("approved")
        except (CapabilityVersionConflict, ValueError): outcomes.append("conflict")
        except Exception as exc: outcomes.append(type(exc).__name__)
    workers = [threading.Thread(target=update) for _ in range(2)]
    for worker in workers: worker.start()
    barrier.wait()
    for worker in workers: worker.join(15)
    assert sorted(outcomes) == ["approved", "conflict"]
    assert e.service.graph(e.nid, e.scope, g["id"])["nodes"][0]["version"] == 2
    assert len(e.service.history(e.nid, e.scope, p["id"])) == 1


def planning_client(e):
    state = {"enabled": True, "permissions": {"domain.read", "domain.write", "domain.review"}, "calls": []}
    def authorize(nid, token, branch, permission):
        state["calls"].append(permission)
        if token != "session" or permission not in state["permissions"]: raise HTTPException(403, "denied")
        scope = e.scope if not branch else {"mode": "collaboration", "novel_id": nid, "workspace_id": "w", "storyline_id": "s", "branch_id": branch}
        return "authenticated", scope
    def flag(name):
        if not state["enabled"]: raise HTTPException(404, "disabled")
    app = FastAPI()
    app.include_router(create_planning_router(e.service, authorize, flag))
    return TestClient(app), state


def test_planning_api_flags_permissions_scope_conflict_and_crud(planning_env):
    e = planning_env
    client, flags = planning_client(e)
    base, headers = f"/novels/{e.nid}/experimental/planning", {"X-Session-Token": "session"}
    assert client.get(base + "/graphs").status_code == 403
    flags["enabled"] = False
    assert client.get(base + "/graphs", headers=headers).status_code == 404
    flags["enabled"] = True
    g = client.post(base + "/graphs", headers=headers, json={"title": "API"}).json()
    result = client.post(base + "/generate", headers=headers, json={"node_id": g["root_node_id"], "expected_node_version": 1, "template_id": "multiple-endings"})
    assert result.status_code == 201
    a, b = result.json()["items"]
    assert client.post(base + "/proposals/compare", headers=headers, json={"proposal_ids": [a["id"], b["id"]]}).status_code == 200
    flags["permissions"].remove("domain.review")
    assert client.post(base + f"/proposals/{a['id']}/approve", headers=headers, json={"expected_version": 1}).status_code == 403
    flags["permissions"].add("domain.review")
    assert client.post(base + f"/proposals/{a['id']}/approve", headers=headers, json={"expected_version": 99}).status_code == 409
    assert client.post(base + f"/proposals/{a['id']}/approve", headers=headers, json={"expected_version": 1}).status_code == 200
    assert client.post(base + f"/proposals/{b['id']}/approve", headers=headers, json={"expected_version": 1}).status_code == 409
    assert len(client.get(base + f"/proposals/{a['id']}/history", headers=headers).json()["items"]) == 1
    assert client.get(base + f"/graphs/{g['id']}", headers={**headers, "X-Branch-ID": "other"}).status_code == 404
    assert client.get(base + "/graphs", headers={**headers, "X-Branch-ID": "other"}).json() == {"items": []}
    assert client.post(base + "/graphs", headers=headers, json={"title": "Forged", "status": "APPROVED"}).status_code == 422
    assert client.post(base + "/graphs", headers={**headers, "X-Branch-ID": "other"}, json={"title": "Source", "links": {"chapter_ids": [e.order[0]]}}).status_code == 422


def test_planning_node_edit_optimistic_version_and_branch_metadata(planning_env):
    e = planning_env
    g = graph(e)
    row = e.service.edit_node(e.nid, e.scope, "writer", g["root_node_id"], {"title": "Revised", "expected_version": 1, "fields": {"goal": "Revised goal"}})
    assert row["version"] == 2 and row["history"][0]["title"] == "Project"
    with pytest.raises(CapabilityVersionConflict):
        e.service.edit_node(e.nid, e.scope, "writer", g["root_node_id"], {"title": "Lost", "expected_version": 1})
    branch = {"mode": "collaboration", "novel_id": e.nid, "workspace_id": "w", "storyline_id": "s", "branch_id": "branch"}
    other = e.service.create_graph(e.nid, branch, "writer", {"title": "Branch plan"})
    assert e.service.graph(e.nid, branch, other["id"])["scope"] == branch
    with pytest.raises(FileNotFoundError): e.service.graph(e.nid, e.scope, other["id"])


def test_planning_archive_hierarchy_and_restore_do_not_bypass_review(planning_env):
    e = planning_env
    g = graph(e)
    volume = e.service.create_node(e.nid, e.scope, "writer", {"graph_id": g["id"], "parent_id": g["root_node_id"], "level": "VOLUME", "title": "Volume"})
    child = e.service.create_node(e.nid, e.scope, "writer", {"graph_id": g["id"], "parent_id": volume["id"], "level": "CHAPTER", "title": "Chapter", "links": {"chapter_ids": [e.order[0]]}})
    with pytest.raises(ValueError, match="child nodes"):
        e.service.transition_node(e.nid, e.scope, "writer", volume["id"], "archive", 1)
    e.service.transition_node(e.nid, e.scope, "writer", child["id"], "archive", 1)
    e.service.transition_node(e.nid, e.scope, "writer", volume["id"], "archive", 1)
    with pytest.raises(ValueError, match="parent node"):
        e.service.transition_node(e.nid, e.scope, "writer", child["id"], "restore", 2)
    e.service.transition_node(e.nid, e.scope, "writer", volume["id"], "restore", 2)
    restored = e.service.transition_node(e.nid, e.scope, "writer", child["id"], "restore", 2)
    assert restored["status"] == "DRAFT"
    p = proposal(e, g["root_node_id"])
    e.service.transition_graph(e.nid, e.scope, "writer", g["id"], "archive", 1)
    with pytest.raises(ValueError, match="archived"):
        e.service.review(e.nid, e.scope, "reviewer", p["id"], "approve", 1)
    e.service.transition_graph(e.nid, e.scope, "writer", g["id"], "restore", 2)
    assert e.service.review(e.nid, e.scope, "reviewer", p["id"], "approve", 1)["status"] == "APPROVED"


def test_planning_adapter_late_source_change_is_atomic(planning_env, monkeypatch):
    e = planning_env
    g = graph(e, links={"chapter_ids": [e.order[0]]})
    original = MockStructuredPlanningAdapter.generate
    def generate(self, request):
        output = original(self, request)
        e.chapters[e.order[0]]["content"] += " changed while generating"
        return output
    monkeypatch.setattr(MockStructuredPlanningAdapter, "generate", generate)
    with pytest.raises(StaleSourceError):
        e.service.generate(e.nid, e.scope, "writer", {"node_id": g["root_node_id"], "expected_node_version": 1})
    assert not e.service.proposals(e.nid, e.scope)


def test_planning_parent_context_fences_child_proposals_and_archived_edit(planning_env):
    e = planning_env
    g = graph(e)
    child = e.service.create_node(e.nid, e.scope, "writer", {"graph_id": g["id"], "parent_id": g["root_node_id"], "level": "VOLUME", "title": "Volume"})
    candidate = proposal(e, child["id"])
    assert candidate["ancestor_versions"] == {g["root_node_id"]: 1}
    approved = e.service.review(e.nid, e.scope, "reviewer", candidate["id"], "approve", 1)
    assert not e.service.proposal(e.nid, e.scope, approved["id"])["stale"]
    e.service.edit_node(e.nid, e.scope, "writer", g["root_node_id"], {"expected_version": 1, "title": "Changed direction", "fields": {"goal": "A different goal"}})
    assert e.service.proposal(e.nid, e.scope, approved["id"])["stale"]
    e.service.transition_node(e.nid, e.scope, "writer", child["id"], "archive", 2)
    with pytest.raises(ValueError, match="restore archived"):
        e.service.edit_node(e.nid, e.scope, "writer", child["id"], {"expected_version": 3, "title": "Cannot unarchive by PUT"})

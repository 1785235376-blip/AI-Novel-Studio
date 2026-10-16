"""World semantic state uses only reviewed, version-fenced experimental Canon."""
import copy
import threading

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.experimental.common import StaleSourceError
from app.experimental.store import ExperimentalStore
from app.experimental.world import WorldService, WorldRecordIn
from app.experimental.world_api import create_world_router
from app.services.v1_capability_service import CapabilityVersionConflict
from test_r3_planning import planning_env


@pytest.fixture
def world_env(planning_env):
    planning_env.world = WorldService(planning_env.store, planning_env.novels, planning_env.chapter_service)
    return planning_env


def record(e, kind, data, chapter=0, **kwargs):
    return e.world.create_record(e.nid, e.scope, "writer", {"kind": kind, "title": kind.title(), "data": data, "chapter_id": e.order[chapter - 1] if chapter else None, **kwargs})


def approve(e, row):
    return e.world.review(e.nid, e.scope, "reviewer", row["id"], "approve", row["version"])


def codes(e, include_candidates=False):
    return {finding["code"] for finding in e.world.continuity(e.nid, e.scope, include_candidates)["items"]}


def test_world_canon_requires_review_restart_and_never_mutates_legacy(world_env):
    e = world_env
    original = copy.deepcopy((e.rows, e.chapters))
    candidate = record(e, "CHARACTER_EVENT", {"character_id": "alice", "event": "DEATH"}, 1)
    assert candidate["status"] == "REVIEW"
    assert e.world.canon(e.nid, e.scope) == []
    assert e.world.character_state(e.nid, e.scope, "alice", e.order[1])["life_state"] == "UNSPECIFIED"
    approved = approve(e, candidate)
    assert approved["canon_state"] == "CANON"
    canon = e.world.canon(e.nid, e.scope)
    assert len(canon) == 1 and canon[0]["source_record_id"] == candidate["id"] and not canon[0]["stale"]
    restarted = WorldService(ExperimentalStore(e.root, e.backend, e.url), e.novels, e.chapter_service)
    assert restarted.character_state(e.nid, e.scope, "alice", e.order[1])["life_state"] == "DEAD"
    assert (e.rows, e.chapters) == original
    with pytest.raises(ValueError, match="immutable"):
        e.world.edit_record(e.nid, e.scope, "writer", approved["id"], {"kind": "CHARACTER_EVENT", "title": "No silent change", "chapter_id": e.order[0], "data": {"character_id": "alice", "event": "REVIVAL"}, "expected_version": 2})


def test_world_death_appearance_and_explained_revival(world_env):
    e = world_env
    approve(e, record(e, "CHARACTER_EVENT", {"character_id": "alice", "event": "DEATH"}, 1))
    appearance = record(e, "CHARACTER_EVENT", {"character_id": "alice", "event": "APPEARANCE"}, 2)
    assert "DEAD_CHARACTER_APPEARANCE" not in codes(e)
    assert "DEAD_CHARACTER_APPEARANCE" in codes(e, True)
    approve(e, appearance)
    assert "DEAD_CHARACTER_APPEARANCE" in codes(e)
    approve(e, record(e, "CHARACTER_EVENT", {"character_id": "alice", "event": "REVIVAL", "explanation": "The approved resurrection ritual"}, 3))
    later = approve(e, record(e, "CHARACTER_EVENT", {"character_id": "alice", "event": "APPEARANCE"}, 4))
    findings = e.world.continuity(e.nid, e.scope)["items"]
    assert not any(f["record_id"] == later["id"] for f in findings)
    assert e.world.character_state(e.nid, e.scope, "alice", e.order[1])["life_state"] == "DEAD"
    assert e.world.character_state(e.nid, e.scope, "alice", e.order[3])["life_state"] == "ALIVE"


def test_world_geography_organization_and_temporal_event_relations(world_env):
    e = world_env
    a = approve(e, record(e, "CIVILIZATION", {"name": "North", "organization_type": "FACTION", "location_ids": ["region"]}))
    b = approve(e, record(e, "CIVILIZATION", {"name": "South", "parent_id": a["id"]}))
    first = approve(e, record(e, "GEOGRAPHY", {"location_id": "city", "region_id": "region", "owner_id": a["id"], "relations": [{"location_id": "region", "relation": "CONNECTED"}]}, 1))
    second = approve(e, record(e, "GEOGRAPHY", {"location_id": "city", "region_id": "region", "owner_id": b["id"]}, 2))
    assert "LOCATION_OWNERSHIP_CONFLICT" in codes(e)
    approve(e, record(e, "GEOGRAPHY", {"location_id": "city", "region_id": "region", "owner_id": a["id"], "supersedes_id": second["id"], "explanation": "Peace treaty"}, 3))
    assert len([f for f in e.world.continuity(e.nid, e.scope)["items"] if f["code"] == "LOCATION_OWNERSHIP_CONFLICT"]) == 1
    event = approve(e, record(e, "HISTORY", {"time": 100, "character_ids": ["alice"], "location_ids": ["city"]}))
    approve(e, record(e, "HISTORY", {"time": 200, "relations": [{"event_id": event["id"], "relation": "BEFORE"}]}))
    assert "HISTORY_TEMPORAL_CONFLICT" in codes(e)
    with pytest.raises(ValueError, match="contain itself"):
        record(e, "GEOGRAPHY", {"location_id": "city", "region_id": "city"})
    with pytest.raises(ValueError): record(e, "HISTORY", {"time": 200, "end_time": 100})


def test_world_ability_constraints_costs_and_rule_conflicts(world_env):
    e = world_env
    fire = approve(e, record(e, "ABILITY", {"name": "Fire", "limits": {"range": 10}, "costs": {"energy": 3}, "forbidden_actions": ["teleport"]}))
    ice = approve(e, record(e, "ABILITY", {"name": "Ice", "conflicts_with": [fire["id"]]}))
    use = approve(e, record(e, "ABILITY_USE", {"character_id": "alice", "rule_id": fire["id"], "metrics": {"range": 11}, "actions": ["teleport"], "cost_paid": {"energy": 2}}, 2))
    approve(e, record(e, "ABILITY_USE", {"character_id": "alice", "rule_id": ice["id"]}, 2))
    findings = e.world.continuity(e.nid, e.scope)["items"]
    assert {"ABILITY_LIMIT_VIOLATION", "ABILITY_RULE_CONFLICT"} <= {f["code"] for f in findings}
    violation = next(f for f in findings if f["record_id"] == use["id"] and f["code"] == "ABILITY_LIMIT_VIOLATION")
    assert all(text in violation["message"] for text in ["range", "teleport", "cost:energy"])
    assert violation["related_record_ids"] == [fire["id"]]
    with pytest.raises(ValueError): record(e, "ABILITY", {"name": "Infinite", "limits": {"x": float("inf")}})


def test_world_character_snapshots_arcs_relationship_evolution_and_reversal(world_env):
    e = world_env
    first = approve(e, record(e, "PSYCHOLOGY", {"character_id": "alice", "state": "Hopeful", "arc_id": "trust", "arc_stage": 1}, 1))
    last = approve(e, record(e, "PSYCHOLOGY", {"character_id": "alice", "state": "Bitter", "from_state": "Hopeful", "arc_id": "trust", "arc_stage": 3, "previous_snapshot_id": first["id"]}, 3))
    relationship = approve(e, record(e, "RELATIONSHIP", {"source_character_id": "alice", "target_character_id": "bob", "state": "Friends"}, 1))
    approve(e, record(e, "RELATIONSHIP", {"source_character_id": "alice", "target_character_id": "bob", "from_state": "Friends", "state": "Enemies", "previous_record_id": relationship["id"]}, 3))
    at_two = e.world.character_state(e.nid, e.scope, "alice", e.order[1])
    assert at_two["psychology"]["state"] == "Hopeful"
    assert at_two["relationships"]["alice->bob"]["state"] == "Friends"
    at_three = e.world.character_state(e.nid, e.scope, "alice", e.order[2])
    assert at_three["psychology"]["state"] == "Bitter" and len(at_three["arcs"]["trust"]) == 2
    approve(e, record(e, "PSYCHOLOGY", {"character_id": "alice", "state": "Trusting", "arc_id": "trust", "previous_snapshot_id": last["id"]}, 2))
    assert "CHARACTER_STATE_TIME_REVERSAL" in codes(e)
    with pytest.raises(ValueError, match="same character"):
        record(e, "PSYCHOLOGY", {"character_id": "bob", "state": "Wrong predecessor", "arc_id": "trust", "previous_snapshot_id": first["id"]}, 2)


def test_world_source_hash_version_order_and_transitive_stale_fences(world_env):
    e = world_env
    ability = approve(e, record(e, "ABILITY", {"name": "Power"}, 1))
    use = record(e, "ABILITY_USE", {"character_id": "alice", "rule_id": ability["id"]}, 2)
    e.chapters[e.order[0]]["content"] += " changed"
    assert e.world.record(e.nid, e.scope, ability["id"])["stale"]
    assert e.world.record(e.nid, e.scope, use["id"])["stale"]
    with pytest.raises(StaleSourceError): approve(e, use)
    assert "STALE_SOURCE" in codes(e, True)
    e.chapters[e.order[0]]["content"] = "Synthetic chapter 1"
    assert not e.world.record(e.nid, e.scope, use["id"])["stale"]
    e.order[0], e.order[1] = e.order[1], e.order[0]
    assert e.world.record(e.nid, e.scope, ability["id"])["stale"]
    assert e.world.record(e.nid, e.scope, use["id"])["stale"]
    with pytest.raises(StaleSourceError): approve(e, use)


def test_world_history_reopen_edit_and_canon_archival_are_explicit(world_env):
    e = world_env
    row = record(e, "ABILITY", {"name": "Power"})
    row = e.world.review(e.nid, e.scope, "reviewer", row["id"], "reject", 1)
    assert row["status"] == "REJECTED"
    row = e.world.review(e.nid, e.scope, "reviewer", row["id"], "reopen", 2)
    assert row["status"] == "REVIEW"
    row = e.world.edit_record(e.nid, e.scope, "writer", row["id"], {"title": "Revised", "kind": "ABILITY", "data": {"name": "Revised power"}, "expected_version": 3})
    row = approve(e, row)
    assert len(e.world.history(e.nid, e.scope, row["id"])) == 4
    row = e.world.review(e.nid, e.scope, "writer", row["id"], "archive", row["version"])
    assert not e.world.canon(e.nid, e.scope)
    row = e.world.review(e.nid, e.scope, "reviewer", row["id"], "reopen", row["version"])
    assert not e.world.canon(e.nid, e.scope)
    row = approve(e, row)
    assert len(e.world.canon(e.nid, e.scope)) == 1
    assert row["canon_id"] == e.world.canon(e.nid, e.scope)[0]["id"]


def test_world_atomic_approval_crash_and_concurrent_cas(world_env, monkeypatch):
    e = world_env
    row = record(e, "ABILITY", {"name": "Durable power"})
    import app.experimental.world as module
    original = module.new_row
    def fail(*args, **kwargs): raise RuntimeError("synthetic failure before Canon commit")
    monkeypatch.setattr(module, "new_row", fail)
    with pytest.raises(RuntimeError): approve(e, row)
    assert e.world.record(e.nid, e.scope, row["id"])["status"] == "REVIEW"
    assert not e.world.canon(e.nid, e.scope)
    monkeypatch.setattr(module, "new_row", original)
    barrier, results = threading.Barrier(3), []
    def run():
        service = WorldService(ExperimentalStore(e.root, e.backend, e.url), e.novels, e.chapter_service)
        barrier.wait()
        try:
            service.review(e.nid, e.scope, "reviewer", row["id"], "approve", 1)
            results.append("approved")
        except (ValueError, CapabilityVersionConflict): results.append("conflict")
        except Exception as exc: results.append(type(exc).__name__)
    workers = [threading.Thread(target=run) for _ in range(2)]
    for worker in workers: worker.start()
    barrier.wait()
    for worker in workers: worker.join(15)
    assert sorted(results) == ["approved", "conflict"]
    assert len(e.world.canon(e.nid, e.scope)) == 1
    assert len(e.world.history(e.nid, e.scope, row["id"])) == 1


def test_world_api_contract_authorization_scope_and_stale(world_env):
    e = world_env
    controls = {"enabled": True, "review": True}
    def flag(name):
        assert name == "world_character_engines_v2"
        if not controls["enabled"]: raise HTTPException(404, "disabled")
    def authorize(nid, token, branch, permission):
        if token != "session" or (permission == "domain.review" and not controls["review"]): raise HTTPException(403, "denied")
        return "actor", e.scope if not branch else {"mode": "collaboration", "novel_id": nid, "workspace_id": "w", "storyline_id": "s", "branch_id": branch}
    app = FastAPI()
    app.include_router(create_world_router(e.world, authorize, flag))
    client = TestClient(app)
    base, headers = f"/novels/{e.nid}/experimental/world", {"X-Session-Token": "session"}
    controls["enabled"] = False
    assert client.get(base + "/records", headers=headers).status_code == 404
    controls["enabled"] = True
    assert client.get(base + "/records").status_code == 403
    schemas = client.get(base + "/schema", headers=headers).json()
    assert set(schemas["kinds"]) >= {"HISTORY", "GEOGRAPHY", "CIVILIZATION", "ABILITY", "PSYCHOLOGY"}
    body = {"kind": "CHARACTER_EVENT", "title": "Death", "chapter_id": e.order[0], "data": {"character_id": "alice", "event": "DEATH"}}
    assert client.post(base + "/records", json={**body, "status": "APPROVED"}, headers=headers).status_code == 422
    assert client.post(base + "/records", json={**body, "data": {"character_id": "forged", "event": "DEATH"}}, headers=headers).status_code == 422
    created = client.post(base + "/records", json=body, headers=headers)
    assert created.status_code == 201
    rid = created.json()["id"]
    assert client.get(base + f"/records/{rid}", headers={**headers, "X-Branch-ID": "another"}).status_code == 404
    assert client.post(base + "/records", json=body, headers={**headers, "X-Branch-ID": "another"}).status_code == 422
    controls["review"] = False
    assert client.post(base + f"/records/{rid}/approve", json={"expected_version": 1}, headers=headers).status_code == 403
    controls["review"] = True
    assert client.post(base + f"/records/{rid}/approve", json={"expected_version": 99}, headers=headers).status_code == 409
    e.chapters[e.order[0]]["version"] += 1
    assert client.post(base + f"/records/{rid}/approve", json={"expected_version": 1}, headers=headers).status_code == 409
    e.chapters[e.order[0]]["version"] = 1
    assert client.post(base + f"/records/{rid}/approve", json={"expected_version": 1}, headers=headers).status_code == 200
    controls["review"] = False
    assert client.post(base + f"/records/{rid}/archive", json={"expected_version": 2}, headers=headers).status_code == 403
    assert len(client.get(base + "/canon", headers=headers).json()["items"]) == 1
    controls["review"] = True
    assert client.get(base + "/character-state", params={"character_id": "alice", "chapter_id": e.order[1]}, headers=headers).json()["life_state"] == "DEAD"
    assert len(client.get(base + f"/records/{rid}/history", headers=headers).json()["items"]) == 1
    assert len(client.get(base + "/canon", headers=headers).json()["items"]) == 1
    assert client.get(base + "/continuity", headers=headers).json()["verification"] == "DETERMINISTIC_RULES"

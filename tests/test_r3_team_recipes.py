"""File and explicit real-PostgreSQL creative team contracts, no model APIs."""
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import copy
import os
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.config import Settings
from app.experimental.common import StaleSourceError
from app.experimental.store import ExperimentalStore
from app.experimental.teams import TeamService, TeamRunIn, TEAM_RECIPES
from app.experimental.teams_api import create_team_router
from app.repositories.factory import create_repository_bundle
from app.services import NovelService, ChapterService
from app.services.v1_capability_service import CapabilityVersionConflict

TEST_URL = os.getenv("TEST_POSTGRES_DATABASE_URL", "")


@pytest.fixture(params=[
    pytest.param("file", marks=pytest.mark.file_backend_only),
    pytest.param("postgres", marks=[pytest.mark.postgres_backend_only, pytest.mark.skipif(not TEST_URL, reason="NOT_RUN: dedicated TEST_POSTGRES_DATABASE_URL not configured")]),
])
def env(request, tmp_path):
    backend = request.param
    bundle = create_repository_bundle(Settings(storage_backend=backend, database_url=TEST_URL), data_root=tmp_path)
    novels, chapters = NovelService(bundle.novels, bundle.chapters), ChapterService(bundle.chapters)
    nid = "r3-team-" + uuid4().hex
    novels.create({"id": nid, "title": "Synthetic creative-team contract"})
    chapter = chapters.create(nid, {"title": "Original", "content": "The cartographer enters a city.\nA letter reveals a secret."})
    chapter = chapters.get(chapter["id"])
    scope = {"mode": "local", "novel_id": nid}
    store = ExperimentalStore(tmp_path, backend=backend, database_url=TEST_URL)
    service = TeamService(store, novels, chapters, host_id="first-host")
    seeded = SimpleNamespace(backend=backend, root=tmp_path, bundle=bundle, novels=novels, chapters=chapters,
                             nid=nid, cid=chapter["id"], scope=scope, actor="author-test", store=store, service=service)
    seeded.create = lambda recipe="outline_chapter_editor": service.create_run(nid, scope, seeded.actor, TeamRunIn(recipe_id=recipe, chapter_ids=[chapter["id"]]))
    seeded.reopen = lambda: TeamService(ExperimentalStore(tmp_path, backend=backend, database_url=TEST_URL), novels, chapters, host_id="restarted-host")
    try:
        yield seeded
    finally:
        if backend == "postgres":
            # Cleanup only this fixture's unique synthetic project and scopes.
            with store._connect() as conn:
                conn.execute("DELETE FROM experimental_scope_documents WHERE novel_id = %s", (nid,))
            novels.delete(nid)
            bundle.novels.database.engine.dispose()


def action(env, row, name, service=None):
    return (service or env.service).transition(env.nid, env.scope, env.actor, row["id"], name, row["version"])


def complete(env, row, node_id, service=None, **overrides):
    service = service or env.service
    state = row["node_states"][node_id]
    kwargs = {"nid": env.nid, "scope": env.scope, "actor": env.actor, "run_id": row["id"], "node_id": node_id,
              "expected_version": row["version"], "execution_token": state["execution_token"], "context_hash": row["context_hash"],
              "output": service._contract_output(row, node_id)}
    kwargs.update(overrides)
    return service.complete_node(**kwargs)


@pytest.mark.parametrize("recipe", [row["id"] for row in TEAM_RECIPES])
def test_all_roles_recipes_and_review_only_outputs(env, recipe):
    assert len(env.service.catalog()["roles"]) == 8
    original = copy.deepcopy(env.chapters.get(env.cid))
    canon_before = env.novels.data_set(env.nid, "canon")
    row = env.create(recipe)
    assert row["execution_scope"]["project_id"] == env.nid
    assert row["execution_scope"]["branch_id"] == "local"
    row = action(env, row, "execute")
    assert row["status"] == "WAITING_APPROVAL"
    assert len(row["artifacts"]) == len(row["node_states"]) - 1
    assert all(artifact["status"] == "PROPOSED" and not artifact["applied"] for artifact in row["artifacts"].values())
    items = env.service.list_review_items(env.nid, env.scope)
    assert items[0]["id"] == row["id"] and items[0]["status"] == "PENDING"
    assert not items[0]["batch_safe"] and not items[0]["stale"]
    row = env.service.review(env.nid, env.scope, env.actor, row["id"], "approve", row["version"])
    assert row["status"] == "SUCCEEDED"
    assert all(artifact["status"] == "APPROVED" and not artifact["applied"] for artifact in row["artifacts"].values())
    assert row["verification"] == "CONTRACT_VERIFIED" and row["external_calls"] == 0
    assert env.chapters.get(env.cid) == original
    assert env.novels.data_set(env.nid, "canon") == canon_before
    reopened = env.reopen().get_run(env.nid, env.scope, row["id"])
    assert reopened["version"] == row["version"] and reopened["history"]


def test_pause_resume_cancel_retry_and_review_reopen(env):
    row = env.create()
    row = action(env, row, "pause")
    assert row["status"] == "PAUSED"
    row = action(env, row, "resume")
    assert row["status"] == "RUNNING"
    row = action(env, row, "cancel")
    assert row["status"] == "CANCELLED"
    row = action(env, row, "retry")
    assert row["attempt"] == 2
    row = action(env, row, "execute")
    row = action(env, row, "pause")
    row = action(env, row, "resume")
    assert row["status"] == "WAITING_APPROVAL"
    for decision, status in [("reject", "REJECTED"), ("reopen", "WAITING_APPROVAL"), ("approve", "SUCCEEDED"), ("reopen", "WAITING_APPROVAL")]:
        row = env.service.review(env.nid, env.scope, env.actor, row["id"], decision, row["version"])
        assert row["status"] == status


@pytest.mark.parametrize("fence", ["version", "token", "hash", "actor", "scope", "project", "source", "cancel", "pause"])
def test_late_or_cross_scope_callbacks_fail_closed(env, fence):
    row = env.create()
    row = env.service.claim_node(env.nid, env.scope, env.actor, row["id"], "outline", row["version"])
    kwargs = {}
    if fence == "version": kwargs["expected_version"] = row["version"] - 1
    elif fence == "token": kwargs["execution_token"] = str(uuid4())
    elif fence == "hash": kwargs["context_hash"] = "0" * 64
    elif fence == "actor": kwargs["actor"] = "another-author"
    elif fence == "scope": kwargs["scope"] = {**env.scope, "branch_id": "another-branch"}
    elif fence == "project": kwargs["nid"] = "missing-project"
    elif fence == "source": env.chapters.save(env.cid, {"content": "NEW AUTHOR EDIT", "version": 1})
    elif fence in {"cancel", "pause"}:
        changed = action(env, row, fence)
        kwargs["expected_version"] = changed["version"]
    with pytest.raises((ValueError, FileNotFoundError, CapabilityVersionConflict)):
        complete(env, row, "outline", **kwargs)
    assert env.service.get_run(env.nid, env.scope, row["id"])["artifacts"] == {}


def test_source_stale_blocks_approval_retry_and_is_visible_in_inbox(env):
    row = action(env, env.create(), "execute")
    env.chapters.save(env.cid, {"content": "Changed chapter", "version": 1})
    assert env.service.list_review_items(env.nid, env.scope)[0]["stale"]
    with pytest.raises(StaleSourceError):
        env.service.review(env.nid, env.scope, env.actor, row["id"], "approve", row["version"])
    row = action(env, row, "cancel")
    with pytest.raises(StaleSourceError): action(env, row, "retry")


def test_restart_unknown_outcome_requires_explicit_retry_and_fences_old_attempt(env):
    row = env.create()
    claimed = env.service.claim_node(env.nid, env.scope, env.actor, row["id"], "outline", row["version"])
    restarted = env.reopen()
    assert restarted.get_run(env.nid, env.scope, row["id"])["recovery_required"]
    with pytest.raises(ValueError, match="no longer authorized"):
        complete(env, claimed, "outline", restarted)
    row = action(env, claimed, "recover", restarted)
    assert row["status"] == "FAILED" and row["node_states"]["outline"]["error"]["replay_safe"] is False
    row = action(env, row, "retry", restarted)
    new_claim = restarted.claim_node(env.nid, env.scope, env.actor, row["id"], "outline", row["version"])
    with pytest.raises(ValueError):
        complete(env, claimed, "outline", expected_version=new_claim["version"])
    assert new_claim["node_states"]["outline"]["attempt"] == 2
    completed = complete(env, new_claim, "outline", restarted)
    assert len(completed["artifacts"]) == 1


def test_recovery_never_steals_this_hosts_live_claim(env):
    row = env.create()
    row = env.service.claim_node(env.nid, env.scope, env.actor, row["id"], "outline", row["version"])
    with pytest.raises(ValueError, match="host still owns"):
        action(env, row, "recover")
    paused = action(env, row, "pause")
    resumed = action(env, paused, "resume")
    assert resumed["status"] == "FAILED"
    retried = action(env, resumed, "retry")
    assert retried["node_states"]["outline"]["status"] == "READY"


def test_crash_after_commit_before_response_does_not_lose_or_duplicate_output(env, monkeypatch):
    row = env.create()
    row = env.service.claim_node(env.nid, env.scope, env.actor, row["id"], "outline", row["version"])
    original = env.service.mutate
    def commit_then_disconnect(*args, **kwargs):
        original(*args, **kwargs)
        raise ConnectionError("simulated response gap after durable commit")
    monkeypatch.setattr(env.service, "mutate", commit_then_disconnect)
    with pytest.raises(ConnectionError): complete(env, row, "outline")
    restarted = env.reopen()
    persisted = restarted.get_run(env.nid, env.scope, row["id"])
    assert persisted["node_states"]["outline"]["status"] == "SUCCEEDED"
    assert len(persisted["artifacts"]) == 1
    with pytest.raises(CapabilityVersionConflict): complete(env, row, "outline", restarted)
    final = action(env, persisted, "execute", restarted)
    assert final["status"] == "WAITING_APPROVAL" and len(final["artifacts"]) == 3
    assert final["node_states"]["outline"]["attempt"] == 1


def test_recovery_advances_persisted_receipt_without_dispatch(env):
    row = env.create()
    row = env.service.claim_node(env.nid, env.scope, env.actor, row["id"], "outline", row["version"])
    row = complete(env, row, "outline")
    with env.store.transaction(env.nid, env.scope) as doc:
        saved = doc["collections"]["team_runs"][row["id"]]
        saved["node_states"]["outline"]["status"] = "RESULT_READY"
        saved["node_states"]["chapter_draft"]["status"] = "PENDING"
    restarted = env.reopen()
    result = action(env, row, "recover", restarted)
    assert result["node_states"]["outline"]["status"] == "SUCCEEDED"
    assert result["node_states"]["outline"]["attempt"] == 1
    assert result["node_states"]["chapter_draft"]["status"] == "READY"
    assert len(result["artifacts"]) == 1


def test_concurrent_claim_exactly_one_wins_durably(env):
    row = env.create()
    other = env.reopen()
    def claim(service):
        try:
            return service.claim_node(env.nid, env.scope, env.actor, row["id"], "outline", row["version"])["version"]
        except CapabilityVersionConflict:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, [env.service, other]))
    assert sorted(results, key=str) == [2, "conflict"]
    assert env.reopen().get_run(env.nid, env.scope, row["id"])["node_states"]["outline"]["attempt"] == 1


def test_malformed_output_rolls_back_receipt_artifact_and_version(env):
    row = env.create()
    row = env.service.claim_node(env.nid, env.scope, env.actor, row["id"], "outline", row["version"])
    output = env.service._contract_output(row, "outline")
    output["agent_id"] = "writer"
    with pytest.raises(ValueError): complete(env, row, "outline", output=output)
    assert env.service.get_run(env.nid, env.scope, row["id"])["version"] == row["version"]
    assert env.service.get_run(env.nid, env.scope, row["id"])["artifacts"] == {}


def test_source_text_only_contract_and_unknown_recipe_validation(env):
    row = env.service.create_run(env.nid, env.scope, env.actor, {"recipe_id": "screenplay_shots", "source_text": "A supplied scene."})
    assert row["sources"] == {}
    assert action(env, row, "execute")["status"] == "WAITING_APPROVAL"
    for data in [{"recipe_id": "missing", "instruction": "Write"}, {"recipe_id": "continuity_fix"}, {"recipe_id": "continuity_fix", "source_text": "x", "actor": "spoof"}]:
        with pytest.raises(ValueError): env.service.create_run(env.nid, env.scope, env.actor, data)


def test_http_feature_gate_authority_version_and_review(env):
    enabled = [False]
    access_log = []
    def flag(name):
        assert name == "agent_team_recipes"
        if not enabled[0]: raise HTTPException(404, "FEATURE_DISABLED")
    def authorize(nid, token, branch, permission):
        access_log.append(permission)
        if token != "test-session": raise HTTPException(401, "SESSION_REQUIRED")
        if branch != "test-branch": raise HTTPException(403, "SCOPE_MISMATCH")
        assert nid == env.nid
        return env.actor, env.scope
    app = FastAPI()
    app.include_router(create_team_router(env.service, authorize, flag))
    client = TestClient(app)
    base = f"/novels/{env.nid}/experimental/teams"
    headers = {"x-session-token": "test-session", "x-branch-id": "test-branch"}
    assert client.get(base + "/catalog", headers=headers).status_code == 404
    enabled[0] = True
    assert client.get(base + "/catalog").status_code == 401
    assert len(client.get(base + "/catalog", headers=headers).json()["roles"]) == 8
    response = client.post(base + "/runs", headers=headers, json={"recipe_id": "continuity_fix", "chapter_ids": [env.cid]})
    assert response.status_code == 201
    row = response.json()
    url = base + "/runs/" + row["id"]
    assert client.post(url + "/execute", headers=headers, json={"expected_version": 99}).status_code == 409
    row = client.post(url + "/execute", headers=headers, json={"expected_version": row["version"]}).json()
    assert row["status"] == "WAITING_APPROVAL"
    row = client.post(url + "/review/approve", headers=headers, json={"expected_version": row["version"]}).json()
    assert row["status"] == "SUCCEEDED"
    assert client.get(url + "/history", headers=headers).json()["items"]
    assert {"domain.write", "domain.read", "domain.review"} <= set(access_log)


def test_branch_chapter_input_fails_closed_but_explicit_text_is_isolated(env):
    branch = {"mode": "collaboration", "novel_id": env.nid, "workspace_id": "workspace-test", "storyline_id": "story-test", "branch_id": "branch-test"}
    with pytest.raises(StaleSourceError, match="branch chapter snapshots"):
        env.service.create_run(env.nid, branch, env.actor, {"recipe_id": "continuity_fix", "chapter_ids": [env.cid]})
    row = env.service.create_run(env.nid, branch, env.actor, {"recipe_id": "continuity_fix", "source_text": "Explicit branch-author input."})
    assert row["execution_scope"]["branch_id"] == "branch-test"
    assert env.service.list_runs(env.nid, env.scope)["items"] == []
    with pytest.raises(FileNotFoundError):
        env.service.get_run(env.nid, {**branch, "branch_id": "other-branch"}, row["id"])
    result = env.service.execute(env.nid, branch, env.actor, row["id"], row["version"])
    assert result["status"] == "WAITING_APPROVAL"


def test_execute_revoked_authority_discards_late_output(env):
    row = env.create()
    checks = []
    def reauthorize():
        checks.append(True)
        if len(checks) == 2:
            raise PermissionError("membership revoked while executing")
    with pytest.raises(PermissionError):
        env.service.execute(env.nid, env.scope, env.actor, row["id"], row["version"], check_authority=reauthorize)
    current = env.service.get_run(env.nid, env.scope, row["id"])
    assert current["artifacts"] == {}
    assert current["node_states"]["outline"]["status"] == "WORKING"


def test_explicit_branch_reader_never_substitutes_base_manuscript(env):
    branch = {"mode": "collaboration", "novel_id": env.nid, "workspace_id": "workspace-test", "storyline_id": "story-test", "branch_id": "branch-test"}
    branch_chapter = {**env.chapters.get(env.cid), "content": "A BRANCH-SPECIFIC synthetic source", "version": 8}
    seen = []
    def branch_reader(scope):
        seen.append(scope)
        assert scope == branch
        return SimpleNamespace(get=lambda cid: copy.deepcopy(branch_chapter))
    service = TeamService(env.store, env.novels, env.chapters, host_id="branch-host", branch_chapters=branch_reader)
    row = service.create_run(env.nid, branch, env.actor, {"recipe_id": "continuity_fix", "chapter_ids": [env.cid]})
    assert row["source_text"] == branch_chapter["content"]
    assert row["sources"][env.cid]["version"] == 8
    row = service.execute(env.nid, branch, env.actor, row["id"], row["version"])
    branch_chapter["version"] += 1
    with pytest.raises(StaleSourceError):
        service.review(env.nid, branch, env.actor, row["id"], "approve", row["version"])
    assert seen
    assert "BRANCH-SPECIFIC" not in env.chapters.get(env.cid)["content"]


def test_retry_preserves_completed_nodes_and_failed_claim_creates_no_artifact(env):
    row = env.create()
    row = env.service.claim_node(env.nid, env.scope, env.actor, row["id"], "outline", row["version"])
    row = complete(env, row, "outline")
    receipt = copy.deepcopy(row["node_states"]["outline"]["receipt"])
    row = env.service.claim_node(env.nid, env.scope, env.actor, row["id"], "chapter_draft", row["version"])
    row = complete(env, row, "chapter_draft", output=None, error="synthetic failure")
    assert row["status"] == "FAILED" and len(row["artifacts"]) == 1
    row = action(env, row, "retry")
    row = action(env, row, "execute")
    assert row["status"] == "WAITING_APPROVAL" and len(row["artifacts"]) == 3
    assert row["node_states"]["outline"]["receipt"] == receipt
    assert row["node_states"]["chapter_draft"]["attempt"] == 2


def test_recovery_rejects_corrupt_receipt_without_advancing(env):
    row = env.create()
    row = env.service.claim_node(env.nid, env.scope, env.actor, row["id"], "outline", row["version"])
    row = complete(env, row, "outline")
    with env.store.transaction(env.nid, env.scope) as doc:
        saved = doc["collections"]["team_runs"][row["id"]]
        saved["node_states"]["outline"]["status"] = "RESULT_READY"
        saved["node_states"]["outline"]["receipt"]["output_hash"] = "0" * 64
        saved["node_states"]["chapter_draft"]["status"] = "PENDING"
    with pytest.raises(ValueError, match="incomplete or inconsistent"):
        action(env, row, "recover", env.reopen())
    current = env.reopen().get_run(env.nid, env.scope, row["id"])
    assert current["version"] == row["version"]
    assert current["node_states"]["chapter_draft"]["status"] == "PENDING"

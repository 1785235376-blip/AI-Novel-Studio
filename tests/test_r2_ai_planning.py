import copy
import json
import threading
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.ai_planning_api import create_ai_planning_router
from app.model_runtime import TextGenerationResponse, TextModelNodeOutput
from app.planning_extraction import extract_explicit_planning
from app.services.ai_planning_service import AIPlanningService, PlanningRunIn
from app.services.creation_workbench_service import CreationWorkbenchService, WorkbenchRecordIn
from app.services.v1_capability_service import V1CapabilityService, CapabilityVersionConflict
from app.source_privacy import content_digest, review_source_privacy


@pytest.fixture
def setup(tmp_path):
    chapter = {"id": "n:1", "novel_id": "n", "version": 1, "title": "章一", "content": "Alice said hello. 世界规则：须付出代价。\n"}
    records = {}
    novels = SimpleNamespace(get=lambda nid: {"id": nid}, data_set=lambda nid, kind: copy.deepcopy(records.get(kind, [])), public_secrets=lambda nid: [], outline=lambda nid: None)
    novels.novels = SimpleNamespace(get_context_sources=lambda nid: {"secrets": records.get("secrets", [])}, get_data_set=lambda nid, kind: copy.deepcopy(records.get(kind, [])))
    chapters = SimpleNamespace(get=lambda cid: copy.deepcopy(chapter))
    store = V1CapabilityService(tmp_path, novels, chapters, None)
    workbench = CreationWorkbenchService(store, chapters, novels)
    runtime = SimpleNamespace(calls=[], cloud=False)
    runtime.is_remote_text_provider = lambda provider: runtime.cloud
    def execute(value):
        runtime.calls.append(value.request)
        response = TextGenerationResponse(runtime.output, "completed", value.request.provider_id, value.request.model_id, execution_mode="mock_standin")
        return TextModelNodeOutput(response.text, response, value.request.job_id)
    runtime.node = SimpleNamespace(execute=execute)
    runtime.prepare_text_route = lambda *args: runtime.node
    runtime.output = json.dumps({"candidates": [{"record": {"kind": "STYLE", "title": "短句", "instructions": "使用短句"}, "evidence": [{"chapter_id": "n:1", "start": 0, "end": 5, "quote": "Alice"}]}]})
    service = AIPlanningService(workbench, runtime)
    return SimpleNamespace(service=service, chapter=chapter, runtime=runtime, workbench=workbench, scope=workbench.local_scope("n"), root=tmp_path, records=records)


def create(env, **kwargs):
    body = PlanningRunIn.model_validate({"kind": "STYLE", "provider_id": "configured-local", "model_id": "model", "sources": [{"chapter_id": "n:1", "expected_version": env.chapter["version"]}], **kwargs})
    return env.service.create("n", env.scope, "author", body, start=False)


def execute(env, **kwargs):
    row = create(env, **kwargs)
    return env.service.execute("n", env.scope, row["id"])


def test_model_output_persists_as_reviewable_candidates_then_draft_only(setup):
    env = setup
    row = execute(env)
    assert row["status"] == "READY"
    assert row["execution_mode"] == "mock_standin" and row["usage_status"] == "UNKNOWN"
    assert len(env.runtime.calls) == 1
    assert not env.workbench.list_records("n", env.scope)["items"]
    assert env.chapter["version"] == 1
    restarted = AIPlanningService(env.workbench, env.runtime)
    assert restarted.get("n", env.scope, row["id"])["candidates"] == row["candidates"]
    result = restarted.save_candidate("n", env.scope, "author", row["id"], row["candidates"][0]["id"], row["version"])
    saved = result["record"]
    assert saved["status"] == "DRAFT" and saved["privacy_level"] == "LOCAL_ONLY"
    assert saved["source_provenance"]["sources"][0]["content_sha256"] == content_digest(env.chapter)
    assert saved["source_provenance"]["evidence"][0]["quote"] == "Alice"
    with pytest.raises(ValueError):
        env.workbench.generation_inputs("n", env.scope, saved["id"])
    approved = env.workbench.transition_record("n", env.scope, "author", saved["id"], "approve", 1)
    assert approved["status"] == "APPROVED"
    assert env.workbench.generation_inputs("n", env.scope, saved["id"])["style"] == "使用短句"


@pytest.mark.parametrize("change", ["version", "hash"])
def test_source_change_without_or_with_version_blocks_dispatch_and_approval(setup, change):
    env = setup
    row = create(env)
    if change == "version": env.chapter["version"] += 1
    else: env.chapter["content"] += "changed"
    result = env.service.execute("n", env.scope, row["id"])
    assert result["status"] == "FAILED" and not env.runtime.calls
    row = execute(env)
    saved = env.service.save_candidate("n", env.scope, "author", row["id"], row["candidates"][0]["id"], row["version"])["record"]
    env.chapter["content"] += "modified without revision"
    with pytest.raises(ValueError, match="source chapter changed"):
        env.workbench.transition_record("n", env.scope, "author", saved["id"], "approve", 1)


def test_cloud_requires_persisted_exact_branch_hash_version_review(setup):
    env = setup
    env.runtime.cloud = True
    assert execute(env)["status"] == "FAILED"
    assert not env.runtime.calls
    review_source_privacy(env.chapter, None, "author", "CLOUD_ALLOWED", 1, content_digest(env.chapter), env.root)
    assert execute(env)["status"] == "READY"
    env.scope = {"mode": "collaboration", "novel_id": "n", "branch_id": "another"}
    assert execute(env)["status"] == "FAILED"
    assert len(env.runtime.calls) == 1


def test_rechecks_policy_after_route_preparation(setup):
    env = setup
    env.runtime.cloud = True
    review_source_privacy(env.chapter, None, "author", "CLOUD_ALLOWED", 1, content_digest(env.chapter), env.root)
    def prepare(*args):
        review_source_privacy(env.chapter, None, "author", "LOCAL_ONLY", 1, content_digest(env.chapter), env.root)
        return env.runtime.node
    env.runtime.prepare_text_route = prepare
    assert execute(env)["status"] == "FAILED"
    assert not env.runtime.calls


def test_reauthorization_failure_blocks_provider_and_hides_internals(setup):
    env = setup
    row = create(env)
    def deny(): raise HTTPException(403, "private-token-and-provider-url")
    result = env.service.execute("n", env.scope, row["id"], deny)
    assert result["status"] == "FAILED" and not env.runtime.calls
    assert "private-token" not in json.dumps(result)


@pytest.mark.parametrize("output", ["not json", '{"candidates":[]}', '{"candidates":[],"manuscript":"overwrite"}'])
def test_malformed_output_is_failed_without_writes(setup, output):
    env = setup
    env.runtime.output = output
    row = execute(env)
    assert row["status"] == "FAILED" and row["error_code"] == "PLANNING_VALIDATION_FAILED"
    assert row["execution_mode"] == "mock_standin"
    assert not env.workbench.list_records("n", env.scope)["items"]


@pytest.mark.parametrize("mutate", [lambda value: value["evidence"][0].update(quote="fabricated"), lambda value: value["evidence"][0].update(chapter_id="other:1"), lambda value: value["record"].update(kind="HISTORY", description="wrong kind"), lambda value: value["record"].update(character_ids=["forged"])])
def test_hallucinated_evidence_and_refs_rejected(setup, mutate):
    env = setup
    parsed = json.loads(env.runtime.output)
    mutate(parsed["candidates"][0])
    env.runtime.output = json.dumps(parsed)
    assert execute(env)["status"] == "FAILED"
    assert not env.workbench.list_records("n", env.scope)["items"]


def test_host_overrides_model_privacy_and_chapter_references(setup):
    env = setup
    parsed = json.loads(env.runtime.output)
    parsed["candidates"][0]["record"].update(privacy_level="CLOUD_ALLOWED", chapter_ids=["invented"])
    env.runtime.output = json.dumps(parsed)
    row = execute(env)
    assert row["candidates"][0]["record"]["privacy_level"] == "LOCAL_ONLY"
    assert row["candidates"][0]["record"]["chapter_ids"] == ["n:1"]


@pytest.mark.parametrize("terminal", ["cancel", "timeout"])
def test_late_provider_response_cannot_overwrite_cancel_or_timeout(setup, terminal):
    env = setup
    entered, release = threading.Event(), threading.Event()
    original = env.runtime.node.execute
    def delayed(value):
        entered.set()
        assert release.wait(3)
        return original(value)
    env.runtime.node.execute = delayed
    row = create(env)
    worker = threading.Thread(target=env.service.execute, args=("n", env.scope, row["id"]))
    worker.start()
    assert entered.wait(2)
    working = env.service.get("n", env.scope, row["id"])
    if terminal == "cancel": env.service.cancel("n", env.scope, row["id"], working["version"])
    else: env.service._timeout("n", env.scope, row["id"])
    release.set()
    worker.join(3)
    result = env.service.get("n", env.scope, row["id"])
    assert result["status"] == ("CANCELLED" if terminal == "cancel" else "FAILED")
    assert not result["candidates"]


def test_restart_marks_interrupted_without_replay(setup):
    env = setup
    row = create(env)
    restarted = AIPlanningService(env.workbench, env.runtime)
    assert restarted.list("n", env.scope)["items"][0]["error_code"] == "INTERRUPTED"
    assert restarted.get("n", env.scope, row["id"])["status"] == "FAILED"
    assert not env.runtime.calls


def test_draft_promotion_checkpoint_retry_is_idempotent(setup, monkeypatch):
    env = setup
    row = execute(env)
    original = env.service._save
    monkeypatch.setattr(env.service, "_save", lambda rows: (_ for _ in ()).throw(OSError("checkpoint write failure")))
    with pytest.raises(OSError):
        env.service.save_candidate("n", env.scope, "author", row["id"], row["candidates"][0]["id"], row["version"])
    assert len(env.workbench.list_records("n", env.scope)["items"]) == 1
    monkeypatch.setattr(env.service, "_save", original)
    env.service.save_candidate("n", env.scope, "author", row["id"], row["candidates"][0]["id"], row["version"])
    assert len(env.workbench.list_records("n", env.scope)["items"]) == 1
    with pytest.raises(CapabilityVersionConflict):
        env.service.save_candidate("n", env.scope, "author", row["id"], row["candidates"][0]["id"], row["version"])


def test_local_explicit_rule_dedup_and_plot_evidence(setup):
    env = setup
    env.chapter["content"] = "世界规则：魔法需要代价。\nWorld rule: Magic needs a cost.\n世界规则：魔法需要代价。\n"
    row = execute(env, mode="LOCAL_EXPLICIT", kind="ABILITY")
    assert row["status"] == "READY" and len(row["candidates"]) == 2
    assert not env.runtime.calls and row["execution_mode"] == "local_explicit"
    for candidate in row["candidates"]:
        evidence = candidate["evidence"][0]
        assert env.chapter["content"][evidence["start"]:evidence["end"]] == evidence["quote"]
    env.chapter["content"] = "第一幕：相遇\nAct 2: Battle\n第三幕：和解\n冲突：资源不足\nClimax: Victory\n结局：归乡\n"
    row = execute(env, mode="LOCAL_EXPLICIT", kind="PLOT")
    assert row["candidates"][0]["record"]["acts"] == ["相遇", "Battle", "和解"]
    assert len(row["candidates"][0]["evidence"]) == 6


def test_incomplete_or_ambiguous_plot_has_findings_no_fabricated_filler(setup):
    env = setup
    env.chapter["content"] = "第一幕：相遇\n冲突：危机\n"
    row = execute(env, mode="LOCAL_EXPLICIT", kind="PLOT")
    assert row["status"] == "READY" and not row["candidates"]
    assert row["findings"][0]["missing_fields"] == ["act2", "act3", "climax", "ending"]
    env.chapter["content"] = "Act 1: A\nAct 1: other A\nAct 2: B\nAct 3: C\nConflict: D\nClimax: E\nEnding: F\n"
    row = execute(env, mode="LOCAL_EXPLICIT", kind="PLOT")
    assert row["findings"][0]["duplicate_fields"] == ["act1"] and not row["candidates"]


def test_explicit_extractor_does_not_infer_rules_from_prose_and_large_offsets():
    chapter = {"id": "n:1", "version": 1, "content": "这是剧情中的规则。" * 4000 + "\n世界规则：保留原文\n", "novel_id": "n"}
    values, _ = extract_explicit_planning([chapter], "ABILITY")
    assert len(values) == 1 and values[0]["evidence"][0]["start"] > 16000
    assert extract_explicit_planning([{**chapter, "content": "World rule: no newline required"}], "ABILITY")[0]


def test_router_authorizes_reads_writes_and_rejects_client_scope_override(setup):
    env = setup
    permissions = []
    def authorize(nid, token, branch, permission):
        permissions.append(permission)
        if token != "valid": raise HTTPException(403, "denied")
        return "author", env.scope
    app = FastAPI()
    app.include_router(create_ai_planning_router(env.service, authorize))
    client = TestClient(app)
    assert client.get("/novels/n/planning-runs").status_code == 403
    assert client.get("/novels/n/planning-runs", headers={"X-Session-Token": "valid"}).status_code == 200
    body = {"mode": "LOCAL_EXPLICIT", "kind": "ABILITY", "sources": [{"chapter_id": "n:1", "expected_version": 1}], "allow_cloud": True}
    assert client.post("/novels/n/planning-runs", headers={"X-Session-Token": "valid"}, json=body).status_code == 422
    row = execute(env)
    response = client.post(f"/novels/n/planning-runs/{row['id']}/candidates/{row['candidates'][0]['id']}/save-draft", headers={"X-Session-Token": "valid"}, json={"expected_version": row["version"]})
    assert response.status_code == 200 and response.json()["record"]["status"] == "DRAFT"
    assert permissions[-1] == "domain.write"
    assert client.get(f"/novels/n/planning-runs/{row['id']}", headers={"X-Session-Token": "valid"}).json()["status"] == "READY"


def test_scope_isolation_and_corrupt_store_fail_closed(setup):
    env = setup
    row = execute(env)
    with pytest.raises(FileNotFoundError):
        env.service.get("n", {**env.scope, "branch_id": "other"}, row["id"])
    path = env.workbench.store._path("planning_runs")
    path.write_text("{corrupt")
    with pytest.raises(ValueError):
        create(env)
    assert path.read_text() == "{corrupt"


@pytest.mark.parametrize("policy", ["LOCAL_ONLY", "REDACT_BEFORE_CLOUD", None])
def test_cloud_source_review_does_not_override_private_project_facts(setup, policy):
    env = setup
    env.runtime.cloud = True
    review_source_privacy(env.chapter, None, "author", "CLOUD_ALLOWED", 1, content_digest(env.chapter), env.root)
    env.records["secrets"] = [{"id": "s", "privacy_level": policy}]
    assert execute(env)["status"] == "FAILED" and not env.runtime.calls
    env.records["secrets"] = [{"id": "s", "privacy_level": "CLOUD_ALLOWED"}]
    assert execute(env)["status"] == "READY" and len(env.runtime.calls) == 1


def test_explicit_markers_support_crlf_without_quote_normalization():
    chapter = {"id": "n:1", "novel_id": "n", "version": 1, "content": "世界规则：代价\r\nAct 1: begin\r\n"}
    values, _ = extract_explicit_planning([chapter], "ABILITY")
    assert values[0]["evidence"][0]["quote"] == "代价"
    evidence = values[0]["evidence"][0]
    assert chapter["content"][evidence["start"]:evidence["end"]] == "代价"

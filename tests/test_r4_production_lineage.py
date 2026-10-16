"""A09/A13 real persistence and deterministic PNG replay; no model quality claim."""
import base64
import copy
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.experimental.common import StaleSourceError
from app.experimental.media import MediaService, MediaAdapterRegistry, MockImageWorkflowAdapter
from app.experimental.production_lineage import ProductionLineageService
from app.experimental.production_lineage_api import create_production_lineage_router
from app.experimental.store import ExperimentalStore
from app.services.v1_capability_service import CapabilityVersionConflict
from app.source_privacy import content_digest, review_source_privacy
from test_r3_media_support import rig, branch_scope


@pytest.fixture
def production(rig):
    media = MediaService(rig.store, rig.novels, rig.chapters, rig.assets, rig.screenplays, production_capture_enabled=lambda: True)
    return ProductionLineageService(rig.store, rig.novels, rig.chapters, rig.assets, media)


def asset(rig, name="input.png", payload=b"synthetic asset", branch=None):
    return rig.assets.create(rig.nid, name, base64.b64encode(payload).decode(), "image/png", "image", branch_id=branch)


def declaration(version, parents=(), **kw):
    return {"expected_version": version, "origin": "DERIVED_PROCESSING" if parents else "ORIGINAL_INPUT",
            "parent_asset_ids": list(parents), "license": {"label": "Author declaration", "source": "Synthetic fixture"}, **kw}


def prepared(rig, p, **brief_args):
    brief = p.media.create_cover(rig.nid, rig.scope, rig.actor, {"title": "Synthetic cover", "prompt": "PRIVATE PROMPT /home/private sk-secret", "chapter_ids": [rig.chapter["id"]], **brief_args})
    task = p.media.queue(rig.nid, rig.scope, rig.actor, {"brief_id": brief["id"], "expected_brief_version": 1, "adapter_id": "mock-image-v1", "candidate_count": 2})
    task = p.media.execute(rig.nid, rig.scope, rig.actor, task["id"], 1)
    manifest = p.capture(rig.nid, rig.scope, rig.actor, {"task_id": task["id"], "expected_task_version": task["version"]})
    return brief, task, manifest


def new_replay(rig, p, manifest, key="replay-one", actor=None):
    actor = actor or rig.actor
    preflight = p.preflight(rig.nid, rig.scope, actor, manifest["id"], manifest["version"])
    assert preflight["ready"], preflight
    body = {"expected_version": manifest["version"], "preflight_digest": preflight["preflight_digest"], "idempotency_key": key,
            "broker_decision_id": preflight["broker_decision_id"], "broker_decision_version": preflight["broker_decision_version"]}
    return p.replay(rig.nid, rig.scope, actor, manifest["id"], body), body


def test_asset_lineage_reuses_dag_snapshots_cas_cycles_and_license(rig, production):
    p = production; a, b, c = asset(rig, "a"), asset(rig, "b"), asset(rig, "c")
    source = p.annotate(rig.nid, rig.scope, rig.actor, a["id"], declaration(1, chapter_ids=[rig.chapter["id"]]))
    derived = p.annotate(rig.nid, rig.scope, rig.actor, b["id"], declaration(1, [a["id"]]))
    assert derived["origin"] == "DERIVED_PROCESSING" and derived["parents"][0]["state"] == "CURRENT"
    stored = rig.assets.get(b["id"])
    assert stored["source_asset_ids"] == [a["id"]]
    assert stored["parameters"]["asset_lineage_v2"]["parents"][a["id"]] == {"version": source["version"], "digest": a["sha256"]}
    assert derived["license_verification"] == "AUTHOR_DECLARATION_NOT_LEGAL_VERIFICATION"
    with pytest.raises(CapabilityVersionConflict): p.annotate(rig.nid, rig.scope, rig.actor, b["id"], declaration(1, [a["id"]]))
    with pytest.raises(ValueError, match="cycle"): p.annotate(rig.nid, rig.scope, rig.actor, a["id"], declaration(source["version"], [b["id"]]))
    with pytest.raises(ValueError, match="REMOVAL"): p.annotate(rig.nid, rig.scope, rig.actor, b["id"], declaration(derived["version"]))
    p.annotate(rig.nid, rig.scope, rig.actor, c["id"], declaration(1, [b["id"]]))
    impact = p.impact(rig.nid, rig.scope, a["id"])
    assert {r["id"] for r in impact["assets"]} == {b["id"], c["id"]}
    assert impact["automatic_regeneration"] is False and impact["other_dependencies"] == "UNKNOWN"


def test_missing_deleted_and_denied_parents_remain_honest_without_identifier_leaks(rig, production):
    p = production; a, b = asset(rig, "source-secret-name"), asset(rig, "derived")
    p.annotate(rig.nid, rig.scope, rig.actor, b["id"], declaration(1, [a["id"]]))
    rig.assets.delete(a["id"])
    child = p.asset(rig.nid, rig.scope, b["id"])
    assert child["parents"][0]["state"] == "DELETED" and child["origin"] == "DERIVED_PROCESSING"
    assert rig.assets._bin_path(a["id"]).read_bytes() == b"synthetic asset"
    rig.assets.restore(a["id"])
    assert p.asset(rig.nid, rig.scope, b["id"])["parents"][0]["state"] == "STALE"
    # Simulate an imported legacy reference whose parent moved out of scope.
    meta = rig.assets.get(a["id"]); meta["branch_id"] = "private-branch"; rig.assets._write_meta(meta)
    projection = p.asset(rig.nid, rig.scope, b["id"])
    serialized = json.dumps(projection)
    assert a["id"] not in serialized and "source-secret-name" not in serialized
    assert projection["parents"] == [{"state": "UNAVAILABLE", "label": "来源不可用或无权访问"}]
    assert a["id"] not in json.dumps(p.assets_view(rig.nid, rig.scope))
    with pytest.raises(FileNotFoundError): p.asset(rig.nid, rig.scope, a["id"])


def test_asset_integrity_and_source_revision_drift_are_detected(rig, production):
    p = production; a = asset(rig)
    p.annotate(rig.nid, rig.scope, rig.actor, a["id"], declaration(1, chapter_ids=[rig.chapter["id"]]))
    rig.chapters.save(rig.chapter["id"], {"version": rig.chapter["version"], "content": "changed"})
    assert p.asset(rig.nid, rig.scope, a["id"])["sources"][0]["state"] == "STALE"
    rig.assets._bin_path(a["id"]).write_bytes(b"not original")
    assert p.asset(rig.nid, rig.scope, a["id"])["integrity"] == "CONTENT_UNAVAILABLE"


def test_manifest_replay_new_existing_domain_task_exact_bytes_pending_review_restart(rig, production):
    p = production; _, task, manifest = prepared(rig, p)
    assert manifest["environment"]["verification"] == "SYNTHETIC_PROTOCOL_ONLY"
    before = p.preflight(rig.nid, rig.scope, rig.actor, manifest["id"], 1)
    assert before["states"] == {"traceable": True, "rebuildable": True, "replayable": True, "deterministic": True, "byte_equal": None}
    replay, body = new_replay(rig, p, manifest)
    assert replay["task_id"] != task["id"] and replay["status"] == "QUEUED"
    assert p.replay(rig.nid, rig.scope, rig.actor, manifest["id"], body)["id"] == replay["id"]
    assert len(p.media.tasks(rig.nid, rig.scope)) == 2
    reopened_store = ExperimentalStore(rig.root, rig.backend, rig.store.database_url)
    media = MediaService(reopened_store, rig.novels, rig.chapters, rig.assets, rig.screenplays, production_capture_enabled=lambda: True)
    reopened = ProductionLineageService(reopened_store, rig.novels, rig.chapters, rig.assets, media)
    complete = reopened.execute_replay(rig.nid, rig.scope, rig.actor, replay["id"], replay["task_version"])
    assert complete["status"] == "SUCCEEDED" and complete["byte_equal"] is True
    assert all(o["status"] == "PENDING_REVIEW" for o in complete["outputs"])
    assert rig.assets.list(rig.nid) == []
    assert reopened.manifests(rig.nid, rig.scope)["items"][0]["manifest_digest"] == manifest["manifest_digest"]
    assert reopened.replays(rig.nid, rig.scope, rig.actor)["items"][0]["byte_equal"] is True
    assert rig.chapters.get(rig.chapter["id"])["content"] == rig.chapter["content"]


def test_replay_cannot_dispatch_or_retry_through_ordinary_media_routes(rig, production):
    p = production; _, _, m = prepared(rig, p); replay, _ = new_replay(rig, p, m)
    with pytest.raises(ValueError, match="DISPATCH_AUTHORITY_REQUIRED"):
        p.media.execute(rig.nid, rig.scope, rig.actor, replay["task_id"], 1)
    cancelled = p.cancel_replay(rig.nid, rig.scope, rig.actor, replay["id"], 1)
    assert cancelled["status"] == "CANCELLED"
    with pytest.raises(ValueError, match="NEW_PREFLIGHT"):
        p.media.transition(rig.nid, rig.scope, rig.actor, replay["task_id"], "retry", cancelled["task_version"])


def test_preflight_changed_source_privacy_adapter_runtime_missing_model(rig, production):
    p = production; _, _, m = prepared(rig, p)
    original = p.media.registry._adapters["mock-image-v1"]
    original.definition = original.definition.model_copy(update={"model_id": "changed"})
    check = p.preflight(rig.nid, rig.scope, rig.actor, m["id"], 1)
    assert not check["ready"] and "ADAPTER_OR_MODEL_CHANGED" in check["blockers"]
    original.definition = MockImageWorkflowAdapter.definition
    p.media.registry = MediaAdapterRegistry(include_mock=False)
    assert "CONFIGURED_ADAPTER_REQUIRED" in p.preflight(rig.nid, rig.scope, rig.actor, m["id"], 1)["blockers"]
    p.media.registry = MediaAdapterRegistry()
    review_source_privacy(rig.chapter, None, rig.actor, "CLOUD_ALLOWED", rig.chapter["version"], content_digest(rig.chapter), rig.root)
    assert "CURRENT_PRIVACY_CHANGED" in p.preflight(rig.nid, rig.scope, rig.actor, m["id"], 1)["blockers"]
    rig.chapters.save(rig.chapter["id"], {"version": rig.chapter["version"], "content": "changed"})
    assert "SOURCE_CHANGED_OR_UNAVAILABLE" in p.preflight(rig.nid, rig.scope, rig.actor, m["id"], 1)["blockers"]


def test_historical_tasks_cannot_invent_original_runtime(rig, production):
    p = production; _, task, _ = prepared(rig, p)
    with rig.store.transaction(rig.nid, rig.scope) as doc:
        doc["collections"][p.media.TASKS][task["id"]].pop("observed_environment")
    m = p.capture(rig.nid, rig.scope, rig.actor, {"task_id": task["id"], "expected_task_version": task["version"]})
    check = p.preflight(rig.nid, rig.scope, rig.actor, m["id"], 1)
    assert "ORIGINAL_RUNTIME_EVIDENCE_MISSING" in check["blockers"]
    assert not check["states"]["rebuildable"] and not check["states"]["deterministic"]


def test_export_closed_allowlist_never_prompts_keys_paths_or_reference_ids(rig, production):
    p = production; a = asset(rig, "/private/secret-name.png")
    _, _, m = prepared(rig, p, reference_asset_ids=[a["id"]])
    exported = p.export(rig.nid, rig.scope, m["id"])
    encoded = json.dumps(exported)
    for secret in ["PRIVATE PROMPT", "sk-secret", "/home/", "secret-name", a["id"], rig.chapter["id"], rig.nid]:
        assert secret not in encoded
    assert exported["model_digest"] and exported["adapter_digest"] and exported["workflow_digest"]
    assert exported["parameters"] == {"candidate_count": 2} and exported["seed"]["value"] is None
    assert exported["redaction"] == {"raw_prompts": False, "source_text": False, "credentials": False, "paths": False, "asset_ids": False}
    assert exported["quality_verified"] is False and exported["license_verified"] is False


def test_actor_branch_and_fresh_preflight_fences(rig, production):
    p = production; _, _, m = prepared(rig, p); replay, body = new_replay(rig, p, m)
    with pytest.raises(StaleSourceError, match="PREFLIGHT_CHANGED"):
        p.replay(rig.nid, rig.scope, "different-author", m["id"], {**body, "idempotency_key": "other"})
    with pytest.raises(FileNotFoundError): p.execute_replay(rig.nid, rig.scope, "different-author", replay["id"], 1)
    with pytest.raises(FileNotFoundError): p.preflight(rig.nid, branch_scope(rig), rig.actor, m["id"], 1)
    assert p.replays(rig.nid, rig.scope, "different-author")["items"] == []
    p.broker_enabled = lambda: True
    with pytest.raises(StaleSourceError, match="PREFLIGHT_CHANGED"):
        p.execute_replay(rig.nid, rig.scope, rig.actor, replay["id"], 1)
    assert p._task(rig.nid, rig.scope, replay["task_id"])["status"] == "QUEUED"


def test_atomic_parallel_idempotency_does_not_duplicate_media_tasks(rig, production):
    p = production; _, _, m = prepared(rig, p)
    preflight = p.preflight(rig.nid, rig.scope, rig.actor, m["id"], 1)
    body = {"expected_version": 1, "preflight_digest": preflight["preflight_digest"], "idempotency_key": "parallel"}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: p.replay(rig.nid, rig.scope, rig.actor, m["id"], body), range(2)))
    assert results[0]["id"] == results[1]["id"] and len(p.media.tasks(rig.nid, rig.scope)) == 2
    with pytest.raises(ValueError, match="IDEMPOTENCY_CONFLICT"):
        # Same key + another manifest is never silently rebound.
        with rig.store.transaction(rig.nid, rig.scope) as doc:
            old = doc["collections"][p.MANIFESTS][m["id"]]
            duplicate = copy.deepcopy(old); duplicate["id"] = "other-manifest"
            doc["collections"][p.MANIFESTS][duplicate["id"]] = duplicate
        p.replay(rig.nid, rig.scope, rig.actor, "other-manifest", body)


def test_current_authority_failure_after_adapter_drops_results(rig, production):
    p = production; _, _, m = prepared(rig, p); replay, _ = new_replay(rig, p, m)
    calls = []; adapter = p.media.registry._adapters["mock-image-v1"]; generate = adapter.generate
    def generating(request):
        calls.append(request)
        return generate(request)
    adapter.generate = generating
    def guard():
        if calls: raise ValueError("AUTHORITY_REVOKED")
    with pytest.raises(ValueError, match="AUTHORITY_REVOKED"):
        p.execute_replay(rig.nid, rig.scope, rig.actor, replay["id"], 1, guard)
    assert p._task(rig.nid, rig.scope, replay["task_id"])["status"] == "FAILED"
    assert len(p.media.proposals(rig.nid, rig.scope)) == 2


def test_router_flags_permissions_and_old_callback_fences(rig, production):
    p = production; flags = {"asset_lineage_v2", "production_manifest_v2", "cover_storyboard_generation", "media_adapter_registry"}
    permissions = []; allowed = [True]
    def auth(nid, token, branch, permission):
        if token != "valid" or not allowed[0]: raise HTTPException(403, "denied")
        permissions.append(permission)
        return rig.actor, rig.scope if branch is None else branch_scope(rig, branch)
    def require(name):
        if name not in flags: raise HTTPException(404, "disabled")
    app = FastAPI(); app.include_router(create_production_lineage_router(p, auth, require)); client = TestClient(app)
    base = f"/novels/{rig.nid}/experimental/production"; headers = {"X-Session-Token": "valid"}
    assert client.get(base + "/assets").status_code == 403
    a = asset(rig)
    assert client.put(base + f"/assets/{a['id']}/lineage", headers=headers, json=declaration(1)).status_code == 200
    assert permissions[-1] == "domain.write"
    _, task, m = prepared(rig, p)
    assert client.post(base + "/manifests", headers=headers, json={"task_id": task["id"], "expected_task_version": 1}).status_code == 409
    pf = client.post(base + f"/manifests/{m['id']}/preflight", headers=headers, json={"expected_version": 1}).json()
    replay = client.post(base + f"/manifests/{m['id']}/replay", headers=headers, json={"expected_version": 1, "preflight_digest": pf["preflight_digest"], "idempotency_key": "http"}).json()
    flags.remove("production_manifest_v2")
    assert client.post(base + f"/replays/{replay['id']}/execute", headers=headers, json={"expected_task_version": 1}).status_code == 404
    assert p._task(rig.nid, rig.scope, replay["task_id"])["status"] == "QUEUED"
    assert client.get(base + "/assets", headers=headers).status_code == 200
    flags.clear()
    assert client.get(base + "/assets", headers=headers).status_code == 404


def test_legacy_parameter_write_cannot_forge_or_erase_reserved_lineage(rig, production):
    p = production; a = asset(rig)
    for value in ({"origin": "ORIGINAL_INPUT"}, None):
        with pytest.raises(ValueError, match="scoped versioned annotation"):
            rig.assets.update_metadata(a["id"], {"parameters": {"asset_lineage_v2": value}})
    p.annotate(rig.nid, rig.scope, rig.actor, a["id"], declaration(1))
    original = rig.assets.get(a["id"])["parameters"]["asset_lineage_v2"]
    rig.assets.update_metadata(a["id"], {"parameters": {"legacy": "allowed"}})
    assert rig.assets.get(a["id"])["parameters"]["asset_lineage_v2"] == original


def test_original_media_features_do_not_capture_manifest_evidence_when_off(rig, monkeypatch):
    from app.experimental.flags import FLAGS
    for flags, acceptance in [("", "false"), ("cover_storyboard_generation,media_adapter_registry", "false"), (",".join(FLAGS), "true")]:
        monkeypatch.setenv("EXPERIMENTAL_FEATURES", flags); monkeypatch.setenv("V1_ACCEPTANCE_MODE", acceptance)
        media = MediaService(rig.store, rig.novels, rig.chapters, rig.assets, rig.screenplays)
        brief = media.create_cover(rig.nid, rig.scope, rig.actor, {"title": "Legacy"})
        task = media.queue(rig.nid, rig.scope, rig.actor, {"brief_id": brief["id"], "expected_brief_version": 1, "adapter_id": "mock-image-v1"})
        assert "queued_environment" not in task
        task = media.execute(rig.nid, rig.scope, rig.actor, task["id"], 1)
        assert "observed_environment" not in task


def test_lineage_current_authority_and_source_checked_inside_asset_commit(rig, production):
    p = production; a = asset(rig); calls = []
    def guard():
        calls.append(1)
        if len(calls) == 2: raise ValueError("CURRENT_AUTHORITY_REVOKED")
    with pytest.raises(ValueError, match="REVOKED"):
        p.annotate(rig.nid, rig.scope, rig.actor, a["id"], declaration(1), guard)
    assert rig.assets.get(a["id"])["version"] == 1


def test_broker_budget_seam_reserves_dispatches_settles_and_never_bypasses(rig, production):
    from app.experimental.model_broker import ModelBrokerService
    from app.runtime import Runtime
    from app.stable_identity import StableIdentityStore
    p = production
    p.broker = ModelBrokerService(rig.store, rig.novels, rig.chapters,
        runtime=Runtime(StableIdentityStore(rig.root / "runtime-ids.json")), media_registry=p.media.registry)
    p.broker_enabled = lambda: True
    _, _, m = prepared(rig, p); replay, _ = new_replay(rig, p, m)
    assert p.broker.ledger(rig.nid, rig.scope, rig.actor) == []
    completed = p.execute_replay(rig.nid, rig.scope, rig.actor, replay["id"], 1)
    assert completed["byte_equal"] is True
    ledger = p.broker.ledger(rig.nid, rig.scope, rig.actor)
    assert len(ledger) == 1 and ledger[0]["job_id"] == replay["task_id"]
    assert ledger[0]["status"] == "SETTLED" and ledger[0]["actual_microusd"] == 0
    replay2, _ = new_replay(rig, p, m, key="second")
    p.broker.configure_budget(rig.nid, rig.scope, rig.actor, {"expected_version": 0, "limit_microusd": 0})
    with pytest.raises(StaleSourceError, match="BUDGET_CHANGED"):
        p.execute_replay(rig.nid, rig.scope, rig.actor, replay2["id"], 1)
    assert p._task(rig.nid, rig.scope, replay2["task_id"])["status"] == "QUEUED"


def test_cancel_running_replay_drops_late_output_and_restart_never_retries(rig, production):
    p = production; _, _, m = prepared(rig, p); replay, _ = new_replay(rig, p, m)
    entered, release = Event(), Event(); adapter = p.media.registry._adapters["mock-image-v1"]
    generate = adapter.generate
    def slow(request):
        entered.set(); assert release.wait(10); return generate(request)
    adapter.generate = slow
    with ThreadPoolExecutor() as pool:
        future = pool.submit(p.execute_replay, rig.nid, rig.scope, rig.actor, replay["id"], 1)
        try:
            assert entered.wait(10)
            task = p._task(rig.nid, rig.scope, replay["task_id"])
            p.cancel_replay(rig.nid, rig.scope, rig.actor, replay["id"], task["version"])
        finally: release.set()
        assert future.result(20)["status"] == "CANCELLED"
    assert len(p.media.proposals(rig.nid, rig.scope)) == 2
    replay2, _ = new_replay(rig, p, m, key="restart")
    with rig.store.transaction(rig.nid, rig.scope) as doc:
        doc["collections"][p.media.TASKS][replay2["task_id"]].update(status="RUNNING", execution_token="dead-process")
    view = next(r for r in p.replays(rig.nid, rig.scope, rig.actor)["items"] if r["id"] == replay2["id"])
    assert view["recoverable"] and view["recovery"] == "NEW_PREFLIGHT_AND_NEW_TASK_REQUIRED"
    with pytest.raises(ValueError, match="NOT_QUEUED"):
        p.execute_replay(rig.nid, rig.scope, rig.actor, replay2["id"], 1)


def test_replay_never_claims_byte_equality_for_corrupt_persisted_output(rig, production):
    p = production; _, _, m = prepared(rig, p); replay, _ = new_replay(rig, p, m)
    result = p.execute_replay(rig.nid, rig.scope, rig.actor, replay['id'], 1)
    assert result['byte_equal'] is True
    with rig.store.transaction(rig.nid, rig.scope) as doc:
        doc['collections'][p.media.PROPOSALS][result['outputs'][0]['proposal_id']]['content_base64'] = base64.b64encode(b'corrupt').decode()
    result = p.replays(rig.nid, rig.scope, rig.actor)['items'][0]
    assert result['byte_equal'] is None and result['recovery']
    assert result['outputs'][0]['integrity'] == 'CONTENT_UNAVAILABLE'


def test_lineage_retains_declaration_versions_without_leaking_historical_parent_ids(rig, production):
    p = production; a, b = asset(rig, 'first'), asset(rig, 'child')
    row = p.annotate(rig.nid, rig.scope, rig.actor, b['id'], declaration(1, [a['id']]))
    row = p.annotate(rig.nid, rig.scope, rig.actor, b['id'], declaration(row['version'], [a['id']], operation='author attribution correction'))
    assert row['declaration_history_versions'] == [2]
    parent = rig.assets.get(a['id']); parent['branch_id'] = 'denied'; rig.assets._write_meta(parent)
    assert a['id'] not in json.dumps(p.asset(rig.nid, rig.scope, b['id']))


def test_existing_r3_approved_asset_provenance_is_projected_without_duplicate_library(rig, production):
    p = production; source = asset(rig)
    _, task, _ = prepared(rig, p, reference_asset_ids=[source['id']])
    proposal = p.media.proposals(rig.nid, rig.scope)[0]
    approved = p.media.review(rig.nid, rig.scope, rig.actor, proposal['id'], 'approve', proposal['version'])
    row = p.asset(rig.nid, rig.scope, approved['asset_id'])
    assert row['origin'] == 'GENERATED_RESULT' and row['generation']['task_id'] == task['id']
    assert row['parents'][0]['id'] == source['id'] and row['parents'][0]['state'] == 'CURRENT'
    assert row['sources'][0]['id'] == rig.chapter['id'] and row['sources'][0]['state'] == 'CURRENT'
    assert 'asset_lineage_v2' not in rig.assets.get(approved['asset_id'])['parameters']


def test_production_version_conflicts_do_not_return_raw_private_records(rig, production):
    p = production; a = asset(rig, 'denied-parent-title')
    _, task, m = prepared(rig, p, reference_asset_ids=[a['id']])
    parent = rig.assets.get(a['id']); parent['branch_id'] = 'hidden-branch'; rig.assets._write_meta(parent)
    app = FastAPI(); app.include_router(create_production_lineage_router(p, lambda *_: (rig.actor, rig.scope), lambda _: None))
    client = TestClient(app); base = f'/novels/{rig.nid}/experimental/production'
    responses = [client.post(base + '/manifests', json={'task_id': task['id'], 'expected_task_version': 1}),
                 client.post(base + f"/manifests/{m['id']}/preflight", json={'expected_version': 99})]
    for response in responses:
        assert response.status_code == 409
        assert a['id'] not in response.text and 'PRIVATE PROMPT' not in response.text and 'denied-parent-title' not in response.text
        assert set(response.json()['detail']['current']) <= {'version', 'status'}


def test_cancel_recovers_budget_committed_before_replay_pointer_checkpoint(rig, production):
    from app.experimental.model_broker import ModelBrokerService
    from app.runtime import Runtime
    from app.stable_identity import StableIdentityStore
    p = production
    p.broker = ModelBrokerService(rig.store, rig.novels, rig.chapters,
        runtime=Runtime(StableIdentityStore(rig.root / 'runtime-ids.json')), media_registry=p.media.registry)
    p.broker_enabled = lambda: True
    _, _, m = prepared(rig, p); replay, request = new_replay(rig, p, m)
    entry = p.broker.reserve(rig.nid, rig.scope, rig.actor, request['broker_decision_id'], request['broker_decision_version'],
        'production:' + replay['id'], replay['task_id'])
    assert p.broker.budget(rig.nid, rig.scope)['inflight'] == 1
    assert p.get(rig.nid, rig.scope, p.REPLAYS, replay['id'])['reservation_id'] is None
    p.cancel_replay(rig.nid, rig.scope, rig.actor, replay['id'], 1)
    assert p.broker.get(rig.nid, rig.scope, p.broker.LEDGER, entry['id'])['status'] == 'RELEASED'
    assert p.broker.budget(rig.nid, rig.scope)['inflight'] == 0

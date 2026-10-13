"""Schema-3 24-node review recovery through the real File/PostgreSQL owners.

Only the local FFmpeg audio.trim operation runs. The candidate is synthesized
from an owned WAV, and a process-stop injection leaves the original audio review
reservation durable before any promotion. No provider/model output is fabricated.
"""
from copy import deepcopy
import hashlib
from uuid import uuid4

import pytest

from app.audio_production_store import AudioProductionStore
from app.creative.graph import CreativeGraphService
from app.creative.production_execution import ProductionExecutionService
from app.experimental.common import StaleSourceError
from app.services.image_job_service import ImageJobService
from app.services.studio_audio_execution import StudioAudioExecution
from test_v2_independent_workspace import rig, reopened, import_asset, wav_bytes, decoders, branch_scope


class NoExternalControl:
    def __getattr__(self, name):
        raise AssertionError("Local graph recovery attempted external control: " + name)


class StoppedBeforePromotion(BaseException):
    """A process stop bypasses ordinary failed-review compensation."""


def owners(e, workspace=None):
    workspace = workspace or e.service
    production = ProductionExecutionService(workspace, ImageJobService(e.root),
        NoExternalControl(), NoExternalControl(), {}, {},
        AudioProductionStore(e.root / "audio-production"), NoExternalControl(), NoExternalControl())
    graph = CreativeGraphService(workspace.store, workspace)
    graph.configure_media(production)
    return graph, production


def definition(source):
    # The 21 disconnected local nodes are also explicitly selected. Recovery
    # must reconstruct all 24 targets, rather than just the 3-node audio branch.
    nodes = [{"id": f"text{index:02}", "definition_id": "text_input",
              "parameters": {"text": f"Owned local text {index}"}} for index in range(21)]
    nodes.extend([
        {"id": "source", "definition_id": "asset_reference", "parameters": {
            "asset_id": source["id"], "version": source["version"],
            "digest": source["sha256"], "kind": "audio"}},
        {"id": "trim", "definition_id": "media_generate", "parameters": {
            "operation_id": "m8.audio.trim", "parameters": {"in_ms": 0, "out_ms": 50},
            "license_note": "Author-owned synthetic WAV"}},
        {"id": "review", "definition_id": "media_review"},
    ])
    return {"schema_version": 3, "title": "24-node local audio recovery", "nodes": nodes, "edges": [
        {"id": "source_to_trim", "source_node_id": "source", "source_port": "asset",
         "target_node_id": "trim", "target_port": "source"},
        {"id": "trim_to_review", "source_node_id": "trim", "source_port": "candidate",
         "target_node_id": "review", "target_port": "candidate"},
    ]}


@pytest.fixture
def media24(rig, decoders):
    e = rig
    e.service.activate(e.nid, e.scope, e.actor)
    e.source = import_asset(e, data=wav_bytes(), filename="owned.wav", kind="audio")
    e.graphs, e.production = owners(e)
    value = definition(e.source)
    e.graph = e.graphs.create(e.nid, e.scope, e.actor,
        {"request_id": "graph-" + uuid4().hex, "definition": value})
    targets = [node["id"] for node in value["nodes"]]
    preflight = e.graphs.preflight(e.nid, e.scope, e.actor, e.graph["id"],
        {"expected_version": 1, "target_node_ids": targets})
    assert preflight["executable"] and len(preflight["selected_closure"]) == 24
    e.run = e.graphs.create_run(e.nid, e.scope, e.actor, e.graph["id"], {
        "expected_graph_version": 1, "request_id": "run-" + uuid4().hex,
        "target_node_ids": targets, "reviewed_preflight_digest": preflight["preflight_digest"]})
    assert len(raw_run(e)["selected_closure"]) == 24
    return e


def raw_run(e):
    return e.graphs._owned(e.nid, e.scope, e.actor, e.graphs.RUNS, e.run["id"])


def media_node(row):
    return next(node for node in row["media_runtime"]["nodes"] if node["node_id"] == "trim")


def job_action(row, *, review=False):
    job = media_node(row)["execution"]["job"]
    result = {"expected_version": row["version"], "node_id": "review" if review else "trim",
        "expected_job_version": job["version"], "expected_request_digest": job["request_digest"]}
    if review:
        result["reviewed_output_digest"] = job["output_candidate"]["digest"]
    return result


def stopped_review(e, monkeypatch):
    runtime = e.graphs.media_runtime
    row = e.graphs.action(e.nid, e.scope, e.actor, e.run["id"], "execute",
        {"expected_version": e.run["version"]})
    assert row["status"] == "WAITING_APPROVAL" and row["current_node_id"] == "trim"
    row = runtime.preview(e.nid, e.scope, e.actor, row["id"],
        {"expected_version": row["version"], "node_id": "trim"}, lambda: None)
    preview = media_node(row)["preview"]
    assert preview["production_preview"]["provider"] is None
    assert preview["production_preview"]["execution_recipe"]["adapter"] == "LOCAL_FFMPEG"
    row = runtime.dispatch(e.nid, e.scope, e.actor, row["id"], {
        "expected_version": row["version"], "node_id": "trim",
        "reviewed_preview_digest": preview["preview_digest"]}, lambda: None)
    row = runtime.execute_job(e.nid, e.scope, e.actor, row["id"], job_action(row), lambda: None)
    assert row["status"] == "WAITING_APPROVAL" and row["current_node_id"] == "review"
    candidate = deepcopy(media_node(row)["execution"]["job"]["output_candidate"])
    assert media_node(row)["execution"]["job"]["status"] == "AWAITING_REVIEW"
    with e.service._asset_scope(e.nid, e.scope):
        content = e.assets.content(candidate["id"], actor_id=e.actor)
    assert content.startswith(b"RIFF") and content[8:12] == b"WAVE"
    assert hashlib.sha256(content).hexdigest() == candidate["digest"]
    with pytest.raises(FileNotFoundError):
        e.service.asset(e.nid, e.scope, candidate["id"])

    def stop(*args, **kwargs):
        raise StoppedBeforePromotion("Stopped before original asset promotion")

    with monkeypatch.context() as patch:
        patch.setattr(e.assets, "promote_owned", stop)
        with pytest.raises(StoppedBeforePromotion):
            runtime.review(e.nid, e.scope, e.actor, row["id"], job_action(row, review=True), lambda: None)
    captured = deepcopy(raw_run(e))
    execution = captured["media_executions"]["trim"]
    assert execution["review_state"] == "REVIEW_RESERVED"
    job = e.production.get(e.nid, e.scope, e.actor, "audio", execution["job_id"], lambda: None,
        graph_binding=execution["graph_binding"])
    assert job["status"] == "REVIEWING" and job["output_candidate"] == candidate
    assert len(captured["selected_closure"]) == len(captured["node_states"]) == 24
    return captured, job, candidate


def change_current_graph(e, change):
    if change == "edited":
        # Downgrade the current graph to schema 1. Recovery must select its
        # 24-target contract from the durable schema-3 snapshot, not this row.
        e.graphs.save(e.nid, e.scope, e.actor, e.graph["id"], {
            "expected_version": e.graph["version"], "definition": {
                "schema_version": 1, "title": "Replacement local graph",
                "nodes": [deepcopy(node) for node in e.graph["definition"]["nodes"]
                          if node["id"] == "source"], "edges": []}})
    else:
        # Graph has no public delete operation; remove only its current
        # definition in the original durable scope to simulate missing state.
        with e.store.transaction(e.nid, e.scope) as state:
            del state["collections"][e.graphs.GRAPHS][e.graph["id"]]


def recovery_read(e, guard=lambda: None):
    return e.graphs.get_run(e.nid, e.scope, e.actor, e.run["id"], guard)


@pytest.mark.parametrize("change", ["edited", "deleted"])
def test_24_node_stopped_review_reopens_and_recovers_without_current_graph(media24, monkeypatch, change):
    e = media24
    captured, stopped_job, candidate = stopped_review(e, monkeypatch)
    change_current_graph(e, change)
    current_graphs = deepcopy(e.store.read(e.nid, e.scope)["collections"][e.graphs.GRAPHS])
    workspace = reopened(e)
    e.graphs, e.production = owners(e, workspace)

    def no_replay(*args, **kwargs):
        pytest.fail("Review recovery must not render, send, or promote")

    monkeypatch.setattr(StudioAudioExecution, "execute", no_replay)
    monkeypatch.setattr(workspace.assets, "promote_owned", no_replay)
    before = deepcopy(raw_run(e))
    view = recovery_read(e)
    assert raw_run(e) == before == captured
    assert view["stale"] and view["status"] == "WAITING_APPROVAL"
    assert view["current_node_id"] == "review" and len(view["node_states"]) == 24
    assert view["review"] is None and not view["reviewed"]
    assert all(node["output"] is None for node in view["node_states"].values())
    public = media_node(view)
    assert public["preview"] is None and public["execution"]["job"] is None
    recovery = public["execution"]["review_recovery"]
    assert recovery == {"contract": "creative-graph-review-recovery/1",
        "job_version": stopped_job["version"], "request_digest": stopped_job["request_digest"]}
    action = {"expected_version": view["version"], "node_id": "trim",
        "expected_job_version": recovery["job_version"], "expected_request_digest": recovery["request_digest"]}

    def revoked():
        raise PermissionError("Recovery authority revoked")

    with pytest.raises(PermissionError, match="authority revoked"):
        recovery_read(e, revoked)
    with pytest.raises(PermissionError, match="authority revoked"):
        e.graphs.media_runtime.reconcile(e.nid, e.scope, e.actor, view["id"], action, revoked)
    for actor, scope in (("another-author", e.scope), (e.actor, branch_scope(e))):
        with pytest.raises(FileNotFoundError):
            e.graphs.get_run(e.nid, scope, actor, view["id"])
    assert raw_run(e) == before

    recovered = e.graphs.media_runtime.reconcile(e.nid, e.scope, e.actor, view["id"], action, lambda: None)
    latest = raw_run(e)
    assert recovered["stale"] and recovered["status"] == "WAITING_APPROVAL"
    assert recovered["current_node_id"] == "review" and recovered["review"] is None
    assert all(node["output"] is None for node in recovered["node_states"].values())
    assert latest["selected_closure"] == captured["selected_closure"]
    assert latest["definition_snapshot"] == captured["definition_snapshot"]
    assert latest["node_states"] == captured["node_states"] and latest["typed_outputs"] == captured["typed_outputs"]
    assert latest["reviewed_nodes"] == [] and not latest["reviewed"]
    execution = latest["media_executions"]["trim"]
    job = e.production.get(e.nid, e.scope, e.actor, "audio", execution["job_id"], lambda: None,
        graph_binding=execution["graph_binding"])
    assert job["status"] == execution["status"] == "AWAITING_REVIEW"
    assert job["output_candidate"] == candidate and job["approved_asset_version"] is None
    assert job["version"] == stopped_job["version"] + 1
    assert e.store.read(e.nid, e.scope)["collections"][e.graphs.GRAPHS] == current_graphs
    with workspace._asset_scope(e.nid, e.scope):
        content = workspace.assets.content(candidate["id"], actor_id=e.actor)
    assert hashlib.sha256(content).hexdigest() == candidate["digest"]
    assert len(e.production.audio_store.for_actor(e.actor).load(e.nid, include_studio=True)["jobs"]) == 1
    assert [asset["id"] for asset in workspace.list_assets(e.nid, e.scope)["items"]] == [e.source["id"]]
    with pytest.raises(FileNotFoundError):
        workspace.asset(e.nid, e.scope, candidate["id"])
    assert not recovered["model_called"] and recovered["external_calls"] == 0 and not recovered["applied"]


@pytest.mark.parametrize("change", ["duplicate", "overflow", "missing", "unknown", "order", "schema"])
def test_24_node_recovery_rejects_corrupt_durable_selection(media24, change):
    e = media24
    with e.store.transaction(e.nid, e.scope) as state:
        row = state["collections"][e.graphs.RUNS][e.run["id"]]
        if change == "duplicate": row["selected_closure"][-1] = row["selected_closure"][0]
        elif change == "overflow": row["selected_closure"].append("extra25")
        elif change == "missing": row["selected_closure"].pop()
        elif change == "unknown": row["selected_closure"][-1] = "unknown"
        elif change == "order": row["selected_closure"].reverse()
        else: row["graph_schema_version"] = 1
    before = deepcopy(raw_run(e))
    with pytest.raises((StaleSourceError, ValueError), match="RECOVERY_|CONTRACT_REQUIRED"):
        e.graphs.media_runtime.review_recovery_read(e.nid, e.scope, e.actor, e.run["id"], lambda: None)
    assert raw_run(e) == before

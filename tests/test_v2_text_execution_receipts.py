"""M4-C passive receipt verification over original owners.

All worker inference here is explicitly built-in Mock, never real inference.
Real CPU evidence is a separate mounted acceptance exercise. Reuse the original
File/PostgreSQL fixtures; the focused File command deselects PostgreSQL cases.
"""
from copy import deepcopy
from hashlib import sha256
import json
from types import SimpleNamespace

import pytest

from app.creative.text_execution_receipt import (CONTRACT, PRIVATE_FIELD, request_payload,
    public_receipt, validate_receipt)
from app.experimental.common import StaleSourceError
from app.experimental.store import canonical
from app.jobs import JobManager
from app.model_execution import GraphRequestBinding, graph_request_payload_digest
from test_v2_independent_workspace import rig, branch_scope
from test_v2_ai_execution_runtime import (model_rig, admit, preview, dispatch, raw, current,
    wait_job, spy_transport, ForbiddenOwner, owned_jobs, generation_delta)
from test_v2_graph_text_assets import dispatch_asset, assets, approve


def reopened(e, monkeypatch):
    owner = ForbiddenOwner()
    manager = JobManager(e.persistence, owner, owner, owner, memory_extractor=owner,
        snapshot_required=True, collaboration_updates=owner)
    def forbidden(*args, **kwargs):
        raise AssertionError("receipt attempted to prepare or replay inference")
    monkeypatch.setattr(manager, "prepare_graph_job", forbidden)
    monkeypatch.setattr(manager, "start_prepared", forbidden)
    monkeypatch.setattr(e.models, "manager", manager)
    return manager


def seed_stored_job_fixture(e, job):
    """Write historical/corrupt storage bytes in this owned fixture only.

    Production save correctly refuses binding mutation. Recovery tests must
    model bytes originating before this version or corrupted outside that API.
    Both backends still use their actual repositories, database and load path.
    """
    previous = e.persistence.get(job.id)
    assert previous["novel_id"] == e.nid and previous["actor_id"] == e.actor and previous["scope"] == e.scope
    payload = job.public()
    if e.backend == "file":
        (e.root / "runtime/jobs" / (job.id + ".json")).write_text(json.dumps(payload), encoding="utf-8")
    else:
        from uuid import UUID
        from app.repositories.postgres.models import GenerationJobModel
        with e.bundle.generations.database.session() as session:
            item = session.get(GenerationJobModel, UUID(job.id))
            assert item is not None
            item.request = {**item.request, "_repository_payload": payload}


def test_receipt_preserves_exact_request_original_identity_and_terminal_time(model_rig, monkeypatch):
    from app.author_request import request_payload as original_payload
    e = model_rig; spy_transport(e, monkeypatch)
    sent, job = dispatch_asset(e)
    waiting = current(e, sent)
    row = raw(e, sent)
    receipt = waiting["asset_output"]["execution_receipt"]
    saved = assets(e)[0][PRIVATE_FIELD]
    decision = e.broker.get(e.nid, e.scope, e.broker.DECISIONS, row["model_preview"]["broker_preview_id"])
    ledger = e.broker.get(e.nid, e.scope, e.broker.LEDGER, row["model_execution"]["reservation_id"])
    assert receipt == public_receipt(saved) and "route_identity" not in receipt
    assert receipt["contract"] == job.graph_binding["execution_receipt_contract"] == CONTRACT
    assert job.graph_binding["execution_receipt_source_version"] == receipt["workflow"]["source_run_version"]
    assert receipt["prompt"] == row["model_preview"]["prompt"] == job.prepared_text_invocation.request.prompt
    assert receipt["prompt_sha256"] == sha256(receipt["prompt"].encode()).hexdigest()
    assert request_payload(row["model_preview"], e.models.node(row)) == original_payload(job.prepared_text_invocation.request)
    assert receipt["parameters"] == original_payload(job.prepared_text_invocation.request)["parameters"]
    assert receipt["request_digest"] == job.expected_request_digest == e.persistence.get(job.id)["expected_request_digest"]
    assert saved["route_identity"] == decision["chosen"]["identity"]
    assert receipt["route_fingerprint"] == job.graph_binding["route_fingerprint"] == ledger["route_fingerprint"]
    assert receipt["execution_mode"] == job.execution_mode == "mock_standin"
    assert receipt["model_evidence"]["kind"] == "SYNTHETIC_PROTOCOL"
    assert receipt["model_evidence"]["model_fingerprint"] == "synthetic-protocol-v1"
    assert receipt["model_evidence"]["runtime_fingerprint"] is None
    assert receipt["quality_verification"] == "NOT_RUN"
    assert receipt["workflow"] == waiting["asset_output"]["source"]
    assert receipt["terminal"] == {"status": "COMPLETED", "settlement_id": ledger["id"], "settled_at": ledger["updated_at"]}
    e.manager._emit(job)
    assert current(e, sent)["asset_output"]["execution_receipt"] == receipt
    approved = approve(e, current(e, sent))
    assert approved["asset_output"]["execution_receipt"] == receipt
    assert approved["asset_output"]["version"] == 2
    assert len(assets(e)) == len(e.calls) == len(owned_jobs(e)) == len(generation_delta(e)) == 1


@pytest.mark.parametrize("already_archived", [False, True])
def test_restored_receipt_never_rebuilds_authority_or_duplicates(model_rig, monkeypatch, already_archived):
    e = model_rig; spy_transport(e, monkeypatch)
    sent, job = dispatch_asset(e)
    before = current(e, sent)["asset_output"] if already_archived else None
    manager = reopened(e, monkeypatch)
    recovered = current(e, sent)
    assert not recovered["stale"] and recovered["asset_output"]["state"] == "DRAFT"
    if before:
        assert recovered["asset_output"] == before
    loaded = manager.get(job.id)
    assert loaded.prepared_text_invocation is loaded.request_authorization is None
    assert recovered["asset_output"]["execution_receipt"]["request_digest"] == loaded.expected_request_digest
    assert current(e, sent) == recovered
    assert len(e.calls) == len(assets(e)) == 1


@pytest.mark.parametrize("field,value", [
    ("prompt", "tampered private prompt"), ("prompt_sha256", "0" * 64),
    ("execution_mode", "real"), ("request_digest", "1" * 64),
    ("route_fingerprint", "2" * 64), ("quality_verification", "PASSED"),
    ("parameters", {"temperature": 0.0, "max_output_tokens": 1, "stop_sequences": []}),
    ("model_evidence", {"kind": "MODEL_CENTER_METADATA", "model_fingerprint": "a" * 64,
        "runtime_fingerprint": "b" * 64, "runtime_version": "fake"}),
])
def test_tampered_private_asset_receipt_masks_review_without_replay(model_rig, monkeypatch, field, value):
    e = model_rig; spy_transport(e, monkeypatch)
    sent, _ = dispatch_asset(e)
    waiting = current(e, sent)
    asset = assets(e)[0]
    asset[PRIVATE_FIELD][field] = value
    e.assets._write_meta(asset)
    result = current(e, sent)
    assert result["stale"] and result["review"] is None and result["asset_output"]["state"] == "INCOMPLETE"
    assert "execution_receipt" not in result["asset_output"]
    with pytest.raises((ValueError, StaleSourceError)):
        approve(e, waiting)
    assert len(e.calls) == len(assets(e)) == 1 and assets(e)[0]["version"] == 1


@pytest.mark.parametrize("change", ["mode", "request_digest", "deadline", "limit"])
def test_original_job_request_and_mode_are_verified_even_after_restore(model_rig, monkeypatch, change):
    e = model_rig; spy_transport(e, monkeypatch)
    sent, job = dispatch_asset(e)
    if change == "mode": job.execution_mode = "real"
    if change == "request_digest": job.expected_request_digest = "a" * 64
    if change == "deadline": job.generation_deadline = "2026-10-10T00:00:00+00:00"
    if change == "limit": job.generation_max_output_bytes = 31_999
    if change == "request_digest":
        from app.repositories.generation_repository import GenerationProjectIdentityError
        with pytest.raises(GenerationProjectIdentityError, match="BINDING_CHANGED"):
            e.manager._persist(job)
        seed_stored_job_fixture(e, job)
    else:
        e.manager._persist(job)
    reopened(e, monkeypatch)
    result = current(e, sent)
    assert result["stale"] and result["asset_output"]["state"] == "INCOMPLETE" and result["review"] is None
    assert not assets(e) and len(e.calls) == 1


@pytest.mark.parametrize("change", ["intent_marker", "source_version", "binding_marker"])
def test_new_contract_cannot_be_stripped_or_source_version_rewritten(model_rig, monkeypatch, change):
    e = model_rig; spy_transport(e, monkeypatch)
    sent, job = dispatch_asset(e)
    row = raw(e, sent)
    if change == "intent_marker": row["model_asset_intent"].pop("execution_receipt_contract")
    if change == "source_version": row["model_asset_intent"]["source_run_version"] += 1
    if change == "binding_marker": job.graph_binding.pop("execution_receipt_contract")
    with pytest.raises(StaleSourceError, match="JOB_BINDING_CHANGED"):
        e.models.bound_job(row)
    assert not assets(e) and len(e.calls) == 1


def test_scoped_receipt_prompt_is_private_and_generic_metadata_cannot_change_it(model_rig, monkeypatch):
    e = model_rig; spy_transport(e, monkeypatch)
    sent, _ = dispatch_asset(e)
    waiting = current(e, sent)
    asset = assets(e)[0]
    public = e.assets.public({"items": [asset], "nested": {"value": asset}})
    assert PRIVATE_FIELD not in json.dumps(public) and "prompt_sha256" not in json.dumps(public)
    assert asset[PRIVATE_FIELD]["prompt"] not in json.dumps(public, ensure_ascii=False)
    assert e.assets.list(e.nid) == []
    with e.service._asset_scope(e.nid, e.scope):
        for fields in ({PRIVATE_FIELD: {}}, {"parameters": {"prompt": "replacement"}},
                       {"provider_id": "forged-provider"}):
            with pytest.raises(ValueError):
                e.assets.update_metadata(asset["id"], fields, actor_id=e.actor, expected_version=1)
        with pytest.raises(FileNotFoundError):
            e.assets.get(asset["id"], actor_id="other-author")
    other_scope = branch_scope(e, "other-branch")
    with e.service._asset_scope(e.nid, other_scope):
        assert e.assets.list(e.nid, branch_id="other-branch", actor_id=e.actor) == []
    with pytest.raises(FileNotFoundError):
        e.graphs.get_run(e.nid, e.scope, "other-author", sent["id"], e.guard)
    assert current(e, sent)["asset_output"] == waiting["asset_output"]


def test_legacy_dispatch_omission_does_not_add_archival_contract(model_rig, monkeypatch):
    e = model_rig; spy_transport(e, monkeypatch)
    sent = dispatch(e, preview(e, admit(e)))
    job = e.manager.get(sent["model_runtime"]["execution"]["job_id"])
    wait_job(e, job); e.calls[-1]["worker"].join(8)
    assert "asset_output" not in current(e, sent)
    assert "model_asset_intent" not in raw(e, sent)
    assert "execution_receipt_contract" not in job.graph_binding
    assert "execution_receipt_source_version" not in job.graph_binding
    assert not assets(e)


def test_historical_v1_durable_fixture_recovers_without_adding_new_receipt(model_rig, monkeypatch):
    e = model_rig; spy_transport(e, monkeypatch)
    sent, job = dispatch_asset(e)
    # Construct the exact older persisted shape, including its older request
    # digest. This is a historical-data fixture, not a migration or API action.
    job.graph_binding.pop("execution_receipt_contract")
    job.graph_binding.pop("execution_receipt_source_version")
    row = raw(e, sent)
    job.expected_request_digest = graph_request_payload_digest(job,
        request_payload(row["model_preview"], e.models.node(row)), row["model_preview"]["allow_synthetic"])
    seed_stored_job_fixture(e, job)
    with e.graphs.store.transaction(e.nid, e.scope) as state:
        stored = state["collections"][e.graphs.RUNS][sent["id"]]
        for snapshot in [*stored["history"], stored]:
            if snapshot.get("model_asset_intent"):
                snapshot["model_asset_intent"].pop("execution_receipt_contract", None)
    reopened(e, monkeypatch)
    restored = current(e, sent)
    assert not restored["stale"] and restored["asset_output"]["state"] == "DRAFT"
    assert "execution_receipt" not in restored["asset_output"] and PRIVATE_FIELD not in assets(e)[0]
    assert approve(e, restored)["asset_output"]["version"] == 2
    assert len(e.calls) == len(assets(e)) == 1


def test_old_graph_binding_and_request_canonical_bytes_are_unchanged():
    binding = {"graph_id": "g", "graph_version": 1, "run_id": "r", "node_id": "n",
        "project_incarnation": "inc", "input_digest": "a" * 64,
        "reviewed_preview_digest": "b" * 64, "route_fingerprint": "c" * 64}
    assert GraphRequestBinding.model_validate(binding).model_dump() == binding
    job = SimpleNamespace(id="job", novel_id="novel", actor_id="actor", scope={"mode": "local", "novel_id": "novel"},
        graph_binding=binding, profile="LOCAL_ONLY", operation="graph_text", chapter_id=None,
        requested_provider="mock", requested_model="mock-text", generation_max_output_bytes=32_000,
        generation_deadline="2026-10-10T00:00:00+00:00")
    payload = {"prompt": "historical canonical request"}
    old_value = {"request": payload, "job_id": job.id, "project_id": job.novel_id, "actor_id": job.actor_id,
        "scope": job.scope, "graph_binding": binding, "profile": job.profile, "operation": job.operation,
        "chapter_id": job.chapter_id, "provider_id": job.requested_provider, "model_id": job.requested_model,
        "max_output_bytes": job.generation_max_output_bytes, "deadline": job.generation_deadline, "synthetic_allowed": True}
    assert graph_request_payload_digest(job, payload, True) == sha256(canonical(old_value).encode()).hexdigest()


def test_asset_owner_rejects_unsupported_or_forged_execution_receipt(model_rig, monkeypatch):
    e = model_rig; spy_transport(e, monkeypatch)
    sent, _ = dispatch_asset(e); current(e, sent)
    asset = assets(e)[0]
    for field, value in (("prompt_sha256", "a" * 64), ("execution_mode", "real"),
                         ("unknown_authority", True), ("quality_verification", "PASSED")):
        changed = deepcopy(asset[PRIVATE_FIELD]); changed[field] = value
        with pytest.raises(ValueError):
            validate_receipt(changed, source=asset["_text_result_origin"], provider_id=asset["provider_id"],
                model_id=asset["model_id"], parameters=asset["parameters"])


def test_large_unicode_prompt_is_preserved_without_truncation(model_rig, monkeypatch):
    from test_v2_ai_execution_runtime import create_graph, definition
    e = model_rig; spy_transport(e, monkeypatch)
    text = "原始输入。" * 1400
    graph = create_graph(e, definition(text=text, instruction="保留原始文本和换行\n不改变事实。"))
    sent = dispatch(e, preview(e, admit(e, graph)), archive_result=True)
    job = e.manager.get(sent["model_runtime"]["execution"]["job_id"])
    wait_job(e, job); e.calls[-1]["worker"].join(8)
    result = current(e, sent)
    receipt = result["asset_output"]["execution_receipt"]
    assert 16_000 < len(receipt["prompt"].encode()) <= 32_000
    assert receipt["prompt"] == job.prepared_text_invocation.request.prompt == raw(e, sent)["model_preview"]["prompt"]
    assert text in receipt["prompt"] and receipt["prompt_sha256"] == sha256(receipt["prompt"].encode()).hexdigest()
    assert assets(e)[0][PRIVATE_FIELD]["prompt"] == receipt["prompt"]


@pytest.mark.parametrize("change", ["chosen_identity", "ledger_route", "ledger_preview"])
def test_original_router_and_settlement_evidence_cannot_be_replaced(model_rig, monkeypatch, change):
    e = model_rig; spy_transport(e, monkeypatch)
    sent, _ = dispatch_asset(e)
    row = raw(e, sent)
    with e.broker.store.transaction(e.nid, e.scope) as state:
        if change == "chosen_identity":
            state["collections"][e.broker.DECISIONS][row["model_preview"]["broker_preview_id"]]["chosen"]["identity"]["model_version"] = "forged"
        else:
            ledger = state["collections"][e.broker.LEDGER][row["model_execution"]["reservation_id"]]
            ledger["route_fingerprint" if change == "ledger_route" else "preview_id"] = "a" * 64
    result = current(e, sent)
    assert result["stale"] and result["review"] is None and result["asset_output"]["state"] == "INCOMPLETE"
    assert not assets(e) and len(e.calls) == 1


def test_asset_review_commit_rechecks_sealed_receipt_after_original_workflow_commit(model_rig, monkeypatch):
    e = model_rig; spy_transport(e, monkeypatch)
    sent, _ = dispatch_asset(e)
    waiting = current(e, sent)
    original = e.assets.review_text_result
    def corrupt(*args, **kwargs):
        # This callback is already inside the original asset scope lease.
        asset = e.assets.get(args[0], actor_id=e.actor, branch_id=e.scope.get("branch_id"))
        asset[PRIVATE_FIELD]["prompt"] = "changed between validation and asset review"
        e.assets._write_meta(asset)
        return original(*args, **kwargs)
    monkeypatch.setattr(e.assets, "review_text_result", corrupt)
    with pytest.raises(ValueError, match="RECEIPT_CHANGED"):
        approve(e, waiting)
    assert raw(e, sent)["status"] == "SUCCEEDED"
    assert assets(e)[0]["version"] == 1 and assets(e)[0]["_text_result_review"]["status"] == "DRAFT"
    assert current(e, sent)["asset_output"]["state"] == "INCOMPLETE"
    assert len(e.calls) == len(assets(e)) == 1

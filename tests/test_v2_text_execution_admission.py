"""Receipt sizing uses real File/PostgreSQL owners and only built-in Mock inference."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from uuid import UUID

import pytest

from app.creative.text_execution_receipt import CONTRACT, PRIVATE_FIELD, model_evidence, request_payload
from app.experimental.common import api_call
from fastapi import HTTPException
from test_v2_independent_workspace import rig
from test_v2_ai_execution_runtime import (model_rig, admit, preview, dispatch, raw,
    create_graph, definition, spy_transport, owned_jobs, generation_delta, wait_job, current, refresh)
from test_v2_graph_text_assets import assets


def escaped_definition(length, *, suffix="", escape="\\"):
    value = definition(text=escape * length + suffix, instruction=escape * 4000)
    value["nodes"].insert(1, {"id": "Direction", "definition_id": "director_note", "parameters": {"note": escape * 4000}})
    value["edges"].append({"id": "Guidance", "source_node_id": "Direction", "source_port": "direction",
        "target_node_id": "Generate", "target_port": "direction"})
    return value


def budget_fixture(e, row):
    """Independent exact shape of current terminal owners, with maximum emitted timestamp."""
    row = raw(e, row)
    route, p = e.route, row["model_preview"]
    node = e.models.node(row)
    stamp = datetime.max.replace(tzinfo=timezone.utc).isoformat()
    job_id = str(UUID(int=0))
    source = {"schema_version": 1, "contract": "creative-graph-text-asset/1", "graph_id": row["graph_id"],
        "graph_version": row["graph_version"], "graph_digest": row["graph_digest"], "run_id": row["id"],
        "source_run_version": row["version"] + 1, "model_node_id": node["id"], "job_id": job_id,
        "input_digest": p["input_digest"], "output_digest": sha256(b"x").hexdigest(),
        "preview_digest": p["preview_digest"], "produced_at": stamp}
    payload = request_payload(p, node)
    receipt = {"schema_version": 1, "contract": CONTRACT,
        "prompt": payload["prompt"], "prompt_sha256": sha256(payload["prompt"].encode()).hexdigest(),
        "provider_id": route["provider_id"], "model_id": route["model_id"], "route_id": route["route_id"],
        "route_fingerprint": route["fingerprint"], "route_identity": deepcopy(route["identity"]),
        "model_evidence": model_evidence(route["identity"]), "parameters": payload["parameters"],
        "execution_mode": "mock_standin", "request_digest": "0" * 64, "workflow": source,
        "terminal": {"status": "COMPLETED", "settlement_id": "0" * 64, "settled_at": stamp},
        "quality_verification": "NOT_RUN"}
    initial = {"_text_result_origin": source, "source_job_id": job_id, "provider_id": route["provider_id"],
        "model_id": route["model_id"], "parameters": e.models.text_assets._parameters(row), PRIVATE_FIELD: receipt}
    return initial


def encoded_bytes(value):
    return len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode())


@pytest.mark.parametrize("escape", ["\\", '"'])
@pytest.mark.parametrize("length,error", [(7800, "TEXT_EXECUTION_RECEIPT_INVALID"), (7200, "TEXT_RESULT_METADATA_LIMIT")])
def test_oversized_receipt_rejected_before_original_admission(model_rig, monkeypatch, length, error, escape):
    e = model_rig; spy_transport(e, monkeypatch)
    row = preview(e, admit(e, create_graph(e, escaped_definition(length, escape=escape))))
    initial = budget_fixture(e, row)
    assert len(initial[PRIVATE_FIELD]["prompt"].encode()) <= 32_000
    if error == "TEXT_EXECUTION_RECEIPT_INVALID":
        assert encoded_bytes(initial[PRIVATE_FIELD]) > 64_000
    else:
        assert encoded_bytes(initial[PRIVATE_FIELD]) <= 64_000 < encoded_bytes(initial)
    before = deepcopy(e.graphs.store.read(e.nid, e.scope))
    calls = []
    def forbidden(*args, **kwargs):
        calls.append("prepare_graph_job")
        raise AssertionError("unarchivable receipt reached original Job preparation")
    monkeypatch.setattr(e.manager, "prepare_graph_job", forbidden)
    with pytest.raises(HTTPException) as failed:
        api_call(dispatch, e, row, archive_result=True)
    assert failed.value.status_code == 422
    assert failed.value.detail == {"code": "EXPERIMENTAL_INVALID", "message": error}
    assert not calls and not e.calls and not owned_jobs(e) and not generation_delta(e) and not assets(e)
    assert e.graphs.store.read(e.nid, e.scope) == before


def complete(e, row, *, archive_result=True):
    sent = dispatch(e, row, archive_result=archive_result)
    job = e.manager.get(sent["model_runtime"]["execution"]["job_id"])
    wait_job(e, job); e.calls[-1]["worker"].join(8)
    assert not e.calls[-1]["worker"].is_alive()
    return current(e, sent), job


@pytest.mark.parametrize("target", [63_999, 64_000, 64_001])
def test_exact_serialized_metadata_boundary_at_original_admission(model_rig, monkeypatch, target):
    from app.experimental import common
    e = model_rig; spy_transport(e, monkeypatch)
    # Match the owner's longest UTC form, including the rare zero-microsecond
    # clock reading. This changes no workflow timeout or execution deadline.
    monkeypatch.setattr(common, "now", lambda: datetime.now(timezone.utc).isoformat(timespec="microseconds"))
    baseline = preview(e, admit(e, create_graph(e, escaped_definition(7000))))
    difference = target - encoded_bytes(budget_fixture(e, baseline))
    assert difference >= 0
    slash_count, ascii_count = divmod(difference, 4)
    row = preview(e, admit(e, create_graph(e, escaped_definition(7000 + slash_count, suffix="a" * ascii_count))))
    initial = budget_fixture(e, row)
    assert encoded_bytes(initial) == target and encoded_bytes(initial[PRIVATE_FIELD]) < 64_000
    if target > 64_000:
        before = deepcopy(e.graphs.store.read(e.nid, e.scope))
        with pytest.raises(ValueError, match="^TEXT_RESULT_METADATA_LIMIT$"):
            dispatch(e, row, archive_result=True)
        assert not e.calls and not owned_jobs(e) and not generation_delta(e) and not assets(e)
        assert e.graphs.store.read(e.nid, e.scope) == before
    else:
        result, job = complete(e, row)
        assert not result["stale"] and result["asset_output"]["state"] == "DRAFT"
        asset = assets(e)[0]
        actual_initial = {key: asset[key] for key in initial}
        assert encoded_bytes(actual_initial) == target
        assert asset[PRIVATE_FIELD]["prompt"] == initial[PRIVATE_FIELD]["prompt"] == job.prepared_text_invocation.request.prompt
        assert len(e.calls) == len(owned_jobs(e)) == len(generation_delta(e)) == len(assets(e)) == 1


def test_oversized_receipt_does_not_change_legacy_opt_out(model_rig, monkeypatch):
    e = model_rig; spy_transport(e, monkeypatch)
    row = preview(e, admit(e, create_graph(e, escaped_definition(7800))))
    assert encoded_bytes(budget_fixture(e, row)) > 64_000
    result, job = complete(e, row, archive_result=False)
    result = refresh(e, result)
    assert not result["stale"] and result["review"]["draft"]["text"] == job.output
    assert job.prepared_text_invocation.request.prompt == raw(e, row)["model_preview"]["prompt"]
    assert "asset_output" not in result and "model_asset_intent" not in raw(e, row)
    assert "execution_receipt_contract" not in job.graph_binding and not assets(e)
    assert len(e.calls) == len(owned_jobs(e)) == len(generation_delta(e)) == 1


def test_unicode_and_json_escaping_are_measured_without_changing_prompt(model_rig, monkeypatch):
    e = model_rig; spy_transport(e, monkeypatch)
    text = '界\\"\n\t' * 1000
    graph = create_graph(e, definition(text=text, instruction='Keep exact \"quoted\" text, 路径\\文件 and controls\n\t.'))
    row = preview(e, admit(e, graph))
    expected = budget_fixture(e, row)
    result, job = complete(e, row)
    receipt = result["asset_output"]["execution_receipt"]
    assert not result["stale"] and result["asset_output"]["state"] == "DRAFT"
    assert receipt["prompt"] == expected[PRIVATE_FIELD]["prompt"] == job.prepared_text_invocation.request.prompt
    assert json.loads(receipt["prompt"].split("\n", 1)[1])["input"]["text"] == text
    assert encoded_bytes({key: assets(e)[0][key] for key in expected}) <= encoded_bytes(expected) <= 64_000
    assert len(e.calls) == len(assets(e)) == 1


def test_original_prompt_limit_remains_before_receipt_admission(model_rig, monkeypatch):
    e = model_rig; spy_transport(e, monkeypatch)
    row = admit(e, create_graph(e, escaped_definition(8000)))
    before = deepcopy(e.graphs.store.read(e.nid, e.scope))
    with pytest.raises(ValueError, match="^CREATIVE_MODEL_INPUT_LIMIT$"):
        preview(e, row)
    assert e.graphs.store.read(e.nid, e.scope) == before
    assert not e.calls and not owned_jobs(e) and not generation_delta(e) and not assets(e)


def test_revoked_authority_precedes_receipt_capacity_details(model_rig, monkeypatch):
    e = model_rig; spy_transport(e, monkeypatch)
    row = preview(e, admit(e, create_graph(e, escaped_definition(7800))))
    before = deepcopy(e.graphs.store.read(e.nid, e.scope))
    e.active = False
    with pytest.raises(PermissionError, match="authority revoked"):
        dispatch(e, row, archive_result=True)
    e.active = True
    assert e.graphs.store.read(e.nid, e.scope) == before
    assert not e.calls and not owned_jobs(e) and not generation_delta(e) and not assets(e)


@pytest.mark.parametrize("target", [63_999, 64_000, 64_001])
def test_exact_receipt_boundary_retains_both_original_owner_limits(model_rig, target):
    from app.creative.text_execution_receipt import validate_receipt
    e = model_rig
    row = preview(e, admit(e, create_graph(e, escaped_definition(7000))))
    initial = budget_fixture(e, row)
    receipt = initial[PRIVATE_FIELD]
    # A receipt's exact boundary is reachable with an ordinary ASCII suffix,
    # while retaining a legal <=32,000-byte prompt and unchanged owner IDs.
    receipt["prompt"] += "a" * (target - encoded_bytes(receipt))
    receipt["prompt_sha256"] = sha256(receipt["prompt"].encode()).hexdigest()
    assert encoded_bytes(receipt) == target and len(receipt["prompt"].encode()) <= 32_000
    args = {"source": initial["_text_result_origin"], "provider_id": initial["provider_id"],
        "model_id": initial["model_id"], "parameters": initial["parameters"]}
    if target > 64_000:
        with pytest.raises(ValueError, match="^TEXT_EXECUTION_RECEIPT_INVALID$"):
            validate_receipt(receipt, **args)
    else:
        assert validate_receipt(receipt, **args) == receipt
        assert encoded_bytes(initial) > 64_000
        with pytest.raises(ValueError, match="^TEXT_RESULT_METADATA_LIMIT$"):
            e.assets._text_initial(initial, b"x")
    assert not e.calls and not owned_jobs(e) and not generation_delta(e) and not assets(e)

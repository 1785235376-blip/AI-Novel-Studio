"""Regression candidate: actual owner admission must reject unarchivable receipts."""
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
    create_graph, definition, spy_transport, owned_jobs, generation_delta)
from test_v2_graph_text_assets import assets


def escaped_definition(length):
    value = definition(text="\\" * length, instruction="\\" * 4000)
    value["nodes"].insert(1, {"id": "Direction", "definition_id": "director_note", "parameters": {"note": "\\" * 4000}})
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


@pytest.mark.parametrize("length,error", [(7800, "TEXT_EXECUTION_RECEIPT_INVALID"), (7200, "TEXT_RESULT_METADATA_LIMIT")])
def test_oversized_receipt_rejected_before_original_admission(model_rig, monkeypatch, length, error):
    e = model_rig; spy_transport(e, monkeypatch)
    row = preview(e, admit(e, create_graph(e, escaped_definition(length))))
    initial = budget_fixture(e, row)
    print("BUDGET", length, len(initial[PRIVATE_FIELD]["prompt"].encode()),
        encoded_bytes(initial[PRIVATE_FIELD]), encoded_bytes(initial))
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

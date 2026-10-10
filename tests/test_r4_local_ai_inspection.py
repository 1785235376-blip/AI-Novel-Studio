"""Free synthetic protocol tests: never launch ComfyUI, models or GPU work."""
import copy
import json
from unittest.mock import Mock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.experimental.local_ai_inspection import InspectionInput, LocalAIInspectionService, MAX_BYTES, parse_workflow
from app.experimental.local_ai_inspection_api import create_local_ai_inspection_router
from app.experimental.media import MediaAdapterRegistry
from app.experimental.store import ExperimentalStore


@pytest.fixture
def graph():
    return {"1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "synthetic.safetensors"}},
            "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "PRIVATE PROMPT DO NOT EXPORT", "clip": ["1", 1]}},
            "3": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512, "batch_size": 1}},
            "4": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["2", 0], "negative": ["2", 0], "latent_image": ["3", 0]}},
            "5": {"class_type": "VAEDecode", "inputs": {"samples": ["4", 0], "vae": ["1", 2]}},
            "6": {"class_type": "SaveImage", "inputs": {"images": ["5", 0], "filename_prefix": "/private/user/output"}}}


@pytest.fixture
def snapshot(graph):
    return {"scan": {"status": "COMPLETED", "finished_at": "2026-10-05T00:00:00Z",
            "runtimes": [{"id": "local-fixture", "type": "COMFYUI", "status": "RUNNING", "version": "0.fixture", "endpoint": "http://127.0.0.1:8188", "name": "/private/runtime"}],
            "candidates": [{"runtime_id": "local-fixture", "runtime_type": "COMFYUI", "model_name": "synthetic.safetensors", "evidence": {"model_listed": True, "node_classes": [n["class_type"] for n in graph.values()], "loader_bindings": [{"node_class": "CheckpointLoaderSimple", "input_field": "ckpt_name"}]}}]},
            "registrations": [], "hardware": {"secret": "PRIVATE HARDWARE"},
            "workflow_adapters": [{"id": "comfy-sd-checkpoint-v1", "required_nodes": [n["class_type"] for n in graph.values()]}]}


@pytest.fixture
def service(tmp_path, snapshot):
    return LocalAIInspectionService(ExperimentalStore(tmp_path), Mock(get=Mock(return_value={"id": "n"})), None,
                                    discovery_snapshot=lambda: copy.deepcopy(snapshot), adapter_definitions=MediaAdapterRegistry().definitions)


def inspect(service, graph, **kwargs):
    return service.inspect(InspectionInput(workflow_json=json.dumps(graph), **kwargs))


def codes(result): return {row["code"] for row in result["issues"]}


def test_metadata_presence_never_grants_execution_or_quality(service, graph):
    result = inspect(service, graph, runtime_id="local-fixture")
    assert result["status"] == "REVIEW_REQUIRED"
    assert result["runnable"] is False
    assert result["execution_policy"] == "DENY_ALL"
    assert result["real_runtime"] == result["real_model"] == "NOT_RUN"
    assert all(n["registry_status"] == "LISTED_IN_SNAPSHOT" for n in result["nodes"])
    assert result["model_components"][0]["status"] == "LISTED_METADATA_ONLY"
    assert result["adapters"][0]["state"] == "REQUIRED_NODE_NAMES_PRESENT_ONLY"
    assert all(row["imported_graph_bound"] is False for row in result["adapters"])
    assert any(row["source"] == "R3_MEDIA_REGISTRY" and row["state"] == "MOCK_ONLY" for row in result["adapters"])
    assert "IMPORTED_GRAPH_HAS_NO_REVIEWED_ADAPTER" in codes(result)
    assert len(result["edges"]) == 8
    assert all(e["schema_validation"] == "NOT_VERIFIED" for e in result["edges"])


def test_inspection_is_passive_and_summary_never_contains_input_values(service, graph, monkeypatch):
    import socket
    import subprocess
    monkeypatch.setattr(socket, "socket", Mock(side_effect=AssertionError("network not allowed")))
    monkeypatch.setattr(subprocess, "Popen", Mock(side_effect=AssertionError("process not allowed")))
    graph["2"]["inputs"].update(api_key="sk-fixture-secret-key", code="import os; os.system('evil')", url="https://invalid.example/?key=secret", path="C:\\private\\model.safetensors")
    result = inspect(service, graph, runtime_id="local-fixture", declared_alias="Qwen-Image")
    assert {"CREDENTIAL_MATERIAL", "NETWORK_REFERENCE", "FILESYSTEM_REFERENCE", "CODE_INPUT"} <= codes(result)
    encoded = json.dumps(result)
    for private in ["PRIVATE PROMPT", "sk-fixture", "import os", "invalid.example", "C:\\private", "/private/user/output", "PRIVATE HARDWARE"]:
        assert private not in encoded
    summary = json.dumps(result["export_summary"])
    assert "synthetic.safetensors" not in summary
    assert "Qwen-Image" not in summary
    assert "local-fixture" not in summary
    assert "ComfyUI" not in summary


def test_api_wrapper_and_envelope_risks_are_inspected(service, graph):
    result = inspect(service, {"prompt": graph, "extra_data": {"api_key": "sensitive", "path": "//network/private"}})
    assert {"CREDENTIAL_MATERIAL", "FILESYSTEM_REFERENCE"} <= codes(result)


@pytest.mark.parametrize("raw,code", [
    ('{"a":1,"a":2}', 'WORKFLOW_DUPLICATE_KEY'),
    ('{"1":{"class_type":"X","inputs":{"v":NaN}}}', 'WORKFLOW_NONFINITE_NUMBER'),
    ('{"1":{"class_type":"X","inputs":{"v":1e999}}}', 'WORKFLOW_NONFINITE_NUMBER'),
    ('{', 'WORKFLOW_INVALID_JSON'), ('[]', 'WORKFLOW_API_OBJECT_REQUIRED'), ('{}', 'WORKFLOW_API_FORMAT_REQUIRED'),
    ('{"nodes":[]}', 'WORKFLOW_API_FORMAT_REQUIRED'),
    ('{"1":{"inputs":{}}}', 'WORKFLOW_NODE_CLASS_REQUIRED'),
    ('{"1":{"class_type":"X","inputs":[]}}', 'WORKFLOW_INPUTS_INVALID'),
    ('[' * 25 + '0' + ']' * 25, 'WORKFLOW_TOO_DEEP'),
    (' ' * (MAX_BYTES + 1), 'WORKFLOW_TOO_LARGE'),
])
def test_malformed_bounded_json_is_rejected(raw, code):
    with pytest.raises(ValueError, match=code): parse_workflow(raw)


def test_nodes_inputs_utf8_and_total_values_are_bounded():
    node = {"class_type": "X", "inputs": {}}
    with pytest.raises(ValueError, match="WORKFLOW_NODE_LIMIT"):
        parse_workflow(json.dumps({str(i): node for i in range(257)}))
    with pytest.raises(ValueError, match="WORKFLOW_INPUTS_INVALID"):
        parse_workflow(json.dumps({"1": {**node, "inputs": {str(i): 1 for i in range(129)}}}))
    with pytest.raises(ValueError, match="WORKFLOW_TOO_LARGE"):
        parse_workflow(json.dumps({"1": {**node, "inputs": {"v": "中" * (MAX_BYTES // 2)}}}, ensure_ascii=False))
    with pytest.raises(ValueError, match="WORKFLOW_VALUE_LIMIT"):
        parse_workflow(json.dumps({"1": {**node, "inputs": {"v": [0] * 20001}}}))


def test_cycles_invalid_connections_and_code_nodes(service, graph):
    graph["1"]["inputs"]["loop"] = ["6", 0]
    graph["2"]["inputs"]["missing"] = ["missing-private-node", 0]
    graph["3"]["inputs"]["slot"] = ["1", True]
    graph["7"] = {"class_type": "PythonExecHTTPUpload", "inputs": {}}
    result = inspect(service, graph, runtime_id="local-fixture")
    assert result["status"] == "INVALID"
    assert {"WORKFLOW_CYCLE", "LINK_SOURCE_MISSING", "LINK_SLOT_INVALID", "CODE_EXECUTION_NODE", "NETWORK_NODE", "NODE_IMPLEMENTATION_UNKNOWN", "NODE_NOT_LISTED"} <= codes(result)
    assert "missing-private-node" not in json.dumps(result)


def test_missing_model_bindings_and_other_runtime_evidence_do_not_count(service, snapshot, graph):
    snapshot["scan"]["candidates"][0]["runtime_id"] = "other-host"
    result = inspect(service, graph, runtime_id="local-fixture")
    assert all(row["registry_status"] == "UNKNOWN" for row in result["nodes"])
    assert result["model_components"][0]["status"] == "UNKNOWN"
    snapshot["scan"]["candidates"][0]["runtime_id"] = "local-fixture"
    snapshot["scan"]["candidates"][0]["evidence"]["loader_bindings"][0]["input_field"] = "other_field"
    assert inspect(service, graph, runtime_id="local-fixture")["model_components"][0]["status"] == "NOT_LISTED"
    with pytest.raises(ValueError, match="WORKFLOW_RUNTIME_SNAPSHOT_CHANGED"):
        inspect(service, graph, runtime_id="removed-runtime")


def test_no_scans_no_inventory_leaks_and_missing_snapshots_remain_usable(service, snapshot, graph):
    metadata = service.metadata()
    assert metadata["runtimes"][0]["label"] == "ComfyUI 1"
    assert "/private" not in json.dumps(metadata)
    snapshot["scan"] = None
    result = inspect(service, graph)
    assert {"RUNTIME_SNAPSHOT_REQUIRED", "NODE_CATALOG_NOT_CAPTURED", "DISCOVERY_SNAPSHOT_INCOMPLETE"} <= codes(result)
    assert result["runnable"] is False


def test_summary_persistence_is_explicit_immutable_scope_bound_and_excludes_raw(service, graph):
    body = InspectionInput(workflow_json=json.dumps(graph))
    scope = {"mode": "local", "novel_id": "n"}
    service.inspect(body)
    assert service.list("n", scope, service.REPORTS) == []
    saved = service.save_report("n", scope, "actor", body)
    assert saved["version"] == 1 and saved["privacy_level"] == "LOCAL_ONLY"
    stored = service.list("n", scope, service.REPORTS)
    assert len(stored) == 1
    assert "PRIVATE PROMPT" not in json.dumps(stored)
    assert "synthetic.safetensors" not in json.dumps(stored)
    assert service.list("other", {"mode": "local", "novel_id": "other"}, service.REPORTS) == []


@pytest.fixture
def client(service):
    app = FastAPI()
    def flag(name):
        assert name == "local_ai_workflow_inspector_v2"
        if not app.state.enabled: raise HTTPException(404, {"code": "EXPERIMENTAL_FEATURE_DISABLED"})
    def host(token):
        if token != "host-session": raise HTTPException(401, {"code": "SESSION_REQUIRED"})
    def authorize(nid, token, branch, permission):
        if nid != "n" or branch == "forbidden": raise HTTPException(403, {"code": "PROJECT_SCOPE_FORBIDDEN"})
        return "actor", {"mode": "local", "novel_id": nid}
    app.state.enabled = True
    router = create_local_ai_inspection_router(service, authorize, flag, host)
    app.include_router(router, prefix="/api")
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_http_auth_flag_readonly_reports_and_no_execution(client, service, graph, prefix):
    url = prefix + "/novels/n/experimental/local-ai/workflow-inspections"
    headers = {"X-Session-Token": "host-session"}
    assert client.get(url).status_code == 401
    assert client.get(url, headers={**headers, "X-Branch-Id": "forbidden"}).status_code == 403
    body = {"workflow_json": json.dumps(graph), "runtime_id": "local-fixture"}
    result = client.post(url + "/inspect", json=body, headers=headers)
    assert result.status_code == 200
    assert result.headers["cache-control"] == "no-store"
    assert client.get(url + "/reports", headers=headers).json()["items"] == []
    assert client.post(url + "/reports", json=body, headers=headers).status_code == 201
    assert len(client.get(url + "/reports", headers=headers).json()["items"]) == 1
    assert client.post(url + "/execute", json=body, headers=headers).status_code == 404
    client.app.state.enabled = False
    service.discovery_snapshot = Mock(side_effect=AssertionError("flag off must not access snapshot"))
    assert client.post(url + "/inspect", json=body, headers=headers).status_code == 404
    assert client.get(url + "/reports", headers=headers).status_code == 404


def test_http_errors_never_echo_raw_workflow_credentials(client):
    url = "/api/novels/n/experimental/local-ai/workflow-inspections/inspect"
    headers = {"X-Session-Token": "host-session"}
    for payload in [{"workflow_json": {"api_key": "SECRET"}}, {"workflow_json": "SECRET"}, {"workflow_json": "{}", "enable": "SECRET"}, {"workflow_json": "SECRET" * MAX_BYTES}]:
        result = client.post(url, json=payload, headers=headers)
        assert result.status_code in {413, 422}
        assert "SECRET" not in result.text

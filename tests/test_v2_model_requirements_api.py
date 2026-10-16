"""M4-B advisory routes over the original mounted authority and persistence.

No provider generation is invoked. File and PostgreSQL use the original fixture
owners; a positive match never becomes preview, dispatch or model verification.
"""
from copy import deepcopy

import pytest

from test_r3_mounted_contracts import checked, mounted, prefix, scoped
from test_v2_independent_workspace_api import client
from test_v2_creative_graph_api import graph_client
from test_v2_ai_execution_api import ai_client
from test_v2_ai_execution_runtime import FLAGS, generation_delta, owned_jobs


def match(e, body):
    return e.client.post(e.graph_base + "/model-match", headers=e.headers, json=body)


def test_provider_families_are_static_advisory_and_do_not_register_or_dispatch(ai_client, monkeypatch):
    e = ai_client
    before = deepcopy(e.graphs.store.read(e.nid, e.scope))
    providers = e.runtime.provider_registry.descriptors()
    models = e.runtime.model_registry.descriptors()
    def forbidden(*args, **kwargs):
        raise AssertionError("Provider catalog must not invoke/probe/admit")
    monkeypatch.setattr(e.models.router.broker, "candidates", forbidden)
    monkeypatch.setattr(e.manager, "prepare_graph_job", forbidden)
    response = e.client.get(e.graph_base + "/provider-contracts", headers=e.headers)
    data = checked(response)
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert data["project_id"] == e.nid and data["scope"] == e.scope
    assert data["contract"] == "creative-model-provider/1"
    assert data["advisory_only"] and not data["dispatch_authorized"] and not data["automatic_fallback"]
    assert data["task_types"] == ["TEXT_GENERATION", "IMAGE_GENERATION", "VIDEO_GENERATION"]
    assert [row["family"] for row in data["providers"]] == ["LOCAL_OLLAMA", "LM_STUDIO", "COMFYUI", "LLAMA_CPP", "API"]
    for row in data["providers"]:
        assert not row["availability"]["execution_available"]
        assert row["capability"]["inference_verification"] == row["real_model_verification"] == "NOT_RUN"
    assert e.runtime.provider_registry.descriptors() == providers
    assert e.runtime.model_registry.descriptors() == models
    assert e.graphs.store.read(e.nid, e.scope) == before
    assert not owned_jobs(e) and not generation_delta(e)


def test_requirement_matches_only_explicit_synthetic_route_and_never_grants_dispatch(ai_client, monkeypatch):
    e = ai_client
    before = deepcopy(e.graphs.store.read(e.nid, e.scope))
    def candidates(*, local_text_only=False):
        assert local_text_only is True, "No cloud credential or unrelated modality access"
        return [deepcopy(e.route)]
    monkeypatch.setattr(e.broker, "candidates", candidates)
    monkeypatch.setattr(e.broker, "hardware_capacity", lambda: {
        "state": "HOST_TOTAL_CAPACITY", "ram_mib": 8192, "vram_mib": 4096, "free_memory": None})
    value = {"task_type": "TEXT_GENERATION", "preferred_route": e.route["route_id"],
        "min_host_ram_mib": 8192, "min_host_vram_mib": 4096, "allow_synthetic": True,
        "api_available": True}
    data = checked(match(e, value))
    assert data["requirement"]["api_available"] is False
    assert data["api_provider"] == {"status": "RESERVED", "execution_available": False}
    assert data["hardware"]["free_memory"] is None
    row = data["matches"][0]
    assert row["eligible"] and row["preferred"] and row["synthetic"]
    assert row["hardware_state"] == "TOTAL_CAPACITY_ONLY" and not row["gpu_fit_verified"]
    assert not row["execution_authority"] and not data["dispatch_authorized"]
    assert row["reasons"] == []
    denied = checked(match(e, {**value, "allow_synthetic": False}))["matches"][0]
    assert not denied["eligible"] and "SYNTHETIC_NOT_AUTHORIZED" in denied["reasons"]
    other = checked(match(e, {**value, "preferred_route": "f" * 64}))["matches"][0]
    assert not other["eligible"] and not other["preferred"] and "EXACT_PREFERRED_ROUTE_REQUIRED" in other["reasons"]
    assert e.graphs.store.read(e.nid, e.scope) == before
    assert not owned_jobs(e) and not generation_delta(e)


@pytest.mark.parametrize("task", ["IMAGE_GENERATION", "VIDEO_GENERATION"])
def test_image_video_requests_cannot_claim_available_graph_execution(ai_client, task):
    e = ai_client
    data = checked(match(e, {"task_type": task, "allow_synthetic": True}))
    assert data["matches"]
    assert all(not row["eligible"] and not row["execution_authority"]
        and "GRAPH_" + task.split("_")[0] + "_EXECUTION_NOT_ENABLED" in row["reasons"] for row in data["matches"])
    assert not owned_jobs(e)


@pytest.mark.parametrize("hardware,expected", [
    ({"state": "UNAVAILABLE", "ram_mib": None, "vram_mib": None, "free_memory": None}, "UNKNOWN"),
    ({"state": "HOST_TOTAL_CAPACITY", "ram_mib": 1, "vram_mib": 1, "free_memory": None}, "INSUFFICIENT"),
])
def test_unknown_and_insufficient_host_capacity_fail_closed(ai_client, monkeypatch, hardware, expected):
    e = ai_client
    monkeypatch.setattr(e.broker, "hardware_capacity", lambda: deepcopy(hardware))
    data = checked(match(e, {"allow_synthetic": True, "min_host_ram_mib": 16, "min_host_vram_mib": 16}))
    assert all(not row["eligible"] and row["hardware_state"] == expected for row in data["matches"])
    assert not owned_jobs(e)


@pytest.mark.parametrize("payload", [
    {"local_only": False}, {"min_host_ram_mib": True}, {"min_host_vram_mib": "1"},
    {"min_host_vram_mib": 0}, {"min_host_ram_mib": 10000001}, {"task_type": "CODE_EXECUTION"},
    {"preferred_route": "mock"}, {"endpoint": "http://127.0.0.1:1234"},
    {"hardware": {"vram_mib": 999999}}, {"output": "untrusted"}, {"api_key": "not-a-real-key"},
])
def test_untrusted_provider_facts_paths_or_output_are_not_request_authority(ai_client, payload):
    assert match(ai_client, payload).status_code == 422
    assert not owned_jobs(ai_client)


@pytest.mark.parametrize("flag", [*FLAGS.split(","), "acceptance"])
def test_advisory_routes_still_require_every_flag_and_acceptance_override(ai_client, monkeypatch, flag):
    e = ai_client
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", FLAGS if flag == "acceptance" else ",".join(item for item in FLAGS.split(",") if item != flag))
    monkeypatch.setenv("V1_ACCEPTANCE_MODE", "true" if flag == "acceptance" else "")
    for response in (e.client.get(e.graph_base + "/provider-contracts", headers=e.headers), match(e, {})):
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "EXPERIMENTAL_FEATURE_DISABLED"


def test_provider_and_match_endpoints_require_host_identity(ai_client):
    e = ai_client
    for headers in ({}, {"X-Session-Token": "untrusted"}):
        assert e.client.get(e.graph_base + "/provider-contracts", headers=headers).status_code == 401
        assert e.client.post(e.graph_base + "/model-match", headers=headers, json={}).status_code == 401
    assert not owned_jobs(e)


@pytest.mark.parametrize("method", ["providers", "match_task"])
def test_late_revoke_suppresses_private_advisory_result(ai_client, monkeypatch, method):
    e = ai_client
    original = getattr(e.models, method)
    def revoke(*args):
        result = original(*args)
        e.sessions.revoke(e.host)
        result["private_marker"] = "not-to-be-disclosed"
        return result
    monkeypatch.setattr(e.models, method, revoke)
    response = (e.client.get(e.graph_base + "/provider-contracts", headers=e.headers)
        if method == "providers" else match(e, {}))
    assert response.status_code == 401 and "not-to-be-disclosed" not in response.text
    assert not owned_jobs(e)


def test_remote_collaboration_role_never_grants_local_provider_authority(ai_client, monkeypatch):
    e = scoped(ai_client, monkeypatch)
    for response in (e.client.get(e.graph_base + "/provider-contracts", headers=e.headers), match(e, {})):
        assert response.status_code == 403
    assert not owned_jobs(e)


def test_method_path_admission_does_not_create_wildcard_model_actions():
    from app.creative.workspace_api import is_independent_studio_route
    path = "/api/projects/fixture/studio/graphs/model-match"
    assert is_independent_studio_route("POST", path)
    for method, suffix in (("DELETE", ""), ("PATCH", ""), ("POST", "/dispatch"), ("POST", "/../dispatch")):
        assert not is_independent_studio_route(method, path + suffix)

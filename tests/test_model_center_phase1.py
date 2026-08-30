from __future__ import annotations

from pathlib import Path
import sys
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.model_center.domain import RuntimeDefinition, RuntimeType
from app.model_center.service import RuntimeLifecycle, create_default_model_center


def wait_for_exit(lifecycle: RuntimeLifecycle, runtime_id: str, timeout: float = 5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        instance = lifecycle.refresh(runtime_id)
        if instance and instance.state == "FAILED":
            return instance
        time.sleep(0.02)
    raise AssertionError(f"runtime {runtime_id} did not exit")


def test_registry_uses_structured_model_identity_and_verified_inference():
    center=create_default_model_center(); model=center.model("qwen36-27b-q4km")
    assert model["family"] == "QWEN3.6"
    assert model["variant"] == "27B"
    assert model["quantization"] == "Q4_K_M"
    assert model["verified"] is True


def test_flux_component_compatibility_is_variant_and_architecture_specific():
    center=create_default_model_center()
    klein=center.models["flux2-klein-4b-fp8"]; dev=center.models["flux2-dev"]
    assert center.compatibility.compatible(klein,"flux2-klein-qwen3-encoder")
    assert not center.compatibility.compatible(klein,"flux2-dev-mistral-encoder")
    assert center.compatibility.compatible(dev,"flux2-dev-mistral-encoder")
    assert not center.compatibility.compatible(dev,"flux2-klein-qwen3-encoder")


def test_rife_426_remains_incompatible_without_fallback():
    center=create_default_model_center()
    assert center.models["rife-426"].status == "INCOMPATIBLE"
    assert center.models["rife-426"].metadata["reason"] == "CHECKPOINT_ARCHITECTURE_MISMATCH"


def test_smoke_and_default_hardware_profiles_are_distinct():
    center=create_default_model_center()
    wan=center.profiles["wan22-smoke-rtx5080"]
    assert wan.profile_kind == "SMOKE" and wan.resolution == "256x256"
    assert center.profiles["qwen36-rtx5080-8k"].profile_kind == "DEFAULT"


def test_pipeline_is_a_graph_with_capability_contracts():
    pipeline=create_default_model_center().pipelines["LOCAL_VIDEO_PIPELINE_V1"]
    assert [node["model_id"] for node in pipeline.nodes] == ["wan22-ti2v-5b","seedvr2-3b","rife-49"]
    assert pipeline.required_capabilities == ("VIDEO","RESTORATION","INTERPOLATION")


def test_local_routing_policy_resolves_model_runtime_and_provider_adapter():
    center = create_default_model_center()
    text = center.route("TEXT")
    image = center.route("IMAGE_FAST")
    assert (text.model_id, text.runtime_id, text.provider_adapter) == (
        "qwen36-27b-q4km", "llama-cpp-local", "OPENAI_COMPATIBLE_TEXT"
    )
    assert (image.model_id, image.runtime_id, image.provider_adapter) == (
        "flux2-klein-4b-fp8", "comfyui-local", "COMFYUI_ASSET"
    )


def test_runtime_discovery_is_explicit_and_warns_on_non_loopback(tmp_path: Path):
    executable=tmp_path/"llama-server.exe"; executable.write_bytes(b"")
    lifecycle=RuntimeLifecycle(); definition=RuntimeDefinition("local",RuntimeType.LLAMA_CPP,str(executable),"http://0.0.0.0:8081","0.0.0.0")
    result=lifecycle.discover(definition)
    assert result["executable_exists"] is True
    assert result["security_warning"] == "RUNTIME_NOT_LOOPBACK_BOUND"
    with pytest.raises(ValueError,match="RUNTIME_NOT_LOOPBACK_BOUND"): lifecycle.start(definition)


@pytest.mark.parametrize("base_url", ["http://localhost.evil:8081", "http://192.168.1.20:8081"])
def test_runtime_rejects_lookalike_and_lan_urls(tmp_path: Path, base_url: str):
    executable = tmp_path / "llama-server.exe"
    executable.write_bytes(b"")
    definition = RuntimeDefinition(
        "unsafe",
        RuntimeType.LLAMA_CPP,
        str(executable),
        base_url,
        "127.0.0.1",
    )
    with pytest.raises(ValueError, match="RUNTIME_NOT_LOOPBACK_BOUND"):
        RuntimeLifecycle().start(definition)


def test_explicit_runtime_validation_can_probe_version():
    definition = RuntimeDefinition(
        "python-version",
        RuntimeType.LLAMA_CPP,
        sys.executable,
        "http://127.0.0.1:54320",
    )
    result = RuntimeLifecycle().discover(definition, probe_version=True)
    assert result["version"].startswith("Python ")


def test_runtime_stop_refuses_unowned_process():
    with pytest.raises(ValueError,match="RUNTIME_NOT_OWNED"): RuntimeLifecycle().stop("external")


def test_managed_runtime_captures_bounded_logs_and_detects_crash():
    lifecycle = RuntimeLifecycle(log_line_limit=3)
    script = "import sys;[print(f'line-{i}') for i in range(8)];print('failed',file=sys.stderr);sys.exit(17)"
    definition = RuntimeDefinition(
        "crashing",
        RuntimeType.LLAMA_CPP,
        sys.executable,
        "http://127.0.0.1:54321",
        "127.0.0.1",
        54321,
        launch_arguments=("-c", script),
    )
    lifecycle.start(definition)
    instance = wait_for_exit(lifecycle, "crashing")
    assert instance.error == "RUNTIME_EXITED:17"
    assert instance.health["exit_code"] == 17
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and not lifecycle.logs("crashing")["stderr"]:
        time.sleep(0.02)
    logs = lifecycle.logs("crashing")
    assert logs["stdout"] == ["line-5", "line-6", "line-7"]
    assert logs["stderr"] == ["failed"]


def test_owned_runtime_can_be_stopped_without_killing_external_processes():
    lifecycle = RuntimeLifecycle()
    definition = RuntimeDefinition(
        "sleeping",
        RuntimeType.LLAMA_CPP,
        sys.executable,
        "http://127.0.0.1:54322",
        "127.0.0.1",
        54322,
        launch_arguments=("-c", "import time;time.sleep(30)"),
    )
    started = lifecycle.start(definition)
    assert started.process_id
    stopped = lifecycle.stop("sleeping")
    assert stopped.state == "STOPPED"
    assert stopped.process_id is None


def test_running_process_health_can_recover_after_initial_probe_failure(monkeypatch):
    lifecycle = RuntimeLifecycle()
    definition = RuntimeDefinition(
        "recovering",
        RuntimeType.LLAMA_CPP,
        sys.executable,
        "http://127.0.0.1:54323",
        "127.0.0.1",
        54323,
        launch_arguments=("-c", "import time;time.sleep(30)"),
    )
    lifecycle.start(definition)
    try:
        assert lifecycle.health(definition).state == "FAILED"

        class HealthyResponse:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *_args): return None

        monkeypatch.setattr("app.model_center.service.urllib.request.urlopen", lambda *_args, **_kwargs: HealthyResponse())
        assert lifecycle.health(definition).state == "RUNNING"
    finally:
        lifecycle.stop("recovering")


def test_comfyui_runtime_is_external_only(tmp_path: Path):
    lifecycle = RuntimeLifecycle()
    definition = RuntimeDefinition(
        "comfy",
        RuntimeType.COMFYUI,
        working_directory=str(tmp_path),
        base_url="http://127.0.0.1:8188",
    )
    with pytest.raises(ValueError, match="RUNTIME_EXTERNAL_ONLY"):
        lifecycle.start(definition)


def test_runtime_configuration_persists_but_instance_state_does_not(tmp_path: Path):
    path=tmp_path/"runtime-config.json"; center=create_default_model_center(path)
    center.configure_runtime("llama-cpp-local",{"executable":str(tmp_path/"llama-server.exe"),"port":9090,"environment":{"SECRET":"not-persisted"}})
    payload = path.read_text(encoding="utf-8")
    assert '"schema_version": 1' in payload
    assert "SECRET" not in payload
    reloaded=create_default_model_center(path)
    assert reloaded.runtimes["llama-cpp-local"].port == 9090
    assert reloaded.lifecycle.instances == {}


def test_corrupt_or_unknown_runtime_configuration_falls_back_safely(tmp_path: Path):
    path = tmp_path / "runtime-config.json"
    path.write_text('{"schema_version":999,"runtimes":{"llama-cpp-local":{"port":1}}}', encoding="utf-8")
    center = create_default_model_center(path)
    assert center.runtimes["llama-cpp-local"].port == 8081
    path.write_text("not-json", encoding="utf-8")
    assert create_default_model_center(path).runtimes["llama-cpp-local"].port == 8081


def test_model_center_api_lists_models_runtimes_pipeline_and_health():
    client=TestClient(app)
    assert client.get("/api/model-center/models").status_code == 200
    assert client.get("/api/model-center/models/rife-426").json()["status"] == "INCOMPATIBLE"
    assert client.get("/api/model-center/runtimes").status_code == 200
    assert client.get("/api/model-center/pipelines").json()["items"][0]["id"] == "LOCAL_VIDEO_PIPELINE_V1"
    assert client.get("/api/model-center/health").json()["status"] == "READY"
    assert client.get("/api/v1/model-center/models").status_code == 200


def test_model_center_api_rejects_non_loopback_configuration():
    client = TestClient(app)
    response = client.post(
        "/api/model-center/runtimes/llama-cpp-local/validate",
        json={"bind_address": "0.0.0.0", "base_url": "http://0.0.0.0:8081"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "RUNTIME_NOT_LOOPBACK_BOUND"


def test_model_center_api_reports_start_stop_contract_errors():
    client = TestClient(app)
    assert client.post("/api/model-center/runtimes/comfyui-local/start").json()["code"] == "RUNTIME_EXTERNAL_ONLY"
    assert client.post("/api/model-center/runtimes/comfyui-local/stop").json()["code"] == "RUNTIME_NOT_OWNED"

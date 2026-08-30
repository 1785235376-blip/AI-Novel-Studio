from __future__ import annotations

import json
import os
from pathlib import Path
import threading
import sys
import time
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.actor_context import SessionContext
from app.config import settings
from app.dependencies import packaged_bootstrap_registry, trusted_session_resolver
from app.main import app
from app.model_center.api import create_model_center_router
from app.model_center.domain import ModelValidationRecord, RuntimeDefinition, RuntimeType
from app.model_center.service import RuntimeLifecycle, create_default_model_center


TRUSTED_TOKEN = "model-center-security-test"


@pytest.fixture(autouse=True)
def trusted_model_center_session():
    trusted_session_resolver.register(TRUSTED_TOKEN, SessionContext("model-center-test", "test-client", "local-author", "workspace-a"))
    try:
        yield
    finally:
        trusted_session_resolver.revoke(TRUSTED_TOKEN)


def auth_headers():
    return {"X-Session-Token": TRUSTED_TOKEN}


def wait_for_exit(lifecycle: RuntimeLifecycle, runtime_id: str, timeout: float = 5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        instance = lifecycle.refresh(runtime_id)
        if instance and instance.state == "FAILED":
            return instance
        time.sleep(0.02)
    raise AssertionError(f"runtime {runtime_id} did not exit")


def test_registry_uses_structured_model_identity_and_historical_inference():
    center=create_default_model_center(); model=center.model("qwen36-27b-q4km")
    assert model["family"] == "QWEN3.6"
    assert model["variant"] == "27B"
    assert model["quantization"] == "Q4_K_M"
    assert model["historically_validated"] is True
    assert model["verified"] is False


def test_flux_component_compatibility_is_variant_and_architecture_specific():
    center=create_default_model_center()
    klein=center.models["flux2-klein-4b-fp8"]; dev=center.models["flux2-dev"]
    assert center.compatibility.compatible(klein,"flux2-klein-qwen3-encoder")
    assert not center.compatibility.compatible(klein,"flux2-dev-mistral-encoder")
    assert center.compatibility.compatible(dev,"flux2-dev-mistral-encoder")
    assert not center.compatibility.compatible(dev,"flux2-klein-qwen3-encoder")


@pytest.mark.parametrize("missing", ["family", "variant", "architecture", "version"])
def test_component_compatibility_requires_every_identity_dimension(missing: str):
    center = create_default_model_center()
    model = center.models["flux2-klein-4b-fp8"]
    requirement = dict(model.compatibility["components"]["TEXT_ENCODER"])
    requirement.pop(missing)
    incomplete = replace(model, compatibility={"components": {"TEXT_ENCODER": requirement}})
    assert not center.compatibility.compatible(incomplete, "flux2-klein-qwen3-encoder")
    assert not center.compatibility.compatible(model, "unknown-component")


def test_component_compatibility_rejects_explicit_model_with_architecture_mismatch():
    center = create_default_model_center()
    model = center.models["flux2-klein-4b-fp8"]
    requirement = dict(model.compatibility["components"]["TEXT_ENCODER"])
    requirement["architecture"] = "MISTRAL"
    mismatched = replace(model, compatibility={"components": {"TEXT_ENCODER": requirement}})
    assert not center.compatibility.compatible(mismatched, "flux2-klein-qwen3-encoder")


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


def _currently_verified_center():
    center = create_default_model_center()
    center.configure_runtime("llama-cpp-local", {"executable": sys.executable})
    center.set_runtime_version("llama-cpp-local", "runtime-v1")
    center.set_current_hardware_profile("qwen36-27b-q4km", "qwen36-rtx5080-8k")
    fingerprint = center.runtime_fingerprint("llama-cpp-local")
    center.validations.append(ModelValidationRecord(
        "qwen36-27b-q4km",
        "llama-cpp-local",
        "qwen36-rtx5080-8k",
        "INFERENCE",
        "PASS",
        "2026-08-30T00:00:00+00:00",
        hash=center.models["qwen36-27b-q4km"].metadata["sha256"],
        runtime_version="runtime-v1",
        runtime_fingerprint=fingerprint or "",
        gpu="RTX 5080",
    ))
    return center


def test_current_verification_requires_complete_matching_identity():
    center = _currently_verified_center()
    assert center.model("qwen36-27b-q4km")["verified"] is True


def test_current_verification_invalidates_model_runtime_version_and_profile_changes(tmp_path: Path):
    center = _currently_verified_center()
    original_model = center.models["qwen36-27b-q4km"]
    center.models[original_model.id] = replace(original_model, metadata={**original_model.metadata, "sha256": "changed"})
    assert center.model(original_model.id)["verified"] is False
    center.models[original_model.id] = original_model

    center.set_runtime_version("llama-cpp-local", "runtime-v2")
    assert center.model(original_model.id)["verified"] is False
    center.set_runtime_version("llama-cpp-local", "runtime-v1")

    center.set_current_hardware_profile("qwen36-27b-q4km", "qwen36-rtx5080-16k")
    assert center.model(original_model.id)["verified"] is False
    center.set_current_hardware_profile("qwen36-27b-q4km", "qwen36-rtx5080-8k")

    other = tmp_path / "other-runtime.exe"
    other.write_bytes(b"")
    center.configure_runtime("llama-cpp-local", {"executable": str(other)})
    center.set_runtime_version("llama-cpp-local", "runtime-v1")
    assert center.model(original_model.id)["verified"] is False


@pytest.mark.parametrize("validation_type", ["FILE", "HASH", "LOAD"])
def test_non_inference_validation_never_marks_model_verified(validation_type: str):
    center = _currently_verified_center()
    center.validations = [replace(center.validations[-1], validation_type=validation_type)]
    assert center.model("qwen36-27b-q4km")["verified"] is False


@pytest.mark.parametrize("field", ["hash", "runtime_version", "runtime_fingerprint", "hardware_profile_id"])
def test_incomplete_validation_identity_is_historical_only(field: str):
    center = _currently_verified_center()
    center.validations = [replace(center.validations[-1], **{field: ""})]
    model = center.model("qwen36-27b-q4km")
    assert model["historically_validated"] is True
    assert model["verified"] is False


def test_runtime_discovery_is_explicit_and_warns_on_non_loopback(tmp_path: Path):
    executable=tmp_path/"llama-server.exe"; executable.write_bytes(b"")
    lifecycle=RuntimeLifecycle(); definition=RuntimeDefinition("local",RuntimeType.LLAMA_CPP,str(executable),"http://0.0.0.0:8081","0.0.0.0")
    result=lifecycle.discover(definition)
    assert result["executable_exists"] is True
    assert result["security_warning"] == "RUNTIME_NOT_LOOPBACK_BOUND"
    with pytest.raises(ValueError,match="RUNTIME_NOT_LOOPBACK_BOUND"): lifecycle.start(definition)


@pytest.mark.parametrize("base_url", [
    "http://localhost.evil:8081",
    "http://127.0.0.1.evil:8081",
    "http://192.168.1.20:8081",
    "http://169.254.169.254:80",
    "http://0.0.0.0:8081",
    "http://[::]:8081",
    "http://user@localhost:8081",
    "http://localhost:not-a-port",
])
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


class _ProbeHandler(BaseHTTPRequestHandler):
    status = 200
    location = ""
    hits: list[str] = []

    def do_GET(self):
        type(self).hits.append(self.path)
        self.send_response(type(self).status)
        if type(self).location:
            self.send_header("Location", type(self).location)
        self.end_headers()

    def log_message(self, *_args):
        pass


def _serve(handler: type[BaseHTTPRequestHandler]):
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_runtime_probe_allows_direct_loopback_and_ignores_proxy(monkeypatch):
    class Direct(_ProbeHandler):
        hits = []

    server = _serve(Direct)
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    try:
        definition = RuntimeDefinition("direct", RuntimeType.COMFYUI, base_url=f"http://127.0.0.1:{server.server_port}", health_endpoint="/health")
        assert RuntimeLifecycle().health(definition).state == "RUNNING"
        assert Direct.hits == ["/health"]
    finally:
        server.shutdown()


@pytest.mark.parametrize("target", [
    "http://192.168.1.20/private",
    "http://example.com/public",
    "http://169.254.169.254/latest/meta-data",
])
@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_runtime_probe_rejects_redirect_without_requesting_target(target: str, status: int):
    class Redirect(_ProbeHandler):
        pass
    Redirect.status = status
    Redirect.location = target
    Redirect.hits = []

    server = _serve(Redirect)
    try:
        definition = RuntimeDefinition("redirect", RuntimeType.COMFYUI, base_url=f"http://127.0.0.1:{server.server_port}", health_endpoint="/health")
        instance = RuntimeLifecycle().health(definition)
        assert instance.error == "MODEL_CENTER_RUNTIME_REDIRECT_REJECTED"
        assert Redirect.hits == ["/health"]
    finally:
        server.shutdown()


def test_runtime_probe_rejects_redirect_even_when_target_is_loopback():
    class Target(_ProbeHandler):
        hits = []

    target = _serve(Target)

    class Redirect(_ProbeHandler):
        status = 302
        location = f"http://127.0.0.1:{target.server_port}/escaped"
        hits = []

    redirect = _serve(Redirect)
    try:
        definition = RuntimeDefinition("redirect", RuntimeType.COMFYUI, base_url=f"http://127.0.0.1:{redirect.server_port}", health_endpoint="/health")
        instance = RuntimeLifecycle().health(definition)
        assert instance.error == "MODEL_CENTER_RUNTIME_REDIRECT_REJECTED"
        assert Target.hits == []
    finally:
        redirect.shutdown()
        target.shutdown()


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


def test_double_start_is_idempotent_and_owns_one_process():
    lifecycle = RuntimeLifecycle()
    definition = RuntimeDefinition(
        "single",
        RuntimeType.LLAMA_CPP,
        sys.executable,
        "http://127.0.0.1:54324",
        "127.0.0.1",
        54324,
        launch_arguments=("-c", "import time;time.sleep(30)"),
    )
    first = lifecycle.start(definition)
    try:
        second = lifecycle.start(definition)
        assert second.process_id == first.process_id
        assert len(lifecycle._owned) == 1
    finally:
        lifecycle.stop("single")


def test_managed_runtime_does_not_inherit_host_secrets(monkeypatch):
    secret = "super-secret-value"
    monkeypatch.setenv("MODEL_CENTER_TEST_SECRET", secret)
    lifecycle = RuntimeLifecycle()
    script = "import os;print(os.getenv('MODEL_CENTER_TEST_SECRET','missing'));print(bool(os.getenv('PATH')))"
    definition = RuntimeDefinition(
        "isolated-env",
        RuntimeType.LLAMA_CPP,
        sys.executable,
        "http://127.0.0.1:54325",
        "127.0.0.1",
        54325,
        launch_arguments=("-c", script),
    )
    lifecycle.start(definition)
    wait_for_exit(lifecycle, "isolated-env")
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and len(lifecycle.logs("isolated-env")["stdout"]) < 2:
        time.sleep(0.02)
    assert lifecycle.logs("isolated-env")["stdout"] == ["missing", "True"]


def test_secret_like_explicit_runtime_environment_is_rejected():
    definition = RuntimeDefinition(
        "secret-env",
        RuntimeType.LLAMA_CPP,
        sys.executable,
        "http://127.0.0.1:54326",
        environment={"OPENAI_API_KEY": "secret"},
    )
    with pytest.raises(ValueError, match="RUNTIME_ENVIRONMENT_SECRET_REJECTED"):
        RuntimeLifecycle().start(definition)


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

        lifecycle._probe_open = lambda *_args, **_kwargs: HealthyResponse()
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
    center.configure_runtime("llama-cpp-local",{"executable":str(tmp_path/"llama-server.exe"),"port":9090,"environment":{"CUDA_VISIBLE_DEVICES":"0"}})
    payload = path.read_text(encoding="utf-8")
    assert '"schema_version": 1' in payload
    assert "CUDA_VISIBLE_DEVICES" not in payload
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
    path.write_text('{"schema_version":1,"runtimes":{"llama-cpp-local":[]}}', encoding="utf-8")
    assert create_default_model_center(path).runtimes["llama-cpp-local"].port == 8081
    path.write_text('{"schema_version":1,"runtimes":{"llama-cpp-local":{"base_url":"http://0.0.0.0:8081"}}}', encoding="utf-8")
    assert create_default_model_center(path).runtimes["llama-cpp-local"].base_url == "http://127.0.0.1:8081"


def test_concurrent_runtime_configuration_keeps_disk_and_memory_consistent(tmp_path: Path):
    path = tmp_path / "runtime-config.json"
    center = create_default_model_center(path)
    barrier = threading.Barrier(3)
    errors: list[Exception] = []

    def configure(port: int):
        try:
            barrier.wait()
            center.configure_runtime("llama-cpp-local", {"port": port})
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=configure, args=(port,)) for port in (9101, 9102)]
    for thread in threads: thread.start()
    barrier.wait()
    for thread in threads: thread.join()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert errors == []
    assert payload["runtimes"]["llama-cpp-local"]["port"] == center.runtimes["llama-cpp-local"].port
    assert not list(tmp_path.glob("*.tmp"))


def test_failed_runtime_configuration_write_does_not_publish_memory_state(tmp_path: Path, monkeypatch):
    path = tmp_path / "runtime-config.json"
    center = create_default_model_center(path)
    original = center.runtimes["llama-cpp-local"]

    def fail_replace(*_args):
        raise OSError("simulated write failure")

    monkeypatch.setattr("app.model_center.service.os.replace", fail_replace)
    with pytest.raises(ValueError, match="RUNTIME_CONFIG_WRITE_FAILED"):
        center.configure_runtime("llama-cpp-local", {"port": 9199})
    assert center.runtimes["llama-cpp-local"] == original
    assert not list(tmp_path.glob("*.tmp"))


def test_model_center_api_lists_models_runtimes_pipeline_and_health():
    client=TestClient(app)
    assert client.get("/api/model-center/models").status_code == 200
    assert client.get("/api/model-center/models/rife-426").json()["status"] == "INCOMPATIBLE"
    assert client.get("/api/model-center/runtimes").status_code == 200
    assert client.get("/api/model-center/pipelines").json()["items"][0]["id"] == "LOCAL_VIDEO_PIPELINE_V1"
    assert client.get("/api/model-center/health").json()["status"] == "READY"
    assert client.get("/api/v1/model-center/models").status_code == 200


@pytest.mark.parametrize("prefix", ["/api/model-center", "/api/v1/model-center"])
def test_default_local_health_declares_read_only_without_trusted_session(prefix: str):
    client = TestClient(app)
    authorization = client.get(f"{prefix}/health").json()["mutation_authorization"]
    assert authorization == {
        "can_mutate": False,
        "mutation_auth_mode": "DEVELOPMENT_SESSION_REQUIRED",
    }
    assert client.get(f"{prefix}/models").status_code == 200
    assert client.get(f"{prefix}/runtimes").status_code == 200


@pytest.mark.parametrize("prefix", ["/api/model-center", "/api/v1/model-center"])
def test_explicit_dev_session_enables_mutation_capability(prefix: str):
    client = TestClient(app)
    enabled = client.get(f"{prefix}/health", headers=auth_headers()).json()["mutation_authorization"]
    invalid = client.get(f"{prefix}/health", headers={"X-Session-Token": "invalid"}).json()["mutation_authorization"]
    assert enabled == {"can_mutate": True, "mutation_auth_mode": "DEVELOPMENT_SESSION_REQUIRED"}
    assert invalid["can_mutate"] is False


def test_model_center_api_rejects_non_loopback_configuration():
    client = TestClient(app)
    response = client.post(
        "/api/model-center/runtimes/llama-cpp-local/validate",
        json={"bind_address": "0.0.0.0", "base_url": "http://0.0.0.0:8081"},
        headers=auth_headers(),
    )
    assert response.status_code == 409
    assert response.json()["code"] == "RUNTIME_NOT_LOOPBACK_BOUND"


def test_model_center_api_reports_start_stop_contract_errors():
    client = TestClient(app)
    assert client.post("/api/model-center/runtimes/comfyui-local/start", headers=auth_headers()).json()["code"] == "RUNTIME_EXTERNAL_ONLY"
    assert client.post("/api/model-center/runtimes/comfyui-local/stop", headers=auth_headers()).json()["code"] == "RUNTIME_NOT_OWNED"


@pytest.mark.parametrize("prefix", ["/api/model-center", "/api/v1/model-center"])
@pytest.mark.parametrize("operation", ["validate", "start", "stop"])
def test_model_center_mutations_require_trusted_session_in_local_mode(prefix: str, operation: str):
    response = TestClient(app).post(f"{prefix}/runtimes/comfyui-local/{operation}", json={})
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "SESSION_REQUIRED"


@pytest.mark.parametrize("prefix", ["/api/model-center", "/api/v1/model-center"])
@pytest.mark.parametrize("operation", ["validate", "start", "stop"])
def test_model_center_mutations_accept_registered_trusted_session(prefix: str, operation: str):
    response = TestClient(app).post(
        f"{prefix}/runtimes/comfyui-local/{operation}",
        json={},
        headers=auth_headers(),
    )
    assert response.status_code != 401


@pytest.mark.parametrize("prefix", ["/api/model-center", "/api/v1/model-center"])
@pytest.mark.parametrize("mode", ["collaboration", "packaged"])
def test_model_center_mutation_auth_applies_in_every_runtime_mode(prefix: str, mode: str, monkeypatch):
    original = (settings.enable_collaboration_runtime, settings.enable_packaged_runtime)

    class PackagedManager:
        def resolve_issued_session(self, token):
            return trusted_session_resolver.resolve(token)

    try:
        object.__setattr__(settings, "enable_collaboration_runtime", True)
        object.__setattr__(settings, "enable_packaged_runtime", mode == "packaged")
        if mode == "packaged":
            monkeypatch.setattr(packaged_bootstrap_registry, "current", lambda: PackagedManager())
        client = TestClient(app)
        assert client.post(f"{prefix}/runtimes/comfyui-local/start").status_code == 401
        assert client.post(f"{prefix}/runtimes/comfyui-local/start", headers=auth_headers()).status_code == 409
        authorization = client.get(f"{prefix}/health", headers=auth_headers()).json()["mutation_authorization"]
        assert authorization["can_mutate"] is True
        assert authorization["mutation_auth_mode"] == ("PACKAGED_BOOTSTRAP" if mode == "packaged" else "TRUSTED_SESSION")
    finally:
        object.__setattr__(settings, "enable_collaboration_runtime", original[0])
        object.__setattr__(settings, "enable_packaged_runtime", original[1])


def test_raw_runtime_logs_are_not_exposed_by_general_api(tmp_path: Path):
    secret = "super-secret-value"
    center = create_default_model_center()
    center.configure_runtime("llama-cpp-local", {
        "executable": sys.executable,
        "base_url": "http://127.0.0.1:54327",
        "port": 54327,
        "launch_arguments": ["-c", f"print({secret!r})"],
    })
    started = center.lifecycle.start(center.runtimes["llama-cpp-local"])
    assert secret not in json.dumps(started.__dict__)
    wait_for_exit(center.lifecycle, "llama-cpp-local")
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and not center.lifecycle.logs("llama-cpp-local")["stdout"]:
        time.sleep(0.02)
    assert secret in center.lifecycle.logs("llama-cpp-local")["stdout"]

    isolated_app = FastAPI()
    isolated_app.include_router(create_model_center_router(center))
    client = TestClient(isolated_app)
    assert secret not in client.get("/api/model-center/runtimes").text
    assert secret not in client.get("/api/model-center/runtimes/llama-cpp-local").text
    stopped = client.post("/api/model-center/runtimes/llama-cpp-local/stop")
    assert secret not in stopped.text
    assert secret not in client.get("/api/model-center/health").text

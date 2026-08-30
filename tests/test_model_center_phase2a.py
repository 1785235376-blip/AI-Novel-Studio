from __future__ import annotations

import json
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.model_center.api import create_model_center_router
from app.model_center.domain import RuntimeDefinition, RuntimeManagement, RuntimeType
from app.model_center.runtime_profiles import LlamaCppRuntimeConfig, RuntimeLogSanitizer
from app.model_center.service import RuntimeLifecycle, create_default_model_center
from app.actor_context import SessionContext
from app.dependencies import trusted_session_resolver
from app.main import app as production_app


def llama_values(tmp_path: Path, port: int = 19081) -> dict:
    executable = tmp_path / "llama-server.exe"
    model = tmp_path / "model.gguf"
    executable.write_bytes(b"runtime")
    model.write_bytes(b"GGUF")
    return {
        "runtime_type": "LLAMA_CPP",
        "management": "MANAGED",
        "executable": str(executable),
        "working_directory": str(tmp_path),
        "model_path": str(model),
        "base_url": f"http://127.0.0.1:{port}",
        "bind_address": "127.0.0.1",
        "port": port,
        "health_endpoint": "/v1/models",
        "context_size": 8192,
        "gpu_layers": 40,
        "threads": 12,
        "batch_size": 512,
        "extra_arguments": ["--flash-attn"],
    }


def test_llama_profile_builds_argv_without_shell_or_protected_overrides(tmp_path: Path):
    center = create_default_model_center()
    configured = center.configure_runtime_profile("llama-cpp-local", llama_values(tmp_path))
    assert configured.management == RuntimeManagement.MANAGED
    assert configured.launch_arguments[:2] == ("--model", str(tmp_path / "model.gguf"))
    assert configured.launch_arguments.count("--host") == 1
    assert configured.launch_arguments.count("--port") == 1
    assert configured.launch_arguments[-1] == "--flash-attn"


@pytest.mark.parametrize("extra", [["--host"], ["--host=0.0.0.0"], ["--port"], ["--model"], ["--ctx-size"], ["--unknown"]])
def test_llama_profile_rejects_protected_and_unknown_arguments(tmp_path: Path, extra: list[str]):
    values = llama_values(tmp_path); values["extra_arguments"] = extra
    with pytest.raises(ValueError, match="RUNTIME_(PROTECTED_ARGUMENT|ARGUMENT_NOT_ALLOWED)"):
        create_default_model_center().configure_runtime_profile("llama-cpp-local", values)


def test_runtime_profile_rejects_unknown_fields_and_non_loopback(tmp_path: Path):
    values = llama_values(tmp_path); values["shell_command"] = "calc.exe"
    with pytest.raises(ValueError, match="RUNTIME_CONFIG_INVALID"):
        create_default_model_center().configure_runtime_profile("llama-cpp-local", values)
    values = llama_values(tmp_path); values["bind_address"] = "0.0.0.0"
    with pytest.raises(ValueError, match="RUNTIME_NOT_LOOPBACK_BOUND"):
        create_default_model_center().configure_runtime_profile("llama-cpp-local", values)


def test_runtime_profile_transaction_persists_then_publishes(tmp_path: Path, monkeypatch):
    sidecar = tmp_path / "runtime-config.json"
    center = create_default_model_center(sidecar)
    original = center.runtimes["llama-cpp-local"]
    monkeypatch.setattr("app.model_center.service.os.replace", lambda *_args: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(ValueError, match="RUNTIME_CONFIG_WRITE_FAILED"):
        center.configure_runtime_profile("llama-cpp-local", llama_values(tmp_path))
    assert center.runtimes["llama-cpp-local"] == original


def test_llama_validation_checks_gguf_and_cuda_backend(tmp_path: Path, monkeypatch):
    center = create_default_model_center()
    values = llama_values(tmp_path)
    configured = center.configure_runtime_profile("llama-cpp-local", values)
    class Version:
        stdout = b"llama.cpp b7000 CUDA"
        stderr = b""
    monkeypatch.setattr("app.model_center.service.subprocess.run", lambda *_args, **_kwargs: Version())
    assert center.validate_runtime(configured.id)["status"] == "READY"
    Path(configured.model_path).write_bytes(b"nope")
    result = center.validate_runtime(configured.id)
    assert result["safe_error_code"] == "MODEL_FILE_INVALID"


def test_managed_start_rejects_port_conflict(tmp_path: Path):
    listener = socket.socket(); listener.bind(("127.0.0.1", 0)); listener.listen()
    port = listener.getsockname()[1]
    try:
        definition = RuntimeDefinition(
            "conflict", RuntimeType.LLAMA_CPP, sys.executable, f"http://127.0.0.1:{port}",
            "127.0.0.1", port, launch_arguments=("-c", "pass"), management=RuntimeManagement.MANAGED,
        )
        with pytest.raises(ValueError, match="PORT_IN_USE"):
            RuntimeLifecycle().start(definition)
    finally:
        listener.close()


def test_log_buffer_is_bounded_and_redacted():
    lifecycle = RuntimeLifecycle(log_line_limit=2, log_byte_limit=100)
    lifecycle._logs["runtime"] = {"stdout": __import__("collections").deque(maxlen=2), "stderr": __import__("collections").deque(maxlen=2)}
    lifecycle._logs["runtime"]["stdout"].extend(["old", "TOKEN=abc123", "Authorization: Bearer secret-value"])
    result = lifecycle.sanitized_logs("runtime")["stdout"]
    assert "old" not in result
    assert "abc123" not in json.dumps(result)
    assert "secret-value" not in json.dumps(result)
    assert "[REDACTED]" in json.dumps(result)
    assert RuntimeLogSanitizer.sanitize("password = hunter2") == "password = [REDACTED]"


class ComfyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        payload = {"KSampler": {}, "RIFEInterpolation": {}, "WanVideoSampler": {}} if self.path == "/object_info" else {"system": {}}
        encoded = json.dumps(payload).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(encoded))); self.end_headers(); self.wfile.write(encoded)

    def log_message(self, *_args):
        pass


def test_comfy_capability_nodes_do_not_become_verified_models():
    server = HTTPServer(("127.0.0.1", 0), ComfyHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        center = create_default_model_center()
        center.configure_runtime_profile("comfyui-local", {
            "runtime_type": "COMFYUI", "management": "EXTERNAL", "installation_path": "",
            "base_url": f"http://127.0.0.1:{server.server_port}", "bind_address": "127.0.0.1",
            "port": server.server_port, "health_endpoint": "/system_stats",
        })
        snapshot = center.capability_snapshot("comfyui-local")
        assert "RIFEInterpolation" in snapshot.node_classes
        assert snapshot.available_models == ()
        assert center.model("rife-426")["verified"] is False
        assert center.runtimes["comfyui-local"].management == RuntimeManagement.EXTERNAL
        with pytest.raises(ValueError, match="RUNTIME_NOT_OWNED"):
            center.lifecycle.stop("comfyui-local")
    finally:
        server.shutdown()


def protected_client(tmp_path: Path, prefix: str) -> tuple[TestClient, object]:
    center = create_default_model_center(tmp_path / "runtime-config.json")
    app = FastAPI()
    app.include_router(create_model_center_router(
        center, prefix=prefix,
        mutation_authorization=lambda token: {"can_mutate": token == "trusted", "mutation_auth_mode": "TEST"},
    ))
    return TestClient(app), center


@pytest.mark.parametrize("prefix", ["/api/model-center", "/api/v1/model-center"])
def test_configuration_diagnostics_and_logs_require_trusted_session(tmp_path: Path, prefix: str):
    client, center = protected_client(tmp_path, prefix)
    paths = ["configuration", "diagnostics", "logs"]
    for suffix in paths:
        response = client.get(f"{prefix}/runtimes/llama-cpp-local/{suffix}")
        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "SESSION_REQUIRED"
    assert client.put(f"{prefix}/runtimes/llama-cpp-local/configuration", json=llama_values(tmp_path)).status_code == 401

    updated = client.put(
        f"{prefix}/runtimes/llama-cpp-local/configuration",
        headers={"X-Session-Token": "trusted"}, json=llama_values(tmp_path),
    )
    assert updated.status_code == 200
    assert updated.json()["model_path"].endswith("model.gguf")
    public = client.get(f"{prefix}/runtimes/llama-cpp-local").json()
    assert "model_path" not in public and "executable" not in public
    center.lifecycle._logs["llama-cpp-local"] = {"stdout": __import__("collections").deque(["TOKEN=value"]), "stderr": __import__("collections").deque()}
    logs = client.get(f"{prefix}/runtimes/llama-cpp-local/logs", headers={"X-Session-Token": "trusted"})
    assert logs.status_code == 200 and "value" not in logs.text
    assert client.get(f"{prefix}/runtimes/llama-cpp-local/diagnostics", headers={"X-Session-Token": "trusted"}).status_code == 200


@pytest.mark.parametrize("prefix", ["/api/model-center", "/api/v1/model-center"])
def test_capability_snapshot_is_read_only_and_api_versions_match(tmp_path: Path, prefix: str):
    client, _ = protected_client(tmp_path, prefix)
    response = client.get(f"{prefix}/runtimes/llama-cpp-local/capabilities")
    assert response.status_code == 200
    assert response.json()["runtime_id"] == "llama-cpp-local"


@pytest.mark.parametrize("prefix", ["/api/model-center", "/api/v1/model-center"])
@pytest.mark.parametrize("suffix", ["configuration", "diagnostics", "logs"])
def test_production_middleware_protects_new_control_reads(prefix: str, suffix: str):
    token = "phase2a-production-auth"
    trusted_session_resolver.register(token, SessionContext("phase2a", "client", "local-author", "workspace-a"))
    try:
        client = TestClient(production_app)
        assert client.get(f"{prefix}/runtimes/llama-cpp-local/{suffix}").status_code == 401
        assert client.get(f"{prefix}/runtimes/llama-cpp-local/{suffix}", headers={"X-Session-Token": "invalid"}).status_code == 401
        assert client.get(f"{prefix}/runtimes/llama-cpp-local/{suffix}", headers={"X-Session-Token": token}).status_code == 200
    finally:
        trusted_session_resolver.revoke(token)

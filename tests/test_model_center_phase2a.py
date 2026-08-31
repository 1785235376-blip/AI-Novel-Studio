from __future__ import annotations

import json
import os
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
            "127.0.0.1", port, management=RuntimeManagement.MANAGED,
        )
        with pytest.raises(ValueError, match="PORT_IN_USE"):
            RuntimeLifecycle().start(definition, host_argv=("-c", "pass"))
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


class _CapturingPopen:
    calls: list[list[str]] = []

    def __init__(self, args, **_kwargs):
        type(self).calls.append(list(args))
        self.pid = 4242
        self.stdout = None
        self.stderr = None

    def poll(self):
        return None


def _patch_popen(monkeypatch) -> type[_CapturingPopen]:
    _CapturingPopen.calls = []
    monkeypatch.setattr("app.model_center.service.subprocess.Popen", _CapturingPopen)
    return _CapturingPopen


def test_raw_launch_arguments_cannot_be_submitted_or_persisted(tmp_path: Path):
    sidecar = tmp_path / "runtime-config.json"
    center = create_default_model_center(sidecar)
    values = llama_values(tmp_path)
    values["launch_arguments"] = ["--host", "0.0.0.0", "--port", "8081"]
    with pytest.raises(ValueError, match="RUNTIME_ARGV_NOT_ALLOWED"):
        center.configure_runtime_profile("llama-cpp-local", values)
    with pytest.raises(ValueError, match="RUNTIME_ARGV_NOT_ALLOWED"):
        center.configure_runtime("llama-cpp-local", {"launch_arguments": ["--host", "0.0.0.0"]})
    assert center.runtimes["llama-cpp-local"].bind_address == "127.0.0.1"
    if sidecar.is_file():
        persisted = json.loads(sidecar.read_text(encoding="utf-8"))
        stored = persisted.get("runtimes", {}).get("llama-cpp-local", {})
        assert "launch_arguments" not in stored
        assert stored.get("bind_address", "127.0.0.1") != "0.0.0.0"


def test_raw_launch_arguments_rejected_on_validate_and_put(tmp_path: Path):
    client, center = protected_client(tmp_path, "/api/model-center")
    headers = {"X-Session-Token": "trusted"}
    validate = client.post(
        "/api/model-center/runtimes/llama-cpp-local/validate",
        headers=headers,
        json={"launch_arguments": ["--host", "0.0.0.0"], "bind_address": "127.0.0.1", "base_url": "http://127.0.0.1:8081"},
    )
    assert validate.status_code == 409
    assert validate.json()["detail"]["code"] == "RUNTIME_ARGV_NOT_ALLOWED"
    put = client.put(
        "/api/model-center/runtimes/llama-cpp-local/configuration",
        headers=headers,
        json={**llama_values(tmp_path), "launch_arguments": ["--host", "0.0.0.0"]},
    )
    assert put.status_code == 409
    assert put.json()["detail"]["code"] == "RUNTIME_ARGV_NOT_ALLOWED"
    assert "0.0.0.0" not in center.runtimes["llama-cpp-local"].launch_arguments


def test_wildcard_bind_in_stale_argv_cannot_bypass_typed_bind(tmp_path: Path, monkeypatch):
    captured = _patch_popen(monkeypatch)
    executable = tmp_path / "llama-server.exe"
    model = tmp_path / "model.gguf"
    executable.write_bytes(b"runtime")
    model.write_bytes(b"GGUF")
    definition = RuntimeDefinition(
        "llama-cpp-local",
        RuntimeType.LLAMA_CPP,
        str(executable),
        "http://127.0.0.1:19101",
        "127.0.0.1",
        19101,
        launch_arguments=("--host", "0.0.0.0", "--port", "19101"),
        management=RuntimeManagement.MANAGED,
        model_path=str(model),
        extra_arguments=("--flash-attn",),
    )
    RuntimeLifecycle().start(definition)
    argv = captured.calls[0]
    assert "0.0.0.0" not in argv
    assert argv[argv.index("--host") + 1] == "127.0.0.1"
    assert argv[argv.index("--port") + 1] == "19101"
    assert argv[argv.index("--model") + 1] == str(model)
    assert "--flash-attn" in argv


def test_stale_sidecar_raw_argv_cannot_reach_popen(tmp_path: Path, monkeypatch):
    captured = _patch_popen(monkeypatch)
    executable = tmp_path / "llama-server.exe"
    model = tmp_path / "model.gguf"
    executable.write_bytes(b"runtime")
    model.write_bytes(b"GGUF")
    sidecar = tmp_path / "runtime-config.json"
    sidecar.write_text(json.dumps({
        "schema_version": 1,
        "runtimes": {
            "llama-cpp-local": {
                "executable": str(executable),
                "model_path": str(model),
                "working_directory": str(tmp_path),
                "base_url": "http://127.0.0.1:19102",
                "bind_address": "127.0.0.1",
                "port": 19102,
                "health_endpoint": "/v1/models",
                "launch_arguments": ["--host", "0.0.0.0", "--port", "19102", "-c", "print('pwned')"],
            }
        },
    }), encoding="utf-8")
    center = create_default_model_center(sidecar)
    stored = json.dumps(center.runtimes["llama-cpp-local"].launch_arguments)
    assert "0.0.0.0" not in stored
    assert "-c" not in center.runtimes["llama-cpp-local"].launch_arguments
    center.lifecycle.start(center.runtimes["llama-cpp-local"])
    argv = captured.calls[0]
    assert "0.0.0.0" not in argv
    assert "-c" not in argv
    assert "pwned" not in argv
    assert argv[argv.index("--host") + 1] == "127.0.0.1"


def test_python_c_raw_argv_cannot_enter_managed_launch_path(tmp_path: Path, monkeypatch):
    captured = _patch_popen(monkeypatch)
    executable = tmp_path / "llama-server.exe"
    model = tmp_path / "model.gguf"
    executable.write_bytes(b"runtime")
    model.write_bytes(b"GGUF")
    definition = RuntimeDefinition(
        "managed",
        RuntimeType.LLAMA_CPP,
        str(executable),
        "http://127.0.0.1:19103",
        "127.0.0.1",
        19103,
        launch_arguments=("-c", "import os;os.write(1,b'pwned')"),
        management=RuntimeManagement.MANAGED,
        model_path=str(model),
    )
    RuntimeLifecycle().start(definition)
    argv = captured.calls[0]
    assert "-c" not in argv
    assert "pwned" not in " ".join(argv)
    assert argv[0] == str(executable)
    assert "--model" in argv


def test_typed_allowed_runtime_profile_still_launches(tmp_path: Path, monkeypatch):
    captured = _patch_popen(monkeypatch)
    center = create_default_model_center()
    configured = center.configure_runtime_profile("llama-cpp-local", llama_values(tmp_path, port=19104))
    center.lifecycle.start(configured)
    argv = captured.calls[0]
    assert argv[0] == str(tmp_path / "llama-server.exe")
    assert argv[argv.index("--host") + 1] == "127.0.0.1"
    assert argv[argv.index("--port") + 1] == "19104"
    assert "--flash-attn" in argv
    assert "0.0.0.0" not in argv


def test_host_argv_wildcard_bind_is_still_rejected(tmp_path: Path):
    executable = tmp_path / "llama-server.exe"
    executable.write_bytes(b"runtime")
    definition = RuntimeDefinition(
        "host-argv",
        RuntimeType.LLAMA_CPP,
        str(executable),
        "http://127.0.0.1:19105",
        "127.0.0.1",
        19105,
        management=RuntimeManagement.MANAGED,
    )
    with pytest.raises(ValueError, match="RUNTIME_NOT_LOOPBACK_BOUND"):
        RuntimeLifecycle().start(definition, host_argv=("--host", "0.0.0.0", "--port", "19105"))


def test_editable_configuration_get_put_roundtrip(tmp_path: Path):
    client, _center = protected_client(tmp_path, "/api/model-center")
    headers = {"X-Session-Token": "trusted"}
    created = client.put(
        "/api/model-center/runtimes/llama-cpp-local/configuration",
        headers=headers,
        json=llama_values(tmp_path),
    )
    assert created.status_code == 200
    for leaked in ("launch_arguments", "capabilities", "status", "provider_adapter", "environment"):
        assert leaked not in created.json()
    editable = client.get("/api/model-center/runtimes/llama-cpp-local/configuration", headers=headers)
    assert editable.status_code == 200
    payload = editable.json()
    for leaked in ("launch_arguments", "capabilities", "status", "provider_adapter", "environment"):
        assert leaked not in payload
    roundtrip = client.put(
        "/api/model-center/runtimes/llama-cpp-local/configuration",
        headers=headers,
        json=payload,
    )
    assert roundtrip.status_code == 200
    edited = {key: value for key, value in payload.items() if key != "id"}
    edited["context_size"] = 4096
    saved = client.put(
        "/api/model-center/runtimes/llama-cpp-local/configuration",
        headers=headers,
        json=edited,
    )
    assert saved.status_code == 200
    assert saved.json()["context_size"] == 4096
    reread = client.get("/api/model-center/runtimes/llama-cpp-local/configuration", headers=headers)
    assert reread.json()["context_size"] == 4096
    assert "launch_arguments" not in reread.json()


def test_never_started_logs_always_include_empty_arrays(tmp_path: Path):
    client, center = protected_client(tmp_path, "/api/model-center")
    assert center.lifecycle.sanitized_logs("llama-cpp-local") == {"stdout": [], "stderr": []}
    logs = client.get(
        "/api/model-center/runtimes/llama-cpp-local/logs",
        headers={"X-Session-Token": "trusted"},
    )
    assert logs.status_code == 200
    assert logs.json() == {"runtime_id": "llama-cpp-local", "stdout": [], "stderr": []}


def test_relative_executable_cannot_use_path_lookup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "llama-server.exe").write_bytes(b"runtime")
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))
    values = llama_values(tmp_path)
    values["executable"] = "llama-server.exe"
    with pytest.raises(ValueError, match="RUNTIME_EXECUTABLE_NOT_ABSOLUTE"):
        create_default_model_center().configure_runtime_profile("llama-cpp-local", values)
    definition = RuntimeDefinition(
        "relative",
        RuntimeType.LLAMA_CPP,
        "llama-server.exe",
        "http://127.0.0.1:19120",
        "127.0.0.1",
        19120,
        management=RuntimeManagement.MANAGED,
        model_path=str(tmp_path / "model.gguf"),
    )
    with pytest.raises(ValueError, match="RUNTIME_EXECUTABLE_NOT_ABSOLUTE"):
        RuntimeLifecycle().start(definition)


def test_comfy_configuration_uses_canonical_installation_path(tmp_path: Path):
    client, _center = protected_client(tmp_path, "/api/model-center")
    headers = {"X-Session-Token": "trusted"}
    install = tmp_path / "comfy"
    install.mkdir()
    body = {
        "runtime_type": "COMFYUI",
        "management": "EXTERNAL",
        "executable": "",
        "installation_path": str(install),
        "base_url": "http://127.0.0.1:8188",
        "bind_address": "127.0.0.1",
        "port": 8188,
        "health_endpoint": "/system_stats",
    }
    saved = client.put("/api/model-center/runtimes/comfyui-local/configuration", headers=headers, json=body)
    assert saved.status_code == 200
    payload = saved.json()
    assert payload["installation_path"] == str(install)
    assert "working_directory" not in payload
    assert "launch_arguments" not in payload
    roundtrip = client.put("/api/model-center/runtimes/comfyui-local/configuration", headers=headers, json=payload)
    assert roundtrip.status_code == 200
    conflict = {**body, "working_directory": str(tmp_path / "other")}
    rejected = client.put("/api/model-center/runtimes/comfyui-local/configuration", headers=headers, json=conflict)
    assert rejected.status_code == 409
    assert rejected.json()["detail"]["code"] == "RUNTIME_PATH_CONFLICT"
    reread = client.get("/api/model-center/runtimes/comfyui-local/configuration", headers=headers)
    assert reread.json()["installation_path"] == str(install)

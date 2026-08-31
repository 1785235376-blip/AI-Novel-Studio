from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import socket
import subprocess
import tempfile
import threading
import time
import urllib.request
from urllib.parse import urlsplit
from collections import deque
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .domain import Capability, HardwareProfile, ModelComponentDefinition, ModelDefinition, ModelStatus, ModelValidationRecord, PipelineDefinition, RoutingDecision, RoutingPolicy, RuntimeCapabilitySnapshot, RuntimeDefinition, RuntimeInstance, RuntimeManagement, RuntimeState, RuntimeType, serialize
from .runtime_profiles import (
    RuntimeLogSanitizer,
    argv_contains_wildcard_bind,
    canonicalize_managed_executable,
    definition_from_profile,
    managed_executable_file,
    profile_from_values,
    resynthesize_runtime_argv,
    synthesized_launch_arguments,
)
from ..stable_identity import IdentityMutationError, StableIdentityStore, canonical_model_identity_key, get_host_identity_store, validate_uuid


class CompatibilityGraph:
    def __init__(self, components: list[ModelComponentDefinition]): self.components = {item.component_id: item for item in components}
    def compatible(self, model: ModelDefinition, component_id: str) -> bool:
        item = self.components.get(component_id)
        if item is None or model.id not in item.compatible_models: return False
        requirement = model.compatibility.get("components", {}).get(item.component_type, {})
        dimensions = ("family", "variant", "architecture", "version")
        return all(requirement.get(key) and requirement[key] == getattr(item, key) for key in dimensions)


class RuntimeProbeRedirectRejected(RuntimeError):
    pass


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeProbeRedirectRejected("MODEL_CENTER_RUNTIME_REDIRECT_REJECTED")


SAFE_RUNTIME_ENV_ALLOWLIST = frozenset({"PATH", "PATHEXT", "TEMP", "TMP", "SYSTEMROOT", "WINDIR"})
SECRET_ENV_MARKERS = ("AUTH", "COOKIE", "CREDENTIAL", "DATABASE_URL", "KEY", "PASSWORD", "PRIVATE", "SECRET", "SESSION", "TOKEN")


def _safe_runtime_environment(explicit: dict[str, str]) -> dict[str, str]:
    rejected = [key for key in explicit if any(marker in key.upper() for marker in SECRET_ENV_MARKERS)]
    if rejected:
        raise ValueError("RUNTIME_ENVIRONMENT_SECRET_REJECTED")
    inherited = {
        key: value for key, value in os.environ.items()
        if key.upper() in SAFE_RUNTIME_ENV_ALLOWLIST
    }
    inherited.update(explicit)
    return inherited


def _runtime_probe_opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), _RejectRedirects())


class RuntimeLifecycle:
    def __init__(self, log_line_limit: int = 200, log_byte_limit: int = 64 * 1024):
        self.instances: dict[str, RuntimeInstance] = {}
        self._owned: dict[str, subprocess.Popen[bytes]] = {}
        self._logs: dict[str, dict[str, deque[str]]] = {}
        self._log_line_limit = log_line_limit
        self._log_byte_limit = log_byte_limit
        self._lock = threading.Lock()
        self._probe_open = _runtime_probe_opener().open

    def _drain(self, runtime_id: str, stream_name: str, stream: Any) -> None:
        logs = self._logs[runtime_id][stream_name]
        try:
            for raw_line in iter(stream.readline, b""):
                logs.append(raw_line.decode("utf-8", errors="replace").rstrip()[:4096])
        finally:
            stream.close()

    def _start_log_readers(self, runtime_id: str, process: subprocess.Popen[bytes]) -> None:
        self._logs[runtime_id] = {
            "stdout": deque(maxlen=self._log_line_limit),
            "stderr": deque(maxlen=self._log_line_limit),
        }
        for stream_name, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
            if stream is not None:
                threading.Thread(
                    target=self._drain,
                    args=(runtime_id, stream_name, stream),
                    daemon=True,
                    name=f"model-center-{runtime_id}-{stream_name}",
                ).start()

    def logs(self, runtime_id: str) -> dict[str, list[str]]:
        stored = self._logs.get(runtime_id) or {}
        result: dict[str, list[str]] = {"stdout": [], "stderr": []}
        for name in ("stdout", "stderr"):
            lines = stored.get(name) or ()
            selected: list[str] = []
            used = 0
            for line in reversed(lines):
                size = len(line.encode("utf-8", errors="replace"))
                if used + size > self._log_byte_limit:
                    break
                selected.append(line); used += size
            result[name] = list(reversed(selected))
        return result

    def sanitized_logs(self, runtime_id: str) -> dict[str, list[str]]:
        return {
            name: [RuntimeLogSanitizer.sanitize(line) for line in lines]
            for name, lines in self.logs(runtime_id).items()
        }

    def refresh(self, runtime_id: str) -> RuntimeInstance | None:
        instance = self.instances.get(runtime_id)
        process = self._owned.get(runtime_id)
        if instance is None or process is None:
            return instance
        return_code = process.poll()
        if return_code is not None and instance.state != RuntimeState.STOPPED:
            instance.state = RuntimeState.FAILED
            instance.error = f"RUNTIME_EXITED:{return_code}"
            instance.health = {
                "reachable": False,
                "exit_code": return_code,
            }
            instance.process_alive = False; instance.http_reachable = False
            instance.last_failure = datetime.now(timezone.utc).isoformat(); instance.safe_error_code = "PROCESS_EXITED"
        return instance
    @staticmethod
    def _is_loopback_host(host: str) -> bool:
        if not host:
            return False
        if host.casefold() == "localhost":
            try:
                addresses = {
                    item[4][0]
                    for item in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
                }
                return bool(addresses) and all(ipaddress.ip_address(value).is_loopback for value in addresses)
            except (OSError, ValueError):
                return False
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False

    @classmethod
    def is_local(cls, definition: RuntimeDefinition) -> bool:
        if not cls._is_loopback_host(definition.bind_address):
            return False
        if not definition.base_url:
            return True
        try:
            parsed = urlsplit(definition.base_url)
            return (
                parsed.scheme in {"http", "https"}
                and parsed.username is None
                and parsed.password is None
                and cls._is_loopback_host(parsed.hostname or "")
                and parsed.port is not None
            )
        except ValueError:
            return False
    def discover(self, definition: RuntimeDefinition, probe_version: bool = False) -> dict[str, Any]:
        executable: Path | None = None
        if definition.executable:
            try:
                executable = Path(canonicalize_managed_executable(definition.executable))
            except ValueError:
                executable = None
        path_ok = bool(executable and executable.is_file()) if definition.runtime_type == RuntimeType.LLAMA_CPP else bool(definition.working_directory and Path(definition.working_directory).is_dir())
        version = None
        if probe_version and executable and executable.is_file():
            try:
                result = subprocess.run(
                    [str(executable), "--version"],
                    cwd=definition.working_directory or executable.parent,
                    env=_safe_runtime_environment(definition.environment),
                    capture_output=True,
                    check=False,
                    timeout=5,
                )
                version = (result.stdout or result.stderr).decode("utf-8", errors="replace").strip()[:500] or None
            except (OSError, subprocess.TimeoutExpired):
                version = None
        instance = self.refresh(definition.id)
        return {
            "runtime_id": definition.id,
            "runtime_type": definition.runtime_type,
            "path_exists": path_ok,
            "executable_exists": bool(executable and executable.is_file()),
            "version": version,
            "health": instance.health if instance else {"reachable": False},
            "gpu_capability": (instance.health.get("gpu") if instance else None) or "UNKNOWN",
            "security_warning": None if self.is_local(definition) else "RUNTIME_NOT_LOOPBACK_BOUND",
        }
    def health(self, definition: RuntimeDefinition) -> RuntimeInstance:
        self.refresh(definition.id)
        instance = self.instances.setdefault(definition.id, RuntimeInstance(definition.id, base_url=definition.base_url, management=definition.management))
        instance.management = definition.management
        owned_process = self._owned.get(definition.id)
        if owned_process is not None and owned_process.poll() is not None:
            instance.last_health_check = datetime.now(timezone.utc).isoformat()
            return instance
        url = definition.base_url.rstrip("/") + (definition.health_endpoint or "/") if definition.base_url else ""
        started = time.perf_counter()
        try:
            if not self.is_local(definition): raise RuntimeError("RUNTIME_NOT_LOOPBACK_BOUND")
            with self._probe_open(url, timeout=1.5) as response: ok = 200 <= response.status < 500
            instance.state = RuntimeState.EXTERNAL if ok and definition.management == RuntimeManagement.EXTERNAL else (RuntimeState.RUNNING if ok else RuntimeState.DEGRADED); instance.health = {"reachable": ok, "url": url}
            instance.http_reachable = ok; instance.process_alive = bool(owned_process and owned_process.poll() is None)
            instance.latency_ms = round((time.perf_counter() - started) * 1000, 2)
            instance.safe_error_code = None if ok else "HTTP_UNREACHABLE"
            if ok: instance.last_success = datetime.now(timezone.utc).isoformat(); instance.error = None
        except RuntimeProbeRedirectRejected:
            instance.state = RuntimeState.FAILED if definition.id in self._owned else RuntimeState.STOPPED; instance.health = {"reachable": False}; instance.error = "MODEL_CENTER_RUNTIME_REDIRECT_REJECTED"; instance.safe_error_code = instance.error
        except Exception:
            instance.state = RuntimeState.FAILED if definition.id in self._owned else RuntimeState.STOPPED; instance.health = {"reachable": False}; instance.error = "RUNTIME_HEALTH_FAILED"; instance.safe_error_code = "HTTP_UNREACHABLE"
        if not instance.http_reachable: instance.last_failure = datetime.now(timezone.utc).isoformat()
        instance.last_health_check = datetime.now(timezone.utc).isoformat(); return instance
    def start(self, definition: RuntimeDefinition, *, host_argv: tuple[str, ...] | None = None) -> RuntimeInstance:
        if not self.is_local(definition): raise ValueError("RUNTIME_NOT_LOOPBACK_BOUND")
        if definition.runtime_type != RuntimeType.LLAMA_CPP or definition.management != RuntimeManagement.MANAGED: raise ValueError("RUNTIME_EXTERNAL_ONLY")
        _safe_runtime_environment(definition.environment)
        executable = managed_executable_file(definition.executable)
        with self._lock:
            current = self._owned.get(definition.id)
            if current and current.poll() is None: return self.instances[definition.id]
            if definition.port is None: raise ValueError("RUNTIME_PORT_REQUIRED")
            probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                probe.bind((definition.bind_address, definition.port))
            except OSError as exc:
                raise ValueError("PORT_IN_USE") from exc
            finally:
                probe.close()
            argv = host_argv if host_argv is not None else synthesized_launch_arguments(definition)
            if argv_contains_wildcard_bind(argv):
                raise ValueError("RUNTIME_NOT_LOOPBACK_BOUND")
            args = [str(executable), *argv]
            try:
                proc = subprocess.Popen(
                    args,
                    cwd=definition.working_directory or executable.parent,
                    env=_safe_runtime_environment(definition.environment),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except (OSError, ValueError) as exc:
                if isinstance(exc, ValueError) and str(exc) == "RUNTIME_ENVIRONMENT_SECRET_REJECTED":
                    raise
                raise ValueError("RUNTIME_START_FAILED") from exc
            self._owned[definition.id] = proc
            instance = RuntimeInstance(definition.id, proc.pid, RuntimeState.STARTING, definition.base_url, datetime.now(timezone.utc).isoformat(), management=definition.management, process_alive=True)
            self.instances[definition.id] = instance
            self._start_log_readers(definition.id, proc)
            return instance
    def stop(self, runtime_id: str) -> RuntimeInstance:
        with self._lock:
            proc = self._owned.get(runtime_id)
            if proc is None: raise ValueError("RUNTIME_NOT_OWNED")
            if proc.poll() is None:
                proc.terminate()
                try: proc.wait(timeout=5)
                except subprocess.TimeoutExpired: proc.kill(); proc.wait(timeout=2)
            self._owned.pop(runtime_id, None)
            instance = self.instances.setdefault(runtime_id, RuntimeInstance(runtime_id)); instance.process_id = None; instance.state = RuntimeState.STOPPED
            instance.health = {"reachable": False}; instance.process_alive = False; instance.http_reachable = False
            return instance

    def stop_all(self) -> None:
        for runtime_id in tuple(self._owned):
            try:
                self.stop(runtime_id)
            except ValueError:
                continue


class ModelCenterService:
    RUNTIME_CONFIG_SCHEMA_VERSION = 1
    PERSISTED_RUNTIME_FIELDS = {
        "executable",
        "base_url",
        "bind_address",
        "port",
        "working_directory",
        "health_endpoint",
        "management", "model_path", "context_size", "gpu_layers", "threads", "batch_size", "extra_arguments",
    }

    def __init__(self, models: list[ModelDefinition], components: list[ModelComponentDefinition], profiles: list[HardwareProfile], runtimes: list[RuntimeDefinition], pipelines: list[PipelineDefinition], validations: list[ModelValidationRecord], routing_policy: RoutingPolicy, config_path: Path | None = None, identity_store: StableIdentityStore | None = None):
        if identity_store is not None:
            def owned(kind: str, key: str, supplied: Any) -> Any:
                previous = identity_store.get(kind, key)
                parsed = validate_uuid(supplied, field=f"{kind}_id") if supplied is not None else None
                canonical = identity_store.get_or_create(kind, key)
                if parsed is not None and previous is not None and parsed != previous:
                    raise IdentityMutationError(f"{kind}_ID_IMMUTABLE")
                return canonical
            domain_by_type = {
                RuntimeType.LLAMA_CPP: "ollama",
                RuntimeType.COMFYUI: "comfyui",
            }
            models = [replace(item, identity_id=owned("model", canonical_model_identity_key(domain_by_type.get(item.runtime_type, "model-center"), item.id), item.identity_id)) for item in models]
            runtimes = [replace(item, identity_id=owned("runtime", item.id, item.identity_id)) for item in runtimes]
        self.models={x.id:x for x in models}; self.components={x.component_id:x for x in components}; self.profiles={x.id:x for x in profiles}; self.runtimes={x.id:x for x in runtimes}; self.pipelines={x.id:x for x in pipelines}; self.validations=validations; self.compatibility=CompatibilityGraph(components); self.lifecycle=RuntimeLifecycle()
        self.routing_policy = routing_policy
        self.config_path=config_path
        self.runtime_versions: dict[str, str] = {}
        self.current_hardware_profiles: dict[str, str] = {}
        self._config_lock = threading.RLock()
        if config_path and config_path.is_file():
            try:
                saved=json.loads(config_path.read_text(encoding="utf-8"))
                if not isinstance(saved, dict) or not isinstance(saved.get("runtimes", {}), dict):
                    raise ValueError("invalid runtime configuration")
                if saved.get("schema_version", self.RUNTIME_CONFIG_SCHEMA_VERSION) != self.RUNTIME_CONFIG_SCHEMA_VERSION:
                    raise ValueError("unsupported runtime configuration schema")
                candidates = dict(self.runtimes)
                for runtime_id, values in saved.get("runtimes", {}).items():
                    if runtime_id in candidates:
                        values = self._validated_persisted_values(values)
                        configured = replace(candidates[runtime_id], **values)
                        configured = resynthesize_runtime_argv(configured)
                        if not self.lifecycle.is_local(configured):
                            raise ValueError("unsafe runtime configuration")
                        candidates[runtime_id] = configured
                self.runtimes = candidates
            except (OSError, ValueError, TypeError, json.JSONDecodeError): pass

    def _validated_persisted_values(self, values: Any) -> dict[str, Any]:
        if not isinstance(values, dict):
            raise ValueError("invalid runtime configuration")
        filtered = {key: value for key, value in values.items() if key in self.PERSISTED_RUNTIME_FIELDS}
        for key in ("executable", "base_url", "bind_address", "working_directory", "health_endpoint", "model_path"):
            if key in filtered and not isinstance(filtered[key], str):
                raise ValueError("invalid runtime configuration")
        if filtered.get("executable"):
            try:
                filtered["executable"] = canonicalize_managed_executable(filtered["executable"])
            except ValueError as exc:
                raise ValueError("invalid runtime configuration") from exc
        if "port" in filtered and (not isinstance(filtered["port"], int) or not 1 <= filtered["port"] <= 65535):
            raise ValueError("invalid runtime configuration")
        filtered.pop("launch_arguments", None)
        if "extra_arguments" in filtered:
            arguments = filtered["extra_arguments"]
            if not isinstance(arguments, list) or not all(isinstance(item, str) for item in arguments):
                raise ValueError("invalid runtime configuration")
            filtered["extra_arguments"] = tuple(arguments)
        if "management" in filtered:
            filtered["management"] = RuntimeManagement(filtered["management"])
        return filtered
    def model(self, model_id: str) -> dict[str, Any]:
        model=self.models[model_id]; value=serialize(model)
        eligible = [x for x in self.validations if x.model_id==model_id and x.validation_type in {"INFERENCE","PIPELINE"} and x.status=="PASS"]
        value["historically_validated"] = bool(eligible)
        value["verified"] = any(self._validation_is_current(model, record) for record in eligible)
        value["hardware_profile_details"]=[serialize(self.profiles[x]) for x in model.hardware_profiles if x in self.profiles]
        return value

    def set_runtime_version(self, runtime_id: str, version: str | None) -> None:
        if version:
            self.runtime_versions[runtime_id] = version

    def set_current_hardware_profile(self, model_id: str, profile_id: str) -> None:
        if profile_id not in self.models[model_id].hardware_profiles:
            raise ValueError("MODEL_CENTER_HARDWARE_PROFILE_MISMATCH")
        self.current_hardware_profiles[model_id] = profile_id

    def runtime_fingerprint(self, runtime_id: str, version: str | None = None) -> str | None:
        runtime = self.runtimes[runtime_id]
        runtime_version = version or self.runtime_versions.get(runtime_id)
        if not runtime_version:
            return None
        executable = str(Path(runtime.executable).resolve()) if runtime.executable else ""
        if runtime.runtime_type == RuntimeType.LLAMA_CPP and not executable:
            return None
        identity = {
            "runtime_id": runtime.id,
            "runtime_type": runtime.runtime_type,
            "executable": executable,
            "working_directory": str(Path(runtime.working_directory).resolve()) if runtime.working_directory else "",
            "base_url": runtime.base_url,
            "bind_address": runtime.bind_address,
            "port": runtime.port,
            "launch_arguments": runtime.launch_arguments,
            "version": runtime_version,
        }
        payload = json.dumps(identity, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _validation_is_current(self, model: ModelDefinition, record: ModelValidationRecord) -> bool:
        model_hash = str(model.metadata.get("sha256") or "")
        runtime_version = self.runtime_versions.get(record.runtime_id, "")
        fingerprint = self.runtime_fingerprint(record.runtime_id, runtime_version) if record.runtime_id in self.runtimes else None
        return bool(
            model_hash
            and record.hash == model_hash
            and self.current_hardware_profiles.get(model.id) == record.hardware_profile_id
            and runtime_version
            and record.runtime_version == runtime_version
            and fingerprint
            and record.runtime_fingerprint == fingerprint
        )
    def health(self) -> dict[str, Any]:
        return {"status":"READY","models":len(self.models),"ready_models":sum(x.status==ModelStatus.READY for x in self.models.values()),"runtimes":len(self.runtimes),"runtime_instances":[serialize(x) for x in self.lifecycle.instances.values()]}
    def route(self, capability: str) -> RoutingDecision:
        route = self.routing_policy.routes.get(capability)
        if route is None:
            raise ValueError("MODEL_CENTER_ROUTE_NOT_FOUND")
        model = self.models.get(route["model_id"])
        runtime = self.runtimes.get(route["runtime_id"])
        if model is None or model.status != ModelStatus.READY:
            raise ValueError("MODEL_CENTER_MODEL_NOT_READY")
        if runtime is None:
            raise ValueError("MODEL_CENTER_RUNTIME_NOT_FOUND")
        return RoutingDecision(
            capability=capability,
            model_id=model.id,
            runtime_id=runtime.id,
            provider_adapter=runtime.provider_adapter,
        )
    def configure_runtime(self, runtime_id: str, values: dict[str, Any]) -> RuntimeDefinition:
        with self._config_lock:
            if any(key in values for key in ("identity_id", "runtime_uuid", "runtime_id")):
                raise ValueError("RUNTIME_ID_IMMUTABLE")
            if "launch_arguments" in values:
                raise ValueError("RUNTIME_ARGV_NOT_ALLOWED")
            if "environment" in values:
                _safe_runtime_environment(values["environment"])
            configured = replace(self.runtimes[runtime_id], **values)
            configured = resynthesize_runtime_argv(configured)
            if not self.lifecycle.is_local(configured):
                raise ValueError("RUNTIME_NOT_LOOPBACK_BOUND")
            candidates = {**self.runtimes, runtime_id: configured}
            if self.config_path:
                self._persist_runtimes(candidates)
            self.runtimes = candidates
            self.runtime_versions.pop(runtime_id, None)
            return configured

    def configure_runtime_profile(self, runtime_id: str, values: dict[str, Any]) -> RuntimeDefinition:
        with self._config_lock:
            if any(key in values for key in ("identity_id", "runtime_uuid", "runtime_id")):
                raise ValueError("RUNTIME_ID_IMMUTABLE")
            runtime = self.runtimes[runtime_id]
            configured = definition_from_profile(runtime, profile_from_values(runtime, values))
            if not self.lifecycle.is_local(configured):
                raise ValueError("RUNTIME_NOT_LOOPBACK_BOUND")
            candidates = {**self.runtimes, runtime_id: configured}
            if self.config_path:
                self._persist_runtimes(candidates)
            self.runtimes = candidates
            self.runtime_versions.pop(runtime_id, None)
            return configured

    def validate_runtime(self, runtime_id: str) -> dict[str, Any]:
        runtime = self.runtimes[runtime_id]
        checks: list[dict[str, Any]] = []
        def check(name: str, passed: bool, code: str):
            checks.append({"name": name, "status": "PASS" if passed else "FAIL", "code": None if passed else code})
        check("loopback", self.lifecycle.is_local(runtime), "RUNTIME_NOT_LOOPBACK_BOUND")
        check("port", runtime.port is not None and 1 <= runtime.port <= 65535, "RUNTIME_PORT_INVALID")
        discovery = self.lifecycle.discover(runtime, probe_version=True)
        if runtime.runtime_type == RuntimeType.LLAMA_CPP:
            check("executable", discovery["executable_exists"], "EXECUTABLE_NOT_FOUND")
            check("version", bool(discovery["version"]), "VERSION_UNSUPPORTED")
            model_exists = bool(runtime.model_path and Path(runtime.model_path).is_file())
            check("model", model_exists, "MODEL_FILE_NOT_FOUND")
            gguf_valid = False
            if model_exists:
                try:
                    with Path(runtime.model_path).open("rb") as model_file:
                        gguf_valid = model_file.read(4) == b"GGUF"
                except OSError:
                    gguf_valid = False
            check("gguf", gguf_valid, "MODEL_FILE_INVALID")
            if (runtime.gpu_layers or 0) > 0:
                executable_parent = Path(runtime.executable).parent if runtime.executable else Path()
                cuda_detected = "cuda" in str(discovery.get("version") or "").casefold() or any(executable_parent.glob("ggml-cuda*.dll"))
                check("cuda", cuda_detected, "CUDA_BACKEND_UNAVAILABLE")
        else:
            check("installation", not runtime.working_directory or Path(runtime.working_directory).is_dir(), "RUNTIME_NOT_FOUND")
            instance = self.lifecycle.health(runtime)
            check("http", instance.http_reachable, "HTTP_UNREACHABLE")
        failed = next((item["code"] for item in checks if item["status"] == "FAIL"), None)
        state = "READY" if failed is None else ("MODEL_MISSING" if failed == "MODEL_FILE_NOT_FOUND" else "DEGRADED")
        if discovery.get("version"): self.set_runtime_version(runtime_id, discovery["version"])
        return {"runtime_id": runtime_id, "status": state, "safe_error_code": failed, "checks": checks, "version": discovery.get("version")}

    def capability_snapshot(self, runtime_id: str) -> RuntimeCapabilitySnapshot:
        runtime = self.runtimes[runtime_id]
        instance = self.lifecycle.health(runtime)
        capabilities = tuple(str(item) for item in runtime.capabilities) if instance.http_reachable else ()
        nodes: tuple[str, ...] = ()
        warnings: list[str] = []
        available_models = (Path(runtime.model_path).name,) if runtime.model_path and Path(runtime.model_path).is_file() else ()
        if runtime.runtime_type == RuntimeType.COMFYUI and instance.http_reachable:
            url = runtime.base_url.rstrip("/") + "/object_info"
            try:
                with self.lifecycle._probe_open(url, timeout=2) as response:
                    payload = json.loads(response.read(2 * 1024 * 1024).decode("utf-8"))
                if isinstance(payload, dict): nodes = tuple(sorted(str(key) for key in payload))
            except Exception:
                warnings.append("CAPABILITY_DETECTION_UNAVAILABLE")
        return RuntimeCapabilitySnapshot(
            runtime_id, self.runtime_versions.get(runtime_id), datetime.now(timezone.utc).isoformat(), instance.state,
            capabilities, available_models, (runtime.provider_adapter,) if runtime.provider_adapter else (), nodes, tuple(warnings),
        )

    def diagnostics(self, runtime_id: str) -> dict[str, Any]:
        runtime = self.runtimes[runtime_id]; instance = self.lifecycle.health(runtime)
        validation = self.validate_runtime(runtime_id)
        return {"runtime_id": runtime_id, "management": runtime.management, "state": instance.state, "process_alive": instance.process_alive, "http_reachable": instance.http_reachable, "version": validation["version"], "latency_ms": instance.latency_ms, "last_success": instance.last_success, "last_failure": instance.last_failure, "safe_error_code": instance.safe_error_code or validation["safe_error_code"], "checks": validation["checks"]}

    def _persist_runtimes(self, runtimes: dict[str, RuntimeDefinition]) -> None:
        assert self.config_path is not None
        payload={"schema_version":self.RUNTIME_CONFIG_SCHEMA_VERSION,"runtimes":{key:{name:value for name,value in serialize(item).items() if name in self.PERSISTED_RUNTIME_FIELDS} for key,item in runtimes.items()}}
        temporary_path: Path | None = None
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.config_path.parent, prefix=f".{self.config_path.name}.", suffix=".tmp", delete=False) as temporary:
                temporary_path = Path(temporary.name)
                json.dump(payload, temporary, ensure_ascii=False, indent=2)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, self.config_path)
            temporary_path = None
            try:
                directory_fd = os.open(self.config_path.parent, os.O_RDONLY)
                try: os.fsync(directory_fd)
                finally: os.close(directory_fd)
            except OSError:
                pass
        except OSError as exc:
            raise ValueError("RUNTIME_CONFIG_WRITE_FAILED") from exc
        finally:
            if temporary_path is not None:
                try: temporary_path.unlink()
                except OSError: pass


def create_default_model_center(config_path: Path | None = None, identity_store: StableIdentityStore | None = None) -> ModelCenterService:
    verified="2026-08-29T00:00:00+00:00"
    components=[
        ModelComponentDefinition("flux2-klein-qwen3-encoder","TEXT_ENCODER","FLUX2","KLEIN","QWEN3","1","SAFETENSORS","BF16",compatible_models=("flux2-klein-4b-fp8",)),
        ModelComponentDefinition("flux2-dev-mistral-encoder","TEXT_ENCODER","FLUX2","DEV","MISTRAL","1","SAFETENSORS","BF16",compatible_models=("flux2-dev",)),
        ModelComponentDefinition("rife-49-checkpoint","CHECKPOINT","RIFE","4.9","RIFE49","4.9","PYTORCH","FP32",compatible_models=("rife-49",)),
    ]
    profiles=[
        HardwareProfile("qwen36-rtx5080-8k","qwen36-27b-q4km","RTX 5080",context=8192,offload_mode="GPU_CPU_MIXED",tested=True,verified_at=verified,benchmark={"tokens_per_second":10.03},profile_kind="DEFAULT"),
        HardwareProfile("qwen36-rtx5080-16k","qwen36-27b-q4km","RTX 5080",context=16384,offload_mode="GPU_CPU_MIXED",tested=True,verified_at=verified,benchmark={"tokens_per_second":9.25},profile_kind="VERIFIED_MAX"),
        HardwareProfile("flux2-klein-rtx5080","flux2-klein-4b-fp8","RTX 5080",resolution="512x512",tested=True,verified_at=verified,benchmark={"seconds":10.2}),
        HardwareProfile("zimage-rtx5080","z-image-turbo-bf16","RTX 5080",resolution="1024x1024",tested=True,verified_at=verified,benchmark={"seconds":25.28}),
        HardwareProfile("wan22-smoke-rtx5080","wan22-ti2v-5b","RTX 5080",resolution="256x256",frames=9,fps=8,tested=True,verified_at=verified,benchmark={"seconds":29.78},profile_kind="SMOKE"),
        HardwareProfile("rife49-rtx5080","rife-49","RTX 5080",tested=True,verified_at=verified,benchmark={"interpolation":"2X","seconds":0.408}),
    ]
    models=[
        ModelDefinition("qwen36-27b-q4km","Qwen3.6 27B Q4_K_M","QWEN3.6","27B","1",(Capability.TEXT,),RuntimeType.LLAMA_CPP,"GGUF","Q4_K_M","Q4",hardware_profiles=("qwen36-rtx5080-8k","qwen36-rtx5080-16k"),status=ModelStatus.READY,metadata={"role":"LOCAL_TEXT_DEFAULT","sha256":"65B753EA835627F7B511143C6CEB976525C7F21F5DF8C664BC0A9C23D1C49921"}),
        ModelDefinition("flux2-klein-4b-fp8","FLUX.2 Klein 4B FP8","FLUX2","KLEIN","1",(Capability.IMAGE,),RuntimeType.COMFYUI,"SAFETENSORS",precision="FP8",components=("flux2-klein-qwen3-encoder",),hardware_profiles=("flux2-klein-rtx5080",),compatibility={"components":{"TEXT_ENCODER":{"family":"FLUX2","variant":"KLEIN","architecture":"QWEN3","version":"1"}}},status=ModelStatus.READY),
        ModelDefinition("flux2-dev","FLUX.2 Dev","FLUX2","DEV","1",(Capability.IMAGE,),RuntimeType.COMFYUI,"SAFETENSORS",components=("flux2-dev-mistral-encoder",),compatibility={"components":{"TEXT_ENCODER":{"family":"FLUX2","variant":"DEV","architecture":"MISTRAL","version":"1"}}},status=ModelStatus.NOT_INSTALLED),
        ModelDefinition("z-image-turbo-bf16","Z-Image Turbo BF16","ZIMAGE","TURBO","1",(Capability.IMAGE,),RuntimeType.COMFYUI,"SAFETENSORS",precision="BF16",hardware_profiles=("zimage-rtx5080",),status=ModelStatus.READY),
        ModelDefinition("wan22-ti2v-5b","Wan2.2 TI2V 5B","WAN2.2","TI2V-5B","1",(Capability.VIDEO,),RuntimeType.COMFYUI,"SAFETENSORS",precision="FP16",hardware_profiles=("wan22-smoke-rtx5080",),status=ModelStatus.READY,metadata={"role":"LOCAL_VIDEO_DRAFT"}),
        ModelDefinition("seedvr2-3b","SeedVR2 3B","SEEDVR2","3B","1",(Capability.RESTORATION,),RuntimeType.COMFYUI,"CHECKPOINT",status=ModelStatus.READY),
        ModelDefinition("seedvr2-7b-sharp","SeedVR2 7B Sharp","SEEDVR2","7B_SHARP","1",(Capability.RESTORATION,),RuntimeType.COMFYUI,"CHECKPOINT",status=ModelStatus.READY),
        ModelDefinition("rife-49","RIFE 4.9","RIFE","4.9","4.9",(Capability.INTERPOLATION,),RuntimeType.COMFYUI,"CHECKPOINT",components=("rife-49-checkpoint",),hardware_profiles=("rife49-rtx5080",),compatibility={"components":{"CHECKPOINT":{"family":"RIFE","variant":"4.9","architecture":"RIFE49","version":"4.9"}}},status=ModelStatus.READY),
        ModelDefinition("rife-426","RIFE 4.26","RIFE","4.26","4.26",(Capability.INTERPOLATION,),RuntimeType.COMFYUI,"CHECKPOINT",status=ModelStatus.INCOMPATIBLE,metadata={"reason":"CHECKPOINT_ARCHITECTURE_MISMATCH"}),
        ModelDefinition("dasheng-audiogen","Dasheng AudioGen","DASHENG","DEFAULT","1",(Capability.AUDIO,),RuntimeType.CUSTOM_HTTP,"CHECKPOINT",status=ModelStatus.RUNTIME_REQUIRED),
        ModelDefinition("minimax-h3","MiniMax H3","MINIMAX","H3","1",(Capability.TTS,Capability.AUDIO),RuntimeType.CUSTOM_HTTP,"CHECKPOINT",status=ModelStatus.RUNTIME_REQUIRED,metadata={"license_status":"VALIDATION_REQUIRED"}),
        ModelDefinition("ltx25","LTX 2.5","LTX","2.5","2.5",(Capability.VIDEO,),RuntimeType.COMFYUI,"CHECKPOINT",status=ModelStatus.LICENSE_REQUIRED),
        ModelDefinition("qwen-image-2512","Qwen Image 2512","QWEN_IMAGE","2512","1",(Capability.IMAGE,),RuntimeType.COMFYUI,"CHECKPOINT",status=ModelStatus.NOT_INSTALLED,metadata={"deferred":True}),
    ]
    runtimes=[RuntimeDefinition("llama-cpp-local",RuntimeType.LLAMA_CPP,base_url="http://127.0.0.1:8081",bind_address="127.0.0.1",port=8081,health_endpoint="/v1/models",capabilities=(Capability.TEXT,),provider_adapter="OPENAI_COMPATIBLE_TEXT",management=RuntimeManagement.MANAGED,context_size=8192,gpu_layers=0),RuntimeDefinition("comfyui-local",RuntimeType.COMFYUI,base_url="http://127.0.0.1:8188",bind_address="127.0.0.1",port=8188,health_endpoint="/system_stats",capabilities=(Capability.IMAGE,Capability.VIDEO,Capability.RESTORATION,Capability.INTERPOLATION),provider_adapter="COMFYUI_ASSET",management=RuntimeManagement.EXTERNAL)]
    pipelines=[PipelineDefinition("LOCAL_VIDEO_PIPELINE_V1",({"id":"generate","capability":"VIDEO","model_id":"wan22-ti2v-5b"},{"id":"restore","capability":"RESTORATION","model_id":"seedvr2-3b"},{"id":"interpolate","capability":"INTERPOLATION","model_id":"rife-49"}),({"from":"generate","to":"restore"},{"from":"restore","to":"interpolate"}),{"kind":"VIDEO_GENERATION_REQUEST"},{"resolution":"512x512","fps":16},("VIDEO","RESTORATION","INTERPOLATION"),hardware_requirements={"tested_gpu":"RTX 5080"})]
    validations=[ModelValidationRecord(model.id,"comfyui-local" if model.runtime_type==RuntimeType.COMFYUI else "llama-cpp-local",model.hardware_profiles[0] if model.hardware_profiles else "","INFERENCE","PASS",verified,hash=model.metadata.get("sha256", ""),gpu="RTX 5080") for model in models if model.status==ModelStatus.READY]
    routing_policy = RoutingPolicy("LOCAL_DEFAULT_V1", {
        "TEXT": {"model_id": "qwen36-27b-q4km", "runtime_id": "llama-cpp-local"},
        "IMAGE_FAST": {"model_id": "flux2-klein-4b-fp8", "runtime_id": "comfyui-local"},
        "IMAGE_QUALITY": {"model_id": "z-image-turbo-bf16", "runtime_id": "comfyui-local"},
        "VIDEO_DRAFT": {"model_id": "wan22-ti2v-5b", "runtime_id": "comfyui-local"},
        "VIDEO_RESTORATION_STANDARD": {"model_id": "seedvr2-3b", "runtime_id": "comfyui-local"},
        "VIDEO_RESTORATION_FINAL": {"model_id": "seedvr2-7b-sharp", "runtime_id": "comfyui-local"},
        "FRAME_INTERPOLATION": {"model_id": "rife-49", "runtime_id": "comfyui-local"},
    })
    if identity_store is None:
        identity_store = get_host_identity_store()
    return ModelCenterService(models,components,profiles,runtimes,pipelines,validations,routing_policy,config_path,identity_store)

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .domain import RuntimeDefinition, RuntimeManagement, RuntimeType


LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
WILDCARD_BIND_TOKENS = {"0.0.0.0", "::", "*"}
LLAMA_SAFE_EXTRA_FLAGS = frozenset({"--no-mmap", "--mlock", "--flash-attn", "--no-webui", "--verbose"})
PROTECTED_LLAMA_FLAGS = frozenset({
    "-m", "--model", "-c", "--ctx-size", "-ngl", "--gpu-layers", "--host", "--port",
    "-t", "--threads", "-b", "--batch-size",
})
EDITABLE_COMMON_FIELDS = (
    "runtime_type", "management", "executable", "working_directory",
    "base_url", "bind_address", "port", "health_endpoint",
)
EDITABLE_LLAMA_FIELDS = EDITABLE_COMMON_FIELDS + (
    "model_path", "context_size", "gpu_layers", "threads", "batch_size", "extra_arguments",
)
EDITABLE_COMFY_FIELDS = EDITABLE_COMMON_FIELDS + ("installation_path",)
OUTPUT_CONFIGURATION_FIELDS = frozenset({
    "id", "capabilities", "status", "provider_adapter", "environment",
    "instance", "discovery",
})


class RuntimeProfileBase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    executable: str = ""
    working_directory: str = ""
    base_url: str
    bind_address: str = "127.0.0.1"
    port: int = Field(ge=1, le=65535)
    health_endpoint: str = "/health"

    @field_validator("bind_address")
    @classmethod
    def loopback_bind_only(cls, value: str) -> str:
        if value not in LOOPBACK_HOSTS:
            raise ValueError("RUNTIME_NOT_LOOPBACK_BOUND")
        return value

    @field_validator("health_endpoint")
    @classmethod
    def health_path_only(cls, value: str) -> str:
        if not value.startswith("/") or "?" in value or "#" in value:
            raise ValueError("RUNTIME_HEALTH_ENDPOINT_INVALID")
        return value


class LlamaCppRuntimeConfig(RuntimeProfileBase):
    runtime_type: Literal[RuntimeType.LLAMA_CPP] = RuntimeType.LLAMA_CPP
    management: Literal[RuntimeManagement.MANAGED, RuntimeManagement.EXTERNAL] = RuntimeManagement.MANAGED
    model_path: str
    context_size: int = Field(default=8192, ge=512, le=131072)
    gpu_layers: int = Field(default=0, ge=0, le=999)
    threads: int | None = Field(default=None, ge=1, le=512)
    batch_size: int | None = Field(default=None, ge=1, le=4096)
    extra_arguments: list[str] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def safe_arguments(self):
        for argument in self.extra_arguments:
            flag = argument.split("=", 1)[0]
            if flag in PROTECTED_LLAMA_FLAGS:
                raise ValueError("RUNTIME_PROTECTED_ARGUMENT")
            if flag not in LLAMA_SAFE_EXTRA_FLAGS or argument != flag:
                raise ValueError("RUNTIME_ARGUMENT_NOT_ALLOWED")
        return self

    def launch_arguments(self) -> tuple[str, ...]:
        values = [
            "--model", self.model_path,
            "--ctx-size", str(self.context_size),
            "--gpu-layers", str(self.gpu_layers),
            "--host", self.bind_address,
            "--port", str(self.port),
        ]
        if self.threads is not None:
            values.extend(("--threads", str(self.threads)))
        if self.batch_size is not None:
            values.extend(("--batch-size", str(self.batch_size)))
        values.extend(self.extra_arguments)
        return tuple(values)


class ComfyUIRuntimeConfig(RuntimeProfileBase):
    runtime_type: Literal[RuntimeType.COMFYUI] = RuntimeType.COMFYUI
    management: Literal[RuntimeManagement.EXTERNAL] = RuntimeManagement.EXTERNAL
    installation_path: str = ""


RuntimeProfile = LlamaCppRuntimeConfig | ComfyUIRuntimeConfig


def _reject_raw_argv(values: dict) -> None:
    if "launch_arguments" in values:
        raise ValueError("RUNTIME_ARGV_NOT_ALLOWED")


def profile_from_values(runtime: RuntimeDefinition, values: dict) -> RuntimeProfile:
    expected = runtime.runtime_type
    supplied = values.get("runtime_type", expected)
    if supplied != expected:
        raise ValueError("RUNTIME_TYPE_MISMATCH")
    _reject_raw_argv(values)
    try:
        if expected == RuntimeType.LLAMA_CPP:
            return LlamaCppRuntimeConfig.model_validate({"runtime_type": expected, **values})
        if expected == RuntimeType.COMFYUI:
            return ComfyUIRuntimeConfig.model_validate({"runtime_type": expected, **values})
    except ValueError as exc:
        message = str(exc)
        for code in (
            "RUNTIME_NOT_LOOPBACK_BOUND", "RUNTIME_HEALTH_ENDPOINT_INVALID",
            "RUNTIME_PROTECTED_ARGUMENT", "RUNTIME_ARGUMENT_NOT_ALLOWED",
            "RUNTIME_ARGV_NOT_ALLOWED",
        ):
            if code in message:
                raise ValueError(code) from exc
        raise ValueError("RUNTIME_CONFIG_INVALID") from exc
    raise ValueError("RUNTIME_TYPE_UNSUPPORTED")


def definition_from_profile(runtime: RuntimeDefinition, profile: RuntimeProfile) -> RuntimeDefinition:
    common = dict(
        executable=profile.executable,
        working_directory=profile.working_directory,
        base_url=profile.base_url,
        bind_address=profile.bind_address,
        port=profile.port,
        health_endpoint=profile.health_endpoint,
        management=profile.management,
    )
    if isinstance(profile, LlamaCppRuntimeConfig):
        values = {**runtime.__dict__, **common}
        values.update(
            model_path=profile.model_path,
            context_size=profile.context_size,
            gpu_layers=profile.gpu_layers,
            threads=profile.threads,
            batch_size=profile.batch_size,
            extra_arguments=tuple(profile.extra_arguments),
            launch_arguments=profile.launch_arguments(),
        )
        return RuntimeDefinition(**values)
    return RuntimeDefinition(**{
        **runtime.__dict__, **common,
        "working_directory": profile.installation_path or profile.working_directory,
        "launch_arguments": (), "extra_arguments": (),
    })


def editable_configuration(runtime: RuntimeDefinition) -> dict[str, Any]:
    """Fields that may be GET and PUT. Raw argv, status, capabilities, and adapters are omitted."""
    fields = EDITABLE_LLAMA_FIELDS if runtime.runtime_type == RuntimeType.LLAMA_CPP else EDITABLE_COMFY_FIELDS
    payload: dict[str, Any] = {"id": runtime.id}
    for name in fields:
        if name == "installation_path":
            payload[name] = runtime.working_directory
        elif name == "extra_arguments":
            payload[name] = list(runtime.extra_arguments)
        else:
            payload[name] = getattr(runtime, name)
    return payload


def mutation_payload(values: dict[str, Any]) -> dict[str, Any]:
    _reject_raw_argv(values)
    return {key: value for key, value in values.items() if key not in OUTPUT_CONFIGURATION_FIELDS}


def profile_from_definition(runtime: RuntimeDefinition) -> RuntimeProfile:
    if runtime.port is None:
        raise ValueError("RUNTIME_PORT_REQUIRED")
    values: dict[str, Any] = {
        "executable": runtime.executable,
        "working_directory": runtime.working_directory,
        "base_url": runtime.base_url or f"http://127.0.0.1:{runtime.port}",
        "bind_address": runtime.bind_address,
        "port": runtime.port,
        "health_endpoint": runtime.health_endpoint or "/health",
        "management": runtime.management,
    }
    if runtime.runtime_type == RuntimeType.LLAMA_CPP:
        values.update(
            model_path=runtime.model_path,
            context_size=runtime.context_size if runtime.context_size is not None else 8192,
            gpu_layers=runtime.gpu_layers if runtime.gpu_layers is not None else 0,
            threads=runtime.threads,
            batch_size=runtime.batch_size,
            extra_arguments=list(runtime.extra_arguments),
        )
    else:
        values["installation_path"] = runtime.working_directory
    return profile_from_values(runtime, values)


def _host_is_non_loopback(host: str) -> bool:
    return host in WILDCARD_BIND_TOKENS or host not in LOOPBACK_HOSTS


def argv_contains_wildcard_bind(argv: tuple[str, ...] | list[str]) -> bool:
    tokens = list(argv)
    for index, token in enumerate(tokens):
        if token in WILDCARD_BIND_TOKENS:
            return True
        if token.startswith("--host="):
            if _host_is_non_loopback(token.split("=", 1)[1]):
                return True
        if token in {"--host", "-h"} and index + 1 < len(tokens) and _host_is_non_loopback(tokens[index + 1]):
            return True
    return False


def protected_argv_matches_profile(argv: tuple[str, ...], profile: LlamaCppRuntimeConfig) -> bool:
    mapping: dict[str, str] = {}
    index = 0
    while index < len(argv):
        flag = argv[index]
        if flag in {"--host", "--port", "--model"}:
            if index + 1 >= len(argv):
                return False
            mapping[flag] = argv[index + 1]
            index += 2
            continue
        index += 1
    return (
        mapping.get("--host") == profile.bind_address
        and mapping.get("--port") == str(profile.port)
        and mapping.get("--model") == profile.model_path
        and mapping.get("--host") in LOOPBACK_HOSTS
    )


def synthesized_launch_arguments(runtime: RuntimeDefinition) -> tuple[str, ...]:
    profile = profile_from_definition(runtime)
    if not isinstance(profile, LlamaCppRuntimeConfig):
        raise ValueError("RUNTIME_EXTERNAL_ONLY")
    argv = profile.launch_arguments()
    if argv_contains_wildcard_bind(argv) or not protected_argv_matches_profile(argv, profile):
        raise ValueError("RUNTIME_NOT_LOOPBACK_BOUND")
    return argv


def resynthesize_runtime_argv(runtime: RuntimeDefinition) -> RuntimeDefinition:
    if runtime.runtime_type != RuntimeType.LLAMA_CPP:
        return runtime.__class__(**{**runtime.__dict__, "launch_arguments": ()})
    profile = profile_from_definition(runtime)
    assert isinstance(profile, LlamaCppRuntimeConfig)
    return definition_from_profile(runtime, profile)


class RuntimeLogSanitizer:
    _assignments = re.compile(
        r"(?i)\b(api[_-]?key|authorization|cookie|credential|password|private[_-]?key|secret|session|token)\b"
        r"(\s*[:=]\s*|\s+)([^\s,;]+)"
    )
    _bearer = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")

    @classmethod
    def sanitize(cls, line: str) -> str:
        value = cls._bearer.sub("Bearer [REDACTED]", line)
        return cls._assignments.sub(lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", value)

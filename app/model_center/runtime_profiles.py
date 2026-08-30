from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .domain import RuntimeDefinition, RuntimeManagement, RuntimeType


LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
LLAMA_SAFE_EXTRA_FLAGS = frozenset({"--no-mmap", "--mlock", "--flash-attn", "--no-webui", "--verbose"})
PROTECTED_LLAMA_FLAGS = frozenset({
    "-m", "--model", "-c", "--ctx-size", "-ngl", "--gpu-layers", "--host", "--port",
    "-t", "--threads", "-b", "--batch-size",
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


def profile_from_values(runtime: RuntimeDefinition, values: dict) -> RuntimeProfile:
    expected = runtime.runtime_type
    supplied = values.get("runtime_type", expected)
    if supplied != expected:
        raise ValueError("RUNTIME_TYPE_MISMATCH")
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

"""Plugin Contract v1 — the single source of truth for declarative manifests.

This module is a validator only. It never executes plugin code, imports a
plugin module, evaluates JSON strings, starts a process, or reads secrets.
"""

from __future__ import annotations

import json
import re
from typing import Any, Literal
from urllib.parse import unquote

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


PLUGIN_MANIFEST_VERSION = "1.0"
HOST_API_VERSION = "1"
EXECUTION_MODE_DECLARATIVE = "declarative"

PLUGIN_CAPABILITIES = frozenset({"provider", "writing_tool", "multimodal_tool", "exporter", "workflow"})
PLUGIN_PERMISSIONS = frozenset({
    "network", "filesystem.read", "filesystem.write", "process",
    "model.text", "model.image", "model.audio", "model.video", "project.read", "project.write",
})

DECLARATIVE_RESOURCE_KINDS = frozenset({
    "writing_presets", "workflow_templates", "export_profiles",
})
ALLOWED_RESOURCE_MEDIA_TYPES = frozenset({"application/json"})

FORBIDDEN_EXECUTION_FIELDS = frozenset({
    "entrypoint", "script", "command", "executable", "module",
    "url-based-code", "install_hook", "postinstall",
})

MAX_RESOURCE_BYTES = 1 * 1024 * 1024
MAX_RESOURCE_COUNT = 100
MAX_TOTAL_RESOURCE_BYTES = 10 * 1024 * 1024
MAX_MANIFEST_BYTES = 256 * 1024

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?$")
PLUGIN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,79}$")
SHA256_HEX_RE = re.compile(r"^[a-fA-F0-9]{64}$")
PATH_COMPONENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")

PLUGIN_MANIFEST_INVALID = "PLUGIN_MANIFEST_INVALID"
PLUGIN_MANIFEST_UNSUPPORTED_VERSION = "PLUGIN_MANIFEST_UNSUPPORTED_VERSION"
PLUGIN_RESOURCE_PATH_INVALID = "PLUGIN_RESOURCE_PATH_INVALID"
PLUGIN_RESOURCE_TYPE_UNSUPPORTED = "PLUGIN_RESOURCE_TYPE_UNSUPPORTED"
PLUGIN_RESOURCE_TOO_LARGE = "PLUGIN_RESOURCE_TOO_LARGE"
PLUGIN_RESOURCE_HASH_MISMATCH = "PLUGIN_RESOURCE_HASH_MISMATCH"
PLUGIN_RESOURCE_INVALID_JSON = "PLUGIN_RESOURCE_INVALID_JSON"
PLUGIN_RESOURCE_SYMLINK_REJECTED = "PLUGIN_RESOURCE_SYMLINK_REJECTED"

SAFE_ERROR_MESSAGES = {
    PLUGIN_MANIFEST_INVALID: "插件清单无效，未通过合同校验。",
    PLUGIN_MANIFEST_UNSUPPORTED_VERSION: "插件清单或宿主 API 版本不受支持。",
    PLUGIN_RESOURCE_PATH_INVALID: "插件资源路径不合法。",
    PLUGIN_RESOURCE_TYPE_UNSUPPORTED: "插件资源类型不受支持。仅允许 JSON 声明式资源。",
    PLUGIN_RESOURCE_TOO_LARGE: "插件资源超出大小或数量限制。",
    PLUGIN_RESOURCE_HASH_MISMATCH: "插件资源完整性校验失败。",
    PLUGIN_RESOURCE_INVALID_JSON: "插件资源不是合法的 JSON 数据。",
    PLUGIN_RESOURCE_SYMLINK_REJECTED: "插件资源路径包含被拒绝的符号链接。",
}


class PluginContractError(ValueError):
    def __init__(self, code: str, message: str | None = None):
        self.code = code
        self.message = message or SAFE_ERROR_MESSAGES.get(code, SAFE_ERROR_MESSAGES[PLUGIN_MANIFEST_INVALID])
        super().__init__(f"{self.code}: {self.message}")


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def decode_until_stable(value: str, rounds: int = 4) -> str:
    current = value
    for _ in range(max(1, rounds)):
        nxt = unquote(current)
        if nxt == current:
            return current
        current = nxt
    return current


def _looks_like_windows_abs(value: str) -> bool:
    if re.match(r"^[A-Za-z]:[\\/]", value):
        return True
    if value.startswith("\\\\") or value.startswith("//"):
        return True
    if value.startswith("\\\\?\\") or value.lower().startswith("unc\\"):
        return True
    return False


def validate_declarative_relative_path(value: str) -> str:
    """Reject absolute, drive, UNC, traversal, backslash, and encoded variants."""
    if not isinstance(value, str) or not value or len(value) > 240:
        raise PluginContractError(PLUGIN_RESOURCE_PATH_INVALID)
    if "\x00" in value:
        raise PluginContractError(PLUGIN_RESOURCE_PATH_INVALID)
    decoded = decode_until_stable(value)
    if decoded != value:
        raise PluginContractError(PLUGIN_RESOURCE_PATH_INVALID)
    if "\\" in value or value.startswith("/") or _looks_like_windows_abs(value):
        raise PluginContractError(PLUGIN_RESOURCE_PATH_INVALID)
    if ":" in value:
        raise PluginContractError(PLUGIN_RESOURCE_PATH_INVALID)
    lowered = value.casefold()
    if ".." in value or "%2e" in lowered or "%2f" in lowered or "%5c" in lowered:
        raise PluginContractError(PLUGIN_RESOURCE_PATH_INVALID)
    parts = value.split("/")
    if any(not part or part in {".", ".."} for part in parts):
        raise PluginContractError(PLUGIN_RESOURCE_PATH_INVALID)
    filename = parts[-1]
    if "." not in filename:
        raise PluginContractError(PLUGIN_RESOURCE_TYPE_UNSUPPORTED)
    stem, ext = filename.rsplit(".", 1)
    if ext.casefold() != "json":
        raise PluginContractError(PLUGIN_RESOURCE_TYPE_UNSUPPORTED)
    if not PATH_COMPONENT_RE.fullmatch(stem):
        raise PluginContractError(PLUGIN_RESOURCE_PATH_INVALID)
    for part in parts[:-1]:
        if not PATH_COMPONENT_RE.fullmatch(part):
            raise PluginContractError(PLUGIN_RESOURCE_PATH_INVALID)
    return value


def resource_id_for(relative_path: str) -> str:
    return relative_path.replace("/", ":")


class PluginResourceRef(_StrictModel):
    kind: Literal["writing_presets", "workflow_templates", "export_profiles"]
    relative_path: str = Field(min_length=1, max_length=240)
    sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    media_type: str = Field(default="", max_length=120)
    schema_version: str = Field(default="", max_length=40)

    @field_validator("relative_path")
    @classmethod
    def safe_relative_path(cls, value: str) -> str:
        return validate_declarative_relative_path(value)

    @field_validator("sha256")
    @classmethod
    def lowercase_sha256(cls, value: str) -> str:
        if not SHA256_HEX_RE.fullmatch(value):
            raise ValueError("resource sha256 must be 64 hex characters")
        return value.lower()

    @field_validator("media_type")
    @classmethod
    def json_media_type(cls, value: str) -> str:
        if value and value not in ALLOWED_RESOURCE_MEDIA_TYPES:
            raise PluginContractError(PLUGIN_RESOURCE_TYPE_UNSUPPORTED)
        return value

    @model_validator(mode="after")
    def require_media_or_schema(self):
        if not self.media_type and not self.schema_version:
            raise ValueError("resource must declare media_type or schema_version")
        if self.media_type and self.media_type not in ALLOWED_RESOURCE_MEDIA_TYPES:
            raise PluginContractError(PLUGIN_RESOURCE_TYPE_UNSUPPORTED)
        return self


class PluginManifestV1(_StrictModel):
    """Declarative plugin manifest. Missing v1 fields receive safe defaults."""

    manifest_version: Literal["1.0"] = PLUGIN_MANIFEST_VERSION
    host_api_version: Literal["1"] = HOST_API_VERSION
    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{1,79}$")
    name: str = Field(min_length=1, max_length=160)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?$")
    description: str = Field(default="", max_length=4000)
    capabilities: list[str] = Field(default_factory=list, max_length=20)
    requested_permissions: list[str] = Field(default_factory=list, max_length=30)
    execution_mode: Literal["declarative"] = EXECUTION_MODE_DECLARATIVE
    publisher: str = Field(default="", max_length=160, description="Unverified publisher metadata; never a signature.")
    resources: list[PluginResourceRef] = Field(default_factory=list, max_length=MAX_RESOURCE_COUNT)

    @model_validator(mode="before")
    @classmethod
    def reject_execution_and_map_versions(cls, data: Any):
        if not isinstance(data, dict):
            return data
        forbidden = sorted(FORBIDDEN_EXECUTION_FIELDS.intersection(data))
        if forbidden:
            raise ValueError("plugin execution fields are not allowed")
        manifest_version = data.get("manifest_version", PLUGIN_MANIFEST_VERSION)
        host_api_version = data.get("host_api_version", HOST_API_VERSION)
        if manifest_version != PLUGIN_MANIFEST_VERSION or str(host_api_version) != HOST_API_VERSION:
            raise PluginContractError(PLUGIN_MANIFEST_UNSUPPORTED_VERSION)
        return data

    @model_validator(mode="after")
    def supported_contract(self):
        unknown_capabilities = set(self.capabilities) - PLUGIN_CAPABILITIES
        unknown_permissions = set(self.requested_permissions) - PLUGIN_PERMISSIONS
        if unknown_capabilities:
            raise ValueError("unsupported plugin capabilities")
        if unknown_permissions:
            raise ValueError("unsupported plugin permissions")
        self.capabilities = list(dict.fromkeys(self.capabilities))
        self.requested_permissions = list(dict.fromkeys(self.requested_permissions))
        if len(self.resources) > MAX_RESOURCE_COUNT:
            raise PluginContractError(PLUGIN_RESOURCE_TOO_LARGE)
        seen_paths: set[str] = set()
        for resource in self.resources:
            if resource.relative_path in seen_paths:
                raise PluginContractError(PLUGIN_RESOURCE_PATH_INVALID)
            seen_paths.add(resource.relative_path)
        return self

    def public_dump(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


PluginManifestIn = PluginManifestV1


def canonical_manifest_schema() -> dict[str, Any]:
    """JSON Schema derived from the runtime Pydantic model. Do not hand-edit."""
    return PluginManifestV1.model_json_schema()


def parse_plugin_manifest(payload: Any) -> PluginManifestV1:
    if not isinstance(payload, dict):
        raise PluginContractError(PLUGIN_MANIFEST_INVALID)
    forbidden = FORBIDDEN_EXECUTION_FIELDS.intersection(payload)
    if forbidden:
        raise PluginContractError(PLUGIN_MANIFEST_INVALID)
    manifest_version = payload.get("manifest_version", PLUGIN_MANIFEST_VERSION)
    host_api_version = payload.get("host_api_version", HOST_API_VERSION)
    if manifest_version != PLUGIN_MANIFEST_VERSION or str(host_api_version) != HOST_API_VERSION:
        raise PluginContractError(PLUGIN_MANIFEST_UNSUPPORTED_VERSION)
    try:
        return PluginManifestV1.model_validate(payload)
    except PluginContractError:
        raise
    except Exception as exc:
        code = _code_from_validation(exc)
        raise PluginContractError(code) from None


def _code_from_validation(exc: BaseException) -> str:
    text = str(exc)
    for code in (
        PLUGIN_MANIFEST_UNSUPPORTED_VERSION,
        PLUGIN_RESOURCE_PATH_INVALID,
        PLUGIN_RESOURCE_TYPE_UNSUPPORTED,
        PLUGIN_RESOURCE_TOO_LARGE,
        PLUGIN_RESOURCE_HASH_MISMATCH,
        PLUGIN_RESOURCE_INVALID_JSON,
        PLUGIN_RESOURCE_SYMLINK_REJECTED,
    ):
        if code in text:
            return code
    lowered = text.casefold()
    if "semver" in lowered or "version" in lowered and "pattern" in lowered:
        return PLUGIN_MANIFEST_INVALID
    if "relative_path" in lowered or "path" in lowered:
        return PLUGIN_RESOURCE_PATH_INVALID
    if "media_type" in lowered or "unsupported" in lowered and "resource" in lowered:
        return PLUGIN_RESOURCE_TYPE_UNSUPPORTED
    return PLUGIN_MANIFEST_INVALID


def safe_error(code: str) -> dict[str, str]:
    return {"error_code": code, "error": SAFE_ERROR_MESSAGES.get(code, SAFE_ERROR_MESSAGES[PLUGIN_MANIFEST_INVALID])}


def schema_json_bytes() -> bytes:
    return json.dumps(canonical_manifest_schema(), ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"

"""Plugin Runtime Foundation Phase 1 — execution contracts only.

These types are the shared vocabulary for a future Host → Broker → Supervisor
→ Worker path. This module never executes plugin code, never spawns a process,
never talks to the Credential Vault, never calls a Provider, and never mounts
a filesystem. `execution_supported` remains false.

Capability names reuse Plugin Contract v1 `PLUGIN_PERMISSIONS`. The existence
of a capability in this vocabulary is not an implementation of that capability.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.plugin_contracts import PLUGIN_ID_RE, PLUGIN_PERMISSIONS, SEMVER_RE, SHA256_HEX_RE


PLUGIN_RUNTIME_CONTRACT_VERSION = "phase1.v1"
PLUGIN_CAPABILITY_POLICY_VERSION = "phase1.v1"

KNOWN_RUNTIME_CAPABILITIES = PLUGIN_PERMISSIONS

PLUGIN_RUNTIME_CONTRACT_INVALID = "PLUGIN_RUNTIME_CONTRACT_INVALID"
PLUGIN_RUNTIME_UNKNOWN_FIELD = "PLUGIN_RUNTIME_UNKNOWN_FIELD"
PLUGIN_RUNTIME_SECRET_FIELD_FORBIDDEN = "PLUGIN_RUNTIME_SECRET_FIELD_FORBIDDEN"
PLUGIN_RUNTIME_ABSOLUTE_PATH_FORBIDDEN = "PLUGIN_RUNTIME_ABSOLUTE_PATH_FORBIDDEN"
PLUGIN_RUNTIME_COMMAND_FORBIDDEN = "PLUGIN_RUNTIME_COMMAND_FORBIDDEN"

ALLOWED_VIRTUAL_MOUNTS = ("/plugin", "/job/in", "/job/out", "/tmp")
FORBIDDEN_MOUNT_TARGETS = (
    "repository_source",
    "dotenv",
    "credential_vault",
    "database_data_directory",
    "other_plugin_packages",
    "user_home",
    "host_drive",
)

SECRET_FIELD_NAMES = frozenset({
    "secret", "api_key", "apikey", "password", "token", "access_token",
    "refresh_token", "private_key", "credential", "credentials", "dsn",
    "token_value", "raw_secret", "vault_secret", "plaintext",
})
COMMAND_FIELD_NAMES = frozenset({
    "command", "shell", "executable", "python_code", "js_code", "javascript",
    "entrypoint", "script", "module", "powershell", "subprocess", "argv",
    "host_path", "absolute_path", "cwd",
})
FORBIDDEN_RUNTIME_FIELDS = SECRET_FIELD_NAMES | COMMAND_FIELD_NAMES

OPERATION_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){1,6}$")
CAPABILITY_TOKEN_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]+)*$")
ISO_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")
HANDLE_ID_RE = re.compile(r"^credh_[0-9a-f]{32}$")
DECISION_ID_RE = re.compile(r"^capd_[0-9a-f]{32}$")

SAFE_RUNTIME_ERROR_MESSAGES = {
    PLUGIN_RUNTIME_CONTRACT_INVALID: "插件运行时契约无效。",
    PLUGIN_RUNTIME_UNKNOWN_FIELD: "插件运行时契约包含未知字段。",
    PLUGIN_RUNTIME_SECRET_FIELD_FORBIDDEN: "插件运行时契约禁止承载密钥或凭据明文。",
    PLUGIN_RUNTIME_ABSOLUTE_PATH_FORBIDDEN: "插件运行时契约禁止承载宿主绝对路径。",
    PLUGIN_RUNTIME_COMMAND_FORBIDDEN: "插件运行时契约禁止承载可执行命令或代码。",
}

JOB_OBJECT_IS_NOT_A_SECURITY_SANDBOX = True


class PluginRuntimeContractError(ValueError):
    def __init__(self, code: str, message: str | None = None):
        self.code = code
        self.message = message or SAFE_RUNTIME_ERROR_MESSAGES.get(
            code, SAFE_RUNTIME_ERROR_MESSAGES[PLUGIN_RUNTIME_CONTRACT_INVALID],
        )
        super().__init__(f"{self.code}: {self.message}")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_uuid() -> str:
    return str(uuid.uuid4())


def new_job_id() -> str:
    return new_uuid()


def new_execution_attempt_id() -> str:
    return new_uuid()


def new_credential_handle_id() -> str:
    return "credh_" + uuid.uuid4().hex


def new_decision_id() -> str:
    return "capd_" + uuid.uuid4().hex


def _normalize_key(key: str) -> str:
    return str(key).casefold().replace("-", "_")


def _looks_like_windows_abs(value: str) -> bool:
    if re.match(r"^[A-Za-z]:[\\/]", value):
        return True
    if value.startswith("\\\\") or value.startswith("//"):
        return True
    if value.startswith("\\\\?\\") or value.lower().startswith("unc\\"):
        return True
    return False


def _looks_like_host_absolute_path(value: str) -> bool:
    if value in ALLOWED_VIRTUAL_MOUNTS:
        return False
    if _looks_like_windows_abs(value):
        return True
    if value.startswith("/") and not value.startswith("/plugin") and value not in ALLOWED_VIRTUAL_MOUNTS:
        return True
    return False


def _looks_like_command(value: str) -> bool:
    lowered = value.casefold()
    if any(token in lowered for token in (".exe", "powershell", "cmd.exe", "/bin/sh", "bash -c")):
        return True
    if re.search(r"\b(python|node|pwsh|cmd)\b", lowered) and (" " in value or value.endswith(".py") or value.endswith(".js")):
        return True
    return False


def inspect_forbidden_payload(payload: Any) -> str | None:
    """Return a stable error code if the payload carries forbidden keys or values."""
    if isinstance(payload, dict):
        for key, value in payload.items():
            normalized = _normalize_key(key)
            if normalized in SECRET_FIELD_NAMES or "api_key" in normalized or normalized.endswith("_secret"):
                return PLUGIN_RUNTIME_SECRET_FIELD_FORBIDDEN
            if normalized in COMMAND_FIELD_NAMES:
                return PLUGIN_RUNTIME_COMMAND_FORBIDDEN
            nested = inspect_forbidden_payload(value)
            if nested:
                return nested
        return None
    if isinstance(payload, (list, tuple)):
        for item in payload:
            nested = inspect_forbidden_payload(item)
            if nested:
                return nested
        return None
    if isinstance(payload, str):
        if _looks_like_host_absolute_path(payload):
            return PLUGIN_RUNTIME_ABSOLUTE_PATH_FORBIDDEN
        if _looks_like_command(payload):
            return PLUGIN_RUNTIME_COMMAND_FORBIDDEN
    return None


def parse_runtime_model(cls: type[BaseModel], payload: Any) -> Any:
    if not isinstance(payload, dict):
        raise PluginRuntimeContractError(PLUGIN_RUNTIME_CONTRACT_INVALID)
    forbidden_code = inspect_forbidden_payload(payload)
    if forbidden_code:
        raise PluginRuntimeContractError(forbidden_code)
    unknown = set(payload) - set(cls.model_fields)
    if unknown:
        secretish = {_normalize_key(name) for name in unknown} & (SECRET_FIELD_NAMES | COMMAND_FIELD_NAMES)
        if secretish:
            code = PLUGIN_RUNTIME_SECRET_FIELD_FORBIDDEN if secretish & SECRET_FIELD_NAMES else PLUGIN_RUNTIME_COMMAND_FORBIDDEN
            raise PluginRuntimeContractError(code)
        raise PluginRuntimeContractError(PLUGIN_RUNTIME_UNKNOWN_FIELD)
    try:
        return cls.model_validate(payload)
    except PluginRuntimeContractError:
        raise
    except Exception as exc:
        text = str(exc).casefold()
        if "extra inputs are not permitted" in text:
            raise PluginRuntimeContractError(PLUGIN_RUNTIME_UNKNOWN_FIELD) from None
        raise PluginRuntimeContractError(PLUGIN_RUNTIME_CONTRACT_INVALID) from None


class StrictFrozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    @classmethod
    def parse(cls, payload: Any):
        return parse_runtime_model(cls, payload)

    def public_dump(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def canonical_json(self) -> bytes:
        return json.dumps(self.public_dump(), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _require_uuid(value: str) -> str:
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        raise ValueError("value must be a UUID") from None
    return str(parsed)


def _require_plugin_id(value: str) -> str:
    if not PLUGIN_ID_RE.fullmatch(value):
        raise ValueError("plugin_id is invalid")
    return value


def _require_semver(value: str) -> str:
    if not SEMVER_RE.fullmatch(value):
        raise ValueError("version is invalid")
    return value


def _require_sha256(value: str) -> str:
    if not SHA256_HEX_RE.fullmatch(value):
        raise ValueError("sha256 must be 64 hex characters")
    return value.lower()


def _require_timestamp(value: str) -> str:
    if not ISO_TIMESTAMP_RE.fullmatch(value):
        raise ValueError("timestamp must be ISO-8601")
    return value


def _require_operation(value: str) -> str:
    if not OPERATION_RE.fullmatch(value):
        raise ValueError("operation must be a dotted semantic token")
    return value


def _require_capability_token(value: str) -> str:
    if not value or not CAPABILITY_TOKEN_RE.fullmatch(value):
        raise ValueError("capability token is invalid")
    if "*" in value or "?" in value or "/" in value:
        raise ValueError("capability wildcards are forbidden")
    return value


def scope_id_violation(value: str | None) -> str | None:
    """Return a stable policy reason if a scope id is illegal. None means structurally usable."""
    if value is None:
        return None
    if value == "" or value != value.strip():
        return "INVALID_SCOPE"
    if "*" in value or "?" in value or "/" in value or value.endswith("-"):
        return "WILDCARD_SCOPE_FORBIDDEN"
    if value.startswith("workspace/") or value.endswith("/*") or "-*" in value:
        return "WILDCARD_SCOPE_FORBIDDEN"
    return None


class ExecutionModality(StrEnum):
    NOVEL = "NOVEL"
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    AUDIO = "AUDIO"
    TEXT = "TEXT"


class TrustStatus(StrEnum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    REVOKED = "REVOKED"


class OsSandboxKind(StrEnum):
    NOT_CONFIGURED = "NOT_CONFIGURED"
    APPCONTAINER = "APPCONTAINER"
    LPAC = "LPAC"
    EQUIVALENT_OS_ISOLATION = "EQUIVALENT_OS_ISOLATION"
    JOB_OBJECT_NOT_A_SANDBOX = "JOB_OBJECT_NOT_A_SANDBOX"


class CapabilityVerdict(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"


class ExecutionLifecycleState(StrEnum):
    CREATED = "CREATED"
    AUTHORIZATION_PENDING = "AUTHORIZATION_PENDING"
    AUTHORIZED = "AUTHORIZED"
    READY = "READY"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"
    REJECTED = "REJECTED"


TERMINAL_LIFECYCLE_STATES = frozenset({
    ExecutionLifecycleState.SUCCEEDED,
    ExecutionLifecycleState.FAILED,
    ExecutionLifecycleState.CANCELLED,
    ExecutionLifecycleState.TIMED_OUT,
    ExecutionLifecycleState.REJECTED,
})

EXECUTING_LIFECYCLE_STATES = frozenset({
    ExecutionLifecycleState.READY,
    ExecutionLifecycleState.STARTING,
    ExecutionLifecycleState.RUNNING,
})


class RuntimeKind(StrEnum):
    PLUGIN_WORKER = "plugin_worker"
    PROVIDER_RUNTIME = "provider_runtime"
    NODE_WORKFLOW = "node_workflow"
    COMPUTE_FABRIC = "compute_fabric"


class RuntimePlatform(StrEnum):
    WINDOWS = "windows"
    LINUX = "linux"
    DARWIN = "darwin"


class RuntimeArchitecture(StrEnum):
    X86_64 = "x86_64"
    ARM64 = "arm64"


class IsolationRequirement(StrEnum):
    DENY_ALL = "DENY_ALL"
    APPCONTAINER = "APPCONTAINER"
    LPAC = "LPAC"
    EQUIVALENT_OS_ISOLATION = "EQUIVALENT_OS_ISOLATION"


class ResourceClass(StrEnum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class MountMode(StrEnum):
    READ_ONLY = "read_only"
    QUOTA_WRITE = "quota_write"
    EPHEMERAL = "ephemeral"


class ImmutableExecutionScope(StrictFrozen):
    """Frozen, exact-match permission scope. Parent/child is never inferred from strings."""

    workspace_id: str | None = None
    project_id: str | None = None
    storyline_id: str | None = None
    modality: ExecutionModality | None = None
    resource_id: str | None = None

    @field_validator("workspace_id", "project_id", "storyline_id", "resource_id")
    @classmethod
    def reject_blank_or_wildcard(cls, value: str | None) -> str | None:
        if value is None:
            return value
        violation = scope_id_violation(value)
        if violation:
            raise ValueError(violation)
        if len(value) > 120:
            raise ValueError("INVALID_SCOPE")
        return value

    def exact_match(self, other: ImmutableExecutionScope) -> bool:
        return self.public_dump() == other.public_dump()


class PackageIdentity(StrictFrozen):
    plugin_id: str
    plugin_version: str
    package_sha256: str
    manifest_sha256: str

    @field_validator("plugin_id")
    @classmethod
    def valid_plugin_id(cls, value: str) -> str:
        return _require_plugin_id(value)

    @field_validator("plugin_version")
    @classmethod
    def valid_version(cls, value: str) -> str:
        return _require_semver(value)

    @field_validator("package_sha256", "manifest_sha256")
    @classmethod
    def valid_sha(cls, value: str) -> str:
        return _require_sha256(value)


class PluginIdentity(StrictFrozen):
    plugin_id: str
    plugin_version: str
    publisher: str = Field(default="", max_length=160)

    @field_validator("plugin_id")
    @classmethod
    def valid_plugin_id(cls, value: str) -> str:
        return _require_plugin_id(value)

    @field_validator("plugin_version")
    @classmethod
    def valid_version(cls, value: str) -> str:
        return _require_semver(value)


class ArtifactReference(StrictFrozen):
    artifact_id: str = Field(min_length=1, max_length=80)
    kind: Literal["input", "output"]
    media_type: str = Field(default="application/json", max_length=120)
    digest_sha256: str | None = None

    @field_validator("artifact_id")
    @classmethod
    def relative_artifact_id(cls, value: str) -> str:
        if not re.fullmatch(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$", value):
            raise ValueError("artifact_id must be a relative token")
        return value

    @field_validator("digest_sha256")
    @classmethod
    def optional_sha(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _require_sha256(value)


class OutputPolicyRef(StrictFrozen):
    policy_id: str = Field(min_length=1, max_length=80)
    max_output_bytes: int = Field(gt=0, le=10 * 1024 * 1024)
    allowed_media_types: tuple[str, ...] = ("application/json",)

    @field_validator("policy_id")
    @classmethod
    def semantic_policy_id(cls, value: str) -> str:
        if not re.fullmatch(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$", value):
            raise ValueError("policy_id must be a semantic token")
        return value


class RuntimeProfile(StrictFrozen):
    """Portable semantic description. Never a host executable path."""

    runtime_kind: RuntimeKind
    platform: RuntimePlatform
    architecture: RuntimeArchitecture
    isolation_requirement: IsolationRequirement = IsolationRequirement.DENY_ALL
    resource_class: ResourceClass = ResourceClass.SMALL
    capability_class: str = Field(default="none", max_length=40)

    @field_validator("capability_class")
    @classmethod
    def semantic_class(cls, value: str) -> str:
        if not re.fullmatch(r"^[a-z][a-z0-9_]*$", value):
            raise ValueError("capability_class must be a semantic token")
        return value


class ResourceLimitPolicy(StrictFrozen):
    wall_time_ms: int = Field(gt=0, le=600_000)
    cpu_time_ms: int = Field(gt=0, le=600_000)
    memory_bytes: int = Field(gt=0, le=4 * 1024 * 1024 * 1024)
    output_bytes: int = Field(gt=0, le=64 * 1024 * 1024)
    temp_bytes: int = Field(gt=0, le=64 * 1024 * 1024)
    process_count: int = Field(ge=1, le=1)
    file_count: int = Field(gt=0, le=256)
    enforcement_implemented: Literal[False] = False


class VirtualMount(StrictFrozen):
    path: Literal["/plugin", "/job/in", "/job/out", "/tmp"]
    mode: MountMode


class VirtualMountPolicy(StrictFrozen):
    mounts: tuple[VirtualMount, ...]
    forbidden_targets: tuple[str, ...] = FORBIDDEN_MOUNT_TARGETS
    host_mount_implemented: Literal[False] = False

    @model_validator(mode="after")
    def known_mounts_only(self):
        paths = tuple(item.path for item in self.mounts)
        if set(paths) != set(ALLOWED_VIRTUAL_MOUNTS):
            raise ValueError("virtual mount set must be exactly the four worker mounts")
        if len(paths) != 4:
            raise ValueError("virtual mount set must not duplicate mounts")
        return self


class NetworkPolicy(StrictFrozen):
    default: Literal["DENY"] = "DENY"
    domain_allowlist: tuple[str, ...] = ()
    broker_controlled: Literal[True] = True
    implementation_status: Literal["NONE"] = "NONE"

    @field_validator("domain_allowlist")
    @classmethod
    def reserved_allowlist_not_self_grant(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value:
            raise ValueError("Phase 1 network allowlist must stay empty; broker implementation is NONE")
        return value


class SubprocessPolicy(StrictFrozen):
    default: Literal["PROHIBITED"] = "PROHIBITED"
    blender_via_host_adapter_only: Literal[True] = True
    comfyui_via_host_adapter_only: Literal[True] = True
    implementation_status: Literal["POLICY_DECLARED"] = "POLICY_DECLARED"


class CredentialHandle(StrictFrozen):
    """Opaque handle. Raw secrets never belong on this contract."""

    handle_id: str
    provider_id: str = Field(min_length=1, max_length=80)
    scope: ImmutableExecutionScope
    kind: str = Field(default="model.text", max_length=40)
    expires_at: str | None = None

    @field_validator("handle_id")
    @classmethod
    def opaque_handle(cls, value: str) -> str:
        if not HANDLE_ID_RE.fullmatch(value):
            raise ValueError("handle_id must be an opaque credh_ reference")
        return value

    @field_validator("provider_id")
    @classmethod
    def semantic_provider(cls, value: str) -> str:
        if not re.fullmatch(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$", value):
            raise ValueError("provider_id must be a semantic token")
        return value

    @field_validator("kind")
    @classmethod
    def capability_kind(cls, value: str) -> str:
        return _require_capability_token(value)

    @field_validator("expires_at")
    @classmethod
    def optional_expiry(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _require_timestamp(value)


class CapabilityRequest(StrictFrozen):
    capability: str
    scope: ImmutableExecutionScope
    operation: str
    execution_attempt_id: str
    plugin_id: str
    plugin_version: str
    resource_ref: ArtifactReference | None = None
    constraints: tuple[str, ...] = ()

    @field_validator("capability")
    @classmethod
    def capability_token(cls, value: str) -> str:
        return _require_capability_token(value)

    @field_validator("operation")
    @classmethod
    def semantic_operation(cls, value: str) -> str:
        return _require_operation(value)

    @field_validator("execution_attempt_id")
    @classmethod
    def uuid_attempt(cls, value: str) -> str:
        return _require_uuid(value)

    @field_validator("plugin_id")
    @classmethod
    def valid_plugin_id(cls, value: str) -> str:
        return _require_plugin_id(value)

    @field_validator("plugin_version")
    @classmethod
    def valid_version(cls, value: str) -> str:
        return _require_semver(value)

    @field_validator("constraints")
    @classmethod
    def semantic_constraints(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for item in value:
            if not re.fullmatch(r"^[a-z][a-z0-9_]{0,40}=[A-Za-z0-9._-]{1,80}$", item):
                raise ValueError("constraint must be a semantic key=value token")
        return value


class CapabilityDecision(StrictFrozen):
    decision: CapabilityVerdict
    reason_code: str = Field(min_length=1, max_length=80)
    execution_attempt_id: str
    capability: str
    scope: ImmutableExecutionScope
    policy_version: str = PLUGIN_CAPABILITY_POLICY_VERSION
    evaluated_at: str
    decision_id: str

    @field_validator("execution_attempt_id")
    @classmethod
    def uuid_attempt(cls, value: str) -> str:
        return _require_uuid(value)

    @field_validator("decision_id")
    @classmethod
    def opaque_decision(cls, value: str) -> str:
        if not DECISION_ID_RE.fullmatch(value):
            raise ValueError("decision_id must be an opaque capd_ reference")
        return value

    @field_validator("evaluated_at")
    @classmethod
    def iso_time(cls, value: str) -> str:
        return _require_timestamp(value)

    @field_validator("capability")
    @classmethod
    def capability_token(cls, value: str) -> str:
        return _require_capability_token(value)

    @field_validator("reason_code")
    @classmethod
    def stable_reason(cls, value: str) -> str:
        if not re.fullmatch(r"^[A-Z][A-Z0-9_]{2,78}$", value):
            raise ValueError("reason_code must be a stable uppercase token")
        return value


class CapabilityDecisionRef(StrictFrozen):
    decision_id: str
    decision: CapabilityVerdict
    reason_code: str
    capability: str
    policy_version: str = PLUGIN_CAPABILITY_POLICY_VERSION

    @field_validator("decision_id")
    @classmethod
    def opaque_decision(cls, value: str) -> str:
        if not DECISION_ID_RE.fullmatch(value):
            raise ValueError("decision_id must be an opaque capd_ reference")
        return value


class ExecutionGateSnapshot(StrictFrozen):
    plugin_contract_valid: bool = False
    manifest_reviewed: bool = False
    plugin_enabled: bool = False
    package_identity_verified: bool = False
    package_trust: TrustStatus = TrustStatus.UNVERIFIED
    capability_broker_ready: bool = False
    worker_runtime_ready: bool = False
    os_sandbox_ready: bool = False
    os_sandbox_kind: OsSandboxKind = OsSandboxKind.NOT_CONFIGURED
    runtime_profile_supported: bool = False
    execution_supported: bool = False
    captured_at: str = Field(default_factory=utcnow)

    @field_validator("captured_at")
    @classmethod
    def iso_time(cls, value: str) -> str:
        return _require_timestamp(value)

    @model_validator(mode="after")
    def production_honesty(self):
        if self.package_trust is TrustStatus.VERIFIED and self.execution_supported is False:
            return self
        return self


class ExecutionProvenance(StrictFrozen):
    plugin_id: str
    plugin_version: str
    package_sha256: str
    manifest_sha256: str
    job_id: str
    execution_attempt_id: str
    scope: ImmutableExecutionScope
    runtime_profile: RuntimeProfile
    capability_decision_refs: tuple[CapabilityDecisionRef, ...] = ()
    created_at: str
    publisher_trust: TrustStatus = TrustStatus.UNVERIFIED

    @field_validator("plugin_id")
    @classmethod
    def valid_plugin_id(cls, value: str) -> str:
        return _require_plugin_id(value)

    @field_validator("plugin_version")
    @classmethod
    def valid_version(cls, value: str) -> str:
        return _require_semver(value)

    @field_validator("package_sha256", "manifest_sha256")
    @classmethod
    def valid_sha(cls, value: str) -> str:
        return _require_sha256(value)

    @field_validator("job_id", "execution_attempt_id")
    @classmethod
    def uuid_ids(cls, value: str) -> str:
        return _require_uuid(value)

    @field_validator("created_at")
    @classmethod
    def iso_time(cls, value: str) -> str:
        return _require_timestamp(value)


class PluginExecutionJob(StrictFrozen):
    job_id: str
    execution_attempt_id: str
    plugin_id: str
    plugin_version: str
    package_identity: PackageIdentity
    operation: str
    scope: ImmutableExecutionScope
    runtime_profile: RuntimeProfile
    requested_capabilities: tuple[str, ...] = ()
    approved_capabilities: tuple[str, ...] = ()
    created_at: str
    provenance: ExecutionProvenance
    input_references: tuple[ArtifactReference, ...] = ()
    output_policy: OutputPolicyRef
    lifecycle_state: ExecutionLifecycleState = ExecutionLifecycleState.CREATED
    resource_limits: ResourceLimitPolicy
    virtual_mounts: VirtualMountPolicy
    network_policy: NetworkPolicy = Field(default_factory=NetworkPolicy)
    subprocess_policy: SubprocessPolicy = Field(default_factory=SubprocessPolicy)
    trust_status: TrustStatus = TrustStatus.UNVERIFIED

    @field_validator("job_id", "execution_attempt_id")
    @classmethod
    def uuid_ids(cls, value: str) -> str:
        return _require_uuid(value)

    @field_validator("plugin_id")
    @classmethod
    def valid_plugin_id(cls, value: str) -> str:
        return _require_plugin_id(value)

    @field_validator("plugin_version")
    @classmethod
    def valid_version(cls, value: str) -> str:
        return _require_semver(value)

    @field_validator("operation")
    @classmethod
    def semantic_operation(cls, value: str) -> str:
        return _require_operation(value)

    @field_validator("created_at")
    @classmethod
    def iso_time(cls, value: str) -> str:
        return _require_timestamp(value)

    @field_validator("requested_capabilities", "approved_capabilities")
    @classmethod
    def capability_tokens(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_require_capability_token(item) for item in value)

    @model_validator(mode="after")
    def identities_align(self):
        if self.package_identity.plugin_id != self.plugin_id:
            raise ValueError("package identity plugin_id mismatch")
        if self.package_identity.plugin_version != self.plugin_version:
            raise ValueError("package identity plugin_version mismatch")
        if self.provenance.plugin_id != self.plugin_id or self.provenance.plugin_version != self.plugin_version:
            raise ValueError("provenance plugin identity mismatch")
        if self.provenance.job_id != self.job_id or self.provenance.execution_attempt_id != self.execution_attempt_id:
            raise ValueError("provenance attempt identity mismatch")
        if not self.provenance.scope.exact_match(self.scope):
            raise ValueError("provenance scope mismatch")
        return self


class ExecutionResultEnvelope(StrictFrozen):
    job_id: str
    execution_attempt_id: str
    produced_at: str
    output_digest_sha256: str | None = None
    status: Literal["SUCCEEDED", "FAILED"] = "SUCCEEDED"

    @field_validator("job_id", "execution_attempt_id")
    @classmethod
    def uuid_ids(cls, value: str) -> str:
        return _require_uuid(value)

    @field_validator("produced_at")
    @classmethod
    def iso_time(cls, value: str) -> str:
        return _require_timestamp(value)

    @field_validator("output_digest_sha256")
    @classmethod
    def optional_sha(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _require_sha256(value)


class LateResultDecision(StrictFrozen):
    accepted: bool
    reason_code: str
    expected_job_id: str
    expected_attempt_id: str
    actual_job_id: str
    actual_attempt_id: str

    @field_validator("reason_code")
    @classmethod
    def stable_reason(cls, value: str) -> str:
        if not re.fullmatch(r"^[A-Z][A-Z0-9_]{2,78}$", value):
            raise ValueError("reason_code must be a stable uppercase token")
        return value


class LifecycleTransitionDecision(StrictFrozen):
    allowed: bool
    reason_code: str
    source: ExecutionLifecycleState
    target: ExecutionLifecycleState


class GateEvaluation(StrictFrozen):
    allowed: bool
    reason_codes: tuple[str, ...]
    snapshot: ExecutionGateSnapshot


def phase1_resource_limit_policy() -> ResourceLimitPolicy:
    return ResourceLimitPolicy(
        wall_time_ms=15_000,
        cpu_time_ms=5_000,
        memory_bytes=256 * 1024 * 1024,
        output_bytes=1 * 1024 * 1024,
        temp_bytes=64 * 1024 * 1024,
        process_count=1,
        file_count=32,
        enforcement_implemented=False,
    )


def phase1_virtual_mount_policy() -> VirtualMountPolicy:
    return VirtualMountPolicy(
        mounts=(
            VirtualMount(path="/plugin", mode=MountMode.READ_ONLY),
            VirtualMount(path="/job/in", mode=MountMode.READ_ONLY),
            VirtualMount(path="/job/out", mode=MountMode.QUOTA_WRITE),
            VirtualMount(path="/tmp", mode=MountMode.EPHEMERAL),
        ),
        forbidden_targets=FORBIDDEN_MOUNT_TARGETS,
        host_mount_implemented=False,
    )


def phase1_runtime_profile(*, platform: RuntimePlatform = RuntimePlatform.LINUX) -> RuntimeProfile:
    return RuntimeProfile(
        runtime_kind=RuntimeKind.PLUGIN_WORKER,
        platform=platform,
        architecture=RuntimeArchitecture.X86_64,
        isolation_requirement=IsolationRequirement.DENY_ALL,
        resource_class=ResourceClass.SMALL,
        capability_class="none",
    )


def phase1_production_gate(*, captured_at: str | None = None) -> ExecutionGateSnapshot:
    """Honest production snapshot. Signing, worker, sandbox, and broker are not ready."""
    return ExecutionGateSnapshot(
        plugin_contract_valid=True,
        manifest_reviewed=True,
        plugin_enabled=True,
        package_identity_verified=True,
        package_trust=TrustStatus.UNVERIFIED,
        capability_broker_ready=False,
        worker_runtime_ready=False,
        os_sandbox_ready=False,
        os_sandbox_kind=OsSandboxKind.NOT_CONFIGURED,
        runtime_profile_supported=True,
        execution_supported=False,
        captured_at=captured_at or utcnow(),
    )


def default_output_policy() -> OutputPolicyRef:
    return OutputPolicyRef(policy_id="phase1.quota-limited", max_output_bytes=1 * 1024 * 1024)


def dump_without_secrets(model: StrictFrozen) -> dict[str, Any]:
    payload = model.public_dump()
    code = inspect_forbidden_payload(payload)
    if code:
        raise PluginRuntimeContractError(code)
    return payload

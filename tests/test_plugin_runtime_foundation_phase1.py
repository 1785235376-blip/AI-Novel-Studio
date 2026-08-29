from __future__ import annotations

import hashlib
import json
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.plugin_capability_policy import (
    REASON_ACCEPTED,
    REASON_ATTEMPT_MISMATCH,
    REASON_CAPABILITY_NOT_APPROVED,
    REASON_EXECUTION_NOT_SUPPORTED,
    REASON_ILLEGAL_LIFECYCLE_TRANSITION,
    REASON_JOB_ID_MISMATCH,
    REASON_JOB_OBJECT_IS_NOT_A_SANDBOX,
    REASON_MISSING_APPROVAL,
    REASON_OS_SANDBOX_NOT_READY,
    REASON_PACKAGE_UNTRUSTED,
    REASON_PLUGIN_IDENTITY_MISMATCH,
    REASON_PREFIX_SCOPE_FORBIDDEN,
    REASON_RETRY_REQUIRES_NEW_ATTEMPT,
    REASON_SCOPE_MISMATCH,
    REASON_STALE_EXECUTION_ATTEMPT,
    REASON_TERMINAL_STATE_CANNOT_RESTART,
    REASON_UNKNOWN_CAPABILITY,
    REASON_WILDCARD_SCOPE_FORBIDDEN,
    REASON_WORKER_RUNTIME_NOT_READY,
    begin_retry,
    evaluate_capability_request,
    evaluate_execution_gate,
    evaluate_late_result,
    evaluate_lifecycle_transition,
    evaluate_retry_attempt,
)
from app.plugin_contracts import EXECUTION_MODE_DECLARATIVE, PLUGIN_PERMISSIONS, parse_plugin_manifest
from app.plugin_runtime_contracts import (
    FORBIDDEN_RUNTIME_FIELDS,
    JOB_OBJECT_IS_NOT_A_SECURITY_SANDBOX,
    KNOWN_RUNTIME_CAPABILITIES,
    PLUGIN_RUNTIME_ABSOLUTE_PATH_FORBIDDEN,
    PLUGIN_RUNTIME_COMMAND_FORBIDDEN,
    PLUGIN_RUNTIME_SECRET_FIELD_FORBIDDEN,
    PLUGIN_RUNTIME_UNKNOWN_FIELD,
    ArtifactReference,
    CapabilityDecision,
    CapabilityRequest,
    CapabilityVerdict,
    CredentialHandle,
    ExecutionGateSnapshot,
    ExecutionLifecycleState,
    ExecutionProvenance,
    ExecutionResultEnvelope,
    ImmutableExecutionScope,
    IsolationRequirement,
    OsSandboxKind,
    PackageIdentity,
    PluginExecutionJob,
    PluginRuntimeContractError,
    RuntimeKind,
    RuntimePlatform,
    TrustStatus,
    default_output_policy,
    dump_without_secrets,
    inspect_forbidden_payload,
    is_allowed_virtual_mount_path,
    new_credential_handle_id,
    new_execution_attempt_id,
    new_job_id,
    phase1_production_gate,
    phase1_resource_limit_policy,
    phase1_runtime_profile,
    phase1_virtual_mount_policy,
    utcnow,
)


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def make_scope(**overrides) -> ImmutableExecutionScope:
    payload = {
        "workspace_id": "ws-main",
        "project_id": "proj-alpha",
        "storyline_id": "story-1",
        "modality": "NOVEL",
        "resource_id": "chapter-9",
    }
    payload.update(overrides)
    return ImmutableExecutionScope.parse(payload)


def make_package() -> PackageIdentity:
    return PackageIdentity.parse({
        "plugin_id": "story-workflow-pack",
        "plugin_version": "1.0.0",
        "package_sha256": _sha("package"),
        "manifest_sha256": _sha("manifest"),
    })


def make_job(**overrides) -> PluginExecutionJob:
    job_id = overrides.get("job_id") or new_job_id()
    attempt_id = overrides.get("execution_attempt_id") or new_execution_attempt_id()
    scope = overrides.get("scope") or make_scope()
    package = overrides.get("package_identity") or make_package()
    profile = overrides.get("runtime_profile") or phase1_runtime_profile()
    created_at = overrides.get("created_at") or utcnow()
    provenance = overrides.get("provenance") or ExecutionProvenance.parse({
        "plugin_id": package.plugin_id,
        "plugin_version": package.plugin_version,
        "package_sha256": package.package_sha256,
        "manifest_sha256": package.manifest_sha256,
        "job_id": job_id,
        "execution_attempt_id": attempt_id,
        "scope": scope.public_dump(),
        "runtime_profile": profile.public_dump(),
        "created_at": created_at,
        "publisher_trust": "UNVERIFIED",
    })
    payload = {
        "job_id": job_id,
        "execution_attempt_id": attempt_id,
        "plugin_id": package.plugin_id,
        "plugin_version": package.plugin_version,
        "package_identity": package.public_dump(),
        "operation": "workflow.template.instantiate",
        "scope": scope.public_dump(),
        "runtime_profile": profile.public_dump(),
        "requested_capabilities": ["project.read"],
        "approved_capabilities": ["project.read"],
        "created_at": created_at,
        "provenance": provenance.public_dump(),
        "input_references": [{"artifact_id": "scene-draft", "kind": "input"}],
        "output_policy": default_output_policy().public_dump(),
        "lifecycle_state": "CREATED",
        "resource_limits": phase1_resource_limit_policy().public_dump(),
        "virtual_mounts": phase1_virtual_mount_policy().public_dump(),
        "network_policy": {"default": "DENY", "domain_allowlist": [], "broker_controlled": True, "implementation_status": "NONE"},
        "subprocess_policy": {
            "default": "PROHIBITED",
            "blender_via_host_adapter_only": True,
            "comfyui_via_host_adapter_only": True,
            "implementation_status": "POLICY_DECLARED",
        },
        "trust_status": "UNVERIFIED",
    }
    payload.update({key: (value.public_dump() if hasattr(value, "public_dump") else value) for key, value in overrides.items()})
    return PluginExecutionJob.parse(payload)


def make_request(job: PluginExecutionJob, **overrides) -> CapabilityRequest:
    payload = {
        "capability": "project.read",
        "scope": job.scope.public_dump(),
        "operation": job.operation,
        "execution_attempt_id": job.execution_attempt_id,
        "plugin_id": job.plugin_id,
        "plugin_version": job.plugin_version,
    }
    payload.update(overrides)
    return CapabilityRequest.parse(payload)


def open_gate() -> ExecutionGateSnapshot:
    return ExecutionGateSnapshot.parse({
        "plugin_contract_valid": True,
        "manifest_reviewed": True,
        "plugin_enabled": True,
        "package_identity_verified": True,
        "package_trust": "VERIFIED",
        "capability_broker_ready": True,
        "worker_runtime_ready": True,
        "os_sandbox_ready": True,
        "os_sandbox_kind": "APPCONTAINER",
        "runtime_profile_supported": True,
        "execution_supported": True,
        "captured_at": utcnow(),
    })


def _assert_code(exc: pytest.ExceptionInfo, code: str) -> None:
    assert exc.value.code == code


def test_job_round_trip_serialization():
    job = make_job()
    restored = PluginExecutionJob.parse(json.loads(job.canonical_json()))
    assert restored.public_dump() == job.public_dump()
    assert restored.execution_attempt_id == job.execution_attempt_id
    assert restored.network_policy.default == "DENY"
    assert restored.subprocess_policy.default == "PROHIBITED"
    assert restored.resource_limits.enforcement_implemented is False
    assert restored.virtual_mounts.host_mount_implemented is False


def test_unknown_field_rejected_on_job_and_scope():
    job = make_job().public_dump()
    job["extra_hook"] = True
    with pytest.raises(PluginRuntimeContractError) as caught:
        PluginExecutionJob.parse(job)
    _assert_code(caught, PLUGIN_RUNTIME_UNKNOWN_FIELD)
    with pytest.raises(PluginRuntimeContractError) as caught:
        ImmutableExecutionScope.parse({"workspace_id": "ws-main", "unexpected": "x"})
    _assert_code(caught, PLUGIN_RUNTIME_UNKNOWN_FIELD)


@pytest.mark.parametrize("field", sorted(SECRET_FIELD for SECRET_FIELD in FORBIDDEN_RUNTIME_FIELDS if SECRET_FIELD in {
    "secret", "api_key", "password", "token", "dsn",
}))
def test_secret_like_fields_forbidden_on_runtime_contracts(field):
    payload = make_job().public_dump()
    payload[field] = "super-secret"
    with pytest.raises(PluginRuntimeContractError) as caught:
        PluginExecutionJob.parse(payload)
    _assert_code(caught, PLUGIN_RUNTIME_SECRET_FIELD_FORBIDDEN)


@pytest.mark.parametrize("field,value", [
    ("command", "rm -rf /"),
    ("executable", "python.exe"),
    ("entrypoint", "main.py"),
    ("host_path", "C:\\Windows\\System32"),
])
def test_command_and_host_path_fields_forbidden(field, value):
    payload = make_job().public_dump()
    payload[field] = value
    with pytest.raises(PluginRuntimeContractError) as caught:
        PluginExecutionJob.parse(payload)
    assert caught.value.code in {PLUGIN_RUNTIME_COMMAND_FORBIDDEN, PLUGIN_RUNTIME_ABSOLUTE_PATH_FORBIDDEN, PLUGIN_RUNTIME_SECRET_FIELD_FORBIDDEN}


def test_host_absolute_path_values_forbidden():
    with pytest.raises(PluginRuntimeContractError) as caught:
        ArtifactReference.parse({"artifact_id": "scene-draft", "kind": "input", "media_type": "C:\\secrets\\key.json"})
    assert caught.value.code in {PLUGIN_RUNTIME_ABSOLUTE_PATH_FORBIDDEN, PLUGIN_RUNTIME_COMMAND_FORBIDDEN, PLUGIN_RUNTIME_UNKNOWN_FIELD, "PLUGIN_RUNTIME_CONTRACT_INVALID"}


def test_execution_scope_is_immutable():
    scope = make_scope()
    with pytest.raises((ValidationError, TypeError)):
        scope.project_id = "proj-beta"
    dumped = scope.public_dump()
    dumped["project_id"] = "proj-beta"
    mutated = ImmutableExecutionScope.parse(dumped)
    assert scope.exact_match(mutated) is False


def test_exact_scope_matching_and_no_prefix_or_wildcard_authorization():
    job = make_job()
    request = make_request(job)
    allowed = evaluate_capability_request(request, job=job, gate=open_gate())
    assert allowed.decision is CapabilityVerdict.ALLOW

    prefix = make_request(job, scope=make_scope(project_id="proj").public_dump())
    denied_prefix = evaluate_capability_request(prefix, job=job, gate=open_gate())
    assert denied_prefix.decision is CapabilityVerdict.DENY
    assert denied_prefix.reason_code == REASON_PREFIX_SCOPE_FORBIDDEN

    other = make_request(job, scope=make_scope(project_id="proj-omega").public_dump())
    denied_other = evaluate_capability_request(other, job=job, gate=open_gate())
    assert denied_other.decision is CapabilityVerdict.DENY
    assert denied_other.reason_code == REASON_SCOPE_MISMATCH


@pytest.mark.parametrize("wildcard", ["proj-*", "workspace/*", "*", "project-*"])
def test_wildcard_scope_ids_are_rejected(wildcard):
    with pytest.raises((PluginRuntimeContractError, ValidationError)):
        make_scope(project_id=wildcard)


def test_unknown_capability_is_denied():
    job = make_job()
    request = make_request(job, capability="novel.read")
    decision = evaluate_capability_request(request, job=job, gate=open_gate())
    assert decision.decision is CapabilityVerdict.DENY
    assert decision.reason_code == REASON_UNKNOWN_CAPABILITY


def test_missing_approval_is_denied():
    job = make_job(approved_capabilities=())
    request = make_request(job)
    decision = evaluate_capability_request(request, job=job, gate=open_gate())
    assert decision.decision is CapabilityVerdict.DENY
    assert decision.reason_code == REASON_MISSING_APPROVAL


def test_capability_outside_approved_set_is_denied():
    job = make_job(requested_capabilities=["project.read", "project.write"], approved_capabilities=["project.read"])
    request = make_request(job, capability="project.write")
    decision = evaluate_capability_request(request, job=job, gate=open_gate())
    assert decision.decision is CapabilityVerdict.DENY
    assert decision.reason_code == REASON_CAPABILITY_NOT_APPROVED


def test_production_gate_denies_execution():
    snapshot = phase1_production_gate()
    result = evaluate_execution_gate(snapshot)
    assert result.allowed is False
    assert REASON_EXECUTION_NOT_SUPPORTED in result.reason_codes
    assert REASON_WORKER_RUNTIME_NOT_READY in result.reason_codes
    assert REASON_OS_SANDBOX_NOT_READY in result.reason_codes
    assert REASON_PACKAGE_UNTRUSTED in result.reason_codes
    assert snapshot.execution_supported is False
    job = make_job()
    decision = evaluate_capability_request(make_request(job), job=job, gate=snapshot)
    assert decision.decision is CapabilityVerdict.DENY
    assert decision.reason_code == REASON_PACKAGE_UNTRUSTED


def test_execution_supported_false_denies():
    gate = open_gate().model_copy(update={"execution_supported": False})
    job = make_job()
    decision = evaluate_capability_request(make_request(job), job=job, gate=gate)
    assert decision.decision is CapabilityVerdict.DENY
    assert decision.reason_code == REASON_EXECUTION_NOT_SUPPORTED


def test_worker_runtime_ready_false_denies():
    gate = open_gate().model_copy(update={"worker_runtime_ready": False})
    job = make_job()
    decision = evaluate_capability_request(make_request(job), job=job, gate=gate)
    assert decision.decision is CapabilityVerdict.DENY
    assert decision.reason_code == REASON_WORKER_RUNTIME_NOT_READY


def test_os_sandbox_ready_false_denies():
    gate = open_gate().model_copy(update={"os_sandbox_ready": False, "os_sandbox_kind": OsSandboxKind.NOT_CONFIGURED})
    job = make_job()
    decision = evaluate_capability_request(make_request(job), job=job, gate=gate)
    assert decision.decision is CapabilityVerdict.DENY
    assert decision.reason_code == REASON_OS_SANDBOX_NOT_READY


def test_capability_broker_not_ready_denies():
    gate = open_gate().model_copy(update={"capability_broker_ready": False})
    job = make_job()
    decision = evaluate_capability_request(make_request(job), job=job, gate=gate)
    assert decision.decision is CapabilityVerdict.DENY
    assert decision.reason_code == "CAPABILITY_BROKER_NOT_READY"


def test_job_object_is_not_a_security_sandbox():
    assert JOB_OBJECT_IS_NOT_A_SECURITY_SANDBOX is True
    gate = open_gate().model_copy(update={
        "os_sandbox_ready": True,
        "os_sandbox_kind": OsSandboxKind.JOB_OBJECT_NOT_A_SANDBOX,
    })
    result = evaluate_execution_gate(gate)
    assert result.allowed is False
    assert REASON_JOB_OBJECT_IS_NOT_A_SANDBOX in result.reason_codes


def test_opaque_credential_handle_contains_no_secret():
    handle = CredentialHandle.parse({
        "handle_id": new_credential_handle_id(),
        "provider_id": "openai",
        "scope": make_scope().public_dump(),
        "kind": "model.text",
        "expires_at": utcnow(),
    })
    dumped = dump_without_secrets(handle)
    assert "secret" not in dumped
    assert "api_key" not in dumped
    assert "password" not in dumped
    assert dumped["handle_id"].startswith("credh_")
    with pytest.raises(PluginRuntimeContractError) as caught:
        CredentialHandle.parse({**handle.public_dump(), "secret": "sk-live"})
    _assert_code(caught, PLUGIN_RUNTIME_SECRET_FIELD_FORBIDDEN)


def test_illegal_lifecycle_transition_rejected():
    decision = evaluate_lifecycle_transition(ExecutionLifecycleState.SUCCEEDED, ExecutionLifecycleState.RUNNING)
    assert decision.allowed is False
    assert decision.reason_code == REASON_TERMINAL_STATE_CANNOT_RESTART
    created_to_running = evaluate_lifecycle_transition(ExecutionLifecycleState.CREATED, ExecutionLifecycleState.RUNNING)
    assert created_to_running.allowed is False
    assert created_to_running.reason_code == REASON_ILLEGAL_LIFECYCLE_TRANSITION


@pytest.mark.parametrize("terminal", [
    ExecutionLifecycleState.SUCCEEDED,
    ExecutionLifecycleState.FAILED,
    ExecutionLifecycleState.CANCELLED,
    ExecutionLifecycleState.TIMED_OUT,
    ExecutionLifecycleState.REJECTED,
])
def test_terminal_states_cannot_restart(terminal):
    decision = evaluate_lifecycle_transition(terminal, ExecutionLifecycleState.RUNNING, gate=open_gate())
    assert decision.allowed is False
    assert decision.reason_code == REASON_TERMINAL_STATE_CANNOT_RESTART


def test_retry_requires_new_attempt_id():
    job = make_job(lifecycle_state=ExecutionLifecycleState.FAILED)
    same = evaluate_retry_attempt(job.execution_attempt_id, job.execution_attempt_id)
    assert same.allowed is False
    assert same.reason_code == REASON_RETRY_REQUIRES_NEW_ATTEMPT
    retried = begin_retry(job)
    assert retried.job_id == job.job_id
    assert retried.execution_attempt_id != job.execution_attempt_id
    assert retried.lifecycle_state is ExecutionLifecycleState.CREATED
    assert retried.scope.exact_match(job.scope)


def test_late_old_attempt_result_rejected_and_current_accepted():
    first = make_job(lifecycle_state=ExecutionLifecycleState.TIMED_OUT)
    second = begin_retry(first)
    running = second.model_copy(update={"lifecycle_state": ExecutionLifecycleState.RUNNING})
    stale = ExecutionResultEnvelope.parse({
        "job_id": first.job_id,
        "execution_attempt_id": first.execution_attempt_id,
        "produced_at": utcnow(),
        "output_digest_sha256": _sha("late"),
        "status": "SUCCEEDED",
    })
    rejected = evaluate_late_result(
        stale,
        expected_job_id=running.job_id,
        expected_attempt_id=running.execution_attempt_id,
        current_lifecycle=running.lifecycle_state,
    )
    assert rejected.accepted is False
    assert rejected.reason_code == REASON_STALE_EXECUTION_ATTEMPT

    current = ExecutionResultEnvelope.parse({
        "job_id": running.job_id,
        "execution_attempt_id": running.execution_attempt_id,
        "produced_at": utcnow(),
        "output_digest_sha256": _sha("ok"),
        "status": "SUCCEEDED",
    })
    accepted = evaluate_late_result(
        current,
        expected_job_id=running.job_id,
        expected_attempt_id=running.execution_attempt_id,
        current_lifecycle=ExecutionLifecycleState.RUNNING,
    )
    assert accepted.accepted is True
    assert accepted.reason_code == REASON_ACCEPTED


def test_provenance_does_not_contain_raw_credential():
    job = make_job()
    dumped = dump_without_secrets(job.provenance)
    blob = json.dumps(dumped)
    assert "sk-" not in blob
    assert "api_key" not in dumped
    assert "password" not in dumped
    assert "secret" not in dumped
    assert dumped["publisher_trust"] == "UNVERIFIED"


def test_official_publisher_is_not_cryptographic_trust():
    job = make_job()
    assert job.trust_status is TrustStatus.UNVERIFIED
    assert job.provenance.publisher_trust is TrustStatus.UNVERIFIED
    gate = phase1_production_gate()
    assert gate.package_trust is TrustStatus.UNVERIFIED


def test_runtime_profile_is_portable_not_a_host_path():
    profile = phase1_runtime_profile(platform=RuntimePlatform.WINDOWS)
    assert profile.runtime_kind is RuntimeKind.PLUGIN_WORKER
    assert profile.isolation_requirement is IsolationRequirement.DENY_ALL
    dumped = profile.public_dump()
    assert "python.exe" not in json.dumps(dumped)
    assert "C:\\" not in json.dumps(dumped)
    with pytest.raises(PluginRuntimeContractError):
        type(profile).parse({**dumped, "python_path": "C:\\Python\\python.exe"})


def test_ready_state_requires_open_gate():
    denied = evaluate_lifecycle_transition(
        ExecutionLifecycleState.AUTHORIZED,
        ExecutionLifecycleState.READY,
        gate=phase1_production_gate(),
    )
    assert denied.allowed is False
    allowed = evaluate_lifecycle_transition(
        ExecutionLifecycleState.AUTHORIZED,
        ExecutionLifecycleState.READY,
        gate=open_gate(),
    )
    assert allowed.allowed is True


def test_stale_request_attempt_is_denied():
    job = make_job()
    request = make_request(job, execution_attempt_id=new_execution_attempt_id())
    decision = evaluate_capability_request(request, job=job, gate=open_gate())
    assert decision.decision is CapabilityVerdict.DENY
    assert decision.reason_code == REASON_ATTEMPT_MISMATCH


def test_capability_vocabulary_reuses_plugin_contract_permissions():
    assert KNOWN_RUNTIME_CAPABILITIES == PLUGIN_PERMISSIONS
    for name in ("project.read", "project.write", "model.text", "model.image", "model.audio", "model.video",
                 "filesystem.read", "filesystem.write", "network", "process"):
        assert name in KNOWN_RUNTIME_CAPABILITIES


def test_virtual_mount_policy_is_declared_not_mounted():
    policy = phase1_virtual_mount_policy()
    paths = {item.path: item.mode.value for item in policy.mounts}
    assert paths == {
        "/plugin": "read_only",
        "/job/in": "read_only",
        "/job/out": "quota_write",
        "/tmp": "ephemeral",
    }
    assert policy.host_mount_implemented is False
    assert "credential_vault" in policy.forbidden_targets
    assert "repository_source" in policy.forbidden_targets


def test_network_and_subprocess_remain_denied():
    job = make_job()
    assert job.network_policy.default == "DENY"
    assert job.network_policy.implementation_status == "NONE"
    assert job.network_policy.domain_allowlist == ()
    assert job.subprocess_policy.default == "PROHIBITED"
    with pytest.raises(PluginRuntimeContractError):
        type(job.network_policy).parse({**job.network_policy.public_dump(), "domain_allowlist": ["evil.example"]})


def test_request_is_not_authorization():
    job = make_job(approved_capabilities=())
    request = make_request(job, capability="network")
    decision = evaluate_capability_request(request, job=job, gate=open_gate())
    assert request.capability == "network"
    assert decision.decision is CapabilityVerdict.DENY
    assert decision.reason_code == REASON_MISSING_APPROVAL


def test_decision_is_serializable_and_fail_closed_by_default():
    job = make_job()
    decision = evaluate_capability_request(make_request(job), job=job, gate=phase1_production_gate())
    restored = CapabilityDecision.parse(json.loads(decision.canonical_json()))
    assert restored.decision is CapabilityVerdict.DENY
    assert restored.policy_version == "phase1.v1"


def test_declarative_execution_mode_is_unchanged_data_only():
    manifest = parse_plugin_manifest({"id": "story-workflow-pack", "name": "故事", "version": "1.0.0"})
    assert manifest.execution_mode == EXECUTION_MODE_DECLARATIVE
    job = make_job()
    assert "execution_mode" not in job.public_dump()
    assert job.trust_status is TrustStatus.UNVERIFIED


def test_policy_and_contracts_have_no_subprocess_network_vault_or_provider_side_effects():
    def boom(*_args, **_kwargs):
        raise AssertionError("forbidden side effect")

    job = make_job()
    request = make_request(job)
    with patch("subprocess.Popen", boom), patch("subprocess.run", boom), \
            patch("os.system", boom), patch("socket.create_connection", boom), \
            patch("httpx.Client.request", boom), patch("httpx.Client.get", boom):
        with patch("app.credential_vault.credential_vault.resolve", boom):
            dumped = PluginExecutionJob.parse(job.public_dump())
            evaluate_capability_request(request, job=dumped, gate=phase1_production_gate())
            evaluate_execution_gate(phase1_production_gate())
            evaluate_lifecycle_transition(ExecutionLifecycleState.CREATED, ExecutionLifecycleState.REJECTED)
            evaluate_late_result(
                ExecutionResultEnvelope.parse({
                    "job_id": job.job_id,
                    "execution_attempt_id": job.execution_attempt_id,
                    "produced_at": utcnow(),
                    "status": "FAILED",
                }),
                expected_job_id=job.job_id,
                expected_attempt_id=new_execution_attempt_id(),
                current_lifecycle=ExecutionLifecycleState.RUNNING,
            )
            dump_without_secrets(job)


@pytest.mark.parametrize("capability", ["UNKNOWN", "model.*", "project-*"])
def test_security_unknown_or_wildcard_capability_fail_closed(capability):
    job = make_job()
    try:
        request = make_request(job, capability=capability)
    except PluginRuntimeContractError:
        return
    decision = evaluate_capability_request(request, job=job, gate=open_gate())
    assert decision.decision is CapabilityVerdict.DENY
    assert decision.reason_code in {REASON_UNKNOWN_CAPABILITY, REASON_WILDCARD_SCOPE_FORBIDDEN}


def test_wrong_plugin_id_is_denied():
    job = make_job()
    request = make_request(job, plugin_id="other-plugin-pack")
    decision = evaluate_capability_request(request, job=job, gate=open_gate())
    assert decision.decision is CapabilityVerdict.DENY
    assert decision.reason_code == REASON_PLUGIN_IDENTITY_MISMATCH


def test_wrong_plugin_version_is_denied():
    job = make_job()
    request = make_request(job, plugin_version="9.9.9")
    decision = evaluate_capability_request(request, job=job, gate=open_gate())
    assert decision.decision is CapabilityVerdict.DENY
    assert decision.reason_code == REASON_PLUGIN_IDENTITY_MISMATCH


def test_omitted_scope_field_is_not_a_wildcard():
    job = make_job()
    omitted = make_request(job, scope=make_scope(resource_id=None).public_dump())
    decision = evaluate_capability_request(omitted, job=job, gate=open_gate())
    assert decision.decision is CapabilityVerdict.DENY
    assert decision.reason_code == REASON_SCOPE_MISMATCH
    job_without = make_job(scope=ImmutableExecutionScope.parse({
        "workspace_id": "ws-main",
        "project_id": "proj-alpha",
        "storyline_id": "story-1",
        "modality": "NOVEL",
    }))
    extra = make_request(job_without, scope=make_scope().public_dump())
    denied = evaluate_capability_request(extra, job=job_without, gate=open_gate())
    assert denied.decision is CapabilityVerdict.DENY
    assert denied.reason_code == REASON_SCOPE_MISMATCH


def test_revoked_package_trust_is_denied():
    gate = open_gate().model_copy(update={"package_trust": TrustStatus.REVOKED})
    result = evaluate_execution_gate(gate)
    assert result.allowed is False
    assert "PACKAGE_REVOKED" in result.reason_codes
    job = make_job()
    decision = evaluate_capability_request(make_request(job), job=job, gate=gate)
    assert decision.decision is CapabilityVerdict.DENY
    assert decision.reason_code == "PACKAGE_REVOKED"


def test_wrong_job_id_late_result_is_rejected():
    job = make_job()
    envelope = ExecutionResultEnvelope.parse({
        "job_id": new_job_id(),
        "execution_attempt_id": job.execution_attempt_id,
        "produced_at": utcnow(),
        "status": "SUCCEEDED",
    })
    rejected = evaluate_late_result(
        envelope,
        expected_job_id=job.job_id,
        expected_attempt_id=job.execution_attempt_id,
        current_lifecycle=ExecutionLifecycleState.RUNNING,
    )
    assert rejected.accepted is False
    assert rejected.reason_code == REASON_JOB_ID_MISMATCH


@pytest.mark.parametrize("value,allowed", [
    ("/plugin", True),
    ("/plugin/foo", True),
    ("/job/in", True),
    ("/job/in/input.json", True),
    ("/job/out", True),
    ("/tmp", True),
    ("/tmp/cache", True),
    ("/plugin-evil", False),
    ("/plugin-evil/x", False),
    ("/job/input", False),
    ("/tmpfoo", False),
    ("/plugin/../etc/passwd", False),
    ("/job/in/../out", False),
    ("/tmp/..", False),
    ("/plugin/", False),
    ("/etc/passwd", False),
])
def test_virtual_mount_paths_are_component_aware(value, allowed):
    assert is_allowed_virtual_mount_path(value) is allowed
    code = inspect_forbidden_payload(value)
    if allowed:
        assert code is None
    else:
        assert code == PLUGIN_RUNTIME_ABSOLUTE_PATH_FORBIDDEN

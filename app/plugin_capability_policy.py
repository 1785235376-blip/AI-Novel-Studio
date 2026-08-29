"""Pure, side-effect-free capability and execution policy for Plugin Runtime Phase 1.

This evaluator does not access a database, filesystem, Credential Vault,
Provider, network, or process. It only maps typed contracts onto fail-closed
decisions. Plugin code execution remains disabled.
"""

from __future__ import annotations

from typing import Iterable

from app.plugin_runtime_contracts import (
    PLUGIN_CAPABILITY_POLICY_VERSION,
    CapabilityDecision,
    CapabilityRequest,
    CapabilityVerdict,
    EXECUTING_LIFECYCLE_STATES,
    ExecutionGateSnapshot,
    ExecutionLifecycleState,
    ExecutionResultEnvelope,
    GateEvaluation,
    ImmutableExecutionScope,
    KNOWN_RUNTIME_CAPABILITIES,
    LateResultDecision,
    LifecycleTransitionDecision,
    OsSandboxKind,
    PluginExecutionJob,
    TERMINAL_LIFECYCLE_STATES,
    TrustStatus,
    new_decision_id,
    new_execution_attempt_id,
    scope_id_violation,
    utcnow,
)


REASON_ACCEPTED = "ACCEPTED"
REASON_STALE_EXECUTION_ATTEMPT = "STALE_EXECUTION_ATTEMPT"
REASON_JOB_ID_MISMATCH = "JOB_ID_MISMATCH"
REASON_ATTEMPT_NOT_RUNNING = "ATTEMPT_NOT_RUNNING"
REASON_UNKNOWN_CAPABILITY = "UNKNOWN_CAPABILITY"
REASON_MISSING_APPROVAL = "MISSING_APPROVAL"
REASON_CAPABILITY_NOT_APPROVED = "CAPABILITY_NOT_APPROVED"
REASON_INVALID_SCOPE = "INVALID_SCOPE"
REASON_WILDCARD_SCOPE_FORBIDDEN = "WILDCARD_SCOPE_FORBIDDEN"
REASON_PREFIX_SCOPE_FORBIDDEN = "PREFIX_SCOPE_FORBIDDEN"
REASON_SCOPE_MISMATCH = "SCOPE_MISMATCH"
REASON_MISSING_CONTEXT = "MISSING_CONTEXT"
REASON_ATTEMPT_MISMATCH = "ATTEMPT_MISMATCH"
REASON_PLUGIN_IDENTITY_MISMATCH = "PLUGIN_IDENTITY_MISMATCH"
REASON_AMBIGUOUS_REQUEST = "AMBIGUOUS_REQUEST"
REASON_EXECUTION_NOT_SUPPORTED = "EXECUTION_NOT_SUPPORTED"
REASON_WORKER_RUNTIME_NOT_READY = "WORKER_RUNTIME_NOT_READY"
REASON_OS_SANDBOX_NOT_READY = "OS_SANDBOX_NOT_READY"
REASON_CAPABILITY_BROKER_NOT_READY = "CAPABILITY_BROKER_NOT_READY"
REASON_PACKAGE_UNTRUSTED = "PACKAGE_UNTRUSTED"
REASON_PACKAGE_REVOKED = "PACKAGE_REVOKED"
REASON_PLUGIN_CONTRACT_INVALID = "PLUGIN_CONTRACT_INVALID"
REASON_MANIFEST_NOT_REVIEWED = "MANIFEST_NOT_REVIEWED"
REASON_PLUGIN_NOT_ENABLED = "PLUGIN_NOT_ENABLED"
REASON_PACKAGE_IDENTITY_UNVERIFIED = "PACKAGE_IDENTITY_UNVERIFIED"
REASON_RUNTIME_PROFILE_UNSUPPORTED = "RUNTIME_PROFILE_UNSUPPORTED"
REASON_JOB_OBJECT_IS_NOT_A_SANDBOX = "JOB_OBJECT_IS_NOT_A_SANDBOX"
REASON_GATE_NOT_READY = "GATE_NOT_READY"
REASON_ILLEGAL_LIFECYCLE_TRANSITION = "ILLEGAL_LIFECYCLE_TRANSITION"
REASON_TERMINAL_STATE_CANNOT_RESTART = "TERMINAL_STATE_CANNOT_RESTART"
REASON_RETRY_REQUIRES_NEW_ATTEMPT = "RETRY_REQUIRES_NEW_ATTEMPT"

LEGAL_LIFECYCLE_TRANSITIONS: dict[ExecutionLifecycleState, frozenset[ExecutionLifecycleState]] = {
    ExecutionLifecycleState.CREATED: frozenset({
        ExecutionLifecycleState.AUTHORIZATION_PENDING,
        ExecutionLifecycleState.REJECTED,
    }),
    ExecutionLifecycleState.AUTHORIZATION_PENDING: frozenset({
        ExecutionLifecycleState.AUTHORIZED,
        ExecutionLifecycleState.REJECTED,
    }),
    ExecutionLifecycleState.AUTHORIZED: frozenset({
        ExecutionLifecycleState.READY,
        ExecutionLifecycleState.REJECTED,
    }),
    ExecutionLifecycleState.READY: frozenset({
        ExecutionLifecycleState.STARTING,
        ExecutionLifecycleState.REJECTED,
        ExecutionLifecycleState.CANCEL_REQUESTED,
    }),
    ExecutionLifecycleState.STARTING: frozenset({
        ExecutionLifecycleState.RUNNING,
        ExecutionLifecycleState.FAILED,
        ExecutionLifecycleState.REJECTED,
        ExecutionLifecycleState.CANCEL_REQUESTED,
    }),
    ExecutionLifecycleState.RUNNING: frozenset({
        ExecutionLifecycleState.SUCCEEDED,
        ExecutionLifecycleState.FAILED,
        ExecutionLifecycleState.TIMED_OUT,
        ExecutionLifecycleState.CANCEL_REQUESTED,
    }),
    ExecutionLifecycleState.CANCEL_REQUESTED: frozenset({
        ExecutionLifecycleState.CANCELLED,
        ExecutionLifecycleState.FAILED,
        ExecutionLifecycleState.TIMED_OUT,
    }),
}

OS_SANDBOX_READY_KINDS = frozenset({
    OsSandboxKind.APPCONTAINER,
    OsSandboxKind.LPAC,
    OsSandboxKind.EQUIVALENT_OS_ISOLATION,
})


def _deny(
    request: CapabilityRequest,
    reason_code: str,
    *,
    evaluated_at: str | None = None,
) -> CapabilityDecision:
    return CapabilityDecision(
        decision=CapabilityVerdict.DENY,
        reason_code=reason_code,
        execution_attempt_id=request.execution_attempt_id,
        capability=request.capability,
        scope=request.scope,
        policy_version=PLUGIN_CAPABILITY_POLICY_VERSION,
        evaluated_at=evaluated_at or utcnow(),
        decision_id=new_decision_id(),
    )


def _allow(
    request: CapabilityRequest,
    *,
    evaluated_at: str | None = None,
) -> CapabilityDecision:
    return CapabilityDecision(
        decision=CapabilityVerdict.ALLOW,
        reason_code=REASON_ACCEPTED,
        execution_attempt_id=request.execution_attempt_id,
        capability=request.capability,
        scope=request.scope,
        policy_version=PLUGIN_CAPABILITY_POLICY_VERSION,
        evaluated_at=evaluated_at or utcnow(),
        decision_id=new_decision_id(),
    )


def _scope_field_violation(scope: ImmutableExecutionScope) -> str | None:
    for value in (scope.workspace_id, scope.project_id, scope.storyline_id, scope.resource_id):
        violation = scope_id_violation(value)
        if violation:
            return violation
    return None


def scopes_match_exactly(left: ImmutableExecutionScope, right: ImmutableExecutionScope) -> bool:
    return left.exact_match(right)


def is_prefix_impersonation(request_scope: ImmutableExecutionScope, job_scope: ImmutableExecutionScope) -> bool:
    """True when a request id is a string prefix of the frozen job id (or vice versa)."""
    pairs = (
        (request_scope.workspace_id, job_scope.workspace_id),
        (request_scope.project_id, job_scope.project_id),
        (request_scope.storyline_id, job_scope.storyline_id),
        (request_scope.resource_id, job_scope.resource_id),
    )
    for requested, frozen in pairs:
        if requested is None or frozen is None or requested == frozen:
            continue
        if frozen.startswith(requested) or requested.startswith(frozen):
            return True
    return False


def evaluate_execution_gate(snapshot: ExecutionGateSnapshot) -> GateEvaluation:
    reasons: list[str] = []
    if not snapshot.plugin_contract_valid:
        reasons.append(REASON_PLUGIN_CONTRACT_INVALID)
    if not snapshot.manifest_reviewed:
        reasons.append(REASON_MANIFEST_NOT_REVIEWED)
    if not snapshot.plugin_enabled:
        reasons.append(REASON_PLUGIN_NOT_ENABLED)
    if not snapshot.package_identity_verified:
        reasons.append(REASON_PACKAGE_IDENTITY_UNVERIFIED)
    if snapshot.package_trust is TrustStatus.REVOKED:
        reasons.append(REASON_PACKAGE_REVOKED)
    elif snapshot.package_trust is not TrustStatus.VERIFIED:
        reasons.append(REASON_PACKAGE_UNTRUSTED)
    if not snapshot.capability_broker_ready:
        reasons.append(REASON_CAPABILITY_BROKER_NOT_READY)
    if not snapshot.worker_runtime_ready:
        reasons.append(REASON_WORKER_RUNTIME_NOT_READY)
    if snapshot.os_sandbox_kind is OsSandboxKind.JOB_OBJECT_NOT_A_SANDBOX:
        reasons.append(REASON_JOB_OBJECT_IS_NOT_A_SANDBOX)
    if not snapshot.os_sandbox_ready or snapshot.os_sandbox_kind not in OS_SANDBOX_READY_KINDS:
        if REASON_JOB_OBJECT_IS_NOT_A_SANDBOX not in reasons:
            reasons.append(REASON_OS_SANDBOX_NOT_READY)
    if not snapshot.runtime_profile_supported:
        reasons.append(REASON_RUNTIME_PROFILE_UNSUPPORTED)
    if not snapshot.execution_supported:
        reasons.append(REASON_EXECUTION_NOT_SUPPORTED)
    unique = tuple(dict.fromkeys(reasons))
    return GateEvaluation(allowed=not unique, reason_codes=unique, snapshot=snapshot)


def evaluate_capability_request(
    request: CapabilityRequest,
    *,
    job: PluginExecutionJob | None = None,
    approved_capabilities: Iterable[str] | None = None,
    gate: ExecutionGateSnapshot | None = None,
    evaluated_at: str | None = None,
) -> CapabilityDecision:
    """Fail-closed capability decision. Request is never authorization."""
    if not request.plugin_id or not request.execution_attempt_id:
        return _deny(request, REASON_MISSING_CONTEXT, evaluated_at=evaluated_at)
    if request.scope.modality is None and request.scope.project_id is None and request.scope.workspace_id is None:
        return _deny(request, REASON_MISSING_CONTEXT, evaluated_at=evaluated_at)

    scope_violation = _scope_field_violation(request.scope)
    if scope_violation:
        return _deny(request, scope_violation, evaluated_at=evaluated_at)

    if job is not None:
        if request.execution_attempt_id != job.execution_attempt_id:
            return _deny(request, REASON_ATTEMPT_MISMATCH, evaluated_at=evaluated_at)
        if request.plugin_id != job.plugin_id or request.plugin_version != job.plugin_version:
            return _deny(request, REASON_PLUGIN_IDENTITY_MISMATCH, evaluated_at=evaluated_at)
        if not scopes_match_exactly(request.scope, job.scope):
            if is_prefix_impersonation(request.scope, job.scope):
                return _deny(request, REASON_PREFIX_SCOPE_FORBIDDEN, evaluated_at=evaluated_at)
            return _deny(request, REASON_SCOPE_MISMATCH, evaluated_at=evaluated_at)
        host_approved = tuple(job.approved_capabilities)
    else:
        host_approved = tuple(approved_capabilities or ())

    if request.capability not in KNOWN_RUNTIME_CAPABILITIES:
        return _deny(request, REASON_UNKNOWN_CAPABILITY, evaluated_at=evaluated_at)

    approved = frozenset(host_approved)
    if not approved:
        return _deny(request, REASON_MISSING_APPROVAL, evaluated_at=evaluated_at)
    if request.capability not in approved:
        return _deny(request, REASON_CAPABILITY_NOT_APPROVED, evaluated_at=evaluated_at)
    if any(item not in KNOWN_RUNTIME_CAPABILITIES for item in approved):
        return _deny(request, REASON_AMBIGUOUS_REQUEST, evaluated_at=evaluated_at)

    snapshot = gate
    if snapshot is None:
        return _deny(request, REASON_GATE_NOT_READY, evaluated_at=evaluated_at)
    gate_result = evaluate_execution_gate(snapshot)
    if not gate_result.allowed:
        return _deny(request, gate_result.reason_codes[0], evaluated_at=evaluated_at)

    return _allow(request, evaluated_at=evaluated_at)


def evaluate_lifecycle_transition(
    source: ExecutionLifecycleState,
    target: ExecutionLifecycleState,
    *,
    gate: ExecutionGateSnapshot | None = None,
) -> LifecycleTransitionDecision:
    if source is target:
        return LifecycleTransitionDecision(
            allowed=False,
            reason_code=REASON_ILLEGAL_LIFECYCLE_TRANSITION,
            source=source,
            target=target,
        )
    if source in TERMINAL_LIFECYCLE_STATES:
        return LifecycleTransitionDecision(
            allowed=False,
            reason_code=REASON_TERMINAL_STATE_CANNOT_RESTART,
            source=source,
            target=target,
        )
    allowed_targets = LEGAL_LIFECYCLE_TRANSITIONS.get(source, frozenset())
    if target not in allowed_targets:
        return LifecycleTransitionDecision(
            allowed=False,
            reason_code=REASON_ILLEGAL_LIFECYCLE_TRANSITION,
            source=source,
            target=target,
        )
    if target in EXECUTING_LIFECYCLE_STATES:
        snapshot = gate
        if snapshot is None:
            return LifecycleTransitionDecision(
                allowed=False,
                reason_code=REASON_GATE_NOT_READY,
                source=source,
                target=target,
            )
        gate_result = evaluate_execution_gate(snapshot)
        if not gate_result.allowed:
            return LifecycleTransitionDecision(
                allowed=False,
                reason_code=gate_result.reason_codes[0],
                source=source,
                target=target,
            )
    return LifecycleTransitionDecision(
        allowed=True,
        reason_code=REASON_ACCEPTED,
        source=source,
        target=target,
    )


def evaluate_retry_attempt(previous_attempt_id: str, next_attempt_id: str) -> LifecycleTransitionDecision:
    if not previous_attempt_id or not next_attempt_id or previous_attempt_id == next_attempt_id:
        return LifecycleTransitionDecision(
            allowed=False,
            reason_code=REASON_RETRY_REQUIRES_NEW_ATTEMPT,
            source=ExecutionLifecycleState.FAILED,
            target=ExecutionLifecycleState.CREATED,
        )
    return LifecycleTransitionDecision(
        allowed=True,
        reason_code=REASON_ACCEPTED,
        source=ExecutionLifecycleState.FAILED,
        target=ExecutionLifecycleState.CREATED,
    )


def begin_retry(job: PluginExecutionJob) -> PluginExecutionJob:
    """Create a new attempt for the same job. Never resurrects the old attempt."""
    if job.lifecycle_state not in TERMINAL_LIFECYCLE_STATES:
        raise ValueError(REASON_RETRY_REQUIRES_NEW_ATTEMPT)
    next_attempt = new_execution_attempt_id()
    retry = evaluate_retry_attempt(job.execution_attempt_id, next_attempt)
    if not retry.allowed:
        raise ValueError(retry.reason_code)
    provenance = job.provenance.model_copy(update={
        "execution_attempt_id": next_attempt,
        "created_at": utcnow(),
        "capability_decision_refs": (),
    })
    return job.model_copy(update={
        "execution_attempt_id": next_attempt,
        "lifecycle_state": ExecutionLifecycleState.CREATED,
        "created_at": provenance.created_at,
        "provenance": provenance,
    })


def evaluate_late_result(
    envelope: ExecutionResultEnvelope,
    *,
    expected_job_id: str,
    expected_attempt_id: str,
    current_lifecycle: ExecutionLifecycleState,
) -> LateResultDecision:
    if envelope.job_id != expected_job_id:
        return LateResultDecision(
            accepted=False,
            reason_code=REASON_JOB_ID_MISMATCH,
            expected_job_id=expected_job_id,
            expected_attempt_id=expected_attempt_id,
            actual_job_id=envelope.job_id,
            actual_attempt_id=envelope.execution_attempt_id,
        )
    if envelope.execution_attempt_id != expected_attempt_id:
        return LateResultDecision(
            accepted=False,
            reason_code=REASON_STALE_EXECUTION_ATTEMPT,
            expected_job_id=expected_job_id,
            expected_attempt_id=expected_attempt_id,
            actual_job_id=envelope.job_id,
            actual_attempt_id=envelope.execution_attempt_id,
        )
    if current_lifecycle is not ExecutionLifecycleState.RUNNING:
        return LateResultDecision(
            accepted=False,
            reason_code=REASON_ATTEMPT_NOT_RUNNING,
            expected_job_id=expected_job_id,
            expected_attempt_id=expected_attempt_id,
            actual_job_id=envelope.job_id,
            actual_attempt_id=envelope.execution_attempt_id,
        )
    return LateResultDecision(
        accepted=True,
        reason_code=REASON_ACCEPTED,
        expected_job_id=expected_job_id,
        expected_attempt_id=expected_attempt_id,
        actual_job_id=envelope.job_id,
        actual_attempt_id=envelope.execution_attempt_id,
    )

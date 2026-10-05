"""Internal, read-only orchestration; never an execution or authorization API.

Production accepts a request only and reads already-initialized Host owners.
The private owner seam exists for isolated tests, not client dependency injection.
"""
from __future__ import annotations

import sys
from enum import Enum
from typing import Annotated, Literal

from pydantic import Field

from .provider_routing_policy_v2 import evaluate_routing
from .provider_runtime_v2_contracts import (
    CandidateDescriptor, Contract, ExecutionNodeIdentity, HardwareSnapshot,
    Location, ProviderRoutingDecision, ProviderRoutingRequest,
)
from .provider_runtime_v2_host_hardware_inventory import (
    HostHardwareInventoryError, collect_host_hardware_snapshot,
)
from .provider_runtime_v2_model_center_snapshot_bridge import (
    ProviderRuntimeSnapshot, SnapshotItem, SnapshotRejection, SnapshotRejectionCode,
    build_provider_runtime_snapshot,
)
from .stable_identity import validate_uuid


MAX_SOURCE_ITEMS = 1024
Count = Annotated[int, Field(ge=0, le=MAX_SOURCE_ITEMS)]


class ServiceCode(str, Enum):
    HOST_NOT_INITIALIZED = "HOST_NOT_INITIALIZED"
    INVALID_REQUEST = "INVALID_REQUEST"
    REQUEST_AUTHORITY_UNSUPPORTED = "REQUEST_AUTHORITY_UNSUPPORTED"
    NODE_ID_UNAVAILABLE = "NODE_ID_UNAVAILABLE"
    REQUEST_NODE_MISMATCH = "REQUEST_NODE_MISMATCH"
    SNAPSHOT_SOURCE_FAILED = "SNAPSHOT_SOURCE_FAILED"
    SNAPSHOT_VERSION_UNSUPPORTED = "SNAPSHOT_VERSION_UNSUPPORTED"
    SNAPSHOT_LIMIT_EXCEEDED = "SNAPSHOT_LIMIT_EXCEEDED"
    SNAPSHOT_INVALID = "SNAPSHOT_INVALID"
    SNAPSHOT_PROFILE_UNSUPPORTED = "SNAPSHOT_PROFILE_UNSUPPORTED"
    SNAPSHOT_NODE_MISMATCH = "SNAPSHOT_NODE_MISMATCH"
    HARDWARE_SOURCE_FAILED = "HARDWARE_SOURCE_FAILED"
    HARDWARE_INVALID = "HARDWARE_INVALID"
    HARDWARE_NODE_MISMATCH = "HARDWARE_NODE_MISMATCH"


class HardwareStatus(str, Enum):
    NOT_COLLECTED = "NOT_COLLECTED"
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    UNSUPPORTED_PLATFORM = "UNSUPPORTED_PLATFORM"
    EXECUTION_NODE_ID_INVALID = "EXECUTION_NODE_ID_INVALID"
    EXECUTION_NODE_ID_UNAVAILABLE = "EXECUTION_NODE_ID_UNAVAILABLE"
    GPU_FACT_UNAVAILABLE = "GPU_FACT_UNAVAILABLE"
    INVALID_HARDWARE_FACT = "INVALID_HARDWARE_FACT"
    RAM_FACT_UNAVAILABLE = "RAM_FACT_UNAVAILABLE"
    UNKNOWN_ARCHITECTURE = "UNKNOWN_ARCHITECTURE"


class RejectionCount(Contract):
    code: SnapshotRejectionCode
    count: Annotated[int, Field(gt=0, le=MAX_SOURCE_ITEMS)]


class RoutingReport(Contract):
    version: Literal["2.1D-routing-service-1"] = "2.1D-routing-service-1"
    decision: ProviderRoutingDecision
    service_codes: tuple[ServiceCode, ...] = ()
    # Counts describe a fully validated snapshot only. Zero on failure is not
    # evidence of an empty source; snapshot_complete distinguishes those cases.
    snapshot_complete: bool = False
    source_item_count: Count = 0
    candidate_count: Count = 0
    rejection_count: Count = 0
    source_rejections: tuple[RejectionCount, ...] = ()
    hardware_status: HardwareStatus = HardwareStatus.NOT_COLLECTED

    def to_dict(self) -> dict:
        return self.model_dump(mode="json")


def _empty_report(request: ProviderRoutingRequest | None, code: ServiceCode) -> RoutingReport:
    # Use the existing evaluator's empty-source decision, not a new policy reason.
    if request is None:
        # An invalid request was never evaluated. The existing decision schema
        # can describe unavailable routing, but carries no service failure codes.
        from .provider_runtime_v2_contracts import Decision, ReasonCode
        decision = ProviderRoutingDecision(
            decision=Decision.NO_COMPATIBLE_ROUTE, reason_code=ReasonCode.NO_CANDIDATES,
        )
    else:
        decision = evaluate_routing(request, ())
    return RoutingReport(decision=decision, service_codes=(code,))


def _validated_request(request: ProviderRoutingRequest) -> ProviderRoutingRequest | None:
    if type(request) is not ProviderRoutingRequest:
        return None
    try:
        # Revalidate nested values as well; no unchecked model_copy trust.
        return ProviderRoutingRequest.model_validate(request.model_dump(mode="python", warnings=False))
    except Exception:
        return None


def _snapshot_candidates(snapshot, node):
    if type(snapshot) is not ProviderRuntimeSnapshot:
        return ServiceCode.SNAPSHOT_INVALID, (), ()
    if snapshot.version != "2.1A-snapshot-1":
        return ServiceCode.SNAPSHOT_VERSION_UNSUPPORTED, (), ()
    if type(snapshot.items) is not tuple:
        return ServiceCode.SNAPSHOT_INVALID, (), ()
    if len(snapshot.items) > MAX_SOURCE_ITEMS:
        return ServiceCode.SNAPSHOT_LIMIT_EXCEEDED, (), ()
    candidates = []
    counts = {}
    keys = set()
    for item in snapshot.items:
        if type(item) is not SnapshotItem or type(item.source_key) is not str:
            return ServiceCode.SNAPSHOT_INVALID, (), ()
        if item.source_key in keys or (item.candidate is None) == (item.rejection is None):
            return ServiceCode.SNAPSHOT_INVALID, (), ()
        keys.add(item.source_key)
        if item.rejection is not None:
            rejection = item.rejection
            if (type(rejection) is not SnapshotRejection
                    or type(rejection.code) is not SnapshotRejectionCode
                    or rejection.source_key != item.source_key):
                return ServiceCode.SNAPSHOT_INVALID, (), ()
            counts[rejection.code] = counts.get(rejection.code, 0) + 1
            continue
        if type(item.candidate) is not CandidateDescriptor:
            return ServiceCode.SNAPSHOT_INVALID, (), ()
        try:
            candidate = CandidateDescriptor.model_validate(item.candidate.model_dump(mode="python", warnings=False))
        except Exception:
            return ServiceCode.SNAPSHOT_INVALID, (), ()
        if candidate.identity.node != node:
            return ServiceCode.SNAPSHOT_NODE_MISMATCH, (), ()
        # This version consumes only the current bridge's local, non-authorizing
        # profile. New authorities require a separately reviewed integration.
        if (candidate.location is not Location.DEVICE
                or candidate.owner_user_id is not None or candidate.workspace_id is not None
                or candidate.trusted or candidate.self_hosted
                or candidate.availability.authorized or candidate.availability.compatible
                or candidate.credential is not None
                or candidate.estimated_cost_microusd is not None
                or candidate.estimated_latency_ms is not None or candidate.quality_score is not None):
            return ServiceCode.SNAPSHOT_PROFILE_UNSUPPORTED, (), ()
        candidates.append(candidate)
    rejections = tuple(RejectionCount(code=code, count=counts[code])
                       for code in sorted(counts, key=lambda value: value.value))
    return None, tuple(candidates), rejections


def _route_with_owners(request: ProviderRoutingRequest, owners) -> RoutingReport:
    """Private test/Host seam. Never expose owners or facts as request fields."""
    request = _validated_request(request)
    if request is None:
        return _empty_report(None, ServiceCode.INVALID_REQUEST)
    # Budget limits are preferences. Approval claims are authority and there is
    # no Host approval owner in this phase, even though the pure contract has them.
    if request.budget.approvals:
        return _empty_report(request, ServiceCode.REQUEST_AUTHORITY_UNSUPPORTED)
    try:
        runtime = owners.runtime
        center = owners.model_center_service
        identity = runtime.execution_node_identity
        node = ExecutionNodeIdentity(execution_node_id=validate_uuid(
            identity.store.get("execution_node", "local"), field="execution_node_id",
        ))
    except Exception:
        return _empty_report(request, ServiceCode.NODE_ID_UNAVAILABLE)
    if request.local_node != node:
        return _empty_report(request, ServiceCode.REQUEST_NODE_MISMATCH)
    try:
        snapshot = build_provider_runtime_snapshot(
            runtime.provider_registry, runtime.model_registry, center, identity,
        )
    except Exception:
        return _empty_report(request, ServiceCode.SNAPSHOT_SOURCE_FAILED)
    code, candidates, rejections = _snapshot_candidates(snapshot, node)
    if code is not None:
        return _empty_report(request, code)
    hardware = ()
    codes = ()
    status = HardwareStatus.UNAVAILABLE
    try:
        raw = collect_host_hardware_snapshot(identity, center)
        if type(raw) is not HardwareSnapshot:
            raise ValueError("invalid hardware contract")
        fact = HardwareSnapshot.model_validate(raw.model_dump(mode="python", warnings=False))
        if fact.node != node:
            codes = (ServiceCode.HARDWARE_NODE_MISMATCH,)
        else:
            hardware = (fact,)
            status = HardwareStatus.AVAILABLE
    except HostHardwareInventoryError as exc:
        try:
            status = HardwareStatus(exc.code)
            if status in (HardwareStatus.AVAILABLE, HardwareStatus.NOT_COLLECTED):
                status = HardwareStatus.UNAVAILABLE
        except (ValueError, TypeError):
            status = HardwareStatus.UNAVAILABLE
        codes = (ServiceCode.HARDWARE_SOURCE_FAILED,)
    except (ValueError, TypeError):
        codes = (ServiceCode.HARDWARE_INVALID,)
    except Exception:
        codes = (ServiceCode.HARDWARE_SOURCE_FAILED,)
    return RoutingReport(
        decision=evaluate_routing(request, candidates, credentials=(), hardware=hardware),
        service_codes=codes, snapshot_complete=True,
        source_item_count=len(snapshot.items), candidate_count=len(candidates),
        rejection_count=sum(item.count for item in rejections), source_rejections=rejections,
        hardware_status=status,
    )


def route_provider_request(request: ProviderRoutingRequest) -> RoutingReport:
    """Internal production entrypoint, after Host startup; never starts the Host.

    No caller-controlled owner, candidate, hardware, credential, trust or approval
    injection. No API/frontend/generation-router wiring is installed by this module.
    """
    validated = _validated_request(request)
    if validated is None:
        return _empty_report(None, ServiceCode.INVALID_REQUEST)
    owners = sys.modules.get(f"{__package__}.dependencies")
    if owners is None:
        return _empty_report(validated, ServiceCode.HOST_NOT_INITIALIZED)
    return _route_with_owners(validated, owners)

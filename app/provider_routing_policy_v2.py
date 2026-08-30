"""Pure routing over trusted, normalized snapshots. Does not execute decisions."""
from app.provider_runtime_v2_contracts import (
    CandidateDescriptor, CredentialAvailability, CredentialScope,
    Decision, HardwareSnapshot, Location, Preference, PrivacyPolicy,
    ProviderRoutingDecision, ProviderRoutingRequest, ReasonCode,
)

_LOCATION_ORDER = {Location.DEVICE: 0, Location.SAME_USER_NODE: 1,
                   Location.WORKSPACE_NODE: 2, Location.CLOUD: 3}


def _location_allowed(request, candidate):
    location = candidate.location
    if location not in request.candidate_locations:
        return False
    same_device = candidate.identity.node == request.local_node
    if (location == Location.DEVICE) != same_device:
        return False
    if location == Location.DEVICE and candidate.owner_user_id != request.user_id:
        return False
    if location == Location.SAME_USER_NODE and not (
        candidate.trusted and candidate.owner_user_id == request.user_id
    ):
        return False
    if location == Location.WORKSPACE_NODE and not (
        candidate.trusted and candidate.workspace_id == request.workspace_id
    ):
        return False
    if location == Location.CLOUD and candidate.self_hosted:
        return False
    if request.privacy == PrivacyPolicy.DEVICE_ONLY:
        return location == Location.DEVICE
    if request.privacy == PrivacyPolicy.SELF_HOSTED_ONLY:
        return location != Location.CLOUD and candidate.self_hosted
    if request.privacy == PrivacyPolicy.TRUSTED_WORKSPACE_NODES:
        return location != Location.CLOUD
    return request.privacy == PrivacyPolicy.CLOUD_ALLOWED


def _credential_allowed(request, candidate, credentials):
    ref = candidate.credential
    if ref is None:
        return True
    expected = {CredentialScope.SYSTEM: None,
                CredentialScope.WORKSPACE: request.workspace_id,
                CredentialScope.USER: request.user_id,
                CredentialScope.EXECUTION_NODE: candidate.identity.node.execution_node_id}
    if ref.scope_id != expected[ref.scope]:
        return False
    return any(f.reference == ref and f.provider == candidate.identity.provider
               and f.available and f.authorized for f in credentials)


def _capable(request, candidate, hardware):
    cap, need = candidate.capabilities, request.required
    if request.modality not in cap.supported_modalities:
        return False
    if not need.input_asset_types <= cap.input_asset_types or not need.output_asset_types <= cap.output_asset_types:
        return False
    if (need.streaming and not cap.streaming) or (need.batch and not cap.batch):
        return False
    for required, maximum in ((need.context_tokens, cap.max_context_tokens),
                              (need.output_tokens, cap.max_output_tokens)):
        if required is not None and (maximum is None or required > maximum):
            return False
    # Hosted APIs expose compatibility via availability; local client hardware is irrelevant.
    if candidate.location == Location.CLOUD:
        return True
    facts = next((h for h in hardware if h.node == candidate.identity.node), None)
    req = cap.requirements
    return facts is not None and (
        facts.architecture_id == req.architecture_id
        and req.runtime_family_id in facts.runtime_family_ids
        and (req.gpu_vendor_id is None or facts.gpu_vendor_id == req.gpu_vendor_id)
        and facts.vram_mib >= max(req.minimum_vram_mib, cap.estimated_vram_mib or 0)
        and facts.ram_mib >= max(req.minimum_ram_mib, cap.estimated_ram_mib or 0)
    )


def _approved(request: ProviderRoutingRequest, candidate: CandidateDescriptor):
    return any(a.identity == candidate.identity and a.user_id == request.user_id
               and a.workspace_id == request.workspace_id
               and a.maximum_cost_microusd >= candidate.estimated_cost_microusd
               for a in request.budget.approvals)


def _rank(request, candidate):
    metrics = {Preference.COST: candidate.estimated_cost_microusd,
               Preference.LATENCY: candidate.estimated_latency_ms,
               Preference.QUALITY: -candidate.quality_score if candidate.quality_score is not None else None}
    ordered = tuple((metrics[p] is None, metrics[p] or 0) for p in request.preferences)
    identity = candidate.identity
    return (_LOCATION_ORDER[candidate.location], ordered,
            identity.provider.provider_id.int, identity.model.model_id.int,
            identity.runtime.runtime_id.int, identity.node.execution_node_id.int)


def evaluate_routing(
    request: ProviderRoutingRequest,
    candidates: tuple[CandidateDescriptor, ...],
    credentials: tuple[CredentialAvailability, ...] = (),
    hardware: tuple[HardwareSnapshot, ...] = (),
) -> ProviderRoutingDecision:
    """No I/O, clocks, environment, credential resolution or hidden mutable state.

    Inputs are authoritative snapshots, not untrusted client authorization claims.
    Duplicate identity facts fail closed rather than depend on input order.
    """
    groups = ((c.identity for c in candidates), (h.node for h in hardware),
              ((c.reference.handle, c.provider) for c in credentials))
    for group in groups:
        values = tuple(group)
        if len(values) != len(set(values)):
            return ProviderRoutingDecision(decision=Decision.DENY, reason_code=ReasonCode.CONFLICTING_FACTS)
    eligible = []
    pending = []
    for candidate in candidates:
        state = candidate.availability
        if not (state.configured and state.installed and state.healthy and state.reachable
                and state.authorized and state.compatible):
            continue
        if not _location_allowed(request, candidate) or not _credential_allowed(request, candidate, credentials):
            continue
        if not _capable(request, candidate, hardware):
            continue
        cost = candidate.estimated_cost_microusd
        if cost is None or cost > request.budget.maximum_cost_microusd:
            continue
        if candidate.location == Location.CLOUD and cost > 0 and not _approved(request, candidate):
            pending.append(candidate)
        else:
            eligible.append(candidate)
    pool = eligible or pending
    if not pool:
        return ProviderRoutingDecision(
            decision=Decision.NO_COMPATIBLE_ROUTE,
            reason_code=ReasonCode.NO_ELIGIBLE_CANDIDATE if candidates else ReasonCode.NO_CANDIDATES,
        )
    chosen = min(pool, key=lambda c: _rank(request, c))
    allowed = bool(eligible)
    return ProviderRoutingDecision(
        decision=Decision.ALLOW if allowed else Decision.REQUIRES_APPROVAL,
        identity=chosen.identity,
        credential_handle=chosen.credential.handle if allowed and chosen.credential else None,
        reason_code=ReasonCode.SELECTED if allowed else ReasonCode.CLOUD_COST_APPROVAL,
    )

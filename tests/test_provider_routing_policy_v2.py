from itertools import permutations
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.provider_runtime_v2_contracts import *
from app.provider_routing_policy_v2 import evaluate_routing


@pytest.fixture(autouse=True)
def restore_global_settings():
    """Contract tests intentionally do not initialize app runtime or Vault."""
    yield


def uid(n):
    return UUID(int=n)


def change(value, **updates):
    return type(value).model_validate({**dict(value), **updates})


def scenario(location=Location.DEVICE, cost=0, index=1):
    node = ExecutionNodeIdentity(execution_node_id=uid(index))
    identity = RouteIdentity(provider=ProviderIdentity(provider_id=uid(index)),
                             model=ModelIdentity(model_id=uid(index)),
                             runtime=RuntimeIdentity(runtime_id=uid(index)), node=node)
    request = ProviderRoutingRequest(modality=Modality.TEXT, workspace_id=uid(100), user_id=uid(101),
        local_node=ExecutionNodeIdentity(execution_node_id=uid(1)), privacy=PrivacyPolicy.CLOUD_ALLOWED,
        candidate_locations=frozenset(Location), budget=BudgetPolicy(maximum_cost_microusd=100))
    candidate = CandidateDescriptor(identity=identity, location=location, owner_user_id=uid(101),
        workspace_id=uid(100), trusted=True, self_hosted=location != Location.CLOUD,
        availability=Availability(**{k: True for k in Availability.model_fields}),
        capabilities=CapabilityDescriptor(supported_modalities=frozenset({Modality.TEXT}),
            input_asset_types=frozenset({AssetType.TEXT}), output_asset_types=frozenset({AssetType.TEXT}),
            requirements=RuntimeRequirements(runtime_family_id=uid(200), architecture_id=uid(201),
                minimum_vram_mib=4096, minimum_ram_mib=8192)), estimated_cost_microusd=cost)
    hardware = HardwareSnapshot(node=node, architecture_id=uid(201), vram_mib=8192, ram_mib=16384,
                                runtime_family_ids=frozenset({uid(200)}))
    return request, candidate, hardware


@pytest.mark.parametrize('privacy', [PrivacyPolicy.DEVICE_ONLY, PrivacyPolicy.SELF_HOSTED_ONLY,
                                      PrivacyPolicy.TRUSTED_WORKSPACE_NODES])
def test_cloud_never_broadens_privacy(privacy):
    r, c, h = scenario(Location.CLOUD, index=2)
    assert evaluate_routing(change(r, privacy=privacy), (c,), hardware=(h,)).decision == Decision.NO_COMPATIBLE_ROUTE


def test_paid_cloud_requires_scoped_approval():
    r, c, h = scenario(Location.CLOUD, cost=50, index=2)
    assert evaluate_routing(r, (c,)).decision == Decision.REQUIRES_APPROVAL
    approval = CloudApproval(identity=c.identity, user_id=r.user_id, workspace_id=r.workspace_id,
                             maximum_cost_microusd=50)
    for bad in (change(approval, user_id=uid(900)), change(approval, workspace_id=uid(900)),
                change(approval, maximum_cost_microusd=49),
                change(approval, identity=scenario()[1].identity)):
        req = change(r, budget=BudgetPolicy(maximum_cost_microusd=100, approvals=(bad,)))
        assert evaluate_routing(req, (c,)).decision == Decision.REQUIRES_APPROVAL
    r = change(r, budget=BudgetPolicy(maximum_cost_microusd=100, approvals=(approval,)))
    assert evaluate_routing(r, (c,)).decision == Decision.ALLOW
    assert evaluate_routing(change(r, budget=BudgetPolicy(maximum_cost_microusd=49, approvals=(approval,))), (c,)).decision == Decision.NO_COMPATIBLE_ROUTE


@pytest.mark.parametrize('state', list(Availability.model_fields))
def test_availability_dimensions_independently_exclude(state):
    r, c, h = scenario()
    c = change(c, availability=change(c.availability, **{state: False}))
    assert evaluate_routing(r, (c,), hardware=(h,)).decision == Decision.NO_COMPATIBLE_ROUTE


@pytest.mark.parametrize('scope', list(CredentialScope))
def test_credential_scope_provider_and_availability(scope):
    r, c, h = scenario()
    scope_id = {CredentialScope.SYSTEM: None, CredentialScope.WORKSPACE: r.workspace_id,
                CredentialScope.USER: r.user_id, CredentialScope.EXECUTION_NODE: h.node.execution_node_id}[scope]
    ref = CredentialReference(handle=uid(400), scope=scope, scope_id=scope_id)
    c = change(c, credential=ref)
    fact = CredentialAvailability(reference=ref, provider=c.identity.provider, available=True, authorized=True)
    for facts in ((), (change(fact, available=False),), (change(fact, authorized=False),),
                  (change(fact, provider=ProviderIdentity(provider_id=uid(999))),)):
        assert evaluate_routing(r, (c,), facts, (h,)).decision == Decision.NO_COMPATIBLE_ROUTE
    result = evaluate_routing(r, (c,), (fact,), (h,))
    assert result.decision == Decision.ALLOW and result.credential_handle == ref.handle
    if scope_id is not None:
        bad_ref = change(ref, scope_id=uid(999))
        assert evaluate_routing(r, (change(c, credential=bad_ref),),
            (change(fact, reference=bad_ref),), (h,)).decision == Decision.NO_COMPATIBLE_ROUTE


@pytest.mark.parametrize('changes', [dict(vram_mib=4095), dict(ram_mib=8191),
    dict(architecture_id=UUID(int=900)), dict(runtime_family_ids=frozenset())])
def test_incompatible_hardware(changes):
    r, c, h = scenario()
    assert evaluate_routing(r, (c,), hardware=(change(h, **changes),)).decision == Decision.NO_COMPATIBLE_ROUTE


def test_missing_hardware_wrong_modality_and_requirements():
    r, c, h = scenario()
    assert evaluate_routing(r, (c,)).decision == Decision.NO_COMPATIBLE_ROUTE
    for modality in set(Modality) - {Modality.TEXT}:
        assert evaluate_routing(change(r, modality=modality), (c,), hardware=(h,)).decision == Decision.NO_COMPATIBLE_ROUTE
    for need in (RequiredCapabilities(streaming=True), RequiredCapabilities(batch=True),
                 RequiredCapabilities(context_tokens=10), RequiredCapabilities(output_tokens=10),
                 RequiredCapabilities(input_asset_types=frozenset({AssetType.IMAGE})),
                 RequiredCapabilities(output_asset_types=frozenset({AssetType.AUDIO}))):
        assert evaluate_routing(change(r, required=need), (c,), hardware=(h,)).decision == Decision.NO_COMPATIBLE_ROUTE


def test_no_candidates_and_conflicting_facts():
    r, c, h = scenario()
    assert evaluate_routing(r, ()).reason_code == ReasonCode.NO_CANDIDATES
    assert evaluate_routing(r, (c, c), hardware=(h,)).decision == Decision.DENY
    assert evaluate_routing(r, (c,), hardware=(h, h)).decision == Decision.DENY


def test_deterministic_order_and_location_priority():
    r, local, h1 = scenario()
    _, same, h2 = scenario(Location.SAME_USER_NODE, index=2)
    _, team, h3 = scenario(Location.WORKSPACE_NODE, index=3)
    _, cloud, _ = scenario(Location.CLOUD, index=4)
    expected = evaluate_routing(r, (local, same, team, cloud), hardware=(h1, h2, h3))
    for order in permutations((local, same, team, cloud)):
        assert evaluate_routing(r, order, hardware=(h3, h1, h2)) == expected
        assert evaluate_routing(r, order, hardware=(h3, h1, h2)) == expected
    assert expected.identity == local.identity
    assert evaluate_routing(r, (same, team, cloud), hardware=(h2, h3)).identity == same.identity
    assert evaluate_routing(r, (team, cloud), hardware=(h3,)).identity == team.identity
    assert evaluate_routing(change(r, privacy=PrivacyPolicy.DEVICE_ONLY), (same, cloud), hardware=(h2,)).decision == Decision.NO_COMPATIBLE_ROUTE


@pytest.mark.parametrize('preference,selected', [(Preference.COST, 2), (Preference.LATENCY, 3), (Preference.QUALITY, 3)])
def test_explicit_preference(preference, selected):
    r, a, ha = scenario(Location.SAME_USER_NODE, cost=1, index=2)
    _, b, hb = scenario(Location.SAME_USER_NODE, cost=2, index=3)
    a = change(a, estimated_latency_ms=100, quality_score=10)
    b = change(b, estimated_latency_ms=10, quality_score=90)
    r = change(r, preferences=(preference,))
    result = evaluate_routing(r, (b, a), hardware=(ha, hb))
    assert result.identity.node.execution_node_id == uid(selected)


@pytest.mark.parametrize('update', [dict(trusted=False), dict(owner_user_id=UUID(int=900))])
def test_same_user_trust(update):
    r, c, h = scenario(Location.SAME_USER_NODE, index=2)
    assert evaluate_routing(r, (change(c, **update),), hardware=(h,)).decision == Decision.NO_COMPATIBLE_ROUTE


def test_workspace_and_location_spoofing_unknown_cost():
    r, c, h = scenario(Location.WORKSPACE_NODE, index=2)
    for bad in (change(c, trusted=False), change(c, workspace_id=uid(900)),
                change(c, location=Location.DEVICE), change(c, estimated_cost_microusd=None)):
        assert evaluate_routing(r, (bad,), hardware=(h,)).decision == Decision.NO_COMPATIBLE_ROUTE
    assert evaluate_routing(change(r, candidate_locations=frozenset()), (c,), hardware=(h,)).decision == Decision.NO_COMPATIBLE_ROUTE


def test_evaluator_no_io(monkeypatch):
    import builtins
    import io
    import os
    import pathlib
    import socket
    import subprocess
    r, c, h = scenario()
    def forbidden(*args, **kwargs):
        raise AssertionError('routing attempted I/O')
    with monkeypatch.context() as patch:
        for obj, name in ((builtins, 'open'), (io, 'open'), (os, 'open'), (os, 'system'),
                          (pathlib.Path, 'open'), (socket, 'socket'), (socket, 'create_connection'),
                          (subprocess, 'Popen'), (subprocess, 'run')):
            patch.setattr(obj, name, forbidden)
        assert evaluate_routing(r, (c,), hardware=(h,)).decision == Decision.ALLOW
        assert evaluate_routing(r, ()).decision == Decision.NO_COMPATIBLE_ROUTE
        cloud_r, cloud, _ = scenario(Location.CLOUD, cost=50, index=2)
        assert evaluate_routing(cloud_r, (cloud,)).decision == Decision.REQUIRES_APPROVAL


@pytest.mark.parametrize('modality', list(Modality))
def test_each_modality_is_explicitly_routable(modality):
    r, c, h = scenario()
    c = change(c, capabilities=change(c.capabilities, supported_modalities=frozenset({modality})))
    r = change(r, modality=modality)
    assert evaluate_routing(r, (c,), hardware=(h,)).decision == Decision.ALLOW
    assert ProviderRoutingRequest.model_validate_json(r.model_dump_json()) == r
    with pytest.raises(ValidationError):
        r.preferences = ()


def test_tie_break_unknown_metrics_and_approved_pool_priority():
    r, a, ha = scenario(Location.SAME_USER_NODE, index=2)
    _, b, hb = scenario(Location.SAME_USER_NODE, index=3)
    for order in ((a, b), (b, a)):
        assert evaluate_routing(r, order, hardware=(ha, hb)).identity == a.identity
    b = change(b, quality_score=0)
    r = change(r, preferences=(Preference.QUALITY,))
    assert evaluate_routing(r, (a, b), hardware=(ha, hb)).identity == b.identity
    _, pending, _ = scenario(Location.CLOUD, cost=10, index=4)
    _, free, _ = scenario(Location.CLOUD, cost=0, index=5)
    pending = change(pending, quality_score=100)
    assert evaluate_routing(r, (pending, free)).identity == free.identity


def test_capability_limits_gpu_and_memory_estimates():
    r, c, h = scenario()
    cap = change(c.capabilities, streaming=True, batch=True, max_context_tokens=100, max_output_tokens=10)
    c = change(c, capabilities=cap)
    r = change(r, required=RequiredCapabilities(streaming=True, batch=True, context_tokens=100, output_tokens=10))
    assert evaluate_routing(r, (c,), hardware=(h,)).decision == Decision.ALLOW
    assert evaluate_routing(change(r, required=RequiredCapabilities(context_tokens=101)), (c,), hardware=(h,)).decision == Decision.NO_COMPATIBLE_ROUTE
    for bad_cap in (change(cap, estimated_vram_mib=8193), change(cap, estimated_ram_mib=16385),
                    change(cap, requirements=change(cap.requirements, gpu_vendor_id=uid(333)))):
        assert evaluate_routing(r, (change(c, capabilities=bad_cap),), hardware=(h,)).decision == Decision.NO_COMPATIBLE_ROUTE


def test_self_hosted_positive_and_negative_and_duplicate_credentials():
    r, c, h = scenario(Location.SAME_USER_NODE, index=2)
    r = change(r, privacy=PrivacyPolicy.SELF_HOSTED_ONLY)
    assert evaluate_routing(r, (c,), hardware=(h,)).decision == Decision.ALLOW
    assert evaluate_routing(r, (change(c, self_hosted=False),), hardware=(h,)).decision == Decision.NO_COMPATIBLE_ROUTE
    ref = CredentialReference(handle=uid(400), scope=CredentialScope.SYSTEM)
    f = CredentialAvailability(reference=ref, provider=c.identity.provider, available=True, authorized=True)
    assert evaluate_routing(r, (c,), (f, change(f, authorized=False)), (h,)).decision == Decision.DENY

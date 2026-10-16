"""Desktop SDK boundaries: synthetic/contract checks, never real desktop acceptance."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from local_interop_desktop import (
    AttestationState,
    EventProvenance,
    InstallationRecord,
    InteropAudit,
    InteropDiagnosticSnapshot,
    InteropEventSourceRegistry,
    InteropHandoffHandler,
    InteropLifecycleCoordinator,
    InteropModelRegistryCache,
    InteropPeerDiscovery,
    InteropPeerTrustStore,
    InteropTransport,
    MockPeerAttestation,
    PeerOSFacts,
    ProductionPeerAttestation,
    TransportState,
    TrustRecord,
    UserPresenceGate,
)
from local_interop_desktop.testing import (
    SyntheticContextOwner,
    SyntheticDesktopPeer,
    studio_product,
)
from local_interop_protocol import (
    HandoffTarget,
    ModelRegistry,
    ProtocolViolation,
    TransportRequest,
    TutorRequest,
)


class Clock:
    def __init__(self):
        self.now = datetime(2026, 10, 6, 12, tzinfo=timezone.utc)
        self.tick = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += timedelta(seconds=seconds)
        self.tick += seconds


def run(coro):
    return asyncio.run(coro)


def configured(*, clock=None, **kwargs):
    clock = clock or Clock()
    peer = SyntheticDesktopPeer(clock=clock)
    transport = InteropTransport(
        peer,
        studio_product(),
        MockPeerAttestation(),
        enabled=True,
        mock_only=True,
        clock=clock,
        **kwargs,
    )
    return clock, peer, transport


async def connect(transport, peer):
    assert await transport.start()
    return await transport.connect(
        peer.discovered(),
        requested_capabilities=transport.product.capabilities,
        user_identity="local-user",
    )


def request_for(transport, clock, request_id="request-1"):
    return TransportRequest(
        operation="TUTOR",
        payload=TutorRequest(
            request_id=request_id,
            session_id=transport.session.session_id,
            context=SyntheticContextOwner(clock=clock).capsule(),
        ),
    )


def trust_fixture(*, approved=True, require_signature=True):
    clock = Clock()
    peer = SyntheticDesktopPeer(clock=clock)
    facts = replace(
        peer.facts,
        installation_id="install-1",
        registered_product_id=peer.product.product_id,
        publisher_id="publisher-1",
        signature_valid=True,
    )
    installed = InstallationRecord(
        "install-1",
        peer.product.product_id,
        facts.executable_path_hash,
        facts.executable_hash,
        "publisher-1",
        require_signature,
    )
    store = InteropPeerTrustStore()
    record = TrustRecord(
        peer.product.product_id,
        "install-1",
        "TRUSTED_INSTALLATION",
        clock(),
        clock(),
        "1.0+build",
        "1.0",
    )
    if approved:
        store.approve(record, user_approved=True)
    attest = ProductionPeerAttestation(
        current_user_sid=facts.user_sid,
        installations={"install-1": installed},
        trust_store=store,
        clock=clock,
    )
    return clock, peer, facts, installed, store, record, attest


def test_feature_defaults_and_acceptance_mode_never_start_adapter(monkeypatch):
    async def scenario():
        peer = SyntheticDesktopPeer()
        disabled = InteropTransport(peer, studio_product(), MockPeerAttestation(), mock_only=True)
        assert await disabled.start() is False
        assert not peer.started
        _, peer, transport = configured()
        monkeypatch.setenv("V1_ACCEPTANCE_MODE", "true")
        assert await transport.start() is False
        assert not peer.started
        monkeypatch.delenv("V1_ACCEPTANCE_MODE")
        transport.acceptance_mode = True
        assert await transport.start() is False

    run(scenario())


def test_all_five_states_are_independently_observable():
    async def scenario():
        _, peer, transport = configured()
        observed = []
        remove = transport.observe(observed.append)
        session = await connect(transport, peer)
        assert session is transport.session
        states = [snapshot.state for snapshot in observed]
        for state in (
            "STARTING",
            "LISTENING",
            "CONNECTING",
            "HANDSHAKING",
            "AUTHENTICATING",
            "NEGOTIATING",
            "READY",
        ):
            assert state in states
        physical = next(s for s in observed if s.state == "HANDSHAKING")
        assert physical.physically_connected and not physical.handshake_complete
        assert not physical.peer_authenticated and not physical.session_established
        hello = next(s for s in observed if s.state == "AUTHENTICATING")
        assert hello.handshake_complete and not hello.peer_authenticated
        assert any(s.peer_authenticated and not s.capabilities_negotiated for s in observed)
        assert any(s.capabilities_negotiated and not s.session_established for s in observed)
        assert transport.peer_identity().attestation_state == AttestationState.MOCK_ONLY
        assert transport.health().session == "READY"
        assert transport.diagnostic_snapshot().trust_state == "MOCK_ONLY"
        assert [s.revision for s in observed] == sorted({s.revision for s in observed})
        remove()
        await transport.shutdown()
        assert transport.snapshot().state == "STOPPED"
        assert not transport.snapshot().physically_connected

    run(scenario())


def test_mock_and_production_trust_cannot_mix():
    _, peer, _, _, _, _, attest = trust_fixture()
    with pytest.raises(ValueError):
        InteropTransport(peer, studio_product(), attest, enabled=True)
    with pytest.raises(ValueError):
        InteropTransport(peer, studio_product(), MockPeerAttestation(), enabled=True)


@pytest.mark.parametrize(
    "change",
    [
        {"user_sid": "S-1-5-21-9999"},
        {"local_connection": False},
        {"installation_id": "unknown-install"},
        {"registered_product_id": "fake.product"},
        {"executable_path_hash": "c" * 64},
        {"executable_hash": "d" * 64},
        {"publisher_id": "fake-publisher"},
        {"signature_valid": False},
    ],
)
def test_production_attestation_rejects_changed_os_evidence(change):
    _, peer, facts, _, _, _, attest = trust_fixture()
    assert (
        attest.attest(peer.product, facts).attestation_state
        == AttestationState.TRUSTED_INSTALLATION
    )
    assert (
        attest.attest(peer.product, replace(facts, **change)).attestation_state
        == AttestationState.REJECTED
    )


def test_approved_name_and_path_hash_alone_do_not_authenticate():
    _, peer, facts, _, _, _, attest = trust_fixture(approved=False)
    assert attest.attest(peer.product, facts).attestation_state == AttestationState.SIGNED_PRODUCT
    fake = peer.product.model_copy(update={"product_id": "malicious.tutor"})
    assert attest.attest(fake, facts).attestation_state == AttestationState.REJECTED
    path_only = PeerOSFacts(facts.process_id, facts.user_sid, facts.executable_path_hash, "e" * 64)
    assert attest.attest(peer.product, path_only).attestation_state == AttestationState.REJECTED


def test_signature_downgrade_rejected_even_when_unsigned_policy_allowed():
    _, peer, facts, _, _, _, attest = trust_fixture(require_signature=False)
    assert (
        attest.attest(peer.product, replace(facts, signature_valid=False)).attestation_state
        == AttestationState.REJECTED
    )


def test_trust_revocation_and_version_only_upgrade_rules():
    clock, peer, facts, _, store, _, attest = trust_fixture()
    upgraded = peer.product.model_copy(update={"product_version": "2.0+build"})
    clock.advance(3)
    assert attest.attest(upgraded, facts).attestation_state == AttestationState.TRUSTED_INSTALLATION
    record = store.get(upgraded.product_id, "install-1")
    assert record.product_version == "2.0+build" and record.last_verified_time == clock()
    store.revoke(upgraded.product_id, "install-1")
    assert attest.attest(upgraded, facts).attestation_state == AttestationState.SIGNED_PRODUCT


def test_trust_store_persists_exact_allowlist_without_grants_or_content():
    _, _, _, _, store, record, _ = trust_fixture()
    restored = InteropPeerTrustStore.loads(store.dumps())
    assert restored.dumps() == store.dumps()
    assert set(json.loads(store.dumps())[0]) == set(TrustRecord.__dataclass_fields__)
    with pytest.raises(ProtocolViolation):
        restored.approve(record)
    for key in ("session_token", "api_key", "prompt", "manuscript", "standing_grants"):
        rows = json.loads(store.dumps())
        rows[0][key] = "private-value"
        with pytest.raises(ValueError):
            InteropPeerTrustStore.loads(json.dumps(rows))
    with pytest.raises(ValueError):
        InteropPeerTrustStore.loads(
            store.dumps().replace('"revoked":false', '"revoked":false,"revoked":true')
        )
    with pytest.raises(ValueError):
        replace(record, trust_level="MOCK_ONLY")
    with pytest.raises(ValueError):
        replace(record, approved_installation_identity="sk-" + "a" * 24)


def test_discovery_is_registered_bounded_and_does_not_upgrade_trust():
    _, peer, _ = configured()
    seen = []

    def candidates():
        for index in range(1000):
            seen.append(index)
            yield replace(peer.discovered(), instance_id=f"peer-{index}")

    discovery = InteropPeerDiscovery(registered=candidates, limit=3)
    result = discovery.discover()
    assert len(result) == 3 and len(seen) <= 4
    assert all(item.trust_state == AttestationState.MOCK_ONLY for item in result)


def test_broken_protocol_and_tampered_handshake_fail_closed():
    async def scenario():
        _, peer, transport = configured()
        await transport.start()
        with pytest.raises(ProtocolViolation) as error:
            await transport.connect(
                replace(peer.discovered(), protocol_versions=("2.0",)), user_identity="user"
            )
        assert error.value.code == "PROTOCOL_INCOMPATIBLE"
        original = peer.exchange

        async def malicious(message, **kwargs):
            result = await original(message, **kwargs)
            if message.operation == "HELLO":
                return result.model_copy(
                    update={
                        "payload": result.payload.model_copy(update={"session_nonce": "f" * 64})
                    }
                )
            return result

        peer.exchange = malicious
        with pytest.raises(ProtocolViolation):
            await transport.connect(peer.discovered(), user_identity="user")
        assert transport.state == TransportState.FAILED and transport.session is None
        assert not transport.snapshot().physically_connected
        await transport.shutdown()

    run(scenario())


def test_negotiation_never_implies_content_or_request_authorization():
    async def scenario():
        clock, peer, transport = configured()
        await connect(transport, peer)
        request = request_for(transport, clock)
        with pytest.raises(ProtocolViolation) as error:
            await transport.request(request)
        assert error.value.code == "CONTEXT_NOT_AUTHORIZED"
        assert "TUTOR" not in peer.calls
        response = await transport.request(request, authorize=lambda: True)
        assert response.payload.request_id == request.payload.request_id
        with pytest.raises(ProtocolViolation):
            await transport.request(request, authorize=lambda: True)
        await transport.shutdown()

    run(scenario())


@pytest.mark.parametrize("failure", ["project", "version", "permission"])
def test_late_response_rechecks_project_version_and_permission(failure):
    async def scenario():
        clock, peer, transport = configured()
        await connect(transport, peer)
        current = {"project": "A", "version": 37, "permission": True}
        binding = current.copy()
        peer.before_reply = lambda: current.update(
            {failure: False if failure == "permission" else "changed"}
        )
        with pytest.raises(ProtocolViolation) as error:
            await transport.request(
                request_for(transport, clock),
                fresh=lambda: (
                    (current["project"], current["version"])
                    == (binding["project"], binding["version"])
                ),
                authorize=lambda: current["permission"],
            )
        assert error.value.code == (
            "CONTEXT_NOT_AUTHORIZED" if failure == "permission" else "SOURCE_CHANGED"
        )
        await transport.shutdown()

    run(scenario())


def test_disconnect_cancels_old_request_and_reconnect_has_no_old_grants():
    async def scenario():
        clock, peer, transport = configured()
        old_session = await connect(transport, peer)
        transport.events.register("TASK")
        sid = transport.subscribe(authorize=lambda _: True)
        peer.wait_before_reply = asyncio.Event()
        task = asyncio.create_task(
            transport.request(request_for(transport, clock), authorize=lambda: True)
        )
        for _ in range(15):
            await asyncio.sleep(0)
            if "TUTOR" in peer.calls:
                break
        await transport.disconnect()
        with pytest.raises(ProtocolViolation) as error:
            await task
        assert error.value.code == "CANCELLED"
        peer.wait_before_reply.set()
        peer.wait_before_reply = None
        new_session = await transport.connect(
            peer.discovered(),
            requested_capabilities=transport.product.capabilities,
            user_identity="local-user",
        )
        assert old_session.session_id != new_session.session_id
        assert transport.events.drain(sid) == ()
        response = await transport.request(
            request_for(transport, clock, "new-request"), authorize=lambda: True
        )
        assert response.payload.session_id == new_session.session_id
        await transport.shutdown()

    run(scenario())


def test_expired_session_invalidates_events_and_requests():
    async def scenario():
        clock, peer, transport = configured()
        await connect(transport, peer)
        request = request_for(transport, clock)
        clock.advance(61)
        with pytest.raises(ProtocolViolation) as error:
            await transport.request(request, authorize=lambda: True)
        assert error.value.code == "SESSION_REQUIRED"
        assert transport.session is None and transport.state == "DEGRADED"
        await transport.shutdown()

    run(scenario())


def test_cancel_and_request_deadline_are_bounded():
    async def scenario():
        clock, peer, transport = configured()
        await connect(transport, peer)
        peer.wait_before_reply = asyncio.Event()
        task = asyncio.create_task(
            transport.request(request_for(transport, clock), authorize=lambda: True)
        )
        for _ in range(10):
            await asyncio.sleep(0)
            if "TUTOR" in peer.calls:
                break
        assert transport.cancel("request-1")
        assert not transport.cancel("request-1")
        with pytest.raises(ProtocolViolation) as error:
            await task
        assert error.value.code == "CANCELLED"
        start = asyncio.get_running_loop().time()
        with pytest.raises(ProtocolViolation) as error:
            await transport.request(
                request_for(transport, clock, "timeout-request"),
                timeout=0.01,
                authorize=lambda: True,
            )
        assert error.value.code == "TIMEOUT"
        assert asyncio.get_running_loop().time() - start < 0.15
        peer.wait_before_reply.set()
        await transport.shutdown()

    run(scenario())


def test_response_request_binding_is_checked():
    async def scenario():
        clock, peer, transport = configured()
        await connect(transport, peer)
        original = peer.exchange

        async def wrong_id(request, **kwargs):
            result = await original(request, **kwargs)
            return result.model_copy(
                update={
                    "payload": result.payload.model_copy(update={"request_id": "wrong-request"})
                }
            )

        peer.exchange = wrong_id
        with pytest.raises(ProtocolViolation) as error:
            await transport.request(request_for(transport, clock), authorize=lambda: True)
        assert error.value.code == "INVALID_MESSAGE"
        await transport.shutdown()

    run(scenario())


def test_event_revocation_does_not_disable_another_peer():
    clock = Clock()
    capsule = SyntheticContextOwner(clock=clock).capsule()
    registry = InteropEventSourceRegistry(clock=clock)
    registry.register("TASK")
    a = registry.subscribe(
        session_id="session-a",
        peer_id="peer-a",
        expires_at=clock() + timedelta(seconds=30),
        authorize=lambda _: True,
    )
    b = registry.subscribe(
        session_id="session-b",
        peer_id="peer-b",
        expires_at=clock() + timedelta(seconds=30),
        authorize=lambda _: True,
    )
    assert registry.publish("TASK", "TASK_UPDATED", capsule) == 2
    assert len(registry.drain(a)) == 1
    registry.revoke(a)
    registry.publish("TASK", "TASK_UPDATED", capsule)
    assert registry.drain(a) == ()
    delivery = registry.drain(b)
    assert len(delivery) == 1 and delivery[0].event.session_id == "session-b"
    assert delivery[0].provenance == EventProvenance.DIRECT_EVENT


def test_event_authority_rechecked_on_delivery_and_pause_drops_queued_content():
    clock = Clock()
    capsule = SyntheticContextOwner(clock=clock).capsule()
    registry = InteropEventSourceRegistry(clock=clock)
    registry.register("TASK")
    allowed = [True]
    sid = registry.subscribe(
        session_id="session",
        peer_id="peer",
        expires_at=clock() + timedelta(seconds=30),
        authorize=lambda _: allowed[0],
    )
    registry.publish("TASK", "TASK_UPDATED", capsule)
    allowed[0] = False
    assert registry.drain(sid) == ()
    allowed[0] = True
    registry.publish("TASK", "TASK_UPDATED", capsule)
    registry.pause(sid)
    registry.resume(sid)
    assert registry.drain(sid) == ()
    registry.publish("TASK", "TASK_UPDATED", capsule)
    clock.advance(31)
    assert registry.drain(sid) == ()


def test_event_metadata_only_and_synthetic_provenance_are_fail_closed():
    clock = Clock()
    owner = SyntheticContextOwner(clock=clock)
    registry = InteropEventSourceRegistry(clock=clock)
    registry.register("CHAPTER")
    with pytest.raises(ProtocolViolation) as error:
        registry.publish(
            "CHAPTER", "CHAPTER_OPENED", owner.capsule(level="CURRENT_CHAPTER", approved=True)
        )
    assert error.value.code == "CONTEXT_NOT_AUTHORIZED"
    with pytest.raises(ValueError):
        registry.register("MODEL", provenance=EventProvenance.SYNTHETIC)
    with pytest.raises(ValueError):
        registry.register("TASK", poll=lambda: (), provenance=EventProvenance.DIRECT_EVENT)


def test_event_queue_coalesces_and_is_bounded():
    clock = Clock()
    owner = SyntheticContextOwner(clock=clock)
    registry = InteropEventSourceRegistry(clock=clock, queue_limit=2)
    registry.register("TASK")
    sid = registry.subscribe(
        session_id="session",
        peer_id="peer",
        expires_at=clock() + timedelta(seconds=30),
        authorize=lambda _: True,
    )
    for _ in range(100):
        registry.publish("TASK", "TASK_UPDATED", owner.capsule())
    assert len(registry.drain(sid)) == 1
    for kind in ("TASK_STARTED", "TASK_UPDATED", "TASK_COMPLETED"):
        registry.publish("TASK", kind, owner.capsule())
    assert len(registry.drain(sid)) == 2


def test_polling_is_idle_backed_off_and_disabled_without_subscribers():
    clock = Clock()
    calls = []
    registry = InteropEventSourceRegistry(
        clock=clock, monotonic=lambda: clock.tick, poll_interval=1, max_idle_interval=8
    )
    registry.register("MODEL", poll=lambda: calls.append(clock.tick) or ())
    registry.poll_due()
    assert calls == []
    sid = registry.subscribe(
        session_id="session",
        peer_id="peer",
        expires_at=clock() + timedelta(seconds=60),
        authorize=lambda _: True,
    )
    registry.poll_due()
    assert calls == [0]
    for _ in range(10):
        registry.poll_due()
    assert calls == [0]
    clock.advance(2)
    registry.poll_due()
    assert calls == [0, 2]
    assert registry.describe()[0]["provenance"] == "POLLING"
    assert registry.describe()[0]["poll_interval_seconds"] == 4
    registry.revoke(sid)
    clock.advance(10)
    registry.poll_due()
    assert calls == [0, 2]


def test_bad_subscriber_callback_does_not_stop_good_subscriber():
    clock = Clock()
    registry = InteropEventSourceRegistry(clock=clock)
    registry.register("TASK")

    def broken(_):
        raise RuntimeError("private error content")

    a = registry.subscribe(
        session_id="a",
        peer_id="a",
        expires_at=clock() + timedelta(seconds=30),
        authorize=lambda _: True,
        callback=broken,
    )
    b = registry.subscribe(
        session_id="b",
        peer_id="b",
        expires_at=clock() + timedelta(seconds=30),
        authorize=lambda _: True,
    )
    registry.publish("TASK", "TASK_UPDATED", SyntheticContextOwner(clock=clock).capsule())
    assert registry.drain(a) == ()
    assert len(registry.drain(b)) == 1


def test_model_registry_cache_has_strict_metadata_and_stale_state():
    clock = Clock()

    class Provider:
        def snapshot(self):
            return ModelRegistry(created_at=clock())

    provider = Provider()
    cache = InteropModelRegistryCache(provider, clock=clock, ttl_seconds=10)
    assert cache.snapshot().state == "UNAVAILABLE"
    cache.refresh()
    assert cache.snapshot().state == "READY"
    clock.advance(10)
    assert cache.snapshot().state == "STALE"
    provider.snapshot = lambda: {
        "protocol_name": "PoemSeed Local Interop",
        "protocol_version": "1.0",
        "created_at": clock().isoformat(),
        "models": [],
        "api_key": "secret",
    }
    with pytest.raises(ProtocolViolation):
        cache.refresh()
    assert cache.snapshot().state == "STALE"


def test_handoff_presence_binds_full_product_version_parent_and_session():
    clock = Clock()
    gate = UserPresenceGate(clock=clock)
    opened = []
    handler = InteropHandoffHandler(gate, resolve=lambda _: True, open_target=opened.append)
    target = HandoffTarget(
        action="OPEN_TASK",
        target_product_id="poemseed.creative.studio",
        task_id="task-1",
        project_id="project-1",
        source_version="37",
    )
    for update, session in [
        ({"source_version": "38"}, "session-a"),
        ({"target_product_id": "malicious.product"}, "session-a"),
        ({"project_id": "project-2"}, "session-a"),
        ({}, "session-b"),
    ]:
        proof = gate.issue_target(target, session_id="session-a")
        with pytest.raises(ProtocolViolation):
            handler.open(
                target.model_copy(update=update), user_presence_token=proof, session_id=session
            )
    assert opened == []
    proof = gate.issue_target(target, session_id="session-a")
    handler.open(target, user_presence_token=proof, session_id="session-a")
    assert opened == [target]
    with pytest.raises(ProtocolViolation):
        handler.open(target, user_presence_token=proof, session_id="session-a")


def test_handoff_expiry_and_no_automatic_response_action():
    clock = Clock()
    gate = UserPresenceGate(clock=clock)
    opened = []
    handler = InteropHandoffHandler(gate, resolve=lambda _: True, open_target=opened.append)
    target = HandoffTarget(
        action="OPEN_FEATURE", target_product_id="poemseed.creative.studio", feature="settings"
    )
    with pytest.raises(ProtocolViolation):
        handler.open(target, user_presence_token="peer-claims-click")
    proof = gate.issue_target(target, ttl_seconds=1)
    clock.advance(1)
    with pytest.raises(ProtocolViolation):
        handler.open(target, user_presence_token=proof)
    assert opened == []


def test_audit_and_diagnostics_allow_only_bounded_noncontent_fields():
    audit = InteropAudit(limit=2)
    for _ in range(3):
        audit.record("TUTOR", decision="ALLOW")
    assert len(audit.snapshot()) == 2
    with pytest.raises(ValueError):
        audit.record("private manuscript")
    with pytest.raises(ValueError):
        audit.record("TUTOR", error_code="private path /home/person")
    with pytest.raises(ValueError):
        InteropDiagnosticSnapshot("READY", error_codes=("api_key=secret",))
    flushed = []
    audit.flush(flushed.extend)
    assert len(flushed) == 2 and not audit.snapshot()
    assert set(flushed[0]) == {
        "timestamp",
        "operation",
        "peer_product_id",
        "capability",
        "decision",
        "result",
        "error_code",
    }


def test_lifecycle_bridge_failure_never_blocks_app_start():
    async def scenario():
        _, peer, transport = configured()

        async def broken():
            raise RuntimeError("private error")

        peer.start = broken
        lifecycle = InteropLifecycleCoordinator(transport)
        assert await lifecycle.app_start()
        assert await lifecycle.app_ready()
        assert not await lifecycle.bridge_start()
        assert lifecycle.app_is_ready
        assert transport.state == "FAILED"
        await lifecycle.shutdown()

    run(scenario())


def test_restart_generates_new_instance_and_never_restores_session_or_grant():
    async def scenario():
        _, peer, transport = configured()
        await connect(transport, peer)
        old_instance = transport.instance_id
        old_session = transport.session

        def fresh_transport():
            return configured(clock=transport.clock)[2]

        lifecycle = InteropLifecycleCoordinator(transport, restart_factory=fresh_transport)
        assert await lifecycle.restart()
        assert lifecycle.transport.instance_id != old_instance
        assert lifecycle.transport.session is None and transport.session is None
        assert old_session is not lifecycle.transport.session
        await lifecycle.shutdown()

    run(scenario())


def test_shutdown_deadline_survives_uncooperative_async_hook():
    async def scenario():
        _, peer, transport = configured()
        await connect(transport, peer)
        release = asyncio.Event()

        async def stubborn():
            try:
                await release.wait()
            except asyncio.CancelledError:
                await release.wait()

        lifecycle = InteropLifecycleCoordinator(transport, revoke_subscriptions=stubborn)
        started = asyncio.get_running_loop().time()
        report = await lifecycle.shutdown(timeout=0.02)
        assert asyncio.get_running_loop().time() - started < 0.2
        assert "REVOKE_SUBSCRIPTIONS" in report.timed_out
        assert transport.session is None
        release.set()
        await asyncio.sleep(0.01)

    run(scenario())


def test_concurrent_duplicate_request_is_reserved_before_attestation_await():
    async def scenario():
        clock, peer, transport = configured()
        await connect(transport, peer)
        release = asyncio.Event()
        entered = asyncio.Event()
        original = peer.refresh_peer_facts

        async def slow_facts():
            entered.set()
            await release.wait()
            return await original()

        peer.refresh_peer_facts = slow_facts
        request = request_for(transport, clock)
        first = asyncio.create_task(transport.request(request, authorize=lambda: True))
        await entered.wait()
        with pytest.raises(ProtocolViolation) as error:
            await transport.request(request, authorize=lambda: True)
        assert error.value.code == "INVALID_MESSAGE"
        release.set()
        assert (await first).payload.request_id == request.payload.request_id
        await transport.shutdown()

    run(scenario())


def test_request_queue_backpressure_before_sending_more_content():
    async def scenario():
        clock, peer, transport = configured(max_pending=1)
        await connect(transport, peer)
        peer.wait_before_reply = asyncio.Event()
        first = asyncio.create_task(
            transport.request(request_for(transport, clock), authorize=lambda: True)
        )
        for _ in range(20):
            await asyncio.sleep(0)
            if "TUTOR" in peer.calls:
                break
        with pytest.raises(ProtocolViolation) as error:
            await transport.request(request_for(transport, clock, "second"), authorize=lambda: True)
        assert error.value.code == "TRANSPORT_ERROR"
        assert peer.calls.count("TUTOR") == 1
        peer.wait_before_reply.set()
        await first
        await transport.shutdown()

    run(scenario())


def test_timed_out_cancellation_suppressing_adapter_is_bounded_and_fenced():
    async def scenario():
        clock, peer, transport = configured()
        await connect(transport, peer)
        release = asyncio.Event()
        original = peer.exchange

        async def stubborn(request, **kwargs):
            result = await original(request, **kwargs)
            if request.operation == "TUTOR":
                try:
                    await release.wait()
                except asyncio.CancelledError:
                    await release.wait()
            return result

        peer.exchange = stubborn
        started = asyncio.get_running_loop().time()
        with pytest.raises(ProtocolViolation) as error:
            await transport.request(
                request_for(transport, clock), timeout=0.01, authorize=lambda: True
            )
        assert error.value.code == "TIMEOUT"
        assert asyncio.get_running_loop().time() - started < 0.15
        await transport.disconnect()
        old_epoch = transport.snapshot().epoch
        release.set()
        await asyncio.sleep(0.01)
        assert not transport._pending and transport.session is None
        assert transport.snapshot().epoch == old_epoch
        await transport.shutdown()

    run(scenario())


def test_refresh_authority_detects_new_os_facts_and_post_response_trust_downgrade():
    async def scenario():
        clock, peer, facts, _, _, _, attest = trust_fixture()
        peer.facts = facts

        # Explicit test-only OS adapter injection exercises the production policy;
        # this is not real signed binary or Windows evidence.
        class OSBoundaryTestAdapter:
            def __getattr__(self, name):
                if name == "mock_only":
                    return False
                return getattr(peer, name)

        transport = InteropTransport(
            OSBoundaryTestAdapter(), studio_product(), attest, enabled=True, clock=clock
        )
        await connect(transport, peer)
        assert (
            await transport.refresh_authority()
        ).attestation_state == AttestationState.TRUSTED_INSTALLATION
        peer.before_reply = lambda: setattr(peer, "facts", replace(facts, signature_valid=False))
        with pytest.raises(ProtocolViolation) as error:
            await transport.request(request_for(transport, clock), authorize=lambda: True)
        assert error.value.code == "PERMISSION_DENIED"
        assert transport.session is None and transport.state == "DEGRADED"
        await transport.shutdown()

    run(scenario())


def test_enrolled_event_delivery_refreshes_trust_and_rejects_pid_change():
    async def scenario():
        clock, peer, transport = configured()
        await connect(transport, peer)
        transport.events.register("TASK")
        sid = transport.subscribe(authorize=lambda _: True)
        transport.events.publish(
            "TASK", "TASK_UPDATED", SyntheticContextOwner(clock=clock).capsule()
        )
        peer.facts = replace(peer.facts, process_id=456)
        assert await transport.drain_events(sid) == ()
        assert transport.session is None
        await transport.shutdown()

    run(scenario())


def test_subscribe_rejects_no_negotiated_metadata_support():
    async def scenario():
        _, peer, transport = configured()
        await transport.start()
        await transport.connect(peer.discovered(), user_identity="local-user")
        with pytest.raises(ProtocolViolation) as error:
            transport.subscribe(authorize=lambda _: True)
        assert error.value.code == "CAPABILITY_NOT_SUPPORTED"
        await transport.shutdown()

    run(scenario())


def test_scoped_disconnect_and_lifecycle_leave_unrelated_peer_untouched():
    async def scenario():
        _, peer, transport = configured()
        await connect(transport, peer)
        original = transport.session
        lifecycle = InteropLifecycleCoordinator(transport)
        await lifecycle.peer_lost("other.product")
        assert transport.session is original
        await lifecycle.session_revoked(peer.product.product_id)
        assert transport.session is None
        await lifecycle.shutdown()

    run(scenario())


def test_restart_rejects_reused_adapter_to_fence_late_os_closes():
    async def scenario():
        _, peer, transport = configured()
        await connect(transport, peer)
        lifecycle = InteropLifecycleCoordinator(
            transport,
            restart_factory=lambda: InteropTransport(
                peer, studio_product(), MockPeerAttestation(), enabled=True, mock_only=True
            ),
        )
        with pytest.raises(ValueError, match="old adapter"):
            await lifecycle.restart()
        assert transport.session is None

    run(scenario())


def test_expired_capsule_is_never_sent_even_with_host_authorization():
    async def scenario():
        clock, peer, transport = configured()
        peer.ttl = 3600
        await connect(transport, peer)
        request = request_for(transport, clock)
        clock.advance(301)
        with pytest.raises(ProtocolViolation) as error:
            await transport.request(request, authorize=lambda: True)
        assert error.value.code == "CONTEXT_STALE"
        assert "TUTOR" not in peer.calls
        await transport.shutdown()

    run(scenario())


def test_direct_source_unsubscribes_only_at_registry_shutdown():
    clock = Clock()
    handlers = []
    closed = []

    class Source:
        def subscribe(self, callback):
            handlers.append(callback)
            return lambda: closed.append(True)

    registry = InteropEventSourceRegistry(clock=clock)
    registry.register("TASK", source=Source())
    sid = registry.subscribe(
        session_id="session",
        peer_id="peer",
        expires_at=clock() + timedelta(seconds=20),
        authorize=lambda _: True,
    )
    handlers[0]("TASK_UPDATED", SyntheticContextOwner(clock=clock).capsule())
    assert len(registry.drain(sid)) == 1
    registry.revoke(sid)
    assert closed == []
    registry.shutdown()
    assert closed == [True]


def test_two_transports_sharing_registry_revoke_only_their_own_subscriptions():
    async def scenario():
        clock = Clock()
        registry = InteropEventSourceRegistry(clock=clock)
        registry.register("TASK")
        _, peer_a, a = configured(clock=clock, events=registry)
        _, peer_b, b = configured(clock=clock, events=registry)
        await connect(a, peer_a)
        await connect(b, peer_b)
        aid = a.subscribe(authorize=lambda _: True)
        bid = b.subscribe(authorize=lambda _: True)
        capsule = SyntheticContextOwner(clock=clock).capsule()
        registry.publish("TASK", "TASK_UPDATED", capsule)
        assert await a.drain_events(bid) == ()
        a.unsubscribe(bid)
        await a.disconnect()
        assert registry.drain(aid) == ()
        assert len(await b.drain_events(bid)) == 1
        registry.publish("TASK", "TASK_UPDATED", capsule)
        assert len(await b.drain_events(bid)) == 1
        await a.shutdown()
        await b.shutdown()

    run(scenario())


@pytest.mark.parametrize(
    "credential",
    [
        "sk-" + "a" * 20,
        "meta.sk-" + "a" * 20,
        "sk_proj_" + "a" * 20,
        "ghp_" + "a" * 20,
        "github_pat_" + "a" * 20,
        "xoxb-" + "a" * 20,
        "eyJ" + "a" * 8 + "." + "b" * 8 + "." + "c" * 8,
        "api_key:" + "a" * 20,
        "Bearer." + "a" * 20,
    ],
)
def test_secret_shapes_rejected_in_allowlisted_trust_and_audit_fields(credential):
    _, _, _, _, _, record, _ = trust_fixture()
    for field in ("approved_product_identity", "approved_installation_identity", "product_version"):
        with pytest.raises(ValueError):
            replace(record, **{field: credential})
    with pytest.raises(ValueError):
        InteropAudit().record("ATTEST", peer_product_id=credential)


def test_explicit_empty_event_scope_does_not_expand_to_all_modules():
    clock = Clock()
    registry = InteropEventSourceRegistry(clock=clock)
    registry.register("TASK")
    sid = registry.subscribe(
        session_id="s",
        peer_id="p",
        expires_at=clock() + timedelta(seconds=5),
        authorize=lambda _: True,
        modules=(),
    )
    assert (
        registry.publish("TASK", "TASK_UPDATED", SyntheticContextOwner(clock=clock).capsule()) == 0
    )
    assert registry.drain(sid) == ()


def test_failed_direct_projection_does_not_break_business_source():
    handlers = []

    class Source:
        def subscribe(self, callback):
            handlers.append(callback)
            return lambda: None

    registry = InteropEventSourceRegistry()
    registry.register("TASK", source=Source())
    handlers[0]("unrecognized", None)
    assert registry.describe()[0]["status"] == "DEGRADED"


def test_expired_transport_subscription_tracking_is_bounded():
    async def scenario():
        clock, peer, transport = configured()
        await connect(transport, peer)
        for _ in range(15):
            transport.subscribe(authorize=lambda _: True, expires_at=clock() + timedelta(seconds=1))
            clock.advance(1)
        transport.subscribe(authorize=lambda _: True)
        assert len(transport._subscriptions) == 1
        await transport.shutdown()

    run(scenario())

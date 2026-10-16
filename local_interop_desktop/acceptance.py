"""Runnable A01–A24 contract acceptance, with native evidence kept separate.

Product test hosts can supply a DesktopAcceptanceAdapter programmatically. There
is no dynamic plugin loading, executable path argument, discovery scan or listener.
The bundled adapter is explicit MOCK_ONLY and uses the actual prepared SDK.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from local_interop_protocol import (
    CAPABILITIES,
    Heartbeat,
    ModelRegistry,
    ProtocolViolation,
    SharedModelDescriptor,
    TransportRequest,
    TutorRequest,
    VerifierRequest,
    create_diagnostic,
    validate_capsule,
)

from .diagnostics import InteropAudit, InteropDiagnosticSnapshot
from .events import EventProvenance, InteropEventSourceRegistry
from .identity import (
    AttestationState,
    InstallationRecord,
    InteropPeerDiscovery,
    InteropPeerTrustStore,
    MockPeerAttestation,
    ProductionPeerAttestation,
    TrustRecord,
)
from .lifecycle import InteropLifecycleCoordinator
from .providers import (
    InteropHandoffHandler,
    InteropModelRegistryCache,
    UserPresenceGate,
)
from .testing import SyntheticContextOwner, SyntheticDesktopPeer
from .transport import InteropTransport

SCENARIOS = (
    "Install state",
    "Peer discovery",
    "Trust",
    "Handshake",
    "Capability negotiation",
    "Metadata context",
    "Selection context",
    "Chapter context",
    "Diagnostic",
    "Event",
    "Session revoke",
    "Permission revoke",
    "Tutor guidance",
    "Verifier",
    "Deep Link",
    "Model Registry",
    "Tutor crash",
    "Studio crash",
    "Restart",
    "Upgrade compatibility",
    "Different Windows user",
    "Fake product_id",
    "Expired session",
    "Offline",
)


@dataclass
class FixtureClock:
    now: datetime

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


@dataclass
class DesktopAcceptanceFixture:
    """A test-host composition uses only synthetic projects and explicit controls.

    These ports make the scenario procedures reusable after Desktop source mapping.
    Native hosts must provide equivalent seeded-fixture controls; real user content
    must never be substituted. Native security probes remain separate evidence.
    """

    clock: FixtureClock
    peer: SyntheticDesktopPeer
    context: SyntheticContextOwner
    transport: InteropTransport
    events: InteropEventSourceRegistry
    scope: str = "MOCK_ONLY"


class DesktopAcceptanceAdapter(Protocol):
    async def create_fixture(self, scenario_id: str) -> DesktopAcceptanceFixture: ...


class SyntheticAcceptanceAdapter:
    """Explicit contract fixture; cannot approve a production installation."""

    async def create_fixture(self, scenario_id: str) -> DesktopAcceptanceFixture:
        clock = FixtureClock(datetime.now(UTC))
        peer = SyntheticDesktopPeer(clock=clock)
        context = SyntheticContextOwner(clock=clock)
        events = InteropEventSourceRegistry(clock=clock, mock_only=True)
        transport = InteropTransport(
            peer,
            context.product,
            MockPeerAttestation(),
            enabled=True,
            mock_only=True,
            timeout=0.2,
            clock=clock,
            events=events,
        )
        return DesktopAcceptanceFixture(clock, peer, context, transport, events)


@dataclass(frozen=True)
class ScenarioResult:
    id: str
    name: str
    outcome: str
    scope: str
    native_status: str
    checks: tuple[str, ...]
    elapsed_ms: float
    error_code: str | None = None


def require(condition: bool, code: str) -> None:
    if condition is not True:
        raise AssertionError(code)


def denied(call, allowed=("PERMISSION_DENIED", "CONTEXT_NOT_AUTHORIZED")) -> str:
    try:
        call()
    except ProtocolViolation as error:
        require(error.code in allowed, "unexpected_denial_code")
        return error.code
    raise AssertionError("expected_denial_missing")


async def denied_async(call, allowed) -> str:
    try:
        await call()
    except ProtocolViolation as error:
        require(error.code in allowed, "unexpected_denial_code")
        return error.code
    raise AssertionError("expected_denial_missing")


class DesktopInteropAcceptanceHarness:
    def __init__(self, adapter: DesktopAcceptanceAdapter, *, timeout_seconds: float = 10):
        if not 0 < timeout_seconds <= 300:
            raise ValueError("Acceptance timeout must be bounded")
        self.adapter = adapter
        self.timeout_seconds = timeout_seconds

    async def run(self) -> dict:
        results = []
        for index, name in enumerate(SCENARIOS, 1):
            identifier = f"A{index:02d}"
            if index == 21:
                results.append(
                    ScenarioResult(
                        identifier,
                        name,
                        "NOT_RUN",
                        "NATIVE_REQUIRED",
                        "NOT_RUN",
                        ("distinct_windows_user_probe_required",),
                        0.0,
                    )
                )
                continue
            fixture = None
            started = time.perf_counter()
            try:
                async with asyncio.timeout(self.timeout_seconds):
                    fixture = await self.adapter.create_fixture(identifier)
                    require(
                        fixture.scope in {"MOCK_ONLY", "CONTRACT_VERIFIED"},
                        "invalid_scope",
                    )
                    checks = await self._scenario(index, fixture)
                result = ScenarioResult(
                    identifier,
                    name,
                    "PASS",
                    fixture.scope,
                    "LOCAL_REQUIRED",
                    checks,
                    round((time.perf_counter() - started) * 1000, 3),
                )
            except Exception as error:
                # Retain typed metadata only; an exception may contain content or paths.
                code = getattr(error, "code", None)
                code = code if isinstance(error, ProtocolViolation) else type(error).__name__
                result = ScenarioResult(
                    identifier,
                    name,
                    "FAIL",
                    "CONTRACT_VERIFIED",
                    "LOCAL_REQUIRED",
                    (),
                    round((time.perf_counter() - started) * 1000, 3),
                    code,
                )
            finally:
                if fixture is not None:
                    try:
                        await fixture.transport.shutdown(timeout=0.3)
                    except Exception:
                        pass
            results.append(result)
        return {
            "protocol": "PoemSeed Local Interop 1.0",
            "scope": "Desktop preparation contract harness; real Desktop acceptance LOCAL_REQUIRED",
            "results": [asdict(row) for row in results],
            "summary": {
                key: sum(row.outcome == key for row in results)
                for key in ("PASS", "FAIL", "NOT_RUN")
            },
            "native_acceptance": "LOCAL_REQUIRED",
        }

    async def _connect(self, f: DesktopAcceptanceFixture):
        require(await f.transport.start(), "bridge_start_failed")
        return await f.transport.connect(
            f.peer.discovered(),
            requested_capabilities=tuple(CAPABILITIES),
            user_identity="synthetic-owner",
        )

    def _heartbeat(self, session) -> TransportRequest:
        return TransportRequest(
            operation="HEARTBEAT",
            payload=Heartbeat(
                session_id=session.session_id,
                sequence=1,
                created_at=session.created_at,
            ),
        )

    async def _scenario(self, index: int, f: DesktopAcceptanceFixture) -> tuple[str, ...]:
        if index == 1:
            require(InteropPeerDiscovery().discover() == (), "absent_installation_not_empty")
            require(not f.peer.started, "discovery_started_peer")
            return ("absent_installation", "no_auto_launch")
        if index == 2:
            discovery = InteropPeerDiscovery(registered=lambda: [f.peer.discovered()])
            require(len(discovery.discover()) == 1, "registered_discovery")
            bounded = InteropPeerDiscovery(running=lambda: [f.peer.discovered()] * 100, limit=2)
            require(len(bounded.discover()) == 1, "deduplicated_bounded_discovery")
            return ("registered_discovery", "bounded_deduplication", "no_process_scan")
        if index in {3, 22}:
            store = InteropPeerTrustStore()
            policy = ProductionPeerAttestation(
                current_user_sid=f.peer.facts.user_sid,
                installations={},
                trust_store=store,
                clock=f.clock,
            )
            require(
                policy.attest(f.peer.product, f.peer.facts).attestation_state
                == AttestationState.REJECTED,
                "fake_product_accepted",
            )
            require(store.dumps() == "[]", "unknown_peer_auto_approved")
            if index == 22:
                return ("claimed_known_product_rejected", "no_installation_no_trust")
            facts = replace(
                f.peer.facts,
                installation_id="synthetic-install",
                registered_product_id=f.peer.product.product_id,
                publisher_id="synthetic-publisher",
                signature_valid=True,
            )
            installation = InstallationRecord(
                facts.installation_id,
                f.peer.product.product_id,
                facts.executable_path_hash,
                facts.executable_hash,
                facts.publisher_id,
            )
            policy.installations[installation.installation_id] = installation
            require(
                policy.attest(f.peer.product, facts).attestation_state
                == AttestationState.SIGNED_PRODUCT,
                "signature_inferred_approval",
            )
            record = TrustRecord(
                f.peer.product.product_id,
                installation.installation_id,
                "TRUSTED_INSTALLATION",
                f.clock(),
                f.clock(),
                f.peer.product.product_version,
                "1.0",
            )
            denied(lambda: store.approve(record))
            store.approve(record, user_approved=True)
            require(
                policy.attest(f.peer.product, facts).attestation_state
                == AttestationState.TRUSTED_INSTALLATION,
                "approved_identity_not_trusted",
            )
            require(
                policy.attest(
                    f.peer.product, replace(facts, signature_valid=False)
                ).attestation_state
                == AttestationState.REJECTED,
                "trust_downgrade_missing",
            )
            store.revoke(f.peer.product.product_id, installation.installation_id)
            require(
                policy.attest(f.peer.product, facts).attestation_state
                != AttestationState.TRUSTED_INSTALLATION,
                "revoked_trust_reused",
            )
            return (
                "synthetic_os_facts_only",
                "explicit_approval",
                "trust_downgrade",
                "revocation",
            )
        if index in {6, 7, 8}:
            level = {6: "NONE", 7: "SELECTED_TEXT", 8: "CURRENT_CHAPTER"}[index]
            if index == 6:
                capsule = f.context.capsule()
                raw = capsule.model_dump_json()
                require(capsule.content.text is None, "metadata_contains_content")
                require(
                    f.context.selection not in raw and f.context.chapter not in raw,
                    "metadata_contains_manuscript",
                )
                return ("metadata_only", "no_manuscript_selection_prompt")
            denied(lambda: f.context.capsule(level))
            capsule = f.context.capsule(level, approved=True)
            require(
                capsule.content.level == level and capsule.content.consent_id is not None,
                "consent_scope_mismatch",
            )
            f.context.chapter_version += 1
            denied(
                lambda: validate_capsule(
                    capsule, now=f.clock(), chapter_version=f.context.chapter_version
                ),
                ("SOURCE_CHANGED",),
            )
            return ("explicit_consent", "exact_content_scope", "chapter_version_fence")
        if index == 9:
            diagnostic = create_diagnostic(
                diagnostic_id="synthetic-diagnostic",
                source_version="37",
                software_id=f.context.product.product_id,
                software_version="0.1.0-mock",
                feature="task-center",
                task_state="FAILED",
                created_at=f.clock(),
                expires_at=f.clock() + timedelta(seconds=60),
                evidence=f.context.capsule().evidence,
            )
            audit = InteropAudit(limit=2, clock=f.clock)
            for _ in range(4):
                audit.record("DIAGNOSTICS", result="SUCCESS")
            require(len(audit.snapshot()) == 2, "audit_unbounded")
            snapshot = InteropDiagnosticSnapshot("STOPPED")
            raw = json.dumps(
                {
                    "diagnostic": diagnostic.model_dump(mode="json"),
                    "health": asdict(snapshot),
                },
                default=str,
            )
            require(
                f.context.selection not in raw and f.context.chapter not in raw,
                "diagnostic_contains_content",
            )
            return ("non_content_diagnostic", "allowlisted_audit", "bounded_audit")
        if index in {10, 12}:
            registry = f.events
            registry.register("TASK", provenance=EventProvenance.SYNTHETIC)
            active = {"a": True, "b": True}

            def subscribe(peer):
                return registry.subscribe(
                    session_id="session-" + peer,
                    peer_id="peer-" + peer,
                    expires_at=f.clock() + timedelta(seconds=30),
                    authorize=lambda capsule: active[peer],
                    modules=("TASK",),
                )

            a, b = subscribe("a"), subscribe("b")
            for _ in range(100):
                registry.publish("TASK", "TASK_FAILED", f.context.capsule())
            require(len(registry.drain(a)) == 1, "event_coalescing_missing")
            registry.publish("TASK", "TASK_FAILED", f.context.capsule())
            active["a"] = False
            require(registry.drain(a) == (), "late_permission_change_ignored")
            registry.revoke(a)
            require(len(registry.drain(b)) == 1, "peer_a_revoke_stopped_b")
            registry.pause(b)
            registry.publish("TASK", "TASK_FAILED", f.context.capsule())
            require(registry.drain(b) == (), "pause_still_delivers")
            registry.resume(b)
            registry.publish("TASK", "TASK_FAILED", f.context.capsule())
            require(len(registry.drain(b)) == 1, "resume_failed")
            registry.disconnect("peer-b")
            require(registry.drain(b) == (), "disconnect_restored_grant")
            return (
                "coalescing",
                "live_delivery_permission",
                "isolated_revocation",
                "pause_resume",
                "disconnect_no_grant",
            )
        if index == 15:
            presence = UserPresenceGate(clock=f.clock)
            opened = []
            target = f.context.target()
            handler = InteropHandoffHandler(
                presence,
                resolve=lambda candidate: candidate == f.context.target(),
                open_target=opened.append,
            )
            denied(lambda: handler.open(target, user_presence_token="peer-action"))
            token = presence.issue_target(target, source="USER_CLICK")
            handler.open(target, user_presence_token=token)
            require(opened == [target], "user_click_navigation_missing")
            denied(lambda: handler.open(target, user_presence_token=token))
            return (
                "advice_does_not_navigate",
                "local_user_click",
                "single_use_presence",
            )
        if index == 16:

            class RegistryOwner:
                def snapshot(self):
                    return ModelRegistry(
                        models=(
                            SharedModelDescriptor(
                                runtime_id="synthetic-runtime",
                                model_id="synthetic-model",
                                family="synthetic",
                                modality=("TEXT",),
                                runtime_type="synthetic",
                                local=True,
                            ),
                        ),
                        created_at=f.clock(),
                    )

            cache = InteropModelRegistryCache(RegistryOwner(), ttl_seconds=2, clock=f.clock)
            cache.refresh()
            require(cache.snapshot().state == "READY", "model_cache_not_ready")
            f.clock.advance(3)
            require(cache.snapshot().state == "STALE", "expired_model_cache_not_stale")
            raw = cache.snapshot().registry.model_dump_json()
            require(
                "credential" not in raw and "endpoint" not in raw,
                "model_metadata_secret",
            )
            return ("owner_projection", "read_only_metadata", "stale_cache")
        if index == 24:
            f.peer.offline = True
            coordinator = InteropLifecycleCoordinator(f.transport)
            await coordinator.app_start()
            await coordinator.app_ready()
            require(await coordinator.bridge_start(), "offline_host_bridge_start_failed")
            await denied_async(
                lambda: coordinator.peer_found(
                    f.peer.discovered(),
                    requested_capabilities=(),
                    user_identity="owner",
                ),
                ("PRODUCT_NOT_AVAILABLE", "PERMISSION_DENIED"),
            )
            require(f.transport.session is None, "offline_session_exists")
            return ("offline_peer_isolated", "no_application_failure")
        if index == 20:
            f.peer.product = f.peer.product.model_copy(
                update={
                    "product_version": "0.2.0-mock",
                    "protocol_versions": ("1.0", "1.1"),
                }
            )
            await self._connect(f)
            require(f.transport.session.protocol_version == "1.0", "version_not_frozen")
            await f.transport.disconnect()
            breaking = replace(f.peer.discovered(), protocol_versions=("2.0",))
            await denied_async(
                lambda: f.transport.connect(
                    breaking, requested_capabilities=(), user_identity="owner"
                ),
                ("PROTOCOL_INCOMPATIBLE",),
            )
            return (
                "product_upgrade_compatible",
                "optional_1_1_advertisement_selects_1_0",
                "unknown_major_rejected",
            )
        session = await self._connect(f)
        if index == 4:
            snapshots = tuple(f.transport.history)
            require(
                any(s.physically_connected and not s.handshake_complete for s in snapshots),
                "physical_and_handshake_collapsed",
            )
            require(
                any(s.handshake_complete and not s.peer_authenticated for s in snapshots),
                "handshake_and_auth_collapsed",
            )
            require(
                any(s.peer_authenticated and not s.capabilities_negotiated for s in snapshots),
                "auth_and_capabilities_collapsed",
            )
            require(
                any(s.capabilities_negotiated and not s.session_established for s in snapshots),
                "capabilities_and_session_collapsed",
            )
            return ("five_distinct_stages", "deterministic_observable_history")
        request = TransportRequest(
            operation="TUTOR",
            payload=TutorRequest(
                request_id="acceptance-" + uuid4().hex,
                session_id=session.session_id,
                context=f.context.capsule(),
            ),
        )
        if index == 5:
            require(set(session.capabilities) == set(CAPABILITIES), "capability_projection")
            await denied_async(
                lambda: f.transport.request(request),
                ("PERMISSION_DENIED", "CONTEXT_NOT_AUTHORIZED"),
            )
            return ("negotiated_support", "content_permission_not_implied")
        if index == 11:
            await f.transport.disconnect()
            require(f.transport.session is None, "disconnect_retained_session")
            await denied_async(
                lambda: f.transport.request(request, authorize=lambda: True),
                ("SESSION_REQUIRED", "SESSION_REVOKED", "PERMISSION_DENIED"),
            )
            return ("session_revoked", "later_delivery_rejected")
        if index in {13, 14}:
            before = f.context.identity_binding(), f.context.task_status
            guidance = (await f.transport.request(request, authorize=lambda: True)).payload
            require(guidance.request_id == request.payload.request_id, "response_binding")
            require(
                (f.context.identity_binding(), f.context.task_status) == before,
                "advice_mutated_owner",
            )
            if index == 13:
                return ("v1_request_response_loop", "advice_no_mutation")
            verification = TransportRequest(
                operation="VERIFY",
                payload=VerifierRequest(
                    request_id="verify-" + uuid4().hex,
                    session_id=session.session_id,
                    guidance_id=guidance.guidance_id,
                    condition=guidance.verification_condition,
                    context=f.context.capsule(),
                ),
            )
            result = await f.transport.request(
                verification, authorize=lambda: True, fresh=lambda: True
            )
            require(result.payload.status == "UNKNOWN", "wire_authority_promoted")
            return ("fresh_owner_callback", "wire_evidence_never_promoted")
        if index == 17:
            f.peer.crash()
            await denied_async(
                lambda: f.transport.request(self._heartbeat(session)),
                ("PRODUCT_NOT_AVAILABLE", "PERMISSION_DENIED", "TRANSPORT_ERROR"),
            )
            return ("synthetic_peer_crash", "no_successful_late_delivery")
        if index in {18, 19}:

            def restart_factory():
                peer = SyntheticDesktopPeer(clock=f.clock)
                context = SyntheticContextOwner(clock=f.clock)
                return InteropTransport(
                    peer,
                    context.product,
                    MockPeerAttestation(),
                    enabled=True,
                    mock_only=True,
                    timeout=0.2,
                    clock=f.clock,
                )

            coordinator = InteropLifecycleCoordinator(f.transport, restart_factory=restart_factory)
            original_instance = f.transport.instance_id
            report = await coordinator.shutdown(timeout=0.2)
            require(
                report.completed and f.transport.session is None,
                "shutdown_retained_session",
            )
            if index == 18:
                return ("simulated_host_shutdown", "volatile_session_revoked")
            require(await coordinator.restart(), "restart_failed")
            require(
                coordinator.transport.instance_id != original_instance,
                "restart_instance_reused",
            )
            require(coordinator.transport.session is None, "restart_restored_session")
            await coordinator.shutdown(timeout=0.2)
            return ("fresh_instance", "no_session_or_standing_grant_restoration")
        if index == 23:
            expiry = session.expires_at
            await f.transport.request(self._heartbeat(session))
            require(f.transport.session.expires_at == expiry, "heartbeat_renewed_session")
            f.clock.advance(f.peer.ttl + 1)
            await denied_async(
                lambda: f.transport.request(self._heartbeat(session)),
                ("SESSION_REVOKED", "SESSION_REQUIRED", "PERMISSION_DENIED"),
            )
            return (
                "fixed_expiry",
                "heartbeat_does_not_extend",
                "expired_request_rejected",
            )
        raise AssertionError("scenario_not_implemented")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Explicit offline MOCK_ONLY Desktop SDK acceptance"
    )
    parser.add_argument("--mock-only", action="store_true", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = asyncio.run(DesktopInteropAcceptanceHarness(SyntheticAcceptanceAdapter()).run())
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 1 if report["summary"]["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

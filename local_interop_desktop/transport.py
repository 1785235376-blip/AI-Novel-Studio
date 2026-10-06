"""Adapter-driven async desktop transport runtime over frozen Local Interop V1.

Physical connection, handshake, identity, negotiation and session are independent
observable facts. Capability negotiation describes support, never user consent.
Native byte I/O adapters must enforce framing, ACL, identity and cancellation at
the OS boundary. This module starts no listener on import or construction.
"""

from __future__ import annotations

import asyncio
import os
import secrets
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Awaitable, Callable, Protocol
from uuid import uuid4

from local_interop_protocol import (
    CAPABILITIES,
    PROTOCOL_VERSION,
    CapabilityNegotiation,
    HandshakeHello,
    InteropError,
    ProductDescriptor,
    ProtocolViolation,
    SessionDescriptor,
    SessionOpenRequest,
    TransportRequest,
    TransportResponse,
    parse_wire,
    validate_capsule,
)

from .diagnostics import (
    HealthStatus,
    InteropAudit,
    InteropDiagnosticSnapshot,
    InteropHealth,
)
from .events import InteropEventSourceRegistry
from .identity import (
    AttestationState,
    DiscoveredPeer,
    InteropPeerAttestation,
    PeerIdentity,
    PeerOSFacts,
    utcnow,
)


class TransportState(str, Enum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    LISTENING = "LISTENING"
    DISCOVERING = "DISCOVERING"
    CONNECTING = "CONNECTING"
    HANDSHAKING = "HANDSHAKING"
    AUTHENTICATING = "AUTHENTICATING"
    NEGOTIATING = "NEGOTIATING"
    READY = "READY"
    DEGRADED = "DEGRADED"
    REVOKING = "REVOKING"
    DISCONNECTING = "DISCONNECTING"
    FAILED = "FAILED"


_TRANSITIONS = {
    "STOPPED": {"STARTING"},
    "STARTING": {"LISTENING", "FAILED", "REVOKING"},
    "LISTENING": {"DISCOVERING", "CONNECTING", "REVOKING", "FAILED"},
    "DISCOVERING": {"LISTENING", "CONNECTING", "FAILED", "REVOKING"},
    "CONNECTING": {"HANDSHAKING", "FAILED", "REVOKING"},
    "HANDSHAKING": {"AUTHENTICATING", "FAILED", "REVOKING"},
    "AUTHENTICATING": {"NEGOTIATING", "FAILED", "REVOKING"},
    "NEGOTIATING": {"READY", "FAILED", "REVOKING"},
    "READY": {"DEGRADED", "REVOKING", "FAILED"},
    "DEGRADED": {"REVOKING", "FAILED"},
    "REVOKING": {"DISCONNECTING", "STOPPED", "FAILED"},
    "DISCONNECTING": {"LISTENING", "STOPPED", "FAILED"},
    "FAILED": {"REVOKING", "STARTING", "STOPPED"},
}


@dataclass(frozen=True)
class TransportSnapshot:
    state: TransportState
    revision: int
    physically_connected: bool
    handshake_complete: bool
    peer_authenticated: bool
    session_established: bool
    capabilities_negotiated: bool
    epoch: int
    instance_id: str
    error_code: str | None = None


class DesktopTransportAdapter(Protocol):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def connect(self, peer: DiscoveredPeer) -> PeerOSFacts: ...
    async def disconnect(self) -> None: ...
    async def exchange(
        self, request: TransportRequest, *, session_token: str | None, cancellation: asyncio.Event
    ) -> bytes | TransportResponse: ...
    async def refresh_peer_facts(self) -> PeerOSFacts: ...


@dataclass
class _Pending:
    epoch: int
    cancellation: asyncio.Event
    task: asyncio.Task


class InteropTransport:
    def __init__(
        self,
        adapter: DesktopTransportAdapter,
        product: ProductDescriptor,
        attestation: InteropPeerAttestation,
        *,
        enabled: bool = False,
        acceptance_mode: bool = False,
        mock_only: bool = False,
        timeout: float = 4,
        max_pending: int = 32,
        clock: Callable[[], datetime] = utcnow,
        events: InteropEventSourceRegistry | None = None,
        audit: InteropAudit | None = None,
    ):
        if not 0.01 <= timeout <= 30 or not 1 <= max_pending <= 256:
            raise ValueError("Invalid transport bounds")
        if bool(attestation.mock_only) != bool(mock_only) or (
            getattr(adapter, "mock_only", False) and not mock_only
        ):
            raise ValueError("Mock attestation must be isolated from production transport")
        self.adapter, self.product, self.attestation = adapter, product, attestation
        self.enabled, self.acceptance_mode, self.mock_only = enabled, acceptance_mode, mock_only
        self.timeout, self.max_pending, self.clock = timeout, max_pending, clock
        self.events = events or InteropEventSourceRegistry(clock=clock, mock_only=mock_only)
        self.audit = audit or InteropAudit(clock=clock)
        self.state = TransportState.STOPPED
        self._revision = self._epoch = 0
        self._physical = self._handshake = self._authenticated = self._negotiated = False
        self._identity: PeerIdentity | None = None
        self._peer: ProductDescriptor | None = None
        self._facts: PeerOSFacts | None = None
        self._session: SessionDescriptor | None = None
        self._session_token: str | None = None
        self._pending: dict[str, _Pending] = {}
        self._inflight: set[asyncio.Task] = set()
        self._used_requests: set[str] = set()
        self._subscriptions: set[str] = set()
        self._error: str | None = None
        self._observers: list[Callable[[TransportSnapshot], None]] = []
        self.history: deque[TransportSnapshot] = deque(maxlen=128)
        self._observe()

    @property
    def instance_id(self) -> str:
        return self.product.instance_id

    @property
    def session(self) -> SessionDescriptor | None:
        if self._session is not None and (
            self._session.expires_at <= self.clock() or not self._feature_allowed()
        ):
            self._invalidate("SESSION_REVOKED")
        return self._session

    def snapshot(self) -> TransportSnapshot:
        return TransportSnapshot(
            self.state,
            self._revision,
            self._physical,
            self._handshake,
            self._authenticated,
            self._session is not None,
            self._negotiated,
            self._epoch,
            self.instance_id,
            self._error,
        )

    def observe(self, callback: Callable[[TransportSnapshot], None]) -> Callable[[], None]:
        if len(self._observers) >= 32:
            raise ValueError("Observer capacity reached")
        self._observers.append(callback)
        callback(self.snapshot())

        def remove():
            if callback in self._observers:
                self._observers.remove(callback)

        return remove

    def _observe(self) -> None:
        self._revision += 1
        snapshot = self.snapshot()
        self.history.append(snapshot)
        for callback in tuple(self._observers):
            try:
                callback(snapshot)
            except Exception:
                pass

    def _transition(self, target: TransportState, *, error: str | None = None) -> None:
        if target != self.state and target.value not in _TRANSITIONS[self.state.value]:
            raise RuntimeError("Invalid desktop transport state transition")
        self.state, self._error = target, error
        self._observe()

    def _feature_allowed(self) -> bool:
        acceptance = os.getenv("V1_ACCEPTANCE_MODE", "").lower().strip() in {
            "1",
            "true",
            "yes",
            "on",
        }
        return self.enabled is True and not self.acceptance_mode and not acceptance

    def _done(self, task: asyncio.Task) -> None:
        self._inflight.discard(task)
        if not task.cancelled():
            task.exception()  # Retrieve late failures without retaining exception messages.

    async def _bounded(self, awaitable: Awaitable, timeout: float | None = None):
        if len(self._inflight) >= self.max_pending:
            if hasattr(awaitable, "close"):
                awaitable.close()
            raise ProtocolViolation("TRANSPORT_ERROR", "Transport backpressure limit reached")
        task = asyncio.create_task(awaitable)
        self._inflight.add(task)
        task.add_done_callback(self._done)
        try:
            done, _ = await asyncio.wait(
                {task}, timeout=self.timeout if timeout is None else max(0, timeout)
            )
            if not done:
                task.cancel()
                raise ProtocolViolation("TIMEOUT", "Local transport operation timed out")
            return task.result()
        except asyncio.CancelledError:
            task.cancel()
            raise

    async def start(self) -> bool:
        if not self._feature_allowed():
            return False
        if self.state == TransportState.LISTENING:
            return True
        if self.state not in {TransportState.STOPPED, TransportState.FAILED}:
            raise ProtocolViolation("TRANSPORT_ERROR", "Transport is already active")
        self._transition(TransportState.STARTING)
        try:
            await self._bounded(self.adapter.start())
            self._transition(TransportState.LISTENING)
            self.audit.record("START")
            return True
        except Exception:
            self._transition(TransportState.FAILED, error="TRANSPORT_ERROR")
            return False

    async def discover(self, discovery) -> tuple[DiscoveredPeer, ...]:
        if self.state != TransportState.LISTENING or not self._feature_allowed():
            raise ProtocolViolation("PERMISSION_DENIED", "Bridge is not enabled")
        self._transition(TransportState.DISCOVERING)
        try:
            return discovery.discover()
        finally:
            self._transition(TransportState.LISTENING)

    async def connect(
        self, peer: DiscoveredPeer, *, requested_capabilities=(), user_identity: str
    ) -> SessionDescriptor:
        if self.state != TransportState.LISTENING or not self._feature_allowed():
            raise ProtocolViolation("PERMISSION_DENIED", "Bridge is not enabled and listening")
        requested = tuple(requested_capabilities)
        if PROTOCOL_VERSION not in peer.protocol_versions:
            raise ProtocolViolation("PROTOCOL_INCOMPATIBLE", "No compatible protocol version")
        if (
            len(set(requested)) != len(requested)
            or not set(requested).issubset(CAPABILITIES)
            or not set(requested).issubset(self.product.capabilities)
        ):
            raise ProtocolViolation("CAPABILITY_NOT_SUPPORTED", "Unsupported requested capability")
        self._epoch += 1
        epoch = self._epoch
        self._transition(TransportState.CONNECTING)
        try:
            facts = await self._bounded(self.adapter.connect(peer))
            self._guard_epoch(epoch)
            if not isinstance(facts, PeerOSFacts) or not facts.local_connection:
                raise ProtocolViolation("PERMISSION_DENIED", "Local OS peer evidence required")
            self._facts, self._physical = facts, True
            self._transition(TransportState.HANDSHAKING)
            nonce = secrets.token_hex(32)
            result = await self._exchange(
                TransportRequest(
                    operation="HELLO",
                    payload=HandshakeHello(
                        product=self.product, transport=peer.transport, session_nonce=nonce
                    ),
                ),
                epoch=epoch,
            )
            hello = result.payload
            if (
                hello.session_nonce != nonce
                or PROTOCOL_VERSION not in hello.product.protocol_versions
                or (
                    hello.product.product_id,
                    hello.product.instance_id,
                    hello.product.product_version,
                )
                != (peer.product_id, peer.instance_id, peer.product_version)
            ):
                raise ProtocolViolation("PROTOCOL_INCOMPATIBLE", "Handshake identity mismatch")
            self._handshake, self._peer = True, hello.product
            self._transition(TransportState.AUTHENTICATING)
            self._identity = self.attestation.attest(hello.product, facts)
            self._require_trusted_identity(self._identity)
            self._authenticated = True
            self._transition(TransportState.NEGOTIATING)
            if not set(requested).issubset(hello.product.capabilities):
                raise ProtocolViolation(
                    "CAPABILITY_NOT_SUPPORTED", "Peer lacks requested capability"
                )
            result = await self._exchange(
                TransportRequest(
                    operation="CAPABILITY_NEGOTIATION",
                    payload=CapabilityNegotiation(
                        hello_id=hello.hello_id, requested_capabilities=requested
                    ),
                ),
                epoch=epoch,
            )
            negotiated = result.payload
            if (
                negotiated.hello_id != hello.hello_id
                or negotiated.requested_capabilities != requested
                or not set(negotiated.granted_capabilities).issubset(hello.product.capabilities)
            ):
                raise ProtocolViolation(
                    "CAPABILITY_NOT_SUPPORTED", "Capability negotiation mismatch"
                )
            self._negotiated = True
            self._observe()
            result = await self._exchange(
                TransportRequest(
                    operation="SESSION",
                    payload=SessionOpenRequest(
                        hello_id=hello.hello_id, session_nonce=nonce, user_identity=user_identity
                    ),
                ),
                epoch=epoch,
            )
            opened = result.payload
            session = opened.session
            if (
                session.product_id != hello.product.product_id
                or session.instance_id != hello.product.instance_id
                or session.peer_product_id != self.product.product_id
                or session.peer_instance_id != self.product.instance_id
                or session.user_identity != user_identity
                or session.nonce != nonce
                or session.transport != peer.transport
                or session.capabilities != negotiated.granted_capabilities
                or session.created_at > self.clock() + timedelta(seconds=5)
                or session.expires_at <= self.clock()
            ):
                raise ProtocolViolation("SESSION_REQUIRED", "Session binding mismatch")
            self._guard_epoch(epoch)
            self._session, self._session_token = session, opened.session_token
            self._used_requests.clear()
            self._transition(TransportState.READY)
            self.audit.record("CONNECT", peer_product_id=hello.product.product_id, decision="ALLOW")
            return session
        except BaseException as error:
            if epoch == self._epoch:
                self._invalidate(getattr(error, "code", "TRANSPORT_ERROR"), failed=True)
                try:
                    await self._bounded(self.adapter.disconnect())
                except BaseException:
                    pass
            raise

    def _guard_epoch(self, epoch: int) -> None:
        if epoch != self._epoch or not self._feature_allowed():
            raise ProtocolViolation("CANCELLED", "Transport generation is no longer active")

    def _require_trusted_identity(self, identity: PeerIdentity) -> None:
        expected = (
            AttestationState.MOCK_ONLY if self.mock_only else AttestationState.TRUSTED_INSTALLATION
        )
        if identity.attestation_state != expected:
            raise ProtocolViolation("PERMISSION_DENIED", "Peer installation is not authenticated")

    def _cancel_all(self) -> None:
        for pending in tuple(self._pending.values()):
            pending.cancellation.set()
            if pending.task is not asyncio.current_task():
                pending.task.cancel()
        self._pending.clear()

    def _invalidate(self, code: str = "SESSION_REVOKED", *, failed: bool = False) -> None:
        self._epoch += 1
        self._cancel_all()
        self._clear_subscriptions()
        self._session, self._session_token = None, None
        self._authenticated = self._negotiated = False
        if failed:
            self._physical = self._handshake = False
            self._transition(TransportState.FAILED, error=code)
        elif self.state == TransportState.READY:
            self._transition(TransportState.DEGRADED, error=code)
        else:
            self._error = code
            self._observe()

    def peer_identity(self) -> PeerIdentity | None:
        return self._identity

    def authorized(self, capability: str) -> bool:
        """Live negotiated support only. Every sensitive request ALSO needs host consent."""
        try:
            session = self.session
            if (
                not self._feature_allowed()
                or self.state != TransportState.READY
                or session is None
                or capability not in session.capabilities
            ):
                return False
            self._require_trusted_identity(self.attestation.attest(self._peer, self._facts))
            return True
        except Exception:
            self._invalidate("PERMISSION_DENIED")
            return False

    async def _refresh_trust(self, *, timeout: float | None = None) -> None:
        refresh = getattr(self.adapter, "refresh_peer_facts", None)
        if refresh is None and not self.mock_only:
            raise ProtocolViolation("PERMISSION_DENIED", "Fresh OS attestation adapter required")
        facts = await self._bounded(refresh(), timeout) if refresh is not None else self._facts
        identity = self.attestation.attest(self._peer, facts)
        self._require_trusted_identity(identity)
        if self._identity is None or (
            identity.process_id,
            identity.user_sid,
            identity.executable_path_hash,
            identity.installation_id,
        ) != (
            self._identity.process_id,
            self._identity.user_sid,
            self._identity.executable_path_hash,
            self._identity.installation_id,
        ):
            raise ProtocolViolation("PERMISSION_DENIED", "Peer installation identity changed")
        self._facts, self._identity = facts, identity

    async def refresh_authority(self) -> PeerIdentity:
        """For native inbound dispatch: recheck actual OS facts before host work."""
        if self.session is None or self.state != TransportState.READY:
            raise ProtocolViolation("SESSION_REQUIRED", "A live matching session is required")
        epoch = self._epoch
        try:
            await self._refresh_trust()
            self._guard_epoch(epoch)
        except Exception:
            self._invalidate("PERMISSION_DENIED")
            raise
        return self._identity

    refresh_peer_identity = refresh_authority

    async def _exchange(
        self,
        request: TransportRequest,
        *,
        epoch: int,
        timeout: float | None = None,
        cancellation: asyncio.Event | None = None,
    ) -> TransportResponse:
        request = parse_wire(TransportRequest, request.model_dump_json())
        cancellation = cancellation or asyncio.Event()
        self._guard_epoch(epoch)
        raw = await self._bounded(
            self.adapter.exchange(
                request, session_token=self._session_token, cancellation=cancellation
            ),
            timeout,
        )
        self._guard_epoch(epoch)
        if cancellation.is_set():
            raise ProtocolViolation("CANCELLED", "Request was cancelled")
        raw = raw.model_dump_json() if isinstance(raw, TransportResponse) else raw
        response = parse_wire(TransportResponse, raw)
        if response.operation != request.operation:
            raise ProtocolViolation("INVALID_MESSAGE", "Response operation mismatch")
        if isinstance(response.payload, InteropError):
            raise ProtocolViolation(
                response.payload.code,
                "Peer rejected the local request",
                retryable=response.payload.retryable,
            )
        for field in ("request_id", "session_id"):
            expected = getattr(request.payload, field, None)
            if expected is not None and getattr(response.payload, field, None) != expected:
                raise ProtocolViolation("INVALID_MESSAGE", "Response request or session mismatch")
        return response

    async def request(
        self,
        request: TransportRequest,
        *,
        timeout: float | None = None,
        fresh: Callable[[], bool] | None = None,
        authorize: Callable[[], bool] | None = None,
    ) -> TransportResponse:
        if timeout is not None and not 0.01 <= timeout <= 30:
            raise ValueError("Invalid request timeout")
        if request.operation in {"HELLO", "CAPABILITY_NEGOTIATION", "SESSION"}:
            raise ProtocolViolation("PERMISSION_DENIED", "Use connect for protocol establishment")
        session = self.session
        if (
            self.state != TransportState.READY
            or session is None
            or getattr(request.payload, "session_id", None) != session.session_id
        ):
            raise ProtocolViolation("SESSION_REQUIRED", "A live matching session is required")
        required = {
            "TUTOR": {"tutor.guidance.request", "tutor.guidance.receive", "project.context.read"},
            "DIAGNOSTICS": {"diagnostics.read", "tutor.guidance.request", "tutor.guidance.receive"},
            "VERIFY": {"verifier.request", "verifier.result.receive"},
        }.get(request.operation, set())
        if request.operation == "HANDOFF":
            required = {
                "handoff."
                + {
                    "OPEN_FEATURE": "open_feature",
                    "OPEN_PROJECT": "open_project",
                    "OPEN_TASK": "open_task",
                    "OPEN_CHAPTER": "open_project",
                    "OPEN_SESSION": "open_feature",
                }[request.payload.target.action]
            }
        if not required.issubset(session.capabilities):
            raise ProtocolViolation(
                "CAPABILITY_NOT_SUPPORTED", "Required capability was not negotiated"
            )
        context = getattr(request.payload, "context", None)
        if context is not None:
            validate_capsule(context, now=self.clock())
        sensitive = request.operation not in {"HEARTBEAT", "CANCEL"}
        if sensitive and (authorize is None or authorize() is not True):
            raise ProtocolViolation(
                "CONTEXT_NOT_AUTHORIZED", "Explicit host authorization required"
            )
        if fresh is not None and fresh() is not True:
            raise ProtocolViolation("SOURCE_CHANGED", "Host source changed")
        request_id = getattr(request.payload, "request_id", None) or "heartbeat-" + uuid4().hex
        if request_id in self._used_requests:
            raise ProtocolViolation("INVALID_MESSAGE", "Request identity cannot be reused")
        if len(self._pending) >= self.max_pending or len(self._used_requests) >= 4096:
            raise ProtocolViolation("TRANSPORT_ERROR", "Request capacity reached")
        epoch = self._epoch
        cancellation = asyncio.Event()
        task = asyncio.current_task()
        self._pending[request_id] = _Pending(epoch, cancellation, task)
        self._used_requests.add(request_id)
        loop = asyncio.get_running_loop()
        deadline = loop.time() + (self.timeout if timeout is None else timeout)
        try:
            try:
                await self._refresh_trust(timeout=max(0, deadline - loop.time()))
            except Exception:
                self._invalidate("PERMISSION_DENIED")
                raise
            self._guard_epoch(epoch)
            response = await self._exchange(
                request,
                epoch=epoch,
                timeout=max(0, deadline - loop.time()),
                cancellation=cancellation,
            )
            try:
                await self._refresh_trust(timeout=max(0, deadline - loop.time()))
            except Exception:
                self._invalidate("PERMISSION_DENIED")
                raise
            self._guard_epoch(epoch)
            if context is not None:
                validate_capsule(context, now=self.clock())
            if session.expires_at <= self.clock() or (sensitive and authorize() is not True):
                raise ProtocolViolation(
                    "CONTEXT_NOT_AUTHORIZED", "Authorization expired during request"
                )
            if fresh is not None and fresh() is not True:
                raise ProtocolViolation("SOURCE_CHANGED", "Host source changed during request")
            self.audit.record(
                request.operation, peer_product_id=session.product_id, decision="ALLOW"
            )
            return response
        except asyncio.CancelledError:
            cancellation.set()
            raise ProtocolViolation("CANCELLED", "Request was cancelled") from None
        finally:
            cancellation.set()
            if (
                self._pending.get(request_id) is not None
                and self._pending[request_id].epoch == epoch
            ):
                self._pending.pop(request_id, None)

    async def send(self, request: TransportRequest, **kwargs) -> TransportResponse:
        return await self.request(request, **kwargs)

    def subscribe(self, *, authorize, callback=None, modules=None, expires_at=None) -> str:
        session = self.session
        if session is None or self.state != TransportState.READY:
            raise ProtocolViolation("SESSION_REQUIRED", "A live session is required")
        if "project.context.read" not in session.capabilities:
            raise ProtocolViolation(
                "CAPABILITY_NOT_SUPPORTED", "Metadata context capability required"
            )
        if expires_at is None or expires_at > session.expires_at:
            expires_at = session.expires_at
        self._subscriptions = {sid for sid in self._subscriptions if self.events.is_active(sid)}
        subscription_id = self.events.subscribe(
            session_id=session.session_id,
            peer_id=session.instance_id,
            expires_at=expires_at,
            authorize=lambda capsule: (
                self.session is session
                and self.state == TransportState.READY
                and self._subscription_trusted()
                and self._event_capabilities(capsule, session)
                and authorize(capsule) is True
            ),
            callback=callback,
            modules=modules,
        )
        self._subscriptions.add(subscription_id)
        return subscription_id

    def _clear_subscriptions(self) -> None:
        for subscription_id in self._subscriptions:
            self.events.revoke(subscription_id)
        self._subscriptions.clear()

    @staticmethod
    def _event_capabilities(capsule, session: SessionDescriptor) -> bool:
        required = {"project.context.read"}
        if capsule.project_id is not None:
            required.add("project.metadata.read")
        if capsule.task_id is not None or capsule.task_status is not None:
            required.add("task.status.read")
        if capsule.error_code is not None:
            required.add("task.error.read")
        if capsule.model_id is not None:
            required.add("model.registry.read")
        if capsule.runtime_id is not None or capsule.runtime_status is not None:
            required.add("model.runtime.status.read")
        return required.issubset(session.capabilities)

    def _subscription_trusted(self) -> bool:
        try:
            if not self._feature_allowed():
                return False
            self._require_trusted_identity(self.attestation.attest(self._peer, self._facts))
            return True
        except Exception:
            return False

    async def drain_events(self, subscription_id: str):
        """Native event delivery rechecks live OS identity before projection delivery."""
        if (
            subscription_id not in self._subscriptions
            or self.session is None
            or self.state != TransportState.READY
        ):
            return ()
        epoch = self._epoch
        try:
            await self._refresh_trust()
            self._guard_epoch(epoch)
        except Exception:
            self._invalidate("PERMISSION_DENIED")
            return ()
        return self.events.drain(subscription_id)

    def unsubscribe(self, subscription_id: str) -> None:
        if subscription_id in self._subscriptions:
            self.events.revoke(subscription_id)
            self._subscriptions.discard(subscription_id)

    def cancel(self, request_id: str) -> bool:
        pending = self._pending.pop(request_id, None)
        if pending is None:
            return False
        pending.cancellation.set()
        pending.task.cancel()
        self.audit.record("CANCEL", result="CANCELLED")
        return True

    async def disconnect(self, *, timeout: float | None = None, peer: str | None = None) -> None:
        if peer is not None and (
            self._peer is None or peer not in {self._peer.product_id, self._peer.instance_id}
        ):
            return
        if self.state == TransportState.STOPPED:
            return
        self._transition(TransportState.REVOKING)
        self._invalidate()
        self._transition(TransportState.DISCONNECTING)
        error = None
        try:
            await self._bounded(self.adapter.disconnect(), timeout)
        except Exception as exc:
            error = getattr(exc, "code", "TRANSPORT_ERROR")
        finally:
            self._physical = self._handshake = False
            self._identity = self._peer = self._facts = None
            self._transition(
                TransportState.FAILED if error else TransportState.LISTENING, error=error
            )
            self.audit.record(
                "DISCONNECT", result="FAILED" if error else "SUCCESS", error_code=error
            )

    async def shutdown(self, *, timeout: float = 1) -> None:
        if not 0 <= timeout <= 30:
            raise ValueError("Invalid shutdown deadline")
        deadline = asyncio.get_running_loop().time() + timeout
        try:
            if self.state != TransportState.STOPPED:
                await self.disconnect(timeout=max(0, deadline - asyncio.get_running_loop().time()))
            try:
                await self._bounded(
                    self.adapter.stop(), max(0, deadline - asyncio.get_running_loop().time())
                )
            except Exception:
                pass
        finally:
            # Local authority is gone even when a parent shutdown deadline cancels us.
            self._epoch += 1
            self._cancel_all()
            self._clear_subscriptions()
            self._session = self._session_token = None
            self._identity = self._peer = self._facts = None
            self._physical = self._handshake = self._authenticated = self._negotiated = False
            if self.state not in {TransportState.STOPPED, TransportState.FAILED}:
                self._transition(TransportState.REVOKING)
            self._transition(TransportState.STOPPED)
            self.audit.record("SHUTDOWN")

    async def stop(self) -> None:
        await self.shutdown()

    def health(self) -> InteropHealth:
        session = self.session
        ready = self.state == TransportState.READY
        return InteropHealth(
            transport=HealthStatus.READY if self._physical else HealthStatus.UNAVAILABLE,
            peer=HealthStatus.READY if self._authenticated else HealthStatus.UNKNOWN,
            session=HealthStatus.READY if session else HealthStatus.UNAVAILABLE,
            capabilities=HealthStatus.READY if self._negotiated else HealthStatus.UNKNOWN,
            events=HealthStatus.READY if ready else HealthStatus.UNAVAILABLE,
            tutor=HealthStatus.READY
            if ready and "tutor.guidance.request" in session.capabilities
            else HealthStatus.UNAVAILABLE,
            verifier=HealthStatus.READY
            if ready and "verifier.request" in session.capabilities
            else HealthStatus.UNAVAILABLE,
        )

    def diagnostic_snapshot(self) -> InteropDiagnosticSnapshot:
        return InteropDiagnosticSnapshot(
            self.state.value,
            self._session.capabilities if self._session else (),
            (self._error,) if self._error else (),
            trust_state=self._identity.attestation_state.value if self._identity else "UNVERIFIED",
        )

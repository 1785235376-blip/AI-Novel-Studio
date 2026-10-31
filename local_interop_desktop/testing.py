"""MOCK_ONLY fixtures for contract CI; never imported by production composition.

This is a deterministic protocol peer, not an installation or signature verifier.
It opens no socket, reads no business storage and calls no model or provider.
"""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from local_interop_protocol import (
    CAPABILITIES,
    STUDIO_PRODUCT_ID,
    TUTOR_PRODUCT_ID,
    AppContextCapsule,
    CancelResult,
    CapabilityNegotiation,
    ContextContent,
    ContextEvidence,
    GuidanceStep,
    HandoffResult,
    HandoffTarget,
    HandshakeHello,
    Heartbeat,
    HelloResult,
    ProductDescriptor,
    ProtocolViolation,
    SessionDescriptor,
    SessionOpenResult,
    TransportRequest,
    TransportResponse,
    TutorGuidance,
    VerificationCondition,
    VerifierResult,
    canonical_hash,
    create_capsule,
    parse_wire,
    validate_capsule,
)

from .identity import AttestationState, DiscoveredPeer, PeerOSFacts


def utcnow() -> datetime:
    return datetime.now(UTC)


def studio_product() -> ProductDescriptor:
    return ProductDescriptor(
        product_id=STUDIO_PRODUCT_ID,
        display_name="Synthetic Studio (MOCK_ONLY)",
        product_version="0.1.0-mock",
        instance_id="synthetic-studio-" + uuid4().hex,
        product_role="CREATIVE_STUDIO",
        capabilities=tuple(CAPABILITIES),
    )


class SyntheticDesktopPeer:
    """Callable mock transport adapter with the actual frozen V1 envelopes.

    Trust is deliberately MOCK_ONLY. Applications must not select this adapter
    in production. Authentication tests use ProductionPeerAttestation separately.
    A claimed AUTHORITATIVE label never produces a VERIFIED result here.
    """

    mock_only = True

    def __init__(self, *, clock: Callable[[], datetime] = utcnow, ttl: float = 60.0):
        self.clock = clock
        self.ttl = ttl
        self.product = ProductDescriptor(
            product_id=TUTOR_PRODUCT_ID,
            display_name="Synthetic Tutor (MOCK_ONLY)",
            product_version="0.1.0-mock",
            instance_id="synthetic-tutor-" + uuid4().hex,
            product_role="AI_TUTOR",
            capabilities=tuple(CAPABILITIES),
        )
        self.facts = PeerOSFacts(
            process_id=123,
            user_sid="S-1-5-21-1001",
            executable_path_hash="a" * 64,
            executable_hash="b" * 64,
        )
        self.started = False
        self.connected = False
        self.offline = False
        self.hello: HandshakeHello | None = None
        self.hello_id: str | None = None
        self.capabilities: tuple[str, ...] | None = None
        self.session: SessionDescriptor | None = None
        self.token: str | None = None
        self.calls: list[str] = []
        self.cancelled: set[str] = set()
        self.wait_before_reply: asyncio.Event | None = None
        self.before_reply: Callable[[], None] | None = None

    def discovered(self) -> DiscoveredPeer:
        return DiscoveredPeer(
            product_id=self.product.product_id,
            instance_id=self.product.instance_id,
            product_version=self.product.product_version,
            protocol_versions=self.product.protocol_versions,
            transport="NAMED_PIPE",
            trust_state=AttestationState.MOCK_ONLY,
            endpoint_id="synthetic-pipe-" + self.product.instance_id,
        )

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        await self.disconnect()
        self.started = False

    async def connect(self, peer: DiscoveredPeer) -> PeerOSFacts:
        if not self.started or self.offline:
            raise ProtocolViolation("PRODUCT_NOT_AVAILABLE", "Synthetic peer unavailable")
        if (peer.product_id, peer.instance_id) != (
            self.product.product_id,
            self.product.instance_id,
        ):
            raise ProtocolViolation("PERMISSION_DENIED", "Synthetic endpoint identity changed")
        self.connected = True
        return self.facts

    async def refresh_peer_facts(self) -> PeerOSFacts:
        if not self.connected or self.offline:
            raise ProtocolViolation("PRODUCT_NOT_AVAILABLE", "Synthetic peer unavailable")
        return self.facts

    async def disconnect(self) -> None:
        self.connected = False
        self.hello = None
        self.hello_id = None
        self.capabilities = None
        self.session = None
        self.token = None
        self.cancelled.clear()

    def crash(self) -> None:
        self.offline = True
        self.connected = False
        self.session = None
        self.token = None

    def restart(self) -> None:
        self.offline = False
        self.product = self.product.model_copy(
            update={"instance_id": "synthetic-tutor-" + uuid4().hex}
        )
        self.hello = None
        self.hello_id = None
        self.capabilities = None
        self.session = None
        self.token = None
        self.cancelled.clear()

    def _authorize(self, token: str | None, session_id: str | None) -> SessionDescriptor:
        if self.session is None or self.token is None or self.session.expires_at <= self.clock():
            raise ProtocolViolation("SESSION_REVOKED", "Synthetic session unavailable")
        if token is None or not secrets.compare_digest(token, self.token):
            raise ProtocolViolation("SESSION_REQUIRED", "Synthetic session credential required")
        if session_id != self.session.session_id:
            raise ProtocolViolation("SESSION_REVOKED", "Synthetic session mismatch")
        return self.session

    async def exchange(
        self,
        request: TransportRequest,
        *,
        session_token: str | None,
        cancellation: asyncio.Event,
    ) -> TransportResponse:
        if not self.connected or self.offline:
            raise ProtocolViolation("PRODUCT_NOT_AVAILABLE", "Synthetic peer unavailable")
        if cancellation.is_set():
            raise ProtocolViolation("CANCELLED", "Synthetic request cancelled")
        request = parse_wire(TransportRequest, request.model_dump_json().encode())
        self.calls.append(request.operation)
        del self.calls[:-256]
        message = request.payload
        operation = request.operation
        if operation == "HELLO":
            self.hello = message
            self.hello_id = "synthetic-hello-" + uuid4().hex
            result = HelloResult(
                hello_id=self.hello_id,
                product=self.product,
                session_nonce=message.session_nonce,
            )
        elif operation == "CAPABILITY_NEGOTIATION":
            if self.hello is None or self.hello_id != message.hello_id:
                raise ProtocolViolation("SESSION_REQUIRED", "Synthetic HELLO required")
            if self.capabilities is not None:
                raise ProtocolViolation("PERMISSION_DENIED", "Synthetic negotiation is single use")
            granted = tuple(
                item
                for item in message.requested_capabilities
                if item in self.product.capabilities and item in self.hello.product.capabilities
            )
            self.capabilities = granted
            result = CapabilityNegotiation(
                hello_id=message.hello_id,
                requested_capabilities=message.requested_capabilities,
                granted_capabilities=granted,
            )
        elif operation == "SESSION":
            if (
                self.hello is None
                or self.capabilities is None
                or self.hello_id != message.hello_id
                or self.hello.session_nonce != message.session_nonce
            ):
                raise ProtocolViolation("SESSION_REQUIRED", "Synthetic negotiated HELLO required")
            self.session = SessionDescriptor(
                session_id="synthetic-session-" + uuid4().hex,
                product_id=self.product.product_id,
                instance_id=self.product.instance_id,
                peer_product_id=self.hello.product.product_id,
                peer_instance_id=self.hello.product.instance_id,
                user_identity=message.user_identity,
                capabilities=self.capabilities,
                nonce=message.session_nonce,
                created_at=self.clock(),
                expires_at=self.clock() + timedelta(seconds=self.ttl),
                transport=self.hello.transport,
            )
            self.token = secrets.token_hex(32)
            result = SessionOpenResult(session=self.session, session_token=self.token)
        else:
            self._authorize(session_token, getattr(message, "session_id", None))
            if operation in {"TUTOR", "DIAGNOSTICS"}:
                validate_capsule(message.context, now=self.clock())
                result = TutorGuidance(
                    request_id=message.request_id,
                    session_id=message.session_id,
                    guidance_id="synthetic-guidance-" + uuid4().hex,
                    summary="MOCK_ONLY: review the observed task state",
                    diagnosis="No product mutation or model execution has occurred.",
                    steps=(
                        GuidanceStep(
                            step_id="review-task",
                            instruction="Review the task before deciding what to do.",
                        ),
                    ),
                    warnings=("MOCK_ONLY; real Desktop is LOCAL_REQUIRED.",),
                    verification_condition=VerificationCondition(
                        field="task_status",
                        expected_value="COMPLETED",
                        source_id="task_status",
                    ),
                    created_at=self.clock(),
                )
            elif operation == "VERIFY":
                validate_capsule(message.context, now=self.clock())
                result = VerifierResult(
                    request_id=message.request_id,
                    session_id=message.session_id,
                    result_id="synthetic-verification-" + uuid4().hex,
                    status="UNKNOWN",
                    reason=(
                        "Wire authority alone is not fresh, independently trusted host evidence."
                    ),
                    created_at=self.clock(),
                )
            elif operation == "HEARTBEAT":
                result = Heartbeat(
                    session_id=message.session_id,
                    sequence=message.sequence,
                    created_at=self.clock(),
                )
            elif operation == "CANCEL":
                self.cancelled.add(message.request_id)
                result = CancelResult(request_id=message.request_id, session_id=message.session_id)
            elif operation == "HANDOFF":
                result = HandoffResult(
                    request_id=message.request_id,
                    session_id=message.session_id,
                    status="REJECTED",
                    error_code="PERMISSION_DENIED",
                )
            else:
                raise ProtocolViolation(
                    "CAPABILITY_NOT_SUPPORTED", "Unsupported synthetic operation"
                )
        if self.wait_before_reply is not None:
            await self.wait_before_reply.wait()
        if self.before_reply is not None:
            self.before_reply()
        if cancellation.is_set():
            raise ProtocolViolation("CANCELLED", "Synthetic request cancelled before delivery")
        response = TransportResponse(operation=operation, payload=result)
        return parse_wire(TransportResponse, response.model_dump_json().encode())


class SyntheticContextOwner:
    """Explicit synthetic product state; never a second real product state store."""

    mock_only = True

    def __init__(self, *, clock: Callable[[], datetime] = utcnow):
        self.clock = clock
        self.product = studio_product()
        self.project_id = "synthetic-project-a"
        self.chapter_version = 37
        self.task_status = "FAILED"
        self.permission_revision = 1
        self.selection = "Synthetic selected text."
        self.chapter = "Synthetic chapter for consent-only tests."

    def capsule(self, level: str = "NONE", *, approved: bool = False) -> AppContextCapsule:
        if level != "NONE" and approved is not True:
            raise ProtocolViolation("CONTEXT_NOT_AUTHORIZED", "Explicit synthetic consent required")
        text = None
        if level == "SELECTED_TEXT":
            text = self.selection
        elif level in {"CURRENT_CHAPTER", "PROJECT_CONTEXT"}:
            text = self.chapter
        elif level != "NONE":
            raise ProtocolViolation("INVALID_MESSAGE", "Unsupported context scope")
        stamp = self.clock()
        version = str(self.chapter_version)
        return create_capsule(
            capsule_id="synthetic-capsule-" + uuid4().hex,
            source_version=version,
            product_id=self.product.product_id,
            product_version=self.product.product_version,
            instance_id=self.product.instance_id,
            project_id=self.project_id,
            project_version=version,
            chapter_id="synthetic-chapter",
            chapter_version=self.chapter_version,
            selection_id="synthetic-selection" if level == "SELECTED_TEXT" else None,
            selection_hash=canonical_hash(text) if level == "SELECTED_TEXT" else None,
            module="editor",
            surface="task-center",
            task_id="synthetic-task",
            task_status=self.task_status,
            runtime_id="synthetic-runtime",
            runtime_status="READY",
            model_id="synthetic-model",
            content=ContextContent(
                level=level,
                text=text,
                consent_id="synthetic-consent" if approved else None,
            ),
            created_at=stamp,
            expires_at=stamp + timedelta(seconds=60),
            evidence=(
                ContextEvidence(
                    source_id="task_status",
                    source_version=version,
                    locator="task:synthetic-task",
                    content_hash=canonical_hash({"task_status": self.task_status}),
                    timestamp=stamp,
                    authority="AUTHORITATIVE",
                    privacy="LOCAL_ONLY",
                ),
            ),
        )

    def identity_binding(self) -> tuple[str, int, int]:
        return self.project_id, self.chapter_version, self.permission_revision

    def target(self) -> HandoffTarget:
        return HandoffTarget(
            action="OPEN_PROJECT",
            target_product_id=self.product.product_id,
            project_id=self.project_id,
            source_version=str(self.chapter_version),
        )

"""Explicitly launched MOCK_ONLY peer for offline CI; not a real desktop Tutor.

No product implementation imports, model calls, project writes, credentials,
external traffic, file reads or automatic app startup. A wire authority label is
not trusted host provenance, so the default verifier returns UNKNOWN.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import secrets
from typing import Callable
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from local_interop_protocol import (
    CAPABILITIES, TUTOR_PRODUCT_ID, CapabilityNegotiation, CancelRequest,
    CancelResult, DiscoveryRecord, GuidanceStep, HandshakeHello,
    Heartbeat, HelloResult, HandoffTarget, InteropError, InteropEvent,
    ProductDescriptor, ProtocolViolation, SessionDescriptor, SessionOpenRequest,
    SessionOpenResult, TutorGuidance, TutorRequest, VerificationCondition,
    VerifierRequest, VerifierResult, parse_wire, require_capabilities,
    validate_capsule,
)

MAX_BODY_BYTES = 256 * 1024
MAX_SESSIONS = 64


def _now():
    return datetime.now(timezone.utc)


@dataclass
class _Pending:
    hello: HandshakeHello
    created_at: datetime
    capabilities: tuple[str, ...] | None = None


class SyntheticTutor:
    """Stateful protocol peer with explicit MOCK_ONLY software identity."""

    def __init__(self, verifier: Callable[[VerifierRequest], VerifierResult] | None = None):
        self.product = ProductDescriptor(
            product_id=TUTOR_PRODUCT_ID, display_name="Synthetic Tutor (MOCK_ONLY)",
            product_version="0.1.0-mock", instance_id="mock-" + uuid4().hex,
            product_role="AI_TUTOR", capabilities=tuple(CAPABILITIES),
        )
        self.pending: dict[str, _Pending] = {}
        self.sessions: dict[str, tuple[str, SessionDescriptor]] = {}
        self.cancelled: set[str] = set()
        self.event_sequences: dict[str, int] = {}
        self.verifier = verifier

    def prune(self):
        now = _now()
        self.pending = {k: v for k, v in self.pending.items()
                        if (now - v.created_at).total_seconds() < 30}
        self.sessions = {k: v for k, v in self.sessions.items() if v[1].expires_at > now}
        self.event_sequences = {k: v for k, v in self.event_sequences.items() if k in self.sessions}
        # Cancellation tombstones are bounded and sessions last at most ten minutes.
        if len(self.cancelled) > 256:
            self.sessions.clear()
            self.cancelled.clear()

    def authorize(self, authorization: str | None, session_id: str | None = None):
        self.prune()
        if authorization is None or not authorization.startswith("Bearer "):
            raise ProtocolViolation("SESSION_REQUIRED", "Synthetic local protocol request rejected.")
        token = authorization.removeprefix("Bearer ")
        for expected, session in self.sessions.values():
            if secrets.compare_digest(expected, token):
                if session_id is not None and session.session_id != session_id:
                    raise ProtocolViolation("SESSION_REVOKED", "Synthetic local protocol request rejected.")
                return session
        raise ProtocolViolation("SESSION_REVOKED", "Synthetic local protocol request rejected.")

    def guidance(self, request: TutorRequest) -> TutorGuidance:
        validate_capsule(request.context)
        context = request.context
        condition = None
        source = next((item for item in context.evidence if item.authority == "AUTHORITATIVE" and item.source_id == "runtime_status"), None)
        if context.runtime_status is not None and source is not None:
            condition = VerificationCondition(field="runtime_status", operator="EQ",
                                              expected_value="READY", source_id=source.source_id)
        if condition is None and context.task_status is not None:
            source = next((item for item in context.evidence if item.authority == "AUTHORITATIVE" and item.source_id == "task_status"), None)
            if source is not None:
                condition = VerificationCondition(field="task_status", operator="EQ", expected_value="COMPLETED", source_id=source.source_id)
        return TutorGuidance(
            request_id=request.request_id, session_id=request.session_id,
            guidance_id="guidance-" + uuid4().hex,
            summary="MOCK_ONLY: structured local guidance",
            diagnosis="This synthetic peer received a versioned capsule. Review the current task and runtime status in Studio; no corrective action has been executed.",
            steps=(GuidanceStep(step_id="inspect-models", instruction="Review model availability in Model Center.",
                               handoff=HandoffTarget(action="OPEN_FEATURE", target_product_id=context.product_id,
                                                     feature="model-center")),),
            warnings=("MOCK_ONLY: no real Tutor Desktop or model execution.",
                      "Advice does not change project content or settings."),
            verification_condition=condition, privacy_scope=context.privacy_scope, created_at=_now(),
        )


def create_synthetic_tutor_app(peer: SyntheticTutor | None = None) -> FastAPI:
    peer = peer or SyntheticTutor()
    app = FastAPI(title="Synthetic Tutor (MOCK_ONLY)", docs_url=None, redoc_url=None,
                  openapi_url=None)
    app.state.synthetic_tutor = peer

    def failure(code="INVALID_MESSAGE", status=400):
        error = InteropError(code=code, message="Synthetic local protocol request rejected.")
        return JSONResponse(error.model_dump(mode="json"), status_code=status)

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        if request.client is None or request.client.host != "127.0.0.1":
            return failure("PERMISSION_DENIED", 403)
        if request.url.query or "cookie" in request.headers:
            return failure("INVALID_MESSAGE", 400)
        declared = request.headers.get("content-length", "0")
        try:
            if not 0 <= int(declared) <= MAX_BODY_BYTES:
                return failure("INVALID_MESSAGE", 413)
        except ValueError:
            return failure()
        return await call_next(request)

    @app.get("/interop/v1/discovery")
    async def discovery():
        return DiscoveryRecord(product_id=peer.product.product_id,
                               instance_id=peer.product.instance_id,
                               product_version=peer.product.product_version,
                               capabilities=peer.product.capabilities).model_dump(mode="json")

    @app.post("/interop/v1/{operation}")
    async def operation(operation: str, request: Request):
        try:
            raw = bytearray()
            async for chunk in request.stream():
                raw.extend(chunk)
                if len(raw) > MAX_BODY_BYTES:
                    return failure("INVALID_MESSAGE", 413)
            peer.prune()
            if operation == "hello":
                hello = parse_wire(HandshakeHello, bytes(raw))
                if hello.transport != "LOOPBACK_HTTP" or "1.0" not in hello.product.protocol_versions:
                    raise ProtocolViolation("PROTOCOL_INCOMPATIBLE", "Synthetic local protocol request rejected.")
                if len(peer.pending) >= MAX_SESSIONS:
                    return failure("TRANSPORT_ERROR", 429)
                hello_id = "hello-" + uuid4().hex
                peer.pending[hello_id] = _Pending(hello, _now())
                result = HelloResult(hello_id=hello_id, product=peer.product,
                                     session_nonce=hello.session_nonce)
            elif operation == "negotiate":
                proposal = parse_wire(CapabilityNegotiation, bytes(raw))
                pending = peer.pending.get(proposal.hello_id)
                if pending is None or pending.capabilities is not None:
                    raise ProtocolViolation("SESSION_REQUIRED", "Synthetic local protocol request rejected.")
                require_capabilities(proposal.requested_capabilities, pending.hello.product.capabilities)
                require_capabilities(proposal.requested_capabilities, peer.product.capabilities)
                pending.capabilities = proposal.requested_capabilities
                result = CapabilityNegotiation(hello_id=proposal.hello_id,
                                               requested_capabilities=proposal.requested_capabilities,
                                               granted_capabilities=proposal.requested_capabilities)
            elif operation == "session":
                opened = parse_wire(SessionOpenRequest, bytes(raw))
                pending = peer.pending.get(opened.hello_id)
                if pending is None or pending.capabilities is None:
                    raise ProtocolViolation("SESSION_REQUIRED", "Synthetic local protocol request rejected.")
                if not secrets.compare_digest(opened.session_nonce, pending.hello.session_nonce):
                    raise ProtocolViolation("PERMISSION_DENIED", "Synthetic local protocol request rejected.")
                if len(peer.sessions) >= MAX_SESSIONS:
                    return failure("TRANSPORT_ERROR", 429)
                now = _now()
                session = SessionDescriptor(
                    session_id="session-" + uuid4().hex,
                    product_id=peer.product.product_id, instance_id=peer.product.instance_id,
                    peer_product_id=pending.hello.product.product_id,
                    peer_instance_id=pending.hello.product.instance_id,
                    # Fixture-only identity. Real reference adapters require a separate
                    # trusted local identity; a posted string is not OS authentication.
                    user_identity=opened.user_identity, capabilities=pending.capabilities,
                    nonce=opened.session_nonce, created_at=now,
                    expires_at=now + timedelta(minutes=10), transport="LOOPBACK_HTTP",
                )
                token = secrets.token_urlsafe(32)
                peer.sessions[session.session_id] = token, session
                del peer.pending[opened.hello_id]
                result = SessionOpenResult(session=session, session_token=token)
            else:
                session = peer.authorize(request.headers.get("authorization"))
                if operation in {"tutor", "diagnostics"}:
                    message = parse_wire(TutorRequest, bytes(raw))
                    peer.authorize(request.headers.get("authorization"), message.session_id)
                    require_capabilities(("tutor.guidance.request",), session.capabilities)
                    if message.request_id in peer.cancelled:
                        raise ProtocolViolation("CANCELLED", "Synthetic local protocol request rejected.")
                    if operation == "diagnostics":
                        require_capabilities(("diagnostics.read",), session.capabilities)
                        if message.diagnostic is None:
                            raise ProtocolViolation("INVALID_MESSAGE", "Synthetic local protocol request rejected.")
                    result = peer.guidance(message)
                elif operation == "verify":
                    message = parse_wire(VerifierRequest, bytes(raw))
                    peer.authorize(request.headers.get("authorization"), message.session_id)
                    require_capabilities(("verifier.request",), session.capabilities)
                    validate_capsule(message.context)
                    result = peer.verifier(message) if peer.verifier else VerifierResult(
                        request_id=message.request_id, session_id=message.session_id,
                        result_id="result-" + uuid4().hex, status="UNKNOWN",
                        reason="MOCK_ONLY: wire evidence alone is not independently trusted host state.",
                        privacy_scope=message.context.privacy_scope, created_at=_now(),
                    )
                elif operation == "events":
                    message = parse_wire(InteropEvent, bytes(raw))
                    peer.authorize(request.headers.get("authorization"), message.session_id)
                    require_capabilities(("task.status.read",), session.capabilities)
                    if message.sequence <= peer.event_sequences.get(session.session_id, 0):
                        raise ProtocolViolation("CONTEXT_STALE", "Synthetic local protocol request rejected.")
                    validate_capsule(message.context)
                    peer.event_sequences[session.session_id] = message.sequence
                    result = message
                elif operation == "heartbeat":
                    result = parse_wire(Heartbeat, bytes(raw))
                    peer.authorize(request.headers.get("authorization"), result.session_id)
                elif operation in {"cancel", "disconnect"}:
                    message = parse_wire(CancelRequest, bytes(raw))
                    if message.session_id is not None:
                        peer.authorize(request.headers.get("authorization"), message.session_id)
                    peer.cancelled.add(message.request_id)
                    if operation == "disconnect":
                        peer.sessions.pop(session.session_id, None)
                        peer.event_sequences.pop(session.session_id, None)
                    result = CancelResult(request_id=message.request_id, session_id=message.session_id)
                else:
                    raise ProtocolViolation("CAPABILITY_NOT_SUPPORTED", "Synthetic local protocol request rejected.")
            return JSONResponse(result.model_dump(mode="json"))
        except ProtocolViolation as exc:
            return failure(exc.code)
        except (ValidationError, ValueError, TypeError):
            return failure()

    return app

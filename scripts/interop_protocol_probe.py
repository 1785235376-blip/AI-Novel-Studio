"""MOCK_ONLY interop probe using this product's public loopback transport.

Run against an explicitly started development peer with independently enrolled
synthetic state. No peer implementation is imported. No real content, model,
credential store, project write or native Desktop integration is exercised.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import secrets
from pathlib import Path
from uuid import uuid4

import local_interop_protocol
from app.local_interop import transport as transport_module
from app.local_interop.errors import InteropFailure
from app.local_interop.transport import LoopbackTransport
from local_interop_protocol import (
    AppContextCapsule,
    CapabilityNegotiation,
    DiscoveryRecord,
    HandshakeHello,
    HelloResult,
    ProductDescriptor,
    SessionOpenRequest,
    SessionOpenResult,
    TutorGuidance,
    TutorRequest,
    VerifierRequest,
    VerifierResult,
    canonical_hash,
    create_capsule,
    parse_wire,
)

REQUIRED = (
    "project.context.read",
    "project.metadata.read",
    "task.status.read",
    "task.error.read",
    "model.runtime.status.read",
    "model.registry.read",
    "tutor.guidance.request",
    "tutor.guidance.receive",
    "verifier.request",
    "verifier.result.receive",
)


async def probe(endpoint: str, fixture: dict) -> dict:
    root = Path(__file__).resolve().parents[1]
    for module in (local_interop_protocol, transport_module):
        if not Path(module.__file__).resolve().is_relative_to(root):
            raise RuntimeError(
                "Probe must use this checkout's protocol and transport modules"
            )
    if (
        fixture.get("fixture_status") != "MOCK_ONLY"
        or len(fixture.get("contexts", [])) != 2
    ):
        raise ValueError("Exactly two explicitly synthetic state capsules are required")
    initial, updated = tuple(
        parse_wire(AppContextCapsule, row["capsule"]) for row in fixture["contexts"]
    )
    if initial.content.level != "NONE" or updated.content.level != "NONE":
        raise ValueError("Process probe only accepts metadata-only synthetic fixtures")
    if initial.task_status != "FAILED" or initial.runtime_status != "UNAVAILABLE":
        raise ValueError("Initial synthetic state must be FAILED and UNAVAILABLE")
    if updated.task_status != "COMPLETED" or updated.runtime_status != "READY":
        raise ValueError("Updated synthetic state must be COMPLETED and READY")
    if (
        initial.source_version == updated.source_version
        or initial.capsule_id == updated.capsule_id
    ):
        raise ValueError(
            "Updated state requires a new source version and immutable capsule identity"
        )
    if (initial.product_id, initial.instance_id) != (
        updated.product_id,
        updated.instance_id,
    ):
        raise ValueError(
            "Both synthetic states must belong to the same source instance"
        )
    transport = LoopbackTransport(endpoint)
    discovery = parse_wire(DiscoveryRecord, await transport.request("discovery"))
    product = ProductDescriptor(
        product_id=initial.product_id,
        display_name="MOCK_ONLY Creative Tool Probe",
        product_version=initial.product_version,
        instance_id=initial.instance_id,
        product_role="CREATIVE_STUDIO",
        capabilities=REQUIRED,
    )
    nonce = secrets.token_urlsafe(24)
    hello = parse_wire(
        HelloResult,
        await transport.request(
            "hello",
            HandshakeHello(
                product=product,
                transport="LOOPBACK_HTTP",
                session_nonce=nonce,
            ),
        ),
    )
    if (
        hello.session_nonce != nonce
        or hello.product.instance_id != discovery.instance_id
    ):
        raise RuntimeError("Discovery and handshake identities differ")
    negotiated = parse_wire(
        CapabilityNegotiation,
        await transport.request(
            "negotiate",
            CapabilityNegotiation(
                hello_id=hello.hello_id, requested_capabilities=REQUIRED
            ),
        ),
    )
    if set(negotiated.granted_capabilities) != set(REQUIRED):
        raise RuntimeError("Peer did not negotiate the required capabilities")
    opened = parse_wire(
        SessionOpenResult,
        await transport.request(
            "session",
            SessionOpenRequest(
                hello_id=hello.hello_id,
                session_nonce=nonce,
                user_identity=fixture["user_identity"],
            ),
        ),
    )
    session, token = opened.session, opened.session_token
    if session.peer_instance_id != initial.instance_id or session.nonce != nonce:
        raise RuntimeError("Session is not bound to the probe instance and nonce")
    immutable_hash = canonical_hash(initial)
    guidance = parse_wire(
        TutorGuidance,
        await transport.request(
            "tutor",
            TutorRequest(
                request_id=str(uuid4()),
                session_id=session.session_id,
                context=initial,
                question="An AI claims success. Check the actual FAILED task state.",
            ),
            token=token,
        ),
    )
    if guidance.verification_condition is None:
        raise RuntimeError("Peer did not provide a verifiable condition")
    if guidance.authority != "ADVISORY" or canonical_hash(initial) != immutable_hash:
        raise RuntimeError("Guidance changed authoritative source state")
    initial_result = parse_wire(
        VerifierResult,
        await transport.request(
            "verify",
            VerifierRequest(
                request_id=str(uuid4()),
                session_id=session.session_id,
                guidance_id=guidance.guidance_id,
                condition=guidance.verification_condition,
                context=initial,
            ),
            token=token,
        ),
    )
    if initial_result.status != "FAILED":
        raise RuntimeError(
            "The initial authoritative failed state was incorrectly verified"
        )
    updated_result = parse_wire(
        VerifierResult,
        await transport.request(
            "verify",
            VerifierRequest(
                request_id=str(uuid4()),
                session_id=session.session_id,
                guidance_id=guidance.guidance_id,
                condition=guidance.verification_condition,
                context=updated,
            ),
            token=token,
        ),
    )
    if updated_result.status != "VERIFIED":
        raise RuntimeError("The independently enrolled repaired state was not verified")
    # Correct schema + a fresh self-asserted hash must not create peer authority.
    unenrolled = create_capsule(
        **{
            **updated.model_dump(mode="json"),
            "capsule_id": str(uuid4()),
            "source_version": "999",
        }
    )
    try:
        await transport.request(
            "tutor",
            TutorRequest(
                request_id=str(uuid4()),
                session_id=session.session_id,
                context=unenrolled,
            ),
            token=token,
        )
    except InteropFailure as error:
        if error.code != "PERMISSION_DENIED":
            raise
    else:
        raise RuntimeError("Unenrolled capsule was incorrectly trusted")
    # Deliberately omit session credentials, paths, questions and message bodies.
    return {
        "fixture_status": "MOCK_ONLY",
        "protocol_version": "1.0",
        "transport": "LoopbackTransport",
        "checkout_local_modules": True,
        "handshake_stages": ["HELLO", "CAPABILITY_NEGOTIATION", "SESSION"],
        "source_product_id": product.product_id,
        "peer_product_id": hello.product.product_id,
        "initial_source_version": initial.source_version,
        "updated_source_version": updated.source_version,
        "initial_content": initial.content.level,
        "initial_task_status_after_guidance": initial.task_status,
        "guidance_authority": guidance.authority,
        "initial_verifier_status": initial_result.status,
        "updated_task_status": updated.task_status,
        "updated_runtime_status": updated.runtime_status,
        "updated_verifier_status": updated_result.status,
        "unenrolled_capsule": "PERMISSION_DENIED",
        "source_state_unchanged_by_guidance": canonical_hash(initial) == immutable_hash,
        "native_desktop": "LOCAL_REQUIRED",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    args = parser.parse_args()
    if args.fixture.stat().st_size > 2 * 1024 * 1024:
        parser.error("Synthetic fixture exceeds 2 MiB")
    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    print(json.dumps(asyncio.run(probe(args.endpoint, fixture)), indent=2))


if __name__ == "__main__":
    main()

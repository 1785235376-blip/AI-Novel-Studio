"""Real offline loopback subprocess proof, always against a MOCK_ONLY counterparty."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
from queue import Empty, Queue
import secrets
import subprocess
import sys
from threading import Thread
from uuid import uuid4

import httpx
import pytest

from app.local_interop.errors import InteropFailure
from app.local_interop.transport import LoopbackTransport
from local_interop_protocol import (
    CAPABILITIES, STUDIO_PRODUCT_ID, CapabilityNegotiation, ContextContent,
    DiscoveryRecord, HandshakeHello, HelloResult, InteropEvent, ProductDescriptor,
    SessionOpenRequest, SessionOpenResult, TutorGuidance, TutorRequest,
    VerificationCondition, VerifierRequest, VerifierResult, canonical_hash, create_capsule,
    parse_wire,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def synthetic_endpoint():
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
    child = subprocess.Popen(
        [sys.executable, "scripts/run_synthetic_tutor.py"], cwd=ROOT, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    lines: Queue[str] = Queue()
    Thread(target=lambda: lines.put(child.stdout.readline()), daemon=True).start()
    try:
        try:
            line = lines.get(timeout=10).strip()
        except Empty:
            pytest.fail("MOCK_ONLY peer did not publish its bounded local endpoint")
        assert line.startswith("MOCK_ONLY_ENDPOINT=http://127.0.0.1:")
        endpoint = line.split("=", 1)[1]
        for _ in range(100):
            try:
                with httpx.Client(trust_env=False, timeout=.2) as client:
                    if client.get(endpoint + "/interop/v1/discovery").status_code == 200:
                        break
            except httpx.HTTPError:
                pass
            import time
            time.sleep(.02)
        else:
            pytest.fail("MOCK_ONLY peer did not become available")
        yield endpoint
    finally:
        child.terminate()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=5)
        child.stdout.close()
        child.stderr.close()


def capsule(content=None):
    now = datetime.now(timezone.utc)
    return create_capsule(
        capsule_id="capsule-" + uuid4().hex, source_version="source-1",
        product_id=STUDIO_PRODUCT_ID, product_version="0.7.0",
        instance_id="studio-test-instance", project_id="project-test",
        project_version="1", module="NOVEL", surface="editor",
        chapter_id="chapter-test", chapter_version=1, task_status="FAILED",
        privacy_scope="LOCAL_ONLY", created_at=now, expires_at=now + timedelta(minutes=1),
        content=content or ContextContent(),
        selection_id="selection-test" if content and content.level == "SELECTED_TEXT" else None,
        selection_hash=canonical_hash(content.text) if content and content.level == "SELECTED_TEXT" else None,
    )


async def handshake(transport):
    discovery = parse_wire(DiscoveryRecord, await transport.request("discovery"))
    product = ProductDescriptor(
        product_id=STUDIO_PRODUCT_ID, display_name="Synthetic Studio (MOCK_ONLY)",
        product_version="0.7.0-mock", instance_id="studio-test-instance",
        product_role="CREATIVE_STUDIO", capabilities=tuple(CAPABILITIES),
    )
    nonce = secrets.token_urlsafe(24)
    hello = parse_wire(HelloResult, await transport.request("hello", HandshakeHello(
        product=product, transport="LOOPBACK_HTTP", session_nonce=nonce)))
    assert hello.product.instance_id == discovery.instance_id
    negotiated = parse_wire(CapabilityNegotiation, await transport.request("negotiate",
        CapabilityNegotiation(hello_id=hello.hello_id, requested_capabilities=tuple(CAPABILITIES))))
    assert negotiated.granted_capabilities == tuple(CAPABILITIES)
    opened = parse_wire(SessionOpenResult, await transport.request("session", SessionOpenRequest(
        hello_id=hello.hello_id, session_nonce=nonce, user_identity="synthetic-test-user")))
    assert opened.session.peer_instance_id == product.instance_id
    assert opened.session.nonce == nonce
    return opened


def test_real_two_process_handshake_context_selection_guidance_and_no_proxy(synthetic_endpoint, monkeypatch):
    # An unreachable environment proxy cannot intercept local interop.
    monkeypatch.setenv("HTTP_PROXY", "http://192.0.2.1:1")
    monkeypatch.setenv("HTTPS_PROXY", "http://192.0.2.1:1")
    monkeypatch.setenv("ALL_PROXY", "http://192.0.2.1:1")
    monkeypatch.setenv("NO_PROXY", "")

    async def run():
        transport = LoopbackTransport(synthetic_endpoint)
        opened = await handshake(transport)
        metadata = capsule()
        assert metadata.content.level == "NONE" and metadata.content.text is None
        for current in (metadata, capsule(ContextContent(level="SELECTED_TEXT",
                              text="Synthetic selection only.", consent_id="consent-test"))):
            request = TutorRequest(request_id="request-" + uuid4().hex,
                                   session_id=opened.session.session_id, context=current)
            response = parse_wire(TutorGuidance, await transport.request(
                "tutor", request, token=opened.session_token))
            assert response.request_id == request.request_id
            assert response.session_id == request.session_id
            assert response.authority == "ADVISORY"
            assert response.privacy_scope == "LOCAL_ONLY"
            assert "MOCK_ONLY" in response.summary
            assert "Synthetic selection only." not in response.model_dump_json()
            assert response.steps[0].handoff.action == "OPEN_FEATURE"
    asyncio.run(run())


def test_real_verifier_never_trusts_wire_success_without_host_provenance(synthetic_endpoint):
    async def run():
        transport = LoopbackTransport(synthetic_endpoint)
        opened = await handshake(transport)
        request = VerifierRequest(
            request_id="verify-test", session_id=opened.session.session_id,
            guidance_id="guidance-test", context=capsule(),
            condition=VerificationCondition(field="task_status", operator="EQ",
                                            expected_value="COMPLETED", source_id="task-test"),
        )
        response = parse_wire(VerifierResult, await transport.request(
            "verify", request, token=opened.session_token))
        assert response.status == "UNKNOWN"
        assert response.evidence == ()
    asyncio.run(run())


def test_real_peer_rejects_query_tokens_unknown_fields_missing_session_and_replay(synthetic_endpoint):
    with httpx.Client(trust_env=False, follow_redirects=False) as client:
        query = client.get(synthetic_endpoint + "/interop/v1/discovery?token=synthetic-only")
        assert query.status_code == 400
        assert query.json()["code"] == "INVALID_MESSAGE"
        denied = client.post(synthetic_endpoint + "/interop/v1/tutor", json={})
        assert denied.status_code == 400
        assert denied.json()["code"] == "SESSION_REQUIRED"
        invalid = client.post(synthetic_endpoint + "/interop/v1/hello", json={"unknown": True})
        assert invalid.status_code == 400
    async def run():
        transport = LoopbackTransport(synthetic_endpoint)
        opened = await handshake(transport)
        message = TutorRequest(request_id="request-test", session_id="forged-session", context=capsule())
        with pytest.raises(InteropFailure):
            await transport.request("tutor", message, token=opened.session_token)
    asyncio.run(run())


@pytest.mark.parametrize("endpoint", [
    "http://0.0.0.0:8000", "http://localhost:8000", "http://192.168.1.2:8000",
    "http://127.0.0.1:8000?token=x", "http://user:pass@127.0.0.1:8000",
    "https://127.0.0.1:8000", "http://127.0.0.1:8000/redirect", "http://[::1]:8000",
])
def test_transport_rejects_noncanonical_or_credential_urls(endpoint):
    with pytest.raises(InteropFailure):
        LoopbackTransport(endpoint)


def test_transport_rejects_redirect_without_following():
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    class Redirect(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(302)
            self.send_header("Location", "http://192.0.2.1:1/private")
            self.end_headers()
        def log_message(self, *_):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(InteropFailure) as rejected:
            asyncio.run(LoopbackTransport(f"http://127.0.0.1:{server.server_port}").request("discovery"))
        assert rejected.value.code == "TRANSPORT_ERROR"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_real_two_sessions_event_revoke_isolated_and_restart_nonce(synthetic_endpoint):
    from local_interop_protocol import CancelRequest, CancelResult
    async def run():
        transport = LoopbackTransport(synthetic_endpoint)
        first, second = await handshake(transport), await handshake(transport)
        assert first.session.session_id != second.session.session_id
        assert first.session.nonce != second.session.nonce
        def event(opened, sequence):
            return InteropEvent(event_id="event-" + uuid4().hex,
                                session_id=opened.session.session_id, sequence=sequence,
                                event_type="TASK_FAILED", created_at=datetime.now(timezone.utc),
                                context=capsule())
        for opened in (first, second):
            payload = event(opened, 1)
            assert parse_wire(InteropEvent, await transport.request("events", payload,
                              token=opened.session_token)) == payload
        cancelled = parse_wire(CancelResult, await transport.request("disconnect",
            CancelRequest(request_id="disconnect-test", session_id=first.session.session_id),
            token=first.session_token))
        assert cancelled.status == "CANCELLED"
        with pytest.raises(InteropFailure) as revoked:
            await transport.request("events", event(first, 2), token=first.session_token)
        assert revoked.value.code == "SESSION_REVOKED"
        allowed = event(second, 2)
        assert parse_wire(InteropEvent, await transport.request("events", allowed,
                          token=second.session_token)) == allowed
        with pytest.raises(InteropFailure) as stale:
            await transport.request("events", allowed, token=second.session_token)
        assert stale.value.code == "CONTEXT_STALE"
    asyncio.run(run())


def test_transport_actual_deadline_and_cancellation():
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import time
    class Slow(BaseHTTPRequestHandler):
        def do_GET(self):
            time.sleep(.3)
            try:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{}')
            except (BrokenPipeError, ConnectionResetError):
                pass
        def log_message(self, *_):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Slow)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    async def run():
        transport = LoopbackTransport(f"http://127.0.0.1:{server.server_port}", timeout=.05)
        with pytest.raises(InteropFailure) as timeout:
            await transport.request("discovery")
        assert timeout.value.code == "TIMEOUT"
        task = asyncio.create_task(LoopbackTransport(transport.endpoint).request("discovery"))
        await asyncio.sleep(.02)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    try:
        asyncio.run(run())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_real_diagnostics_rejects_missing_capsule_and_source_content(synthetic_endpoint):
    from local_interop_protocol import create_diagnostic
    async def run():
        transport = LoopbackTransport(synthetic_endpoint)
        opened = await handshake(transport)
        now = datetime.now(timezone.utc)
        diagnostic = create_diagnostic(
            diagnostic_id="diagnostic-test", source_version="source-1",
            software_id=STUDIO_PRODUCT_ID, software_version="0.7.0", feature="editor",
            created_at=now, expires_at=now + timedelta(minutes=1))
        missing = TutorRequest(request_id="diagnostic-missing", session_id=opened.session.session_id,
                               context=capsule())
        selected = TutorRequest(request_id="diagnostic-content", session_id=opened.session.session_id,
                                context=capsule(ContextContent(level="SELECTED_TEXT",
                                    text="Synthetic selection only.", consent_id="consent-test")),
                                diagnostic=diagnostic)
        for message in (missing, selected):
            with pytest.raises(InteropFailure) as denied:
                await transport.request("diagnostics", message, token=opened.session_token)
            assert denied.value.code == "INVALID_MESSAGE"
        with pytest.raises(InteropFailure) as bypass:
            await transport.request("tutor", selected, token=opened.session_token)
        assert bypass.value.code == "INVALID_MESSAGE"
        valid = TutorRequest(request_id="diagnostic-valid", session_id=opened.session.session_id,
                             context=capsule(), diagnostic=diagnostic)
        result = parse_wire(TutorGuidance, await transport.request("diagnostics", valid,
                            token=opened.session_token))
        assert result.request_id == valid.request_id
    asyncio.run(run())

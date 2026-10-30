"""Opt-in Local Interop event consent and Tutor/Verifier round-trip boundaries.

Uses the frozen ``SyntheticDesktopPeer`` plus an injected transport. Event
delivery is acknowledged by the injected transport itself because the frozen
protocol peer has no EVENTS operation; everything else (context capsule,
TutorRequest/TutorGuidance, Host-side verification, event consent and
permission generation) runs through the real ``LocalInteropHost``.

Security properties pinned here: Tutor prose or wire text can never become a
VERIFIED Host result; event subscription requires an explicit confirmed preview
and a standing event consent; revoking that consent clears the grant and
invalidates queued delivery and request bindings.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.local_interop.api import (
    AskInput, ContextPreviewInput, EventPreviewInput, EventSubscribeInput,
    PermissionRevokeInput, VerifyInput,
)
from app.local_interop.errors import InteropFailure
from app.local_interop.host import LocalInteropHost
from local_interop_desktop.testing import SyntheticDesktopPeer
from test_local_interop_session_boundary import (
    FLAG, FLAG_ENV, TOKEN, PeerTransport, SessionProvider, _connect_body,
)


class GuidanceTransport(PeerTransport):
    OPERATIONS = {**PeerTransport.OPERATIONS, "tutor": "TUTOR",
                  "diagnostics": "DIAGNOSTICS", "verify": "VERIFY"}

    async def request(self, operation, message=None, *, token=None, before_send=None):
        if operation == "events":
            # The frozen peer exposes no EVENTS operation; acknowledge the exact
            # event object so the Host dispatch loop is exercised deterministically.
            if before_send:
                before_send()
            return message.model_dump_json().encode()
        return await super().request(operation, message, token=token, before_send=before_send)


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def guidance_rig(monkeypatch):
    monkeypatch.setenv(FLAG_ENV, FLAG)
    provider = SessionProvider()
    peer = SyntheticDesktopPeer()
    transport = GuidanceTransport(peer)
    host = LocalInteropHost(provider, transport_factory=lambda endpoint: transport)
    yield SimpleNamespace(host=host, provider=provider, peer=peer, transport=transport)


def test_context_preview_tutor_roundtrip_cannot_produce_verified_result(guidance_rig):
    host, peer = guidance_rig.host, guidance_rig.peer

    async def scenario():
        await host.app_start()
        await peer.start()
        await peer.connect(peer.discovered())
        host.configure(TOKEN, True)
        session_id = (await host.connect(TOKEN, _connect_body(host)))["session_id"]
        preview = host.context_preview(TOKEN, ContextPreviewInput(session_id=session_id))
        assert preview["capsule"]["content"]["level"] == "NONE"
        unconfirmed = AskInput(session_id=session_id, preview_id=preview["preview_id"],
                               confirmed=False)
        with pytest.raises(InteropFailure) as refused:
            await host.ask(TOKEN, unconfirmed)
        assert (refused.value.code, refused.value.status) == ("CONTEXT_NOT_AUTHORIZED", 403)
        guidance = await host.ask(TOKEN, AskInput(session_id=session_id,
                                                  preview_id=preview["preview_id"],
                                                  confirmed=True))
        assert guidance["guidance"]["privacy_scope"] == "LOCAL_ONLY"
        assert guidance["guidance"]["request_id"]
        # The consumed preview cannot be replayed.
        with pytest.raises(InteropFailure) as stale:
            await host.ask(TOKEN, AskInput(session_id=session_id,
                                           preview_id=preview["preview_id"], confirmed=True))
        assert (stale.value.code, stale.value.status) == ("CONTEXT_STALE", 409)
        result = await host.verify(TOKEN, VerifyInput(
            session_id=session_id, guidance_id=guidance["guidance"]["guidance_id"]))
        # Peer prose claims are not Host evidence: verification stays UNKNOWN.
        assert result["result"]["status"] == "UNKNOWN"
        assert result["result"]["status"] != "VERIFIED"
        await host.shutdown(timeout=.5)

    _run(scenario())


def test_event_consent_requires_confirmed_preview_and_is_revocable(guidance_rig):
    host, peer = guidance_rig.host, guidance_rig.peer

    async def scenario():
        await host.app_start()
        await peer.start()
        await peer.connect(peer.discovered())
        host.configure(TOKEN, True)
        session_id = (await host.connect(TOKEN, _connect_body(host)))["session_id"]
        # No event grant exists before an explicit confirmed preview.
        assert host.capture_event(TOKEN, session_id) is None
        preview = host.event_preview(TOKEN, EventPreviewInput(session_id=session_id))
        unconfirmed = EventSubscribeInput(session_id=session_id,
                                          preview_id=preview["preview_id"], confirmed=False)
        with pytest.raises(InteropFailure) as refused:
            host.event_subscribe(TOKEN, unconfirmed)
        assert (refused.value.code, refused.value.status) == ("CONTEXT_NOT_AUTHORIZED", 403)
        grant = host.event_subscribe(TOKEN, EventSubscribeInput(
            session_id=session_id, preview_id=preview["preview_id"], confirmed=True))
        assert grant["subscription_active"] is True and grant["subscription_id"]
        grant_id = grant["subscription_id"]
        session = host._session(TOKEN, session_id)
        assert session.event_grant_id == grant_id
        host._event_guard(session, grant_id)
        # The Host dispatch loop may enqueue/deliver while consent is live.
        await asyncio.sleep(.05)
        session = host._session(TOKEN, session_id)
        assert session.event_grant_id == grant_id
        # Revoking the standing consent clears the grant, queued delivery and the
        # old request binding immediately.
        revoked = host.permission_revoke(TOKEN, PermissionRevokeInput(
            session_id=session_id, permission_id="standing_metadata_events"))
        assert revoked["status"] == "REVOKED"
        session = host._session(TOKEN, session_id)
        assert session.event_grant_id is None
        with pytest.raises(InteropFailure) as stale_grant:
            host._event_guard(session, grant_id)
        assert (stale_grant.value.code, stale_grant.value.status) == ("PERMISSION_DENIED", 403)
        with pytest.raises(InteropFailure) as stale_binding:
            host.delivery_guard(TOKEN, session_id, preview["request_id"])
        assert stale_binding.value.code == "PERMISSION_DENIED"
        await host.shutdown(timeout=.5)

    _run(scenario())


def test_diagnostic_preview_pauses_events_and_requires_capability(guidance_rig):
    host, peer = guidance_rig.host, guidance_rig.peer

    async def scenario():
        await host.app_start()
        await peer.start()
        await peer.connect(peer.discovered())
        host.configure(TOKEN, True)
        session_id = (await host.connect(TOKEN, _connect_body(host)))["session_id"]
        preview = host.event_preview(TOKEN, EventPreviewInput(session_id=session_id))
        grant = host.event_subscribe(TOKEN, EventSubscribeInput(
            session_id=session_id, preview_id=preview["preview_id"], confirmed=True))
        assert grant["subscription_active"] is True
        # A minimized diagnostic must pause a broader standing grant.
        from app.local_interop.api import DiagnosticPreviewInput
        diagnostic = host.diagnostic_preview(TOKEN, DiagnosticPreviewInput(session_id=session_id))
        assert diagnostic["event_subscription_paused"] is True
        session = host._session(TOKEN, session_id)
        assert session.event_grant_id is None
        await host.shutdown(timeout=.5)

    _run(scenario())

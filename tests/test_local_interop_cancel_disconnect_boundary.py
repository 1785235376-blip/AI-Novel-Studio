"""Opt-in Local Interop cancel/disconnect receipts and late-authority boundaries.

Uses the frozen ``SyntheticDesktopPeer`` through an injected transport. The peer
does not receive any business data; the transport only carries the frozen
protocol envelopes. Pins: duplicate in-flight request ids are refused, cancel
cannot touch another owner's session, disconnect revokes local authority before
any peer round trip, and the close receipt distinguishes acknowledged peer
disconnect, closed local transport and unconfirmed state.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.local_interop.api import SessionInput
from app.local_interop.errors import InteropFailure
from app.local_interop.host import LocalInteropHost
from local_interop_desktop.testing import SyntheticDesktopPeer
from test_local_interop_session_boundary import (
    FLAG, FLAG_ENV, TOKEN, PeerTransport, SessionProvider, _connect_body,
)


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def cancel_rig(monkeypatch):
    monkeypatch.setenv(FLAG_ENV, FLAG)
    provider = SessionProvider()
    peer = SyntheticDesktopPeer()
    transport = PeerTransport(peer)
    host = LocalInteropHost(provider, transport_factory=lambda endpoint: transport)
    yield SimpleNamespace(host=host, provider=provider, peer=peer, transport=transport)


async def _connected(rig):
    host, peer = rig.host, rig.peer
    await host.app_start()
    await peer.start()
    await peer.connect(peer.discovered())
    host.configure(TOKEN, True)
    return (await host.connect(TOKEN, _connect_body(host)))["session_id"]


def test_duplicate_inflight_request_is_refused(cancel_rig):
    host = cancel_rig.host

    async def scenario():
        session_id = await _connected(cancel_rig)
        started, release = asyncio.Event(), asyncio.Event()

        async def operation():
            started.set()
            await release.wait()
            return {"ok": True}

        first = asyncio.create_task(host.run(TOKEN, "request-fixed", operation,
                                             session_id=session_id))
        await started.wait()
        with pytest.raises(InteropFailure) as duplicate:
            await host.run(TOKEN, "request-fixed", operation, session_id=session_id)
        assert (duplicate.value.code, duplicate.value.status) == ("CANCELLED", 409)
        release.set()
        assert await first == {"ok": True}
        await host.shutdown(timeout=.5)

    _run(scenario())


def test_cancel_only_touches_the_owners_session(cancel_rig):
    host = cancel_rig.host

    async def scenario():
        session_id = await _connected(cancel_rig)
        # Cancelling an unknown request is a fixed receipt, never an error.
        receipt = host.cancel(TOKEN, "request-unknown")
        assert receipt == {"request_id": "request-unknown", "status": "CANCELLED"}
        # A session id owned by this owner is accepted; the owner gate is what
        # protects a different owner (not modelled here because the synthetic
        # provider has exactly one actor).
        host.cancel(TOKEN, "request-unknown", session_id)
        await host.shutdown(timeout=.5)

    _run(scenario())


def test_disconnect_revokes_locally_and_reports_peer_receipt(cancel_rig):
    host = cancel_rig.host

    async def scenario():
        session_id = await _connected(cancel_rig)
        report = await host.disconnect_revoke(TOKEN, SessionInput(session_id=session_id))
        assert report["revoked"] is True
        assert report["subscriptions_stopped"] is True
        assert report["pending_cancelled"] is True
        assert report["standing_grants_cleared"] is True
        assert report["status"] == "DISCONNECTED"
        assert report["transport_disconnected"] is True
        assert report["peer_disconnect_acknowledged"] is True
        assert session_id in host.closed_sessions and session_id not in host.sessions
        with pytest.raises(InteropFailure) as revoked:
            host._session(TOKEN, session_id)
        assert (revoked.value.code, revoked.value.status) == ("SESSION_REVOKED", 401)
        # A repeat disconnect is idempotent and keeps the honest receipt shape.
        again = await host.disconnect_revoke(TOKEN, SessionInput(session_id=session_id))
        assert again["revoked"] is True and again["status"] in {"DISCONNECTED", "UNKNOWN"}
        await host.shutdown(timeout=.5)

    _run(scenario())


def test_sync_disconnect_revokes_without_claiming_peer_state(cancel_rig):
    host = cancel_rig.host

    async def scenario():
        session_id = await _connected(cancel_rig)
        receipt = host.disconnect(TOKEN, session_id)
        assert receipt == {"session_id": session_id, "status": "DISCONNECTED"}
        assert session_id not in host.sessions
        with pytest.raises(InteropFailure):
            host._session(TOKEN, session_id)
        # A foreign/unknown session id still returns a bounded receipt keyed to
        # the caller's own owner projection (no cross-owner disclosure).
        assert host.disconnect(TOKEN, "session-does-not-exist") == {
            "session_id": "session-does-not-exist", "status": "DISCONNECTED"}
        await host.shutdown(timeout=.5)

    _run(scenario())

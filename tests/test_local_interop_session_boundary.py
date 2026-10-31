"""Opt-in Local Interop session boundary: connect, revocation, reconnect, handoff.

Uses the repository's frozen ``SyntheticDesktopPeer`` (MOCK_ONLY protocol peer,
no socket, no business storage) behind an injected transport, so the real
``LocalInteropHost`` session/authorization code runs end to end without a real
desktop peer. No production code changes are made by this file.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.local_interop.api import ConnectInput, HandoffInput, PermissionRevokeInput, ScopeInput
from app.local_interop.errors import InteropFailure
from app.local_interop.host import LocalInteropHost
from local_interop_desktop.testing import SyntheticDesktopPeer
from local_interop_protocol import (
    CancelRequest, HandshakeHello, CapabilityNegotiation, SessionOpenRequest,
    TransportRequest, HandoffTarget,
)

FLAG_ENV = "EXPERIMENTAL_FEATURES"
FLAG = "local_tutor_interop_v1"
TOKEN = "token-known"
SCOPE = dict(workspace_id="workspace-synthetic", project_id="project-synthetic",
             storyline_id="storyline-synthetic", branch_id="branch-synthetic")


class SessionProvider:
    """Synthetic read-only Host provider; toggles authorization changes."""

    def __init__(self):
        self.fingerprint = "fingerprint-1"
        self.denied = False
        self.actor_obj = SimpleNamespace(actor_id="actor-synthetic", session_id="host-session",
                                         workspace_id="workspace-synthetic")

    def actor(self, token):
        if token != TOKEN:
            raise InteropFailure("SESSION_REQUIRED", 401)
        return self.actor_obj

    def authorize(self, token, scope):
        if self.denied:
            raise InteropFailure("PERMISSION_DENIED", 403)
        return self.actor_obj, self.fingerprint, {"id": scope["project_id"]}

    def snapshot(self, token, scope, *, module, surface, chapter_id=None, task_id=None):
        if self.denied:
            raise InteropFailure("PERMISSION_DENIED", 403)
        return {"authorization": self.fingerprint, "chapter": None, "source_version": "source-v1",
                "state": {**scope, "project_version": "project-v1", "chapter_id": chapter_id,
                          "chapter_version": None, "task_id": task_id, "task_type": None,
                          "task_status": None, "error_code": None, "model_id": None,
                          "runtime_id": None, "runtime_status": None, "module": module,
                          "surface": surface}}

    def model_rows(self):
        return []

    def chapter_entries(self, scope):
        return []

    def chapter(self, scope, chapter_id):
        return None


class PeerTransport:
    """Inject the frozen protocol peer where the Host expects its local transport."""

    OPERATIONS = {"hello": "HELLO", "negotiate": "CAPABILITY_NEGOTIATION", "session": "SESSION",
                  "disconnect": "CANCEL"}

    def __init__(self, peer):
        self.peer = peer
        self.closed = False
        self.requests = []

    async def request(self, operation, message=None, *, token=None, before_send=None):
        wire = self.OPERATIONS.get(operation)
        if wire is None:
            raise InteropFailure("CAPABILITY_NOT_SUPPORTED", 403)
        self.requests.append(wire)
        if before_send:
            before_send()
        request = TransportRequest(operation=wire, payload=message)
        response = await self.peer.exchange(request, session_token=token,
                                            cancellation=asyncio.Event())
        if before_send:
            before_send()
        return response.payload.model_dump_json().encode()

    async def shutdown(self, *, timeout=.25):
        self.closed = True
        return True


@pytest.fixture
def session_rig(monkeypatch):
    monkeypatch.setenv(FLAG_ENV, FLAG)
    provider = SessionProvider()
    peer = SyntheticDesktopPeer()
    transport = PeerTransport(peer)
    host = LocalInteropHost(provider, transport_factory=lambda endpoint: transport)
    yield SimpleNamespace(host=host, provider=provider, peer=peer, transport=transport)


def _connect_body(host):
    return ConnectInput(endpoint="http://127.0.0.1:59999/",
                        scope=ScopeInput(**SCOPE), module="editor", surface="settings")


def _handoff(session_id, host, *, explicit_click=True, action="OPEN_FEATURE", feature="settings"):
    return HandoffInput(session_id=session_id, explicit_click=explicit_click,
                        handoff=HandoffTarget(action=action, feature=feature,
                                              target_product_id=host.product.product_id))


def _run(coro):
    return asyncio.run(coro)


def test_session_connect_handoff_and_permission_revocation(session_rig):
    host, provider, peer = session_rig.host, session_rig.provider, session_rig.peer

    async def scenario():
        await host.app_start()
        await peer.start()
        await peer.connect(peer.discovered())
        host.configure(TOKEN, True)
        opened = await host.connect(TOKEN, _connect_body(host))
        session_id = opened["session_id"]
        assert host._session(TOKEN, session_id).owner == host._owner(TOKEN)
        assert opened["capabilities"], "negotiated capabilities must not be empty"
        # Handoff needs an explicit click, the deep-link capability and the target product.
        assert host.handoff(TOKEN, _handoff(session_id, host))["route"]["feature"] == "settings"
        with pytest.raises(InteropFailure) as no_click:
            host.handoff(TOKEN, _handoff(session_id, host, explicit_click=False))
        assert (no_click.value.code, no_click.value.status) == ("PERMISSION_DENIED", 403)
        # Revoking one consent removes only its mapped capabilities and bumps generation.
        revoked = host.permission_revoke(TOKEN, PermissionRevokeInput(session_id=session_id,
                                                                      permission_id="deep_link"))
        assert revoked["status"] == "REVOKED"
        session = host._session(TOKEN, session_id)
        assert "handoff.open_feature" not in host._capabilities(session)
        with pytest.raises(InteropFailure) as closed_handoff:
            host.handoff(TOKEN, _handoff(session_id, host))
        # The revoked local consent takes precedence over the capability check.
        assert closed_handoff.value.code == "PERMISSION_DENIED"
        # Revoking the negotiation-wide capability is refused by the session gate.
        with pytest.raises(InteropFailure) as missing_cap:
            host._session(TOKEN, session_id, "handoff.open_project")
        assert missing_cap.value.code == "CAPABILITY_NOT_SUPPORTED"
        await host.shutdown(timeout=.5)

    _run(scenario())


def test_authorization_change_revokes_live_session(session_rig):
    host, provider, peer = session_rig.host, session_rig.provider, session_rig.peer

    async def scenario():
        await host.app_start()
        await peer.start()
        await peer.connect(peer.discovered())
        host.configure(TOKEN, True)
        session_id = (await host.connect(TOKEN, _connect_body(host)))["session_id"]
        provider.fingerprint = "fingerprint-2"  # membership/grant fingerprint changed
        with pytest.raises(InteropFailure) as changed:
            host._session(TOKEN, session_id)
        assert (changed.value.code, changed.value.status) == ("PERMISSION_DENIED", 403)
        assert session_id not in host.sessions
        assert session_id in host.closed_sessions
        await host.shutdown(timeout=.5)

    _run(scenario())


def test_explicit_authorization_denial_revokes_live_session(session_rig):
    host, provider, peer = session_rig.host, session_rig.provider, session_rig.peer

    async def scenario():
        await host.app_start()
        await peer.start()
        await peer.connect(peer.discovered())
        host.configure(TOKEN, True)
        session_id = (await host.connect(TOKEN, _connect_body(host)))["session_id"]
        provider.denied = True
        with pytest.raises(InteropFailure) as denied:
            host._session(TOKEN, session_id)
        assert (denied.value.code, denied.value.status) == ("PERMISSION_DENIED", 403)
        assert session_id not in host.sessions
        await host.shutdown(timeout=.5)

    _run(scenario())


def test_reconnect_replaces_only_that_owners_session(session_rig):
    host, provider, peer = session_rig.host, session_rig.provider, session_rig.peer

    async def scenario():
        await host.app_start()
        await peer.start()
        await peer.connect(peer.discovered())
        host.configure(TOKEN, True)
        first = (await host.connect(TOKEN, _connect_body(host)))["session_id"]
        await peer.disconnect()
        await peer.connect(peer.discovered())
        second = (await host.connect(TOKEN, _connect_body(host)))["session_id"]
        assert second != first
        assert first not in host.sessions and first in host.closed_sessions
        assert second in host.sessions
        with pytest.raises(InteropFailure) as old:
            host._session(TOKEN, first)
        assert (old.value.code, old.value.status) == ("SESSION_REVOKED", 401)
        await host.shutdown(timeout=.5)

    _run(scenario())


def test_disabling_the_feature_revokes_the_live_session(session_rig, monkeypatch):
    host, peer = session_rig.host, session_rig.peer

    async def scenario():
        await host.app_start()
        await peer.start()
        await peer.connect(peer.discovered())
        host.configure(TOKEN, True)
        session_id = (await host.connect(TOKEN, _connect_body(host)))["session_id"]
        monkeypatch.setenv(FLAG_ENV, "")
        with pytest.raises(InteropFailure) as disabled:
            host._session(TOKEN, session_id)
        assert (disabled.value.code, disabled.value.status) == ("PERMISSION_DENIED", 403)
        assert session_id not in host.sessions
        await host.shutdown(timeout=.5)

    _run(scenario())

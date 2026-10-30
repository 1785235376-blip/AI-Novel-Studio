"""Local Interop late-response / stale-projection windows.

Pins the last-frame guards that stop a response computed under an older consent
or context from being delivered after a revocation/cancellation/source change.
Uses the frozen synthetic peer and the shared interop session rig; no network,
no real project data, no production change.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.local_interop.api import ContextPreviewInput, PermissionRevokeInput
from app.local_interop.errors import InteropFailure
from test_local_interop_session_boundary import (
    TOKEN, _connect_body, _run, session_rig,  # noqa: F401 - pytest fixture/helpers
)


async def _connected(rig):
    host, peer = rig.host, rig.peer
    await host.app_start()
    await peer.start()
    await peer.connect(peer.discovered())
    host.configure(TOKEN, True)
    return (await host.connect(TOKEN, _connect_body(host)))["session_id"]


def test_desktop_response_guard_refuses_stale_permission_projection(session_rig):
    host = session_rig.host

    async def scenario():
        session_id = await _connected(session_rig)
        value = host.status(TOKEN)
        guard = host.desktop_response_guard(TOKEN, value)
        guard()  # unchanged authority may deliver the browser projection
        host.permission_revoke(TOKEN, PermissionRevokeInput(session_id=session_id,
                                                            permission_id="task_status"))
        with pytest.raises(InteropFailure) as stale:
            guard()
        assert (stale.value.code, stale.value.status) == ("PERMISSION_DENIED", 403)
        await host.shutdown(timeout=.5)

    _run(scenario())


def test_desktop_response_guard_refuses_when_feature_turns_off(session_rig, monkeypatch):
    host = session_rig.host
    from test_local_interop_session_boundary import FLAG_ENV

    async def scenario():
        await _connected(session_rig)
        guard = host.desktop_response_guard(TOKEN, host.status(TOKEN))
        guard()
        monkeypatch.setenv(FLAG_ENV, "")
        with pytest.raises(InteropFailure) as stale:
            guard()
        assert (stale.value.code, stale.value.status) == ("PERMISSION_DENIED", 403)
        await host.shutdown(timeout=.5)

    _run(scenario())


def test_cancelled_request_late_result_is_refused(session_rig):
    host = session_rig.host

    async def scenario():
        session_id = await _connected(session_rig)
        started, release = asyncio.Event(), asyncio.Event()

        async def operation():
            started.set()
            await release.wait()
            return {"late": "result"}

        task = asyncio.create_task(host.run(TOKEN, "request-late", operation,
                                            session_id=session_id))
        await started.wait()
        receipt = host.cancel(TOKEN, "request-late", session_id)
        assert receipt == {"request_id": "request-late", "status": "CANCELLED"}
        with pytest.raises(InteropFailure) as cancelled:
            await task
        assert (cancelled.value.code, cancelled.value.status) == ("CANCELLED", 409)
        # A late response cannot be delivered after cancellation, and the
        # request id cannot be replayed.
        with pytest.raises(InteropFailure) as late:
            host.delivery_guard(TOKEN, session_id, "request-late")
        assert (late.value.code, late.value.status) == ("CANCELLED", 409)
        with pytest.raises(InteropFailure) as replay:
            await host.run(TOKEN, "request-late", operation, session_id=session_id)
        assert (replay.value.code, replay.value.status) == ("CANCELLED", 409)
        release.set()
        await host.shutdown(timeout=.5)

    _run(scenario())


def test_bound_preview_response_is_refused_after_revocation_or_source_change(session_rig):
    host, provider = session_rig.host, session_rig.provider

    async def scenario():
        session_id = await _connected(session_rig)
        preview = host.context_preview(TOKEN, ContextPreviewInput(session_id=session_id,
                                                                  request_id="request-bound"))
        assert preview["preview_id"]
        host.delivery_guard(TOKEN, session_id, "request-bound")  # unchanged authority
        host.permission_revoke(TOKEN, PermissionRevokeInput(session_id=session_id,
                                                            permission_id="task_status"))
        with pytest.raises(InteropFailure) as stale_permission:
            host.delivery_guard(TOKEN, session_id, "request-bound")
        assert (stale_permission.value.code, stale_permission.value.status) == ("PERMISSION_DENIED", 403)

        # A fresh binding whose source version changes before delivery is refused.
        original = provider.snapshot
        provider.snapshot = lambda *args, **kwargs: {**original(*args, **kwargs),
                                                     "source_version": "source-changed"}
        try:
            second = host.context_preview(TOKEN, ContextPreviewInput(session_id=session_id,
                                                                      request_id="request-source"))
            assert second["preview_id"]
            provider.snapshot = lambda *args, **kwargs: {**original(*args, **kwargs),
                                                         "source_version": "source-moved"}
            with pytest.raises(InteropFailure) as changed:
                host.delivery_guard(TOKEN, session_id, "request-source")
            assert (changed.value.code, changed.value.status) == ("SOURCE_CHANGED", 409)
        finally:
            provider.snapshot = original
        await host.shutdown(timeout=.5)

    _run(scenario())

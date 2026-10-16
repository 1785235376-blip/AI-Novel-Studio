"""Bounded regression checks for newly added Desktop host projections."""
from __future__ import annotations

import json

import pytest
from test_local_interop_host import env as _runtime_env
from test_local_interop_host import run

from app.local_interop.api import PermissionRevokeInput, SessionInput, create_local_interop_router

env = _runtime_env


@pytest.mark.parametrize("projection", ["status", "permission-revoke"])
def test_queued_desktop_projection_cannot_restore_a_later_revoked_permission(env, projection):
    e = env

    async def scenario():
        sid = await e.connect()
        routes = {route.path: route.endpoint for route in create_local_interop_router(e.host).routes}
        if projection == "status":
            response = await routes["/api/local-interop/status"](session_id=sid, x_session_token="author")
        else:
            response = await routes["/api/local-interop/permissions/revoke"](
                PermissionRevokeInput(session_id=sid, permission_id="selection"), x_session_token="author")

        sent = []

        async def send(message):
            if message["type"] == "http.response.start":
                e.host.permission_revoke("author", PermissionRevokeInput(session_id=sid, permission_id="deep_link"))
            sent.append(message)

        try:
            await response({"type": "http"}, None, send)
            delivered = json.loads(sent[-1]["body"])
            # A typed stale/permission error or a fresh narrowed snapshot is safe.
            if "desktop" in delivered:
                permissions = delivered["desktop"]["connections"][0]["permissions"]
                assert next(row for row in permissions if row["id"] == "deep_link")["state"] == "REVOKED"
            else:
                assert delivered["code"] in {"PERMISSION_DENIED", "CONTEXT_STALE", "SESSION_REVOKED", "CANCELLED"}
        finally:
            await e.host.shutdown()

    run(scenario)


def test_queued_desktop_status_cannot_reassert_a_stopped_standing_grant(env):
    e = env

    async def scenario():
        sid = await e.connect()
        e.subscribe(sid)
        routes = {route.path: route.endpoint for route in create_local_interop_router(e.host).routes}
        response = await routes["/api/local-interop/status"](session_id=sid, x_session_token="author")
        sent = []

        async def send(message):
            if message["type"] == "http.response.start":
                e.host.event_unsubscribe("author", SessionInput(session_id=sid))
            sent.append(message)

        try:
            await response({"type": "http"}, None, send)
            delivered = json.loads(sent[-1]["body"])
            if "desktop" in delivered:
                connection = delivered["desktop"]["connections"][0]
                assert connection["standing_permissions"] == []
                assert connection["standing_metadata_fields"] == []
            else:
                assert delivered["code"] in {"PERMISSION_DENIED", "CONTEXT_STALE", "SESSION_REVOKED", "CANCELLED"}
        finally:
            await e.host.shutdown()

    run(scenario)

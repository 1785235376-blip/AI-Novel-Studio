"""Browser-to-Host APIs; X-Session-Token is never sent to the peer.

The browser chooses bounded IDs and consent, while authoritative fields and
source text come exclusively from the Host provider. No generic RPC exists.
"""
from __future__ import annotations

import asyncio
import json
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from local_interop_protocol import (
    HandoffTarget,
    InteropError,
    OpaqueId,
    ProtocolViolation,
)

from .errors import InteropFailure
from .host import DIAGNOSTIC_FIELDS, METADATA_FIELDS


def error_response(exc):
    code = exc.code if isinstance(exc, (InteropFailure, ProtocolViolation)) else "INVALID_MESSAGE"
    status = exc.status if isinstance(exc, InteropFailure) else 409 if isinstance(exc, ProtocolViolation) else 400
    return JSONResponse(status_code=status, content=InteropError(code=code, message=code).model_dump(mode="json"))


class SafeRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def handle(request):
            try:
                # No LAN listener/client, reflected validation inputs, query
                # credential, or arbitrary request-body allocation is admitted.
                if request.client is None or request.client.host != "127.0.0.1":
                    raise InteropFailure("TRANSPORT_ERROR", 403)
                if any(key not in {"session_id", "after"} for key in request.query_params):
                    raise InteropFailure("INVALID_MESSAGE", 400)
                raw = bytearray()
                async for chunk in request.stream():
                    raw.extend(chunk)
                    if len(raw) > 96 * 1024: raise InteropFailure("INVALID_MESSAGE", 413)
                request._body = bytes(raw)
                return await handler(request)
            except (InteropFailure, ProtocolViolation, RequestValidationError, ValidationError):
                import sys
                return error_response(sys.exception())
        return handle


class BrowserInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    request_id: OpaqueId = Field(default_factory=lambda: "request-" + uuid4().hex)


class ScopeInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    workspace_id: OpaqueId
    project_id: OpaqueId
    storyline_id: OpaqueId
    branch_id: OpaqueId


class SettingsInput(BrowserInput):
    enabled: bool


class DiscoveryInput(BrowserInput):
    endpoint: str = Field(min_length=1, max_length=128)


class ConnectInput(DiscoveryInput):
    scope: ScopeInput
    project_id: OpaqueId | None = None
    module: OpaqueId
    surface: OpaqueId
    chapter_id: OpaqueId | None = None
    task_id: OpaqueId | None = None


class SessionInput(BrowserInput):
    session_id: OpaqueId


class ContextPreviewInput(SessionInput):
    chapter_id: OpaqueId | None = None
    expected_chapter_version: int | None = Field(default=None, ge=0)
    selection_start: int | None = Field(default=None, ge=0)
    selection_end: int | None = Field(default=None, ge=0)
    content_kind: Literal["NONE", "SELECTION", "CHAPTER", "SPECIFIC_CONTEXT"] = "NONE"
    context_ids: list[OpaqueId] = Field(default_factory=list, max_length=4)
    metadata_fields: list[Literal["task", "error", "model", "runtime"]] = Field(default_factory=lambda: sorted(METADATA_FIELDS), max_length=4)


class EventPreviewInput(SessionInput):
    metadata_fields: list[Literal["task", "error", "model", "runtime"]] = Field(default_factory=list, max_length=4)


class EventSubscribeInput(SessionInput):
    preview_id: OpaqueId
    confirmed: bool


class DiagnosticPreviewInput(SessionInput):
    fields: list[Literal["software_id", "software_version", "feature", "error_code", "task_state", "runtime", "model", "capability_state"]] = Field(default_factory=lambda: sorted(DIAGNOSTIC_FIELDS), max_length=8)


class AskInput(SessionInput):
    preview_id: OpaqueId
    confirmed: bool
    question: str | None = Field(default=None, min_length=1, max_length=2000)


class VerifyInput(SessionInput):
    guidance_id: OpaqueId


class HandoffInput(SessionInput):
    handoff: HandoffTarget
    explicit_click: bool


class PermissionRevokeInput(SessionInput):
    permission_id: Literal["app_status", "task_status", "model_metadata", "diagnostics", "selection", "current_chapter", "specific_context", "standing_metadata_events", "deep_link"]


class CancelInput(BrowserInput):
    session_id: OpaqueId | None = None


class CasePreviewInput(SessionInput):
    result_id: OpaqueId


class CaseApproveInput(SessionInput):
    candidate_id: OpaqueId
    confirmed: bool


class AuthorityJSONResponse(JSONResponse):
    """Recheck at actual response-send boundary, not only in the route."""
    def __init__(self, content, guard):
        super().__init__(content, headers={"Cache-Control": "no-store"})
        self.guard = guard

    async def __call__(self, scope, receive, send):
        try: self.guard()
        except (InteropFailure, ProtocolViolation) as exc:
            await error_response(exc)(scope, receive, send)
            return
        async def guarded_send(message):
            if message["type"] == "http.response.start":
                # A revocation can occur while the header frame is awaited.
                # Omit a fixed length so a safe typed error may replace the body.
                message = {**message, "headers": [(k, v) for k, v in message["headers"] if k.lower() != b"content-length"]}
            elif message["type"] == "http.response.body" and message.get("body"):
                try: self.guard()
                except (InteropFailure, ProtocolViolation) as exc:
                    message = {"type": "http.response.body", "body": error_response(exc).body, "more_body": False}
            await send(message)
        await super().__call__(scope, receive, guarded_send)


class AuthorityEventResponse(StreamingResponse):
    """Every SSE body frame rechecks live authority immediately before ASGI send."""
    def __init__(self, content, guard):
        super().__init__(content, media_type="text/event-stream", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
        self.guard = guard
        self.revoked = False
        self.ended = False

    async def __call__(self, scope, receive, send):
        async def guarded_send(message):
            if self.ended: return
            if message["type"] == "http.response.body" and message.get("body"):
                try: self.guard()
                except (InteropFailure, ProtocolViolation): self.revoked = True
                if self.revoked:
                    # Suppress queued/serialized bytes after revocation; clean EOF.
                    message = {"type": "http.response.body", "body": b"", "more_body": False}
                    self.ended = True
            if not self.revoked or message["type"] == "http.response.body" and not message.get("more_body"):
                await send(message)
        await super().__call__(scope, receive, guarded_send)


def create_local_interop_router(host, *, prefix="/api/local-interop"):
    router = APIRouter(prefix=prefix, tags=["local-interop"], route_class=SafeRoute)
    def reply(value, token, sid=None):
        represented = host._session(token, sid) if sid else None
        generation = represented.permission_generation if represented else None
        desktop_guard = host.desktop_response_guard(token, value) if isinstance(value, dict) and "desktop" in value else None
        def guard():
            host.delivery_guard(token, sid, value.get("request_id") if isinstance(value, dict) else None)
            if represented and represented.permission_generation != generation:
                raise InteropFailure("PERMISSION_DENIED", 403)
            if desktop_guard: desktop_guard()
            if represented and isinstance(value, dict) and value.get("subscription_active") and value.get("subscription_id"):
                host._event_guard(represented, value["subscription_id"], token)
        return AuthorityJSONResponse(value, guard)

    @router.get("/status")
    async def status(session_id: str | None = None, x_session_token: str | None = Header(None)):
        value = host.status(x_session_token, session_id)
        snapshot_guard = host.desktop_response_guard(x_session_token, value)
        def guard():
            host.status_guard(x_session_token, session_id)
            snapshot_guard()
        return AuthorityJSONResponse(value, guard)

    @router.post("/settings")
    async def settings(body: SettingsInput, x_session_token: str | None = Header(None)):
        return reply(host.configure(x_session_token, body.enabled), x_session_token)

    @router.post("/discovery")
    async def discovery(body: DiscoveryInput, x_session_token: str | None = Header(None)):
        result = await host.run(x_session_token, body.request_id, lambda: host.discover(x_session_token, body))
        return reply(result, x_session_token)

    @router.post("/connect")
    async def connect(body: ConnectInput, x_session_token: str | None = Header(None)):
        result = await host.run(x_session_token, body.request_id, lambda: host.connect(x_session_token, body))
        return reply(result, x_session_token, result["session_id"])

    @router.post("/context/preview")
    async def context_preview(body: ContextPreviewInput, x_session_token: str | None = Header(None)):
        return reply(host.context_preview(x_session_token, body), x_session_token, body.session_id)

    @router.get("/context/sources")
    async def context_sources(session_id: str, x_session_token: str | None = Header(None)):
        return reply(host.sources(x_session_token, session_id), x_session_token, session_id)

    @router.post("/ask")
    async def ask(body: AskInput, x_session_token: str | None = Header(None)):
        result = await host.run(x_session_token, body.request_id, lambda: host.ask(x_session_token, body), session_id=body.session_id)
        return reply(result, x_session_token, body.session_id)

    @router.post("/diagnostics/preview")
    async def diagnostic_preview(body: DiagnosticPreviewInput, x_session_token: str | None = Header(None)):
        return reply(host.diagnostic_preview(x_session_token, body), x_session_token, body.session_id)

    @router.post("/diagnostics/share")
    async def diagnostic_share(body: AskInput, x_session_token: str | None = Header(None)):
        result = await host.run(x_session_token, body.request_id, lambda: host.ask(x_session_token, body, diagnostic=True), session_id=body.session_id)
        return reply(result, x_session_token, body.session_id)

    @router.post("/verify")
    async def verify(body: VerifyInput, x_session_token: str | None = Header(None)):
        result = await host.run(x_session_token, body.request_id, lambda: host.verify(x_session_token, body), session_id=body.session_id)
        return reply(result, x_session_token, body.session_id)

    @router.post("/handoff")
    async def handoff(body: HandoffInput, x_session_token: str | None = Header(None)):
        return reply(host.handoff(x_session_token, body), x_session_token, body.session_id)

    @router.get("/models")
    async def models(session_id: str, x_session_token: str | None = Header(None)):
        return reply(host.model_registry(x_session_token, session_id), x_session_token, session_id)

    @router.post("/case/preview")
    async def case_preview(body: CasePreviewInput, x_session_token: str | None = Header(None)):
        return reply(host.case_preview(x_session_token, body), x_session_token, body.session_id)

    @router.post("/case/approve")
    async def case_approve(body: CaseApproveInput, x_session_token: str | None = Header(None)):
        return reply(host.case_approve(x_session_token, body), x_session_token, body.session_id)

    @router.post("/events/preview")
    async def event_preview(body: EventPreviewInput, x_session_token: str | None = Header(None)):
        return reply(host.event_preview(x_session_token, body), x_session_token, body.session_id)

    @router.post("/events/subscribe")
    async def event_subscribe(body: EventSubscribeInput, x_session_token: str | None = Header(None)):
        async def approve(): return host.event_subscribe(x_session_token, body)
        result = await host.run(x_session_token, body.request_id, approve, session_id=body.session_id)
        return reply(result, x_session_token, body.session_id)

    @router.post("/events/unsubscribe")
    async def event_unsubscribe(body: SessionInput, x_session_token: str | None = Header(None)):
        return reply(host.event_unsubscribe(x_session_token, body), x_session_token, body.session_id)

    @router.get("/events")
    async def events(session_id: str, after: int = Query(0, ge=0), x_session_token: str | None = Header(None)):
        value = host.events(x_session_token, session_id, after)
        session = host._session(x_session_token, session_id)
        grant_id = session.event_grant_id
        return AuthorityJSONResponse(value, lambda: host._event_guard(session, grant_id, x_session_token) if grant_id else host._session(x_session_token, session_id))

    @router.get("/events/stream")
    async def events_stream(request: Request, session_id: str, after: int = Query(0, ge=0), x_session_token: str | None = Header(None)):
        session = host._session(x_session_token, session_id)
        grant_id = session.event_grant_id
        host._event_guard(session, grant_id, x_session_token)
        async def stream():
            cursor = after
            while not await request.is_disconnected():
                try:
                    host._event_guard(session, grant_id, x_session_token)
                    result = host.events(x_session_token, session_id, cursor, capture=False)
                except (InteropFailure, ProtocolViolation): return
                for event in result["events"]:
                    try: host._event_guard(session, grant_id, x_session_token)
                    except (InteropFailure, ProtocolViolation): return
                    cursor = event["sequence"]
                    yield ("data: " + json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n\n").encode()
                await asyncio.sleep(host.event_interval)
        return AuthorityEventResponse(stream(), lambda: host._event_guard(session, grant_id, x_session_token))

    @router.post("/cancel")
    async def cancel(body: CancelInput, x_session_token: str | None = Header(None)):
        return AuthorityJSONResponse(host.cancel(x_session_token, body.request_id, body.session_id), lambda: host._owner(x_session_token))

    @router.post("/permissions/revoke")
    async def permission_revoke(body: PermissionRevokeInput, x_session_token: str | None = Header(None)):
        return reply(host.permission_revoke(x_session_token, body), x_session_token, body.session_id)

    @router.post("/events/pause")
    async def event_pause(body: SessionInput, x_session_token: str | None = Header(None)):
        return reply(host.event_unsubscribe(x_session_token, body), x_session_token, body.session_id)

    @router.post("/disconnect-revoke")
    async def disconnect_revoke(body: SessionInput, x_session_token: str | None = Header(None)):
        return reply(await host.disconnect_revoke(x_session_token, body), x_session_token)

    @router.post("/disconnect")
    async def disconnect(body: SessionInput, x_session_token: str | None = Header(None)):
        return reply(host.disconnect(x_session_token, body.session_id), x_session_token)

    return router

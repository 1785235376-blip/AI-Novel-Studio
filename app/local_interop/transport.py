"""Development transport: exact IPv4 loopback, no proxy, redirect or URL token.

Production packaging must opt into a current-user Named Pipe implementation;
constructing this object never scans ports or starts another application.
"""
from __future__ import annotations

import asyncio
import json
from urllib.parse import urlsplit

import httpx

from local_interop_protocol import (
    PROTOCOL_NAME,
    PROTOCOL_VERSION,
    InteropError,
    ProtocolViolation,
    parse_wire,
)

from .errors import InteropFailure

MAX_WIRE_BYTES = 256 * 1024
OPERATIONS = frozenset({"discovery", "hello", "negotiate", "session", "tutor", "diagnostics", "verify", "cancel", "heartbeat", "disconnect", "events"})


def assert_endpoint(endpoint):
    try:
        url = urlsplit(endpoint)
        if (url.scheme != "http" or url.hostname != "127.0.0.1" or not url.port or
                url.username is not None or url.password is not None or url.path not in {"", "/"} or
                url.query or url.fragment or "\\" in endpoint):
            raise ValueError()
    except (ValueError, TypeError):
        raise InteropFailure("TRANSPORT_ERROR", 400) from None
    return endpoint.rstrip("/")


class LoopbackTransport:
    def __init__(self, endpoint, *, timeout=4.0):
        self.endpoint = assert_endpoint(endpoint)
        self.timeout = min(max(float(timeout), 0.05), 10.0)
        self._closed = False
        self._inflight = set()

    async def request(self, operation, message=None, *, token=None, before_send=None):
        if self._closed: raise InteropFailure("TRANSPORT_ERROR", 503)
        task = asyncio.current_task()
        self._inflight.add(task)
        try:
            return await self._exchange(operation, message, token=token, before_send=before_send)
        finally:
            self._inflight.discard(task)

    async def shutdown(self, *, timeout=.25):
        """Prove local cookie-free client closure, not remote data recall."""
        self._closed = True
        pending = {task for task in self._inflight if task is not asyncio.current_task()}
        for task in pending: task.cancel()
        if pending:
            _, pending = await asyncio.wait(pending, timeout=max(0.0, min(float(timeout), 1.0)))
        # Each request leaves _inflight only after its AsyncClient context has
        # closed. Cancellation-resistant requests therefore cannot claim CLOSED.
        return not pending and not self._inflight

    async def _exchange(self, operation, message=None, *, token=None, before_send=None):
        if operation not in OPERATIONS: raise InteropFailure("TRANSPORT_ERROR", 400)
        payload = message.model_dump(mode="json") if hasattr(message, "model_dump") else message
        raw = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode() if payload is not None else None
        if raw is not None and len(raw) > MAX_WIRE_BYTES: raise InteropFailure("INVALID_MESSAGE", 413)
        headers = {"Accept": "application/json", "Accept-Encoding": "identity", "X-Interop-Protocol-Name": PROTOCOL_NAME, "X-Interop-Protocol-Version": PROTOCOL_VERSION}
        if token:
            if not isinstance(token, str) or not 24 <= len(token) <= 256 or any(c.isspace() for c in token):
                raise InteropFailure("SESSION_REQUIRED", 401)
            headers["Authorization"] = "Bearer " + token
        if raw is not None: headers["Content-Type"] = "application/json"
        body = raw
        if before_send:
            before_send()
            class GuardedBody(httpx.AsyncByteStream):
                async def __aiter__(self):
                    before_send()  # Immediately before yielding unsent body bytes.
                    if raw is not None: yield raw
            body = GuardedBody()
            headers["Content-Length"] = str(len(raw or b""))
        try:
            # A fresh cookie-free client prevents any credential/cookie carryover.
            async with httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=self.timeout) as client:  # noqa: SIM117 - lifetime explicitly encloses bounded streamed response
                async with client.stream("GET" if operation == "discovery" else "POST",
                        self.endpoint + "/interop/v1/" + operation, headers=headers, content=body) as response:
                    if response.headers.get("content-encoding", "identity") != "identity": raise InteropFailure("TRANSPORT_ERROR", 502)
                    if response.is_redirect: raise InteropFailure("TRANSPORT_ERROR", 502)
                    chunks = bytearray()
                    async for chunk in response.aiter_bytes():
                        chunks.extend(chunk)
                        if len(chunks) > MAX_WIRE_BYTES: raise InteropFailure("INVALID_MESSAGE", 502)
                    if response.status_code >= 400:
                        try: error = parse_wire(InteropError, bytes(chunks))
                        except ProtocolViolation: raise InteropFailure("TRANSPORT_ERROR", 502) from None
                        raise InteropFailure(error.code, 502 if response.status_code >= 500 else 409)
                    return bytes(chunks)
        except asyncio.CancelledError:
            raise
        except httpx.TimeoutException:
            raise InteropFailure("TIMEOUT", 504) from None
        except (httpx.HTTPError, ValueError):
            raise InteropFailure("TRANSPORT_ERROR", 502) from None

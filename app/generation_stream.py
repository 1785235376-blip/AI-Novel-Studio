"""Per-observer authority at the SSE transport boundary.

The credential remains in a request-local closure, never in a Job or receipt.
Revoking an observer closes only this response; it does not cancel shared work.
"""
import threading

import anyio

from starlette.responses import StreamingResponse


class AuthorizedGenerationResponse(StreamingResponse):
    def __init__(self, content, *, authorize, stop_event: threading.Event, **kwargs):
        super().__init__(content, **kwargs)
        self._authorize_observer = authorize
        self._observer_stopped = stop_event

    async def stream_response(self, send):
        await send({"type": "http.response.start", "status": self.status_code,
                    "headers": self.raw_headers})
        async for chunk in self.body_iterator:
            # The synchronous iterator runs in a worker thread. Check again
            # after that handoff, immediately before committing these bytes
            # to ASGI; there is no await between this check and send().
            if self._observer_stopped.is_set() or not self._authorize_observer():
                break
            if not isinstance(chunk, (bytes, memoryview)):
                chunk = chunk.encode(self.charset)
            await send({"type": "http.response.body", "body": chunk, "more_body": True})
        await send({"type": "http.response.body", "body": b"", "more_body": False})

    async def __call__(self, scope, receive, send):
        # ASGI 2.4 StreamingResponse relies on send() errors for disconnects.
        # An idle private stream may have no send for ten seconds, so retain a
        # receive-side watcher as well and stop its iterator immediately.
        try:
            async with anyio.create_task_group() as group:
                async def stream():
                    try:
                        await self.stream_response(send)
                    finally:
                        self._observer_stopped.set()
                        group.cancel_scope.cancel()

                async def disconnect():
                    await self.listen_for_disconnect(receive)
                    self._observer_stopped.set()
                    group.cancel_scope.cancel()

                group.start_soon(stream)
                await disconnect()
        finally:
            self._observer_stopped.set()
        if self.background is not None:
            await self.background()

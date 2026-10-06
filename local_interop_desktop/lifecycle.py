"""Best-effort bridge composition cannot hold up application startup or exit."""

from __future__ import annotations

import asyncio
import inspect
from collections import deque
from dataclasses import dataclass
from typing import Callable

from .transport import InteropTransport


@dataclass(frozen=True)
class ShutdownReport:
    completed: tuple[str, ...]
    timed_out: tuple[str, ...]
    error_codes: tuple[str, ...]


class InteropLifecycleCoordinator:
    """Hooks are nonblocking async product-owned operations; no business store here.

    A host bridge can be injected by implementing start()/disconnect()/shutdown().
    A restart factory must return a newly initialized host with a fresh instance.
    Shutdown never waits for an adapter that suppresses cooperative cancellation.
    """

    def __init__(
        self,
        transport,
        *,
        revoke_subscriptions: Callable | None = None,
        close_sessions: Callable | None = None,
        flush_audit: Callable | None = None,
        restart_factory: Callable | None = None,
    ):
        self.transport = transport
        self.revoke_subscriptions = revoke_subscriptions
        self.close_sessions = close_sessions
        self.flush_audit = flush_audit
        self.restart_factory = restart_factory
        self.events = deque(maxlen=64)
        self.app_is_ready = False
        self.closed = False
        self.last_shutdown: ShutdownReport | None = None
        self._stragglers: set[asyncio.Task] = set()

    def _event(self, event: str) -> None:
        self.events.append(event)

    async def app_start(self) -> bool:
        self.closed = False
        self._event("APP_START")
        # App startup does not imply bridge startup or permit opening a listener.
        return True

    async def app_ready(self) -> bool:
        self.app_is_ready = True
        self._event("APP_READY")
        return True

    async def bridge_start(self) -> bool:
        self._event("BRIDGE_START")
        try:
            return await self.transport.start() is not False
        except Exception:
            self._event("BRIDGE_UNAVAILABLE")
            return False

    async def peer_found(self, peer, **kwargs):
        self._event("PEER_FOUND")
        result = await self.transport.connect(peer, **kwargs)
        self._event("HANDSHAKE")
        self._event("SESSION_READY")
        return result

    async def app_sleep(self) -> None:
        self._event("APP_SLEEP")
        await self.transport.disconnect()

    async def peer_lost(self, peer=None) -> None:
        self._event("PEER_LOST")
        if peer is None:
            await self.transport.disconnect()
        else:
            await self.transport.disconnect(peer=peer)

    async def session_revoked(self, peer=None) -> None:
        self._event("SESSION_REVOKED")
        if peer is None:
            await self.transport.disconnect()
        else:
            await self.transport.disconnect(peer=peer)

    def _reap(self, task: asyncio.Task) -> None:
        self._stragglers.discard(task)
        if not task.cancelled():
            task.exception()

    async def _call(self, callback, deadline: float) -> bool:
        async def invoke():
            result = callback()
            if inspect.isawaitable(result):
                return await result
            return result

        task = asyncio.create_task(invoke())
        self._stragglers.add(task)
        task.add_done_callback(self._reap)
        done, _ = await asyncio.wait(
            {task}, timeout=max(0, deadline - asyncio.get_running_loop().time())
        )
        if not done:
            task.cancel()
            return False
        task.result()
        return True

    async def shutdown(self, *, timeout: float = 1) -> ShutdownReport:
        if not 0 <= timeout <= 30:
            raise ValueError("Invalid shutdown deadline")
        self._event("APP_SHUTDOWN")
        self.closed, self.app_is_ready = True, False
        deadline = asyncio.get_running_loop().time() + timeout
        completed, timed_out, errors = [], [], []
        # Immediately invalidate local authority before waiting for external hooks.
        invalidate = getattr(self.transport, "_invalidate", None)
        if invalidate is not None:
            invalidate()
        steps = (
            ("REVOKE_SUBSCRIPTIONS", self.revoke_subscriptions),
            ("CLOSE_SESSIONS", self.close_sessions),
            ("FLUSH_AUDIT", self.flush_audit),
            (
                "CLOSE_TRANSPORT",
                lambda: self.transport.shutdown(
                    timeout=max(0, deadline - asyncio.get_running_loop().time())
                ),
            ),
        )
        for name, callback in steps:
            if callback is None:
                continue
            try:
                if await self._call(callback, deadline):
                    completed.append(name)
                else:
                    timed_out.append(name)
            except Exception:
                errors.append("TRANSPORT_ERROR")
        self.last_shutdown = ShutdownReport(tuple(completed), tuple(timed_out), tuple(errors))
        return self.last_shutdown

    async def restart(self) -> bool:
        self._event("CRASH_RECOVERY")
        previous = self.transport
        old_instance = getattr(previous, "instance_id", None)
        await self.shutdown()
        if self.restart_factory is None:
            raise ValueError("Restart requires a new transport and adapter factory")
        replacement = self.restart_factory()
        if isinstance(previous, InteropTransport) and isinstance(replacement, InteropTransport):
            if replacement.adapter is previous.adapter:
                raise ValueError("Restart cannot reuse the old adapter or OS handles")
            if (
                replacement.session is not None
                or replacement.state.value != "STOPPED"
                or replacement._subscriptions
            ):
                raise ValueError("Restart factory must return a fresh unauthorized transport")
        if replacement is previous or (
            old_instance is not None and getattr(replacement, "instance_id", None) == old_instance
        ):
            raise ValueError("Restart must create a fresh instance without restored grants")
        self.transport = replacement
        self._event("RESTART")
        await self.app_start()
        await self.app_ready()
        return await self.bridge_start()

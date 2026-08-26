from __future__ import annotations

from dataclasses import dataclass, field
from heapq import heappop, heappush
from itertools import count
from threading import Timer
from typing import Callable


class ThreadingScheduler:
    def call_later(self, delay: float, callback: Callable[[], None]) -> Timer:
        timer = Timer(max(0.0, delay), callback)
        timer.daemon = True
        timer.start()
        return timer


@dataclass(order=True)
class _FakeHandle:
    due: float
    order: int
    callback: Callable[[], None] = field(compare=False)
    cancelled: bool = field(default=False, compare=False)

    def cancel(self) -> None:
        self.cancelled = True


class FakeScheduler:
    """Deterministic scheduler for tests and host-controlled event loops."""

    def __init__(self) -> None:
        self.now = 0.0
        self._queue: list[_FakeHandle] = []
        self._orders = count()

    def call_later(self, delay: float, callback: Callable[[], None]) -> _FakeHandle:
        handle = _FakeHandle(self.now + max(0.0, delay), next(self._orders), callback)
        heappush(self._queue, handle)
        return handle

    def advance(self, seconds: float) -> None:
        target = self.now + seconds
        while self._queue and self._queue[0].due <= target:
            handle = heappop(self._queue)
            self.now = handle.due
            if not handle.cancelled:
                handle.callback()
        self.now = target


"""Bounded TaskCenter cursor metadata; never an authority or task cache.

The HTTP adapter must still perform its original authorization, scope fencing,
bounded readers and current safe-projection checks before and after each page.
Only a caller with reliable existing owner/session/permission lifecycle evidence
may opt in with supported=True. This module cannot establish that evidence.

Each observation stores three digests, page size, observed count and one fixed
deadline. Tokens contain a random handle, a non-sensitive page position and an
HMAC. They contain no query, task text, credentials, private path or digest.
No business or credential files are read or written. Supported HTTP adapters
retain all original owner checks; default callers receive UNSUPPORTED.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
import hashlib
import hmac
import json
import math
import os
import re
import secrets
from threading import RLock
import time


MAX_TOKEN_BYTES = 160
MAX_OBSERVED_TOTAL = 1_000_000
MAX_TTL_SECONDS = 900
MAX_CAPACITY = 1024
MAX_PAGE_SIZE = 100
_DIGEST = re.compile(r"[a-f0-9]{64}\Z")
_TOKEN = re.compile(r"tc1\.([A-Za-z0-9_-]{43})\.([1-9][0-9]{0,6})\.([A-Za-z0-9_-]{43})\Z")
_DOMAIN = b"PoemSeedStudio.TaskCenterCursor.v1\x00"


class TaskCenterCursorInvalid(ValueError):
    def __init__(self):
        super().__init__("TASKCENTER_QUERY_INVALID")


class TaskCenterCursorRestart(ValueError):
    def __init__(self):
        super().__init__("TASKCENTER_CURSOR_RESTART_REQUIRED")


class TaskCenterCursorUnsupported(RuntimeError):
    def __init__(self):
        super().__init__("TASKCENTER_CURSOR_UNSUPPORTED")


@dataclass(frozen=True)
class CursorPage:
    offset: int
    next_cursor: str | None
    has_more: bool
    # Internal, bounded final-return receipt; never included in HTTP responses.
    _receipt: object = field(default=None, repr=False, compare=False)


@dataclass(frozen=True)
class _ReturnReceipt:
    issuer: object
    epoch: object
    observation: object
    handle: str | None
    position: tuple


@dataclass(frozen=True)
class _Observation:
    binding: str
    query: str
    projection: str
    limit: int
    total: int
    deadline: float


def canonical_digest(value) -> str:
    """Hash caller-selected canonical evidence; this does not validate authority.

    Never use a hash of reusable actor/scope strings as a lifecycle incarnation.
    The caller must obtain lifecycle evidence from the original authority owners.
    """
    try:
        raw = json.dumps(value, ensure_ascii=True, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("ascii")
    except (TypeError, ValueError, OverflowError, RecursionError):
        raise TaskCenterCursorInvalid() from None
    return hashlib.sha256(raw).hexdigest()


def _strict_int(value, lower, upper):
    if type(value) is not int or not lower <= value <= upper:
        raise TaskCenterCursorInvalid()


def _digest(value):
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise TaskCenterCursorInvalid()
    return value


class TaskCenterCursorEngine:
    """Process-local FIFO observations with a fixed, non-sliding TTL.

    Capacity counts observations, not page tokens. Advancing or replaying a
    cursor does not create another entry or evict its own observation, even
    with capacity=1. New first-page observations may evict the oldest entry.
    An expired, evicted, restarted, forked or different-worker observation must
    restart. An engine inherited across fork rejects every page until the child
    constructs a new instance. A token is never authorization and cannot
    restore a prior result.

    Binding must cover project, branch/scope, actor and session, original
    project incarnation and reliable relevant permission lifecycle evidence.
    Query must cover exact filter semantics, page size and ordering version.
    Projection must cover the complete current bounded safe ordered projection,
    revisions and public coverage/truncation evidence, not only this page.
    Supplying those digests is a trusted internal opt-in, not an HTTP option.
    """
    def __init__(self, *, ttl_seconds=300, capacity=128, max_page_size=100,
                 clock=time.monotonic):
        _strict_int(ttl_seconds, 1, MAX_TTL_SECONDS)
        _strict_int(capacity, 1, MAX_CAPACITY)
        _strict_int(max_page_size, 1, MAX_PAGE_SIZE)
        if not callable(clock):
            raise TaskCenterCursorInvalid()
        self._ttl = ttl_seconds
        self._capacity = capacity
        self._max_page_size = max_page_size
        self._clock = clock
        self._states = OrderedDict()
        self._lock = RLock()
        self._key = self._new_key()
        self._pid = os.getpid()
        self._last_now = None
        self._receipt_issuer = object()
        self._receipt_epoch = object()

    @staticmethod
    def _new_key():
        try:
            key = secrets.token_bytes(32)
            if type(key) is not bytes or len(key) != 32:
                raise TaskCenterCursorUnsupported()
            return key
        except Exception:
            raise TaskCenterCursorUnsupported() from None

    def _current_process(self):
        # A fork may copy a held lock. Never acquire or replace inherited state:
        # concurrent first calls in the child must not race a lock/key reset.
        # The child must construct its own engine, with its own signing key.
        if os.getpid() != self._pid:
            raise TaskCenterCursorRestart()

    def _now(self):
        try:
            value = self._clock()
            if (type(value) not in (int, float) or not math.isfinite(value)
                    or not 0 <= value <= 2**53 - MAX_TTL_SECONDS):
                raise TaskCenterCursorUnsupported()
        except Exception:
            self._states.clear()
            self._receipt_epoch = object()
            raise TaskCenterCursorUnsupported() from None
        if self._last_now is not None and value < self._last_now:
            self._states.clear()
            self._receipt_epoch = object()
            self._last_now = value
            raise TaskCenterCursorRestart()
        self._last_now = value
        return value

    def _prune(self, now):
        for handle, observation in list(self._states.items()):
            if now >= observation.deadline:
                self._states.pop(handle, None)

    def _handle(self):
        try:
            for _ in range(8):
                handle = secrets.token_urlsafe(32)
                if (isinstance(handle, str)
                        and re.fullmatch(r"[A-Za-z0-9_-]{43}", handle)
                        and handle not in self._states):
                    return handle
        except Exception:
            pass
        raise TaskCenterCursorUnsupported() from None

    def _encode(self, handle, offset):
        body = "tc1." + handle + "." + str(offset)
        signature = hmac.new(self._key, _DOMAIN + body.encode("ascii"),
                             hashlib.sha256).digest()
        import base64
        encoded = base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")
        return body + "." + encoded

    def _decode(self, token):
        if (not isinstance(token, str) or not token.isascii()
                or not 1 <= len(token) <= MAX_TOKEN_BYTES):
            raise TaskCenterCursorInvalid()
        match = _TOKEN.fullmatch(token)
        if match is None:
            raise TaskCenterCursorInvalid()
        handle, raw_offset, _ = match.groups()
        offset = int(raw_offset)
        if not hmac.compare_digest(self._encode(handle, offset), token):
            raise TaskCenterCursorRestart()
        return handle, offset

    def page(self, *, binding, query, projection, observed_total, limit,
             token=None, supported=False) -> CursorPage:
        """Return a position after the caller rereads its authorized projection.

        Malformed input is INVALID. Unknown, changed, expired or tampered
        well-shaped cursors uniformly require a restart without echoing input.
        Context mismatch does not poison the original valid observation.
        """
        if type(supported) is not bool:
            raise TaskCenterCursorInvalid()
        if not supported:
            raise TaskCenterCursorUnsupported()
        binding, query, projection = _digest(binding), _digest(query), _digest(projection)
        _strict_int(observed_total, 0, MAX_OBSERVED_TOTAL)
        _strict_int(limit, 1, self._max_page_size)
        if token is not None and not isinstance(token, str):
            raise TaskCenterCursorInvalid()
        self._current_process()
        with self._lock:
            now = self._now()
            self._prune(now)
            if token is None:
                offset = 0
                observation = _Observation(binding, query, projection, limit,
                                           observed_total, now + self._ttl)
                handle = None
            else:
                handle, offset = self._decode(token)
                observation = self._states.get(handle)
                if (observation is None
                        or not hmac.compare_digest(observation.binding, binding)
                        or not hmac.compare_digest(observation.query, query)
                        or not hmac.compare_digest(observation.projection, projection)
                        or observation.limit != limit
                        or observation.total != observed_total
                        or not 0 < offset < observed_total
                        or offset % limit != 0):
                    raise TaskCenterCursorRestart()
            has_more = offset + limit < observed_total
            if has_more and handle is None:
                handle = self._handle()
            next_cursor = self._encode(handle, offset + limit) if has_more else None
            # Check the fixed deadline even for a final page that emits no
            # successor. Reading or issuing a successor never refreshes it.
            if self._now() >= observation.deadline:
                if handle is not None:
                    self._states.pop(handle, None)
                raise TaskCenterCursorRestart()
            if token is None and has_more:
                while len(self._states) >= self._capacity:
                    self._states.popitem(last=False)
                self._states[handle] = observation
            receipt = _ReturnReceipt(self._receipt_issuer, self._receipt_epoch,
                                     observation, handle, (offset, next_cursor, has_more))
            return CursorPage(offset, next_cursor, has_more, receipt)

    def validate_return(self, page):
        """Recheck a position after the adapter's final owner observations.

        This private receipt is not authorization and is not accepted from HTTP.
        No callback runs under the engine lock; no observation is allocated or
        renewed here. Even an empty/single first page retains its original
        ephemeral deadline, and a last page still binds its input observation.
        """
        self._current_process()
        if (type(page) is not CursorPage or type(page._receipt) is not _ReturnReceipt
                or type(page.offset) is not int or type(page.has_more) is not bool
                or (page.next_cursor is not None and type(page.next_cursor) is not str)):
            raise TaskCenterCursorRestart()
        receipt = page._receipt
        with self._lock:
            now = self._now()
            self._prune(now)
            if (receipt.issuer is not self._receipt_issuer
                    or receipt.epoch is not self._receipt_epoch
                    or receipt.position != (page.offset, page.next_cursor, page.has_more)
                    or now >= receipt.observation.deadline
                    or (receipt.handle is not None
                        and self._states.get(receipt.handle) is not receipt.observation)):
                raise TaskCenterCursorRestart()

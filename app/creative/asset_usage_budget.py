"""Opt-in read limits for saved-reference observations, never write authority.

The legacy storage format is a whole JSON document. A page bounds projection
and reference traversal, not JSON decoding. A 4 MiB encoded document can still
have substantial Python overhead; the conservative input-derived allowance is
512 MiB per decoded document, not a measured process RSS guarantee.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import os
import stat
import time

_active = ContextVar('studio_usage_read_budget', default=None)


class UsageBudgetError(RuntimeError):
    def __init__(self):
        super().__init__('STUDIO_USAGE_RESOURCE_UNAVAILABLE')


class UsageReadBudget:
    MAX_SCOPE_BYTES = 4 * 1024 * 1024
    MAX_READ_BYTES = 256 * 1024 * 1024
    MAX_READS = 1024
    MAX_SECONDS = 30

    def __init__(self):
        self.read_bytes = self.reads = 0
        self.deadline = time.monotonic() + self.MAX_SECONDS

    def check(self):
        if time.monotonic() > self.deadline:
            raise UsageBudgetError()

    def read(self, path, limit=None):
        self.check()
        limit = min(limit or self.MAX_SCOPE_BYTES, self.MAX_SCOPE_BYTES)
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or
                getattr(info, 'st_file_attributes', 0) & 0x400 or info.st_size > limit):
            raise UsageBudgetError()
        self.reads += 1
        remaining = self.MAX_READ_BYTES - self.read_bytes
        if self.reads > self.MAX_READS or info.st_size > remaining:
            raise UsageBudgetError()
        with path.open('rb') as stream:
            opened = os.fstat(stream.fileno())
            if ((opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino) or
                    opened.st_size > min(limit, remaining)):
                raise UsageBudgetError()
            data = stream.read(min(limit, remaining))
            final = os.fstat(stream.fileno())
        self.read_bytes += len(data)
        if final.st_size != len(data) or final.st_size != opened.st_size:
            raise UsageBudgetError()
        self.check()
        try:
            return data.decode('utf-8')
        except UnicodeError:
            raise UsageBudgetError() from None


def current_usage_budget():
    return _active.get()


@contextmanager
def usage_read_budget(enabled=True):
    if not enabled or _active.get() is not None:
        yield _active.get()
        return
    budget = UsageReadBudget()
    token = _active.set(budget)
    try:
        yield budget
    finally:
        _active.reset(token)

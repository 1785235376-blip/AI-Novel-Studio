"""Request-local resource accounting, active only for Studio asset queries."""
from contextlib import contextmanager
from contextvars import ContextVar
import stat
import time

from .asset_query_index import AssetQueryBudgetExceeded, AssetQueryUnavailable

_active = ContextVar("studio_asset_query_budget", default=None)


class AssetQueryReadBudget:
    MAX_METADATA_READS = 100_000
    MAX_METADATA_BYTES = 512 * 1024 * 1024
    MAX_CONTENT_READS = 10_000
    MAX_CONTENT_BYTES = 256 * 1024 * 1024
    MAX_SECONDS = 30.0

    def __init__(self):
        self.deadline = time.monotonic() + self.MAX_SECONDS
        self.metadata_reads = self.metadata_bytes = 0
        self.content_reads = self.content_bytes = 0

    def check(self):
        if time.monotonic() > self.deadline:
            raise AssetQueryBudgetExceeded()

    def charge(self, path, *, content=False):
        self.check()
        info = path.stat(follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode):
            raise AssetQueryUnavailable()
        if content:
            self.content_reads += 1
            self.content_bytes += info.st_size
            exceeded = (self.content_reads > self.MAX_CONTENT_READS
                        or self.content_bytes > self.MAX_CONTENT_BYTES)
        else:
            self.metadata_reads += 1
            self.metadata_bytes += info.st_size
            exceeded = (info.st_size > 1024 * 1024
                        or self.metadata_reads > self.MAX_METADATA_READS
                        or self.metadata_bytes > self.MAX_METADATA_BYTES)
        if exceeded:
            raise AssetQueryBudgetExceeded()


def current_query_budget():
    return _active.get()


@contextmanager
def asset_query_budget():
    budget = AssetQueryReadBudget()
    token = _active.set(budget)
    try:
        yield budget
        budget.check()
    finally:
        _active.reset(token)
